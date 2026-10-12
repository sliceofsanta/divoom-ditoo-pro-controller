# Claude Code status display

Turn a Divoom Ditoo Pro into **Clawd**, the orange, four-footed desk companion
for [Claude Code](https://claude.com/claude-code). Thirty-two animated scenes cover
work, input requests, presence and idle play. Every frame is drawn directly on
the 16x16 grid: one large flat terracotta body, black eyes and a readable prop.

| State | When | Animation |
|---|---|---|
| `thinking` | you submit a prompt | **THINKING:** still code, resting paws and a blinking laptop cursor |
| `working` | Claude runs a tool | **CODING:** cyan code scrolls in typing bursts; pauses, blinks and a tiny sweat break |
| `compacting` | Claude compacts context | **TIDYING UP:** squeeze loose pages into a bound bundle |
| `alerting` | Claude needs your input | **HEY:** amber laptop cursor pulses; Clawd stops typing, looks at you and waves |
| `alerting2` | still waiting after 1 minute | **STILL WAITING:** faster waves, amber side marks and pulsing cursor |
| `alerting3` | still waiting after 5 minutes | **NEED YOU:** two hands up and persistent red warning rails; no strobing |
| `success` / `done` | a turn ends | **NAILED IT:** green laptop check; celebration after 10+ minutes, otherwise a quiet check |
| `error` | a tool or the turn failed | **OOPS:** red laptop cross and sad eyes; six-second loop |
| `chilling` | idle, session start or manual | **DESK NAP:** dim laptop, dozing Clawd and an occasional cursor |
| `off` | the session ends, or manual | blank display |

Alerts share the amber laptop cursor and add a small reason cue above Clawd:

| State | When | Animation |
|---|---|---|
| `alert-permission` | a permission prompt | closed gold padlock cue and a patient wave |
| `alert-question` | a question | amber question cue and a patient wave |
| `alert-plan` | a plan to review | purple document cue and a patient wave |

Anything unrecognised stays plain `alerting` rather than guessing wrong. All
three outrank ordinary work and all three fall back onto the same escalation
ladder once ignored, because after five minutes *why* it wants you stops being
the useful part.

Two more face outward, at whoever is deciding whether to walk over, and only
ever appear when the panel would otherwise be idle:

| State | When | Animation |
|---|---|---|
| `meeting` | you are in one right now | Clawd in a headset, with a microphone and cyan voice bars |
| `busy` | macOS Focus is on | headphones and a steady red do-not-disturb placard |

## Top-row activity strip

Clawd shows **what** is happening; the top row shows activity and attention.
The bottom row remains the optional context-usage gauge.

| Situation | Top row |
|---|---|
| Solo work | a cyan pixel travels back and forth; activity, not percent complete |
| Parallel agents / sessions | fixed dots: pulsing cyan = running, green = finished, amber = waiting, red = failed |
| Needs input | amber edge lights expand and pulse faster at the existing 60s / 5min thresholds |
| Tool failure | steady red until a successful tool result or a new prompt; failed finished agents retain red for the turn |
| Solo turn finished | a green sweep while the completion animation is shown |
| Idle / screensaver / presence | no strip |

The roster has seven fixed individual positions (including the main agent),
plus a double-width overflow indicator at the right. Overflow shows the most
urgent remaining status, not a made-up completion percentage. During parallel
work, waiting dots pulse faster as alerts escalate, without moving other dots.
Finished means an agent stopped, not that its work was independently verified.
Live positions persist while agents join and finish. When all seven positions
are occupied, new workers can reuse completed workers' positions; live workers
never move to make room. A new prompt clears finished
agents but retains running background agents. Ended/stale sessions disappear;
the observer's existing 15-minute stale cutoff also applies to the roster.
The observer writes atomic `agent-strip` snapshots; the daemon composes the row
into existing GIF frames, avoiding a stream of extra Bluetooth writes.

## Key lights

The Ditoo's own key backlight follows the face:

| Face | Keys |
|---|---|
| thinking, reading, reviewing, planning | lit on your chosen effect |
| working, writing, terminal, responding | alternate effects every 2.4s |
| searching, connecting | alternate every 1.8s |
| testing, building, installing | alternate every 1s |
| compacting, delegating | alternate every 1.2s |
| any alert | alternate between your effect and the next one, every 1.5s |
| still waiting / alarm | faster, 0.8s then 0.4s |
| success, done, taskdone, starting, configuring | one quick ripple, then lit |
| error, cancelled | two blinks, then lit |
| idle, screensaver, meeting, Focus | dark |

The implemented protocol supports "next effect", "previous effect" and "toggle", and
answers none of them, so it can't be asked what it is showing. Two consequences:

- Your chosen effect is never lost. Alerts only ever step one effect away and
  back, so ending an alert returns exactly to yours.
- On/off is a belief the daemon keeps in `~/.claude/ditoo/keyboard-state`. If you
  change the keys on the device itself, tell it what you see.

```bash
./integrations/claude-code/ditoo-state.sh keyboard resync on   # or off
./integrations/claude-code/ditoo-state.sh keyboard next        # change your effect
./integrations/claude-code/ditoo-state.sh keyboard disable     # stop following faces
./integrations/claude-code/ditoo-state.sh keyboard enable
```

Manual commands go through the daemon's held connection, so no chime.
Commands use an atomic spool, so concurrent command requests cannot vanish during
queue rotation. A failed relative light write marks the belief `uncertain` and
pauses automatic lighting until `keyboard resync on|off`: replaying an
unacknowledged toggle could invert an already-delivered command. Resync adopts
the effect you currently see as the new home. No exact RGB colours are promised.

### Physical key remapping

Not implemented or confirmed supported. Sending keyboard-light commands does
not provide physical key-press events. The controller currently has no decoded
button input or key-remapping command. Unknown unsolicited Bluetooth frames
must not be treated as key presses without a controlled press-by-press capture.
Until that is verified, the speaker's keys retain their built-in functions.

## Detailed Clawd activity

The file-only `ditoo_hook.py` observer handles 31 lifecycle events. It never
approves, denies, blocks, edits tool inputs, reads transcripts, or logs prompts,
command text, tool output or reply text. Tool/agent IDs and state names are the
only activity data retained. Definitions follow the
[official Claude Code hook reference](https://code.claude.com/docs/en/hooks).

| Scene | Observed activity |
|---|---|
| `starting` | session starts or resumes; hello wave |
| `reading` | Read, NotebookRead, task results, skills; open book |
| `searching` | Grep, Glob, WebSearch, ToolSearch; magnifying glass |
| `writing` | Write, Edit, MultiEdit, NotebookEdit; pencil |
| `terminal` | unclassified Bash/PowerShell commands; terminal prompt |
| `testing` | recognized test/lint/check commands; scanning test tray |
| `building` | recognized build/compile commands; stacking blocks |
| `installing` | recognized install/add/sync commands; delivery box |
| `reviewing` | git diff/show/log/status/blame; document inspection |
| `planning` | plan mode, task creation/update, command expansion; branches |
| `delegating` | steady team-working scene; the original Clawd + small laptop pose in a longer 24-second loop |
| `connecting` | WebFetch, MCP, network commands; two plugs |
| `responding` | MessageDisplay; speech bubble |
| `configuring` | setup, context instructions, config/directory/model changes |
| `taskdone` | a TaskCompleted milestone, not the whole turn finishing |
| `done` | a short completed turn; quiet check for 3s |
| `cancelled` | reported interruption or permission denial; pause bars |

Original permission/question/plan alerts, compaction, success, error, presence,
coffee break and screensaver remain. PostToolUse removes only that tool's ID;
other parallel tools and agents continue voting. Alerts outrank ordinary work.
Successful tool completion returns to thinking when no other tool is running;
it never falsely celebrates the whole turn. Short turns now show `done` before
idle; the full celebration is still reserved for ten-minute work stretches.

Coverage limits are intentional: hidden reasoning, arbitrary keystrokes and
tool validation rejected before hooks fire are not observable. Shell activity
is conservative token-based classification, not command execution or a claim
to understand every shell program. General MCP tools are `connecting`, not
guessed from their content. Fast events can coalesce at the daemon's 250ms poll
interval; the display follows current activity rather than replaying a backlog.
Decorative tests/blocks/dots are not measured completion counts.

`WorktreeCreate` is NOT installed because that hook replaces Git's worktree
creation. `FileChanged` needs a user-chosen watch list and is not installed as
a broad filesystem watcher. `TeammateIdle` is safely ignored so a different
teammate going idle cannot clear the current actor's work. Late MessageDisplay
batches cannot overwrite a completed Stop. No new hook auto-starts Bluetooth:
keep the LaunchAgent running, or start the daemon manually first.

Offline checks:

```bash
python3 -m unittest discover -s integrations/claude-code -p 'test_ditoo_hook.py'
cargo test --no-default-features --features all-image-formats
```

## Parallel agents

The display summarizes the **session**, rather than showing whichever agent
last ran a tool. Once a worker is observed, `delegating` becomes the steady
team-working scene until background work and the parent turn have finished.
The 24-second team-working loop uses the exact layout of `working`: large Clawd,
small laptop in the lower-right, cyan code strokes and visible typing paws.
Short typing pauses, blinks, a sideways glance and two tiny sweat moments vary
the loop without changing its composition. No neural-network symbols, escaped
cursors, extra monitors or miniature agents. Only the live top-row dots describe
individual workers; the typing is decorative, not measured tool progress.
The laptop's six-by-three-pixel screen types and scrolls in bursts. During the
two reading pauses its code freezes while the cursor keeps blinking. Thinking
and reviewing use still code; input requests use a slow amber brightness pulse;
failure uses a red cross; completion uses a persistent green check. Idle dims
the screen and only occasionally blinks a cursor. No fake percentages or results
appear in the working animation, and the laptop bezel stays fixed across states.
Individual reading/writing/testing events still update internal state, but do
not swap the team animation or its keyboard pattern. During solo work, detailed
scenes remain available with a two-second settling period and a four-second
minimum hold for ordinary changes.

| Session situation | Display policy |
|---|---|
| Any known worker running, or parent integrating results | steady team Clawd (`delegating`) |
| Parent replies but background work remains | keep team Clawd; no completion celebration |
| One tool fails while the team continues | red worker dot, same team scene |
| Permission/question/plan needs you | immediate alert; ordinary worker events cannot steal it |
| Main agent reports StopFailure | immediate error scene |
| Parent stopped and no known background work remains | require four quiet seconds before completion; unresolved errors prevent a success scene |

Ordinary dot/context changes are coalesced to at most one refresh every three
seconds so updates do not constantly restart the GIF. New waiting/error dots
and actual scene changes bypass that limit. Alerts keep their existing escalation.
Overlay refreshes resume at the estimated current animation frame instead of
restarting at frame zero. The complete loop and its frame delays are retained;
this is an estimate because the device does not report its playback position.

`Stop` is not synonymous with "all work finished". The observer uses the
documented `background_tasks` snapshots on Stop/SubagentStop, including shell
tasks, and `Agent` async-launch responses in addition to SubagentStart/Stop.
Only IDs and states are retained; task descriptions, commands and output are
discarded. Same-ID snapshots and actor events are deduplicated. Missing or
malformed snapshots do not erase known background work. A valid empty snapshot
clears snapshot-only work; known actor lifecycles still apply.
See [Claude's hook reference](https://code.claude.com/docs/en/hooks#stop-input).

Coverage remains observational: a background shell completion is reconciled at
the next supported snapshot, not inferred from text or screenshots. Events
missed before installation cannot be reconstructed reliably until a snapshot
or lifecycle event arrives. The existing 15-minute stale-session cutoff remains;
a completely silent worker is not independently polled. Scheduled future wakeups
are not counted as currently running work. No permissions or task execution are
changed by this presentation policy.

The identity-aware [activity strip](#top-row-activity-strip) replaces the old
bright/dim blue count. It follows `SubagentStart` / `SubagentStop` plus each
actor's tool and input events across live sessions. `TaskCreated` and
`TaskCompleted` are not used to count subagents. A new prompt clears only its
session's completed agents, preserving active background agents and other
windows. The observer still publishes legacy `fanout` counts for older daemons;
this daemon uses `agent-strip`, with a solo activity fallback when it is absent.

Clawd reacts through the existing hooks and state files. Submitting, running
tools, granting permission and finishing work select the corresponding face;
the art does not infer progress or automatically grant permission. The padlock
stays closed while blocked. Alerts grow in gesture and size on a steady dark
background. Success and error each last six seconds. The top and bottom pixel
rows remain clear for agent pips and the optional context gauge.

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

The bundled screensaver is **Clawd and the runaway cursor**, a 19.2-second
silent comedy: follow a wandering pointer, get booped, sneeze pixels, make a
heart, drink coffee and fall asleep. The cursor comes back for another round;
the last frame matches the first for a continuous loop.

Regenerate it with `python3 faces/make_screensaver.py`; the earlier Santa and
embers versions remain available with `--theme santa` and `--theme embers`.
Replace it like any other face.
Only idle ages into it -- a state that is telling you something is never
interrupted.

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

**4. Install the detailed hooks** with the merge-safe installer (Python 3.9+).
The full event set targets current Claude Code, verified here with 2.1.291.
Keep the daemon running via the LaunchAgent or start it manually first.

```bash
python3 integrations/claude-code/install-hooks.py                 # dry run
python3 integrations/claude-code/install-hooks.py --apply         # backup + merge
```

For a LaunchAgent installation, first rebuild and update the installed files,
then point the hooks at its stable, non-Documents path:

```bash
cargo build --release --no-default-features --features all-image-formats
./integrations/claude-code/install-launchagent.sh
python3 integrations/claude-code/install-hooks.py --apply \
  --hook-path "$HOME/Library/Application Support/ditoo/ditoo_hook.py"
```

The installer replaces only Ditoo hook handlers, preserving unrelated hooks and
every other setting. It creates a timestamped settings backup and is idempotent.
Restart Claude Code and check `/hooks`; already-open sessions may retain their
previous hooks. Check for older Ditoo handlers in project-level settings too:
Claude merges hooks across levels. Do not install both old and new Ditoo handlers.

<details>
<summary>Legacy minimal hooks (older Claude versions; not the detailed router)</summary>

Use the absolute path to your checkout. This older `SessionStart` entry starts
the daemon, but every tool has the same working face:

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

</details>

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
- **Celebrations are earned.** A short turn gets a quiet three-second `done`
  check before idle; only a long stretch of work gets the full celebration.

Escalation and decay happen with the state file sitting completely still, so
the daemon re-evaluates every tick rather than only when a hook fires.
| `DITOO_START_STATE` | `chilling` | state the daemon shows on startup |

## Custom faces

Drop your own 16x16 animated GIF into `faces/` named after the state
(`thinking.gif`, `working.gif`, `compacting.gif`, `alerting.gif`, `success.gif`,
`error.gif`, or `chilling.gif`). A same-named `.png` is used as a single-frame
fallback if no GIF exists. `alerting2` and `alerting3` are the automatic
one-minute and five-minute escalations used by the daemon.

To edit the bundled ones, change the Clawd scenes in
[`faces/clawd_faces.py`](faces/clawd_faces.py), then run the exporter:

```bash
python3 faces/generate_faces.py --preview
```

The script validates every frame, prints an ASCII preview of each first frame,
and, with `--preview`, writes 320x320 `*_preview.gif` and `*_preview.png` files
you can inspect without squinting. The default Clawd export includes 33 files:
32 animated core/tool/lifecycle/presence/idle scenes and a blank off face. The
glyph-only exporter also defaults to the matching Clawd variants; pass
`--theme glyphs` to recover the earlier standalone symbols.

Two things worth knowing before you retime anything. Lock two motions to the
same period and the loop flattens into a single repeat, so fire, stars, feet,
props and sparks deliberately run on different beats. And every jump uses a
short launch plus a held apex; evenly spaced positions look like teleportation
at this scale.

The faces are drawn from scratch directly on the 16x16 grid. The generator uses
the shared low-level pixel helpers in [`faces/mascot.py`](faces/mascot.py), while
the Clawd drawing functions keep his proportions consistent. Earlier themes
remain available with `--theme santa` and `--theme clauddy`. The interactive
review simulates events locally; its boop control is a preview interaction,
not a new touch input on the speaker.

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
