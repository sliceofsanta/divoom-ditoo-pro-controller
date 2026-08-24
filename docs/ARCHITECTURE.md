# Architecture

How the crate is put together and how data flows from a CLI invocation to pixels
on the device.

## Big picture

```
                        src/main.rs  (bin)
                     clap parsing, colors,
                    font lookup, MAC resolve
                              │
                              ▼
                        src/lib.rs  (lib)
        ┌─────────────────────┴──────────────────────┐
        │  send_image / send_video / send_brightness │
        │  send_scrolling_text / … (one per command) │
        └─────────────────────┬──────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
   src/divoom_file_format/            src/protocol/
   pixels ⇄ .divoom16 bytes           bytes ⇄ SPP packets
              │                               │
              └───────────────┬───────────────┘
                              ▼
                      DeviceConnection
                  (bluer RFCOMM, in lib.rs)
                              │
                              ▼
                     Ditoo Pro over SPP
```

Two independent halves meet in `lib.rs`:

- **`divoom_file_format`** knows about *pixels*: decoding/encoding the device's
  `.divoom16` container, converting to and from GIF/PNG/etc. It has no knowledge
  of Bluetooth. See [FILE_FORMAT.md](FILE_FORMAT.md).
- **`protocol`** knows about *bytes on the wire*: SPP framing, opcodes, per-command
  payload layouts. It has no knowledge of Bluetooth transport either. See
  [PROTOCOL.md](PROTOCOL.md).

`lib.rs` is the only place that touches `bluer`.

## `src/main.rs` — the CLI

Pure orchestration; contains no protocol logic. Responsibilities:

1. **Arg parsing** via `clap` derive. Top-level `Args` has an optional
   `--device` plus a `Command` subcommand enum. Subcommands with modes
   (`volume`, `clock`, `convert`, `mode`, `keyboard-backlight`) nest their own
   subcommand enums.
2. **Device resolution** (`resolve_device`): if `--device` is given, parse it as a
   MAC; otherwise call `find_paired_ditoo_pro_devices()` and auto-select when
   exactly one paired device whose name contains `DitooPro` exists. Zero or many
   is an error telling the user to pass `--device`.
3. **Color parsing** (`parse_color`): any CSS color syntax via `csscolorparser`
   (`red`, `#FF0000`, `rgb(255,0,0)`), reduced to `[u8; 3]`.
4. **Font resolution** (`resolve_font`, `text` feature only): a `--font` value is
   first tried as a filesystem path, then looked up through `fontconfig`. With no
   `--font`, it shells out to `fc-match monospace:scalable=false` to prefer a
   *bitmap* monospace font (bitmap fonts look far better at 16px than hinted-down
   TTFs), falling back to fontconfig's `monospace`.
5. **Dispatch** to the matching `send_*` in `lib.rs`. The `convert` and
   `debug-image` subcommands never touch Bluetooth — they go straight to
   `divoom_file_format`.

The three offline subcommands are `convert to-gif`, `convert to-divoom16` and
`debug-image`; everything else resolves a device first.

## `src/lib.rs` — public API and transport

### The `send_*` functions

The crate's public surface is a flat set of `async fn send_*(mac_address, …)`.
Each one is self-contained: connect, send, disconnect. They fall into four shapes.

| Shape | Examples | Behaviour |
|---|---|---|
| Single fire-and-forget packet | `send_set_brightness`, `send_set_volume`, `send_set_datetime`, `send_set_play_status`, `send_set_box_mode`, `send_keyboard_backlight`, `send_set_language`, `send_set_clock_face`, `send_alarm` | build one `Packet`, write, sleep 40ms, disconnect |
| Request/response | `send_get_volume`, `send_get_clock_face` | `send_and_receive`, match the echoed opcode, parse `response.data` |
| Bulk file transfer | `send_image`, `send_static_text`, `send_divoom_animation` | encode to `.divoom16`, split into 256-byte chunks, send as `0x8B` packets |
| Frame streaming | `send_scrolling_text`, `send_video` | `0x6E` start, then a stream of `0x6C` frames, then `0x6E` stop |

### `DeviceConnection` and `src/transport/`

The RFCOMM transport, one implementation per platform selected by
`#[cfg(target_os)]` in `src/transport/mod.rs`; both expose the same interface
(`connect` / `send_and_receive` / `fire_and_forget` / `disconnect`), and the
response-matching loop (`await_response`, which skips unsolicited frames like
the undocumented `0xF7` messages) is shared between them.

**macOS (`transport/iobluetooth.rs`)** talks IOBluetooth RFCOMM directly.
IOBluetooth only works from the process main thread, so on macOS the usual
layering is inverted: `main()` calls `macos_bluetooth_host()`, which keeps the
main thread as a Bluetooth service loop (pumping an `NSRunLoop`, probing RFCOMM
channels `[2, 1, 4, 3, 5, 6]`, dropping the audio link before opening) while
the async CLI body runs on a tokio runtime on a second thread, bridged by
channels. Incoming bytes are reassembled into frames by scanning for the
`0x01 … len … 0x02` structure, because the device concatenates unsolicited
messages with real replies. See the "macOS specifics" section of CLAUDE.md for
the constraints this design is built around.

**Linux (`transport/bluer_transport.rs`)**: connecting is more involved than a
plain socket because `bluer` exposes SPP through the BlueZ **profile** API
rather than a connectable channel number:

1. Open a `bluer::Session`, take `default_adapter()`, power it on.
2. Register an RFCOMM `Profile` for the SPP UUID
   `00001101-0000-1000-8000-00805f9b34fb`, as `Role::Client`, with
   authentication/authorization disabled and `auto_connect`.
3. `device.connect()` if not already connected, then `device.connect_profile(spp_uuid)`.
   A failure here is logged at debug and *not* treated as fatal — the profile
   handle may still deliver a connection.
4. Loop on `profile_handle.next()` until a request arrives from the target MAC,
   then `accept()` it to get the stream.

`try_connect` is wrapped by `connect`, which retries up to
`MAX_CONNECT_ATTEMPTS` (3) with a 1s sleep between attempts.

Once connected the stream is split. The read half moves into a **background
tokio task** that loops on `read_response` and pushes each decoded `Response`
into an unbounded mpsc channel. This matters because the device emits
*unsolicited* responses; a synchronous read-after-write would desynchronize.

- `fire_and_forget(packet)` — write, sleep `INTER_PACKET_DELAY` (40ms). No ACK check.
- `send_and_receive(packet)` — write, sleep, then drain the channel until a
  response whose `original_command` matches is found (unmatched ones are logged
  and dropped), with a 5s overall deadline. A NAK becomes an `Err`.
- `disconnect()` — abort the reader task and shut down the writer.

The struct holds `_session` and `_profile_handle` purely to keep them alive; the
connection dies with them.

### `read_response` framing

Reads the 1-byte start marker (must be `0x01`), then the 2-byte little-endian
length, then `length + 1` more bytes (payload + 2-byte checksum + end marker).
The reassembled frame is handed to `Response::deserialize`, which validates
markers, length, response-type byte and checksum. See [PROTOCOL.md](PROTOCOL.md).

## `src/protocol/` — wire format

- **`packet.rs`** — `Packet::serialize()` (framing + checksum) and
  `Response::deserialize()` (validation + ACK/NAK + data extraction). This is the
  best-tested module in the crate; its unit tests cover ACK, NAK, data payloads,
  bad checksum, short frames, and bad start/end bytes.
- **`command.rs`** — the `Command` enum and its `value() -> u8` opcode mapping.
  Adding a device command starts here.
- **`extended_command.rs`** — opcode `0xBD` is a namespace: the first payload byte
  selects a sub-command. `build_packet(ext_type, params)` wraps that, and the
  module holds the known sub-command constants plus the 16-entry language table.
- **`alarm.rs`, `datetime.rs`, `animation.rs`, `keyboard_backlight.rs`** — payload
  structs with a `serialize()`. Each carries a comment pointing at the vendor doc
  or third-party source it was derived from.
- **`scrolling_text.rs`, `static_text.rs`** (`text` feature) — the text renderer.
- **`video.rs`** (`video` feature) — the mpv FFI renderer.

## Text rendering pipeline

`scrolling_text.rs` owns the rasterizer; `static_text.rs` reuses it for a single
frame. The core representation is a **column-major bitmap**: a `Vec<u16>` where
each element is one screen column and bit *N* means row *N* is lit. 16 rows fit
exactly in a `u16`.

```
"Hi\nYo"
  │
  ├─ split on '\n' → line_height = 16 / num_lines
  │
  ├─ per line: rasterize_line_bdf()   (BDF bitmap fonts, via bdf-parser)
  │            rasterize_line_ttf()   (scalable fonts, via fontdue, alpha ≥ 128 → on)
  │            → Vec<u16> columns, one glyph after another at its advance width
  │
  ├─ layout_text(lines, line_height, halign, valign)
  │    → Vec<[u8; 2]>  ("wide bitmap": full text, arbitrarily wide, 16 rows tall)
  │      each line is OR'd in, shifted vertically by its row offset
  │
  ├─ render_frame(wide_bitmap, scroll_offset, fg, bg)
  │    → [[u8; 3]; 256]  one 16x16 RGB screen, windowing the wide bitmap
  │
  └─ scrolling: one frame per offset in -16..total_width
     static:    one frame at the centered offset
```

Font selection differs by extension: a `.bdf` path is parsed as a BDF bitmap
font, anything else goes through `fontdue`. Both rasterizers rescale the font's
ascent to `target_height` so glyphs stay inside the (possibly 8px or 5px) line
box instead of being pushed out of view — that repositioning is what the BDF
unit tests in `scrolling_text.rs` pin down.

Scrolling frames are then each encoded as a standalone `.divoom16` frame and
streamed with `0x6C`. Static text takes the other path: one image →
`Animation::from_image` → full `.divoom16` file → chunked `0x8B` transfer.

## Video pipeline

`send_video` runs two loops connected by a bounded (capacity 2) mpsc channel:

```
 std::thread                          tokio task (send_video)
 ───────────                          ───────────────────────
 VideoPlayer::new(path, mac, opts)
   mpv: vo=libmpv, sub=no, osd=0,
        vf=crop to square
   pick audio-device whose name
     contains the device MAC
        │
   loop:                                loop: select! {
     poll_events()  ── end? break         frame = rx.recv() →
     render_frame() → [u8; 768] ───►        encode_rgb_frame() → .divoom16 frame
       (16x16 sw render, rgb0→rgb)          send 0x6C packet
     sleep 5ms                            ctrl_c → break
                                        }
```

The bounded channel is deliberate: `try_send` **drops frames when full** so
playback stays real-time instead of drifting behind. Ctrl+C or end-of-file stops
the loop, signals the mpv thread through a oneshot, joins it, and sends the
`0x6E` stop packet.

Audio is routed to the Ditoo Pro itself: mpv's `audio-device-list` is scanned for
a sink whose name contains the MAC with `:` replaced by `_` (how BlueZ/PipeWire
names them). If none matches, mpv's default output is used.

`VideoPlayer` is raw `libmpv2-sys` FFI and is `unsafe impl Send` so it can be
moved onto the render thread. The update callback receives a raw pointer obtained
from `Arc::into_raw`; every error path in `new()` and the `Drop` impl must
reclaim it with `Arc::from_raw`.

## Conversion pipeline (offline)

```
GIF ──GifDecoder──► frames ──resize 16x16 (Lanczos3)──► palette per frame ──► .divoom16
PNG/JPEG/BMP/WebP ──image::open──► resize ──► single-frame .divoom16
.divoom16 ──Frame::from_16x16──► RGB frames ──GifEncoder (infinite repeat)──► GIF
```

`tests/convert.rs` covers both directions: `.divoom16 → GIF` is compared
byte-for-byte against `images/witch.gif`, and `GIF → .divoom16` is round-tripped
back and compared frame delays and every pixel.
