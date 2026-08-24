#!/usr/bin/env python3
"""Generate the 16x16 status faces shown on the Ditoo Pro.

Stdlib only (hand-rolled PNG writer) so it runs anywhere without pip installs.

    python3 generate_faces.py            # write PNGs next to this script
    python3 generate_faces.py --preview  # also write 320x320 previews

Legend used in the grids below:
    .  background      #  face colour
    o  accent colour   -  dim colour
"""

import argparse
import os
import struct
import sys
import zlib

SIZE = 16

# --- faces -----------------------------------------------------------------
# Colour carries most of the signal at 16x16 (readable across a room), the
# shapes disambiguate up close.

CHILLING = {
  "name": "chilling",
  "doc": "idle / done - sleepy eyes, soft smile, calm green",
  "bg": (0, 12, 8),
  "fg": (54, 200, 122),
  "accent": (140, 235, 180),
  "dim": (20, 70, 48),
  "grid": [
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "...####..####...",
    "................",
    "................",
    "................",
    "....#......#....",
    ".....######.....",
    "................",
    "................",
    "................",
    "................",
  ],
}

WORKING = {
  "name": "working",
  "doc": "Claude is running - focused eyes, progress bar, cyan",
  "bg": (0, 10, 18),
  "fg": (0, 190, 226),
  "accent": (150, 240, 255),
  "dim": (0, 60, 80),
  "grid": [
    "................",
    "................",
    "................",
    "................",
    "...####..####...",
    "...####..####...",
    "...####..####...",
    "................",
    "................",
    "......####......",
    "................",
    "................",
    "................",
    "..------------..",
    "..oooooo------..",
    "................",
  ],
}

ALERTING = {
  "name": "alerting",
  "doc": "waiting on you - wide eyes, open mouth, red",
  "bg": (20, 0, 0),
  "fg": (255, 58, 48),
  "accent": (255, 232, 120),
  "dim": (90, 12, 8),
  "grid": [
    "................",
    "................",
    "......####......",
    "................",
    "...oooo..oooo...",
    "...o##o..o##o...",
    "...o##o..o##o...",
    "...oooo..oooo...",
    "................",
    "................",
    "......####......",
    ".....#....#.....",
    ".....#....#.....",
    "......####......",
    "................",
    "................",
  ],
}

OFF = {
  "name": "off",
  "doc": "session ended - blank display",
  "bg": (0, 0, 0),
  "fg": (0, 0, 0),
  "accent": (0, 0, 0),
  "dim": (0, 0, 0),
  "grid": ["." * SIZE for _ in range(SIZE)],
}

FACES = [CHILLING, WORKING, ALERTING, OFF]


def render(face):
  """Grid of characters -> 16x16 list of RGB rows."""
  colours = {
    ".": face["bg"],
    "#": face["fg"],
    "o": face["accent"],
    "-": face["dim"],
  }
  grid = face["grid"]
  if len(grid) != SIZE:
    raise ValueError(f"{face['name']}: expected {SIZE} rows, got {len(grid)}")
  pixels = []
  for y, row in enumerate(grid):
    if len(row) != SIZE:
      raise ValueError(f"{face['name']} row {y}: expected {SIZE} cols, got {len(row)}")
    pixels.append([colours[ch] for ch in row])
  return pixels


def write_png(path, pixels, scale=1):
  height = len(pixels) * scale
  width = len(pixels[0]) * scale
  raw = b""
  for row in pixels:
    line = b"\x00"
    for rgb in row:
      line += bytes(rgb) * scale
    raw += line * scale

  def chunk(tag, data):
    body = tag + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

  png = (
    b"\x89PNG\r\n\x1a\n"
    + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    + chunk(b"IDAT", zlib.compress(raw, 9))
    + chunk(b"IEND", b"")
  )
  with open(path, "wb") as handle:
    handle.write(png)


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--preview", action="store_true", help="also write 320x320 previews")
  parser.add_argument("--out", default=os.path.dirname(os.path.abspath(__file__)))
  args = parser.parse_args()

  for face in FACES:
    pixels = render(face)
    path = os.path.join(args.out, f"{face['name']}.png")
    write_png(path, pixels)
    print(f"{face['name']:9s} {face['doc']}")
    for row in face["grid"]:
      print(f"    {row}")
    print(f"    -> {path}")
    if args.preview:
      preview = os.path.join(args.out, f"{face['name']}_preview.png")
      write_png(preview, pixels, scale=20)
      print(f"    -> {preview}")
    print()
  return 0


if __name__ == "__main__":
  sys.exit(main())
