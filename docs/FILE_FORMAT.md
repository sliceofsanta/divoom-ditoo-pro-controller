# The `.divoom16` file format

The container the Ditoo Pro accepts for images and animations on the 16x16
display. Implemented in [`src/divoom_file_format/`](../src/divoom_file_format/).

The same frame encoding is used in two places: as a whole file uploaded with
opcode `0x8B`, and as individual frames streamed with opcode `0x6C`. See
[PROTOCOL.md](PROTOCOL.md).

All multi-byte integers are **little-endian**.

## File structure

There is **no global header**. A file is simply one or more frames concatenated
back to back; the reader keeps parsing frames until it hits EOF.

```
┌─────────┬─────────┬─────────┬─────┐
│ Frame 0 │ Frame 1 │ Frame 2 │ ... │
└─────────┴─────────┴─────────┴─────┘
```

## Frame

```
 offset  size  field
 ------  ----  ---------------------------------------------------------
      0     1  0xAA                       magic number
      1     2  length   (u16 LE)          total frame size, header included
      3     2  time_ms  (u16 LE)          how long to show this frame
      5     1  reuse_palette              1 = append to previous palette, 0 = replace
      6     1  color_count                number of colors that follow (see below)
      7   3*c  palette                    RGB triples, one byte per channel
    7+3c     p  pixel data                packed palette indices
```

`length = 7 + 3*color_count + pixel_data_len`, i.e. it covers the whole frame
including its own header bytes.

### `color_count` and the 256-color case

`color_count` is a single byte, so a full 256-color palette wraps to `0`. The
reader disambiguates:

```
color_count == 0 && reuse_palette == 0   →  256 colors
otherwise                                →  color_count colors
```

A 16x16 frame has 256 pixels, so 256 is also the hard upper bound on distinct
colors in a frame — no quantization is ever needed. `Animation::from_image`
still rejects palettes larger than 256 defensively.

### `reuse_palette`

When set, the frame's own palette is **appended to** the palette carried over
from the previous frame, and indices address the combined table. When clear, the
carried palette is discarded and replaced.

This crate **reads** `reuse_palette` but never **writes** it: every frame it
produces sets `reuse_palette = 0` and carries a full palette. Files from the
vendor app do use it.

### Pixel data

Pixels are stored as palette indices packed at the minimum bit width for the
palette size:

```
bits_per_pixel = ceil(log2(palette_len))
pixel_data_len = ceil(16 * 16 * bits_per_pixel / 8)
```

| Palette size | bits/pixel | pixel data |
|---|---|---|
| 1 | 0 | 0 bytes |
| 2 | 1 | 32 bytes |
| 3–4 | 2 | 64 bytes |
| 5–8 | 3 | 96 bytes |
| 9–16 | 4 | 128 bytes |
| 17–32 | 5 | 160 bytes |
| 33–64 | 6 | 192 bytes |
| 65–128 | 7 | 224 bytes |
| 129–256 | 8 | 256 bytes |

A single-color frame genuinely encodes to **zero** bytes of pixel data — every
index is 0 and 0 bits are needed to say so. Both the reader and writer handle
this, but it is an easy edge case to break.

Indices are written in **row-major** order (all of row 0 left to right, then row
1, …) and packed **LSB-first within each byte** (`bitstream_io::LittleEndian`).
For a 3-bit width the first byte holds pixel 0 in bits 0–2, pixel 1 in bits 3–5,
and the low 2 bits of pixel 2 in bits 6–7.

## Worked example

The first frame of [`images/witch.divoom16`](../images/witch.divoom16):

```
aa 7f 00 7f 00 00 08 | 00 00 00  9b 9b 9b  36 05 5e  92 6d c4 ...
▲  ▲──▲  ▲──▲  ▲  ▲    ▲───────────────────────────────────────
│  │     │     │  │    palette: 8 RGB triples (24 bytes)
│  │     │     │  └─ color_count = 8
│  │     │     └──── reuse_palette = 0
│  │     └────────── time_ms = 0x007f = 127ms
│  └──────────────── length = 0x007f = 127 bytes
└─────────────────── magic 0xAA
```

8 colors → 3 bits per pixel → `256 * 3 / 8` = 96 bytes of pixel data, starting at
offset 31. Total: `7 + 24 + 96 = 127`, matching the length field. The next frame
begins at file offset 127.

## Reading and writing

| Type | Role |
|---|---|
| `FrameHeader` | the 7 header bytes; validates the magic number, discards `length` |
| `Frame` | header + palettes + a decoded `DynamicImage`; `from_16x16` / `serialize` |
| `Animation` | a `Vec<Frame>` plus all the format conversions |

`Animation` conversions:

| Method | Direction |
|---|---|
| `from_16x16(reader)` | `.divoom16` → frames |
| `from_gif(reader)` | GIF → frames (per-frame delays preserved) |
| `from_image(image)` | any single image → one frame with `time_ms = 0` |
| `save_to_divoom_format(writer)` | frames → `.divoom16` |
| `save_to_gif(writer)` | frames → GIF, infinite repeat |

Input images of any size are resized to exactly 16x16 with a **Lanczos3** filter
(`prepare_image` in `mod.rs`) — aspect ratio is not preserved.

GIF delays are stored in centiseconds, `.divoom16` in milliseconds, so a
round-trip through GIF quantizes the timing (127ms → 120ms).

`save_to_divoom_format` tracks a running palette across frames, honouring each
frame's `reuse_palette` flag, so that the indices it writes match what a reader
will reconstruct.

> **Latent bug in `Animation::from_16x16`:** the loop treats an
> `UnexpectedEof` `io::Error` as a clean end-of-file and propagates
> non-`io::Error` failures, but an `io::Error` of any *other* kind falls through
> both branches and the loop spins forever. A truncated or unreadable file can
> hang instead of erroring.

## Inspecting files

```bash
divoom-ditoo-pro-controller debug-image ./images/witch.divoom16
```

Prints, per frame: the header, the computed bits-per-pixel and pixel data size,
the color count, and the local palette as hex colors.
