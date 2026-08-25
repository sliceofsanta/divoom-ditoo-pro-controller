#!/usr/bin/env python3
"""Generate the animated 16x16 status faces for the Ditoo Pro.

Design brief: every state must be understandable without a legend, and the
panel should be used cleverly rather than filled with detail nobody can
resolve at 256 pixels.

Two ideas do most of the work.

SYMBOLS, NOT CHARACTERS. A check, a cross, an exclamation and three dots are
read instantly and survive being twelve pixels tall. A face at this size is a
smudge you have to learn first.

THE BORDER IS A FREE INSTRUMENT. A 16x16 panel has exactly 60 edge pixels.
Used as a track, the ring shows progress, urgency or activity while the middle
still shows what the state IS -- so each face carries two pieces of
information without either crowding the other.

Every state owns a background colour, because across a room colour is all that
reads. The alert ladder walks the temperature up on purpose: amber, then
orange, then the whole panel red.

    python3 generate_faces.py            # write the GIFs (+ PNG fallbacks)
    python3 generate_faces.py --preview  # also write 320x320 preview GIFs
"""

import argparse
import math
import os
import struct
import sys
import zlib

from glyphs import (
  RING, SIZE, bang, blank, check_path, cross_path, dots, draw_path, put, rect,
  ring, ring_gradient
)
from gifwriter import write_gif

BG_THINK = (6, 10, 40)
BG_WORK = (0, 22, 26)
BG_ALERT = (44, 22, 0)
BG_ALERT2 = (72, 18, 0)
BG_ALERT3_HOT = (235, 30, 20)
BG_ALERT3_COOL = (40, 0, 0)
BG_COMPACT = (22, 8, 34)
BG_OK = (0, 26, 12)
BG_ERR = (32, 0, 10)
BG_IDLE = (4, 8, 16)

CYAN = (60, 220, 235)
CYAN_DIM = (16, 84, 96)
INDIGO = (120, 150, 255)
INDIGO_DIM = (44, 60, 130)
AMBER = (255, 176, 40)
AMBER_DIM = (110, 70, 12)
ORANGE = (255, 120, 30)
CREAM = (255, 240, 210)
VIOLET = (190, 130, 255)
VIOLET_DIM = (80, 50, 120)
GREEN = (60, 240, 130)
GREEN_DIM = (20, 90, 50)
RED = (255, 70, 70)
RED_DIM = (110, 24, 30)


def thinking_frames():
  """Three dots filling in turn, with a comet going round the ring.

  Dots are the universally understood "thinking". The ring turning at its own
  rate says the machine is alive rather than stuck -- and the two run on
  deliberately different periods, because matched periods alias into one flat
  repeat.
  """
  frames, delays = [], []
  for i in range(9):
    g = blank(BG_THINK)
    ring_gradient(g, head=i * 5, length=10, bright=INDIGO, dim=INDIGO_DIM)
    dots(g, CREAM, lit=(i % 3) + 1)
    frames.append(g)
    delays.append(160)
  return frames, delays


def working_frames():
  """The ring fills clockwise -- a progress bar bent around the panel -- with a
  core pulsing on its own beat.

  This is the clever use of a square: a straight progress bar would eat a row
  of the middle, and the border was doing nothing anyway.
  """
  frames, delays = [], []
  count = 10
  for i in range(count):
    g = blank(BG_WORK)
    ring(g, CYAN_DIM, 0, len(RING))
    ring(g, CYAN, 0, int(len(RING) * (i + 1) / count))
    size = 2 + (1 if i % 4 == 0 else 0) + (1 if i % 4 == 2 else 0)
    half = size // 2
    rect(g, 8 - half, 8 - half, 7 + size - half, 7 + size - half, CREAM)
    frames.append(g)
    delays.append(110)
  return frames, delays


def alerting_frames():
  """A big exclamation on amber, ring breathing around it.

  Amber rather than red on purpose: this is the first ask, and the ladder needs
  somewhere left to escalate to.
  """
  frames, delays = [], []
  count = 8
  for i in range(count):
    g = blank(BG_ALERT)
    phase = math.sin(2 * math.pi * i / count)
    span = max(2, int(len(RING) * (0.35 + 0.3 * phase)))
    ring(g, AMBER_DIM, 0, len(RING))
    # Rotated as well as breathed: width alone repeats on the way back down,
    # and identical frames read as a stutter rather than a pulse.
    ring(g, AMBER, i * 7 - span // 2, span)
    bang(g, CREAM if i % 2 == 0 else AMBER)
    frames.append(g)
    delays.append(150)
  return frames, delays


def alerting2_frames():
  """One minute in. The same mark, so it reads as the same event getting worse
  -- hotter ground, the whole ring strobing, the bar jolting sideways."""
  frames, delays = [], []
  for i in range(8):
    hot = i % 2 == 0
    g = blank(BG_ALERT2)
    ring(g, ORANGE if hot else AMBER_DIM, 0, len(RING))
    # A bright arc sweeping round on a 5-beat, so the 2-beat strobe and the
    # 3-beat jolt cannot land the loop back on a frame it has already shown.
    ring(g, CREAM, i * 11, 5)
    bang(g, CREAM if hot else ORANGE, x=7 + (1 if i % 3 == 0 else 0))
    frames.append(g)
    delays.append(100)
  return frames, delays


def alerting3_frames():
  """Five minutes. The panel becomes the alarm: full-field strobe with the mark
  knocked out of it. Legibility stops mattering -- being seen from the far side
  of the room is the whole job."""
  frames, delays = [], []
  for i in range(6):
    hot = i % 2 == 0
    g = blank(BG_ALERT3_HOT if hot else BG_ALERT3_COOL)
    # The mark shifts a pixel on a 3-beat so the strobe's own 2-beat
    # cannot collapse the loop back onto frames already shown.
    bang(g, BG_ALERT3_COOL if hot else RED, x=7 + (1 if i % 3 == 1 else 0))
    if not hot:
      ring(g, RED, 0, len(RING))
    # Corner sparks rotating each frame: without them a two-state strobe is
    # literally two frames repeated, which flickers rather than alarms.
    for k in range(3):
      x, y = RING[(i * 13 + k * 20) % len(RING)]
      put(g, x, y, CREAM if hot else RED)
    frames.append(g)
    delays.append(90)
  return frames, delays


def compacting_frames():
  """Columns squeezing in from both edges -- the panel literally performing a
  compaction, which needs no explaining."""
  frames, delays = [], []
  for i in range(10):
    g = blank(BG_COMPACT)
    # Ten frames against a five-step squeeze: the second pass differs because
    # the drifting motes below are on a period of their own.
    squeeze = i % 5
    for x in range(squeeze):
      for y in range(2, 14):
        put(g, x, y, VIOLET_DIM)
        put(g, SIZE - 1 - x, y, VIOLET_DIM)
    rect(g, 6, 6 - squeeze // 2, 9, 9 + squeeze // 2, VIOLET)
    rect(g, 7, 7, 8, 8, CREAM)
    # Loose motes falling into the crate, on a 7-beat.
    for k in range(2):
      mx = 4 + ((i * 3 + k * 5) % 8)
      my = 1 + ((i * 2 + k * 4) % 3)
      put(g, mx, my, VIOLET_DIM)
    frames.append(g)
    delays.append(130)
  return frames, delays


def success_frames():
  """The tick draws itself, then the ring sweeps round once as a flourish.

  Drawing it on is what makes it feel earned; a tick that simply appears reads
  as a static icon rather than something that just happened.
  """
  path = check_path()
  frames, delays = [], []
  steps = 6
  for i in range(steps):
    g = blank(BG_OK)
    draw_path(g, path, GREEN, upto=int(len(path) * (i + 1) / steps))
    frames.append(g)
    delays.append(70)
  for i in range(4):
    g = blank(BG_OK)
    draw_path(g, path, GREEN)
    ring_gradient(g, head=i * 15, length=20, bright=GREEN, dim=GREEN_DIM)
    frames.append(g)
    delays.append(120)
  return frames, delays


def error_frames():
  """The cross draws itself one arm at a time, then the panel flinches.

  The flinch is two frames offset by a pixel. Small, but at this size a
  one-pixel jolt is the difference between "a cross" and "something broke".
  """
  arm_a, arm_b = cross_path()
  frames, delays = [], []
  for i in range(3):
    g = blank(BG_ERR)
    draw_path(g, arm_a, RED, upto=int(len(arm_a) * (i + 1) / 3))
    frames.append(g)
    delays.append(70)
  for i in range(3):
    g = blank(BG_ERR)
    draw_path(g, arm_a, RED)
    draw_path(g, arm_b, RED, upto=int(len(arm_b) * (i + 1) / 3))
    frames.append(g)
    delays.append(70)
  for i, shift in enumerate((1, -1, 0)):
    g = blank(BG_ERR)
    for x, y in arm_a + arm_b:
      put(g, x + shift, y, RED if i < 2 else RED_DIM)
    ring(g, RED_DIM, 0, len(RING))
    frames.append(g)
    delays.append(110)
  return frames, delays


def chilling_frames():
  """Idle: a slow pulse travelling round the ring, nothing in the middle.

  Deliberately the quietest face -- an empty centre is what makes the busy
  states read as busy. The travelling dot says "on and waiting" where a dark
  panel would just say "off".
  """
  frames, delays = [], []
  count = 12
  for i in range(count):
    g = blank(BG_IDLE)
    ring_gradient(g, head=i * 5, length=6, bright=(70, 110, 150), dim=(18, 30, 46))
    glow = 30 + int(25 * (1 + math.sin(2 * math.pi * i / count)))
    rect(g, 7, 7, 8, 8, (glow, glow + 15, glow + 30))
    frames.append(g)
    delays.append(220)
  return frames, delays


def screensaver_frames():
  """A drifting starfield for long idles: uses the whole panel, costs almost no
  light, and never looks like a status."""
  frames, delays = [], []
  stars = [((i * 7) % SIZE, (i * 11) % SIZE, i % 3) for i in range(18)]
  for i in range(16):
    g = blank((0, 0, 0))
    for sx, sy, speed in stars:
      y = (sy + i * (speed + 1) // 2) % SIZE
      shade = 255 - speed * 70
      put(g, sx, y, (shade - 90, shade - 50, shade))
    frames.append(g)
    delays.append(200)
  return frames, delays


def off_frames():
  return [blank((0, 0, 0))], [500]


FACES = {
  "thinking": (thinking_frames, "three dots filling, comet on the ring"),
  "working": (working_frames, "ring fills like a progress bar, core pulses"),
  "alerting": (alerting_frames, "exclamation on amber, ring breathing"),
  "alerting2": (alerting2_frames, "same mark hotter, ring strobing, bar jolting"),
  "alerting3": (alerting3_frames, "full-field strobe, mark knocked out"),
  "compacting": (compacting_frames, "columns squeezing inward"),
  "success": (success_frames, "tick draws itself, then a ring flourish"),
  "error": (error_frames, "cross draws arm by arm, then the panel flinches"),
  "chilling": (chilling_frames, "quiet pulse round the ring, empty centre"),
  "screensaver": (screensaver_frames, "drifting starfield for long idles"),
  "off": (off_frames, "blank"),
}


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

  png = (b"\x89PNG\r\n\x1a\n"
         + chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 2, 0, 0, 0))
         + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
  with open(path, "wb") as handle:
    handle.write(png)


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--preview", action="store_true")
  parser.add_argument("--out", default=os.path.dirname(os.path.abspath(__file__)))
  args = parser.parse_args()
  for name, (builder, doc) in FACES.items():
    frames, delays = builder()
    distinct = len({tuple(tuple(r) for r in f) for f in frames})
    indexed, palette = index_frames(frames)
    size = write_gif(os.path.join(args.out, f"{name}.gif"), indexed, palette, delays)
    write_png(os.path.join(args.out, f"{name}.png"), frames[0])
    warn = "" if distinct == len(frames) else f"   <-- only {distinct} distinct"
    print(f"{name:12s} {len(frames):2d} frames {len(palette):2d} colours "
          f"{size:5d}B  {doc}{warn}")
    if args.preview:
      big = [scale(f, 20) for f in indexed]
      write_gif(os.path.join(args.out, f"{name}_preview.gif"), big, palette, delays)
  return 0


if __name__ == "__main__":
  sys.exit(main())
