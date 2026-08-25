#!/usr/bin/env python3
"""Generate nine Clauddy-style 16x16 status animations for Ditoo Pro.

The visual grammar is intentionally simple: one large flat terracotta mascot,
one oversized prop, charcoal background, tiny black eyes, stick arms and four
feet. The construction story remains, but scenery never competes with Clauddy:

    thinking    a big cyan blueprint opens in front of Clauddy
    compacting  Clauddy squeezes loose sheets into one small bundle
    working     Clauddy hammers a brick at a workbench
    alerting    one exclamation grows into a full alarm
    success     a tiny finished workshop glows above Clauddy
    error       that workshop cracks while Clauddy stares with X eyes
    chilling    Clauddy closes their eyes and nurses a warm mug

The art is drawn directly on the 16x16 grid and is original to this project;
the style and staging are informed by the Clauddy MiniToo reference.
"""

import argparse
import os
import struct
import sys
import zlib

import mascot
from mascot import SIZE
from gifwriter import write_gif


# Palette sampled from the broad visual language of the reference: almost-flat
# terracotta on charcoal, with one bright accent per scene.
BG = (41, 40, 49)
BG_DARK = (32, 44, 49)
BLACK = (0, 0, 0)
BODY = (213, 113, 82)
BODY_LIGHT = (222, 121, 90)
BODY_DARK = (180, 101, 74)

YELLOW = (255, 210, 106)
YELLOW_LIGHT = (255, 238, 151)
CYAN = (67, 204, 221)
CYAN_LIGHT = (184, 244, 244)
BLUE = (33, 107, 176)
RED = (244, 70, 74)
RED_DARK = (111, 44, 54)
MINT = (73, 224, 153)
PINK = (248, 111, 158)

WOOD_DARK = (76, 48, 39)
WOOD = (135, 82, 55)
WOOD_LIGHT = (191, 122, 71)
BRICK = (183, 72, 53)
BRICK_LIGHT = (234, 119, 73)
STEEL = (107, 119, 124)
STEEL_LIGHT = (185, 195, 192)
PAPER = (247, 226, 181)


def pixels(grid, points, colour):
  for x, y in points:
    mascot.px(grid, x, y, colour)


def clauddy(grid, y=5, jump=0, expression="neutral", gaze=0,
            left="out", right="out", step=0):
  """Draw the reference-style mascot as the dominant 16x16 silhouette.

  The torso spans twelve columns. It has no face panel, costume or outline:
  just a flat block, two black vertical eyes, tiny arms, and four narrow feet.
  """
  top = y - jump

  mascot.rect(grid, 3, top, 12, top, BODY_LIGHT)
  mascot.rect(grid, 2, top + 1, 13, top + 6, BODY)
  mascot.rect(grid, 2, top + 6, 13, top + 6, BODY_DARK)
  mascot.px(grid, 2, top + 1, BODY_LIGHT)

  def arm(side, pose):
    if side == "left":
      shapes = {
        "out": ((0, top + 4), (1, top + 4)),
        "up": ((1, top + 4), (0, top + 3), (0, top + 2)),
        "high": ((1, top + 3), (0, top + 2), (1, top + 1)),
        "down": ((1, top + 5), (1, top + 6), (0, top + 7)),
        "in": ((1, top + 4), (2, top + 4), (3, top + 5)),
      }
    else:
      shapes = {
        "out": ((14, top + 4), (15, top + 4)),
        "up": ((14, top + 4), (15, top + 3), (15, top + 2)),
        "high": ((14, top + 3), (15, top + 2), (14, top + 1)),
        "down": ((14, top + 5), (14, top + 6), (15, top + 7)),
        "in": ((14, top + 4), (13, top + 4), (12, top + 5)),
      }
    pixels(grid, shapes.get(pose, shapes["out"]), BODY)

  arm("left", left)
  arm("right", right)

  eye_y = top + 2
  if expression == "sleep":
    pixels(grid, ((4, eye_y + 1), (5, eye_y + 1),
                  (10, eye_y + 1), (11, eye_y + 1)), BLACK)
  elif expression == "x":
    pixels(grid, ((4, eye_y), (5, eye_y + 1), (4, eye_y + 2),
                  (11, eye_y), (10, eye_y + 1), (11, eye_y + 2)), BLACK)
  else:
    shift = max(-1, min(1, gaze))
    mascot.rect(grid, 5 + shift, eye_y, 5 + shift, eye_y + 1, BLACK)
    mascot.rect(grid, 10 + shift, eye_y, 10 + shift, eye_y + 1, BLACK)

  mouth_y = top + 5
  if expression == "happy":
    pixels(grid, ((6, mouth_y - 1), (7, mouth_y), (8, mouth_y),
                  (9, mouth_y - 1)), BLACK)
  elif expression == "shock":
    mascot.rect(grid, 7, mouth_y - 1, 8, mouth_y, BLACK)
  elif expression == "sleep":
    mascot.rect(grid, 7, mouth_y, 9, mouth_y, BLACK)
  elif expression != "x":
    pixels(grid, ((6, mouth_y), (7, mouth_y), (8, mouth_y),
                  (9, mouth_y - 1)), BLACK)

  foot_y = top + 7
  feet = (3, 5, 10, 12)
  if step:
    feet = tuple(x for index, x in enumerate(feet) if index % 2 == step % 2)
  for x in feet:
    mascot.rect(grid, x, foot_y, x, foot_y + 1, BODY_DARK)


def blueprint(grid, scan=0, pulse=False):
  """A huge plan held across Clauddy's lower body."""
  border = CYAN_LIGHT if pulse else CYAN
  mascot.rect(grid, 3, 9, 12, 15, border)
  mascot.rect(grid, 4, 10, 11, 14, BLUE)
  # Big house elevation: roof, walls, central door.
  pixels(grid, ((4, 12), (5, 11), (6, 10), (7, 10),
                (8, 10), (9, 11), (10, 12)), PAPER)
  mascot.rect(grid, 5, 12, 5, 13, PAPER)
  mascot.rect(grid, 10, 12, 10, 13, PAPER)
  mascot.rect(grid, 5, 13, 10, 13, PAPER)
  mascot.rect(grid, 7, 12, 8, 14, CYAN_LIGHT)
  mascot.px(grid, 4 + scan % 8, 15, YELLOW_LIGHT)
  pixels(grid, ((2, 10), (13, 10)), BODY)


def material_bundle(grid, phase=0):
  """Loose plan sheets visibly compress into a small strapped bundle."""
  layers = max(1, 4 - phase)
  top = 12 - layers
  for index in range(layers):
    y = top + index
    colour = (PAPER, CYAN_LIGHT, CYAN, PAPER)[index % 4]
    mascot.rect(grid, 5 - index % 2, y, 10 + index % 2, y, colour)
  mascot.rect(grid, 4, 13, 11, 15, WOOD_DARK)
  mascot.rect(grid, 5, 14, 10, 14, WOOD)
  mascot.rect(grid, 7, 13, 8, 15, YELLOW)
  pixels(grid, ((3, 11), (4, 11), (11, 11), (12, 11)), BODY)


def workbench(grid):
  mascot.rect(grid, 0, 11, 15, 12, WOOD_DARK)
  mascot.rect(grid, 1, 11, 14, 11, WOOD_LIGHT)
  mascot.rect(grid, 2, 13, 3, 15, WOOD)
  mascot.rect(grid, 12, 13, 13, 15, WOOD)


def work_bricks(grid):
  mascot.rect(grid, 11, 8, 15, 10, BRICK)
  pixels(grid, ((12, 8), (14, 8), (11, 10), (13, 10)), BRICK_LIGHT)
  mascot.px(grid, 13, 9, WOOD_DARK)


def hammer(grid, down=False):
  if down:
    pixels(grid, ((8, 10), (9, 10), (10, 10), (11, 10)), WOOD_LIGHT)
    mascot.rect(grid, 11, 8, 12, 10, STEEL_LIGHT)
  else:
    pixels(grid, ((8, 10), (9, 9), (10, 8), (11, 7)), WOOD_LIGHT)
    mascot.rect(grid, 10, 6, 13, 7, STEEL_LIGHT)
    mascot.px(grid, 10, 7, STEEL)


def exclamation(grid, level=1, on=True):
  colour = (YELLOW, YELLOW_LIGHT, RED)[level - 1] if on else BODY_DARK
  if level == 1:
    mascot.rect(grid, 7, 1, 8, 3, colour)
    mascot.rect(grid, 7, 5, 8, 5, colour)
  elif level == 2:
    mascot.rect(grid, 6, 0, 9, 3, colour)
    mascot.rect(grid, 7, 4, 8, 5, colour)
    pixels(grid, ((4, 1), (11, 1), (5, 4), (10, 4)), colour)
  else:
    mascot.rect(grid, 6, 0, 9, 5, colour)
    mascot.rect(grid, 6, 7, 9, 8, colour)
    pixels(grid, ((3, 0), (12, 0), (4, 4), (11, 4),
                  (2, 6), (13, 6)), YELLOW_LIGHT if on else RED_DARK)


def tiny_workshop(grid, broken=False, bright=True, y=0):
  """A filled roof and square walls make this unmistakably a tiny house."""
  roof = RED if broken else (YELLOW if bright else WOOD)
  walls = BRICK if broken else (YELLOW_LIGHT if bright else WOOD_LIGHT)
  mascot.rect(grid, 7, y, 8, y, roof)
  mascot.rect(grid, 6, y + 1, 9, y + 1, roof)
  mascot.rect(grid, 5, y + 2, 10, y + 2, roof)
  mascot.rect(grid, 4, y + 3, 11, y + 3, roof)
  mascot.rect(grid, 5, y + 4, 10, y + 7, walls)
  mascot.rect(grid, 7, y + 5, 8, y + 7, BLACK)
  mascot.px(grid, 6, y + 5, MINT if bright and not broken else BG_DARK)
  mascot.px(grid, 9, y + 5, MINT if bright and not broken else BG_DARK)
  mascot.rect(grid, 10, y, 11, y + 2, WOOD_DARK)
  if broken:
    pixels(grid, ((8, y + 2), (7, y + 3), (8, y + 4),
                  (7, y + 5), (8, y + 6)), YELLOW_LIGHT)
    mascot.px(grid, 10, y + 2, BG)


def mug(grid, steam=0):
  mascot.rect(grid, 12, 10, 14, 13, YELLOW)
  mascot.rect(grid, 13, 10, 14, 10, PAPER)
  mascot.rect(grid, 15, 11, 15, 12, YELLOW)
  mascot.px(grid, 12, 13, BODY_DARK)
  if steam < 3:
    pixels(grid, ((13, 8 - steam), (14, 7 - steam)), STEEL_LIGHT)


def thinking_frames():
  frames = []
  for i in range(8):
    grid = mascot.blank(BG)
    clauddy(grid, y=4, gaze=-1 if i % 4 < 2 else 1,
            expression="neutral", left="in", right="in")
    blueprint(grid, scan=i, pulse=i in (2, 3, 7))
    frames.append(grid)
  return frames, [230, 220, 180, 260, 230, 220, 180, 300]


def compacting_frames():
  frames = []
  for i in range(10):
    grid = mascot.blank(BG)
    phase = min(i % 5, 3)
    clauddy(grid, y=4 + (1 if phase == 3 else 0), expression="neutral",
            gaze=0, left="in", right="in")
    material_bundle(grid, phase)
    if phase == 3:
      pixels(grid, ((3, 12), (12, 12)), YELLOW_LIGHT)
    frames.append(grid)
  return frames, [150, 130, 120, 180, 250, 150, 130, 120, 180, 280]


def working_frames():
  frames = []
  for i in range(10):
    grid = mascot.blank(BG)
    down = i % 4 in (2, 3)
    clauddy(grid, y=3, gaze=1, expression="neutral",
            left="down", right="in", step=1 + i % 2)
    workbench(grid)
    work_bricks(grid)
    hammer(grid, down=down)
    if down:
      pixels(grid, ((10, 8), (10, 10), (12, 7), (13, 8)), YELLOW_LIGHT)
    if i in (4, 5):
      pixels(grid, ((3, 2), (2, 3)), CYAN)  # one readable sweat beat
    frames.append(grid)
  return frames, [120, 110, 90, 140, 120, 110, 90, 140, 120, 180]


def alert_scene(level):
  frames = []
  count = 8 if level < 3 else 6
  for i in range(count):
    flashing = i % 2 == 0
    bg = RED_DARK if level == 3 and flashing else BG
    grid = mascot.blank(bg)
    exclamation(grid, level=level, on=flashing or level == 1)
    jump = 1 if level == 3 and i % 2 else 0
    clauddy(
      grid, y=7, jump=jump,
      expression="shock" if level >= 2 else "neutral",
      left="high" if level >= 2 else "up",
      right="high" if level >= 2 else "out",
      step=i % 2 if level == 3 else 0,
    )
    frames.append(grid)
  delays = {
    1: [230, 230, 190, 260, 230, 230, 190, 300],
    2: [120, 100, 120, 100, 120, 100, 120, 150],
    3: [80, 80, 80, 80, 80, 110],
  }[level]
  return frames, delays


def alerting_frames():
  return alert_scene(1)


def alerting2_frames():
  return alert_scene(2)


def alerting3_frames():
  return alert_scene(3)


def success_frames():
  frames = []
  for i in range(12):
    grid = mascot.blank(BG)
    tiny_workshop(grid, bright=i % 4 != 3, y=0)
    jump = (0, 1, 2, 2, 1, 0)[i % 6]
    clauddy(grid, y=8, jump=jump, expression="happy",
            left="high", right="high", step=i % 2)
    pixels(grid, ((1, 1 + i % 3), (3, 4), (12, 2 + i % 2),
                  (14, 5 + i % 3)), (CYAN, PINK, MINT, YELLOW)[i % 4])
    frames.append(grid)
  return frames, [150, 130, 130, 170, 130, 220] * 2


def error_frames():
  frames = []
  for i in range(10):
    flash = i in (1, 2, 6)
    grid = mascot.blank(RED_DARK if flash else BG)
    tiny_workshop(grid, broken=True, bright=False, y=0)
    clauddy(grid, y=8, expression="x",
            left="down", right="down", step=0)
    fall_y = 2 + min(i // 2, 5)
    mascot.rect(grid, 11, fall_y, 12, fall_y + 1,
                YELLOW_LIGHT if flash else BRICK)
    pixels(grid, ((2, 2 + i % 3), (13, 1 + i % 4)),
           STEEL_LIGHT if flash else STEEL)
    frames.append(grid)
  return frames, [180, 120, 120, 190, 170, 230, 120, 180, 220, 320]


def chilling_frames():
  frames = []
  for i in range(12):
    grid = mascot.blank(BG)
    clauddy(grid, y=6, expression="sleep", left="down", right="in")
    mug(grid, steam=i % 6)
    if i % 6 < 4:
      z = 4 - i % 3
      pixels(grid, ((2, z), (3, z), (3, z + 1),
                    (2, z + 2), (3, z + 2)), CYAN)
    if i in (4, 10):
      pixels(grid, ((6, 1), (7, 1), (7, 0)), YELLOW)
    frames.append(grid)
  return frames, [300] * 12


def off_frames():
  black = (0, 0, 0)
  return [[[black] * SIZE for _ in range(SIZE)]], [500]


FACES = {
  "thinking": (thinking_frames, "BLUEPRINT -- Clauddy opens the plan"),
  "working": (working_frames, "HAMMERING -- workbench, brick and sparks"),
  "alerting": (alerting_frames, "HEY -- slow exclamation and one raised hand"),
  "alerting2": (alerting2_frames, "STILL WAITING -- larger flash and both hands up"),
  "alerting3": (alerting3_frames, "ALARM -- giant red strobe and jumping Clauddy"),
  "compacting": (compacting_frames, "SQUEEZE -- loose sheets become one bundle"),
  "success": (success_frames, "BUILT -- glowing workshop and happy jump"),
  "error": (error_frames, "BROKEN -- cracked workshop and X eyes"),
  "chilling": (chilling_frames, "TEA BREAK -- closed eyes, steam and a tiny Z"),
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
  BODY: "#", BODY_DARK: "+", BODY_LIGHT: "*", BLACK: "o",
  YELLOW: "!", YELLOW_LIGHT: "!", CYAN: "%", CYAN_LIGHT: "%",
  BLUE: "=", RED: "!", RED_DARK: "+", MINT: "!", PINK: "!",
  WOOD_DARK: "+", WOOD: "+", WOOD_LIGHT: "*", BRICK: "#",
  BRICK_LIGHT: "*", STEEL: "?", STEEL_LIGHT: "?", PAPER: "!",
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
      big = [scale(frame, 20) for frame in indexed]
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
