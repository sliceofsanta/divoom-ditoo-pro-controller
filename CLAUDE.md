# CLAUDE.md

Context for AI agents working in this repository.

## What this is

`divoom-ditoo-pro-controller` is a Rust CLI that drives a **Divoom Ditoo Pro**
(a Bluetooth speaker with a 16x16 RGB LED display) over **Bluetooth SPP/RFCOMM**.

The vendor app is proprietary; this project is a clean-room-ish reimplementation
built from partial vendor docs (<https://docin.divoom-gz.com/web/#/5/146>),
third-party protocol notes, and packet observation. **Assume any protocol detail
not covered by a test is a best-effort guess.**

Upstream: <https://github.com/andreas-mausch/divoom-ditoo-pro-controller> (branch `rust`).
This fork's remotes: `origin` = `sliceofsanta/...`, `upstream` = `futpib/...`.
The default branch is `rust`, not `main`/`master`.

## Platforms

Two transports live in `src/transport/`, selected by `#[cfg(target_os)]`:

- **Linux** (`bluer_transport.rs`): BlueZ/D-Bus via `bluer`. The original and
  most complete platform; `scan` works here and CI runs the full feature set.
- **macOS** (`iobluetooth.rs`): native IOBluetooth RFCOMM, added 2026-08-24 and
  verified against real hardware. `scan` is not implemented (pair in System
  Settings, then `devices`); everything else works.

Windows does not build (no transport).

### macOS specifics (all of these are load-bearing)

- **IOBluetooth RFCOMM only works from the process main thread.** The same
  sequence fails instantly with `kIOReturnError` from any worker thread —
  verified experimentally, see `examples/mac_probe.rs`. Hence the inverted
  architecture in `main.rs`: on macOS, `main()` calls `macos_bluetooth_host()`,
  which serves Bluetooth on the main thread while the async CLI body runs on a
  tokio runtime on a second thread. Library consumers on macOS must do the same.
- **The Ditoo's SPP is an unnamed SDP record on RFCOMM channel 2.** macOS's
  cached service list (`HFP AVRCP A2DP ACL`) never shows it. The transport
  probes channels `[2, 1, 4, 3, 5, 6]` (other Divoom models use 1 and 4).
- **An active audio link blocks RFCOMM opens**, so the transport closes the
  connection first (`closeConnection`) and lets the RFCOMM open re-establish
  baseband. Side effect: sending a command interrupts Bluetooth audio playback.
- **TCC**: the binary embeds `NSBluetoothAlwaysUsageDescription` via a
  `__TEXT,__info_plist` linker section (`build.rs` + `macos/Info.plist`) —
  without it TCC SIGABRTs the process. Additionally the *responsible app*
  (Terminal, IDE) needs a Bluetooth grant in System Settings > Privacy &
  Security > Bluetooth.
- **The `/dev/cu.DitooPro-Audio` serial node is a trap.** It works for exactly
  one session per pairing, then dies permanently (macOS never re-establishes
  RFCOMM through it). Do not build on it.
- `examples/mac_probe.rs` is a self-contained diagnostic that connects and reads
  the volume on the main thread — useful when the transport misbehaves.

### Protocol facts confirmed against real hardware

- The framing and checksum in `protocol/packet.rs` are correct
  (`GetVolume`: tx `01 03 00 09 0c 00 02` -> rx `01 06 00 04 09 55 00 68 00 02`).
- The device sends unsolicited responses, sometimes concatenated with real
  replies — an undocumented spontaneous message with echoed command `0xF7` was
  observed repeatedly. This is why responses are matched by echoed opcode and
  why the macOS transport parses frames out of a byte stream.

## Build, test, lint

```bash
cargo build
cargo test --all
cargo check --no-default-features        # must also pass; CI enforces it
cargo clippy --all-targets --all-features -- --deny warnings
cargo +nightly fmt                       # nightly required: trailing_comma is unstable
```

CI (`.github/workflows/ci.yaml`) runs, in order: clippy (deny warnings),
`cargo check`, `cargo check --no-default-features`, release build with
`--all-features`, `cargo test --all`.

### Feature flags

| Feature | Default | Pulls in | Guards |
|---|---|---|---|
| `text` | yes | `fontdue`, `fontconfig`, `bdf-parser` | `scrolling-text` / `static-text` commands, `protocol::scrolling_text`, `protocol::static_text` |
| `video` | yes | `libmpv2-sys` | `video` command, `protocol::video` |
| `all-image-formats` | yes | `image/default` | extra image codecs |

`text` and `video` need C libraries present (`fontconfig`, `libmpv`). Anything
touching those modules must be behind `#[cfg(feature = "...")]` — including the
`use` statements in `src/main.rs` and `src/lib.rs`, which is why those files have
so many `#[cfg]`-gated imports.

## Layout

```
src/main.rs                     clap CLI: arg parsing, font/color resolution, device resolution
src/lib.rs                      public async API (send_* fns) + DeviceConnection (RFCOMM transport)
src/protocol/                   wire protocol: framing, opcodes, per-command payload encoders
src/protocol/packet.rs          Packet::serialize + Response::deserialize (+ unit tests)
src/protocol/command.rs         Command enum -> opcode byte
src/protocol/extended_command.rs 0xBD sub-command wrapper, language table
src/protocol/scrolling_text.rs  font rasterization -> 16-px columns -> scroll frames (+ unit tests)
src/protocol/static_text.rs     same rasterizer, single centered frame
src/protocol/video.rs           unsafe libmpv FFI: 16x16 software renderer
src/transport/mod.rs            transport selection + shared response filtering
src/transport/bluer_transport.rs Linux transport: BlueZ SDP profile + RFCOMM
src/transport/iobluetooth.rs    macOS transport: IOBluetooth host loop (see above)
src/address.rs                  macOS-only Address type (Linux re-exports bluer's)
build.rs                        embeds macos/Info.plist into the binary (TCC)
examples/mac_probe.rs           macOS diagnostic: main-thread connect + GetVolume
src/divoom_file_format/         the `.divoom16` container: Animation / Frame / FrameHeader
tests/convert.rs                integration tests for divoom16 <-> GIF conversion
images/                         sample art; witch.divoom16/witch.gif are test fixtures
```

Detailed docs live in `docs/`:

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — module map, data flow, connection lifecycle
- [docs/PROTOCOL.md](docs/PROTOCOL.md) — wire framing, opcode table, per-command payloads
- [docs/FILE_FORMAT.md](docs/FILE_FORMAT.md) — the `.divoom16` binary format

## Conventions

- **Formatting**: `rustfmt.toml` sets `tab_spaces = 2`, `trailing_comma = "Never"`.
  Note that `protocol/scrolling_text.rs`, `protocol/static_text.rs` and
  `protocol/video.rs` are currently 4-space and unformatted — running
  `cargo +nightly fmt` will reindent them, which makes a noisy diff. Match the
  surrounding file's existing style when editing rather than reformatting.
- **Error handling**: everything returns `Result<_, Box<dyn Error>>`. Clippy is
  configured with `panic`, `expect_used` and `unwrap_used` set to `warn`, and CI
  denies warnings — so **no `unwrap()`/`expect()`/`panic!` in `src/`**. Use `?`,
  `.ok_or("message")?`, or `.map_err(...)`. Test code is exempt in practice
  (`--all-targets` does lint tests, but existing tests use `unwrap` in
  `packet.rs`; keep new test code consistent with what's already there).
- **Async**: `tokio` multi-thread runtime. The only blocking thread is the mpv
  render loop in `send_video`, which is a `std::thread` bridged by an mpsc channel.
- **Logging**: `log` + `env_logger`, default filter `debug`. User-facing values
  that a script would consume (volume, clock id) go to `println!`; everything
  else goes through `info!`/`debug!`.

## Gotchas

- **One connection per command.** Every `send_*` in `lib.rs` calls
  `DeviceConnection::connect(...)` and `disconnect()` itself. There is no
  connection reuse across commands, and connecting is slow (SDP profile
  registration + up to 3 attempts with 1s backoff). If you add a command that
  needs several round-trips, do them inside a single `send_*`.
  `run_status_daemon` is the exception and the pattern to copy: it connects
  once and holds the connection for its lifetime. That matters beyond speed --
  the device plays its Bluetooth chime on every connect and disconnect, at a
  fixed volume that `volume set 0` does not silence, so reconnecting per
  command is audibly bad.
- **`alarm on` / `alarm off` does not work.** `main.rs` parses and logs the
  `enable` flag but never passes it: `send_alarm()` in `lib.rs` hardcodes
  `enable: false` and a 13:37 time. The README/TODO claim this feature works.
  Fixing it means threading `enable` (and ideally a time) through `send_alarm`.
- **`ControlWord::TerminateSending` is never sent.** `create_network_packets_from`
  emits `StartSeeding` + N `SendingData` chunks and stops. The device appears to
  accept this, but it deviates from the vendor docs.
- **`offset_id` is a chunk index, not a byte offset.** In
  `create_network_packets_from` it is `chunks(256).enumerate()` index. If a
  transfer bug shows up, this is the first thing to re-check against the docs.
- **Image/animation sends are fire-and-forget.** Only `GetVolume` and
  `GetUserDefineTime` use `send_and_receive`; everything else writes and sleeps
  40ms (`INTER_PACKET_DELAY`) without checking the ACK. A failed command is
  silent.
- **`color_count` is a `u8`, so 256 colors wraps to 0.** The reader disambiguates
  via `color_count == 0 && !reuse_palette => 256`. Don't "simplify" that branch.
- **Palette lookup is O(n) per pixel** (`palette.iter().position(...)` in
  `Frame::build_pixel_data`) and runs per frame. It is a real hot spot for video
  and long scrolling text.
- **Bluetooth adapter is not configurable** — `session.default_adapter()` always.
- **`protocol/video.rs` is `unsafe` FFI throughout.** It hand-manages an
  `Arc::into_raw` pointer passed to an mpv C callback and reclaims it in `Drop`
  and on every early-return error path. Changing the construction order there
  can leak or double-free; read the whole `new()` before touching it.

## Where to add things

- New device command → add opcode to `protocol/command.rs`, payload encoder to a
  new `protocol/<name>.rs` (or reuse `extended_command::build_packet` for 0xBD
  sub-commands), a `send_<name>` in `lib.rs`, and a `Command` variant in `main.rs`.
- New unimplemented-feature ideas are tracked in [TODO.md](TODO.md).
