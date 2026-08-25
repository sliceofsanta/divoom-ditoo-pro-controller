// Bundled build of the calendar helper.
//
// Exists as an .app because macOS will not show a Calendar permission prompt
// for a bare CLI binary launched from a non-GUI parent, and the Calendars pane
// in System Settings has no "add application" button -- an app can only get
// there by ASKING. A bundle can ask.
//
// Answers two different questions into two different files:
//
//   agenda   minutes until the next event starts -- something to count down to
//   meeting  minutes left in an event already under way -- something to announce
//
// They are genuinely different. A countdown is for you, so you can decide
// whether to start something; the meeting marker faces outward, at whoever is
// about to walk over. Keeping them apart means neither has to guess which one
// a single number meant.
import Foundation
import EventKit

func rundir() -> URL {
  let dir = ProcessInfo.processInfo.environment["DITOO_RUNDIR"]
    ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".claude/ditoo").path
  try? FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
  return URL(fileURLWithPath: dir)
}

let agendaPath = rundir().appendingPathComponent("agenda")
let meetingPath = rundir().appendingPathComponent("meeting")

func write(_ minutes: Int, to path: URL) {
  try? "\(minutes)\n".write(to: path, atomically: true, encoding: .utf8)
}

func clear(_ path: URL) {
  try? FileManager.default.removeItem(at: path)
}

// Any failure clears BOTH, so a stale countdown or a meeting that ended hours
// ago never lingers on the panel.
func clearAll() {
  clear(agendaPath)
  clear(meetingPath)
}

let store = EKEventStore()
let semaphore = DispatchSemaphore(value: 0)
var granted = false

if #available(macOS 14.0, *) {
  store.requestFullAccessToEvents { ok, _ in granted = ok; semaphore.signal() }
} else {
  store.requestAccess(to: .event) { ok, _ in granted = ok; semaphore.signal() }
}
_ = semaphore.wait(timeout: .now() + 30)

guard granted else {
  clearAll()
  exit(2)
}

// A test seam. The in-progress branch is otherwise only exercisable by
// waiting for a real meeting to start, which is not a test anyone runs -- so
// this lets it be checked against real calendar data by rewinding to a time
// when a meeting WAS under way. Unset in normal use, where it is just Date().
let now = ProcessInfo.processInfo.environment["DITOO_FAKE_NOW"]
  .flatMap(Double.init)
  .map(Date.init(timeIntervalSince1970:)) ?? Date()

// The predicate matches events OVERLAPPING the window, so one that started
// before now and is still running is included -- which is what makes the
// in-progress question answerable at all.
let predicate = store.predicateForEvents(
  withStart: now, end: now.addingTimeInterval(24 * 3600), calendars: nil)
let events = store.events(matching: predicate).filter { !$0.isAllDay }

// In a meeting right now: the one finishing soonest, so back-to-back bookings
// report the one you are actually in rather than the one you are also in.
if let current = events
  .filter({ $0.startDate <= now && $0.endDate > now })
  .sorted(by: { $0.endDate < $1.endDate })
  .first
{
  // Round UP, so a meeting with forty seconds left still reads as 1 rather
  // than 0 -- which would be indistinguishable from "no meeting".
  write(max(1, Int(ceil(current.endDate.timeIntervalSince(now) / 60))), to: meetingPath)
} else {
  clear(meetingPath)
}

// An event already under way is not something to count down to, so the
// countdown still only looks forward.
if let next = events
  .filter({ $0.startDate > now })
  .sorted(by: { $0.startDate < $1.startDate })
  .first
{
  write(Int(next.startDate.timeIntervalSince(now) / 60), to: agendaPath)
} else {
  clear(agendaPath)
}
exit(0)
