"""Drawing primitives for the 16x16 status faces.

The design thesis: at 256 pixels a SYMBOL survives and a character does not.
A check mark, a cross and an exclamation are legible at a glance and need no
legend; a face at this size is a smudge you have to learn. So the states are
built from symbols, and the cleverness goes into using the whole panel rather
than into detail nobody can resolve.

The border ring is the trick worth knowing. A 16x16 panel has exactly 60 edge
pixels, which makes a natural progress track that costs none of the middle --
so a state can show BOTH what it is (the symbol) and how far along it is (the
ring) without the two fighting for space.
"""

SIZE = 16


def blank(bg):
  return [[bg] * SIZE for _ in range(SIZE)]


def put(grid, x, y, colour):
  if 0 <= x < SIZE and 0 <= y < SIZE:
    grid[y][x] = colour


def rect(grid, x0, y0, x1, y1, colour):
  for y in range(min(y0, y1), max(y0, y1) + 1):
    for x in range(min(x0, x1), max(x0, x1) + 1):
      put(grid, x, y, colour)


# --- the border ring -------------------------------------------------------

def ring_positions():
  """The 60 edge pixels, clockwise from the top-left corner."""
  out = []
  for x in range(SIZE):
    out.append((x, 0))
  for y in range(1, SIZE):
    out.append((SIZE - 1, y))
  for x in range(SIZE - 2, -1, -1):
    out.append((x, SIZE - 1))
  for y in range(SIZE - 2, 0, -1):
    out.append((0, y))
  return out


RING = ring_positions()


def ring(grid, colour, start=0, count=len(RING)):
  """Light `count` ring pixels beginning at `start`, wrapping around."""
  for i in range(count):
    x, y = RING[(start + i) % len(RING)]
    put(grid, x, y, colour)


def ring_gradient(grid, head, length, bright, dim):
  """A comet on the ring: brightest at the head, fading behind it. Reads as
  rotation far better than a single lit pixel, which just looks like a fault."""
  for i in range(length):
    x, y = RING[(head - i) % len(RING)]
    put(grid, x, y, bright if i < 2 else dim)


# --- strokes ---------------------------------------------------------------

def line_points(x0, y0, x1, y1):
  """Bresenham, returned as a path so an animation can reveal a prefix of it."""
  points = []
  dx = abs(x1 - x0)
  dy = -abs(y1 - y0)
  sx = 1 if x0 < x1 else -1
  sy = 1 if y0 < y1 else -1
  err = dx + dy
  x, y = x0, y0
  while True:
    points.append((x, y))
    if x == x1 and y == y1:
      break
    e2 = 2 * err
    if e2 >= dy:
      err += dy
      x += sx
    if e2 <= dx:
      err += dx
      y += sy
  return points


def thicken(points):
  """Widen a stroke to two pixels. A single-pixel diagonal breaks up into
  dashes on an LED grid; two pixels reads as a solid line."""
  out = []
  for x, y in points:
    out.append((x, y))
    out.append((x + 1, y))
  return out


def draw_path(grid, points, colour, upto=None):
  for i, (x, y) in enumerate(points):
    if upto is not None and i >= upto:
      break
    put(grid, x, y, colour)


# --- symbols, as paths so they can draw themselves on ----------------------

def check_path():
  """A tick: short stroke down-right, long stroke up-right."""
  short = line_points(3, 8, 6, 11)
  long = line_points(6, 11, 12, 4)
  return thicken(short + long)


def cross_path():
  """A cross, drawn as two strokes so it can appear one arm at a time."""
  a = line_points(3, 3, 12, 12)
  b = line_points(12, 3, 3, 12)
  return thicken(a), thicken(b)


def bang(grid, colour, x=7):
  """An exclamation mark: bar plus a detached dot."""
  rect(grid, x, 2, x + 1, 9, colour)
  rect(grid, x, 12, x + 1, 13, colour)


def dots(grid, colour, lit, y=7):
  """Three dots -- the universal "thinking". `lit` says how many are on."""
  for i in range(3):
    if i < lit:
      rect(grid, 2 + i * 5, y, 3 + i * 5, y + 1, colour)
