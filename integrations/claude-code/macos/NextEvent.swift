// Print the minutes until the next calendar event starting within the day.
// Prints nothing when there is no such event, or when access is not granted.
//
// Used by ditoo-agenda.sh, which writes the number where the daemon can render
// it. Kept as a separate tiny binary because EventKit needs a usage
// description and a TCC grant, and confining that to one place keeps the
// daemon itself free of calendar permissions.
import Foundation
import EventKit

let store = EKEventStore()
let semaphore = DispatchSemaphore(value: 0)
var granted = false

if #available(macOS 14.0, *) {
  store.requestFullAccessToEvents { ok, _ in granted = ok; semaphore.signal() }
} else {
  store.requestAccess(to: .event) { ok, _ in granted = ok; semaphore.signal() }
}
_ = semaphore.wait(timeout: .now() + 20)

guard granted else {
  FileHandle.standardError.write("calendar access not granted\n".data(using: .utf8)!)
  exit(2)
}

let now = Date()
let end = now.addingTimeInterval(24 * 3600)
let predicate = store.predicateForEvents(withStart: now, end: end, calendars: nil)

// All-day events are not appointments you need warning about, and an event
// already under way is not something to count down to.
let next = store.events(matching: predicate)
  .filter { !$0.isAllDay && $0.startDate > now }
  .sorted { $0.startDate < $1.startDate }
  .first

guard let event = next else { exit(1) }
let minutes = Int(event.startDate.timeIntervalSince(now) / 60)
print(minutes)
