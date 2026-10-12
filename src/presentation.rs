//! Turn a bursty event stream into a glanceable display without delaying alerts.
use std::time::Duration;
use crate::divoom_file_format::animation::Animation;

/// Resume a loop at the nearest preceding frame when only its overlays change.
/// Keep every frame and delay so uploads never shorten the underlying story.
pub(crate) fn resume_animation(animation: &mut Animation, elapsed: Duration) -> Duration {
  let total: u64 = animation.frames.iter()
    .map(|f| u64::from(f.header.time_in_milliseconds).max(10)).sum();
  if total == 0 { return Duration::ZERO; }
  let target = (elapsed.as_millis() % u128::from(total)) as u64;
  let mut phase = 0;
  let mut index = 0;
  for (i, frame) in animation.frames.iter().enumerate() {
    let duration = u64::from(frame.header.time_in_milliseconds).max(10);
    if phase + duration > target { index = i; break; }
    phase += duration;
  }
  animation.frames.rotate_left(index);
  // Any frame may now be the first one; make its palette self-contained.
  for frame in &mut animation.frames { frame.header.reuse_palette = false; }
  Duration::from_millis(phase)
}

#[derive(Default)]
pub(crate) struct Stabilizer {
  shown: Option<String>,
  since: Duration,
  pending: Option<(String, Duration)>,
}

fn urgent(state: &str) -> bool {
  state.starts_with("alert") || matches!(state, "error" | "off" | "number" | "custom")
    || state.ends_with(":now")
}

impl Stabilizer {
  pub fn select(&mut self, target: &str, now: Duration) -> String {
    if self.shown.as_deref() == Some(target) {
      self.pending = None;
      return target.to_string();
    }
    // Enter team mode and surface urgent news immediately. Once input has
    // actually resumed, do not keep showing an obsolete permission request.
    let immediate = self.shown.is_none() || urgent(target) || target == "delegating"
      || self.shown.as_deref().is_some_and(|s| s.starts_with("alert"));
    let pending_since = match &self.pending {
      Some((s, since)) if s == target => *since,
      _ => {
        self.pending = Some((target.to_string(), now));
        now
      }
    };
    let stable_for = now.saturating_sub(pending_since);
    let settle = if matches!(target, "success" | "done" | "chilling" | "screensaver") { 4 } else { 2 };
    if immediate || (stable_for >= Duration::from_secs(settle)
      && now.saturating_sub(self.since) >= Duration::from_secs(4)) {
      self.shown = Some(target.to_string());
      self.since = now;
      self.pending = None;
    }
    // Always set by now: `immediate` holds whenever nothing was shown yet.
    self.shown.clone().unwrap_or_else(|| target.to_string())
  }
}

#[cfg(test)]
mod tests {
  #![allow(clippy::unwrap_used)]
  #![allow(clippy::expect_used)]
  use super::*;
  fn at(seconds: u64) -> Duration { Duration::from_secs(seconds) }
  #[test]
  fn overlay_refresh_resumes_workshop_without_losing_frames() {
    use std::fs::File;
    use std::io::{BufReader, Cursor};
    let mut animation = Animation::from_gif(&mut BufReader::new(
      File::open("integrations/claude-code/faces/delegating.gif").unwrap())).unwrap();
    let expected = animation.frames[7].image.to_rgb8();
    let count = animation.frames.len();
    let duration: u64 = animation.frames.iter().map(|f| u64::from(f.header.time_in_milliseconds)).sum();
    assert_eq!(resume_animation(&mut animation, Duration::from_millis(1500)), Duration::from_millis(1400));
    assert_eq!(animation.frames[0].image.to_rgb8(), expected);
    assert_eq!(animation.frames.len(), count);
    assert_eq!(animation.frames.iter().map(|f| u64::from(f.header.time_in_milliseconds)).sum::<u64>(), duration);
    let mut bytes = Vec::new();
    animation.save_to_divoom_format(&mut bytes).unwrap();
    let restored = Animation::from_16x16(&mut Cursor::new(bytes)).unwrap();
    assert_eq!(restored.frames[0].image.to_rgb8(), expected);
    assert_eq!(restored.frames.len(), count);
  }
  #[test]
  fn resume_wraps_and_handles_empty_animation() {
    use std::fs::File;
    use std::io::BufReader;
    let mut empty = Animation { frames: vec![] };
    assert_eq!(resume_animation(&mut empty, at(60)), Duration::ZERO);
    let mut animation = Animation::from_gif(&mut BufReader::new(
      File::open("integrations/claude-code/faces/delegating.gif").unwrap())).unwrap();
    let first = animation.frames[0].image.to_rgb8();
    let duration: u64 = animation.frames.iter().map(|f| u64::from(f.header.time_in_milliseconds)).sum();
    assert_eq!(resume_animation(&mut animation, Duration::from_millis(duration*4)), Duration::ZERO);
    assert_eq!(animation.frames[0].image.to_rgb8(), first);
  }
  #[test]
  fn rapid_tools_do_not_flip_the_face() {
    let mut s = Stabilizer::default();
    assert_eq!(s.select("thinking", at(0)), "thinking");
    for (i, state) in ["reading", "writing", "testing", "reading", "terminal"].iter().enumerate() {
      assert_eq!(s.select(state, at(i as u64+1)), "thinking");
    }
    assert_eq!(s.select("terminal", at(7)), "terminal");
  }
  #[test]
  fn no_false_success_between_background_reports() {
    let mut s = Stabilizer::default();
    s.select("delegating", at(0));
    assert_eq!(s.select("success", at(10)), "delegating");
    assert_eq!(s.select("success", at(13)), "delegating");
    assert_eq!(s.select("delegating", at(13)), "delegating");
    assert_eq!(s.select("success", at(20)), "delegating");
    assert_eq!(s.select("success", at(24)), "success");
  }
  #[test]
  fn alerts_and_recovery_are_immediate() {
    let mut s = Stabilizer::default();
    s.select("delegating", at(0));
    assert_eq!(s.select("alert-permission", at(1)), "alert-permission");
    assert_eq!(s.select("delegating", at(2)), "delegating");
    assert_eq!(s.select("error", at(3)), "error");
    assert_eq!(s.select("off", at(3)), "off");
  }
}
