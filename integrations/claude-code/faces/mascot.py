"""Claude's mascot, drawn for a 16x16 LED matrix.

Proportions follow the SVG it is built from: a stocky rectangular body over
FOUR legs, a hand either side, and eyes that shift about. The original is made
entirely of <rect> elements -- no paths, no curves. At 16x16, however, a literal
reduction becomes an anonymous orange bar. This rig keeps the body, four legs,
and source colour, but exaggerates the readable features: a large warm face
plane, 2x2 eyes, chunky hands, and fake top/right planes that give the block
depth on the LED matrix.

Source proportions: legs 11 units wide at x = 11, 32, 64, 85, each 26 tall
starting at y = 60, body pivoting about (53, 65), fill #DD775B. Scaled to a
16-wide grid that lands the legs on x = 2-3, 5-6, 9-10, 12-13 with the body
spanning 2..13 -- symmetric, which the original very nearly is.

Animation reference:
https://tympanus.net/codrops/2026/05/05/reverse-engineering-claude-ais-mascot-animations-with-svg-and-gsap/

Coordinates are (x, y), origin top-left, matching the display.
"""

SIZE = 16

BODY = (221, 119, 91)          # #DD775B, the mascot's own colour
BODY_DARK = (165, 82, 60)      # underside and legs
BODY_LIGHT = (245, 168, 140)   # top edge, so he reads as lit from above
FACE = (255, 190, 148)         # oversized face plane: readability over realism
FACE_LIGHT = (255, 216, 178)
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
         gaze=0, blink=False, expression="open", squash=0, body=BODY,
         dark=BODY_DARK, light=BODY_LIGHT):
  """Compose one frame.

  body_y   top row of the body; raise it to make him hop
  body_h   body height; `squash` shortens it and widens the stance instead
  legs     per-leg length in rows (0 = resting, +1 = extended, -1 = lifted)
  hand_l   vertical offset of each hand; negative raises it; None hides it
  hand_r
  gaze     -1, 0 or +1 -- which way he is looking
  blink    eyes shut
  expression  open, happy, or x; blink takes precedence
  squash   1 flattens him a row, for the bottom of a hop
  """
  grid = blank(bg)
  top = body_y + squash
  height = body_h - squash
  bottom = top + height

  # Fake three-dimensional block. The top plane is inset and bright; the right
  # plane is two columns of shadow. Those three tones are what make the mascot
  # read as the chunky character in the reference instead of a flat rectangle.
  rect(grid, BODY_X0, top + 1, BODY_X1, bottom, body)
  rect(grid, BODY_X0 + 1, top, BODY_X1 - 2, top, light)
  px(grid, BODY_X0, top + 1, light)
  rect(grid, BODY_X1 - 1, top + 1, BODY_X1, bottom - 1, dark)
  rect(grid, BODY_X0, bottom, BODY_X1, bottom, dark)

  # The pale face panel deliberately consumes most of the front plane. At this
  # scale, facial readability matters more than literal source proportions.
  face_y0 = top + 2
  face_y1 = bottom - 1
  rect(grid, 3, face_y0, 10, face_y1, FACE)
  if face_y0 <= face_y1:
    rect(grid, 4, face_y0, 9, face_y0, FACE_LIGHT)

  # Two-by-two eyes survive the real LED diffusion and make expressions legible
  # from across a room. Gaze shifts the whole eye block within the face panel.
  eye_y = face_y0 + 1
  for eye_x in (4, 8):
    x = eye_x + gaze
    if blink:
      rect(grid, x, eye_y + 1, x + 1, eye_y + 1, EYE)
    elif expression == "happy":
      px(grid, x, eye_y + 1, EYE)
      px(grid, x + 1, eye_y, EYE)
    elif expression == "x":
      px(grid, x, eye_y, EYE)
      px(grid, x + 2, eye_y, EYE)
      px(grid, x + 1, eye_y + 1, EYE)
      px(grid, x, eye_y + 2, EYE)
      px(grid, x + 2, eye_y + 2, EYE)
    else:
      rect(grid, x, eye_y, x + 1, eye_y + 1, EYE)

  # Four legs under the body.
  for (lx0, lx1), extend in zip(LEGS, legs):
    length = 2 + extend
    if length <= 0:
      continue
    rect(grid, lx0, bottom + 1, lx1, bottom + length, dark if extend < 0 else body)

  # Chunky two-pixel hands. They intentionally touch the body when neutral and
  # break away into a clearer silhouette when raised.
  for hx0, hx1, offset in ((0, 1, hand_l), (14, 15, hand_r)):
    if offset is None:
      continue
    hy = top + height // 2 + offset
    rect(grid, hx0, hy, hx1, hy + 1, body)
  return grid


def draw_player(grid, x, y, jump=0, step=0, hand_l=0, hand_r=0,
                gaze=0, blink=False, expression="open", body=BODY,
                dark=BODY_DARK, light=BODY_LIGHT):
  """Draw the mascot as a tiny arcade player inside an existing scene.

  The portrait rig above is for close-ups. This seven-column player sprite is
  deliberately smaller so a 16x16 frame has room for a level, enemies and big
  readable props. He still keeps the source terracotta, cream face, blocky top
  plane and four feet, so he remains Claude rather than becoming a generic
  orange game blob.

  ``x, y`` is the top-left of the six-row body at rest. Positive ``jump``
  raises the whole sprite. ``step`` alternates which pair of feet is visible,
  producing a chunky two-frame arcade run.
  """
  top = y - jump

  # Seven-wide body with a bright top and dark right plane.
  rect(grid, x, top + 1, x + 6, top + 5, body)
  rect(grid, x + 1, top, x + 5, top, light)
  px(grid, x, top + 1, light)
  rect(grid, x + 6, top + 1, x + 6, top + 4, dark)
  rect(grid, x, top + 5, x + 6, top + 5, dark)

  # Five-wide, three-tall face panel. The expression patterns use its whole
  # area because single-pixel eyes disappear in LED bloom from across a room.
  rect(grid, x + 1, top + 2, x + 5, top + 4, FACE)
  rect(grid, x + 2, top + 2, x + 4, top + 2, FACE_LIGHT)
  if expression == "x":
    pixels = (
      (x + 1, top + 2), (x + 2, top + 3), (x + 1, top + 4),
      (x + 5, top + 2), (x + 4, top + 3), (x + 5, top + 4),
    )
    for ex, ey in pixels:
      px(grid, ex, ey, EYE)
  elif blink or expression == "sleep":
    rect(grid, x + 1, top + 3, x + 2, top + 3, EYE)
    rect(grid, x + 4, top + 3, x + 5, top + 3, EYE)
  elif expression == "happy":
    px(grid, x + 1, top + 3, EYE)
    px(grid, x + 2, top + 2, EYE)
    px(grid, x + 4, top + 2, EYE)
    px(grid, x + 5, top + 3, EYE)
  else:
    eye_shift = max(-1, min(1, gaze))
    px(grid, x + 2 + eye_shift, top + 3, EYE)
    px(grid, x + 4 + eye_shift, top + 3, EYE)
    if expression == "shock":
      px(grid, x + 3, top + 4, EYE)

  # Hands can rise, fall or disappear behind a prop.
  if hand_l is not None:
    hand_y = top + 3 + hand_l
    px(grid, x - 1, hand_y, body)
    px(grid, x, hand_y, body)
  if hand_r is not None:
    hand_y = top + 3 + hand_r
    px(grid, x + 6, hand_y, body)
    px(grid, x + 7, hand_y, body)

  # Four source-accurate feet when standing; alternating pairs while running.
  feet = (0, 2, 4, 6)
  for number, foot_x in enumerate(feet):
    if step and number % 2 != (step - 1) % 2:
      continue
    px(grid, x + foot_x, top + 6, body)
