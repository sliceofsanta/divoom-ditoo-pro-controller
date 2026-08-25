# Claude Code status display

Turn a Divoom Ditoo Pro into a **Clauddy desk companion** for
[Claude Code](https://claude.com/claude-code). The art follows the wonderfully
simple staging of [Clauddy MiniToo](https://github.com/bugzmanov/divoom-minitoo/tree/main/apps/clauddy/assets):
one large flat terracotta mascot, tiny black eyes and feet, charcoal background,
and one oversized action or prop. The frames are original 16x16 drawings made
for this display rather than resized copies of the reference assets.

| State | When | Animation |
|---|---|---|
| `thinking` | you submit a prompt | **BLUEPRINT:** Clauddy opens one huge cyan building plan |
| `working` | Claude runs a tool | **HAMMERING:** Clauddy works a brick at the bench with a huge hammer |
| `compacting` | Claude compacts context | **SQUEEZE:** loose plan sheets compress into one strapped bundle |
| `alerting` | Claude needs your input | **HEY:** one slow exclamation and one raised hand |
| `alerting2` | still waiting after 1 minute | **STILL WAITING:** a larger flashing mark and both hands up |
| `alerting3` | still waiting after 5 minutes | **ALARM:** giant red strobe and jumping Clauddy |
| `success` | Claude finished responding | **BUILT:** a finished glowing workshop floats above a happy jump |
| `error` | a tool or the turn failed | **BROKEN:** the workshop cracks while Clauddy stares with X eyes |
| `chilling` | a session starts, or manual | **TEA BREAK:** closed eyes, a steaming mug and a tiny floating Z |
| `off` | the session ends, or manual | blank display |

Alerts split by what they actually want from you, so you can tell a keystroke
from twenty minutes of reading without walking over:

| State | When | Animation |
|---|---|---|
| `alert-permission` | a permission prompt | orange padlock -- one keystroke, go press it |
| `alert-question` | a question | amber question mark -- needs thought |
| `alert-plan` | a plan to review | violet page of text -- sit down and read |

Anything unrecognised stays plain `alerting` rather than guessing wrong. All
three outrank ordinary work and all three fall back onto the same escalation
ladder once ignored, because after five minutes *why* it wants you stops being
the useful part.

Two more face outward, at whoever is deciding whether to walk over, and only
ever appear when the panel would otherwise be idle:

| State | When | Animation |
|---|---|---|
| `meeting` | you are in one right now | teal calendar |
| `busy` | macOS Focus is on | one heavy red bar |

## Parallel agents

When a turn fans out into subagents, the top row grows one pip per agent --
bright for finished, dim for still running -- so a long fan-out says how much
of it is left instead of just "working". Wired to the `SubagentStart` and
`SubagentStop` hooks (note: *not* `TaskCreated`/`TaskCompleted`, which are for
teammates and never fire for subagents). Pips clear at the start of each turn.

Past 16 agents the pips would be thinner than a pixel, so it scales down to a
proportion, rounded down -- it will never claim more progress than there is.

Clauddy remains the largest object in every frame. There is no cream face panel,
costume, scenery or split-screen composition: the terracotta body itself is the
character. Cyan is reserved for plans and tidy-up, yellow for attention and
completion, and red only for failure or the final alert escalation.

The point is still the `alerting` state: you can look away from the terminal and
notice the moment Claude is blocked on you. The other poses turn the display
from a status light into a tiny desk companion.

## Any command, not just Claude Code

```bash
./integrations/claude-code/ditoo-run.sh cargo test
./integrations/claude-code/ditoo-run.sh npm run build
```

Shows `working` while it runs, then `success` or `error` from the exit code.
The command's output and exit status pass straight through, so it wraps
anything -- including inside a pipeline or a Makefile. Each wrapped command
takes its own slot in the merge, so several can run at once without clobbering
a Claude Code session's state, and the slot is released even on Ctrl-C.

It reports verdicts as `success:now` / `error:now`. The `:now` suffix tells the
daemon the caller means it: the earned-celebration rule (ten minutes of work
before a celebration counts) is right for a Claude turn and wrong for a build
that passed in four seconds.

## Watching anything that can be checked from a shell

```bash
./integrations/claude-code/ditoo-watch.sh --name ci --interval 60 -- \
  gh run list -R me/repo -L1 --json conclusion -q '.[0].conclusion=="success"'

./integrations/claude-code/ditoo-watch.sh --name tests --count -- \
  sh -c 'grep -c FAIL out.txt'
```

Where `ditoo-run.sh` wraps a command you are running, this polls one you are
waiting on -- a CI run, a deploy, a queue draining. Exit 0 is `success`,
anything else is `error`; `--count` shows the first integer the command prints
instead, which is how a suite reports *how much* failed rather than just that
it did. Zero is green, anything else red.

Each watch takes its own slot in the merge, so several run at once and the one
with the worst news wins -- and something that needs YOU still outranks all of
them. Ctrl-C releases the slot.

## Coming back to it later

A verdict does not decay to idle while nobody has come back to it. The
six-second decay is right when you are sitting there and wrong when you are
not, so a suite that went red overnight is still red when you sit down. Typing
anything releases the hold, which is what the `turn` subcommand on
`UserPromptSubmit` signals.

For the same reason a verdict outlives its session going stale: `working` is a
claim about the present and expires with the session that made it, but a
verdict is a claim about the past and staying true is the point.

## Next-meeting countdown (optional)

When the panel is idle and a meeting starts within the hour, it shows how many
minutes are left: the number in the middle, and a ring around the edge that
drains as the time runs out.

The ring is doing the explaining. A bare number could be nine of anything --
minutes, messages, o'clock. A ring visibly emptying around it is a timer, which
needs no caption. The colour backs it up: blue while it is far off, amber
inside ten minutes, red inside three, and in the last three minutes the ring
blinks, because by then you should be looking up rather than reading a number.

Anything that is actually telling you something outranks it, so an alert still
wins.

The same helper also reports a meeting **already under way**, which shows the
`meeting` glyph instead of a countdown. They are different questions for
different people: a countdown faces inward, at you deciding whether to start
something; the meeting glyph faces outward, at whoever is deciding whether to
walk over. Being in one outranks one that is merely coming.

```bash
./integrations/claude-code/ditoo-agenda.sh          # writes the number once
* * * * * /ABSOLUTE/PATH/ditoo-agenda.sh            # keep it current
```

`install-launchagent.sh` also registers a second agent that refreshes the
number every minute, so once installed there is nothing to run by hand.

**Granting calendar access.** The helper is an `.app` bundle
(`macos/DitooAgenda.app`) rather than a plain binary, and the reason is worth
knowing: the Calendars pane in System Settings has no "add application" button
-- an app can only appear there by ASKING, and macOS will not show that prompt
for a CLI binary launched from a non-GUI parent. A bundle can ask. Launch it
once and allow the prompt:

```bash
open -a integrations/claude-code/macos/DitooAgenda.app
```

For the same reason `ditoo-agenda.sh` starts it with `open` rather than running
the executable inside the bundle: TCC grants the BUNDLE, and invoking the inner
binary from a shell attributes the request to whatever spawned the shell, which
is refused.

Without the grant nothing is written and the panel shows the normal idle face
-- the countdown is additive, never a prerequisite.

## Launcher shortcuts

`raycast/` holds one-line scripts for Raycast (point Raycast at that folder in
Extensions > Script Commands). They are ordinary shell scripts, so Alfred,
Shortcuts or a keybinding can call them just as well:

| Script | Does |
|---|---|
| `ditoo-idle.sh` | show the idle face |
| `ditoo-alert.sh` | raise an alert -- useful as a timer or a nudge |
| `ditoo-draw.sh <image>` | put any image on the panel |
| `ditoo-off.sh` | blank it |
| `ditoo-status.sh` | what the daemon is doing |

## Focus and sleep

Both are automatic, nothing to configure.

While a macOS **Focus** mode is on, alerts escalate at half the usual delay.
Focus suppresses notifications, which makes the physical panel the channel that
still works -- so it should try harder, not less.

When the Mac **sleeps**, the Bluetooth link dies. The daemon notices the gap in
wall-clock time on waking and rebuilds the connection rather than writing into a
dead one.

## Run it from login

```bash
./integrations/claude-code/install-launchagent.sh          # install
./integrations/claude-code/install-launchagent.sh remove   # uninstall
```

Registers a LaunchAgent so the daemon starts at login and is restarted if it
dies, making the panel a permanent surface rather than something that exists
only while a Claude Code session is open.

The installer COPIES the binary, scripts and faces into
`~/Library/Application Support/ditoo`, because macOS will not let a LaunchAgent
execute anything inside `~/Documents`. **Re-run it after changing faces or
rebuilding** -- the agent uses the copies, not the repository.

## Drawing anything

```bash
./integrations/claude-code/ditoo-state.sh draw picture.gif
```

Shows any image the tool can read (GIF, PNG, JPEG, BMP, WebP; animated GIFs
animate). It is copied into the run directory, never into `faces/`, so it never
overwrites your artwork -- and it stays up only until the next status change,
which the hooks trigger constantly. It is for a deliberate moment, not a
persistent display.

A `ditoo` skill in `.claude/skills/` lets Claude reach for this itself.

## Idle screensaver (optional)

After 30 minutes idle the panel falls through to `screensaver.gif`. With no
such file it simply stays on `chilling`.

The bundled one is generated rather than hand-drawn -- `make_screensaver.py`
builds drifting embers using the palette sampled from the hand-drawn faces, so
it belongs to the set without being mistakable for a status. Replace it like
any other face. Only idle ages into it -- a state that is telling you something is
never interrupted.

```bash
DITOO_SCREENSAVER_AFTER_SECS=0    # switch it off entirely
```

Or hand the panel back to the device's own clock instead of showing art:

```bash
echo 61 > ~/.claude/ditoo/clock     # any clock face id; remove the file to undo
```

A clock is the one thing an animation cannot be -- it shows the actual time --
so an idle panel in the evening is more use telling you that. It takes effect
immediately, and the next state to say something takes the panel straight back.

## Context fuel gauge (optional)

Claude Code can forward how full the context window is, and the daemon paints
it as a bar along the bottom row of whatever face is showing -- green, amber
past half, red when a compact is close. A glance tells you how much room is
left.

It is **off by default and composites over your artwork**, so it is your call:

```json
"statusLine": {
  "type": "command",
  "command": "/ABSOLUTE/PATH/integrations/claude-code/ditoo-context.sh"
}
```

Delete `~/.claude/ditoo/context` (or remove the statusLine entry) and the
faces render exactly as drawn again. To try it without wiring anything up:

```bash
echo 75 > ~/.claude/ditoo/context     # bar appears
rm ~/.claude/ditoo/context            # artwork restored
```

## Replacing the animations

The faces are plain assets -- swap them freely. The daemon reads
`<state>.gif` from the faces directory (falling back to `<state>.png`), so a
new animation is a file drop and a `ditoo-state.sh` restart away.

**Hard requirements**

| | |
|---|---|
| Size | exactly **16x16 pixels**, no padding or borders |
| Format | animated **GIF** (a `.png` is accepted as a single frame) |
| Frames | 6-10 works well; 1 is fine for a still |
| Frame delay | 80-260ms. Under ~80ms reads as a blur on LEDs |
| Colours | at most 256, which 256 pixels can never exceed -- so no constraint in practice |
| Size on wire | 400-1300 bytes is typical; larger just takes longer to send |

**What this display actually rewards** -- learned the hard way here:

- **Colour is the signal.** From across a room you see a colour and a rhythm,
  nothing else. Two states that share a palette are two states you cannot tell
  apart without walking over.
- **Every frame must differ.** Duplicate frames read as a stutter. Watch for
  this specifically: if a shape cycle and a colour pulse share a period, they
  alias and an eight-frame loop collapses into four. Give them different beats.
- **Subtle motion vanishes.** Movement under about 1.5 pixels quantises away
  entirely -- a gentle breath simply sits still. Move things further than feels
  right on a monitor.
- **Silhouette barely survives.** Shapes only resolve up close. Motion and
  colour carry the meaning; detail is decoration.

**Verify a new face before trusting it** -- this catches a malformed GIF, a
wrong size and a frame-count surprise in one go:

```bash
divoom-ditoo-pro-controller convert to-divoom16 faces/working.gif /tmp/f.d16
RUST_LOG=debug divoom-ditoo-pro-controller debug-image /tmp/f.d16 | grep 'Frame #'
```

## The daemon (read this first)

Each connect/disconnect makes the device play its Bluetooth chime, and no
volume setting silences it -- the prompt plays at a fixed level. Connecting per
command therefore means a chime every time the state changes.

The daemon fixes it by connecting **once** and holding the connection:

```bash
./integrations/claude-code/ditoo-state.sh start   # one chime, then silence
./integrations/claude-code/ditoo-state.sh stop    # releases the device
```

While it runs, state changes are a file write and nothing else -- measured at
one connection across twelve state changes. Wire it to `SessionStart` (below)
and you get one chime when you first open Claude Code and none after.

Two consequences worth knowing:

- **The device cannot play audio while the daemon holds it.** Run `stop` when
  you want to use it as a speaker. The two uses are mutually exclusive on this
  hardware.
- **The daemon outlives a session on purpose**, so several Claude Code windows
  share one connection instead of fighting over the device.

Without a daemon everything still works -- the script falls back to connecting
per change, chime and all.

## Setup

**1. Build the controller** (from the repository root):

```bash
cargo build --release
```

On macOS, build without the `text`/`video` features unless you have `fontconfig`
and `mpv` installed:

```bash
cargo build --release --no-default-features --features all-image-formats
```

**2. Pair the Ditoo Pro** and confirm the CLI reaches it:

```bash
./target/release/divoom-ditoo-pro-controller volume get
```

macOS users: the terminal app needs a one-time Bluetooth grant in
**System Settings > Privacy & Security > Bluetooth**. See the macOS section of
the main [README](../../README.md).

**3. Check the script works** before wiring it into hooks:

```bash
./integrations/claude-code/ditoo-state.sh thinking
./integrations/claude-code/ditoo-state.sh success
./integrations/claude-code/ditoo-state.sh status
```

`status` prints the desired/applied state, whether a worker is running, which
binary it resolved, and the tail of the log -- start here when something looks
wrong.

**4. Add the hooks** to `~/.claude/settings.json`. Use the absolute path to your
checkout. The `SessionStart` entry is what starts the daemon:

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [{ "type": "command", "async": true,
        "command": "/ABSOLUTE/PATH/integrations/claude-code/ditoo-state.sh start" }] }
    ],
    "UserPromptSubmit": [
      { "hooks": [{ "type": "command", "async": true,
        "command": "/ABSOLUTE/PATH/integrations/claude-code/ditoo-state.sh thinking" }] }
    ],
    "PreToolUse": [
      { "hooks": [{ "type": "command", "async": true,
        "command": "/ABSOLUTE/PATH/integrations/claude-code/ditoo-state.sh working" }] }
    ],
    "PermissionRequest": [
      { "hooks": [{ "type": "command", "async": true,
        "command": "/ABSOLUTE/PATH/integrations/claude-code/ditoo-state.sh alerting" }] }
    ],
    "Notification": [
      { "matcher": "permission_prompt|idle_prompt|agent_needs_input|elicitation_dialog|elicitation_url_dialog",
        "hooks": [{ "type": "command", "async": true,
        "command": "/ABSOLUTE/PATH/integrations/claude-code/ditoo-state.sh alerting" }] }
    ],
    "PostToolUseFailure": [
      { "hooks": [{ "type": "command", "async": true,
        "command": "/ABSOLUTE/PATH/integrations/claude-code/ditoo-state.sh error" }] }
    ],
    "Stop": [
      { "hooks": [{ "type": "command", "async": true,
        "command": "/ABSOLUTE/PATH/integrations/claude-code/ditoo-state.sh success" }] }
    ],
    "StopFailure": [
      { "hooks": [{ "type": "command", "async": true,
        "command": "/ABSOLUTE/PATH/integrations/claude-code/ditoo-state.sh error" }] }
    ],
    "SessionEnd": [
      { "hooks": [{ "type": "command", "async": true,
        "command": "/ABSOLUTE/PATH/integrations/claude-code/ditoo-state.sh off" }] }
    ]
  }
}
```

Merge these into your existing settings rather than replacing the file. Run
`/hooks` in Claude Code afterwards to confirm they loaded.

## Configuration

All optional, set as environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `DITOO_BIN` | PATH, then `target/release`, then `target/debug` | controller binary |
| `DITOO_DEVICE` | auto-detect | MAC address, when several Ditoos are paired |
| `DITOO_FACES_DIR` | `faces/` next to the script | where the GIF/PNG faces live |
| `DITOO_RUNDIR` | `~/.claude/ditoo` | state files and log |
| `DITOO_OFF_CLOCK_ID` | unset | make `off` restore this clock face instead of blanking |
| `DITOO_SESSION` | from the hook payload | name this caller's slot in the merge; used by `ditoo-watch.sh` |
| `DITOO_RUST_LOG` | `warn` | controller log level; set `debug` to diagnose device problems |
| `DITOO_LOG_MAX_LINES` | `500` | log is trimmed to 200 lines once it exceeds this |
| `DITOO_ALERT_ESCALATE_SECS` | `60` | how long a blocked alert runs before it escalates |
| `DITOO_ALERT_PANIC_SECS` | `300` | how long before it escalates again, to the strobe |
| `DITOO_TRANSIENT_SECS` | `6` | how long `success` and `error` show before decaying to idle |
| `DITOO_CELEBRATE_AFTER_SECS` | `600` | how much work a finish needs before it earns the celebration |

The four timings above are read by the daemon at startup, so change them and
restart it. Short values are also the practical way to watch the escalation
path without waiting five real minutes:

```bash
DITOO_ALERT_ESCALATE_SECS=5 DITOO_ALERT_PANIC_SECS=10 ./integrations/claude-code/ditoo-state.sh start
```

## How states are presented over time

The hooks report what happened; the daemon decides how to show it. Three rules
do the work, and they are why the display is worth glancing at rather than just
being decorative:

- **Alerts escalate.** `alerting` gets more insistent the longer you leave it --
  after a minute, then again after five. Quiet enough to ignore briefly,
  impossible to ignore eventually.
- **Verdicts decay.** `success` and `error` are events, not conditions. They
  play, then the display returns to idle rather than sitting on a stale verdict.
- **Celebrations are earned.** A turn that finishes in seconds goes quietly
  idle; only a long stretch of work gets the celebration. Otherwise it stops
  meaning anything.

Escalation and decay happen with the state file sitting completely still, so
the daemon re-evaluates every tick rather than only when a hook fires.
| `DITOO_START_STATE` | `chilling` | state the daemon shows on startup |

## Custom faces

Drop your own 16x16 animated GIF into `faces/` named after the state
(`thinking.gif`, `working.gif`, `compacting.gif`, `alerting.gif`, `success.gif`,
`error.gif`, or `chilling.gif`). A same-named `.png` is used as a single-frame
fallback if no GIF exists. `alerting2` and `alerting3` are the automatic
one-minute and five-minute escalations used by the daemon.

To edit the bundled ones, change the Clauddy scenes in
[`faces/generate_faces.py`](faces/generate_faces.py) and re-run it. The same file
contains reusable drawing primitives for Clauddy, the blueprint, compressed
material bundle, workbench, hammer, exclamation and tiny workshop:

```bash
python3 faces/generate_faces.py --preview
```

The script validates every frame, prints an ASCII preview of each first frame,
and, with `--preview`, writes 320x320 `*_preview.gif` and `*_preview.png` files
you can inspect without squinting.

Two things worth knowing before you retime anything. Lock two motions to the
same period and the loop flattens into a single repeat, so fire, stars, feet,
props and sparks deliberately run on different beats. And every jump uses a
short launch plus a held apex; evenly spaced positions look like teleportation
at this scale.

The faces are drawn from scratch directly on the 16x16 grid. The generator uses
the shared low-level pixel helpers in [`faces/mascot.py`](faces/mascot.py), while
its own flat Clauddy rig keeps the body, eyes, arms and four feet consistent.

Only stdlib is used -- [`faces/gifwriter.py`](faces/gifwriter.py) is a small
GIF89a encoder written for this purpose, so there are no pip installs. If you
touch its LZW code, note the comment about code-width timing: the widening rule
has to lag by one code or real decoders reject the output.

## How it works

Claude Code hooks block the session while they run, and `PreToolUse` fires on
*every* tool call, so the script is built to return in milliseconds:

1. It writes the desired state to a file and returns. **If the daemon is
   running that is the whole story** -- the daemon is watching that file and
   picks the change up on its held connection.
2. Otherwise, if the desired state is already applied (the common case --
   Claude running tool after tool while already "working"), it exits
   immediately without forking anything.
3. Otherwise it takes a lock and hands off to a detached worker, which does the
   ~3 second connect-send-disconnect in the background.
4. State changes coalesce: the worker re-reads the desired state after each
   write, so a burst of hook calls collapses into one or two device writes and
   the newest state always wins.

A pid file next to the state file is the daemon's single-instance guard. If the
daemon is killed, the next hook call notices the pid is gone, clears the file
and falls back to one-shot sends rather than silently doing nothing.

Measured cost to the hook itself: about 40ms.

Every path exits 0. A missing binary, a powered-off device, or a Bluetooth
failure is logged to `$DITOO_RUNDIR/log` and never disrupts Claude Code.

## Limitations

- **The device cannot be a speaker while the daemon runs.** Opening the control
  channel requires dropping the audio link, so the daemon holds the device to
  itself. Run `stop` to hand it back.
- **Several sessions share one panel sensibly.** Each Claude Code session
  writes its own state file under `sessions/`, and the daemon shows the
  highest-priority live one: `alerting` > `error` > `compacting` > `working` >
  `thinking` > `success` > `chilling`. So a session blocked on you wins over
  any amount of busy work elsewhere, which is the question the display exists
  to answer. A session that dies stops counting after 15 minutes rather than
  pinning the panel to work nobody is doing.
- **~3 second lag without the daemon**, because each change connects afresh.
  With the daemon a change lands in well under a second -- every encoded face
  is under about 1.3 KB, so the transfer was never the bottleneck, the
  connection was.
- **`SessionEnd` blanks the display but leaves the daemon alive** so another
  Claude Code window can reuse the connection. Run `ditoo-state.sh stop` when
  you are done with the device entirely.

Still open: merging states across concurrent sessions, and animations that
respond to what Claude is actually doing rather than looping a fixed clip. See
the ideas in [TODO.md](../../TODO.md).
