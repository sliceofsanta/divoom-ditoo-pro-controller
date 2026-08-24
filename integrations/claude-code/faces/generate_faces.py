#!/usr/bin/env python3
"""Generate the animated 16x16 status faces shown on the Ditoo Pro.

The character is Claude's mascot -- the stocky four-legged fellow from the
marketing site, who is built entirely out of rectangles and therefore takes to
a 256-LED panel better than almost anything else would. He keeps his own colour
in all three states; what changes is what he is DOING:

    working   marching on the spot, hands swinging
    alerting  jumping up and down with both hands over his head
    chilling  idling -- breathing, looking about, blinking

Stdlib only (see mascot.py for the sprite and gifwriter.py for the encoder), so
this runs anywhere without pip installs.

    python3 generate_faces.py            # write the GIFs (+ PNG fallbacks)
    python3 generate_faces.py --preview  # also write 320x320 preview GIFs
"""

import argparse
import os
import struct
import sys
import zlib

import mascot
from mascot import SIZE, draw
from gifwriter import write_gif

# Backgrounds: dark, so the mascot stays the brightest thing on the panel.
BG_CHILL = (0, 14, 9)
BG_WORK = (0, 9, 20)
BG_ALERT_HOT = (104, 6, 0)
BG_ALERT_COOL = (26, 0, 0)

CHILL_BODY = (150, 82, 62)
CHILL_DARK = (104, 54, 40)
CHILL_LIGHT = (186, 110, 86)


def chilling_frames():
  """Idle: breathing, glancing about, and a blink -- he is waiting, not off."""
  bob   = [0, 0, 1, 1, 0, 0, 0, 0]
  gaze  = [0, 0, 0, -1, -1, 0, 1, 0]
  blink = [False, False, False, False, False, True, False, False]
  frames = []
  for i in range(8):
    frames.append(draw(
      BG_CHILL,
      body_y=3 + bob[i], gaze=gaze[i], blink=blink[i],
      hand_l=bob[i], hand_r=bob[i],
      body=CHILL_BODY, dark=CHILL_DARK, light=CHILL_LIGHT
    ))
  return frames, [250] * 8


def working_frames():
  """Busy: marching on the spot, glancing about as he goes.

  The legs run a four-beat contact-pass-contact-pass cycle and the hands swing
  opposite them, which is what sells it as a stride rather than a wobble. The
  gaze runs on a different period on purpose: put both on the same beat and the
  two motions lock together and the whole thing reads as one flat repeat.
  """
  stride = [(1, -1, 1, -1), (0, 0, 0, 0), (-1, 1, -1, 1), (0, 0, 0, 0)]
  swing = [-1, 0, 1, 0]
  gaze = [0, 0, 1, 1, 0, 0, -1, -1]
  frames = []
  for i in range(8):
    beat = i % 4
    frames.append(draw(
      BG_WORK,
      body_y=3 + (i % 2),
      legs=stride[beat],
      hand_l=swing[beat],
      hand_r=-swing[beat],
      gaze=gaze[i]
    ))
  return frames, [120] * 8


def alerting_frames():
  """Blocked on you: jumping up and down with both hands over his head.

  Crouch, launch, hang, fall, land heavy, recover -- the squash at each end is
  what gives the hop any weight at all in six frames.
  """
  # body_y, squash, legs lifted, hand offset, background hot
  poses = [
    (4, 1, (0, 0, 0, 0),         1, False),   # crouch
    (2, 0, (-1, -1, -1, -1),    -1, True),    # launch
    (1, 0, (-1, -1, -1, -1),    -2, True),    # hang at the top
    (2, 0, (-1, -1, -1, -1),    -1, True),    # falling
    (4, 1, (0, 0, 0, 0),         2, False),   # land heavy, hands flung down
    (3, 0, (0, 0, 0, 0),         0, False),   # recover
  ]
  frames = []
  for body_y, squash, legs, hand, hot in poses:
    frames.append(draw(
      BG_ALERT_HOT if hot else BG_ALERT_COOL,
      body_y=body_y, squash=squash, legs=legs,
      hand_l=hand, hand_r=hand, gaze=0
    ))
  return frames, [110] * len(poses)


def off_frames():
  black = (0, 0, 0)
  return [[[black] * SIZE for _ in range(SIZE)]], [500]


FACES = {
  "chilling": (chilling_frames, "idle -- breathing, looking about, blinking"),
  "working": (working_frames, "busy -- marching on the spot"),
  "alerting": (alerting_frames, "blocked on you -- jumping, hands overhead"),
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
  mascot.BODY: "#", mascot.BODY_DARK: "+", mascot.BODY_LIGHT: "*",
  mascot.EYE: "o", mascot.EYE_SHINE: "@",
  CHILL_BODY: "#", CHILL_DARK: "+", CHILL_LIGHT: "*",
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
