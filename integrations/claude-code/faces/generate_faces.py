#!/usr/bin/env python3
"""Generate a tiny Super Mario status world for the Ditoo Pro.

Every Claude Code state is another scene in the same miniature platformer:

    thinking    Mario studies a level map without moving
    working     Mario runs through bricks, coins and a warp pipe
    alerting    a castle door waits for the player's key
    compacting  loose code blocks disappear into a warp pipe
    success     Mario grabs the flagpole under fireworks
    error       a Goomba bonks Mario and knocks off his cap
    chilling    Mario naps on a warp pipe beside a mushroom

Mario is only five pixels wide, leaving most of the panel for recognisable
level geometry: sky, bricks, question blocks, pipes, enemies and castles.

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

# A deliberately recognisable 8-bit plumber palette: blue overworld sky,
# orange bricks, green pipes, gold blocks and high-contrast red danger scenes.
SKY = (28, 106, 190)
SKY_LIGHT = (102, 193, 242)
NIGHT = (8, 18, 58)
BG_CHILL = NIGHT
BG_THINK = SKY
BG_WORK = SKY
BG_ALERT_HOT = (118, 21, 20)
BG_ALERT_COOL = (24, 31, 80)
BG_SUCCESS = SKY
BG_ERROR = (48, 15, 48)

INK = (17, 14, 18)
CODE_DARK = (26, 76, 129)
CODE = (53, 211, 235)
CODE_LIGHT = (151, 239, 248)
AMBER = (248, 181, 65)
CREAM = (255, 230, 178)
MINT = (72, 224, 158)
HOT = (255, 70, 72)
PINK = (255, 98, 150)
PURPLE = (157, 91, 230)
GROUND_DARK = (8, 21, 42)
GROUND = (22, 54, 84)
GROUND_LIGHT = (43, 104, 134)
CAP_RED = (232, 48, 42)
OVERALL_BLUE = (30, 74, 178)
BRICK_DARK = (108, 45, 32)
BRICK = (194, 82, 47)
BRICK_LIGHT = (255, 153, 64)
PIPE_DARK = (0, 91, 52)
PIPE = (34, 177, 76)
PIPE_LIGHT = (130, 232, 102)
LAVA = (245, 51, 35)
LAVA_LIGHT = (255, 194, 55)
TURTLE = (91, 190, 74)
MARIO_SKIN = (255, 187, 112)
MARIO_HAIR = (79, 37, 22)
MARIO_BOOT = (96, 43, 27)


def pixels(grid, points, colour):
  for x, y in points:
    mascot.px(grid, x, y, colour)


def ground(grid, danger=False, offset=0):
  """Classic brick floor, or animated lava for urgent/error scenes."""
  edge = LAVA_LIGHT if danger else BRICK_LIGHT
  fill = LAVA if danger else BRICK
  dark = BRICK_DARK
  mascot.rect(grid, 0, 13, 15, 13, edge)
  mascot.rect(grid, 0, 14, 15, 15, fill)
  for x in range(-2 + offset % 4, 18, 4):
    mascot.rect(grid, x, 14, x + 1, 14, dark)
    mascot.px(grid, x + 2, 15, dark)


def clouds(grid, shift=0, night=False):
  colour = CODE_DARK if night else CREAM
  for origin in (-4 + shift % 12, 8 + shift % 12):
    pixels(grid, (
      (origin, 2), (origin + 1, 1), (origin + 2, 1),
      (origin + 3, 2), (origin + 4, 2), (origin + 1, 2), (origin + 2, 2),
    ), colour)


def mario(grid, x, y, jump=0, step=0, pose="stand", facing=1, cap=True):
  """An original five-wide miniature Mario sprite.

  The previous seven-wide Claude costume left too little room for a level.
  This tighter silhouette gives the environment eleven columns while retaining
  Mario's unmistakable red cap, warm face, black hair/moustache, red shirt,
  blue overalls and brown boots. It is drawn from scratch rather than copied
  from a Nintendo sprite sheet.
  """
  top = y - jump

  def dot(local_x, local_y, colour):
    actual_x = local_x if facing >= 0 else 4 - local_x
    mascot.px(grid, x + actual_x, top + local_y, colour)

  if cap:
    for local_x in (1, 2, 3):
      dot(local_x, 0, CAP_RED)
    for local_x in (0, 1, 2, 3, 4):
      dot(local_x, 1, CAP_RED)
    dot(2, 0, CREAM)

  # Hair, skin, single eye and a two-pixel moustache.
  for local_x, local_y in ((0, 2), (0, 3), (1, 3), (3, 3), (4, 3)):
    dot(local_x, local_y, MARIO_HAIR)
  for local_x, local_y in ((1, 2), (2, 2), (3, 2), (1, 3), (2, 3)):
    dot(local_x, local_y, MARIO_SKIN)
  dot(4, 2, INK if pose != "sleep" else MARIO_HAIR)

  # Red shirt and blue bib. Poses only move the arms; the strong colour blocks
  # stay stable so the character remains legible during fast loops.
  dot(1, 4, CAP_RED)
  dot(2, 4, OVERALL_BLUE)
  dot(3, 4, CAP_RED)
  for local_x in (1, 2, 3):
    dot(local_x, 5, OVERALL_BLUE)
  if pose == "wave":
    dot(0, 4, MARIO_SKIN)
    dot(4, 2, MARIO_SKIN)
    dot(4, 1, MARIO_SKIN)
  elif pose == "read":
    dot(0, 4, MARIO_SKIN)
    dot(4, 4, MARIO_SKIN)
    dot(4, 5, MARIO_SKIN)
  elif pose == "flag":
    dot(0, 4, MARIO_SKIN)
    dot(4, 3, MARIO_SKIN)
    mascot.px(grid, x + (5 if facing >= 0 else -1), top + 2, MARIO_SKIN)
  else:
    dot(0, 4, MARIO_SKIN)
    dot(4, 4, MARIO_SKIN)

  # Alternating boot positions provide the classic two-frame run.
  if step == 1:
    boots = (0, 3)
  elif step == 2:
    boots = (1, 4)
  else:
    boots = (1, 3)
  for local_x in boots:
    dot(local_x, 6, MARIO_BOOT)


def question_block(grid, x, y, flash=False, empty=False):
  face = BRICK if empty else (CREAM if flash else AMBER)
  mascot.rect(grid, x, y, x + 4, y + 4, BRICK_DARK)
  mascot.rect(grid, x, y, x + 3, y + 3, face)
  pixels(grid, ((x, y), (x + 3, y), (x, y + 3), (x + 3, y + 3)), BRICK_LIGHT)
  if not empty:
    pixels(grid, (
      (x + 1, y + 1), (x + 2, y + 1),
      (x + 2, y + 2), (x + 1, y + 3),
    ), INK)


def pipe(grid, x, y, height=5):
  bottom = min(12, y + height)
  mascot.rect(grid, x + 1, y + 2, x + 4, bottom, PIPE_DARK)
  mascot.rect(grid, x + 2, y + 2, x + 3, bottom, PIPE)
  mascot.rect(grid, x, y, x + 5, y + 2, PIPE_DARK)
  mascot.rect(grid, x + 1, y, x + 4, y + 1, PIPE)
  mascot.rect(grid, x + 2, y, x + 2, y + 1, PIPE_LIGHT)


def goomba(grid, x, y, blink=False):
  """Original squat mushroom bug, using the iconic enemy silhouette."""
  mascot.rect(grid, x + 1, y + 1, x + 4, y + 4, BRICK_DARK)
  mascot.rect(grid, x + 2, y, x + 3, y, BRICK_LIGHT)
  pixels(grid, ((x, y + 2), (x + 5, y + 2), (x, y + 5), (x + 5, y + 5)), BRICK_DARK)
  if blink:
    pixels(grid, ((x + 1, y + 2), (x + 4, y + 2)), INK)
  else:
    pixels(grid, ((x + 1, y + 2), (x + 4, y + 2)), CREAM)
    pixels(grid, ((x + 2, y + 3), (x + 3, y + 3)), INK)


def mushroom(grid, x, y, colour=CAP_RED):
  pixels(grid, ((x + 1, y), (x + 2, y), (x, y + 1), (x + 3, y + 1)), colour)
  mascot.rect(grid, x, y + 2, x + 3, y + 2, CREAM)
  mascot.rect(grid, x + 1, y + 3, x + 2, y + 4, CREAM)
  pixels(grid, ((x + 1, y + 1), (x + 3, y + 1)), CREAM)


def heart(grid, x, y, colour=HOT, broken=False):
  if broken:
    pixels(grid, ((x, y), (x + 2, y), (x, y + 1), (x + 2, y + 1)), colour)
    mascot.px(grid, x - 1, y + 2, colour)
    mascot.px(grid, x + 3, y + 3, colour)
    return
  pixels(grid, (
    (x, y), (x + 2, y),
    (x, y + 1), (x + 1, y + 1), (x + 2, y + 1),
    (x + 1, y + 2),
  ), colour)


def coin(grid, x, y, shine=False):
  pixels(grid, ((x + 1, y), (x, y + 1), (x + 2, y + 1), (x + 1, y + 2)), AMBER)
  mascot.px(grid, x + 1, y + 1, CREAM if shine else AMBER)


def key(grid, x, y, colour=AMBER):
  """A five-wide arcade key, intentionally huge enough to read instantly."""
  pixels(grid, (
    (x, y), (x + 1, y), (x + 2, y),
    (x, y + 1), (x + 2, y + 1),
    (x, y + 2), (x + 1, y + 2), (x + 2, y + 2),
    (x + 3, y + 1), (x + 4, y + 1), (x + 4, y + 2),
  ), colour)
  mascot.px(grid, x + 1, y + 1, BG_ALERT_COOL)


def bug(grid, x, y, angry=False, blink=False, colour=PINK):
  """A cute seven-wide code bug with antennae and very readable eyes."""
  mascot.rect(grid, x + 1, y + 1, x + 5, y + 4, colour)
  mascot.rect(grid, x + 2, y, x + 4, y, HOT if angry else colour)
  pixels(grid, ((x, y), (x + 1, y + 1), (x + 5, y + 1), (x + 6, y)), colour)
  pixels(grid, ((x, y + 4), (x + 1, y + 5), (x + 5, y + 5), (x + 6, y + 4)), colour)
  if blink:
    pixels(grid, ((x + 2, y + 2), (x + 4, y + 2)), INK)
  else:
    pixels(grid, ((x + 2, y + 2), (x + 4, y + 2)), CREAM)
    pixels(grid, ((x + 2, y + 3), (x + 4, y + 3)), INK)
  if angry:
    pixels(grid, ((x + 1, y + 2), (x + 5, y + 2)), INK)


def gate(grid, glow=False):
  """Brick castle with a giant keyhole door."""
  stone = CREAM if glow else BRICK
  mascot.rect(grid, 9, 4, 15, 12, BRICK_DARK)
  pixels(grid, ((9, 3), (10, 3), (12, 3), (13, 3), (15, 3)), stone)
  mascot.rect(grid, 10, 4, 15, 7, stone)
  pixels(grid, ((11, 5), (14, 5), (10, 7), (13, 7)), BRICK_LIGHT)
  mascot.rect(grid, 10, 8, 14, 12, INK)
  mascot.rect(grid, 11, 8, 13, 8, mascot.BODY_DARK)
  mascot.rect(grid, 11, 10, 13, 11, HOT if glow else AMBER)
  mascot.px(grid, 12, 12, HOT if glow else CREAM)


def thinking_frames():
  """WORLD MAP: Mario stays put and quietly studies two routes."""
  frames = []
  for i in range(10):
    grid = mascot.blank(BG_THINK)
    clouds(grid, shift=0)
    ground(grid, offset=0)

    # The map is smaller than before, widening the shot enough to see Mario,
    # sky, clouds and brick floor as one complete overworld scene.
    mascot.rect(grid, 7, 3, 13, 11, MARIO_HAIR)
    mascot.rect(grid, 6, 3, 12, 10, CREAM)
    mascot.rect(grid, 7, 3, 13, 4, AMBER)
    mascot.rect(grid, 6, 9, 12, 10, AMBER)
    pixels(grid, ((7, 8), (8, 8), (8, 7), (9, 7), (9, 6), (10, 6)), CODE)
    pixels(grid, ((11, 5), (11, 7)), CODE_DARK)
    if i % 4 < 2:
      pixels(grid, ((11, 5), (12, 4), (12, 5)), PIPE)
      mascot.px(grid, 11, 7, CODE_DARK)
    else:
      pixels(grid, ((11, 7), (12, 7), (12, 8)), CAP_RED)
      mascot.px(grid, 11, 5, CODE_DARK)

    # Thought bubbles rise from the mascot toward a tiny question glyph.
    mascot.px(grid, 5, 5, CODE_DARK)
    pixels(grid, ((13, 0), (14, 0), (15, 1), (14, 2), (14, 3)), CODE_LIGHT)

    mario(grid, 0, 6, pose="read")
    frames.append(grid)
  return frames, [220, 220, 220, 260, 220, 220, 110, 260, 220, 280]


def chilling_frames():
  """1-UP REST STOP: Mario naps beside a green pipe and mushroom."""
  stars = ((1, 1), (5, 2), (9, 0), (14, 3))
  frames = []
  for i in range(12):
    grid = mascot.blank(BG_CHILL)
    ground(grid, offset=0)
    clouds(grid, shift=i // 3, night=True)
    for number, (x, y) in enumerate(stars):
      mascot.px(grid, x, y, CREAM if (i + number * 2) % 6 == 0 else CODE_DARK)

    # Crescent moon and a floating Z make this the attract/save screen, not a
    # generic idle pose.
    pixels(grid, ((13, 0), (14, 0), (12, 1), (13, 2), (14, 2)), CREAM)
    if i % 6 < 4:
      z_y = 4 - i % 4
      pixels(grid, ((5, z_y), (6, z_y), (6, z_y + 1), (5, z_y + 2), (6, z_y + 2)), CODE_LIGHT)

    pipe(grid, 9, 8, height=4)
    mushroom(grid, 11, 3 + (i // 3) % 2, CAP_RED if i % 4 else CREAM)

    mario(grid, 0, 6, pose="sleep")
    frames.append(grid)
  return frames, [240] * 12


def working_frames():
  """WORLD 1-1: Mario runs, jumps, bonks a block and releases a coin."""
  jumps = (0, 0, 1, 3, 4, 3, 1, 0, 0, 0)
  xs = (0, 0, 1, 2, 2, 1, 0, 0, 0, 0)
  frames = []
  for i in range(10):
    grid = mascot.blank(BG_WORK)
    clouds(grid, shift=i // 2)
    ground(grid, offset=i)

    question_block(grid, 6, 2, flash=i in (4, 5), empty=i >= 6)
    pipe(grid, 11, 8, height=4)
    if i >= 4:
      rise = (0, 1, 3, 4, 3, 1)[i - 4]
      coin(grid, 7, max(-1, 1 - rise), shine=i % 2 == 0)
      pixels(grid, ((5, 1), (15, 1 + i % 2)), CREAM)

    mario(
      grid, xs[i], 6, jump=jumps[i], step=1 + i % 2,
      pose="jump" if jumps[i] else "stand"
    )
    frames.append(grid)
  return frames, [110, 100, 90, 90, 180, 95, 105, 130, 120, 150]


def alerting_frames():
  """PLAYER NEEDED: Mario waves at a locked castle while its key pulses."""
  bobs = (0, 0, 1, 1, 0, 0, 1, 0)
  frames = []
  for i in range(8):
    hot = i in (2, 3, 6)
    grid = mascot.blank(BG_ALERT_HOT if hot else BG_ALERT_COOL)
    clouds(grid, shift=0, night=True)
    ground(grid, danger=False)
    gate(grid, glow=hot)
    key(grid, 4, 1 + bobs[i], CREAM if hot else AMBER)
    pixels(grid, ((4, 1), (4, 4), (9, 0), (9, 4)), HOT if hot else PINK)
    mario(grid, 0, 6, pose="wave")
    frames.append(grid)
  return frames, [160, 160, 100, 210, 160, 160, 100, 220]


def success_frames():
  """COURSE CLEAR: Mario grabs the flagpole while fireworks pop."""
  jumps = (0, 0, 1, 3, 4, 3, 1, 0, 0, 0)
  xs = (0, 1, 2, 3, 4, 5, 5, 5, 4, 3)
  flag_y = (2, 2, 2, 3, 4, 5, 6, 7, 7, 7)
  frames = []
  for i in range(10):
    grid = mascot.blank(BG_SUCCESS)
    clouds(grid, shift=i // 4)
    ground(grid, offset=0)

    # The ball, tall white pole and descending green flag are the clearest
    # possible plumber-game victory silhouette at sixteen pixels.
    # A tiny end castle behind the pole widens the shot into a whole goal area.
    mascot.rect(grid, 12, 8, 15, 12, BRICK_DARK)
    pixels(grid, ((12, 7), (13, 7), (15, 7)), BRICK)
    mascot.rect(grid, 13, 10, 14, 12, INK)
    mascot.rect(grid, 10, 1, 10, 12, CREAM)
    coin(grid, 9, 0, shine=True)
    fy = flag_y[i]
    mascot.rect(grid, 7, fy, 9, fy + 2, PIPE)
    pixels(grid, ((7, fy + 2), (8, fy + 3)), PIPE_DARK)

    if i >= 3:
      burst = i % 3
      pixels(grid, (
        (2, 1 + burst), (1, 2 + burst), (3, 2 + burst),
        (6, burst), (5, 1 + burst), (7, 1 + burst),
      ), AMBER if i % 2 else CREAM)

    mario(
      grid, xs[i], 6, jump=jumps[i], step=0,
      pose="flag" if i >= 3 else "stand"
    )
    frames.append(grid)
  return frames, [180, 260, 100, 90, 190, 100, 120, 170, 180, 220]


def error_frames():
  """GAME OVER BEAT: a Goomba bonks Mario and his cap flies off."""
  bug_x = (10, 9, 8, 8, 9, 10, 10, 10)
  recoil = (0, 0, 1, 2, 1, 0, 0, 0)
  frames = []
  for i in range(8):
    grid = mascot.blank(SKY if i not in (2, 3) else BG_ALERT_HOT)
    if i not in (2, 3):
      clouds(grid, shift=0)
    ground(grid, danger=False, offset=i)
    goomba(grid, bug_x[i], 7, blink=i == 6)
    if i < 2:
      heart(grid, 4, 1, HOT)
    else:
      heart(grid, 4, 0, HOT, broken=True)
      pixels(grid, ((7, 6), (8, 5), (8, 7), (9, 6)), CREAM if i % 2 else AMBER)
      cap_x = min(12, 4 + i)
      cap_y = max(0, 5 - (i - 2))
      mascot.rect(grid, cap_x, cap_y, cap_x + 3, cap_y, CAP_RED)
      mascot.rect(grid, cap_x + 2, cap_y + 1, cap_x + 4, cap_y + 1, CAP_RED)
    mario(
      grid, max(-1, 1 - recoil[i]), 6, jump=recoil[i],
      cap=i < 2, pose="hurt" if i >= 2 else "stand"
    )
    frames.append(grid)
  return frames, [170, 110, 90, 210, 120, 180, 200, 220]


def alerting2_frames():
  """PLAYER NEEDED, NOW: the castle flashes while lava rises."""
  jumps = (0, 2, 3, 1, 0, 3, 2, 0)
  frames = []
  for i in range(8):
    hot = i % 2 == 0
    grid = mascot.blank(BG_ALERT_HOT if hot else BG_ALERT_COOL)
    ground(grid, danger=True, offset=i * 2)
    gate(grid, glow=True)
    key(grid, 5, i % 2, CREAM if hot else HOT)
    pixels(grid, ((0, 1), (3, 0), (8, 4), (15, 1), (8, 7)), CREAM if hot else HOT)
    mario(grid, 0, 6, jump=jumps[i], pose="wave")
    frames.append(grid)
  return frames, [95, 85, 110, 85, 95, 110, 85, 120]


def alerting3_frames():
  """BOWSER ALERT: the giant castle boss guards the key in a full strobe."""
  frames = []
  for i in range(6):
    hot = i % 2 == 0
    grid = mascot.blank(HOT if hot else BG_ALERT_COOL)
    ground(grid, danger=True, offset=i)

    # Green turtle-dragon head, orange crown spikes, pale muzzle and fangs.
    boss = CREAM if hot else TURTLE
    mascot.rect(grid, 8, 2, 15, 9, boss)
    pixels(grid, ((8, 1), (10, 0), (12, 1), (14, 0), (15, 1)), AMBER if hot else HOT)
    pixels(grid, ((7, 2), (8, 3), (15, 3)), CREAM)
    mascot.rect(grid, 9, 3, 10, 5, CREAM)
    mascot.rect(grid, 13, 3, 14, 5, CREAM)
    pixels(grid, ((10, 4), (13, 4)), INK)
    mascot.rect(grid, 10, 6, 15, 9, AMBER if hot else CREAM)
    pixels(grid, ((11, 7), (14, 7)), INK)
    pixels(grid, ((10, 9), (12, 9), (14, 9)), INK)
    key(grid, 10, 10, INK if hot else CREAM)

    mario(grid, 0, 6, jump=1 if i in (1, 4) else 0, pose="wave")
    frames.append(grid)
  return frames, [90, 90, 90, 90, 90, 120]


def compacting_frames():
  """WARP CLEANUP: loose context blocks spiral neatly into a green pipe."""
  frames = []
  paths = (
    ((6, 1), (7, 2), (8, 3), (9, 4), (10, 5), (11, 6), (12, 7), (12, 8)),
    ((12, 1), (13, 2), (14, 3), (14, 4), (13, 5), (12, 6), (12, 7), (12, 8)),
    ((7, 5), (8, 5), (9, 5), (10, 6), (11, 6), (12, 7), (12, 8), (12, 8)),
  )
  for i in range(8):
    grid = mascot.blank(SKY)
    clouds(grid, shift=i // 3)
    ground(grid, offset=0)

    # Draw the loose blocks first, then the pipe lip over them so they visibly
    # vanish down the opening instead of merely stopping above it.
    for number, path in enumerate(paths):
      x, y = path[(i + number * 2) % len(path)]
      colour = (CODE, CODE_LIGHT, AMBER)[number]
      mascot.rect(grid, x, y, x + 1, y + 1, colour)
    pipe(grid, 10, 8, height=4)
    pixels(grid, ((9, 7), (15, 7)), CREAM if i % 2 else PIPE_LIGHT)

    # A blue P-switch gives Mario an obvious "tidy now" control.
    mascot.rect(grid, 6, 9, 8, 12, OVERALL_BLUE)
    mascot.rect(grid, 6, 9, 8, 9, CREAM if i in (3, 4) else CODE_LIGHT)
    mario(grid, 0, 6, pose="read" if i in (3, 4) else "stand")
    frames.append(grid)
  return frames, [140, 130, 120, 110, 110, 120, 150, 200]


def off_frames():
  black = (0, 0, 0)
  return [[[black] * SIZE for _ in range(SIZE)]], [500]


FACES = {
  "thinking": (thinking_frames, "WORLD MAP -- quietly considering two routes"),
  "working": (working_frames, "WORLD 1-1 -- running, jumping and bonking a block"),
  "alerting": (alerting_frames, "PLAYER NEEDED -- key at the locked castle"),
  "alerting2": (alerting2_frames, "PLAYER NEEDED -- castle flashes, lava rises"),
  "alerting3": (alerting3_frames, "BOWSER ALERT -- full castle-boss strobe"),
  "compacting": (compacting_frames, "WARP CLEANUP -- blocks disappear into a pipe"),
  "success": (success_frames, "COURSE CLEAR -- flagpole and fireworks"),
  "error": (error_frames, "BONK -- Goomba knocks off Mario's cap"),
  "chilling": (chilling_frames, "1-UP REST STOP -- pipe, mushroom and a nap"),
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
  mascot.FACE: "f", mascot.FACE_LIGHT: "F",
  mascot.EYE: "o", mascot.EYE_SHINE: "@",
  CODE_DARK: "=", CODE: "%", CODE_LIGHT: "%", AMBER: "!", CREAM: "!",
  MINT: "!", HOT: "!", PINK: "!", PURPLE: "!", INK: "+",
  GROUND_DARK: "=", GROUND: "=", GROUND_LIGHT: "=",
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
