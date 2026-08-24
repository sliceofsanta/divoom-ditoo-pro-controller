"""Clawd, the Claude Code pixel crab, drawn for a 16x16 LED matrix.

The mascot stays Claude orange in every state so it reads as the same
character; the STATE is carried by the background wash, the pose, and the
motion. At this size colour is what you notice across a room and motion is what
you notice at a glance -- the silhouette only resolves up close.

Coordinates are (x, y) with the origin top-left, matching the display.
"""

SIZE = 16

# Claude's coral/terracotta, plus a darker tone for shading and the shell rim.
CLAWD = (217, 119, 87)
CLAWD_DARK = (150, 74, 52)
CLAWD_LIGHT = (245, 168, 133)
EYE_WHITE = (255, 240, 230)
EYE_DARK = (40, 18, 12)


def blank(bg):
  return [[bg] * SIZE for _ in range(SIZE)]


def px(grid, x, y, colour):
  if 0 <= x < SIZE and 0 <= y < SIZE:
    grid[y][x] = colour


def hline(grid, x0, x1, y, colour):
  for x in range(x0, x1 + 1):
    px(grid, x, y, colour)


def claw(grid, x, y, colour, rim, flip=False):
  """A 3x3 pincer. `flip` mirrors it for the right-hand side."""
  if not flip:
    hline(grid, x, x + 1, y, colour)
    px(grid, x + 2, y + 1, colour)
    px(grid, x + 1, y + 1, rim)
    hline(grid, x, x + 1, y + 2, colour)
  else:
    hline(grid, x + 1, x + 2, y, colour)
    px(grid, x, y + 1, colour)
    px(grid, x + 1, y + 1, rim)
    hline(grid, x + 1, x + 2, y + 2, colour)


def arm(grid, x0, x1, y, colour):
  hline(grid, x0, x1, y, colour)


def eyes(grid, y, style, body):
  """Eyes sit in the shell. `style` is open | closed | wide | down."""
  for ex in (5, 9):
    if style == "closed":
      hline(grid, ex, ex + 1, y, EYE_DARK)
    elif style == "wide":
      hline(grid, ex, ex + 1, y, EYE_WHITE)
      hline(grid, ex, ex + 1, y + 1, EYE_WHITE)
      px(grid, ex, y, EYE_DARK) if ex == 5 else px(grid, ex + 1, y, EYE_DARK)
    elif style == "down":
      hline(grid, ex, ex + 1, y, EYE_WHITE)
      px(grid, ex, y + 1, EYE_DARK)
      px(grid, ex + 1, y + 1, EYE_DARK)
    else:  # open
      hline(grid, ex, ex + 1, y, EYE_WHITE)
      px(grid, ex + 1, y, EYE_DARK) if ex == 5 else px(grid, ex, y, EYE_DARK)
    if style != "wide":
      # a shell pixel above keeps the eye seated in the body
      px(grid, ex, y - 1, body)
      px(grid, ex + 1, y - 1, body)


def shell(grid, top, colour, rim, light):
  """Rounded 10-wide carapace, 4 rows tall, top-left highlight."""
  hline(grid, 4, 11, top, rim)
  hline(grid, 3, 12, top + 1, colour)
  hline(grid, 3, 12, top + 2, colour)
  hline(grid, 4, 11, top + 3, rim)
  px(grid, 4, top, light)
  px(grid, 5, top, light)


def legs(grid, y, colour, splay=0):
  """Four little legs under the shell; `splay` widens the stance."""
  for x in (4, 6, 9, 11):
    px(grid, x, y, colour)
  if splay:
    px(grid, 3, y + 1, colour)
    px(grid, 12, y + 1, colour)
  else:
    px(grid, 4, y + 1, colour)
    px(grid, 11, y + 1, colour)


def draw(bg, body_y=7, claw_l=0, claw_r=0, eye="open", splay=0,
         colour=CLAWD, rim=CLAWD_DARK, light=CLAWD_LIGHT):
  """Compose one Clawd frame.

  body_y  top row of the shell (bob the whole crab by changing it)
  claw_l  vertical offset of the left claw; negative raises it
  claw_r  same for the right claw
  """
  grid = blank(bg)

  claw(grid, 0, body_y + claw_l, colour, rim, flip=False)
  claw(grid, 13, body_y + claw_r, colour, rim, flip=True)
  arm(grid, 2, 3, body_y + claw_l + 1, rim)
  arm(grid, 12, 13, body_y + claw_r + 1, rim)

  shell(grid, body_y, colour, rim, light)
  eyes(grid, body_y + 2, eye, colour)
  legs(grid, body_y + 4, rim, splay)
  return grid


def to_ascii(grid, bg):
  return ["".join("." if c == bg else "#" for c in row) for row in grid]
