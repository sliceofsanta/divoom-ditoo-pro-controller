# Claude Code status display

Turn a Divoom Ditoo Pro into a physical status light for
[Claude Code](https://claude.com/claude-code): the 16x16 display shows whether
Claude is working, waiting on you, or idle.

The character is **Clawd**, Claude Code's pixel crab.

| State | When | Animation |
|---|---|---|
| `working` | you submit a prompt, or Claude runs any tool | claws alternate on the keys, eyes down, bar sweeping |
| `alerting` | Claude needs your input (permission prompt, question) | both claws waving overhead, wide eyes, red pulse |
| `chilling` | Claude finished responding | napping -- eyes shut, breathing bob, a z drifting off |
| `off` | manual only | blank display |

Clawd keeps his Claude orange in every state so he reads as the same character;
the state is carried by the background wash, his pose, and the motion. At 16x16
colour is what you catch across a room and motion is what you catch at a
glance -- the silhouette only resolves up close.

The point is the `alerting` state: you can look away from the terminal and still
notice the moment Claude is blocked on you.

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
./integrations/claude-code/ditoo-state.sh working
./integrations/claude-code/ditoo-state.sh status
```

`status` prints the desired/applied state, whether a worker is running, which
binary it resolved, and the tail of the log -- start here when something looks
wrong.

**4. Add the hooks** to `~/.claude/settings.json`. Use the absolute path to your
checkout:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [{ "type": "command", "async": true,
        "command": "/ABSOLUTE/PATH/integrations/claude-code/ditoo-state.sh working" }] }
    ],
    "PreToolUse": [
      { "hooks": [{ "type": "command", "async": true,
        "command": "/ABSOLUTE/PATH/integrations/claude-code/ditoo-state.sh working" }] }
    ],
    "Notification": [
      { "hooks": [{ "type": "command", "async": true,
        "command": "/ABSOLUTE/PATH/integrations/claude-code/ditoo-state.sh alerting" }] }
    ],
    "Stop": [
      { "hooks": [{ "type": "command", "async": true,
        "command": "/ABSOLUTE/PATH/integrations/claude-code/ditoo-state.sh chilling" }] }
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
| `DITOO_FACES_DIR` | `faces/` next to the script | where the PNGs live |
| `DITOO_RUNDIR` | `~/.claude/ditoo` | state files and log |
| `DITOO_OFF_CLOCK_ID` | unset | make `off` restore this clock face instead of blanking |
| `DITOO_RUST_LOG` | `warn` | controller log level; set `debug` to diagnose device problems |
| `DITOO_LOG_MAX_LINES` | `500` | log is trimmed to 200 lines once it exceeds this |

## Custom faces

Drop your own 16x16 animated GIF into `faces/` named after the state
(`working.gif`, `alerting.gif`, `chilling.gif`). A same-named `.png` is used as a
single-frame fallback if no GIF exists.

To edit the bundled ones, change the frame definitions in
[`faces/generate_faces.py`](faces/generate_faces.py) and re-run it. The sprite
itself lives in [`faces/clawd.py`](faces/clawd.py), posed by five numbers --
`body_y` bobs him, `claw_l`/`claw_r` raise each claw, `eye` picks
open/down/closed/wide, `splay` widens his stance -- so no pose is drawn twice
by hand:

```bash
python3 faces/generate_faces.py --preview
```

The script prints an ASCII preview of each first frame and, with `--preview`,
writes 320x320 `*_preview.gif` files you can watch without squinting.

One animation trap worth knowing: give a pose cycle and a colour pulse the same
period and they alias into a single flip. The alerting claws see-saw over 3
positions against a 2-frame pulse for exactly that reason.

Only stdlib is used -- [`faces/gifwriter.py`](faces/gifwriter.py) is a small
GIF89a encoder written for this purpose, so there are no pip installs. If you
touch its LZW code, note the comment about code-width timing: the widening rule
has to lag by one code or real decoders reject the output.

## How it works

Claude Code hooks block the session while they run, and `PreToolUse` fires on
*every* tool call, so the script is built to return in milliseconds:

1. It writes the desired state to a file and returns. If the desired state is
   already applied (the common case -- Claude running tool after tool while
   already "working"), it exits immediately without forking anything.
2. Otherwise it takes a lock and hands off to a detached worker, which does the
   ~3 second Bluetooth round-trip in the background.
3. State changes coalesce: the worker re-reads the desired state after each
   write, so a burst of hook calls collapses into one or two device writes and
   the newest state always wins.

Measured cost to the hook itself: about 40ms.

Every path exits 0. A missing binary, a powered-off device, or a Bluetooth
failure is logged to `$DITOO_RUNDIR/log` and never disrupts Claude Code.

## Limitations

- **One display, one session.** Several concurrent Claude Code sessions all
  drive the same device and will fight over it -- last writer wins. Merging
  states across sessions needs the daemon described below.
- **~3 second lag** before a state change reaches the display, because every
  command opens a fresh Bluetooth connection. Not noticeable for `alerting`
  (you were away anyway), noticeable if you watch for it. Each face is only
  500-660 bytes on the wire, so the transfer itself is not the bottleneck --
  the connection setup is.
- **Audio interruption on macOS.** Opening the control channel requires dropping
  the audio link, so each state change briefly interrupts Bluetooth music
  playing on the speaker. If you use the Ditoo as a speaker while coding, you
  probably want the hooks off.
- **No `SessionEnd` hook is wired** by default, so the last state stays on the
  display after you quit. Add one calling `off` if you would rather it blank.

A long-running daemon holding a single connection would fix the lag, the audio
interruption, and multi-session merging, and would let animations respond to
what Claude is actually doing rather than looping a fixed clip. That is the
natural next step; see the ideas in [TODO.md](../../TODO.md).
