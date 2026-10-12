//! A one-pixel-high activity channel. Motion means activity, never percentage.
use image::{DynamicImage, Rgb};
use crate::divoom_file_format::animation::Animation;

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, PartialOrd, Ord)]
pub(crate) enum Status {
  #[default]
  Empty,
  Done,
  Running,
  Error,
  Waiting,
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub(crate) struct Agents(pub [Status; 8]);

impl Agents {
  pub fn parse(text: &str, now: u64) -> Option<Self> {
    let mut lines = text.lines();
    if lines.next()? != "v1" { return None; }
    let mut result = Self::default();
    for line in lines {
      let words: Vec<_> = line.split_whitespace().collect();
      if words.len() != 3 { return None; }
      let slot: usize = words[0].parse().ok()?;
      if slot >= 8 { return None; }
      let status = match words[1] {
        "running" => Status::Running,
        "waiting" => Status::Waiting,
        "error" => Status::Error,
        "done" => Status::Done,
        _ => return None,
      };
      let expires: u64 = words[2].parse().ok()?;
      if expires > now { result.0[slot] = result.0[slot].max(status); }
    }
    Some(result)
  }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Mode { Quiet, Active, Waiting(u32), Error, Complete }

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct Strip { mode: Mode, agents: Agents }

impl Strip {
  pub fn attention_changed(self, previous: Self) -> bool {
    self.agents.0.iter().zip(previous.agents.0).any(|(new, old)|
      *new != old && matches!(new, Status::Waiting | Status::Error))
  }

  pub fn for_face(face: &str, agents: Agents) -> Self {
    let mode = match face {
      "alerting3" => Mode::Waiting(1000),
      "alerting2" => Mode::Waiting(1600),
      "alerting" | "alert-permission" | "alert-question" | "alert-plan" => Mode::Waiting(2400),
      "error" => Mode::Error,
      "success" | "done" => Mode::Complete,
      "starting" | "configuring" | "taskdone" => Mode::Active,
      state if crate::is_busy(state) => Mode::Active,
      _ => Mode::Quiet,
    };
    // Changes to a hidden roster must not keep restarting the idle animation.
    Self { mode, agents: if mode == Mode::Quiet { Agents::default() } else { agents } }
  }

  fn pixels(self, ms: u32) -> [Option<Rgb<u8>>; 16] {
    let mut row = [None; 16];
    if self.mode == Mode::Quiet { return row; }
    let occupied = self.agents.0.iter().filter(|s| **s != Status::Empty).count();
    // Seven fixed positions and a double-width overflow marker. Nothing
    // shifts when another agent joins or finishes.
    if occupied > 1 || self.agents.0[7] != Status::Empty {
      let wait_period = match self.mode { Mode::Waiting(p) => p, _ => 2400 };
      for (slot, status) in self.agents.0.iter().enumerate() {
        let colour = match status {
          Status::Empty => continue,
          Status::Done => Rgb([35, 170, 65]),
          Status::Running => if ms % 1600 < 800 { Rgb([30, 205, 240]) } else { Rgb([15, 75, 95]) },
          Status::Error => Rgb([255, 35, 35]),
          Status::Waiting => if ms % wait_period < wait_period / 2 { Rgb([255, 160, 15]) } else { Rgb([90, 40, 5]) },
        };
        row[slot * 2] = Some(colour);
        if slot == 7 { row[15] = Some(colour); }
      }
      return row;
    }
    // A failed solo tool stays red through retries until one succeeds.
    let solo_mode = if self.agents.0.contains(&Status::Waiting) {
      match self.mode { Mode::Waiting(p) => Mode::Waiting(p), _ => Mode::Waiting(2400) }
    } else if self.agents.0.contains(&Status::Error) { Mode::Error } else { self.mode };
    match solo_mode {
      Mode::Active => {
        let step = (ms / 100) % 30;
        let x = if step <= 15 { step } else { 30 - step };
        row[x as usize] = Some(Rgb([30, 205, 240]));
      },
      Mode::Waiting(period) => {
        let colour = if ms % period < period / 2 { Rgb([255, 160, 15]) } else { Rgb([90, 40, 5]) };
        // Expands from the edges as the wait escalates; not a strobe.
        let width = if period <= 1000 { 8 } else if period <= 1600 { 4 } else { 2 };
        for x in 0..width { row[x] = Some(colour); row[15-x] = Some(colour); }
      },
      Mode::Error => row.fill(Some(Rgb([255, 35, 35]))),
      Mode::Complete => {
        let head = (ms / 90) % 24;
        for x in 0..16 {
          if head >= x && head - x < 5 { row[x as usize] = Some(Rgb([35, 220, 70])); }
        }
      },
      Mode::Quiet => {},
    }
    row
  }

  pub fn paint(self, animation: &mut Animation) {
    // Quiet/custom displays remain untouched. Clawd reserves row zero.
    if self.mode == Mode::Quiet { return; }
    let mut ms = 0u32;
    for frame in &mut animation.frames {
      let mut image = frame.image.to_rgb8();
      if image.width() != 16 || image.height() != 16 { continue; }
      let background = *image.get_pixel(0, 0);
      for (x, pixel) in self.pixels(ms).iter().enumerate() {
        image.put_pixel(x as u32, 0, pixel.unwrap_or(background));
      }
      ms += u32::from(frame.header.time_in_milliseconds).max(10);
      frame.image = DynamicImage::ImageRgb8(image);
      frame.header.reuse_palette = false;
    }
    crate::rebuild_palettes(animation);
  }
}

#[cfg(test)]
mod tests {
  #![allow(clippy::unwrap_used)]
  #![allow(clippy::expect_used)]
  use super::*;
  #[test]
  fn only_new_attention_bypasses_overlay_batching() {
    let normal = Strip::for_face("delegating", Agents::default());
    let running = Strip::for_face("delegating", Agents::parse("v1\n0 running 100", 0).unwrap());
    let failed = Strip::for_face("delegating", Agents::parse("v1\n0 error 100", 0).unwrap());
    let waiting = Strip::for_face("delegating", Agents::parse("v1\n0 waiting 100", 0).unwrap());
    assert!(!running.attention_changed(normal));
    assert!(failed.attention_changed(running));
    assert!(waiting.attention_changed(failed));
    assert!(!running.attention_changed(waiting));
  }
  #[test]
  fn roster_validation_expiry_and_overflow() {
    let agents = Agents::parse("v1\n0 running 100\n2 done 50\n7 running 100\n7 waiting 100\n", 50).unwrap();
    assert_eq!(agents.0[0], Status::Running);
    assert_eq!(agents.0[2], Status::Empty);
    assert_eq!(agents.0[7], Status::Waiting);
    for bad in ["v2", "v1\n8 done 100", "v1\n0 huh 100", "v1\n0 done", "v1\n0 done 100 junk"] {
      assert!(Agents::parse(bad, 0).is_none());
    }
  }
  #[test]
  fn solo_moves_idle_is_quiet_and_alerts_escalate() {
    let empty = Agents::default();
    let active = Strip::for_face("writing", empty);
    assert_ne!(active.pixels(0), active.pixels(500));
    assert_eq!(active.pixels(0), active.pixels(3000));
    for face in ["chilling", "screensaver", "off", "meeting", "number"] {
      assert!(Strip::for_face(face, empty).pixels(0).iter().all(Option::is_none));
    }
    let count = |face| Strip::for_face(face, empty).pixels(0).iter().filter(|p| p.is_some()).count();
    assert!(count("alerting") < count("alerting2"));
    assert!(count("alerting2") < count("alerting3"));
  }
  #[test]
  fn agent_positions_survive_completion() {
    let mut agents = Agents::default();
    agents.0[0] = Status::Running;
    agents.0[3] = Status::Running;
    let before = Strip::for_face("working", agents).pixels(0);
    agents.0[0] = Status::Done;
    agents.0[5] = Status::Waiting;
    let after = Strip::for_face("working", agents).pixels(0);
    assert_eq!(before[6], after[6]);
    assert_eq!(after[0], Some(Rgb([35, 170, 65])));
    assert!(after[10].is_some());
    assert!(after[1].is_none());
  }

  #[test]
  fn solo_failures_persist_and_overflow_never_becomes_a_solo_dot() {
    let mut agents = Agents::default();
    agents.0[0] = Status::Error;
    let strip = Strip::for_face("reading", agents);
    assert!(strip.pixels(0).iter().all(|p| *p == Some(Rgb([255, 35, 35]))));
    assert_eq!(strip.pixels(0), strip.pixels(1000));
    agents.0[0] = Status::Waiting;
    assert_ne!(Strip::for_face("alerting", agents).pixels(0), Strip::for_face("alerting3", agents).pixels(0));
    agents = Agents::default();
    agents.0[7] = Status::Running;
    let row = Strip::for_face("working", agents).pixels(0);
    assert!(row[14].is_some() && row[15].is_some());
    assert!(row[..14].iter().all(Option::is_none));
  }

  #[test]
  fn real_gifs_preserve_art_timing_and_roundtrip_with_both_overlays() {
    use std::io::{BufReader, Cursor};
    use std::fs::File;
    for entry in std::fs::read_dir("integrations/claude-code/faces").unwrap() {
      let path = entry.unwrap().path();
      if path.extension().and_then(|s| s.to_str()) != Some("gif") { continue; }
      let face = path.file_stem().unwrap().to_str().unwrap();
      let mut animation = Animation::from_gif(&mut BufReader::new(File::open(&path).unwrap())).unwrap();
      crate::overlay_context_gauge(&mut animation, 70);
      let originals: Vec<_> = animation.frames.iter().map(|f| (f.image.to_rgb8(), f.header.time_in_milliseconds)).collect();
      let agents = Agents::parse("v1\n0 running 999\n1 done 999\n3 waiting 999\n4 error 999", 0).unwrap();
      Strip::for_face(face, agents).paint(&mut animation);
      let mut bytes = Vec::new();
      animation.save_to_divoom_format(&mut bytes).unwrap();
      let decoded = Animation::from_16x16(&mut Cursor::new(bytes)).unwrap();
      assert_eq!(decoded.frames.len(), originals.len());
      for ((frame, restored), (original, delay)) in animation.frames.iter().zip(&decoded.frames).zip(originals) {
        let image = frame.image.to_rgb8();
        assert_eq!(image, restored.image.to_rgb8(), "{} colour roundtrip", face);
        assert_eq!(frame.header.time_in_milliseconds, delay);
        for y in 1..16 { for x in 0..16 { assert_eq!(image.get_pixel(x,y), original.get_pixel(x,y), "{} art/context changed", face); } }
      }
    }
  }

  #[test]
  #[ignore = "optional visual review export; set DITOO_STRIP_PREVIEW_DIR"]
  fn export_strip_preview() {
    use std::io::BufReader;
    use std::fs::File;
    let out = std::path::PathBuf::from(std::env::var("DITOO_STRIP_PREVIEW_DIR").unwrap());
    std::fs::create_dir_all(&out).unwrap();
    let team = Agents::parse("v1\n0 running 999\n1 done 999\n2 waiting 999\n3 error 999", 0).unwrap();
    for (name, face, agents) in [
      ("solo", "working", Agents::default()), ("team", "delegating", team),
      ("waiting", "alerting", Agents::default()), ("urgent", "alerting3", Agents::default()),
      ("finished", "done", Agents::default()), ("resting", "chilling", Agents::default()),
    ] {
      let path = format!("integrations/claude-code/faces/{}.gif", face);
      let mut animation = Animation::from_gif(&mut BufReader::new(File::open(path).unwrap())).unwrap();
      Strip::for_face(face, agents).paint(&mut animation);
      for frame in &mut animation.frames {
        frame.image = frame.image.resize_exact(256,256,image::imageops::FilterType::Nearest);
      }
      animation.save_to_gif(&mut File::create(out.join(format!("{}.gif",name))).unwrap()).unwrap();
      animation.frames[0].image.save(out.join(format!("{}.png",name))).unwrap();
    }
  }
}
