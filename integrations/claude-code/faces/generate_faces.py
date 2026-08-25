#!/usr/bin/env python3
"""Generate a full-board Pac-Man status arcade for the Ditoo Pro.

Every Claude Code state is another scene in the same miniature platformer:

    thinking    Pac-Man waits at a fork while two routes pulse
    working     Pac-Man traverses the maze, clearing pellets
    alerting    ghosts approach through increasingly urgent warnings
    compacting  a shrinking pellet ring clears into one power pellet
    success     the board is clear; frightened ghosts flee under cherries
    error       a ghost collision triggers Pac-Man's death burst
    chilling    the full maze rests with Pac-Man asleep and ghosts at home

The camera never cuts in. Every frame keeps the entire neon maze visible, with
three-wide characters moving inside it rather than becoming close-up portraits.

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
PAC_YELLOW = (255, 226, 32)
PAC_WALL = (28, 67, 255)
PAC_WALL_LIGHT = (80, 170, 255)
PAC_PELLET = (255, 190, 156)
GHOST_RED = (255, 45, 45)
GHOST_PINK = (255, 130, 190)
GHOST_CYAN = (45, 225, 235)
GHOST_ORANGE = (255, 165, 55)
GHOST_FRIGHT = (45, 75, 230)
CHERRY_RED = (238, 40, 55)


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


# --- Pac-Man board --------------------------------------------------------

PAC_MAZE_LAYOUT = (
  "################",
  "#......##......#",
  "#.##..#..#..##.#",
  "#.##..#..#..##.#",
  "#..............#",
  "#.##.#.##.#.##.#",
  "#....#.##.#....#",
  "####..#==#..####",
  "......#..#......",
  "####..####..####",
  "#......##......#",
  "#.##.#.##.#.##.#",
  "#..#........#..#",
  "##.#.######.#.##",
  "#..............#",
  "################",
)

PAC_POWER_POINTS = ((1, 3), (14, 3), (1, 12), (14, 12))
PAC_DOTS = tuple(
  (x, y)
  for y, row in enumerate(PAC_MAZE_LAYOUT)
  for x, value in enumerate(row)
  if value == "." and (x + y) % 2 == 0 and (x, y) not in PAC_POWER_POINTS
)


def pac_maze(grid, wall=PAC_WALL, gate=GHOST_PINK):
  """Draw a thin, symmetric miniature of the complete arcade maze."""
  for y, row in enumerate(PAC_MAZE_LAYOUT):
    for x, value in enumerate(row):
      if value == "#":
        mascot.px(grid, x, y, wall)
      elif value == "=":
        mascot.px(grid, x, y, gate)


def pac_pellets(grid, hidden=(), colour=PAC_PELLET):
  hidden = set(hidden)
  for point in PAC_DOTS:
    if point not in hidden:
      mascot.px(grid, point[0], point[1], colour)
  for point in PAC_POWER_POINTS:
    if point not in hidden:
      mascot.px(grid, point[0], point[1], CREAM)


def power_pellet(grid, x, y, bright=True):
  colour = CREAM if bright else PAC_PELLET
  mascot.px(grid, x, y, colour)


def pacman(grid, x, y, direction="right", mouth=True):
  """Two-wide Pac-Man; one missing pixel becomes the animated mouth."""
  points = {(0, 0), (1, 0), (0, 1), (1, 1)}
  if mouth:
    missing = {
      "right": {(1, 1)}, "left": {(0, 1)},
      "up": {(1, 0)}, "down": {(1, 1)},
    }.get(direction, {(1, 1)})
    points -= missing
  for px_x, px_y in points:
    mascot.px(grid, x + px_x, y + px_y, PAC_YELLOW)


def ghost(grid, x, y, colour, look=-1, blink=False, eyes_only=False):
  """Two-wide, three-tall ghost for the fully zoomed-out maze."""
  if not eyes_only:
    pixels(grid, ((x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1),
                  (x, y + 2), (x + 1, y + 2)), colour)
  if blink:
    mascot.px(grid, x + 1, y, INK)
  else:
    mascot.px(grid, x + (1 if look > 0 else 0), y, CREAM)


def cherry(grid, x, y):
  pixels(grid, ((x, y + 1), (x + 2, y + 1), (x, y + 2), (x + 2, y + 2)), CHERRY_RED)
  pixels(grid, ((x + 1, y), (x + 1, y + 1)), PIPE)


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
  """READY: Pac-Man waits at a fork while the two routes pulse."""
  frames = []
  for i in range(8):
    grid = mascot.blank(INK)
    pac_maze(grid)
    pac_pellets(grid)
    power_pellet(grid, 1, 3, bright=i % 4 < 2)
    power_pellet(grid, 14, 3, bright=i % 4 >= 2)
    direction = "left" if i % 4 < 2 else "right"
    pacman(grid, 7, 3, direction=direction, mouth=i % 2 == 0)
    frames.append(grid)
  return frames, [240, 180, 240, 300, 240, 180, 240, 320]


def chilling_frames():
  """ATTRACT MODE: full board, sleeping Pac-Man, ghosts resting at home."""
  frames = []
  for i in range(12):
    grid = mascot.blank(INK)
    pac_maze(grid, wall=PAC_WALL_LIGHT if i in (5, 11) else PAC_WALL)
    pac_pellets(grid)
    pacman(grid, 1, 11, direction="right", mouth=False)
    # Two pairs of eyes blink inside the ghost house without leaving it.
    ghost(grid, 6, 6, GHOST_PINK, blink=i in (4, 5), eyes_only=True)
    ghost(grid, 7, 6, GHOST_CYAN, blink=i in (9, 10), eyes_only=True)
    if i % 6 < 4:
      z_y = 10 - i % 4
      pixels(grid, ((4, z_y), (5, z_y), (5, z_y + 1),
                    (4, z_y + 2), (5, z_y + 2)), GHOST_CYAN)
    cherry(grid, 11, 6)
    frames.append(grid)
  return frames, [240] * 12


def working_frames():
  """CHOMP RUN: Pac-Man continuously traverses the maze and clears dots."""
  path = ((1, 1), (3, 1), (5, 1), (7, 1), (9, 1),
          (11, 1), (12, 2), (12, 5), (12, 7), (12, 9))
  frames = []
  for i in range(10):
    grid = mascot.blank(INK)
    pac_maze(grid)
    hidden = PAC_DOTS[:min(len(PAC_DOTS), i * 3)]
    pac_pellets(grid, hidden=hidden)
    x, y = path[i]
    direction = "down" if i >= 6 else "right"
    pacman(grid, x, y, direction=direction, mouth=i % 2 == 0)
    # Ghost-house eyes keep the board alive without turning this into danger.
    ghost(grid, 7, 6, GHOST_RED, look=-1, blink=i == 8, eyes_only=True)
    frames.append(grid)
  return frames, [105] * 10


def alerting_frames():
  """HEY: Pac-Man is stopped while one ghost approaches a power pellet."""
  frames = []
  for i in range(8):
    grid = mascot.blank(INK)
    pac_maze(grid, wall=PAC_WALL_LIGHT if i in (3, 7) else PAC_WALL)
    pac_pellets(grid)
    pacman(grid, 1, 8, direction="right", mouth=i % 3 == 0)
    power_pellet(grid, 7, 7, bright=i % 2 == 0)
    ghost(grid, 12 - (i // 4), 8, GHOST_RED, look=-1, blink=i == 6)
    mascot.rect(grid, 7, 1, 7, 3, GHOST_PINK if i % 2 else CREAM)
    mascot.px(grid, 7, 5, GHOST_PINK if i % 2 else CREAM)
    frames.append(grid)
  return frames, [190, 190, 160, 230, 190, 190, 160, 250]


def success_frames():
  """BOARD CLEAR: frightened ghosts flee under a cherry bonus shower."""
  frames = []
  for i in range(10):
    grid = mascot.blank(INK)
    wall = (PAC_WALL, PAC_WALL_LIGHT, CREAM)[i % 3]
    pac_maze(grid, wall=wall, gate=GHOST_PINK)
    cherry(grid, 6, 1)
    pacman(grid, 2 + min(i, 5), 8, direction="right", mouth=i % 2 == 0)
    if i < 6:
      ghost(grid, 10, 8, GHOST_FRIGHT, look=1, blink=i % 3 == 0)
    else:
      ghost(grid, 10, 8, GHOST_FRIGHT, eyes_only=True)
    if i < 8:
      ghost(grid, 12, 10, GHOST_FRIGHT, look=1, blink=i % 4 == 0)
    pixels(grid, ((1, 2 + i % 2), (4, 1), (11, 2), (14, 1 + i % 3)),
           (AMBER, CREAM, GHOST_CYAN)[i % 3])
    frames.append(grid)
  return frames, [130, 120, 110, 150, 110, 180, 110, 160, 130, 220]


def error_frames():
  """CAUGHT: a red ghost hits Pac-Man and triggers his death burst."""
  frames = []
  for i in range(8):
    grid = mascot.blank(INK)
    wall = GHOST_RED if i in (2, 3, 4) else PAC_WALL
    pac_maze(grid, wall=wall)
    pac_pellets(grid)
    if i < 3:
      pacman(grid, 3 + i, 8, direction="right", mouth=i % 2 == 0)
      ghost(grid, 9 - i, 8, GHOST_RED, look=-1)
    elif i == 3:
      ghost(grid, 6, 8, GHOST_RED, look=-1)
      pixels(grid, ((6, 7), (7, 6), (8, 7), (7, 8)), PAC_YELLOW)
    elif i == 4:
      ghost(grid, 6, 8, GHOST_RED, blink=True)
      pixels(grid, ((7, 5), (5, 7), (9, 7), (7, 9)), PAC_YELLOW)
    elif i == 5:
      ghost(grid, 6, 8, GHOST_RED, look=1)
      pixels(grid, ((5, 5), (9, 5), (5, 9), (9, 9)), PAC_YELLOW)
    elif i == 6:
      ghost(grid, 7, 8, GHOST_RED, look=1)
      pixels(grid, ((4, 4), (10, 4), (4, 10), (10, 10)), PAC_YELLOW)
    else:
      ghost(grid, 8, 8, GHOST_RED, look=1)
    frames.append(grid)
  return frames, [160, 120, 110, 180, 140, 150, 180, 260]


def alerting2_frames():
  """STILL WAITING: two ghosts close in and the maze flashes faster."""
  frames = []
  for i in range(8):
    grid = mascot.blank(INK)
    wall = GHOST_PINK if i % 2 == 0 else PAC_WALL_LIGHT
    pac_maze(grid, wall=wall, gate=CREAM)
    pac_pellets(grid)
    pacman(grid, 1, 8, direction="right", mouth=i % 2 == 0)
    power_pellet(grid, 6, 7, bright=i % 2 == 0)
    ghost(grid, 10 - i // 3, 8, GHOST_RED, look=-1)
    ghost(grid, 12 - i // 4, 11, GHOST_PINK, look=-1, blink=i == 6)
    mascot.rect(grid, 7, 1, 7, 3, CREAM if i % 2 == 0 else GHOST_RED)
    mascot.px(grid, 7, 5, CREAM if i % 2 == 0 else GHOST_RED)
    frames.append(grid)
  return frames, [100, 90, 100, 90, 100, 90, 100, 120]


def alerting3_frames():
  """CORNERED: four ghosts surround Pac-Man while the entire maze strobes."""
  frames = []
  for i in range(6):
    grid = mascot.blank(INK)
    wall = (CREAM, GHOST_RED, PAC_WALL_LIGHT)[i % 3]
    pac_maze(grid, wall=wall, gate=GHOST_PINK)
    pacman(grid, 6, 7, direction="right", mouth=i % 2 == 0)
    ghost(grid, 1, 1, GHOST_RED, look=1)
    ghost(grid, 12, 1, GHOST_PINK, look=-1)
    ghost(grid, 1, 11, GHOST_CYAN, look=1)
    ghost(grid, 12, 11, GHOST_ORANGE, look=-1)
    power_pellet(grid, 1, 7, bright=i % 2 == 0)
    power_pellet(grid, 13, 7, bright=i % 2 == 1)
    frames.append(grid)
  return frames, [80, 80, 80, 80, 80, 100]


def compacting_frames():
  """BOARD CLEANUP: Pac-Man clears a shrinking ring into one power pellet."""
  route = ((1, 1), (4, 1), (7, 1), (11, 1),
           (12, 5), (11, 9), (7, 11), (2, 9))
  frames = []
  for i in range(8):
    grid = mascot.blank(INK)
    pac_maze(grid, wall=PAC_WALL_LIGHT if i == 7 else PAC_WALL)
    hidden = PAC_DOTS[:min(len(PAC_DOTS), i * 4)]
    pac_pellets(grid, hidden=hidden)
    x, y = route[i]
    direction = ("right", "right", "right", "down", "down", "left", "left", "up")[i]
    pacman(grid, x, y, direction=direction, mouth=i % 2 == 0)
    if i >= 4:
      power_pellet(grid, 7, 7, bright=i % 2 == 0)
    pixels(grid, ((2 + i // 2, 7), (13 - i // 2, 7)),
           CREAM if i % 2 else PAC_PELLET)
    frames.append(grid)
  return frames, [120, 120, 120, 120, 130, 130, 150, 240]


def off_frames():
  black = (0, 0, 0)
  return [[[black] * SIZE for _ in range(SIZE)]], [500]


FACES = {
  "thinking": (thinking_frames, "READY -- stationary at a pulsing maze fork"),
  "working": (working_frames, "CHOMP RUN -- traversing and clearing pellets"),
  "alerting": (alerting_frames, "HEY -- one ghost, slow pulse"),
  "alerting2": (alerting2_frames, "STILL WAITING -- two ghosts, fast flash"),
  "alerting3": (alerting3_frames, "CORNERED -- four-ghost full-maze strobe"),
  "compacting": (compacting_frames, "BOARD CLEANUP -- dots compress to a power pellet"),
  "success": (success_frames, "BOARD CLEAR -- frightened ghosts and cherry bonus"),
  "error": (error_frames, "CAUGHT -- ghost collision and death burst"),
  "chilling": (chilling_frames, "ATTRACT MODE -- sleeping on an untouched board"),
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
