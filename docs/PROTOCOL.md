# Divoom Ditoo Pro SPP protocol

Everything this crate knows about the wire protocol. Reverse-engineered from
partial vendor documentation and observation — **treat anything without a test
or a cited source as a working guess.**

Sources referenced from the code:

- Protocol introduction: <https://docin.divoom-gz.com/web/#/5/146>
- "App new send gif cmd" (0x8B): <https://docin.divoom-gz.com/web/#/5/293>
- Alarm (0x43): <https://docin.divoom-gz.com/web/#/5/247>
- Date/time (0x18), undocumented, taken from
  <https://github.com/d03n3rfr1tz3/esp32-divoom>
- node-divoom-timebox-evo PROTOCOL.md:
  <https://github.com/RomRider/node-divoom-timebox-evo/blob/0.3.0/PROTOCOL.md>

## Transport

Classic Bluetooth **RFCOMM / Serial Port Profile**, UUID
`00001101-0000-1000-8000-00805f9b34fb`. The device must already be paired. The
device advertises a name containing `DitooPro` (the audio endpoint shows up as
e.g. `DitooPro-Audio`).

Implementation notes live in [ARCHITECTURE.md](ARCHITECTURE.md#deviceconnection);
the short version is that BlueZ hands out SPP through the profile API, so the
client registers an RFCOMM profile and accepts the incoming request from the
target MAC rather than dialling a channel number.

All multi-byte integers are **little-endian**.

## Packet framing (host → device)

Built by `Packet::serialize()` in [`src/protocol/packet.rs`](../src/protocol/packet.rs).

```
 offset  size  field
 ------  ----  -----------------------------------------------
      0     1  0x01                      start marker
      1     2  length  (u16 LE)          = payload_len + 3
      3     1  command                   opcode byte
      4     n  payload                   command-specific
    4+n     2  checksum (u16 LE)
    6+n     1  0x02                      end marker
```

`length` counts everything after the length field except the end marker:
the opcode (1) + payload (n) + checksum (2).

**Checksum** — a plain 16-bit wrapping sum of every byte from the length field
through the end of the payload (i.e. offsets `1 ..= 3+n`), *including* the two
length bytes and the opcode:

```rust
buffer.iter().fold(0u16, |acc, x| acc.wrapping_add(*x as u16))
```

The wrapping is load-bearing: large payloads overflow a `u16` regularly (an
earlier version overflowed and panicked in debug builds; see commit
"Fix checksum overflow").

## Response framing (device → host)

Parsed by `Response::deserialize()`. The device answers most commands, and also
emits **unsolicited** responses, so responses must be matched to requests by the
echoed opcode rather than by arrival order.

```
 offset  size  field
 ------  ----  -----------------------------------------------
      0     1  0x01                      start marker
      1     2  length  (u16 LE)          = total_len - 4
      3     1  0x04                      "this is a response"
      4     1  original command          echoes the opcode being answered
      5     1  0x55 = ACK, anything else = NAK
      6     m  data                      command-specific, often empty
    6+m     2  checksum (u16 LE)
    8+m     1  0x02                      end marker
```

Validation performed, in order: start marker, end marker, `len == length + 4`,
response byte `0x04`, checksum (same wrapping-sum algorithm, over offsets
`1 ..= 5+m`). A NAK is surfaced as an error by `send_and_receive`.

Note that `Response.data` is everything *after* the ACK byte. For extended
commands (`0xBD`) the first data byte is the echoed sub-command type, so payload
parsing starts at `data[1]`.

## Command opcodes

Defined in [`src/protocol/command.rs`](../src/protocol/command.rs). Names in
parentheses are the vendor `SPP_*` names where known.

| Opcode | Name | Payload | Response used? |
|---|---|---|---|
| `0x08` | `SetVolume` | `volume: u8` (0–16) | no |
| `0x09` | `GetVolume` | *(empty)* | **yes** — `data[0]` = volume |
| `0x0A` | `SetPlayStatus` | `playing: u8` (1 = play, 0 = pause) | no |
| `0x18` | `SetDateTime` | 7 bytes, see below | no |
| `0x23` | `LightArrowSwitch` (`SPP_LIGHT_ARROW_SWITCH`) | `mode: u8` — 0 next, 1 prev, 2 toggle | no |
| `0x43` | `Alarm` | 10 bytes, see below | no |
| `0x45` | `SetBoxMode` | mode-dependent, see below | no |
| `0x6C` | `DrawingEncodeMoviePlay` | streamed frame, see below | no |
| `0x6E` | `DrawingCtrlMoviePlay` | `u8` — 0 stop, 1 start | no |
| `0x74` | `SetBrightness` (`SPP_SET_SYSTEM_BRIGHT`) | `level: u8` (0–100) | no |
| `0x7C` | `LedUpdateFontInfo` | *(declared, unused)* | — |
| `0x86` | `LedWordCmd` | *(declared, unused)* | — |
| `0x8B` | `Animation` | chunked file transfer, see below | no |
| `0xBD` | `ExtendedCommand` | sub-command namespace, see below | sometimes |

`0x7C` and `0x86` exist in the enum but are not sent by any code path.

### `0x18` — set date/time

Undocumented; layout taken from the esp32-divoom project.

```
 byte 0  year % 100        e.g. 25 for 2025
 byte 1  year / 100        e.g. 20
 byte 2  month  (1–12)
 byte 3  day    (1–31)
 byte 4  hour   (0–23)
 byte 5  minute (0–59)
 byte 6  second (0–59)
```

Note the unusual split-year encoding: low part first, century second.

### `0x43` — alarm

```
 byte 0  index          which alarm slot, from 0
 byte 1  enable         1 on, 0 off
 byte 2  hour
 byte 3  minute
 byte 4  repeat         bitmask, bits 0–6 = Sunday–Saturday
 byte 5  mode           ALARM_MUSIC = 0; others 1–4
 byte 6  trigger_mode   ALARM_TRIGGER_MUSIC = 1, ALARM_TRIGGER_GIF = 4
 byte 7  fm[0]          FM frequency point, when trigger_mode = music
 byte 8  fm[1]
 byte 9  volume         0–100
```

> **Known bug:** the CLI's `alarm on` / `alarm off` argument is parsed and logged
> but never reaches the packet. `send_alarm()` hardcodes `enable: false`,
> `index: 0`, `13:37`, `volume: 100`.

### `0x45` — set box mode

The first payload byte selects a mode; the rest is mode-dependent. `mode raw`
in the CLI exists to probe undocumented combinations.

| First byte | Mode | Remaining payload |
|---|---|---|
| `0x01` | Light | `sub_mode: u8`, `r`, `g`, `b`, `brightness: u8`, `on: u8`, then 3 zero bytes |
| `0x02` | Hot / trending | *(none)* |
| `0x03` | Special | `sub_type: u8` |
| `0x04` | Music visualizer | `sub_type: u8`, then 8 zero bytes |

Light sub-modes: `0` clock, `1` temperature, `2` solid color, `3` special,
`4` sound-reactive, `5` sound-reactive (user), `6` music.

The trailing zero padding for light and music modes is what the vendor app
sends; whether the device requires it is untested.

### `0x6E` / `0x6C` — real-time frame streaming

Used for scrolling text and video. Unlike `0x8B` this does not persist anything
on the device — it drives the display frame by frame while the host is connected.

```
0x6E  payload [0x00]     stop  / reset
0x6E  payload [0x01]     start streaming
0x6C  payload:
        offset 0  2  speed    (u16 LE)   milliseconds per frame; always 60 here
        offset 2  2  data_len (u16 LE)   length of the encoded frame
        offset 4  n  encoded frame       a single .divoom16 frame (see FILE_FORMAT.md)
0x6E  payload [0x00]     stop
```

Both senders open with a `[0x00]` *then* a `[0x01]` — the leading stop resets any
stream left running by a previous invocation.

Pacing: `send_scrolling_text` sleeps an extra 20ms between frames on top of the
40ms `INTER_PACKET_DELAY`; `send_video` relies on the mpv render rate and drops
frames rather than buffering.

### `0x8B` — animation / image file transfer

Uploads a whole `.divoom16` file. Documented at
<https://docin.divoom-gz.com/web/#/5/293>. Encoded by
[`src/protocol/animation.rs`](../src/protocol/animation.rs).

```
 byte 0     control_word:  0 = StartSeeding, 1 = SendingData, 2 = TerminateSending
 bytes 1-4  file_size (u32 LE)   — omitted when control_word = 2
 bytes 5-6  offset_id (u16 LE)   — only when control_word = 1
 bytes 7..  image_part           — only when control_word = 1, up to 256 bytes
```

The transfer is one `StartSeeding` packet (announcing the total size) followed by
`ceil(size / 256)` `SendingData` packets.

> **Two deviations from the docs** worth knowing about:
> `TerminateSending` is never sent by this crate, and `offset_id` is the *chunk
> index* (0, 1, 2, …), not a byte offset. Both appear to work, but they are the
> first things to re-check if a transfer misbehaves.

### `0xBD` — extended commands

A namespace: the first payload byte is the sub-command, the rest are its
parameters. `extended_command::build_packet(ext_type, params)` builds these.

| Sub-command | Name | Params | Response |
|---|---|---|---|
| `0x14` | `SET_USER_DEFINE_TIME` | `clock_id: u16 LE` | no |
| `0x15` | `GET_USER_DEFINE_TIME` | *(none)* | **yes** — `data[1..3]` = `clock_id: u16 LE` |
| `0x26` | `SET_LANGUAGE` | `index: u8` | no |

Language indices:

| 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|
| `en` | `zh-hans` | `zh-hant` | `ja` | `th` | `fr` | `it` | `he` |

| 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|
| `es` | `de` | `ru` | `pt` | `ko` | `nl` | `uk` | `ms` |

## Timing

| Constant | Value | Where |
|---|---|---|
| `INTER_PACKET_DELAY` | 40ms after every write | `lib.rs` |
| scrolling-text extra delay | 20ms per frame | `send_scrolling_text` |
| response timeout | 5s | `send_and_receive` |
| `MAX_CONNECT_ATTEMPTS` | 3, with 1s between | `DeviceConnection::connect` |
| scan duration | 20s | `scan_devices` |
| frame `speed` field | 60ms | scrolling text and video |

The 40ms delay is empirical. Sending faster has not been characterised; the
device gives no flow-control signal on this path.

## Not implemented

A large part of the vendor protocol is untouched — drawing pad, sand painting,
sleep mode, EQ, microphone, SD-card music browsing, games, notification
forwarding, firmware update, work-mode switching, and the JSON-over-SPP protocol
used for watch faces and score mode. See [TODO.md](../TODO.md) for the tracked
list.
