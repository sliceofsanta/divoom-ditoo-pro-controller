//! macOS transport over IOBluetooth RFCOMM.
//!
//! Characterised against real hardware (see CLAUDE.md "Running it from macOS"):
//! - The Ditoo's SPP service is an unnamed SDP record on RFCOMM channel 2;
//!   macOS's cached service list never shows it, so we probe a candidate list.
//! - An active audio link (A2DP/HFP) makes every RFCOMM open fail with
//!   kIOReturnError, so the audio connection is closed first; the RFCOMM open
//!   re-establishes the baseband link itself.
//! - RFCOMM opens only succeed from the **process main thread** — the same
//!   sequence fails instantly with kIOReturnError from any other thread. So on
//!   macOS the main thread runs a small Bluetooth host loop
//!   ([`macos_bluetooth_host`]) and the async CLI logic runs on a tokio runtime
//!   on a second thread. `main.rs` wires this up.
//! - TCC kills any process touching IOBluetooth unless the binary embeds
//!   NSBluetoothAlwaysUsageDescription (done in build.rs) and the responsible
//!   app has a Bluetooth grant in System Settings.

use std::cell::RefCell;
use std::error::Error;
use std::ffi::c_void;
use std::rc::Rc;
use std::sync::OnceLock;
use std::time::{Duration, Instant};

use log::{debug, info};
use objc2::rc::Retained;
use objc2::runtime::AnyObject;
use objc2::{define_class, msg_send, AllocAnyThread, DefinedClass};
use objc2_foundation::{NSDate, NSDefaultRunLoopMode, NSObject, NSRunLoop, NSString};
use objc2_io_bluetooth::{IOBluetoothDevice, IOBluetoothRFCOMMChannel};
use tokio::sync::{mpsc, oneshot};

use crate::address::Address;
use crate::protocol::packet::{Packet, Response};
use super::{await_response, INTER_PACKET_DELAY, MAX_CONNECT_ATTEMPTS};

/// RFCOMM channels to probe, in order. The Ditoo Pro's SPP lives on channel 2;
/// other Divoom models use 1 (MiniToo) or 4 (Timebox Mini). Opens on wrong
/// channels fail fast, so probing is cheap.
const CHANNEL_CANDIDATES: [u8; 6] = [2, 1, 4, 3, 5, 6];

/// RFCOMM writes must not exceed the channel MTU; the RFCOMM minimum is 127
/// bytes, so chunking at that size is always safe.
const WRITE_CHUNK: usize = 127;

const KIO_RETURN_SUCCESS: i32 = 0;

enum ThreadCmd {
  Write(Vec<u8>),
  Disconnect
}

struct ConnectRequest {
  mac_address: Address,
  ready_tx: oneshot::Sender<Result<(), String>>,
  cmd_rx: mpsc::UnboundedReceiver<ThreadCmd>,
  response_tx: mpsc::UnboundedSender<Response>
}

static HOST_TX: OnceLock<mpsc::UnboundedSender<ConnectRequest>> = OnceLock::new();

struct DelegateIvars {
  buffer: Rc<RefCell<Vec<u8>>>
}

define_class!(
  #[unsafe(super(NSObject))]
  #[name = "DitooRfcommDelegate"]
  #[ivars = DelegateIvars]
  struct RfcommDelegate;

  /// `IOBluetoothRFCOMMChannelDelegate` is an informal protocol; IOBluetooth
  /// checks `respondsToSelector:` at runtime, so implementing the selectors on
  /// a plain NSObject subclass is sufficient.
  impl RfcommDelegate {
    #[unsafe(method(rfcommChannelData:data:length:))]
    fn rfcomm_channel_data(&self, _channel: *mut AnyObject, data: *mut c_void, length: usize) {
      if data.is_null() || length == 0 {
        return;
      }
      let bytes = unsafe { std::slice::from_raw_parts(data as *const u8, length) };
      self.ivars().buffer.borrow_mut().extend_from_slice(bytes);
    }
  }
);

impl RfcommDelegate {
  fn new(buffer: Rc<RefCell<Vec<u8>>>) -> Retained<Self> {
    let this = Self::alloc().set_ivars(DelegateIvars { buffer });
    unsafe { msg_send![super(this), init] }
  }
}

fn pump_run_loop(seconds: f64) {
  unsafe {
    let run_loop = NSRunLoop::currentRunLoop();
    let date = NSDate::dateWithTimeIntervalSinceNow(seconds);
    run_loop.runMode_beforeDate(NSDefaultRunLoopMode, &date);
  }
}

/// Split complete protocol frames out of the receive buffer and forward them.
fn drain_frames(buffer: &Rc<RefCell<Vec<u8>>>, response_tx: &mpsc::UnboundedSender<Response>) {
  let mut buf = buffer.borrow_mut();
  loop {
    if buf.is_empty() {
      return;
    }
    // Resynchronize on the start marker if the stream got misaligned.
    if buf[0] != 0x01 {
      let skip = buf.iter().position(|&b| b == 0x01).unwrap_or(buf.len());
      debug!("Discarding {} bytes before start marker", skip);
      buf.drain(..skip);
      continue;
    }
    if buf.len() < 3 {
      return;
    }
    let frame_len = u16::from_le_bytes([buf[1], buf[2]]) as usize + 4;
    if buf.len() < frame_len {
      return;
    }
    let frame: Vec<u8> = buf.drain(..frame_len).collect();
    debug!("Received response: {}", hex::encode(&frame));
    match Response::deserialize(&frame) {
      Ok(response) => {
        if response_tx.send(response).is_err() {
          return;
        }
      }
      Err(e) => debug!("Dropping invalid frame: {}", e)
    }
  }
}

fn write_chunked(channel: &IOBluetoothRFCOMMChannel, bytes: &[u8]) -> Result<(), String> {
  for chunk in bytes.chunks(WRITE_CHUNK) {
    let status = unsafe {
      channel.writeSync_length(chunk.as_ptr() as *mut c_void, chunk.len() as u16)
    };
    if status != KIO_RETURN_SUCCESS {
      return Err(format!("writeSync failed with IOReturn {}", status));
    }
  }
  Ok(())
}

/// Serve one connection until the async side disconnects. Must run on the
/// process main thread (see module docs).
fn run_connection(request: ConnectRequest) {
  let ConnectRequest {
    mac_address,
    ready_tx,
    mut cmd_rx,
    response_tx
  } = request;

  let ns_mac = NSString::from_str(&mac_address.to_string());
  let Some(device) = (unsafe { IOBluetoothDevice::deviceWithAddressString(Some(&ns_mac)) }) else {
    let _ = ready_tx.send(Err(format!("No Bluetooth device for address {}", mac_address)));
    return;
  };

  // An active audio link blocks RFCOMM opens; drop it first. The RFCOMM open
  // below re-establishes the baseband connection without the audio profiles.
  if unsafe { device.isConnected() } {
    debug!("Device connected (audio); closing connection before RFCOMM open");
    let status = unsafe { device.closeConnection() };
    debug!("closeConnection -> {}", status);
    let deadline = Instant::now() + Duration::from_secs(5);
    while unsafe { device.isConnected() } && Instant::now() < deadline {
      pump_run_loop(0.05);
    }
    std::thread::sleep(Duration::from_millis(500));
  }

  let buffer = Rc::new(RefCell::new(Vec::new()));
  let delegate = RfcommDelegate::new(Rc::clone(&buffer));

  let mut channel: Option<Retained<IOBluetoothRFCOMMChannel>> = None;
  for candidate in CHANNEL_CANDIDATES {
    let mut opened: Option<Retained<IOBluetoothRFCOMMChannel>> = None;
    let status = unsafe {
      device.openRFCOMMChannelSync_withChannelID_delegate(
        Some(&mut opened),
        candidate,
        Some(&delegate)
      )
    };
    if status == KIO_RETURN_SUCCESS {
      if let Some(ch) = opened {
        info!("Connected via IOBluetooth RFCOMM channel {}", candidate);
        channel = Some(ch);
        break;
      }
    }
    debug!("RFCOMM channel {} open failed: IOReturn {}", candidate, status);
  }

  let Some(channel) = channel else {
    let _ = ready_tx.send(Err(format!(
      "Could not open an RFCOMM channel (tried {:?})",
      CHANNEL_CANDIDATES
    )));
    return;
  };

  if ready_tx.send(Ok(())).is_err() {
    unsafe { channel.closeChannel() };
    return;
  }

  loop {
    objc2::rc::autoreleasepool(|_| {
      pump_run_loop(0.02);
    });
    drain_frames(&buffer, &response_tx);

    match cmd_rx.try_recv() {
      Ok(ThreadCmd::Write(bytes)) => {
        if let Err(e) = write_chunked(&channel, &bytes) {
          debug!("Write failed, closing connection: {}", e);
          break;
        }
      }
      Ok(ThreadCmd::Disconnect) => break,
      Err(mpsc::error::TryRecvError::Disconnected) => break,
      Err(mpsc::error::TryRecvError::Empty) => {}
    }
  }

  drain_frames(&buffer, &response_tx);
  unsafe { channel.closeChannel() };
  // The baseband link is left up on purpose: macOS re-attaches the audio
  // profiles on demand, and tearing the link down here would race with that.
}

/// Run the async program body while this (main) thread serves IOBluetooth
/// connection requests.
///
/// IOBluetooth RFCOMM only works from the process main thread, so on macOS
/// `main()` must call this instead of `#[tokio::main]`: the closure's future
/// runs on a tokio runtime on a second thread, and every
/// [`DeviceConnection::connect`] it performs is served here.
pub fn macos_bluetooth_host<F>(
  future: impl FnOnce() -> F + Send + 'static
) -> Result<(), Box<dyn Error>>
where
  F: std::future::Future<Output = Result<(), String>>
{
  let (host_tx, mut host_rx) = mpsc::unbounded_channel();
  HOST_TX
    .set(host_tx)
    .map_err(|_| "Bluetooth host started twice")?;

  let runtime_thread = std::thread::Builder::new()
    .name("tokio-main".to_string())
    .spawn(move || -> Result<(), String> {
      let runtime = tokio::runtime::Builder::new_multi_thread()
        .enable_all()
        .build()
        .map_err(|e| e.to_string())?;
      runtime.block_on(future())
    })?;

  loop {
    if runtime_thread.is_finished() {
      break;
    }
    match host_rx.try_recv() {
      Ok(request) => run_connection(request),
      Err(mpsc::error::TryRecvError::Disconnected) => break,
      Err(mpsc::error::TryRecvError::Empty) => {
        std::thread::sleep(Duration::from_millis(20));
      }
    }
  }

  runtime_thread
    .join()
    .map_err(|_| "Async runtime thread panicked")?
    .map_err(|e| -> Box<dyn Error> { e.into() })
}

pub(crate) struct DeviceConnection {
  cmd_tx: mpsc::UnboundedSender<ThreadCmd>,
  response_rx: mpsc::UnboundedReceiver<Response>
}

impl DeviceConnection {
  pub(crate) async fn connect(mac_address: Address) -> Result<Self, Box<dyn Error>> {
    info!("Connecting to device with MAC address {}", mac_address);

    for attempt in 1..=MAX_CONNECT_ATTEMPTS {
      if attempt > 1 {
        info!("Retrying connection (attempt {}/{})..", attempt, MAX_CONNECT_ATTEMPTS);
        tokio::time::sleep(Duration::from_secs(1)).await;
      }

      match Self::try_connect(mac_address).await {
        Ok(conn) => return Ok(conn),
        Err(e) => {
          debug!("Connection attempt {} failed: {}", attempt, e);
        }
      }
    }

    Err("Failed to connect to device".into())
  }

  async fn try_connect(mac_address: Address) -> Result<Self, Box<dyn Error>> {
    let host_tx = HOST_TX.get().ok_or(
      "IOBluetooth host is not running. On macOS the program must be started \
       through macos_bluetooth_host() so the main thread can serve Bluetooth."
    )?;

    let (ready_tx, ready_rx) = oneshot::channel();
    let (cmd_tx, cmd_rx) = mpsc::unbounded_channel();
    let (response_tx, response_rx) = mpsc::unbounded_channel();

    host_tx
      .send(ConnectRequest {
        mac_address,
        ready_tx,
        cmd_rx,
        response_tx
      })
      .map_err(|_| "Bluetooth host loop is gone")?;

    match ready_rx.await {
      Ok(Ok(())) => Ok(DeviceConnection { cmd_tx, response_rx }),
      Ok(Err(message)) => Err(message.into()),
      Err(_) => Err("Bluetooth host dropped the connection request".into())
    }
  }

  pub(crate) async fn send_and_receive(&mut self, packet: &Packet) -> Result<Response, Box<dyn Error>> {
    let serialized = packet.serialize()?;
    let expected_command = packet.command.value();
    debug!("send_and_receive 0x{:02x}: {}", expected_command, hex::encode(&serialized));
    self
      .cmd_tx
      .send(ThreadCmd::Write(serialized))
      .map_err(|_| "Bluetooth host connection is gone")?;
    tokio::time::sleep(INTER_PACKET_DELAY).await;
    await_response(&mut self.response_rx, expected_command).await
  }


  /// Take every response waiting in the channel, without blocking.
  ///
  /// The daemon only ever fires and forgets, so nothing else consumes this
  /// channel -- and the device sends unsolicited frames of its own accord.
  /// Left undrained it grows for as long as the daemon runs.
  pub(crate) fn drain_responses(&mut self) -> Vec<Response> {
    let mut out = Vec::new();
    while let Ok(response) = self.response_rx.try_recv() {
      out.push(response);
    }
    out
  }

  pub(crate) async fn fire_and_forget(&mut self, packet: &Packet) -> Result<(), Box<dyn Error>> {
    let serialized = packet.serialize()?;
    debug!("fire_and_forget 0x{:02x}: {}", packet.command.value(), hex::encode(&serialized));
    self
      .cmd_tx
      .send(ThreadCmd::Write(serialized))
      .map_err(|_| "Bluetooth host connection is gone")?;
    tokio::time::sleep(INTER_PACKET_DELAY).await;
    Ok(())
  }

  pub(crate) async fn disconnect(self) -> Result<(), Box<dyn Error>> {
    info!("Disconnecting from device");
    let _ = self.cmd_tx.send(ThreadCmd::Disconnect);
    Ok(())
  }
}

fn paired_ditoo_devices_blocking() -> Vec<(String, Address, bool)> {
  let mut result = Vec::new();
  let Some(devices) = (unsafe { IOBluetoothDevice::pairedDevices() }) else {
    return result;
  };
  for obj in devices.iter() {
    let Some(device) = obj.downcast_ref::<IOBluetoothDevice>() else {
      continue;
    };
    let name = unsafe { device.name() }.to_string();
    if !name.contains("DitooPro") {
      continue;
    }
    let Some(addr_string) = (unsafe { device.addressString() }) else {
      continue;
    };
    let Ok(address) = addr_string.to_string().parse::<Address>() else {
      continue;
    };
    let connected = unsafe { device.isConnected() };
    result.push((name, address, connected));
  }
  result
}

pub async fn find_paired_ditoo_pro_devices() -> Result<Vec<Address>, Box<dyn Error>> {
  let devices = tokio::task::spawn_blocking(paired_ditoo_devices_blocking).await?;
  Ok(devices.into_iter().map(|(_, addr, _)| addr).collect())
}

pub async fn list_paired_devices() -> Result<(), Box<dyn Error>> {
  let devices = tokio::task::spawn_blocking(paired_ditoo_devices_blocking).await?;
  for (name, address, connected) in devices {
    info!("{} ({}) - connected: {}", name, address, connected);
  }
  Ok(())
}

pub async fn scan_devices() -> Result<(), Box<dyn Error>> {
  Err(
    "Scanning is not supported on macOS yet. \
     Pair the device in System Settings > Bluetooth, then use the `devices` command."
      .into()
  )
}
