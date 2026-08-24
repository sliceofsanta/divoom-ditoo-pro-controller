"""Claude's mascot, drawn for a 16x16 LED matrix.

Proportions follow the SVG it is built from: a stocky rectangular body over
FOUR legs, a hand either side, and eyes that shift about. The original is made
entirely of <rect> elements -- no paths, no curves -- which is the happy reason
it survives being squeezed onto 256 LEDs at all. Nothing here has to be
reinterpreted; it only has to be scaled down.

Source proportions: legs 11 units wide at x = 11, 32, 64, 85, each 26 tall
starting at y = 60, body pivoting about (53, 65), fill #DD775B. Scaled to a
16-wide grid that lands the legs on x = 2-3, 5-6, 9-10, 12-13 with the body
spanning 2..13 -- symmetric, which the original very nearly is.

Coordinates are (x, y), origin top-left, matching the display.
"""

SIZE = 16

BODY = (221, 119, 91)          # #DD775B, the mascot's own colour
BODY_DARK = (165, 82, 60)      # underside and legs
BODY_LIGHT = (245, 168, 140)   # top edge, so he reads as lit from above
EYE = (38, 16, 12)
EYE_SHINE = (255, 236, 224)

BODY_X0, BODY_X1 = 2, 13
LEGS = ((2, 3), (5, 6), (9, 10), (12, 13))


def blank(bg):
  return [[bg] * SIZE for _ in range(SIZE)]


def px(grid, x, y, colour):
  if 0 <= x < SIZE and 0 <= y < SIZE:
    grid[y][x] = colour


def rect(grid, x0, y0, x1, y1, colour):
  for y in range(y0, y1 + 1):
    for x in range(x0, x1 + 1):
      px(grid, x, y, colour)


def draw(bg, body_y=3, body_h=7, legs=(0, 0, 0, 0), hand_l=0, hand_r=0,
         gaze=0, blink=False, squash=0, body=BODY, dark=BODY_DARK,
         light=BODY_LIGHT):
  """Compose one frame.

  body_y   top row of the body; raise it to make him hop
  body_h   body height; `squash` shortens it and widens the stance instead
  legs     per-leg length in rows (0 = resting, +1 = extended, -1 = lifted)
  hand_l   vertical offset of each hand; negative raises it
  hand_r
  gaze     -1, 0 or +1 -- which way he is looking
  blink    eyes shut
  squash   1 flattens him a row, for the bottom of a hop
  """
  grid = blank(bg)
  top = body_y + squash
  height = body_h - squash
  bottom = top + height

  # Body block, with a lit top edge and a shaded underside.
  rect(grid, BODY_X0, top, BODY_X1, bottom, body)
  rect(grid, BODY_X0 + 1, top, BODY_X1 - 1, top, light)
  rect(grid, BODY_X0, bottom, BODY_X1, bottom, dark)

  # Eyes sit a third of the way down and shift with the gaze. One pixel wide
  # and two tall: a highlight pixel above reads as a second eye at this size.
  eye_y = top + max(2, height // 2 - 1)
  for ex in (5, 10):
    x = ex + gaze
    if blink:
      px(grid, x, eye_y + 1, EYE)
    else:
      px(grid, x, eye_y, EYE)
      px(grid, x, eye_y + 1, EYE)

  # Four legs under the body.
  for (lx0, lx1), extend in zip(LEGS, legs):
    length = 2 + extend
    if length <= 0:
      continue
    rect(grid, lx0, bottom + 1, lx1, bottom + length, dark if extend < 0 else body)

  # A hand either side. One pixel wide, hard against the outer edge, so the
  # column beside the body stays empty and they read as separate from it --
  # a 2px hand touches the body and the three merge into one bar.
  for hx, offset in ((0, hand_l), (15, hand_r)):
    hy = top + height // 2 + offset
    rect(grid, hx, hy, hx, hy + 1, body)
  return grid
