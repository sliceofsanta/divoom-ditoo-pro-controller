#!/usr/bin/env python3
"""Generate the animated 16x16 status faces shown on the Ditoo Pro.

All three states are Claude's starburst mark; what changes is how it moves and
what it sits on. A radial form is the rare thing that survives 16x16 -- it has
no silhouette to lose and reads at any rotation:

    working   the mark spinning, coral on near-black blue
    alerting  the mark flaring white against a red pulse
    chilling  the mark breathing slowly, dimmed right down

Stdlib only (see mark.py for the sprite and gifwriter.py for the encoder), so
this runs anywhere without pip installs.

    python3 generate_faces.py            # write the GIFs (+ PNG fallbacks)
    python3 generate_faces.py --preview  # also write 320x320 preview GIFs
"""

import argparse
import math
import os
import struct
import sys
import zlib

import mark
from mark import SIZE, draw, px
from gifwriter import write_gif

# Backgrounds: dark enough that the mark stays the brightest thing on the panel.
BG_CHILL = (0, 8, 6)
BG_WORK = (0, 8, 18)
BG_ALERT_HOT = (96, 4, 0)
BG_ALERT_COOL = (26, 0, 0)

ALERT_FLASH = (255, 236, 190)
CHILL_RAY = (150, 78, 55)
CHILL_TIP = (196, 108, 78)
CHILL_CORE = (214, 130, 100)


def chilling_frames():
  """Idle: the mark breathing slowly, dimmed right down.

  The rays have to travel a good pixel and a half either side of centre --
  a subtler breath quantises away to nothing at this resolution and the
  animation just sits there.
  """
  frames = []
  count = 8
  for i in range(count):
    # One smooth in-and-out over the loop, so there is no seam.
    phase = math.sin(2 * math.pi * i / count)
    warmth = (phase + 1) / 2  # 0 at the smallest, 1 at the fullest
    rays = tuple(
      int(base + (full - base) * warmth)
      for base, full in zip(CHILL_RAY, CHILL_TIP)
    )
    grid = draw(
      BG_CHILL,
      rotation=0.0,
      r1=5.9 + 1.5 * phase,
      colour=rays, tip=CHILL_TIP, core=CHILL_CORE, core_size=2
    )
    frames.append(grid)
  return frames, [220] * count


def working_frames():
  """Busy: the mark spinning. Eight rays means 45 degrees is a full period,
  so stepping through exactly that much loops seamlessly."""
  frames = []
  count = 8
  for i in range(count):
    grid = draw(BG_WORK, rotation=(math.pi / 4) * i / count)
    frames.append(grid)
  return frames, [110] * count


def alerting_frames():
  """Blocked on you: the mark flaring against a red pulse.

  The flare and the background run on different periods -- put both on the
  same 2-frame beat and the animation collapses into a single flip.
  """
  frames = []
  count = 6
  for i in range(count):
    hot = i % 2 == 0
    flare = i % 3 == 0
    grid = draw(
      BG_ALERT_HOT if hot else BG_ALERT_COOL,
      rotation=(math.pi / 4) * (i % 2) / 2,
      r1=7.0 if flare else 5.6,
      colour=ALERT_FLASH if flare else mark.CORAL,
      tip=ALERT_FLASH if flare else mark.CORAL_LIGHT,
      core=ALERT_FLASH,
      core_size=3 if flare else 2
    )
    frames.append(grid)
  return frames, [100] * count


def off_frames():
  black = (0, 0, 0)
  return [[[black] * SIZE for _ in range(SIZE)]], [500]


FACES = {
  "chilling": (chilling_frames, "idle -- the mark breathing, dimmed down"),
  "working": (working_frames, "busy -- the mark spinning"),
  "alerting": (alerting_frames, "blocked on you -- the mark flaring, red pulse"),
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
  mark.CORAL: "#", mark.CORAL_LIGHT: "*", mark.CORE: "@",
  CHILL_RAY: "#", CHILL_TIP: "*", CHILL_CORE: "@", ALERT_FLASH: "!",
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
