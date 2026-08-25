#!/usr/bin/env python3
"""Build the one state the hand-drawn set does not cover: `screensaver`.

Shown after 30 minutes idle, so it has two jobs -- stay interesting for a long
time, and never be mistaken for a status. It therefore uses the SAME palette as
the rest of the set (so it belongs) but no symbol and almost no light (so it
cannot be read as the panel trying to tell you something).

Embers drifting upward: sparse, slow, and on three different speeds so the
field never visibly repeats.
"""

import os
import sys

from gifwriter import write_gif

SIZE = 16

# Sampled from the hand-drawn faces so this sits inside the same world.
GROUND = (41, 40, 49)      # #292831, the shared background
EMBER_HOT = (222, 121, 90)  # #DE795A
EMBER_MID = (180, 101, 74)  # #B4654A
EMBER_DIM = (76, 48, 39)    # #4C3027
GLOW = (255, 210, 106)      # #FFD26A, used sparingly


def build():
  frames, delays = [], []
  count = 24  # long loop: at 260ms this is a touch over six seconds

  # Fixed field, so the drift is smooth rather than random flicker. Three
  # speeds mean the pattern only truly repeats after their common multiple,
  # which is far longer than anyone will watch.
  embers = []
  for i in range(11):
    embers.append({
      "x": (i * 7 + (i % 3)) % SIZE,
      "y0": (i * 5) % SIZE,
      "speed": 1 + (i % 3),
      "bright": i % 4
    })

  for f in range(count):
    grid = [[GROUND] * SIZE for _ in range(SIZE)]
    for e in embers:
      # Upward drift; the modulo wraps it back to the bottom.
      y = (e["y0"] - (f * e["speed"]) // 2) % SIZE
      # Fade with height, so embers die out as they rise.
      height = (SIZE - 1 - y) / (SIZE - 1)
      if e["bright"] == 0 and height < 0.5:
        colour = GLOW
      elif height < 0.35:
        colour = EMBER_HOT
      elif height < 0.7:
        colour = EMBER_MID
      else:
        colour = EMBER_DIM
      grid[y][e["x"]] = colour
    frames.append(grid)
    delays.append(260)
  return frames, delays


def index(frames):
  palette, lookup, out = [], {}, []
  for frame in frames:
    rows = []
    for row in frame:
      r = []
      for colour in row:
        if colour not in lookup:
          lookup[colour] = len(palette)
          palette.append(colour)
        r.append(lookup[colour])
      rows.append(r)
    out.append(rows)
  return out, palette


def scale(frame, factor):
  out = []
  for row in frame:
    big = []
    for v in row:
      big.extend([v] * factor)
    out.extend([big] * factor)
  return out


def main():
  here = os.path.dirname(os.path.abspath(__file__))
  frames, delays = build()
  distinct = len({tuple(tuple(r) for r in f) for f in frames})
  indexed, palette = index(frames)
  size = write_gif(os.path.join(here, "screensaver.gif"), indexed, palette, delays)
  write_gif(os.path.join(here, "screensaver_preview.gif"),
            [scale(f, 20) for f in indexed], palette, delays)
  print(f"screensaver  {len(frames)} frames, {distinct} distinct, "
        f"{len(palette)} colours, {size} bytes")
  if distinct != len(frames):
    print(f"  WARNING: only {distinct} distinct frames -- will read as a stutter")
  return 0


if __name__ == "__main__":
  sys.exit(main())
