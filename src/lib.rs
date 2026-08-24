use std::error::Error;
use std::fs::File;
use std::io::BufReader;
use std::path::Path;
use std::time::Duration;
#[cfg(feature = "video")]
use std::thread;

use chrono::{NaiveDateTime, NaiveTime};
#[cfg(feature = "video")]
use image::{DynamicImage, Rgb, RgbImage};
#[cfg(feature = "video")]
use indexmap::IndexSet;
use log::info;
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
  let mut conn = DeviceConnection::connect(mac_address).await?;
  info!(
    "Status daemon connected; watching {} for states from {}",
    state_file.display(),
    faces_dir.display()
  );

  let applied_file = state_file.with_file_name("applied");
  let mut applied: Option<String> = None;
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
        let desired = std::fs::read_to_string(state_file)
          .ok()
          .map(|s| s.trim().to_string())
          .filter(|s| !s.is_empty());
        let Some(state) = desired else { continue };
        if applied.as_deref() == Some(state.as_str()) {
          continue;
        }
        // The state names a file; refuse anything that could leave faces_dir.
        if !state.chars().all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_') {
          info!("Ignoring invalid state name {:?}", state);
          applied = Some(state);
          continue;
        }
        match send_state(&mut conn, faces_dir, &state).await {
          Ok(()) => {
            info!("Applied state {}", state);
            let _ = std::fs::write(&applied_file, format!("{}\n", state));
            applied = Some(state);
          }
          Err(e) => {
            conn.disconnect().await.ok();
            return Err(format!("Failed to apply state {}: {}", state, e).into());
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

  conn.disconnect().await?;
  Ok(())
}

async fn send_state(
  conn: &mut DeviceConnection,
  faces_dir: &Path,
  state: &str
) -> Result<(), Box<dyn Error>> {
  let gif = faces_dir.join(format!("{}.gif", state));
  let png = faces_dir.join(format!("{}.png", state));
  let path = if gif.exists() {
    gif
  } else if png.exists() {
    png
  } else {
    return Err(
      format!("no face image for state '{}' in {}", state, faces_dir.display()).into()
    );
  };

  let animation = if path.extension().is_some_and(|e| e.eq_ignore_ascii_case("gif")) {
    DivoomAnimation::from_gif(&mut BufReader::new(File::open(&path)?))?
  } else {
    DivoomAnimation::from_image(image::open(&path)?)?
  };
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
