#!/usr/bin/env python3
"""Generate Super Claude Bros., a tiny 16x16 status game for Ditoo Pro.

Every Claude Code state is another scene in the same miniature platformer:

    thinking    Claude studies a level map without moving
    working     Claude runs through bricks, coins and a warp pipe
    alerting    a castle door waits for the player's key
    compacting  loose code blocks disappear into a warp pipe
    success     Claude grabs the flagpole under fireworks
    error       a Goomba-like bug bonks Claude and knocks off his cap
    chilling    Claude naps on a warp pipe beside a mushroom

The mascot becomes a real player sprite instead of occupying the entire panel.
That leaves enough room for platforms, enemies, machines and oversized props,
so every loop reads as an action rather than a collection of unrelated pixels.

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
from mascot import BODY, SIZE, draw_player
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


def hero(grid, x, y, **pose):
  """Claude in a red cap and blue overalls: mascot first, plumber second."""
  draw_player(grid, x, y, hat=CAP_RED, overalls=OVERALL_BLUE, **pose)


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
  """QUEST LOG: Claude stays put, reads a map and weighs two routes."""
  gazes = (1, 1, 0, 1, 1, 1, 0, 1, 1, 1)
  frames = []
  for i in range(10):
    grid = mascot.blank(BG_THINK)
    ground(grid, offset=0)

    # A huge parchment quest map gives "reading" a clear physical prop. The
    # cyan trail forks at the top; Claude's eyes and the two destinations pulse
    # slowly as he considers them, but his feet never move.
    mascot.rect(grid, 9, 3, 15, 11, mascot.BODY_DARK)
    mascot.rect(grid, 8, 3, 14, 10, CREAM)
    mascot.rect(grid, 9, 3, 15, 4, AMBER)
    mascot.rect(grid, 8, 9, 14, 10, AMBER)
    pixels(grid, ((9, 8), (10, 8), (10, 7), (11, 7), (11, 6), (12, 6)), CODE)
    pixels(grid, ((13, 5), (13, 7)), CODE_DARK)
    if i % 4 < 2:
      pixels(grid, ((13, 5), (14, 4), (14, 5)), MINT)
      mascot.px(grid, 13, 7, CODE_DARK)
    else:
      pixels(grid, ((13, 7), (14, 7), (14, 8)), PINK)
      mascot.px(grid, 13, 5, CODE_DARK)

    # Thought bubbles rise from the mascot toward a tiny question glyph.
    mascot.px(grid, 6, 5, CODE_DARK)
    mascot.px(grid, 7, 3 + i % 2, CODE)
    pixels(grid, ((7, 0), (8, 0), (9, 1), (8, 2), (8, 3)), CODE_LIGHT)

    draw_player(
      grid, 0, 7, jump=0, step=0,
      hand_l=1, hand_r=-1,
      gaze=gazes[i], blink=i == 6, expression="open"
    )
    frames.append(grid)
  return frames, [220, 220, 220, 260, 220, 220, 110, 260, 220, 280]


def chilling_frames():
  """SAVE POINT: Claude dozes beside a warm animated campfire."""
  stars = ((1, 1), (5, 2), (9, 0), (14, 3), (11, 5))
  frames = []
  for i in range(12):
    grid = mascot.blank(BG_CHILL)
    ground(grid, offset=0)
    for number, (x, y) in enumerate(stars):
      mascot.px(grid, x, y, CREAM if (i + number * 2) % 6 == 0 else CODE_DARK)

    # Crescent moon and a floating Z make this the attract/save screen, not a
    # generic idle pose.
    pixels(grid, ((13, 0), (14, 0), (12, 1), (13, 2), (14, 2)), CREAM)
    if i % 6 < 4:
      z_y = 4 - i % 4
      pixels(grid, ((6, z_y), (7, z_y), (7, z_y + 1), (6, z_y + 2), (7, z_y + 2)), CODE_LIGHT)

    # Logs and a two-tone flame alternate independently for organic flicker.
    pixels(grid, ((9, 12), (10, 11), (11, 12), (12, 11), (13, 12), (14, 12)), mascot.BODY_DARK)
    flame = (
      ((11, 11), (12, 10), (12, 9), (13, 11)),
      ((11, 11), (11, 10), (12, 11), (13, 10), (13, 9)),
      ((11, 11), (12, 10), (13, 11), (12, 8)),
    )[i % 3]
    pixels(grid, flame, HOT)
    pixels(grid, ((12, 11), (12, 10)), AMBER)
    if i % 4 == 0:
      mascot.px(grid, 12, 9, CREAM)

    draw_player(
      grid, 0, 7, step=0, hand_l=1, hand_r=1,
      expression="sleep", blink=True
    )
    frames.append(grid)
  return frames, [240] * 12


def working_frames():
  """CODE DUNGEON: run, raise hammer, smash wall, shower sparks."""
  frames = []
  for i in range(10):
    phase = i % 5
    grid = mascot.blank(BG_WORK)
    ground(grid, offset=i)

    # Tiny score/progress pips make the whole composition read as a game HUD.
    for pip in range(5):
      colour = CREAM if pip == (i // 2) % 5 else CODE_DARK
      mascot.rect(grid, 1 + pip * 3, 0, 2 + pip * 3, 0, colour)

    # The code wall is a large cyan dungeon obstacle, with cracks that appear
    # at impact and glowing fragments that fly into the sky.
    mascot.rect(grid, 11, 5, 15, 12, CODE_DARK)
    mascot.rect(grid, 12, 6, 15, 12, CODE)
    pixels(grid, ((12, 7), (14, 7), (13, 9), (15, 10), (12, 12)), CODE_LIGHT)
    if phase in (3, 4):
      pixels(grid, ((12, 6), (13, 7), (12, 8), (14, 9), (13, 10), (14, 11)), INK)
      pixels(grid, ((10, 4), (9, 6), (14, 3), (15, 1), (10, 9)), CODE_LIGHT)

    draw_player(
      grid, 1, 7, step=1 + i % 2 if phase == 0 else 0,
      hand_l=0, hand_r=-2 if phase in (1, 2) else 0,
      gaze=1, expression="happy" if phase == 4 else "open"
    )

    # A four-beat hammer arc: overhead, diagonal, impact, recoil.
    if phase == 1:
      pixels(grid, ((8, 8), (9, 7), (10, 6), (11, 5)), AMBER)
      mascot.rect(grid, 10, 3, 13, 5, CREAM)
    elif phase == 2:
      pixels(grid, ((8, 9), (9, 8), (10, 7), (11, 7)), AMBER)
      mascot.rect(grid, 12, 6, 14, 8, CREAM)
    elif phase == 3:
      mascot.rect(grid, 8, 10, 12, 10, AMBER)
      mascot.rect(grid, 13, 9, 15, 11, CREAM)
    elif phase == 4:
      pixels(grid, ((8, 9), (9, 8), (10, 7)), AMBER)
      mascot.rect(grid, 10, 5, 13, 7, CREAM)
    frames.append(grid)
  return frames, [105, 130, 95, 170, 110] * 2


def alerting_frames():
  """PLAYER NEEDED: Claude waves at a locked gate while its key pulses."""
  bobs = (0, 0, 1, 1, 0, 0, 1, 0)
  frames = []
  for i in range(8):
    hot = i in (2, 3, 6)
    grid = mascot.blank(BG_ALERT_HOT if hot else BG_ALERT_COOL)
    ground(grid, danger=False)
    gate(grid, glow=hot)
    key(grid, 5, 1 + bobs[i], CREAM if hot else AMBER)
    pixels(grid, ((4, 1), (4, 4), (9, 0), (9, 4)), HOT if hot else PINK)
    draw_player(
      grid, 0, 7, hand_l=1, hand_r=-2 if i % 2 else -1,
      gaze=1, expression="shock" if hot else "open"
    )
    frames.append(grid)
  return frames, [160, 160, 100, 210, 160, 160, 100, 220]


def success_frames():
  """LEVEL CLEAR: a treasure chest opens and Claude jumps through coins."""
  jumps = (0, 0, 1, 3, 4, 3, 1, 0, 0, 0)
  coin_seeds = ((7, 4), (10, 2), (13, 4), (6, 7), (12, 7))
  frames = []
  for i in range(10):
    grid = mascot.blank(BG_SUCCESS)
    ground(grid, offset=0)

    # Chest body stays planted while the lid snaps open on a held anticipation
    # frame, a classic arcade reward beat.
    mascot.rect(grid, 9, 9, 15, 12, mascot.BODY_DARK)
    mascot.rect(grid, 10, 10, 14, 11, AMBER)
    mascot.rect(grid, 12, 10, 13, 11, CREAM)
    if i < 2:
      mascot.rect(grid, 9, 7, 15, 9, AMBER)
      mascot.rect(grid, 10, 7, 14, 7, CREAM)
    else:
      mascot.rect(grid, 10, 5, 15, 6, AMBER)
      mascot.rect(grid, 11, 5, 14, 5, CREAM)
      mascot.rect(grid, 9, 8, 15, 9, INK)

    if i >= 2:
      for number, (x, y) in enumerate(coin_seeds):
        rise = (i - 2 + number) % 5
        coin(grid, x, max(0, y - rise), shine=(i + number) % 2 == 0)
      pixels(grid, ((8, 1 + i % 2), (15, 1), (6, 3), (14, 7)), MINT)

    draw_player(
      grid, 0, 7, jump=jumps[i], step=0,
      hand_l=-2 if i >= 2 else 0, hand_r=-2 if i >= 2 else 0,
      gaze=1, expression="happy" if i >= 2 else "open"
    )
    frames.append(grid)
  return frames, [180, 260, 100, 90, 190, 100, 120, 170, 180, 220]


def error_frames():
  """OUCH: a mischievous code bug bonks Claude and breaks a heart."""
  bug_x = (10, 9, 8, 8, 9, 10, 10, 10)
  recoil = (0, 0, 1, 2, 1, 0, 0, 0)
  frames = []
  for i in range(8):
    grid = mascot.blank(BG_ERROR if i not in (2, 3) else BG_ALERT_HOT)
    ground(grid, danger=True, offset=i)
    bug(grid, bug_x[i], 7, angry=i < 5, blink=i == 6)
    if i < 2:
      heart(grid, 4, 1, HOT)
    else:
      heart(grid, 4, 0, HOT, broken=True)
      pixels(grid, ((7, 6), (8, 5), (8, 7), (9, 6)), CREAM if i % 2 else AMBER)
    draw_player(
      grid, max(-1, 1 - recoil[i]), 7, jump=recoil[i],
      hand_l=1 if i >= 2 else 0, hand_r=1 if i >= 2 else 0,
      gaze=1, expression="x" if 2 <= i <= 5 else ("shock" if i == 1 else "open")
    )
    frames.append(grid)
  return frames, [170, 110, 90, 210, 120, 180, 200, 220]


def alerting2_frames():
  """PLAYER NEEDED, NOW: the same gate, but lava rises and Claude panic-hops."""
  jumps = (0, 2, 3, 1, 0, 3, 2, 0)
  frames = []
  for i in range(8):
    hot = i % 2 == 0
    grid = mascot.blank(BG_ALERT_HOT if hot else BG_ALERT_COOL)
    ground(grid, danger=True, offset=i * 2)
    gate(grid, glow=True)
    key(grid, 5, i % 2, CREAM if hot else HOT)
    pixels(grid, ((0, 1), (3, 0), (8, 4), (15, 1), (8, 7)), CREAM if hot else HOT)
    draw_player(
      grid, 0, 7, jump=jumps[i], step=0,
      hand_l=-2, hand_r=-2, gaze=1, expression="shock"
    )
    frames.append(grid)
  return frames, [95, 85, 110, 85, 95, 110, 85, 120]


def alerting3_frames():
  """BOSS ALERT: a giant bug guards the key while the whole level strobes."""
  frames = []
  for i in range(6):
    hot = i % 2 == 0
    grid = mascot.blank(HOT if hot else BG_ALERT_COOL)
    ground(grid, danger=True, offset=i)

    # The escalated alert swaps the door for its boss: one giant face, fangs,
    # claws and the stolen key. It is loud, but still mischievous rather than
    # grim, which keeps the desk companion cute.
    boss = CREAM if hot else PINK
    mascot.rect(grid, 8, 1, 15, 8, boss)
    mascot.rect(grid, 9, 0, 14, 0, boss)
    pixels(grid, ((7, 0), (8, 1), (15, 1), (7, 4), (15, 5)), boss)
    mascot.rect(grid, 9, 3, 14, 6, CREAM if not hot else AMBER)
    mascot.rect(grid, 9, 3, 10, 4, INK)
    mascot.rect(grid, 13, 3, 14, 4, INK)
    pixels(grid, ((10, 7), (11, 8), (13, 8), (14, 7)), INK)
    key(grid, 10, 9, INK if hot else CREAM)

    draw_player(
      grid, 0, 7, jump=1 if i in (1, 4) else 0,
      hand_l=-2, hand_r=-2, gaze=1,
      expression="shock", body=CREAM if hot else BODY,
      light=CREAM, dark=AMBER if hot else mascot.BODY_DARK
    )
    frames.append(grid)
  return frames, [90, 90, 90, 90, 90, 120]


def compacting_frames():
  """POWER CUBE: Claude pulls a lever while a crusher packs loose pixels."""
  frames = []
  drops = (0, 1, 3, 5, 6, 5, 3, 1)
  for i, drop in enumerate(drops):
    grid = mascot.blank(BG_THINK)
    ground(grid, offset=0)

    # Crusher chamber, loose code blocks, then a bright single power cube at
    # maximum compression.
    mascot.rect(grid, 9, 3, 9, 12, GROUND_LIGHT)
    mascot.rect(grid, 15, 3, 15, 12, GROUND_LIGHT)
    mascot.rect(grid, 9, 11, 15, 12, GROUND)
    if drop < 5:
      mascot.rect(grid, 10, 7, 11, 8, CODE)
      mascot.rect(grid, 13, 6, 14, 7, CODE_LIGHT)
      mascot.rect(grid, 12, 9, 13, 10, CODE_DARK)
    else:
      mascot.rect(grid, 11, 9, 14, 11, CODE)
      mascot.rect(grid, 12, 9, 13, 10, CREAM if i == 4 else CODE_LIGHT)
      pixels(grid, ((10, 8), (15, 8), (10, 10)), MINT)

    head_y = 2 + drop
    mascot.rect(grid, 11, 0, 13, max(0, head_y - 1), GROUND)
    mascot.rect(grid, 10, head_y, 14, min(10, head_y + 1), CREAM if i == 4 else AMBER)

    # Lever and knob visibly connect Claude's hand to the machine.
    mascot.rect(grid, 8, 9, 8, 12, AMBER)
    knob_y = 8 + (1 if i in (3, 4, 5) else 0)
    mascot.rect(grid, 7, knob_y, 8, knob_y + 1, HOT)
    draw_player(
      grid, 0, 7, step=1 + i % 2,
      hand_l=0, hand_r=-1 if i in (2, 3, 4, 5) else 0,
      gaze=1, expression="happy" if i == 4 else "open"
    )
    frames.append(grid)
  return frames, [150, 130, 110, 100, 260, 100, 120, 160]


def off_frames():
  black = (0, 0, 0)
  return [[[black] * SIZE for _ in range(SIZE)]], [500]


FACES = {
  "thinking": (thinking_frames, "QUEST LOG -- reading a map, considering two routes"),
  "working": (working_frames, "CODE DUNGEON -- hammering a glowing wall"),
  "alerting": (alerting_frames, "PLAYER NEEDED -- waiting at a locked gate"),
  "alerting2": (alerting2_frames, "PLAYER NEEDED -- lava rises at the gate"),
  "alerting3": (alerting3_frames, "BOSS ALERT -- giant bug stole the key"),
  "compacting": (compacting_frames, "POWER CUBE -- crushing loose pixels"),
  "success": (success_frames, "LEVEL CLEAR -- treasure and coin shower"),
  "error": (error_frames, "OUCH -- code bug broke a heart"),
  "chilling": (chilling_frames, "SAVE POINT -- napping by the campfire"),
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
