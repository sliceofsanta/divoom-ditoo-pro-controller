#!/usr/bin/env python3
"""Generate the animated 16x16 status faces shown on the Ditoo Pro.

The character is Clawd, Claude Code's pixel crab. He stays Claude orange in
every state so he reads as the same character; the STATE is carried by the
background wash, his pose, and the motion:

    working   claws typing, eyes down, progress bar sweeping
    alerting  both claws waving overhead, wide eyes, red pulse
    chilling  napping -- eyes shut, slow breathing bob, drifting z

Stdlib only (see clawd.py for the sprite and gifwriter.py for the encoder), so
this runs anywhere without pip installs.

    python3 generate_faces.py            # write the GIFs (+ PNG fallbacks)
    python3 generate_faces.py --preview  # also write 320x320 preview GIFs
"""

import argparse
import os
import struct
import sys
import zlib

import clawd
from clawd import SIZE, draw, px, hline
from gifwriter import write_gif

# Backgrounds: dark enough that Clawd's orange stays the brightest thing.
BG_CHILL = (0, 20, 13)
BG_WORK = (0, 14, 28)
BG_ALERT_HOT = (86, 0, 0)
BG_ALERT_COOL = (24, 0, 0)

BAR_TRACK = (0, 52, 74)
BAR_FILL = (120, 226, 255)
ZZZ = (90, 170, 130)
ALERT_FLASH = (255, 226, 150)


def chilling_frames():
  """Napping: eyes shut, a slow breathing bob, and a z drifting up."""
  bob = [0, 0, 1, 1, 1, 0, 0, 0]
  frames = []
  for i, offset in enumerate(bob):
    eye = "open" if i == 5 else "closed"  # one brief peek per loop
    grid = draw(BG_CHILL, body_y=5 + offset, eye=eye)
    # A small z climbing away from him, fading at the top of its rise.
    zy = 3 - i // 3
    if i < 6:
      colour = ZZZ if i < 3 else (60, 115, 88)
      hline(grid, 11, 13, zy, colour)
      px(grid, 13, zy + 1, colour)
      px(grid, 12, zy + 1, colour)
      hline(grid, 11, 13, zy + 2, colour)
    frames.append(grid)
  return frames, [220] * len(frames)


def working_frames():
  """Typing: claws alternate on the keys while a bar sweeps underneath."""
  poses = [(-2, 1), (-2, 1), (1, -2), (1, -2), (-2, 1), (-2, 1), (1, -2), (1, -2)]
  frames = []
  for i, (left, right) in enumerate(poses):
    grid = draw(BG_WORK, body_y=5, claw_l=left, claw_r=right, eye="down")
    hline(grid, 2, 13, 14, BAR_TRACK)
    filled = int(round(12 * (i + 1) / len(poses)))
    if filled:
      hline(grid, 2, 1 + filled, 14, BAR_FILL)
    frames.append(grid)
  return frames, [130] * len(frames)


def alerting_frames():
  """Waving for your attention: both claws overhead, urgent red pulse.

  The claws see-saw rather than flapping in unison, and the sparks move between
  hot frames -- with both on the same 2-frame period the animation collapses
  into a single flip.
  """
  waves = [(-4, -2), (-3, -3), (-2, -4), (-3, -3), (-4, -2), (-3, -3)]
  spark_sets = [
    ((0, 0), (15, 0)),                      # top
    (),
    ((0, 15), (15, 15)),                    # bottom
    (),
    ((0, 0), (15, 0), (0, 15), (15, 15)),   # all four
    (),
  ]
  frames = []
  for i, (left, right) in enumerate(waves):
    hot = i % 2 == 0
    grid = draw(
      BG_ALERT_HOT if hot else BG_ALERT_COOL,
      body_y=6, claw_l=left, claw_r=right, eye="wide", splay=1
    )
    for cx, cy in spark_sets[i]:
      px(grid, cx, cy, ALERT_FLASH)
    frames.append(grid)
  return frames, [110] * len(frames)


def off_frames():
  black = (0, 0, 0)
  return [[[black] * SIZE for _ in range(SIZE)]], [500]


FACES = {
  "chilling": (chilling_frames, "napping -- eyes shut, breathing bob, drifting z"),
  "working": (working_frames, "typing -- claws on the keys, bar sweeping"),
  "alerting": (alerting_frames, "waving both claws, wide eyes, red pulse"),
  "off": (off_frames, "blank display"),
}


# --- output ----------------------------------------------------------------

def index_frames(frames):
  palette, lookup, indexed = [], {}, []
  for frame in frames:
    rows = []
    for row in frame:
      out_row = []
      for colour in row:
        if colour not in lookup:
          lookup[colour] = len(palette)
          palette.append(colour)
        out_row.append(lookup[colour])
      rows.append(out_row)
    indexed.append(rows)
  return indexed, palette


def scale(frame, factor):
  out = []
  for row in frame:
    big = []
    for value in row:
      big.extend([value] * factor)
    out.extend([big] * factor)
  return out


def write_png(path, frame):
  raw = b""
  for row in frame:
    raw += b"\x00" + b"".join(bytes(c) for c in row)

  def chunk(tag, data):
    body = tag + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

  png = (
    b"\x89PNG\r\n\x1a\n"
    + chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 2, 0, 0, 0))
    + chunk(b"IDAT", zlib.compress(raw, 9))
    + chunk(b"IEND", b"")
  )
  with open(path, "wb") as handle:
    handle.write(png)


CHARS = {
  clawd.CLAWD: "#", clawd.CLAWD_DARK: "+", clawd.CLAWD_LIGHT: "*",
  clawd.EYE_WHITE: "O", clawd.EYE_DARK: "o",
  BAR_FILL: "=", BAR_TRACK: "-", ZZZ: "z", ALERT_FLASH: "!",
}


def ascii_preview(frame):
  counts = {}
  for row in frame:
    for colour in row:
      counts[colour] = counts.get(colour, 0) + 1
  bg = max(counts, key=counts.get)
  return ["".join("." if c == bg else CHARS.get(c, "?") for c in row) for row in frame]


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--preview", action="store_true",
                      help="also write 320x320 preview GIFs")
  parser.add_argument("--out", default=os.path.dirname(os.path.abspath(__file__)))
  args = parser.parse_args()

  for name, (builder, doc) in FACES.items():
    frames, delays = builder()
    indexed, palette = index_frames(frames)

    gif_path = os.path.join(args.out, f"{name}.gif")
    size = write_gif(gif_path, indexed, palette, delays)
    write_png(os.path.join(args.out, f"{name}.png"), frames[0])

    print(f"{name:9s} {doc}")
    print(f"    {len(frames)} frames, {delays[0]}ms each, "
          f"{len(palette)} colours, {size} bytes")
    for line in ascii_preview(frames[0]):
      print(f"    {line}")
    print(f"    -> {gif_path}")

    if args.preview:
      big = [scale(f, 20) for f in indexed]
      preview = os.path.join(args.out, f"{name}_preview.gif")
      write_gif(preview, big, palette, delays)
      print(f"    -> {preview}")
    print()
  return 0


if __name__ == "__main__":
  sys.exit(main())
