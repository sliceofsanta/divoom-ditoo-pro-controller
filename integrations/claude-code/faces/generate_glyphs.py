#!/usr/bin/env python3
"""Generate the triage and presence glyphs.

These are ADDITIONS, not replacements: the nine hand-drawn status faces are
untouched. Written separately so re-running this can never overwrite them.

Why they exist. Every interruption used to look identical, so the panel could
say "Claude needs you" but not whether that meant one keystroke or twenty
minutes of reading. These split it three ways, and add two signals that face
outward at the room rather than inward at you.

    alert-question    a question -- needs thought
    alert-permission  a permission prompt -- one keystroke, go press it
    alert-plan        a plan waiting for review -- sit down and read
    meeting           you are in a meeting (for whoever is walking over)
    busy              heads-down, Focus is on

Each owns a background colour so it is separable across a room, and carries a
bold symbol so it is unambiguous up close. That split -- colour at distance,
shape near -- is what has survived every previous round of this artwork.
"""

import argparse
import os
import struct
import sys
import zlib

from glyphs import SIZE, blank, put, rect, RING, ring
from gifwriter import write_gif

# Grounds. Deliberately far apart in hue: telling the three alerts apart at a
# glance is the entire point of splitting them.
BG_QUESTION = (44, 30, 0)
BG_PERMISSION = (48, 16, 0)
BG_PLAN = (26, 12, 44)
BG_MEETING = (0, 24, 30)
BG_BUSY = (30, 4, 8)

AMBER = (255, 200, 70)
ORANGE = (255, 130, 40)
VIOLET = (190, 140, 255)
TEAL = (90, 210, 225)
RED = (255, 80, 76)
CREAM = (255, 240, 214)
DIM = (70, 60, 50)


def question_symbol(grid, colour):
  """A bold question mark: hook, stem, and a detached dot."""
  rect(grid, 5, 2, 10, 3, colour)      # top bar
  rect(grid, 9, 4, 10, 5, colour)      # right shoulder
  rect(grid, 7, 6, 10, 7, colour)      # curve into the stem
  rect(grid, 7, 8, 8, 9, colour)       # stem
  rect(grid, 7, 12, 8, 13, colour)     # the dot


def padlock_symbol(grid, colour, shackle):
  """A padlock. Reads as "permission" far better than a key, whose teeth
  disappear at this size."""
  rect(grid, 6, 2, 9, 3, shackle)      # shackle top
  rect(grid, 5, 4, 6, 5, shackle)      # shackle sides
  rect(grid, 9, 4, 10, 5, shackle)
  rect(grid, 4, 6, 11, 12, colour)     # body
  rect(grid, 7, 8, 8, 10, shackle)     # keyhole


def document_symbol(grid, colour, ink):
  """A page with lines of text: something to read, not something to press."""
  rect(grid, 4, 2, 11, 13, colour)
  for y in (4, 6, 8, 10):
    rect(grid, 6, y, 9, y, ink)
  rect(grid, 6, 12, 8, 12, ink)        # a short last line, so it reads as text


def calendar_symbol(grid, colour, ink):
  """A calendar: two binding rings and a grid of days."""
  rect(grid, 5, 1, 5, 2, ink)
  rect(grid, 10, 1, 10, 2, ink)
  rect(grid, 3, 3, 12, 13, colour)
  rect(grid, 3, 3, 12, 4, ink)         # header band
  for y in (7, 10):
    for x in (5, 8, 11):
      put(grid, x, y, ink)


def busy_bar(grid, colour):
  """A single heavy bar. The universal "no" -- and the only one of these that
  has to read from the far side of a room to someone who is not you."""
  rect(grid, 2, 7, 13, 9, colour)


def pulsing(build, count, delay, bg, accent, dim):
  """Common shape for all of these: the symbol holds still while the ring
  breathes around it. Motion says "live"; a still symbol stays readable.

  The symbol is always the BRIGHTEST thing and the ring sits a step behind it
  in the accent hue. Drawn in the same colour the two merge into one blob and
  the symbol stops being a symbol -- which is exactly what the first cut did.
  """
  frames, delays = [], []
  for i in range(count):
    grid = blank(bg)
    span = 8 + (i % 4) * 9
    ring(grid, dim, 0, len(RING))
    ring(grid, accent, i * 7, span)
    build(grid)
    frames.append(grid)
    delays.append(delay)
  return frames, delays


def alert_question():
  return pulsing(lambda g: question_symbol(g, CREAM),
                 8, 150, BG_QUESTION, AMBER, (72, 56, 12))


def alert_permission():
  # Cream lock on an orange ring: the shackle and keyhole are knocked out in
  # the ground colour so they stay visible against the bright body.
  return pulsing(lambda g: padlock_symbol(g, CREAM, BG_PERMISSION),
                 8, 130, BG_PERMISSION, ORANGE, (78, 34, 8))


def alert_plan():
  return pulsing(lambda g: document_symbol(g, CREAM, BG_PLAN),
                 8, 170, BG_PLAN, VIOLET, (58, 36, 84))


def meeting():
  return pulsing(lambda g: calendar_symbol(g, CREAM, BG_MEETING),
                 6, 260, BG_MEETING, TEAL, (14, 58, 66))


def busy():
  """No ring: heads-down should be the calmest thing on the desk, not another
  thing flickering at you."""
  frames, delays = [], []
  # An explicit ramp, not a sine. A sine sampled over six steps produces equal
  # values on ADJACENT frames (sin 60 == sin 120), which is a visible stall
  # however smooth the curve looks on paper. Up quickly, down slowly, so it
  # reads as breathing rather than blinking.
  for level in (0.0, 0.45, 0.9, 1.0, 0.7, 0.3):
    shade = (
      int(120 + 135 * level),
      int(28 + 58 * level),
      int(26 + 56 * level)
    )
    grid = blank(BG_BUSY)
    busy_bar(grid, shade)
    frames.append(grid)
    delays.append(600)
  return frames, delays


GLYPHS = {
  "alert-question": (alert_question, "a question -- needs thought"),
  "alert-permission": (alert_permission, "permission prompt -- one keystroke"),
  "alert-plan": (alert_plan, "a plan to review -- sit down and read"),
  "meeting": (meeting, "you are in a meeting"),
  "busy": (busy, "heads-down, do not interrupt"),
}


def index_frames(frames):
  palette, lookup, indexed = [], {}, []
  for frame in frames:
    rows = []
    for row in frame:
      out = []
      for colour in row:
        if colour not in lookup:
          lookup[colour] = len(palette)
          palette.append(colour)
        out.append(lookup[colour])
      rows.append(out)
    indexed.append(rows)
  return indexed, palette


def scale(frame, factor):
  out = []
  for row in frame:
    big = []
    for v in row:
      big.extend([v] * factor)
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
  ok = True
  for name, (builder, doc) in GLYPHS.items():
    frames, delays = builder()
    key = [tuple(tuple(r) for r in f) for f in frames]
    distinct = len(set(key))
    # The defect that matters is an ADJACENT repeat, which reads as a stall.
    # A symmetric breath legitimately retraces its path on the way back, so
    # "every frame unique" is the wrong rule for anything that eases in and out.
    stalls = sum(1 for a, b in zip(key, key[1:] + key[:1]) if a == b)
    indexed, palette = index_frames(frames)
    size = write_gif(os.path.join(args.out, f"{name}.gif"), indexed, palette, delays)
    write_png(os.path.join(args.out, f"{name}.png"), frames[0])
    warn = "" if stalls == 0 else f"   <-- {stalls} frame(s) repeat back to back"
    if warn:
      ok = False
    print(f"{name:18s} {len(frames):2d} frames {len(palette):2d} colours "
          f"{size:5d}B  {doc}{warn}")
    if args.preview:
      write_gif(os.path.join(args.out, f"{name}_preview.gif"),
                [scale(f, 20) for f in indexed], palette, delays)
  return 0 if ok else 1


if __name__ == "__main__":
  sys.exit(main())
