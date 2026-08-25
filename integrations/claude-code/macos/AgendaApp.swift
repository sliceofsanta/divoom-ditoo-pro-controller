// Bundled build of the next-event helper.
//
// Exists as an .app because macOS will not show a Calendar permission prompt
// for a bare CLI binary launched from a non-GUI parent, and the Calendars pane
// in System Settings has no "add application" button -- an app can only get
// there by ASKING. A bundle can ask.
//
// Writes the minutes until the next event to ~/.claude/ditoo/agenda, or
// removes the file when there is nothing to show.
import Foundation
import EventKit

func agendaPath() -> URL {
  let rundir = ProcessInfo.processInfo.environment["DITOO_RUNDIR"]
    ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".claude/ditoo").path
  try? FileManager.default.createDirectory(atPath: rundir, withIntermediateDirectories: true)
  return URL(fileURLWithPath: rundir).appendingPathComponent("agenda")
}

func clear() {
  try? FileManager.default.removeItem(at: agendaPath())
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
  clear()
  exit(2)
}

let now = Date()
let predicate = store.predicateForEvents(
  withStart: now, end: now.addingTimeInterval(24 * 3600), calendars: nil)

let next = store.events(matching: predicate)
  .filter { !$0.isAllDay && $0.startDate > now }
  .sorted { $0.startDate < $1.startDate }
  .first

guard let event = next else {
  clear()
  exit(1)
}

let minutes = Int(event.startDate.timeIntervalSince(now) / 60)
try? "\(minutes)\n".write(to: agendaPath(), atomically: true, encoding: .utf8)
exit(0)
