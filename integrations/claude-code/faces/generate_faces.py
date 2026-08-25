#!/usr/bin/env python3
"""Generate Claude's Workshop status animations for the Ditoo Pro.

The nine states form one construction story instead of nine unrelated icons:

    thinking    Claude studies a large cyan building blueprint
    compacting  loose materials are sorted into a tidy crate
    working     hard-hat Claude hammers beside a scaffold and rising wall
    alerting    the almost-finished workshop is waiting at its test switch
    success     the finished workshop lights up and Claude celebrates
    error       the test fails, the wall cracks, and Claude is stunned
    chilling    Claude sleeps beside the warm workshop after hours

Everything is drawn directly on the 16x16 grid. Large silhouettes, a consistent
left-to-right stage, and very little decoration keep the story readable on the
real LED matrix.

Stdlib only (see gifwriter.py for the encoder), so this runs anywhere without
pip installs.

    python3 generate_faces.py            # write the GIFs (+ PNG fallbacks)
    python3 generate_faces.py --preview  # also write 320x320 preview GIFs
"""

import argparse
import os
import struct
import sys
import zlib

import mascot
from mascot import SIZE
from gifwriter import write_gif


# A dark workshop makes the terracotta mascot and construction props read as
# solid silhouettes instead of dissolving into a multicolour pixel soup.
NIGHT = (7, 12, 30)
WALL = (14, 24, 48)
FLOOR_DARK = (47, 33, 38)
FLOOR = (91, 57, 48)
FLOOR_LIGHT = (151, 85, 58)
INK = (25, 17, 22)

BLUEPRINT = (21, 91, 177)
CYAN = (55, 224, 237)
CYAN_LIGHT = (190, 251, 255)
CREAM = (255, 224, 170)
WHITE = (255, 247, 222)

WOOD_DARK = (91, 50, 34)
WOOD = (181, 91, 47)
WOOD_LIGHT = (255, 155, 75)
BRICK = (205, 82, 55)
BRICK_LIGHT = (246, 137, 88)
STEEL = (126, 150, 171)
STEEL_LIGHT = (211, 229, 232)

SAFETY = (255, 194, 51)
GLOW = (255, 235, 103)
MINT = (72, 229, 154)
RED = (255, 66, 72)
RED_DARK = (122, 24, 42)
PINK = (255, 101, 151)


def pixels(grid, points, colour):
  for x, y in points:
    mascot.px(grid, x, y, colour)


def backdrop(grid, alarm=False, night=False):
  """The same floor and back wall anchor every scene."""
  if alarm:
    mascot.rect(grid, 0, 14, 15, 15, RED_DARK)
    pixels(grid, ((1, 15), (5, 15), (9, 15), (13, 15)), RED)
  else:
    mascot.rect(grid, 0, 14, 15, 15, FLOOR_DARK if night else FLOOR)
    mascot.rect(grid, 0, 14, 15, 14, FLOOR if night else FLOOR_LIGHT)
    pixels(grid, ((2, 15), (7, 15), (12, 15)), WOOD_DARK)


def claude_builder(grid, x=0, y=8, jump=0, step=0, gaze=1,
                   expression="open", blink=False, hardhat=True,
                   hand_l=0, hand_r=0):
  """Claude's readable seven-wide workshop sprite."""
  mascot.draw_player(
    grid, x, y, jump=jump, step=step, gaze=gaze, blink=blink,
    expression=expression, hand_l=hand_l, hand_r=hand_r,
    hat=SAFETY if hardhat else None,
  )


def blueprint(grid, pulse=False, scan=0):
  """An oversized cyan plan with an unmistakable house elevation."""
  border = CYAN_LIGHT if pulse else CYAN
  mascot.rect(grid, 8, 2, 15, 11, border)
  mascot.rect(grid, 9, 3, 14, 10, BLUEPRINT)

  # Roof, walls, door and baseline. The icon consumes the whole plan so it is
  # readable even after LED diffusion.
  pixels(grid, ((9, 7), (10, 6), (11, 5), (12, 4),
                (13, 5), (14, 6)), WHITE)
  mascot.rect(grid, 10, 7, 10, 9, WHITE)
  mascot.rect(grid, 14, 7, 14, 9, WHITE)
  mascot.rect(grid, 10, 9, 14, 9, WHITE)
  mascot.rect(grid, 12, 8, 12, 9, CYAN_LIGHT)
  mascot.px(grid, 9 + scan % 6, 10, CYAN_LIGHT)


def brick(grid, x, y, light=False):
  colour = BRICK_LIGHT if light else BRICK
  mascot.rect(grid, x, y, x + 2, y + 1, colour)
  mascot.px(grid, x + 1, y + 1, WOOD_DARK)


def crate(grid, fill=3):
  """Large slatted material crate on the right half of the stage."""
  mascot.rect(grid, 9, 9, 15, 13, WOOD_DARK)
  mascot.rect(grid, 10, 10, 14, 12, WOOD)
  mascot.rect(grid, 10, 11, 14, 11, WOOD_LIGHT)
  mascot.px(grid, 12, 10, WOOD_DARK)
  if fill >= 1:
    mascot.rect(grid, 10, 8, 12, 9, BRICK)
  if fill >= 2:
    mascot.rect(grid, 13, 7, 15, 8, BRICK_LIGHT)
  if fill >= 3:
    mascot.rect(grid, 9, 6, 13, 6, SAFETY)


def loose_materials(grid, phase):
  """One large item visibly travels into the crate on each loop."""
  positions = ((7, 3), (9, 3), (11, 4), (12, 6), (13, 8))
  x, y = positions[min(phase, len(positions) - 1)]
  brick(grid, x, y, light=phase % 2 == 0)
  # A static plank and steel roll make this read as materials, not treasure.
  mascot.rect(grid, 7, 12, 11, 12, SAFETY)
  pixels(grid, ((7, 9), (8, 8), (8, 10)), STEEL_LIGHT)


def scaffold(grid, hot=False):
  colour = GLOW if hot else SAFETY
  mascot.rect(grid, 8, 4, 8, 13, colour)
  mascot.rect(grid, 15, 4, 15, 13, colour)
  mascot.rect(grid, 8, 6, 15, 6, colour)
  mascot.rect(grid, 8, 10, 15, 10, colour)
  pixels(grid, ((9, 9), (10, 8), (11, 7),
                (12, 7), (13, 8), (14, 9)), WOOD_LIGHT)


def half_wall(grid, spark=False):
  """The stable, half-built workshop used during active work."""
  mascot.rect(grid, 10, 8, 14, 13, WOOD_DARK)
  mascot.rect(grid, 10, 9, 14, 13, BRICK)
  pixels(grid, ((11, 9), (13, 9), (10, 11), (12, 11), (14, 11),
                (11, 13), (13, 13)), BRICK_LIGHT)
  if spark:
    pixels(grid, ((9, 10), (10, 9), (10, 11), (11, 10)), GLOW)


def hammer(grid, down=False):
  """A huge hammer connected directly to Claude's raised hand."""
  if down:
    pixels(grid, ((6, 11), (7, 11), (8, 11), (9, 11)), WOOD_LIGHT)
    mascot.rect(grid, 10, 10, 10, 12, STEEL_LIGHT)
    mascot.px(grid, 11, 11, STEEL)
  else:
    pixels(grid, ((6, 11), (7, 10), (8, 9), (9, 8)), WOOD_LIGHT)
    mascot.rect(grid, 8, 7, 10, 8, STEEL_LIGHT)
    mascot.px(grid, 8, 8, STEEL)


def workshop(grid, glow=0, damaged=False, test_light=None):
  """The completed building, always in the same right-hand footprint."""
  roof = GLOW if glow >= 2 else (WOOD_LIGHT if glow else WOOD_DARK)
  wall = CREAM if glow >= 2 else (WOOD_LIGHT if glow else WOOD)

  # Chunky roof silhouette and chimney.
  mascot.rect(grid, 14, 2, 15, 5, WOOD_DARK)
  mascot.rect(grid, 11, 3, 12, 3, roof)
  mascot.rect(grid, 10, 4, 13, 4, roof)
  mascot.rect(grid, 9, 5, 14, 5, roof)
  mascot.rect(grid, 8, 6, 15, 6, roof)
  mascot.rect(grid, 9, 7, 14, 13, wall)

  # Two large windows and a dark door make the object read as a building.
  window = GLOW if glow else WALL
  mascot.rect(grid, 10, 8, 11, 9, window)
  mascot.rect(grid, 13, 8, 14, 9, window)
  mascot.rect(grid, 12, 11, 13, 13, INK)
  mascot.px(grid, 13, 12, GLOW if glow else STEEL)

  if test_light is not None:
    mascot.px(grid, 10, 8, test_light)
    mascot.px(grid, 13, 8, test_light)

  if damaged:
    # A thick red lightning crack cuts through the otherwise stable building.
    pixels(grid, ((12, 5), (11, 6), (12, 7), (11, 8),
                  (12, 9), (11, 10), (12, 11)), RED)
    mascot.rect(grid, 14, 3, 15, 5, NIGHT)
    mascot.px(grid, 9, 13, NIGHT)


def test_cable(grid, phase=0):
  colour = CYAN_LIGHT if phase % 2 == 0 else CYAN
  pixels(grid, ((6, 11), (7, 11), (7, 12), (8, 12), (8, 11)), colour)


def question_mark(grid, colour=SAFETY, double=False):
  """A five-pixel-tall question mark with a large detached dot."""
  pixels(grid, ((1, 2), (2, 1), (3, 1), (4, 2),
                (3, 3), (2, 4), (2, 6)), colour)
  if double:
    pixels(grid, ((5, 1), (6, 1), (7, 2), (6, 3), (6, 5)), colour)


def beacon(grid, level=1, flash=False):
  colour = RED if level >= 3 else (SAFETY if level == 1 else WOOD_LIGHT)
  mascot.rect(grid, 14, 0, 15, 1, colour if flash else RED_DARK)
  if flash:
    pixels(grid, ((12, 0), (13, 1), (15, 2)), colour)


def thinking_frames():
  """BLUEPRINT: Claude considers a large, pulsing building plan."""
  frames = []
  for i in range(8):
    grid = mascot.blank(NIGHT)
    backdrop(grid)
    blueprint(grid, pulse=i in (2, 3, 6), scan=i)
    claude_builder(grid, y=8, gaze=1, blink=i == 6,
                   hand_r=-1 if i % 4 < 2 else 0)
    mascot.px(grid, 7, 9 - (i % 2), CYAN_LIGHT)  # pointing fingertip
    frames.append(grid)
  return frames, [220, 220, 180, 260, 220, 220, 180, 300]


def compacting_frames():
  """MATERIAL SORT: loose supplies travel into one tidy crate."""
  frames = []
  for i in range(10):
    grid = mascot.blank(NIGHT)
    backdrop(grid)
    phase = i % 5
    crate(grid, fill=min(3, 1 + i // 3))
    loose_materials(grid, phase)
    claude_builder(grid, y=8, gaze=1, blink=i == 8,
                   hand_r=-1 if phase < 3 else 0, step=1 + i % 2)
    frames.append(grid)
  return frames, [130, 120, 120, 140, 200, 130, 120, 120, 140, 240]


def working_frames():
  """HAMMER TIME: the same wall stays visible while the hammer cycles."""
  frames = []
  for i in range(10):
    grid = mascot.blank(NIGHT)
    backdrop(grid)
    down = i % 4 in (2, 3)
    scaffold(grid, hot=i in (3, 7))
    half_wall(grid, spark=down and i % 2 == 0)
    claude_builder(grid, y=8, gaze=1, blink=i == 8,
                   hand_r=-1 if not down else 0, step=1 + i % 2)
    hammer(grid, down=down)
    if down:
      pixels(grid, ((9, 9), (9, 11), (11, 9)), GLOW)
    frames.append(grid)
  return frames, [110, 100, 90, 130, 110, 100, 90, 130, 110, 150]


def alert_scene(level):
  frames = []
  count = 8 if level < 3 else 6
  for i in range(count):
    alarm = level >= 3 and i % 2 == 0
    grid = mascot.blank(RED_DARK if alarm else NIGHT)
    backdrop(grid, alarm=alarm)
    light = (SAFETY, WOOD_LIGHT, RED)[level - 1]
    workshop(grid, glow=0, test_light=light if i % 2 == 0 else WALL)
    test_cable(grid, i)
    question_mark(grid, colour=WHITE if alarm else light, double=level >= 2)
    beacon(grid, level=level, flash=i % 2 == 0)
    jump = 1 if level == 3 and i % 2 else 0
    claude_builder(
      grid, y=8, jump=jump, gaze=1,
      expression="shock" if level == 3 else "open",
      hand_l=-2 if level >= 2 else -1,
      hand_r=-2 if level >= 1 else 0,
    )
    frames.append(grid)
  if level == 1:
    delays = [210, 210, 180, 240, 210, 210, 180, 280]
  elif level == 2:
    delays = [110, 100, 110, 100, 110, 100, 110, 140]
  else:
    delays = [80, 80, 80, 80, 80, 110]
  return frames, delays


def alerting_frames():
  """TEST WAIT: one question and a slow yellow test light."""
  return alert_scene(1)


def alerting2_frames():
  """STILL WAITING: two questions, both hands up, faster orange flashes."""
  return alert_scene(2)


def alerting3_frames():
  """SITE ALARM: red test failure strobe and rooftop siren."""
  return alert_scene(3)


def success_frames():
  """GRAND OPENING: the finished workshop turns on and Claude celebrates."""
  frames = []
  for i in range(12):
    grid = mascot.blank(NIGHT)
    backdrop(grid)
    glow = 2 if i % 4 in (1, 2) or i >= 8 else 1
    workshop(grid, glow=glow, test_light=MINT)
    jump = (0, 1, 2, 2, 1, 0)[i % 6]
    claude_builder(grid, y=8, jump=jump, gaze=1, expression="happy",
                   hand_l=-2, hand_r=-2, hardhat=i < 6)
    confetti = ((1, 1 + i % 3), (5, 2), (7, 4 + i % 2),
                (15, 8 + i % 3))
    pixels(grid, confetti, (CYAN, PINK, MINT, GLOW)[i % 4])
    frames.append(grid)
  return frames, [150, 130, 130, 170, 130, 220] * 2


def error_frames():
  """BUILD FAILED: a red crack, falling brick and smoke remain readable."""
  frames = []
  for i in range(10):
    flash = i in (1, 2, 6)
    grid = mascot.blank(RED_DARK if flash else NIGHT)
    backdrop(grid, alarm=flash)
    workshop(grid, damaged=True, test_light=RED)
    claude_builder(grid, y=8, gaze=1, expression="x", hardhat=i < 5,
                   hand_l=-1 if flash else 0, hand_r=-1 if flash else 0)
    # Falling brick and three large smoke puffs.
    brick(grid, 13 - min(i // 3, 3), 4 + min(i // 2, 5), light=flash)
    smoke_y = 1 + (i % 4)
    pixels(grid, ((14, smoke_y), (13, smoke_y + 1),
                  (15, smoke_y + 1)), STEEL_LIGHT if flash else STEEL)
    frames.append(grid)
  return frames, [170, 120, 120, 180, 160, 220, 120, 170, 200, 300]


def chilling_frames():
  """AFTER HOURS: one warm window, chimney smoke and sleeping Claude."""
  frames = []
  for i in range(12):
    grid = mascot.blank(NIGHT)
    backdrop(grid, night=True)
    # Moon and a single living window keep the idle scene gently animated.
    pixels(grid, ((1, 1), (2, 1), (1, 2), (2, 2)), CREAM)
    mascot.px(grid, 2, 1, NIGHT)
    workshop(grid, glow=1 if i % 6 in (3, 4) else 0)
    mascot.rect(grid, 10, 8, 11, 9, GLOW)
    mascot.rect(grid, 13, 8, 14, 9, WALL)
    claude_builder(grid, y=9, gaze=0, expression="sleep", hardhat=False,
                   hand_l=1, hand_r=1)
    if i % 6 < 4:
      z = 5 - i % 3
      pixels(grid, ((5, z), (6, z), (6, z + 1),
                    (5, z + 2), (6, z + 2)), CYAN)
    smoke_y = 1 - (i % 3)
    pixels(grid, ((14, smoke_y), (13, smoke_y + 1)), STEEL)
    frames.append(grid)
  return frames, [240] * 12


def off_frames():
  black = (0, 0, 0)
  return [[[black] * SIZE for _ in range(SIZE)]], [500]


FACES = {
  "thinking": (thinking_frames, "BLUEPRINT -- Claude studies the building plan"),
  "working": (working_frames, "HAMMER TIME -- scaffold, wall, hammer and sparks"),
  "alerting": (alerting_frames, "TEST WAIT -- one question and a slow test light"),
  "alerting2": (alerting2_frames, "STILL WAITING -- two questions and faster flashes"),
  "alerting3": (alerting3_frames, "SITE ALARM -- rooftop siren and full red strobe"),
  "compacting": (compacting_frames, "MATERIAL SORT -- loose supplies pack into a crate"),
  "success": (success_frames, "GRAND OPENING -- finished workshop glows"),
  "error": (error_frames, "BUILD FAILED -- cracked wall, smoke and falling brick"),
  "chilling": (chilling_frames, "AFTER HOURS -- Claude sleeps beside the warm shop"),
  "off": (off_frames, "blank display"),
}


# --- output ---------------------------------------------------------------

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
  mascot.FACE: "f", mascot.FACE_LIGHT: "F", mascot.EYE: "o",
  BLUEPRINT: "=", CYAN: "%", CYAN_LIGHT: "%", CREAM: "!", WHITE: "!",
  WOOD_DARK: "+", WOOD: "+", WOOD_LIGHT: "*", BRICK: "#",
  BRICK_LIGHT: "*", STEEL: "?", STEEL_LIGHT: "?", SAFETY: "!",
  GLOW: "!", MINT: "!", RED: "!", RED_DARK: "+", PINK: "!",
  FLOOR: "_", FLOOR_LIGHT: "_", FLOOR_DARK: "_", INK: "+",
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
    print(f"    {len(frames)} frames, {delays[0]}ms first delay, "
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
