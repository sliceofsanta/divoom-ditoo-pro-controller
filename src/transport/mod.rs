use std::error::Error;
use std::time::Duration;

use log::debug;
use tokio::sync::mpsc;

use crate::protocol::packet::Response;

#[cfg(target_os = "linux")]
mod bluer_transport;
#[cfg(target_os = "macos")]
mod iobluetooth;

#[cfg(target_os = "linux")]
pub(crate) use bluer_transport::DeviceConnection;
#[cfg(target_os = "linux")]
pub use bluer_transport::{find_paired_ditoo_pro_devices, list_paired_devices, scan_devices};
#[cfg(target_os = "macos")]
pub(crate) use iobluetooth::DeviceConnection;
#[cfg(target_os = "macos")]
pub use iobluetooth::{
  find_paired_ditoo_pro_devices, list_paired_devices, macos_bluetooth_host, scan_devices
};

pub(crate) const MAX_CONNECT_ATTEMPTS: u32 = 3;
pub(crate) const INTER_PACKET_DELAY: Duration = Duration::from_millis(40);
pub(crate) const RESPONSE_TIMEOUT: Duration = Duration::from_secs(5);

/// Wait for the response matching `expected_command`, skipping unsolicited
/// responses the device emits on its own (e.g. the undocumented 0xF7 frames).
pub(crate) async fn await_response(
  response_rx: &mut mpsc::UnboundedReceiver<Response>,
  expected_command: u8
) -> Result<Response, Box<dyn Error>> {
  let deadline = tokio::time::Instant::now() + RESPONSE_TIMEOUT;
  loop {
    let response = tokio::time::timeout_at(deadline, response_rx.recv())
      .await
      .map_err(|_| {
        format!(
          "Timed out waiting for response to command 0x{:02x}",
          expected_command
        )
      })?
      .ok_or("Response channel closed")?;
    if response.original_command != expected_command {
      debug!(
        "Skipping unsolicited response for command 0x{:02x}",
        response.original_command
      );
      continue;
    }
    if !response.ack {
      return Err(format!("Device NAK'd command 0x{:02x}", expected_command).into());
    }
    return Ok(response);
  }
}
