#!/usr/bin/env python3
"""Export Clawd's runaway-cursor comedy screensaver for the 16x16 Ditoo.

Earlier animations remain available with --theme santa or --theme embers.
"""

import argparse
import os
import sys

from gifwriter import write_gif
from clawd_faces import screensaver_frames as build
from santa_screensaver import build as build_santa
from generate_faces import write_png, validate_frames

SIZE = 16

# Sampled from the hand-drawn faces so this sits inside the same world.
GROUND = (41, 40, 49)      # #292831, the shared background
EMBER_HOT = (222, 121, 90)  # #DE795A
EMBER_MID = (180, 101, 74)  # #B4654A
EMBER_DIM = (76, 48, 39)    # #4C3027
GLOW = (255, 210, 106)      # #FFD26A, used sparingly


def build_embers():
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
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--theme", choices=("clawd", "santa", "embers"), default="clawd")
  parser.add_argument("--out", default=here)
  args = parser.parse_args()
  here = args.out
  frames, delays = {"clawd": build, "santa": build_santa, "embers": build_embers}[args.theme]()
  validate_frames("screensaver", frames, delays)
  distinct = len({tuple(tuple(r) for r in f) for f in frames})
  indexed, palette = index(frames)
  size = write_gif(os.path.join(here, "screensaver.gif"), indexed, palette, delays)
  write_gif(os.path.join(here, "screensaver_preview.gif"),
            [scale(f, 20) for f in indexed], palette, delays)
  write_png(os.path.join(here, "screensaver.png"), frames[0])
  write_png(os.path.join(here, "screensaver_preview.png"), scale(frames[0], 20))
  print(f"screensaver  {len(frames)} frames, {distinct} distinct, "
        f"{len(palette)} colours, {size} bytes, {sum(delays) / 1000:.1f}s")
  return 0


if __name__ == "__main__":
  sys.exit(main())
