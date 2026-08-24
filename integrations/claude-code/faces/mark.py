"""Claude's starburst mark, drawn for a 16x16 LED matrix.

The mark is a radial burst -- tapered rays around a bright core -- in Claude's
coral orange. Radial forms are the rare thing that survives this resolution:
there is no silhouette to lose and the shape reads at any rotation, which is
what makes it animate well. Spin it and it reads as working; pulse it and it
reads as urgent; breathe it and it reads as idle.

Coordinates are (x, y) with the origin top-left, matching the display. Pixel
(i, j) is treated as having its centre AT (i, j), so the true centre of a 16x16
grid falls at (7.5, 7.5) -- between pixels. Rays are therefore plotted by
distance to pixel centres rather than by rounding a float: rounding makes the
vertical ray land a column off from its opposite (Python rounds halves to even,
and cos(pi/2) is a hair below zero rather than zero), which is visible as a
lopsided burst.
"""

import math

SIZE = 16
CX = 7.5
CY = 7.5

# Claude coral, plus tones for the core and the ray tips.
CORAL = (217, 119, 87)
CORAL_DEEP = (168, 78, 52)
CORAL_LIGHT = (245, 173, 138)
CORE = (255, 226, 205)

# How close a pixel centre must be to the ray to light up. Just over 0.5 so an
# axis-aligned ray straddling the centre lights both of its columns, keeping
# the burst symmetric; diagonals stay a single pixel wide.
_HIT = 0.58


def blank(bg):
  return [[bg] * SIZE for _ in range(SIZE)]


def px(grid, x, y, colour):
  if 0 <= x < SIZE and 0 <= y < SIZE:
    grid[y][x] = colour


def _plot(grid, fx, fy, colour):
  """Light every pixel whose centre is within _HIT of (fx, fy)."""
  for gy in (math.floor(fy), math.floor(fy) + 1):
    for gx in (math.floor(fx), math.floor(fx) + 1):
      if math.hypot(gx - fx, gy - fy) <= _HIT:
        px(grid, gx, gy, colour)


def ray(grid, angle, r0, r1, colour, tip=None):
  """One ray from r0 to r1. Stepped finer than a pixel so diagonals stay solid."""
  dx, dy = math.cos(angle), math.sin(angle)
  steps = max(1, int((r1 - r0) / 0.3))
  for i in range(steps + 1):
    r = r0 + (r1 - r0) * i / steps
    shade = tip if (tip and i >= steps - 1) else colour
    _plot(grid, CX + dx * r, CY + dy * r, shade)


def burst(grid, rotation=0.0, rays=8, r0=1.8, r1=6.6,
          colour=CORAL, tip=CORAL_LIGHT, core=CORE, core_size=2):
  for k in range(rays):
    ray(grid, rotation + k * (2 * math.pi / rays), r0, r1, colour, tip)
  if core and core_size:
    half = (core_size - 1) / 2.0
    for gy in range(SIZE):
      for gx in range(SIZE):
        if abs(gx - CX) <= half + 0.5 and abs(gy - CY) <= half + 0.5:
          px(grid, gx, gy, core)
  return grid


def draw(bg, rotation=0.0, rays=8, r0=1.8, r1=6.6,
         colour=CORAL, tip=CORAL_LIGHT, core=CORE, core_size=2):
  return burst(blank(bg), rotation, rays, r0, r1, colour, tip, core, core_size)
