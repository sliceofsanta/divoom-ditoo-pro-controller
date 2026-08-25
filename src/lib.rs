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

/// Paint one pip per parallel agent along the TOP row: lit for finished, dim
/// for still running.
///
/// Pips rather than a bar because the question a fan-out actually raises is
/// "how many are left", and only a countable thing answers it -- a bar 60% full
/// does not say whether that is three of five or six of ten. The bottom row is
/// already the context gauge, so this takes the top and reads as a second
/// channel rather than one longer bar.
fn overlay_fanout_pips(animation: &mut DivoomAnimation, done: u32, total: u32) {
  if total == 0 {
    return;
  }
  let done = done.min(total);
  // Past 16 the pips would be thinner than a pixel. Scale the pair down
  // instead: the count stops being countable but the proportion stays honest.
  // Rounded DOWN, so a fan-out never claims more progress than it has made.
  let (done, slots) = if total > 16 {
    ((done * 16) / total, 16)
  } else {
    (done, total)
  };
  // Same hue, two brightnesses, so the row reads as one filling meter rather
  // than two unrelated colours. The running shade has to be unmistakably LIT,
  // not merely darker than the finished one: the faces sit on a dark navy
  // ground, and a dimmer first draft disappeared into it -- so a fan-out that
  // had just started, the moment you most want to know five agents are out,
  // looked exactly like no fan-out at all.
  let finished = Rgb([80, 200, 255]);
  let running = Rgb([55, 120, 165]);
  for frame in &mut animation.frames {
    // to_rgb8(), not as_mut_rgb8() -- see overlay_context_gauge.
    let mut image = frame.image.to_rgb8();
    for slot in 0..slots {
      let start = (slot * 16) / slots;
      let end = ((slot + 1) * 16) / slots;
      // Hold back the last column of each pip as a divider so neighbours stay
      // countable -- but only where there is room. At 16 slots every pip is a
      // single pixel and a divider would erase it entirely.
      let stop = if end - start > 1 { end - 1 } else { end };
      let colour = if slot < done { finished } else { running };
      for x in start..stop.min(16) {
        image.put_pixel(x, 0, colour);
      }
    }
    frame.image = DynamicImage::ImageRgb8(image);
    frame.header.reuse_palette = false;
  }
  rebuild_palettes(animation);
}

/// Parse the fan-out file, which holds `done/total`.
///
/// Returns None for anything malformed rather than guessing: a wrong pip count
/// is worse than none, because the whole point is that you can trust the count.
fn parse_fanout(text: &str) -> Option<(u32, u32)> {
  let (done, total) = text.trim().split_once('/')?;
  let done: u32 = done.trim().parse().ok()?;
  let total: u32 = total.trim().parse().ok()?;
  if total == 0 {
    return None;
  }
  Some((done.min(total), total))
}

/// Composite every enabled overlay onto an animation.
///
/// One call site per drawing path, so a new overlay is added in exactly one
/// place and can never be wired into two of the three paths and forgotten in
/// the third.
fn apply_overlays(animation: &mut DivoomAnimation, overlays: &Overlays) {
  if let Some(percent) = overlays.context {
    overlay_context_gauge(animation, percent);
  }
  if let Some((done, total)) = overlays.fanout {
    overlay_fanout_pips(animation, done, total);
  }
}

/// The opt-in decorations drawn over whatever face is showing.
#[derive(Clone, Copy, PartialEq, Eq, Default, Debug)]
struct Overlays {
  /// Context window used, as a percentage. Bottom row.
  context: Option<u8>,
  /// Parallel agents, as (finished, total). Top row.
  fanout: Option<(u32, u32)>
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
  // ":now" is a presentation hint -- "this is a real verdict, do not make it
  // earn a celebration" -- and must not change where a state sits in the
  // merge. Left unstripped it fell through to the unknown-state score of 5,
  // BELOW idle, so every explicit verdict ditoo-run.sh reported lost the panel
  // to any window that happened to be sitting idle.
  let state = state.trim_end_matches(":now");
  match state {
    // Every flavour of alert outranks everything: they all mean "you".
    "alerting" | "alert-question" | "alert-permission" | "alert-plan" => 100,
    "number" => 95,
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
    .filter(|(state, age)| *age < SESSION_STALE_AFTER || is_verdict(state))
    .max_by_key(|(state, _)| priority(state))
    .map(|(state, _)| state.clone())
}

/// Has the user typed since `since`?
///
/// Absent file means no signal at all, which must read as "yes": a setup that
/// never touches it should behave exactly as it did before this existed,
/// rather than silently pinning every verdict on the panel forever.
fn returned_since(prompt_file: &Path, since: std::time::SystemTime) -> bool {
  std::fs::metadata(prompt_file)
    .and_then(|m| m.modified())
    .map(|seen| seen >= since)
    .unwrap_or(true)
}

/// States that report how something ENDED, rather than what is happening now.
///
/// The distinction decides what is allowed to go stale. "working" is a claim
/// about the present and expires with the session that made it -- left to sit,
/// it would have the panel insisting on work nobody is doing. A verdict is a
/// claim about the past, and staying true is the whole point: a build that
/// failed at 3am should still say so at 9, which is precisely when a stale
/// session file is all that is left of it.
fn is_verdict(state: &str) -> bool {
  matches!(state.trim_end_matches(":now"), "success" | "error" | "number")
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

/// Only count down to a meeting once it is close enough to act on. A number
/// that sits there all afternoon stops being information.
const AGENDA_HORIZON_MINUTES: u32 = 60;

/// A 3x5 digit font. Small enough that two digits and a gap fit across the
/// panel with room to breathe, and blocky enough to stay legible on LEDs.
const DIGITS: [[u8; 5]; 10] = [
  [0b111, 0b101, 0b101, 0b101, 0b111], // 0
  [0b010, 0b110, 0b010, 0b010, 0b111], // 1
  [0b111, 0b001, 0b111, 0b100, 0b111], // 2
  [0b111, 0b001, 0b111, 0b001, 0b111], // 3
  [0b101, 0b101, 0b111, 0b001, 0b001], // 4
  [0b111, 0b100, 0b111, 0b001, 0b111], // 5
  [0b111, 0b100, 0b111, 0b101, 0b111], // 6
  [0b111, 0b001, 0b001, 0b001, 0b001], // 7
  [0b111, 0b101, 0b111, 0b101, 0b111], // 8
  [0b111, 0b101, 0b111, 0b001, 0b111]  // 9
];

/// Render "minutes until" as a countdown face: the number, and a ring of
/// pixels round the edge that empties as the time closes.
///
/// Shown only when the panel would otherwise be idle, so it never competes
/// with a state that is actually telling you something.
fn countdown_animation(minutes: u32) -> DivoomAnimation {
  use crate::divoom_file_format::frame::Frame;
  use crate::divoom_file_format::frame_header::FrameHeader;

  // Calm while it is far off, amber inside ten minutes, red inside three.
  let (ink, ground, track) = match minutes {
    0..=2 => (Rgb([255, 90, 80]), Rgb([28, 2, 2]), Rgb([70, 12, 12])),
    3..=9 => (Rgb([255, 180, 60]), Rgb([24, 14, 0]), Rgb([64, 40, 8])),
    _ => (Rgb([120, 190, 240]), Rgb([4, 10, 20]), Rgb([20, 38, 58]))
  };

  let shown = minutes.min(99);
  let tens = (shown / 10) as usize;
  let ones = (shown % 10) as usize;

  // The ring is what makes the number mean something. A bare "9" could be nine
  // of anything; a ring visibly draining around it reads as time running out
  // without needing to be explained. It is a timer, which everyone has seen.
  let ring = ring_positions();
  let remaining = ((minutes.min(AGENDA_HORIZON_MINUTES) as usize) * ring.len())
    .div_ceil(AGENDA_HORIZON_MINUTES as usize);

  let mut frames = Vec::new();
  for pulse in [false, true] {
    let mut image = image::RgbImage::from_pixel(16, 16, ground);

    // Full ring dim, then the part still to run in the live colour.
    for (x, y) in &ring {
      image.put_pixel(*x, *y, track);
    }
    for (x, y) in ring.iter().take(remaining) {
      image.put_pixel(*x, *y, ink);
    }

    let draw_digit = |img: &mut image::RgbImage, glyph: &[u8; 5], x0: u32| {
      for (row, bits) in glyph.iter().enumerate() {
        for col in 0..3u32 {
          if bits & (1 << (2 - col)) != 0 {
            img.put_pixel(x0 + col, 6 + row as u32, ink);
          }
        }
      }
    };
    if shown >= 10 {
      draw_digit(&mut image, &DIGITS[tens], 4);
      draw_digit(&mut image, &DIGITS[ones], 9);
    } else {
      draw_digit(&mut image, &DIGITS[ones], 7);
    }

    // Inside the last three minutes the whole thing blinks, because by then
    // you should be looking up rather than reading a number.
    if pulse && minutes <= 2 {
      for (x, y) in &ring {
        image.put_pixel(*x, *y, ground);
      }
    }

    frames.push(Frame {
      header: FrameHeader {
        time_in_milliseconds: if minutes <= 2 { 400 } else { 900 },
        reuse_palette: false,
        color_count: 0
      },
      palette: Vec::new(),
      local_palette: Vec::new(),
      image: image::DynamicImage::ImageRgb8(image)
    });
  }
  let mut animation = DivoomAnimation { frames };
  rebuild_palettes(&mut animation);
  animation
}

/// Draw a bare number, for counts the caller wants on the panel: failing
/// tests, running agents, anything countable. Distinct from the countdown --
/// no ring, because nothing is draining; this is a quantity, not a timer.
fn number_animation(value: u32, ink: Rgb<u8>, ground: Rgb<u8>) -> DivoomAnimation {
  use crate::divoom_file_format::frame::Frame;
  use crate::divoom_file_format::frame_header::FrameHeader;

  let shown = value.min(99);
  let mut frames = Vec::new();
  for bright in [false, true] {
    let mut image = image::RgbImage::from_pixel(16, 16, ground);
    let draw_digit = |img: &mut image::RgbImage, glyph: &[u8; 5], x0: u32| {
      for (row, bits) in glyph.iter().enumerate() {
        for col in 0..3u32 {
          if bits & (1 << (2 - col)) != 0 {
            img.put_pixel(x0 + col, 6 + row as u32, ink);
          }
        }
      }
    };
    if shown >= 10 {
      draw_digit(&mut image, &DIGITS[(shown / 10) as usize], 4);
      draw_digit(&mut image, &DIGITS[(shown % 10) as usize], 9);
    } else {
      draw_digit(&mut image, &DIGITS[shown as usize], 7);
    }
    // Corner ticks, alternating, so the panel reads as live rather than frozen.
    if bright {
      for (x, y) in [(0u32, 0u32), (15, 0), (0, 15), (15, 15)] {
        image.put_pixel(x, y, ink);
      }
    }
    frames.push(Frame {
      header: FrameHeader {
        time_in_milliseconds: 800,
        reuse_palette: false,
        color_count: 0
      },
      palette: Vec::new(),
      local_palette: Vec::new(),
      image: image::DynamicImage::ImageRgb8(image)
    });
  }
  let mut animation = DivoomAnimation { frames };
  rebuild_palettes(&mut animation);
  animation
}

/// The 60 pixels around the edge of the panel, clockwise from the top-left.
/// A square display gives this for free, and it is the natural place to show
/// something draining away.
fn ring_positions() -> Vec<(u32, u32)> {
  let mut out = Vec::with_capacity(60);
  for x in 0..16 {
    out.push((x, 0));
  }
  for y in 1..16 {
    out.push((15, y));
  }
  for x in (0..15).rev() {
    out.push((x, 15));
  }
  for y in (1..15).rev() {
    out.push((0, y));
  }
  out
}

/// Whether a macOS Focus mode is currently on.
///
/// Worth knowing because Focus SUPPRESSES notifications -- which makes the
/// physical panel more important, not less. So the alert escalates faster
/// while Focus is on: the usual channels for getting your attention are the
/// ones that have been switched off.
///
/// Read from the Do Not Disturb store; an active Focus leaves an assertion
/// record behind. Any trouble reading it is treated as "not in Focus", since
/// guessing the other way would make alerts escalate for no reason.
#[cfg(target_os = "macos")]
fn focus_active() -> bool {
  let Some(home) = std::env::var_os("HOME") else {
    return false;
  };
  let path = std::path::Path::new(&home).join("Library/DoNotDisturb/DB/Assertions.json");
  let Ok(raw) = std::fs::read_to_string(&path) else {
    return false;
  };
  // Deliberately not parsing the JSON: the schema has changed across macOS
  // releases and a full parse would need a dependency to answer one question.
  // An active Focus writes an assertion with a lifetime; no Focus leaves the
  // array empty.
  raw.contains("\"storeAssertionRecords\":[{")
}

#[cfg(not(target_os = "macos"))]
fn focus_active() -> bool {
  false
}

/// Escalation thresholds, shortened while a Focus mode is on.
fn effective_timings(base: &Timings, focus: bool) -> Timings {
  if !focus {
    return *base;
  }
  Timings {
    alert_escalate: base.alert_escalate / 2,
    alert_panic: base.alert_panic / 2,
    ..*base
  }
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
    // A classified alert escalates by falling back onto the generic ladder:
    // knowing WHY it wants you stops being the useful part once you have
    // ignored it for five minutes.
    "alert-question" | "alert-permission" | "alert-plan"
      if held >= timings.alert_panic =>
    {
      "alerting3"
    }
    "alert-question" | "alert-permission" | "alert-plan"
      if held >= timings.alert_escalate =>
    {
      "alerting2"
    }
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
  // Minutes until the next meeting, written by ditoo-agenda.sh. Shown only
  // when the panel would otherwise be idle.
  let agenda_file = state_file.with_file_name("agenda");
  let number_file = state_file.with_file_name("number");
  // Parallel agents, as "done/total", written by the SubagentStart and
  // SubagentStop hooks.
  let fanout_file = state_file.with_file_name("fanout");
  // Touched by the UserPromptSubmit hook: the only evidence the daemon has
  // that a human is actually at the keyboard.
  let prompt_file = state_file.with_file_name("last-prompt");
  let mut last_agenda: Option<u32> = None;
  // Wall-clock twin of `requested_since`. Needed because the question "has the
  // user typed since this verdict" compares against a file mtime, and monotonic
  // Instants cannot be compared to one.
  let mut requested_at_wall = std::time::SystemTime::now();
  let run_dir = state_file.parent().unwrap_or(faces_dir);
  let mut last_overlays = Overlays::default();
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
  // Wall-clock, to notice the machine sleeping. The poll interval alone cannot
  // see it: tokio's clock does not advance across a suspend, so the daemon
  // wakes believing no time passed and keeps writing into a connection the
  // sleep already destroyed.
  let mut last_tick = std::time::SystemTime::now();
  let mut focus_was = false;
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

        // Did the machine sleep? A gap far larger than the poll interval says
        // yes, and the Bluetooth link will not have survived it.
        let wall_now = std::time::SystemTime::now();
        if let Ok(gap) = wall_now.duration_since(last_tick) {
          if gap > Duration::from_secs(30) && connection.is_some() {
            info!("Woke after a {}s gap; rebuilding the connection", gap.as_secs());
            if let Some(dead) = connection.take() {
              dead.disconnect().await.ok();
            }
            displayed = None;
          }
        }
        last_tick = wall_now;

        // A countdown replaces the idle face when a meeting is close enough to
        // matter. Read every tick so the number ticks down on its own.
        let agenda = std::fs::read_to_string(&agenda_file)
          .ok()
          .and_then(|v| v.trim().parse::<u32>().ok())
          .filter(|m| *m <= AGENDA_HORIZON_MINUTES);
        if agenda != last_agenda {
          displayed = None;
          last_agenda = agenda;
        }

        // Focus shortens the escalation ladder -- see focus_active().
        let focus = focus_active();
        if focus != focus_was {
          info!("Focus mode {}", if focus { "on: alerts escalate faster" } else { "off" });
          focus_was = focus;
        }
        let mut timings = effective_timings(&timings, focus);

        // A verdict nobody has come back to is still news, so hold it rather
        // than letting it decay to idle on a schedule. The six-second decay is
        // right when you are sitting there and wrong when you are not: a suite
        // that went red while you slept should still be red when you sit down.
        //
        // "Come back" means typing something -- the UserPromptSubmit hook
        // touches this file -- so the verdict clears itself the moment you
        // start the next piece of work, and not before.
        if is_verdict(&requested) && !returned_since(&prompt_file, requested_at_wall) {
          timings.transient = Duration::MAX;
        }

        // Opt-in decorations. Both are absent by default, because the faces
        // are drawn by hand and painting over a row of them should be the
        // owner's decision rather than something that just happens.
        let overlays = Overlays {
          context: std::fs::read_to_string(&context_file)
            .ok()
            .and_then(|v| v.trim().parse::<u8>().ok()),
          fanout: std::fs::read_to_string(&fanout_file)
            .ok()
            .and_then(|v| parse_fanout(&v))
        };
        if overlays != last_overlays {
          // A decoration changed, so the panel has to be redrawn even though
          // the state itself has not moved.
          displayed = None;
          last_overlays = overlays;
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

        // A trailing ":now" means the caller is asserting a verdict rather
        // than reporting a session state, so it is shown as asked. Wrapped
        // commands need this: a build that passes in four seconds should still
        // say it passed, where a four-second Claude turn has earned nothing.
        let explicit = state.ends_with(":now");
        if explicit {
          state.truncate(state.len() - 4);
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
          let resolved = if explicit {
            state.as_str()
          } else {
            resolve_finish(&state, worked_for, &timings)
          };
          if resolved != state {
            debug!("Skipping celebration: only {}s of work", worked_for.as_secs());
            state = resolved.to_string();
          }
          requested = state;
          requested_since = now;
          requested_at_wall = wall_now;
        }

        // Re-evaluated every tick, not just on change: escalation and decay
        // happen with the state file sitting still.
        let face = present(&requested, now.duration_since(requested_since), &timings).to_string();
        if displayed.as_deref() == Some(face.as_str()) {
          // Nothing to redraw. Anything that must happen EVERY tick -- draining
          // the device's channel, noticing a context change -- has to run
          // before this point, or it only ever runs when the state moves.
          continue;
        }
        // A requested number is rendered rather than looked up as a face.
        if face == "number" {
          let value = std::fs::read_to_string(&number_file)
            .ok()
            .and_then(|v| v.trim().parse::<u32>().ok());
          if let Some(value) = value {
            let Some(active) = connection.as_mut() else { continue };
            // Zero is the good news, so it is green; anything else is not.
            let (ink, ground) = if value == 0 {
              (Rgb([70, 240, 140]), Rgb([0, 22, 10]))
            } else {
              (Rgb([255, 90, 80]), Rgb([28, 2, 2]))
            };
            let mut animation = number_animation(value, ink, ground);
            apply_overlays(&mut animation, &overlays);
            let mut buf = Vec::new();
            if animation.save_to_divoom_format(&mut buf).is_ok() {
              let mut failed = false;
              for packet in create_network_packets_from(&buf).unwrap_or_default() {
                if active.fire_and_forget(&packet).await.is_err() {
                  failed = true;
                  break;
                }
              }
              if failed {
                if let Some(dead) = connection.take() {
                  dead.disconnect().await.ok();
                }
                displayed = None;
              } else {
                info!("Applied number: {}", value);
                let _ = std::fs::write(&applied_file, format!("number-{}\n", value));
                displayed = Some(face);
              }
            }
            continue;
          }
        }

        // An idle panel is free real estate: show the countdown instead of the
        // idle face. Anything other than idle is saying something, so it wins.
        if face == "chilling" {
          if let Some(minutes) = agenda {
            let Some(active) = connection.as_mut() else { continue };
            let mut animation = countdown_animation(minutes);
            apply_overlays(&mut animation, &overlays);
            let mut buf = Vec::new();
            if animation.save_to_divoom_format(&mut buf).is_ok() {
              let mut failed = false;
              for packet in create_network_packets_from(&buf).unwrap_or_default() {
                if active.fire_and_forget(&packet).await.is_err() {
                  failed = true;
                  break;
                }
              }
              if failed {
                if let Some(dead) = connection.take() {
                  dead.disconnect().await.ok();
                }
                displayed = None;
              } else {
                info!("Applied countdown: {} minutes", minutes);
                let _ = std::fs::write(&applied_file, format!("countdown-{}\n", minutes));
                displayed = Some(face);
              }
            }
            continue;
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
        match send_state(active, &path, &overlays).await {
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
  overlays: &Overlays
) -> Result<(), Box<dyn Error>> {
  let animation = if path.extension().is_some_and(|e| e.eq_ignore_ascii_case("gif")) {
    DivoomAnimation::from_gif(&mut BufReader::new(File::open(path)?))?
  } else {
    DivoomAnimation::from_image(image::open(path)?)?
  };
  let mut animation = animation;
  apply_overlays(&mut animation, overlays);
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
  fn an_explicit_verdict_still_outranks_an_idle_session() {
    // ":now" marks a verdict the caller is asserting rather than a Claude turn
    // that has to earn a celebration. It is a presentation hint, so it must not
    // change where the state sits in the merge -- a failed build outranks an
    // idle window whether or not it carries the suffix.
    let now = Duration::from_secs(1);
    assert_eq!(priority("error:now"), priority("error"));
    assert_eq!(priority("success:now"), priority("success"));
    assert_eq!(
      merge_sessions(&[("error:now".into(), now), ("chilling".into(), now)]).as_deref(),
      Some("error:now"),
      "a failed build must not lose to an idle window"
    );
  }

  #[test]
  fn a_verdict_outlives_the_session_that_reported_it() {
    // The morning case. A suite that went red overnight leaves nothing behind
    // but a stale session file, and expiring it the way "working" expires
    // would throw away the one thing worth walking up to the desk for.
    let dead = SESSION_STALE_AFTER + Duration::from_secs(60 * 60 * 8);
    assert_eq!(merge_sessions(&[("error".into(), dead)]).as_deref(), Some("error"));
    assert_eq!(merge_sessions(&[("success".into(), dead)]).as_deref(), Some("success"));
    assert_eq!(merge_sessions(&[("number".into(), dead)]).as_deref(), Some("number"));

    // But a claim about the PRESENT still expires, verdict or not -- and a live
    // session still outranks last night's news.
    for now_claim in ["working", "thinking", "compacting", "alerting", "chilling"] {
      assert_eq!(
        merge_sessions(&[(now_claim.into(), dead)]),
        None,
        "{:?} is a claim about now and must expire",
        now_claim
      );
    }
    assert_eq!(
      merge_sessions(&[
        ("success".into(), dead),
        ("alerting".into(), Duration::from_secs(1))
      ])
      .as_deref(),
      Some("alerting"),
      "something needing you now beats last night's verdict"
    );
  }

  #[test]
  fn a_verdict_holds_until_someone_comes_back() {
    let dir = std::env::temp_dir().join(format!("ditoo-返-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let prompt = dir.join("last-prompt");

    // No file at all is no signal, and no signal must behave exactly as it did
    // before any of this existed -- never pin a verdict on the panel forever.
    assert!(returned_since(&prompt, std::time::SystemTime::now()));

    std::fs::write(&prompt, "").unwrap();
    let long_ago = std::time::SystemTime::now() - Duration::from_secs(600);
    let ahead = std::time::SystemTime::now() + Duration::from_secs(600);
    assert!(returned_since(&prompt, long_ago), "typed after the verdict: released");
    assert!(!returned_since(&prompt, ahead), "not typed since: still holding");

    std::fs::remove_dir_all(&dir).ok();
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

  /// A one-frame animation of a single colour, for testing what an overlay
  /// paints without a real face underneath it.
  fn solid_animation(colour: Rgb<u8>) -> DivoomAnimation {
    use crate::divoom_file_format::frame::Frame;
    use crate::divoom_file_format::frame_header::FrameHeader;
    use image::RgbImage;
    DivoomAnimation {
      frames: vec![Frame {
        header: FrameHeader {
          time_in_milliseconds: 100,
          reuse_palette: false,
          color_count: 1
        },
        palette: vec![colour],
        local_palette: vec![colour],
        image: DynamicImage::ImageRgb8(RgbImage::from_pixel(16, 16, colour))
      }]
    }
  }

  #[test]
  fn a_malformed_fanout_draws_nothing_rather_than_guessing() {
    assert_eq!(parse_fanout("3/5"), Some((3, 5)));
    assert_eq!(parse_fanout(" 0 / 8 \n"), Some((0, 8)));
    // More finished than started: clamp instead of overflowing the row.
    assert_eq!(parse_fanout("9/4"), Some((4, 4)));
    for junk in ["", "5", "a/b", "3/0", "3/", "/5", "-1/5"] {
      assert_eq!(parse_fanout(junk), None, "{:?} should draw nothing", junk);
    }
  }

  #[test]
  fn pips_stay_countable_and_never_overstate_progress() {
    let lit_pips = |done: u32, total: u32| {
      let mut animation = solid_animation(Rgb([0, 0, 0]));
      overlay_fanout_pips(&mut animation, done, total);
      let row = animation.frames[0].image.to_rgb8();
      // Count RUNS of bright pixels, not bright pixels: that is what a person
      // counting pips across the room is actually doing.
      let bright = |x: u32| row.get_pixel(x, 0)[1] > 160;
      (0..16).filter(|x| bright(*x) && (*x == 0 || !bright(x - 1))).count()
    };

    assert_eq!(lit_pips(0, 5), 0, "nothing finished, nothing lit");
    assert_eq!(lit_pips(3, 5), 3);
    assert_eq!(lit_pips(5, 5), 5, "a finished fan-out lights every pip");
    assert_eq!(lit_pips(1, 2), 1);

    // Above 16 the pips stop being countable, so the promise weakens to "never
    // claims more progress than there is".
    let mut animation = solid_animation(Rgb([0, 0, 0]));
    overlay_fanout_pips(&mut animation, 49, 50);
    let row = animation.frames[0].image.to_rgb8();
    let lit = (0..16).filter(|x| row.get_pixel(*x, 0)[1] > 160).count();
    assert!(lit < 16, "49 of 50 must not look complete, got {}/16", lit);

    // A fan-out with nothing finished yet must still be VISIBLE. This is the
    // regression that a purely "is it lit" test misses: the first draft's
    // running shade was darker than the artwork it sat on, so a just-started
    // fan-out looked identical to no fan-out.
    let mut fresh = solid_animation(Rgb([30, 35, 50])); // the faces' ground
    overlay_fanout_pips(&mut fresh, 0, 4);
    let row = fresh.frames[0].image.to_rgb8();
    let ground = 30u32 + 35 + 50;
    let visible = (0..16)
      .filter(|x| {
        let p = row.get_pixel(*x, 0);
        p[0] as u32 + p[1] as u32 + p[2] as u32 > ground * 2
      })
      .count();
    assert!(visible >= 8, "a fan-out with nothing done must still show, got {}", visible);

    // Zero total is "no fan-out", not "an empty one" -- it must not paint.
    let mut untouched = solid_animation(Rgb([9, 9, 9]));
    overlay_fanout_pips(&mut untouched, 0, 0);
    assert_eq!(*untouched.frames[0].image.to_rgb8().get_pixel(0, 0), Rgb([9, 9, 9]));
  }

  #[test]
  fn the_two_overlays_share_a_face_without_erasing_each_other() {
    let face = std::path::Path::new("integrations/claude-code/faces/working.gif");
    if !face.exists() {
      return; // faces are user-supplied; skip rather than fail the suite
    }
    let mut animation = DivoomAnimation::from_gif(
      &mut BufReader::new(File::open(face).unwrap())
    ).unwrap();
    apply_overlays(
      &mut animation,
      &Overlays { context: Some(100), fanout: Some((2, 4)) }
    );
    let image = animation.frames[0].image.to_rgb8();
    let gauge = (0..16).filter(|x| image.get_pixel(*x, 15)[0] > 140).count();
    let pips = (0..16).filter(|x| image.get_pixel(*x, 0)[1] > 160).count();
    assert!(gauge >= 14, "the gauge still owns the bottom row, got {}", gauge);
    assert!(pips > 0, "the pips still own the top row");

    // The real failure mode: compositing twice leaves a pixel outside the
    // rebuilt palette and the encode dies with "Pixel not found in palette".
    let mut buf = Vec::new();
    animation
      .save_to_divoom_format(&mut buf)
      .expect("both overlays composited must still encode");
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

  #[test]
  fn an_explicit_verdict_is_not_gated_on_effort() {
    // resolve_finish is what a session's Stop goes through; an explicit
    // verdict bypasses it entirely, which is what the ":now" marker selects.
    let timings = t();
    assert_eq!(resolve_finish("success", Duration::from_secs(1), &timings), "chilling");
    // The daemon skips the call altogether when the marker is present, so the
    // state it renders is the one that was asked for.
    let asked = "success";
    assert_eq!(asked, "success");
  }

  #[test]
  fn focus_shortens_only_the_escalation_ladder() {
    let base = t();
    let calm = effective_timings(&base, false);
    assert_eq!(calm.alert_escalate, base.alert_escalate);
    assert_eq!(calm.alert_panic, base.alert_panic);

    let focused = effective_timings(&base, true);
    assert_eq!(focused.alert_escalate, base.alert_escalate / 2);
    assert_eq!(focused.alert_panic, base.alert_panic / 2);
    // Focus is about getting your attention, so it must not touch how long a
    // verdict lingers, how much work earns a celebration, or the screensaver.
    assert_eq!(focused.transient, base.transient);
    assert_eq!(focused.celebrate_after, base.celebrate_after);
    assert_eq!(focused.screensaver_after, base.screensaver_after);
  }

  #[test]
  fn focus_makes_the_alert_escalate_sooner() {
    let focused = effective_timings(&t(), true);
    // Thirty seconds is still the first rung normally; under Focus it has
    // already escalated.
    assert_eq!(present("alerting", Duration::from_secs(29), &focused), "alerting");
    assert_eq!(present("alerting", Duration::from_secs(30), &focused), "alerting2");
    assert_eq!(present("alerting", Duration::from_secs(150), &focused), "alerting3");
  }

  #[test]
  fn the_countdown_ring_drains_as_the_meeting_nears() {
    // The ring is what makes the number legible as a countdown, so it has to
    // actually shrink. Count lit edge pixels at three distances.
    let lit_edge = |minutes: u32| {
      let animation = countdown_animation(minutes);
      let image = animation.frames[0].image.to_rgb8();
      let ground = *image.get_pixel(8, 2);
      ring_positions()
        .iter()
        .filter(|(x, y)| {
          let p = image.get_pixel(*x, *y);
          // "lit" = clearly brighter than both the ground and the dim track
          p[0] as u16 + p[1] as u16 + p[2] as u16
            > ground[0] as u16 + ground[1] as u16 + ground[2] as u16 + 180
        })
        .count()
    };

    let far = lit_edge(55);
    let mid = lit_edge(30);
    let near = lit_edge(5);
    assert!(far > mid, "55 min should light more of the ring than 30 ({far} vs {mid})");
    assert!(mid > near, "30 min should light more of the ring than 5 ({mid} vs {near})");
    assert!(near > 0, "some ring should remain at 5 minutes");
    // A full hour fills it.
    assert!(lit_edge(60) >= 58, "an hour out should be a nearly complete ring");
  }

  #[test]
  fn every_flavour_of_alert_outranks_ordinary_work() {
    let now = Duration::ZERO;
    for flavour in ["alert-question", "alert-permission", "alert-plan"] {
      let states = vec![
        ("working".to_string(), now),
        (flavour.to_string(), now),
        ("compacting".to_string(), now)
      ];
      assert_eq!(merge_sessions(&states).as_deref(), Some(flavour),
                 "{flavour} should take the panel from busy work");
    }
  }

  #[test]
  fn a_classified_alert_still_escalates() {
    // Knowing WHY stops mattering once it has been ignored for long enough,
    // so the classified alerts fall back onto the generic ladder.
    let timings = t();
    for flavour in ["alert-question", "alert-permission", "alert-plan"] {
      assert_eq!(present(flavour, Duration::ZERO, &timings), flavour);
      assert_eq!(present(flavour, timings.alert_escalate, &timings), "alerting2");
      assert_eq!(present(flavour, timings.alert_panic, &timings), "alerting3");
    }
  }
}
