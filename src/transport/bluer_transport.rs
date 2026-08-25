use std::error::Error;
use std::time::Duration;

use bluer::Address;
use futures::StreamExt;
use log::{debug, info};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::sync::mpsc;

use crate::protocol::packet::{Packet, Response};
use super::{await_response, INTER_PACKET_DELAY, MAX_CONNECT_ATTEMPTS};

pub async fn scan_devices() -> Result<(), Box<dyn Error>> {
  let session = bluer::Session::new().await?;
  let adapter = session.default_adapter().await?;
  adapter.set_powered(true).await?;

  let duration = Duration::from_secs(20);
  info!("Scanning bluetooth devices for {:?}", duration);

  let discover = adapter.discover_devices().await?;
  tokio::pin!(discover);

  let timeout = tokio::time::sleep(duration);
  tokio::pin!(timeout);

  loop {
    tokio::select! {
      Some(event) = discover.next() => {
        if let bluer::AdapterEvent::DeviceAdded(addr) = event {
          let device = adapter.device(addr)?;
          let name = device.name().await?.unwrap_or_default();
          info!("Found device: {} ({})", name, addr);
        }
      }
      _ = &mut timeout => {
        info!("Scan complete");
        break;
      }
    }
  }

  Ok(())
}

pub async fn find_paired_ditoo_pro_devices() -> Result<Vec<Address>, Box<dyn Error>> {
  let session = bluer::Session::new().await?;
  let adapter = session.default_adapter().await?;

  let addresses = adapter.device_addresses().await?;

  let mut result = Vec::new();
  for addr in addresses {
    let device = adapter.device(addr)?;
    let is_paired = device.is_paired().await?;
    if !is_paired {
      continue;
    }

    let name = device.name().await?.unwrap_or_default();
    if !name.contains("DitooPro") {
      continue;
    }

    result.push(addr);
  }

  Ok(result)
}

pub async fn list_paired_devices() -> Result<(), Box<dyn Error>> {
  let session = bluer::Session::new().await?;
  let adapter = session.default_adapter().await?;

  for addr in find_paired_ditoo_pro_devices().await? {
    let device = adapter.device(addr)?;
    let name = device.name().await?.unwrap_or_default();
    let is_connected = device.is_connected().await?;
    info!(
      "{} ({}) - connected: {}",
      name, addr, is_connected
    );
  }

  Ok(())
}

async fn read_response(reader: &mut bluer::rfcomm::stream::OwnedReadHalf) -> Result<Response, Box<dyn Error + Send + Sync>> {
  let start = reader.read_u8().await?;
  if start != 0x01 {
    return Err(format!("Expected start byte 0x01, got 0x{:02x}", start).into());
  }

  let mut len_bytes = [0u8; 2];
  reader.read_exact(&mut len_bytes).await?;
  let length = u16::from_le_bytes(len_bytes) as usize;

  // Read: payload (length - 2 for checksum) + checksum (2) + end byte (1) = length + 1
  let mut remaining = vec![0u8; length + 1];
  reader.read_exact(&mut remaining).await?;

  let mut frame = vec![0x01];
  frame.extend_from_slice(&len_bytes);
  frame.extend_from_slice(&remaining);

  debug!("Received response: {}", hex::encode(&frame));

  Response::deserialize(&frame)
}

pub(crate) struct DeviceConnection {
  writer: bluer::rfcomm::stream::OwnedWriteHalf,
  _reader_handle: tokio::task::JoinHandle<()>,
  response_rx: mpsc::UnboundedReceiver<Response>,
  _session: bluer::Session,
  _profile_handle: bluer::rfcomm::ProfileHandle,
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
    let session = bluer::Session::new().await?;
    let adapter = session.default_adapter().await?;
    adapter.set_powered(true).await?;

    let spp_uuid = uuid::Uuid::from_u128(0x00001101_0000_1000_8000_00805f9b34fb);

    let profile = bluer::rfcomm::Profile {
      uuid: spp_uuid,
      name: Some("divoom-controller".to_string()),
      role: Some(bluer::rfcomm::Role::Client),
      require_authentication: Some(false),
      require_authorization: Some(false),
      auto_connect: Some(true),
      ..Default::default()
    };

    let mut profile_handle = session.register_profile(profile).await?;
    let device = adapter.device(mac_address)?;

    if !device.is_connected().await? {
      debug!("Device not connected, connecting...");
      device.connect().await?;
    }

    match device.connect_profile(&spp_uuid).await {
      Ok(()) => debug!("connect_profile succeeded"),
      Err(e) => debug!("connect_profile: {} (waiting for profile handle)", e),
    }

    let stream = loop {
      let req = profile_handle.next().await.ok_or("ProfileHandle stream closed")?;
      if req.device() == mac_address {
        break req.accept()?;
      }
    };

    info!("Connected via SDP profile");
    let (reader, writer) = stream.into_split();
    let (tx, rx) = mpsc::unbounded_channel();

    // Spawn background reader task
    let reader_handle = tokio::spawn(async move {
      let mut reader = reader;
      loop {
        match read_response(&mut reader).await {
          Ok(response) => {
            debug!("Background reader got response: {:?}", response);
            if tx.send(response).is_err() {
              debug!("Response channel closed, stopping reader");
              break;
            }
          }
          Err(e) => {
            debug!("Background reader error: {}", e);
            break;
          }
        }
      }
    });

    Ok(DeviceConnection {
      writer,
      _reader_handle: reader_handle,
      response_rx: rx,
      _session: session,
      _profile_handle: profile_handle,
    })
  }

  pub(crate) async fn send_and_receive(&mut self, packet: &Packet) -> Result<Response, Box<dyn Error>> {
    let serialized = packet.serialize()?;
    let expected_command = packet.command.value();
    debug!("send_and_receive 0x{:02x}: {}", expected_command, hex::encode(&serialized));
    self.writer.write_all(&serialized).await?;
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
    self.writer.write_all(&serialized).await?;
    tokio::time::sleep(INTER_PACKET_DELAY).await;
    Ok(())
  }

  pub(crate) async fn disconnect(mut self) -> Result<(), Box<dyn Error>> {
    info!("Disconnecting from device");
    self._reader_handle.abort();
    self.writer.shutdown().await?;
    Ok(())
  }
}
