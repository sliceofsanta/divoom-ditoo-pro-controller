# Claude Code status display

Turn a Divoom Ditoo Pro into a tiny **Pac-Man progress board** for
[Claude Code](https://claude.com/claude-code). Every state keeps the complete
16x16 neon maze visible: Pac-Man and the ghosts remain tiny pieces moving inside
the grid instead of becoming zoomed-in character portraits.

| State | When | Animation |
|---|---|---|
| `thinking` | you submit a prompt | **READY:** Pac-Man stays still at a fork while the two routes pulse |
| `working` | Claude runs a tool | **CHOMP RUN:** traverses the grid continuously, clearing pellets behind him |
| `compacting` | Claude compacts context | **BOARD CLEANUP:** clears a shrinking pellet ring into one power pellet |
| `alerting` | Claude needs your input | **HEY:** one ghost approaches, power pellet and exclamation pulse slowly |
| `alerting2` | still waiting after 1 minute | **STILL WAITING:** two ghosts close in while the maze flashes faster |
| `alerting3` | still waiting after 5 minutes | **CORNERED:** four ghosts surround Pac-Man under a full-maze strobe |
| `success` | Claude finished responding | **BOARD CLEAR:** frightened ghosts flee under a cherry bonus shower |
| `error` | a tool or the turn failed | **CAUGHT:** ghost collision followed by Pac-Man's death burst |
| `chilling` | a session starts, or manual | **ATTRACT MODE:** untouched pellet grid, sleeping Pac-Man, ghosts resting at home |
| `off` | the session ends, or manual | blank display |

The board uses one-pixel blue maze walls, cream pellets, large power pellets and
three-wide characters. State meaning comes from board state and choreography:
stationary versus clearing, one ghost versus four, full pellets versus an empty
board, normal ghosts versus frightened blue ghosts, and calm blue walls versus
red/white escalation flashes.

The point is still the `alerting` state: you can look away from the terminal and
notice the moment Claude is blocked on you. The other poses turn the display
from a status light into a tiny desk companion.

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

To edit the bundled ones, change the board scenes in
[`faces/generate_faces.py`](faces/generate_faces.py) and re-run it. The same file
contains the reusable `pac_maze()`, `pacman()`, `ghost()`, `pac_pellets()`,
`power_pellet()` and `cherry()` drawing primitives:

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

The older Claude and Mario drawing experiments remain as reusable legacy
helpers, but none of these nine animations uses them. The Pac-Man grid and
characters are drawn from scratch rather than copied from an arcade ROM.

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
