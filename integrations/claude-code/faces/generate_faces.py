#!/usr/bin/env python3
"""Generate the animated 16x16 status faces shown on the Ditoo Pro.

The character is Claude's mascot -- the stocky four-legged fellow from the
marketing site, who is built entirely out of rectangles and therefore takes to
a 256-LED panel better than almost anything else would. He keeps his own colour
in all three states; what changes is what he is DOING:

    thinking  following a little orbit of ideas
    working   hammering on a tiny cyan keyboard
    alerting  jumping under a pulsing exclamation mark
    success   doing a confetti stomp
    error     slumping with X eyes and a glitch spark
    chilling  nursing a tiny steaming mug

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
from mascot import BODY, SIZE, draw
from gifwriter import write_gif

# Near-black backgrounds keep the mascot brighter than its props on the LEDs.
# The body remains the source #DD775B in every state; meaning comes from pose,
# not from repainting the character.
BG_CHILL = (1, 12, 12)
BG_THINK = (7, 8, 24)
BG_WORK = (0, 8, 18)
BG_ALERT_HOT = (88, 7, 0)
BG_ALERT_COOL = (28, 0, 1)
BG_SUCCESS = (0, 18, 12)
BG_ERROR = (24, 0, 8)

INK = (17, 14, 18)
CODE_DARK = (26, 76, 129)
CODE = (53, 211, 235)
CODE_LIGHT = (151, 239, 248)
AMBER = (248, 181, 65)
CREAM = (255, 230, 178)
MINT = (72, 224, 158)
HOT = (255, 70, 72)
PINK = (255, 98, 150)


def pixels(grid, points, colour):
  for x, y in points:
    mascot.px(grid, x, y, colour)


def thinking_frames():
  """Prompt received: Claude watches three ideas orbit and taps his chin."""
  orbit = ((2, 2), (5, 0), (10, 0), (13, 2), (14, 5), (1, 5))
  gaze = (-1, -1, 0, 1, 1, 0, -1, 0)
  frames = []
  for i in range(8):
    grid = draw(
      BG_THINK, body_y=4, body_h=6, gaze=gaze[i],
      blink=i == 6, hand_l=1, hand_r=None
    )
    # A bent arm reaching the face is a stronger silhouette than a side hand.
    pixels(grid, ((15, 8), (14, 8), (13, 7)), BODY)
    for offset in (0, 2, 4):
      point = orbit[(i + offset) % len(orbit)]
      mascot.px(grid, point[0], point[1], CREAM if offset == 0 else AMBER)
    frames.append(grid)
  return frames, [170, 170, 170, 240, 170, 170, 120, 240]


def chilling_frames():
  """Idle: slow breathing, a curious glance, and a tiny steaming mug."""
  bob =   [0, 0, 1, 1, 0, 0, 0, 0, 0, 0]
  gaze =  [0, 0, -1, -1, 0, 1, 1, 0, 0, 0]
  blink = [False, False, False, False, False, False, False, True, False, False]
  steam = (
    ((14, 9), (15, 8), (14, 7)),
    ((15, 9), (14, 8), (14, 7)),
    ((14, 9), (14, 8), (15, 7)),
    ((15, 9), (15, 8), (14, 7)),
  )
  frames = []
  for i in range(10):
    grid = draw(
      BG_CHILL, body_y=4 + bob[i], body_h=6, gaze=gaze[i], blink=blink[i],
      hand_l=bob[i], hand_r=None, legs=(0, 0, 0, -2)
    )
    # Three-pixel mug with a dark rim and a one-pixel handle. It hides the
    # fourth foot, as though Claude is hugging it close to the body.
    mascot.rect(grid, 12, 10 + bob[i], 14, 13 + bob[i], INK)
    mascot.rect(grid, 13, 11 + bob[i], 14, 12 + bob[i], CREAM)
    pixels(grid, ((15, 11 + bob[i]), (15, 12 + bob[i])), INK)
    mascot.px(grid, 12, 11 + bob[i], BODY)
    pixels(grid, steam[i % len(steam)], CREAM)
    frames.append(grid)
  return frames, [260] * 10


def working_frames():
  """Busy: four feet brace while both hands hammer a tiny keyboard."""
  stride = [(1, -1, 1, -1), (0, 0, 0, 0), (-1, 1, -1, 1), (0, 0, 0, 0)]
  bob = [0, 0, 1, 0, 0, 1, 0, 0]
  gaze = [-1, 0, 1, 0, -1, 0, 1, 0]
  key_patterns = (
    ((4, 13), (7, 13), (10, 13)),
    ((5, 13), (8, 13), (11, 13)),
  )
  sparks = (
    ((0, 2), (1, 5), (14, 1)),
    ((1, 1), (0, 4), (15, 3)),
    ((0, 3), (1, 6), (14, 2)),
    ((1, 2), (0, 5), (15, 1)),
  )
  frames = []
  for i in range(8):
    beat = i % 4
    grid = draw(
      BG_WORK, body_y=2 + bob[i], body_h=6, legs=stride[beat],
      hand_l=None, hand_r=None, gaze=gaze[i]
    )
    # Keyboard stays planted while Claude bobs above it. The hand phase is
    # intentionally offset from the leg phase so the cycle does not flatten.
    mascot.rect(grid, 3, 12, 12, 14, CODE_DARK)
    mascot.rect(grid, 4, 12, 11, 12, CODE)
    pixels(grid, key_patterns[i % 2], CODE_LIGHT)
    left_x = 4 + (i % 2)
    right_x = 10 + ((i + 1) % 2)
    mascot.rect(grid, left_x, 10 + bob[i], left_x + 1, 11 + bob[i], BODY)
    mascot.rect(grid, right_x, 10 + bob[i], right_x + 1, 11 + bob[i], BODY)
    pixels(grid, sparks[beat], CODE if i % 2 else CODE_LIGHT)
    frames.append(grid)
  return frames, [105] * 8


def alerting_frames():
  """Blocked on you: a weighted hop under a pulsing exclamation mark.

  Crouch, launch, hang, fall, land heavy, recover -- the squash at each end is
  what gives the hop any weight at all in six frames.
  """
  # body_y, squash, legs lifted, left hand, right hand, background hot
  poses = [
    (5, 1, (0, 0, 0, 0),         1,  1, False),   # crouch
    (4, 0, (-1, -1, -1, -1),    -2, -1, True),    # launch
    (3, 0, (-1, -1, -1, -1),    -3, -2, True),    # hang
    (4, 0, (-1, -1, -1, -1),    -1, -3, True),    # fall, other hand waves
    (5, 1, (0, 0, 0, 0),         2,  1, False),   # heavy landing
    (4, 0, (0, 0, 0, 0),         0,  0, False),   # recover
  ]
  frames = []
  for i, (body_y, squash, legs, hand_l, hand_r, hot) in enumerate(poses):
    grid = draw(
      BG_ALERT_HOT if hot else BG_ALERT_COOL,
      body_y=body_y, body_h=6, squash=squash, legs=legs,
      hand_l=hand_l, hand_r=hand_r, gaze=0
    )
    marker = CREAM if i in (1, 2, 3) else AMBER
    mascot.rect(grid, 7, 0, 8, 1, marker)
    mascot.rect(grid, 7, 3, 8, 3, marker)
    frames.append(grid)
  return frames, [140, 90, 190, 100, 160, 180]


def success_frames():
  """Finished: the original mascot's stomp translated into confetti pixels."""
  poses = (
    (5, 1, (0, 0, 0, 0),  1,  1, "open"),
    (4, 0, (-1, 0, 0, -1), -2, -2, "happy"),
    (3, 0, (-1, -1, -1, -1), -3, -3, "happy"),
    (4, 0, (1, -1, 0, -1), -1, -2, "happy"),
    (5, 1, (0, 0, 0, 0),  2,  1, "open"),
    (4, 0, (-1, 0, -1, 0), -2, -2, "happy"),
    (3, 0, (-1, -1, -1, -1), -3, -3, "happy"),
    (4, 0, (-1, 1, -1, 0), -2, -1, "happy"),
  )
  colours = (MINT, AMBER, CODE, CREAM)
  seeds = ((0, 1), (3, 0), (6, 2), (9, 0), (12, 1), (15, 3))
  frames = []
  for i, (body_y, squash, legs, hand_l, hand_r, expression) in enumerate(poses):
    grid = draw(
      BG_SUCCESS, body_y=body_y, body_h=6, squash=squash, legs=legs,
      hand_l=hand_l, hand_r=hand_r, expression=expression
    )
    for j, (x, y) in enumerate(seeds):
      fall = (y + i // 2 + (j % 2)) % 5
      mascot.px(grid, x, fall, colours[(i + j) % len(colours)])
    # Impact sparks alternate between the left and right stomp.
    impact_x = (2, 3, 4) if i < 4 else (11, 12, 13)
    if i in (0, 4):
      pixels(grid, ((impact_x[0], 14), (impact_x[1], 15), (impact_x[2], 14)), AMBER)
    frames.append(grid)
  return frames, [130, 95, 170, 105, 140, 95, 170, 150]


def error_frames():
  """Failed: Claude slumps, flashes X eyes, and sheds a tiny glitch spark."""
  bob = (0, 0, 1, 1, 0, 0)
  glitches = (
    ((14, 1), (13, 2), (15, 3)),
    ((13, 0), (14, 1), (13, 3)),
    ((15, 1), (14, 2), (15, 4)),
  )
  frames = []
  for i in range(6):
    grid = draw(
      BG_ERROR, body_y=4 + bob[i], body_h=6, squash=1 if i in (2, 3) else 0,
      legs=(0, -1, 0, -1), hand_l=2, hand_r=1,
      expression="x"
    )
    pixels(grid, glitches[i % len(glitches)], HOT if i % 2 == 0 else PINK)
    # A one-row colour tear gives the rigid rectangle a convincing glitch.
    tear_y = 8 + (i % 2)
    mascot.rect(grid, 3 + (i % 2), tear_y, 5 + (i % 2), tear_y, HOT)
    frames.append(grid)
  return frames, [180, 120, 220, 120, 180, 260]


def off_frames():
  black = (0, 0, 0)
  return [[[black] * SIZE for _ in range(SIZE)]], [500]


FACES = {
  "thinking": (thinking_frames, "prompt received -- orbiting ideas"),
  "working": (working_frames, "busy -- hammering a tiny keyboard"),
  "alerting": (alerting_frames, "blocked on you -- jumping under an exclamation"),
  "success": (success_frames, "finished -- confetti stomp"),
  "error": (error_frames, "failed -- X eyes and a glitch spark"),
  "chilling": (chilling_frames, "idle -- breathing with a steaming mug"),
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
  height = len(frame)
  width = len(frame[0])
  raw = b""
  for row in frame:
    raw += b"\x00" + b"".join(bytes(c) for c in row)

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


CHARS = {
  mascot.BODY: "#", mascot.BODY_DARK: "+", mascot.BODY_LIGHT: "*",
  mascot.EYE: "o", mascot.EYE_SHINE: "@",
  CODE_DARK: "=", CODE: "%", CODE_LIGHT: "%", AMBER: "!", CREAM: "!",
  MINT: "!", HOT: "!", PINK: "!", INK: "+",
}


def ascii_preview(frame):
  counts = {}
  for row in frame:
    for colour in row:
      counts[colour] = counts.get(colour, 0) + 1
  bg = max(counts, key=counts.get)
  return ["".join("." if c == bg else CHARS.get(c, "?") for c in row) for row in frame]


def validate_frames(name, frames, delays):
  if not frames:
    raise ValueError(f"{name}: no frames")
  if len(frames) != len(delays):
    raise ValueError(f"{name}: {len(frames)} frames but {len(delays)} delays")
  for number, frame in enumerate(frames):
    if len(frame) != SIZE or any(len(row) != SIZE for row in frame):
      raise ValueError(f"{name}: frame {number} is not {SIZE}x{SIZE}")
    for row in frame:
      for colour in row:
        if len(colour) != 3 or any(not 0 <= channel <= 255 for channel in colour):
          raise ValueError(f"{name}: invalid RGB value {colour!r}")
  if any(delay <= 0 for delay in delays):
    raise ValueError(f"{name}: frame delays must be positive")


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--preview", action="store_true",
                      help="also write 320x320 preview GIFs")
  parser.add_argument("--out", default=os.path.dirname(os.path.abspath(__file__)))
  args = parser.parse_args()

  for name, (builder, doc) in FACES.items():
    frames, delays = builder()
    validate_frames(name, frames, delays)
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
      preview_png = os.path.join(args.out, f"{name}_preview.png")
      write_png(preview_png, scale(frames[0], 20))
      print(f"    -> {preview_png}")
    print()
  return 0


if __name__ == "__main__":
  sys.exit(main())
