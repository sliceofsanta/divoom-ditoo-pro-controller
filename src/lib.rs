use std::error::Error;
use std::fs::File;
use std::io::BufReader;
use std::path::Path;
use std::time::Duration;
#[cfg(feature = "video")]
use std::thread;

use chrono::{NaiveDateTime, NaiveTime};
use image::{DynamicImage, Rgb};
#[cfg(feature = "video")]
use image::RgbImage;
#[cfg(feature = "video")]
use indexmap::IndexSet;
use log::{debug, info};
#[cfg(feature = "video")]
use tokio::sync::mpsc;

use crate::divoom_file_format::animation::Animation as DivoomAnimation;
#[cfg(feature = "video")]
use crate::divoom_file_format::frame::Frame;
#[cfg(feature = "video")]
use crate::divoom_file_format::frame_header::FrameHeader;

#[cfg(target_os = "macos")]
mod address;
pub mod divoom_file_format;
pub mod protocol;
mod transport;

#[cfg(target_os = "linux")]
pub use bluer::Address;
#[cfg(target_os = "macos")]
pub use address::Address;
pub use transport::{find_paired_ditoo_pro_devices, list_paired_devices, scan_devices};
#[cfg(target_os = "macos")]
pub use transport::macos_bluetooth_host;

use crate::protocol::alarm::Alarm;
use crate::protocol::animation::{Animation, ControlWord};
use crate::protocol::command::Command;
use crate::protocol::datetime::DateTime;
use crate::protocol::packet::Packet;
use crate::transport::DeviceConnection;


fn create_network_packets_from(animation: &[u8]) -> Result<Vec<Packet>, Box<dyn Error>> {
  let mut packets = Vec::<Packet>::new();
  packets.push(Packet {
    command: Command::Animation,
    payload: Animation {
      control_word: ControlWord::StartSeeding,
      file_size: animation.len() as u32,
      offset_id: 0,
      image_part: Vec::new()
    }
    .serialize()?
  });

  let mut animation_packets = animation
    .chunks(256)
    .enumerate()
    .map(|(index, chunk)| {
      Ok(Packet {
        command: Command::Animation,
        payload: Animation {
          control_word: ControlWord::SendingData,
          file_size: animation.len() as u32,
          offset_id: index as u16,
          image_part: chunk.to_vec()
        }
        .serialize()?
      })
    })
    .collect::<Result<Vec<_>, Box<dyn Error>>>()?;
  packets.append(&mut animation_packets);

  Ok(packets)
}

pub async fn send_alarm(mac_address: Address) -> Result<(), Box<dyn Error>> {
  let alarm = Alarm {
    index: 0,
    enable: false,
    time: NaiveTime::from_hms_opt(13, 37, 0).ok_or("Invalid time")?,
    repeat: 0,
    mode: 0,
    trigger_mode: 0,
    fm: [0, 0],
    volume: 100
  };
  let packet = Packet {
    command: Command::Alarm,
    payload: alarm.serialize()?
  };
  let mut conn = DeviceConnection::connect(mac_address).await?;
  conn.fire_and_forget(&packet).await?;
  conn.disconnect().await?;
  Ok(())
}

pub async fn send_divoom_animation(
  mac_address: Address,
  reader: &mut (dyn std::io::Read + Send)
) -> Result<(), Box<dyn Error>> {
  let mut animation = Vec::new();
  reader.read_to_end(&mut animation)?;

  let packets = create_network_packets_from(&animation)?;
  let mut conn = DeviceConnection::connect(mac_address).await?;
  for (index, packet) in packets.iter().enumerate() {
    info!("Sending packet {}/{}..", index + 1, packets.len());
    conn.fire_and_forget(packet).await?;
  }
  conn.disconnect().await?;
  Ok(())
}

pub async fn send_set_datetime(
  mac_address: Address,
  datetime: NaiveDateTime
) -> Result<(), Box<dyn Error>> {
  let payload = DateTime { datetime };
  let packet = Packet {
    command: Command::SetDateTime,
    payload: payload.serialize()?
  };
  let mut conn = DeviceConnection::connect(mac_address).await?;
  conn.fire_and_forget(&packet).await?;
  conn.disconnect().await?;
  Ok(())
}

pub async fn send_set_brightness(
  mac_address: Address,
  brightness: u8
) -> Result<(), Box<dyn Error>> {
  let packet = Packet {
    command: Command::SetBrightness,
    payload: vec![brightness]
  };
  let mut conn = DeviceConnection::connect(mac_address).await?;
  conn.fire_and_forget(&packet).await?;
  conn.disconnect().await?;
  Ok(())
}

pub async fn send_set_volume(
  mac_address: Address,
  volume: u8
) -> Result<(), Box<dyn Error>> {
  let packet = Packet {
    command: Command::SetVolume,
    payload: vec![volume]
  };
  let mut conn = DeviceConnection::connect(mac_address).await?;
  conn.fire_and_forget(&packet).await?;
  conn.disconnect().await?;
  Ok(())
}

pub async fn send_set_play_status(
  mac_address: Address,
  playing: bool
) -> Result<(), Box<dyn Error>> {
  let packet = Packet {
    command: Command::SetPlayStatus,
    payload: vec![if playing { 1 } else { 0 }]
  };
  let mut conn = DeviceConnection::connect(mac_address).await?;
  conn.fire_and_forget(&packet).await?;
  conn.disconnect().await?;
  Ok(())
}

pub async fn send_get_volume(
  mac_address: Address,
) -> Result<u8, Box<dyn Error>> {
  let packet = Packet {
    command: Command::GetVolume,
    payload: vec![]
  };
  let mut conn = DeviceConnection::connect(mac_address).await?;
  let response = conn.send_and_receive(&packet).await?;
  conn.disconnect().await?;
  let volume = response.data.first()
    .ok_or("GetVolume response contained no data")?;
  Ok(*volume)
}

pub async fn send_set_box_mode(
  mac_address: Address,
  payload: Vec<u8>
) -> Result<(), Box<dyn Error>> {
  let packet = Packet {
    command: Command::SetBoxMode,
    payload
  };
  let mut conn = DeviceConnection::connect(mac_address).await?;
  conn.fire_and_forget(&packet).await?;
  conn.disconnect().await?;
  Ok(())
}

pub async fn send_set_clock_face(
  mac_address: Address,
  clock_id: u16
) -> Result<(), Box<dyn Error>> {
  let packet = protocol::extended_command::build_packet(
    protocol::extended_command::SET_USER_DEFINE_TIME,
    &clock_id.to_le_bytes(),
  );
  let mut conn = DeviceConnection::connect(mac_address).await?;
  conn.fire_and_forget(&packet).await?;
  conn.disconnect().await?;
  Ok(())
}

pub async fn send_get_clock_face(
  mac_address: Address,
) -> Result<u16, Box<dyn Error>> {
  let packet = protocol::extended_command::build_packet(
    protocol::extended_command::GET_USER_DEFINE_TIME,
    &[],
  );
  let mut conn = DeviceConnection::connect(mac_address).await?;
  let response = conn.send_and_receive(&packet).await?;
  conn.disconnect().await?;
  if response.data.len() < 3 {
    return Err("GetClockFace response too short".into());
  }
  let clock_id = u16::from_le_bytes([response.data[1], response.data[2]]);
  Ok(clock_id)
}

pub async fn send_set_language(
  mac_address: Address,
  lang_index: u8
) -> Result<(), Box<dyn Error>> {
  let packet = protocol::extended_command::build_packet(
    protocol::extended_command::SET_LANGUAGE,
    &[lang_index],
  );
  let mut conn = DeviceConnection::connect(mac_address).await?;
  conn.fire_and_forget(&packet).await?;
  conn.disconnect().await?;
  Ok(())
}

pub async fn send_keyboard_backlight(
  mac_address: Address,
  mode: u8
) -> Result<(), Box<dyn Error>> {
  let packet = Packet {
    command: Command::LightArrowSwitch,
    payload: protocol::keyboard_backlight::serialize(mode)
  };
  let mut conn = DeviceConnection::connect(mac_address).await?;
  conn.fire_and_forget(&packet).await?;
  conn.disconnect().await?;
  Ok(())
}

#[cfg(feature = "text")]
#[allow(clippy::too_many_arguments)]
pub async fn send_scrolling_text(
  mac_address: Address,
  font_path: &Path,
  text: &str,
  font_size: f32,
  fg_color: [u8; 3],
  bg_color: [u8; 3],
  halign: protocol::scrolling_text::HAlign,
  valign: protocol::scrolling_text::VAlign,
) -> Result<(), Box<dyn Error>> {
  let scrolling_text = protocol::scrolling_text::build_scrolling_text_frames(font_path, text, font_size, fg_color, bg_color, halign, valign)?;
  let mut conn = DeviceConnection::connect(mac_address).await?;

  conn.fire_and_forget(&Packet {
    command: Command::DrawingCtrlMoviePlay,
    payload: vec![0x00],
  }).await?;

  conn.fire_and_forget(&Packet {
    command: Command::DrawingCtrlMoviePlay,
    payload: vec![0x01],
  }).await?;

  let speed: u16 = 60;
  let total = scrolling_text.encoded_frames.len();
  for (index, encoded_data) in scrolling_text.encoded_frames.iter().enumerate() {
    let data_len = encoded_data.len() as u16;
    let mut payload = Vec::new();
    payload.extend_from_slice(&speed.to_le_bytes());
    payload.extend_from_slice(&data_len.to_le_bytes());
    payload.extend_from_slice(encoded_data);

    let packet = Packet {
      command: Command::DrawingEncodeMoviePlay,
      payload,
    };

    if index % 100 == 0 {
      info!("Sending frame {}/{}..", index + 1, total);
    }
    conn.fire_and_forget(&packet).await?;
    tokio::time::sleep(Duration::from_millis(20)).await;
  }

  conn.fire_and_forget(&Packet {
    command: Command::DrawingCtrlMoviePlay,
    payload: vec![0x00],
  }).await?;

  conn.disconnect().await?;
  Ok(())
}


#[cfg(feature = "text")]
#[allow(clippy::too_many_arguments)]
pub async fn send_static_text(
  mac_address: Address,
  font_path: &Path,
  text: &str,
  font_size: f32,
  fg_color: [u8; 3],
  bg_color: [u8; 3],
  halign: protocol::scrolling_text::HAlign,
  valign: protocol::scrolling_text::VAlign,
) -> Result<(), Box<dyn Error>> {
  let image = protocol::static_text::build_static_text_image(font_path, text, font_size, fg_color, bg_color, halign, valign)?;
  let animation = DivoomAnimation::from_image(image)?;
  let mut buf = Vec::new();
  animation.save_to_divoom_format(&mut buf)?;
  let packets = create_network_packets_from(&buf)?;
  let mut conn = DeviceConnection::connect(mac_address).await?;
  for (index, packet) in packets.iter().enumerate() {
    info!("Sending packet {}/{}..", index + 1, packets.len());
    conn.fire_and_forget(packet).await?;
  }
  conn.disconnect().await?;
  Ok(())
}

pub async fn send_image(
  mac_address: Address,
  filename: &str
) -> Result<(), Box<dyn Error>> {
  let animation = if filename.ends_with(".gif") || filename.ends_with(".GIF") {
    DivoomAnimation::from_gif(&mut BufReader::new(File::open(filename)?))?
  } else {
    DivoomAnimation::from_image(image::open(filename)?)?
  };
  let mut buf = Vec::new();
  animation.save_to_divoom_format(&mut buf)?;
  let packets = create_network_packets_from(&buf)?;
  let mut conn = DeviceConnection::connect(mac_address).await?;
  for (index, packet) in packets.iter().enumerate() {
    info!("Sending packet {}/{}..", index + 1, packets.len());
    conn.fire_and_forget(packet).await?;
  }
  conn.disconnect().await?;
  Ok(())
}

/// Timings that govern how a state is presented over time. Defaults are the
/// sensible ones; every field can be overridden by an environment variable,
/// which is what makes the escalation path testable without sitting through
/// five real minutes.
#[derive(Debug, Clone, Copy)]
pub struct Timings {
  /// How long a blocked alert runs before it escalates. Escalation is what
  /// makes the alert useful: quiet enough to ignore for a minute, impossible
  /// to ignore after five.
  pub alert_escalate: Duration,
  pub alert_panic: Duration,
  /// Success and error are events, not conditions -- they play, then the
  /// display falls back to idle rather than sitting on a stale verdict.
  pub transient: Duration,
  /// A celebration has to be earned or it stops meaning anything. A turn that
  /// finishes in seconds just goes quietly idle.
  pub celebrate_after: Duration,
  /// How long the panel sits idle before falling through to `screensaver`, if
  /// such a face exists. Zero disables it.
  pub screensaver_after: Duration
}

impl Default for Timings {
  fn default() -> Self {
    Timings {
      alert_escalate: Duration::from_secs(60),
      alert_panic: Duration::from_secs(300),
      transient: Duration::from_secs(6),
      celebrate_after: Duration::from_secs(600),
      screensaver_after: Duration::from_secs(1800)
    }
  }
}

impl Timings {
  /// Override any field from the environment; anything unset or unparseable
  /// keeps its default.
  pub fn from_env() -> Self {
    fn secs(key: &str, fallback: Duration) -> Duration {
      std::env::var(key)
        .ok()
        .and_then(|v| v.parse::<u64>().ok())
        .map(Duration::from_secs)
        .unwrap_or(fallback)
    }
    let base = Timings::default();
    Timings {
      alert_escalate: secs("DITOO_ALERT_ESCALATE_SECS", base.alert_escalate),
      alert_panic: secs("DITOO_ALERT_PANIC_SECS", base.alert_panic),
      transient: secs("DITOO_TRANSIENT_SECS", base.transient),
      celebrate_after: secs("DITOO_CELEBRATE_AFTER_SECS", base.celebrate_after),
      screensaver_after: secs("DITOO_SCREENSAVER_AFTER_SECS", base.screensaver_after)
    }
  }
}

/// Paint a context-usage bar along the bottom row of every frame.
///
/// This composites over the artwork, so it is opt-in: the faces are drawn by
/// hand and overwriting a row of them is a decision the owner should make, not
/// a default. Enabled by writing a percentage to the `context` file.
///
/// The bar reads left-to-right and warms as it fills, so a glance says both
/// "how full" and "how worried" without needing to resolve individual pixels.
fn overlay_context_gauge(animation: &mut DivoomAnimation, percent: u8) {
  let percent = percent.min(100);
  let lit = (16 * percent as u32).div_ceil(100);
  if lit == 0 {
    return;
  }
  // Green until it matters, amber past half, red when a compact is imminent.
  let colour = match percent {
    0..=59 => Rgb([40, 190, 120]),
    60..=84 => Rgb([240, 175, 60]),
    _ => Rgb([255, 70, 70])
  };
  for frame in &mut animation.frames {
    // to_rgb8() rather than as_mut_rgb8(): frames decoded from a GIF are
    // RGBA8, so asking for RGB8 in place yields None and the overlay silently
    // does nothing -- which then leaves the rebuilt palette empty and the
    // encode fails with "Pixel not found in palette".
    let mut image = frame.image.to_rgb8();
    for x in 0..lit.min(16) {
      image.put_pixel(x, 15, colour);
    }
    frame.image = DynamicImage::ImageRgb8(image);
    frame.header.reuse_palette = false;
  }
  rebuild_palettes(animation);
}

/// Recompute each frame's palette from its pixels. Needed after compositing,
/// since `save_to_divoom_format` looks colours up in the palette and errors on
/// any pixel it cannot find.
fn rebuild_palettes(animation: &mut DivoomAnimation) {
  for frame in &mut animation.frames {
    let mut palette: Vec<Rgb<u8>> = Vec::new();
    for pixel in frame.image.to_rgb8().pixels() {
      if !palette.contains(pixel) {
        palette.push(*pixel);
      }
    }
    frame.header.color_count = palette.len() as u8;
    frame.local_palette = palette.clone();
    frame.palette = palette;
  }
}

/// A session whose state file has not been touched in this long is treated as
/// gone. Without this a crashed session would pin the panel to "working"
/// forever, and the display would be lying about work nobody is doing.
const SESSION_STALE_AFTER: Duration = Duration::from_secs(900);

/// How much a state deserves the panel when several sessions want it at once.
///
/// The ordering answers the question the display exists to answer: does
/// anything need me? So a session blocked on input outranks every amount of
/// busy work, and a failure outranks activity.
fn priority(state: &str) -> u8 {
  match state {
    "alerting" => 100,
    "error" => 90,
    "compacting" => 70,
    "working" => 60,
    "thinking" => 50,
    "success" => 40,
    "chilling" => 10,
    _ => 5
  }
}

/// Merge the states several Claude Code sessions are asking for into the one
/// the panel should show. Returns None when no session has anything to say.
fn merge_sessions(states: &[(String, Duration)]) -> Option<String> {
  states
    .iter()
    .filter(|(_, age)| *age < SESSION_STALE_AFTER)
    .max_by_key(|(state, _)| priority(state))
    .map(|(state, _)| state.clone())
}

/// Read each live session's requested state from `dir`, newest-first on ties.
fn read_sessions(dir: &Path) -> Vec<(String, Duration)> {
  let now = std::time::SystemTime::now();
  let Ok(entries) = std::fs::read_dir(dir) else {
    return Vec::new();
  };
  let mut out = Vec::new();
  for entry in entries.flatten() {
    let path = entry.path();
    if !path.is_file() {
      continue;
    }
    let Ok(contents) = std::fs::read_to_string(&path) else {
      continue;
    };
    let state = contents.trim().to_string();
    if state.is_empty() {
      continue;
    }
    let age = entry
      .metadata()
      .and_then(|m| m.modified())
      .ok()
      .and_then(|t| now.duration_since(t).ok())
      .unwrap_or(Duration::ZERO);
    out.push((state, age));
  }
  out
}

/// How many times the daemon will rebuild a dropped connection before giving
/// up and letting the caller fall back to one-shot sends.
const MAX_DAEMON_RECONNECTS: u32 = 5;

/// States that mean "Claude is doing something", for the purpose of deciding
/// whether a finish was worth celebrating.
fn is_busy(state: &str) -> bool {
  matches!(state, "thinking" | "working" | "compacting")
}

/// Decide what a finish actually means. Only `success` is gated: a celebration
/// has to be earned or it stops carrying information, so a turn that wrapped
/// up in seconds goes quietly idle instead. Every other state passes through.
fn resolve_finish<'a>(state: &'a str, worked_for: Duration, timings: &Timings) -> &'a str {
  if state == "success" && worked_for < timings.celebrate_after {
    "chilling"
  } else {
    state
  }
}

/// Map a requested state plus how long it has been held onto the face to show.
///
/// This is where time-dependent behaviour lives, so the hooks stay dumb: they
/// report what happened and the daemon decides how to present it.
fn present<'a>(state: &'a str, held: Duration, timings: &Timings) -> &'a str {
  match state {
    "alerting" if held >= timings.alert_panic => "alerting3",
    "alerting" if held >= timings.alert_escalate => "alerting2",
    "success" | "error" if held >= timings.transient => "chilling",
    // A long idle stretch falls through to a screensaver, if one is installed.
    // Only from idle: never interrupt a state that is telling you something.
    "chilling"
      if !timings.screensaver_after.is_zero() && held >= timings.screensaver_after =>
    {
      "screensaver"
    }
    other => other
  }
}

/// Run the status daemon: connect once, hold the connection, and apply state
/// changes written to `state_file` (the name of an image in `faces_dir`,
/// without extension).
///
/// This exists because connecting is expensive in every sense: it takes
/// seconds, and on devices like the Ditoo Pro each connect/disconnect plays a
/// chime that no volume setting silences. Holding one connection turns
/// per-state-change chimes into a single pair at daemon start and stop.
///
/// Returns with an error if a send fails (the connection has usually died);
/// the caller is expected to restart or fall back to one-shot commands.
pub async fn run_status_daemon(
  mac_address: Address,
  state_file: &Path,
  faces_dir: &Path
) -> Result<(), Box<dyn Error>> {
  let conn = DeviceConnection::connect(mac_address).await?;
  info!(
    "Status daemon connected; watching {} for states from {}",
    state_file.display(),
    faces_dir.display()
  );

  let applied_file = state_file.with_file_name("applied");
  let sessions_dir = state_file.with_file_name("sessions");
  let context_file = state_file.with_file_name("context");
  let run_dir = state_file.parent().unwrap_or(faces_dir);
  let mut last_context: Option<u8> = None;
  // `requested` is what the hooks asked for; `displayed` is the face actually
  // on the panel. They differ whenever a state is being presented over time --
  // an alert that has escalated, or a verdict that has decayed to idle.
  // `last_seen` is the raw value from the file; `requested` is what it
  // resolved to. They differ whenever resolution rewrites a state (an unearned
  // success becoming idle), and comparing the file against the RESOLVED value
  // would then re-enter this branch on every tick -- resetting the timer and
  // losing the work duration.
  let mut last_seen = String::new();
  let mut requested = String::new();
  let mut requested_since = tokio::time::Instant::now();
  let mut displayed: Option<String> = None;
  let mut busy_since: Option<tokio::time::Instant> = None;
  let mut worked_for = Duration::ZERO;
  let timings = Timings::from_env();
  // A held connection can be torn down underneath us -- macOS re-attaching the
  // audio profile shows up as kIOReturnNotOpen on the next write, and after a
  // long idle the whole host connection can go. Reconnecting costs one chime;
  // dying costs the whole feature until someone notices the panel is stale.
  //
  // The connection is an Option so that a FAILED reconnect is just "no
  // connection yet, try again next tick" instead of ending the daemon. Getting
  // this wrong is subtle: an earlier version propagated the reconnect error
  // with `?`, so the five-attempt budget never survived past attempt one.
  let mut connection = Some(conn);
  let mut consecutive_failures = 0u32;
  let mut retry_at: Option<tokio::time::Instant> = None;
  debug!("Status daemon timings: {:?}", timings);
  let mut poll = tokio::time::interval(Duration::from_millis(250));

  let ctrl_c = tokio::signal::ctrl_c();
  tokio::pin!(ctrl_c);
  #[cfg(unix)]
  let mut sigterm = tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())?;
  #[cfg(unix)]
  let terminate = async move { sigterm.recv().await };
  #[cfg(not(unix))]
  let terminate = std::future::pending::<Option<()>>();
  tokio::pin!(terminate);

  loop {
    tokio::select! {
      _ = poll.tick() => {
        // Rebuild a lost connection before doing anything else. Backoff grows
        // with consecutive failures so a device that is off or out of range is
        // not hammered.
        if connection.is_none() {
          let now = tokio::time::Instant::now();
          if retry_at.is_some_and(|at| now < at) {
            continue;
          }
          consecutive_failures += 1;
          if consecutive_failures > MAX_DAEMON_RECONNECTS {
            return Err(format!(
              "Giving up after {} failed reconnects", MAX_DAEMON_RECONNECTS
            ).into());
          }
          info!(
            "Reconnecting (attempt {}/{})",
            consecutive_failures, MAX_DAEMON_RECONNECTS
          );
          match DeviceConnection::connect(mac_address).await {
            Ok(fresh) => {
              info!("Status daemon reconnected");
              connection = Some(fresh);
              retry_at = None;
              displayed = None;
            }
            Err(e) => {
              let backoff = Duration::from_secs(
                2u64.saturating_pow(consecutive_failures.min(5))
              );
              info!("Reconnect failed ({}); next try in {:?}", e, backoff);
              retry_at = Some(now + backoff);
              continue;
            }
          }
        }

        // Several Claude Code sessions can drive one panel. Each writes its
        // own file; the highest-priority live one wins. A single state file is
        // still honoured so the CLI and older setups keep working.
        let sessions = read_sessions(&sessions_dir);
        let desired = merge_sessions(&sessions).or_else(|| {
          std::fs::read_to_string(state_file)
            .ok()
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty())
        });
        let Some(mut state) = desired else { continue };
        if !sessions.is_empty() {
          // Record what the merge decided, so `status` explains the panel.
          let _ = std::fs::write(state_file, format!("{}\n", state));
        }

        // The state names a file; refuse anything that could leave faces_dir.
        if !state.chars().all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_') {
          info!("Ignoring invalid state name {:?}", state);
          continue;
        }

        let now = tokio::time::Instant::now();
        if state != last_seen {
          last_seen = state.clone();
          // Entering or leaving a busy stretch: remember how long it ran, so a
          // finish can be judged worth celebrating.
          if is_busy(&state) {
            busy_since.get_or_insert(now);
          } else if let Some(started) = busy_since.take() {
            worked_for = now.duration_since(started);
          }
          let resolved = resolve_finish(&state, worked_for, &timings);
          if resolved != state {
            debug!("Skipping celebration: only {}s of work", worked_for.as_secs());
            state = resolved.to_string();
          }
          requested = state;
          requested_since = now;
        }

        // Re-evaluated every tick, not just on change: escalation and decay
        // happen with the state file sitting still.
        let face = present(&requested, now.duration_since(requested_since), &timings).to_string();
        if displayed.as_deref() == Some(face.as_str()) {
          continue;
        }
        // Opt-in context gauge: a percentage written to this file paints a
        // bar over the bottom row. Absent means the artwork is shown as drawn.
        let context_percent = std::fs::read_to_string(&context_file)
          .ok()
          .and_then(|v| v.trim().parse::<u8>().ok());
        if context_percent != last_context {
          // The bar changed, so the panel has to be redrawn even if the state
          // has not moved.
          displayed = None;
          last_context = context_percent;
        }

        // Drain anything the device sent us. Nothing else consumes this
        // channel in daemon mode, so skipping it leaks for the daemon's whole
        // lifetime. It is also the only chance to observe the device's
        // unsolicited frames -- command 0xF7 shows up unprompted and nobody
        // has worked out what it means.
        if let Some(active) = connection.as_mut() {
          for response in active.drain_responses() {
            info!(
              "Unsolicited frame: command 0x{:02x} ack={} data={}",
              response.original_command,
              response.ack,
              hex::encode(&response.data)
            );
          }
        }

        // Resolve the image BEFORE touching the connection: a missing face is
        // a content problem and must not cost a healthy link.
        // The run directory is searched first so ad-hoc art (`draw`) can
        // override a state without touching the user's faces directory.
        let Some(path) = face_path(&[run_dir, faces_dir], &face) else {
          info!("No image for state {} in {}", face, faces_dir.display());
          displayed = Some(face);
          continue;
        };
        let Some(active) = connection.as_mut() else {
          continue;
        };
        match send_state(active, &path, context_percent).await {
          Ok(()) => {
            info!("Applied state {}", face);
            consecutive_failures = 0;
            let _ = std::fs::write(&applied_file, format!("{}\n", face));
            displayed = Some(face);
          }
          Err(e) => {
            info!("Send failed ({}); dropping the connection to rebuild it", e);
            if let Some(dead) = connection.take() {
              dead.disconnect().await.ok();
            }
            // Rebuilt on a later tick by the block at the top of the loop.
            displayed = None;
          }
        }
      }
      _ = &mut ctrl_c => {
        info!("Interrupted, stopping status daemon");
        break;
      }
      _ = &mut terminate => {
        info!("Terminated, stopping status daemon");
        break;
      }
    }
  }

  if let Some(active) = connection {
    active.disconnect().await?;
  }
  Ok(())
}

/// Find the image for a state. Escalated variants are numbered
/// (alerting2, alerting3); if one is missing -- an older faces directory, say
/// -- fall back to the base face.
fn face_path(dirs: &[&Path], state: &str) -> Option<std::path::PathBuf> {
  let base = state.trim_end_matches(|c: char| c.is_ascii_digit());
  for name in [state, base] {
    for dir in dirs {
      for ext in ["gif", "png"] {
        let candidate = dir.join(format!("{}.{}", name, ext));
        if candidate.exists() {
          return Some(candidate);
        }
      }
    }
  }
  None
}

async fn send_state(
  conn: &mut DeviceConnection,
  path: &Path,
  context_percent: Option<u8>
) -> Result<(), Box<dyn Error>> {
  let animation = if path.extension().is_some_and(|e| e.eq_ignore_ascii_case("gif")) {
    DivoomAnimation::from_gif(&mut BufReader::new(File::open(path)?))?
  } else {
    DivoomAnimation::from_image(image::open(path)?)?
  };
  let mut animation = animation;
  if let Some(percent) = context_percent {
    overlay_context_gauge(&mut animation, percent);
  }
  let mut buf = Vec::new();
  animation.save_to_divoom_format(&mut buf)?;
  for packet in create_network_packets_from(&buf)? {
    conn.fire_and_forget(&packet).await?;
  }
  Ok(())
}

#[cfg(feature = "video")]
fn encode_rgb_frame(rgb: &[u8; 768]) -> Result<Vec<u8>, Box<dyn Error>> {
  let mut palette = IndexSet::new();
  let mut image = RgbImage::new(16, 16);
  for i in 0..256 {
    let color = Rgb([rgb[i * 3], rgb[i * 3 + 1], rgb[i * 3 + 2]]);
    palette.insert(color);
    image.put_pixel((i % 16) as u32, (i / 16) as u32, color);
  }
  let palette: Vec<Rgb<u8>> = palette.into_iter().collect();

  let frame = Frame {
    header: FrameHeader {
      time_in_milliseconds: 60,
      reuse_palette: false,
      color_count: palette.len() as u8,
    },
    palette: palette.clone(),
    local_palette: palette.clone(),
    image: DynamicImage::ImageRgb8(image),
  };

  let mut encoded = Vec::new();
  frame.serialize(&palette, &mut encoded)?;
  Ok(encoded)
}

#[cfg(feature = "video")]
pub async fn send_video(
  mac_address: Address,
  file_path: &str,
  mpv_options: &[(String, String)],
) -> Result<(), Box<dyn Error>> {
  let (frame_tx, mut frame_rx) = mpsc::channel::<[u8; 768]>(2);
  let (stop_tx, stop_rx) = tokio::sync::oneshot::channel::<()>();

  let file_path = file_path.to_string();
  let mpv_options = mpv_options.to_vec();
  let mpv_handle = thread::spawn(move || {
    let player = match protocol::video::VideoPlayer::new(&file_path, mac_address, &mpv_options) {
      Ok(p) => p,
      Err(e) => {
        log::error!("Failed to create video player: {}", e);
        return;
      }
    };

    let mut stop_rx = stop_rx;
    loop {
      if let Ok(()) | Err(tokio::sync::oneshot::error::TryRecvError::Closed) = stop_rx.try_recv() {
        break;
      }

      if player.poll_events() {
        break;
      }

      if let Some(rgb) = player.render_frame() {
        if frame_tx.try_send(rgb).is_err() {
          // Channel full or closed — drop frame to keep real-time pace
        }
      }

      thread::sleep(Duration::from_millis(5));
    }
  });

  let mut conn = DeviceConnection::connect(mac_address).await?;

  conn.fire_and_forget(&Packet {
    command: Command::DrawingCtrlMoviePlay,
    payload: vec![0x00],
  }).await?;

  conn.fire_and_forget(&Packet {
    command: Command::DrawingCtrlMoviePlay,
    payload: vec![0x01],
  }).await?;

  let speed: u16 = 60;
  let mut frame_count: u64 = 0;
  let ctrl_c = tokio::signal::ctrl_c();
  tokio::pin!(ctrl_c);

  loop {
    tokio::select! {
      frame = frame_rx.recv() => {
        match frame {
          Some(rgb) => {
            let encoded = encode_rgb_frame(&rgb)?;
            let data_len = encoded.len() as u16;
            let mut payload = Vec::new();
            payload.extend_from_slice(&speed.to_le_bytes());
            payload.extend_from_slice(&data_len.to_le_bytes());
            payload.extend_from_slice(&encoded);

            conn.fire_and_forget(&Packet {
              command: Command::DrawingEncodeMoviePlay,
              payload,
            }).await?;

            frame_count += 1;
            if frame_count.is_multiple_of(100) {
              info!("Sent {} video frames", frame_count);
            }
          }
          None => {
            info!("Video playback ended ({} frames sent)", frame_count);
            break;
          }
        }
      }
      _ = &mut ctrl_c => {
        info!("Interrupted, stopping video playback");
        break;
      }
    }
  }

  let _ = stop_tx.send(());
  let _ = mpv_handle.join();

  conn.fire_and_forget(&Packet {
    command: Command::DrawingCtrlMoviePlay,
    payload: vec![0x00],
  }).await?;

  conn.disconnect().await?;
  Ok(())
}

#[cfg(test)]
mod status_daemon_tests {
  #![allow(clippy::unwrap_used)]
  #![allow(clippy::expect_used)]

  use super::*;

  fn t() -> Timings {
    Timings::default()
  }

  #[test]
  fn states_pass_through_untouched_when_fresh() {
    // "chilling" is deliberately absent: it is the one idle state that ages
    // into something else (the screensaver), covered by its own test.
    for state in ["thinking", "working", "compacting", "off"] {
      assert_eq!(present(state, Duration::ZERO, &t()), state);
      assert_eq!(present(state, Duration::from_secs(3600), &t()), state);
    }
  }

  #[test]
  fn alert_escalates_on_schedule() {
    assert_eq!(present("alerting", Duration::ZERO, &t()), "alerting");
    assert_eq!(present("alerting", Duration::from_secs(59), &t()), "alerting");
    assert_eq!(present("alerting", Duration::from_secs(60), &t()), "alerting2");
    assert_eq!(present("alerting", Duration::from_secs(299), &t()), "alerting2");
    assert_eq!(present("alerting", Duration::from_secs(300), &t()), "alerting3");
    assert_eq!(present("alerting", Duration::from_secs(86400), &t()), "alerting3");
  }

  #[test]
  fn verdicts_decay_to_idle() {
    for verdict in ["success", "error"] {
      assert_eq!(present(verdict, Duration::ZERO, &t()), verdict);
      assert_eq!(present(verdict, Duration::from_secs(5), &t()), verdict);
      assert_eq!(present(verdict, Duration::from_secs(6), &t()), "chilling");
    }
  }

  #[test]
  fn only_active_states_count_as_busy() {
    assert!(is_busy("thinking"));
    assert!(is_busy("working"));
    assert!(is_busy("compacting"));
    for idle in ["chilling", "alerting", "success", "error", "off"] {
      assert!(!is_busy(idle), "{} should not count as busy", idle);
    }
  }

  #[test]
  fn celebration_must_be_earned() {
    let timings = t();
    assert_eq!(resolve_finish("success", Duration::from_secs(0), &timings), "chilling");
    assert_eq!(resolve_finish("success", Duration::from_secs(599), &timings), "chilling");
    assert_eq!(resolve_finish("success", Duration::from_secs(600), &timings), "success");
  }

  #[test]
  fn only_success_is_gated_on_effort() {
    // An error is worth showing however briefly it took to get there.
    let timings = t();
    for state in ["error", "alerting", "chilling", "working"] {
      assert_eq!(resolve_finish(state, Duration::ZERO, &timings), state);
    }
  }

  #[test]
  fn shortened_timings_escalate_sooner() {
    // The overrides the hardware test drives escalation with.
    let fast = Timings {
      alert_escalate: Duration::from_secs(5),
      alert_panic: Duration::from_secs(10),
      transient: Duration::from_secs(2),
      celebrate_after: Duration::from_secs(3),
      screensaver_after: Duration::ZERO
    };
    assert_eq!(present("alerting", Duration::from_secs(4), &fast), "alerting");
    assert_eq!(present("alerting", Duration::from_secs(5), &fast), "alerting2");
    assert_eq!(present("alerting", Duration::from_secs(10), &fast), "alerting3");
    assert_eq!(present("success", Duration::from_secs(2), &fast), "chilling");
    assert_eq!(resolve_finish("success", Duration::from_secs(3), &fast), "success");
  }

  #[test]
  fn resolution_is_stable_when_it_rewrites_a_state() {
    // An unearned success resolves to "chilling" while the state file still
    // says "success". The daemon must therefore track the RAW file value
    // separately -- comparing the file against the resolved value made this
    // branch re-enter every tick, which reset the state timer (breaking
    // escalation and decay) and lost the recorded work duration.
    let timings = t();
    let raw = "success";
    let resolved = resolve_finish(raw, Duration::from_secs(1), &timings);
    assert_eq!(resolved, "chilling");
    assert_ne!(resolved, raw, "resolution rewrote the state, so the raw value \
                               must be what the loop compares against");
  }

  #[test]
  fn face_resolution_falls_back_from_numbered_variants() {
    let dir = std::env::temp_dir().join("ditoo_face_test");
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    std::fs::write(dir.join("alerting.gif"), b"x").unwrap();
    std::fs::write(dir.join("chilling.png"), b"x").unwrap();

    // exact match wins
    let dirs = [dir.as_path()];
    assert!(face_path(&dirs, "alerting").unwrap().ends_with("alerting.gif"));
    // a numbered variant with no file of its own falls back to the base face,
    // so an older faces directory degrades instead of failing
    assert!(face_path(&dirs, "alerting2").unwrap().ends_with("alerting.gif"));
    assert!(face_path(&dirs, "alerting3").unwrap().ends_with("alerting.gif"));
    // png is accepted when there is no gif
    assert!(face_path(&dirs, "chilling").unwrap().ends_with("chilling.png"));
    // genuinely absent stays absent -- the caller skips without touching the link
    assert!(face_path(&dirs, "nonexistent").is_none());

    // an exact numbered file takes precedence over the fallback
    std::fs::write(dir.join("alerting2.gif"), b"x").unwrap();
    assert!(face_path(&dirs, "alerting2").unwrap().ends_with("alerting2.gif"));
    let _ = std::fs::remove_dir_all(&dir);
  }

  #[test]
  fn the_session_that_needs_you_wins() {
    let now = Duration::ZERO;
    // A session blocked on input beats any amount of busy work elsewhere.
    let states = vec![
      ("working".to_string(), now),
      ("alerting".to_string(), now),
      ("thinking".to_string(), now)
    ];
    assert_eq!(merge_sessions(&states).as_deref(), Some("alerting"));
  }

  #[test]
  fn failure_outranks_activity_but_not_a_block() {
    let now = Duration::ZERO;
    assert_eq!(
      merge_sessions(&[("working".into(), now), ("error".into(), now)]).as_deref(),
      Some("error")
    );
    assert_eq!(
      merge_sessions(&[("error".into(), now), ("alerting".into(), now)]).as_deref(),
      Some("alerting")
    );
  }

  #[test]
  fn idle_only_wins_when_everything_is_idle() {
    let now = Duration::ZERO;
    assert_eq!(
      merge_sessions(&[("chilling".into(), now), ("thinking".into(), now)]).as_deref(),
      Some("thinking")
    );
    assert_eq!(
      merge_sessions(&[("chilling".into(), now), ("chilling".into(), now)]).as_deref(),
      Some("chilling")
    );
  }

  #[test]
  fn a_dead_session_stops_holding_the_panel() {
    // The whole point: a crashed session must not pin the display to "working"
    // and make it lie about work nobody is doing.
    let fresh = Duration::from_secs(1);
    let dead = SESSION_STALE_AFTER + Duration::from_secs(1);
    assert_eq!(
      merge_sessions(&[("working".into(), dead), ("chilling".into(), fresh)]).as_deref(),
      Some("chilling")
    );
    // Every session dead means nothing to show at all.
    assert_eq!(merge_sessions(&[("alerting".into(), dead)]), None);
    assert_eq!(merge_sessions(&[]), None);
  }

  #[test]
  fn the_gauge_fills_left_to_right_and_warns_as_it_goes() {
    use crate::divoom_file_format::frame::Frame;
    use crate::divoom_file_format::frame_header::FrameHeader;
    use image::{DynamicImage, RgbImage};

    let build = |percent: u8| {
      let image = RgbImage::from_pixel(16, 16, Rgb([0, 0, 0]));
      let mut animation = DivoomAnimation {
        frames: vec![Frame {
          header: FrameHeader {
            time_in_milliseconds: 100,
            reuse_palette: false,
            color_count: 1
          },
          palette: vec![Rgb([0, 0, 0])],
          local_palette: vec![Rgb([0, 0, 0])],
          image: DynamicImage::ImageRgb8(image)
        }]
      };
      overlay_context_gauge(&mut animation, percent);
      animation
    };

    // Empty draws nothing at all -- the artwork is untouched.
    let empty = build(0);
    let img = empty.frames[0].image.as_rgb8().unwrap();
    assert_eq!(*img.get_pixel(0, 15), Rgb([0, 0, 0]));

    // Half fills half the row, from the left.
    let half = build(50);
    let img = half.frames[0].image.as_rgb8().unwrap();
    let lit = (0..16).filter(|x| *img.get_pixel(*x, 15) != Rgb([0, 0, 0])).count();
    assert_eq!(lit, 8);
    assert_ne!(*img.get_pixel(0, 15), Rgb([0, 0, 0]), "fills from the left");
    assert_eq!(*img.get_pixel(15, 15), Rgb([0, 0, 0]));

    // Full fills the row and only the row.
    let full = build(100);
    let img = full.frames[0].image.as_rgb8().unwrap();
    assert!((0..16).all(|x| *img.get_pixel(x, 15) != Rgb([0, 0, 0])));
    assert!((0..16).all(|x| *img.get_pixel(x, 14) == Rgb([0, 0, 0])),
            "only the bottom row is overwritten");

    // Colour escalates with pressure.
    let calm = *build(20).frames[0].image.as_rgb8().unwrap().get_pixel(0, 15);
    let warn = *build(70).frames[0].image.as_rgb8().unwrap().get_pixel(0, 15);
    let alarm = *build(95).frames[0].image.as_rgb8().unwrap().get_pixel(0, 15);
    assert_ne!(calm, warn);
    assert_ne!(warn, alarm);
    assert!(alarm[0] > alarm[1], "near-full reads red");

    // The palette must be rebuilt or save_to_divoom_format cannot find the
    // new colours and the whole send fails.
    let mut buf = Vec::new();
    build(50).save_to_divoom_format(&mut buf).expect("composited frame must still encode");
    assert!(!buf.is_empty());
  }

  #[test]
  fn the_gauge_survives_a_real_gif_frame() {
    // The synthetic test above builds an RGB8 image directly, which is not
    // what the daemon ever sees: frames decoded from a GIF are RGBA8. Compose
    // over a real face and require that it still encodes.
    let face = std::path::Path::new("integrations/claude-code/faces/chilling.gif");
    if !face.exists() {
      return; // faces are user-supplied; skip rather than fail the suite
    }
    let mut animation = DivoomAnimation::from_gif(
      &mut BufReader::new(File::open(face).unwrap())
    ).unwrap();
    let before = animation.frames.len();
    overlay_context_gauge(&mut animation, 50);
    assert_eq!(animation.frames.len(), before, "frame count is preserved");

    let painted = animation.frames[0].image.to_rgb8();
    let lit = (0..16).filter(|x| {
      let p = painted.get_pixel(*x, 15);
      p[0] as u16 + p[1] as u16 + p[2] as u16 > 120
    }).count();
    assert!(lit >= 6, "half a gauge should light about half the row, got {}", lit);

    let mut buf = Vec::new();
    animation
      .save_to_divoom_format(&mut buf)
      .expect("a composited GIF frame must still encode");
    assert!(!buf.is_empty());
  }

  #[test]
  fn a_long_idle_falls_through_to_a_screensaver() {
    let timings = t();
    assert_eq!(present("chilling", Duration::from_secs(60), &timings), "chilling");
    assert_eq!(
      present("chilling", timings.screensaver_after, &timings),
      "screensaver"
    );
    // Never from a state that is telling you something.
    assert_eq!(present("alerting", Duration::from_secs(99999), &timings), "alerting3");
    assert_eq!(present("working", Duration::from_secs(99999), &timings), "working");
  }

  #[test]
  fn the_screensaver_can_be_switched_off() {
    let off = Timings { screensaver_after: Duration::ZERO, ..Timings::default() };
    assert_eq!(present("chilling", Duration::from_secs(99999), &off), "chilling");
  }
}
