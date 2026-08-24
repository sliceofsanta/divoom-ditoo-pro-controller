#!/usr/bin/env python3
"""Generate the animated 16x16 status faces shown on the Ditoo Pro.

Stdlib only -- the GIF encoder lives in gifwriter.py -- so this runs anywhere
without pip installs.

    python3 generate_faces.py            # write the GIFs (+ PNG fallbacks)
    python3 generate_faces.py --preview  # also write 320x320 preview GIFs

Each face is built from components (eyes, mouth, extras) rather than hand-drawn
grids, so retiming or restyling an animation means editing a few numbers.

16x16 is a severe canvas: colour does most of the work of telling states apart
across a room, and motion does the rest. Shapes only resolve up close.
"""

import argparse
import os
import struct
import sys
import zlib

from gifwriter import write_gif

SIZE = 16

# Eye slots: two 4-wide columns with a 2px gap.
EYE_L = 3
EYE_R = 9


# --- drawing helpers -------------------------------------------------------

def blank(bg):
  return [[bg] * SIZE for _ in range(SIZE)]


def rect(px, x, y, w, h, colour):
  for yy in range(y, y + h):
    if not 0 <= yy < SIZE:
      continue
    for xx in range(x, x + w):
      if 0 <= xx < SIZE:
        px[yy][xx] = colour


def dot(px, x, y, colour):
  if 0 <= x < SIZE and 0 <= y < SIZE:
    px[y][x] = colour


def eye_open(px, x, y, colour, gaze=0):
  """Open eye, 2px pupil that can look left (-1), centre (0) or right (+1)."""
  rect(px, x + 1 + gaze, y, 2, 3, colour)


def eye_wide(px, x, y, white, pupil):
  """Startled eye: 4x4 white with a 2x2 pupil."""
  rect(px, x, y, 4, 4, white)
  rect(px, x + 1, y + 1, 2, 2, pupil)


def eye_arc(px, x, y, colour):
  """Content, closed eye -- a small ^ arc."""
  dot(px, x + 1, y, colour)
  dot(px, x + 2, y, colour)
  dot(px, x, y + 1, colour)
  dot(px, x + 3, y + 1, colour)


def eye_line(px, x, y, colour):
  """Fully shut eye."""
  rect(px, x, y, 4, 1, colour)


def mouth_smile(px, y, colour):
  dot(px, 4, y, colour)
  dot(px, 11, y, colour)
  rect(px, 5, y + 1, 6, 1, colour)


def mouth_flat(px, y, colour):
  rect(px, 6, y, 4, 1, colour)


def mouth_open(px, y, colour):
  rect(px, 6, y, 4, 1, colour)
  dot(px, 5, y + 1, colour)
  dot(px, 10, y + 1, colour)
  rect(px, 6, y + 2, 4, 1, colour)


# --- the faces -------------------------------------------------------------

def chilling_frames():
  """Idle: resting eyes, soft smile, a slow breathing bob and one peek."""
  bg = (0, 10, 7)
  fg = (54, 200, 122)
  dim = (24, 92, 58)

  # Breathing: 1px down through the middle of the loop, then back up.
  bob = [0, 0, 1, 1, 1, 0, 0, 0]
  frames = []
  for i, offset in enumerate(bob):
    px = blank(bg)
    eye_y = 6 + offset
    if i == 6:
      # A brief peek, so the face reads as resting rather than switched off.
      eye_open(px, EYE_L, eye_y - 1, fg)
      eye_open(px, EYE_R, eye_y - 1, fg)
    else:
      eye_arc(px, EYE_L, eye_y, fg)
      eye_arc(px, EYE_R, eye_y, fg)
    mouth_smile(px, 10 + offset, fg)
    # A dim floor line gives the bob something to move against.
    rect(px, 4, 14, 8, 1, dim)
    frames.append(px)
  return frames, [220] * len(frames)


def working_frames():
  """Busy: eyes scanning back and forth over a filling progress bar."""
  bg = (0, 9, 16)
  fg = (0, 190, 226)
  bar = (150, 240, 255)
  track = (0, 58, 78)

  gazes = [0, -1, -1, 0, 1, 1, 0, 0]
  frames = []
  for i, gaze in enumerate(gazes):
    px = blank(bg)
    eye_open(px, EYE_L, 5, fg, gaze)
    eye_open(px, EYE_R, 5, fg, gaze)
    mouth_flat(px, 10, fg)
    # Progress bar sweeps left to right and restarts -- motion, not real progress.
    rect(px, 2, 13, 12, 1, track)
    filled = int(round(12 * (i + 1) / len(gazes)))
    if filled:
      rect(px, 2, 13, filled, 1, bar)
    frames.append(px)
  return frames, [130] * len(frames)


def alerting_frames():
  """Blocked on you: wide eyes, open mouth, urgent pulse with flashing bars."""
  bg_bright = (34, 0, 0)
  bg_dim = (12, 0, 0)
  red = (255, 58, 48)
  red_dim = (150, 30, 26)
  white = (255, 236, 180)
  pupil = (60, 0, 0)

  frames = []
  for i in range(6):
    hot = i % 2 == 0
    bg = bg_bright if hot else bg_dim
    face = red if hot else red_dim
    px = blank(bg)
    eye_wide(px, EYE_L, 4, white if hot else red, pupil)
    eye_wide(px, EYE_R, 4, white if hot else red, pupil)
    mouth_open(px, 10, face)
    if hot:
      # Exclamation bars in the margins, flashing with the pulse.
      rect(px, 0, 3, 1, 5, face)
      dot(px, 0, 9, face)
      rect(px, 15, 3, 1, 5, face)
      dot(px, 15, 9, face)
    frames.append(px)
  return frames, [110] * len(frames)


def off_frames():
  black = (0, 0, 0)
  return [blank(black)], [500]


FACES = {
  "chilling": (chilling_frames, "idle -- resting eyes, soft smile, breathing"),
  "working": (working_frames, "busy -- scanning eyes over a filling bar"),
  "alerting": (alerting_frames, "blocked on you -- pulsing red, wide eyes"),
  "off": (off_frames, "blank display"),
}


# --- output ----------------------------------------------------------------

def index_frames(frames):
  """Colour grids -> (indexed frames, palette)."""
  palette = []
  lookup = {}
  indexed = []
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
  """First frame as a PNG, so the display still works without GIF support."""
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


def ascii_preview(frame, bg):
  lines = []
  for row in frame:
    lines.append("".join("." if c == bg else "#" for c in row))
  return lines


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
    for line in ascii_preview(frames[0], frames[0][0][0]):
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
