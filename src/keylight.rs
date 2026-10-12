//! Drive the Ditoo's key backlight alongside the status faces.
//!
//! The device offers only three RELATIVE commands -- next effect, previous
//! effect, toggle on/off -- and acknowledges none of them, so there is no way
//! to ask which effect is showing or whether the keys are lit. Everything here
//! follows from that:
//!
//! - On/off is tracked as a belief, persisted by the daemon, and corrected by
//!   hand (`resync`) if someone changes the keys on the device itself.
//! - The user's chosen effect is never lost. Movement is expressed as an offset
//!   from it, and every pattern change first walks that offset back to zero.
//!   Alerts ping-pong between the chosen effect and its neighbour rather than
//!   cycling onward, so the offset never exceeds one and the way home is one
//!   step -- whatever the total number of effects, which nobody knows.

use std::time::{Duration, Instant};

pub(crate) const NEXT: u8 = 0;
pub(crate) const PREV: u8 = 1;
pub(crate) const TOGGLE: u8 = 2;

/// Gap between the steps of a one-shot flourish. Shorter and the device
/// visibly drops steps' worth of change into one blur.
const FLOURISH_STEP: Duration = Duration::from_millis(250);

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub(crate) enum Pattern {
  /// Keys dark.
  Off,
  /// Keys lit, on the user's own effect.
  On,
  /// Keys lit and alternating with the neighbouring effect at this period.
  Alternate(Duration),
  /// A quick there-and-back flourish, then lit.
  Ripple,
  /// Two quick blinks, then lit.
  Blink,
  /// Hands off: bring the effect home once, then leave everything alone.
  Manual
}

/// The key-light behaviour for whatever face the panel is showing.
///
/// Mirrors the faces' own logic: anything asking for you moves, and moves more
/// the longer it is ignored; work keeps the keys lit; anything idle or facing
/// outward at the room turns them off.
pub(crate) fn pattern_for(face: &str) -> Pattern {
  match face {
    "thinking" | "reading" | "reviewing" | "planning" | "number" | "custom" => Pattern::On,
    "working" | "writing" | "terminal" | "responding" => Pattern::Alternate(Duration::from_millis(2400)),
    "searching" | "connecting" => Pattern::Alternate(Duration::from_millis(1800)),
    "testing" | "building" | "installing" => Pattern::Alternate(Duration::from_millis(1000)),
    "compacting" | "delegating" => Pattern::Alternate(Duration::from_millis(1200)),
    "starting" | "done" | "taskdone" | "configuring" => Pattern::Ripple,
    "cancelled" => Pattern::Blink,
    "alerting" | "alert-question" | "alert-permission" | "alert-plan" => {
      Pattern::Alternate(Duration::from_millis(1500))
    }
    "alerting2" => Pattern::Alternate(Duration::from_millis(800)),
    "alerting3" => Pattern::Alternate(Duration::from_millis(400)),
    "success" => Pattern::Ripple,
    "error" => Pattern::Blink,
    _ => Pattern::Off
  }
}

pub(crate) struct KeyLight {
  on: bool,
  offset: i32,
  pattern: Option<Pattern>,
  flourish: Vec<u8>,
  last_step: Option<Instant>,
  synchronized: bool
}

impl KeyLight {
  pub(crate) fn new(on: bool, offset: i32) -> Self {
    KeyLight { on, offset, pattern: None, flourish: Vec::new(), last_step: None, synchronized: true }
  }

  /// Parse the persisted belief: `on 0`, `off 1`. Anything unreadable falls
  /// back to lit-on-home, which is how the keys ship.
  pub(crate) fn load(text: &str) -> Self {
    let mut words = text.split_whitespace();
    let on = words.next() != Some("off");
    let offset = words.next().and_then(|w| w.parse().ok()).unwrap_or(0);
    // A corrupted belief must not generate an unbounded run of relative steps.
    let mut result = KeyLight::new(on, if (-2..=2).contains(&offset) { offset } else { 0 });
    result.synchronized = words.next() != Some("uncertain") && (-2..=2).contains(&offset);
    result
  }

  pub(crate) fn save(&self) -> String {
    format!("{} {}{}\n", if self.on { "on" } else { "off" }, self.offset,
      if self.synchronized { "" } else { " uncertain" })
  }

  #[cfg(test)]
  pub(crate) fn is_on(&self) -> bool {
    self.on
  }

  #[cfg(test)]
  pub(crate) fn offset(&self) -> i32 {
    self.offset
  }

  /// Correct the on/off belief without sending anything -- for when someone
  /// changed the keys on the device and the belief is now wrong.
  pub(crate) fn resync(&mut self, on: bool) {
    self.on = on;
    self.synchronized = true;
    self.offset = 0; // the effect the user sees now becomes the new home
    self.pattern = None;
    self.flourish.clear();
  }

  /// Relative writes have no acknowledgement. After a transport failure,
  /// retrying a toggle may invert a command the device already accepted.
  /// Stop automatic writes until a human resyncs the observed on/off state.
  pub(crate) fn invalidate(&mut self) {
    self.synchronized = false;
    self.pattern = None;
    self.flourish.clear();
  }

  /// Record a command sent on the user's behalf. Next/previous deliberately
  /// change the user's chosen effect, so the offset does not move with them.
  pub(crate) fn manual(&mut self, mode: u8) {
    if mode == TOGGLE {
      self.on = !self.on;
    }
  }

  /// Steps needed to return to the user's own effect.
  pub(crate) fn go_home(&mut self) -> Vec<u8> {
    let mut out = Vec::new();
    if !self.synchronized {
      return out;
    }
    while self.offset > 0 {
      self.apply(PREV);
      out.push(PREV);
    }
    while self.offset < 0 {
      self.apply(NEXT);
      out.push(NEXT);
    }
    out
  }

  fn apply(&mut self, mode: u8) {
    match mode {
      NEXT => self.offset += 1,
      PREV => self.offset -= 1,
      _ => self.on = !self.on
    }
  }

  fn light(&mut self, lit: bool, out: &mut Vec<u8>) {
    if self.on != lit {
      self.apply(TOGGLE);
      out.push(TOGGLE);
    }
  }

  /// Advance to `now` under `target`, returning the commands to send in order.
  pub(crate) fn tick(&mut self, target: Pattern, now: Instant) -> Vec<u8> {
    let mut out = Vec::new();
    if !self.synchronized {
      return out;
    }

    if self.pattern != Some(target) {
      self.pattern = Some(target);
      self.flourish.clear();
      out.extend(self.go_home());
      match target {
        Pattern::Off => self.light(false, &mut out),
        Pattern::On | Pattern::Alternate(_) => self.light(true, &mut out),
        Pattern::Ripple => {
          self.light(true, &mut out);
          self.flourish = vec![NEXT, NEXT, PREV, PREV];
        }
        Pattern::Blink => {
          self.light(true, &mut out);
          self.flourish = vec![TOGGLE; 4];
        }
        Pattern::Manual => {}
      }
      self.last_step = Some(now);
      return out;
    }

    let since = self.last_step.map(|t| now.saturating_duration_since(t));
    if !self.flourish.is_empty() {
      if since.is_none_or(|d| d >= FLOURISH_STEP) {
        let mode = self.flourish.remove(0);
        self.apply(mode);
        out.push(mode);
        self.last_step = Some(now);
      }
    } else if let Pattern::Alternate(every) = target {
      if since.is_none_or(|d| d >= every) {
        let mode = if self.offset == 0 { NEXT } else { PREV };
        self.apply(mode);
        out.push(mode);
        self.last_step = Some(now);
      }
    }
    out
  }
}

#[cfg(test)]
mod tests {
  use super::*;

  fn run(keys: &mut KeyLight, target: Pattern, start: Instant, ms: u64) -> Vec<u8> {
    let mut sent = Vec::new();
    let mut t = 0;
    while t <= ms {
      sent.extend(keys.tick(target, start + Duration::from_millis(t)));
      t += 250;
    }
    sent
  }

  #[test]
  fn an_alert_never_strays_more_than_one_effect_from_home() {
    let mut keys = KeyLight::new(true, 0);
    let t = Instant::now();
    run(&mut keys, Pattern::Alternate(Duration::from_millis(400)), t, 60_000);
    assert!((0..=1).contains(&keys.offset()), "offset drifted to {}", keys.offset());
  }

  #[test]
  fn leaving_an_alert_restores_the_users_effect_exactly() {
    // Stop at every point in the cycle, including mid-step.
    for stop_ms in (0..6_000).step_by(250) {
      let mut keys = KeyLight::new(true, 0);
      let t = Instant::now();
      run(&mut keys, Pattern::Alternate(Duration::from_millis(800)), t, stop_ms);
      keys.tick(Pattern::On, t + Duration::from_millis(stop_ms + 1));
      assert_eq!(keys.offset(), 0, "stopping at {}ms left the effect moved", stop_ms);
    }
  }

  #[test]
  fn flourishes_end_where_they_started() {
    for flourish in [Pattern::Ripple, Pattern::Blink] {
      let mut keys = KeyLight::new(true, 0);
      let sent = run(&mut keys, flourish, Instant::now(), 3_000);
      assert!(sent.len() >= 4, "{:?} should visibly do something", flourish);
      assert_eq!(keys.offset(), 0, "{:?} moved the effect", flourish);
      assert!(keys.is_on(), "{:?} left the keys dark", flourish);
    }
  }

  #[test]
  fn interrupting_a_ripple_still_comes_home() {
    let mut keys = KeyLight::new(true, 0);
    let t = Instant::now();
    run(&mut keys, Pattern::Ripple, t, 500); // two NEXTs in: offset 2
    assert_eq!(keys.offset(), 2);
    let sent = keys.tick(Pattern::Off, t + Duration::from_millis(600));
    assert_eq!(sent, vec![PREV, PREV, TOGGLE]);
    assert_eq!(keys.offset(), 0);
    assert!(!keys.is_on());
  }

  #[test]
  fn on_and_off_only_toggle_when_the_belief_says_so() {
    let mut keys = KeyLight::new(true, 0);
    let t = Instant::now();
    assert_eq!(keys.tick(Pattern::On, t), Vec::<u8>::new(), "already lit");
    assert_eq!(keys.tick(Pattern::Off, t), vec![TOGGLE]);
    assert_eq!(keys.tick(Pattern::Off, t + Duration::from_secs(9)), Vec::<u8>::new());
    keys.resync(true); // someone lit them by hand
    assert_eq!(keys.tick(Pattern::On, t), Vec::<u8>::new(), "resync means no send");
  }

  #[test]
  fn manual_next_moves_home_rather_than_being_undone() {
    let mut keys = KeyLight::new(true, 0);
    keys.manual(NEXT);
    assert_eq!(keys.go_home(), Vec::<u8>::new(), "the user's choice is the new home");
    keys.manual(TOGGLE);
    assert!(!keys.is_on());
  }

  #[test]
  fn the_belief_survives_a_restart() {
    let mut keys = KeyLight::new(false, 1);
    let restored = KeyLight::load(&keys.save());
    assert!(!restored.is_on());
    assert_eq!(restored.offset(), 1);
    assert!(KeyLight::load("garbage").is_on(), "unreadable falls back to lit");
    assert_eq!(keys.go_home(), vec![PREV]);
  }

  #[test]
  fn every_face_has_a_deliberate_pattern() {
    assert_eq!(pattern_for("working"), Pattern::Alternate(Duration::from_millis(2400)));
    assert_eq!(pattern_for("alert-permission"), Pattern::Alternate(Duration::from_millis(1500)));
    assert!(matches!(pattern_for("alerting3"), Pattern::Alternate(d) if d < Duration::from_millis(500)));
    for quiet in ["chilling", "screensaver", "meeting", "busy", "off"] {
      assert_eq!(pattern_for(quiet), Pattern::Off, "{} should leave the keys dark", quiet);
    }
  }

  #[test]
  fn failed_relative_writes_require_resync_not_blind_replay() {
    let mut keys = KeyLight::new(true, 0);
    keys.tick(Pattern::Ripple, Instant::now());
    keys.invalidate();
    assert!(keys.tick(Pattern::Off, Instant::now()).is_empty());
    assert!(keys.go_home().is_empty());
    let mut restored = KeyLight::load(&keys.save());
    assert!(restored.tick(Pattern::Off, Instant::now()).is_empty());
    restored.resync(true);
    assert_eq!(restored.tick(Pattern::Off, Instant::now()), vec![TOGGLE]);
  }

  #[test]
  fn corrupt_offset_never_sends_an_unbounded_recovery() {
    let mut keys = KeyLight::load("on 2147483647");
    assert!(keys.go_home().is_empty());
    assert!(keys.tick(Pattern::Ripple, Instant::now()).is_empty());
  }
}
