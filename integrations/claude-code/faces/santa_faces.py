"""Santa Claus, drawn and animated directly on the Ditoo's 16x16 grid.

One consistent red hat, peach face, white beard and little black boots. Props
stay below or beside the face. Each state communicates through a different
action; the alert ladder adds larger gestures and bells to the same pose.
"""

from mascot import blank, px, rect

BG = (12, 20, 28)
RED = (230, 51, 65)
RED_SHADE = (156, 30, 48)
WHITE = (255, 244, 221)
BEARD = (196, 216, 215)
SKIN = (255, 185, 138)
NOSE = (236, 114, 102)
INK = (9, 13, 20)
GOLD = (255, 201, 65)
GOLD_SHADE = (179, 108, 32)
GREEN = (34, 175, 128)
MINT = (92, 236, 171)
CYAN = (91, 201, 233)
PAPER = (239, 214, 164)
WRITING = (106, 93, 74)
SACK = (162, 96, 51)
SACK_LIGHT = (211, 151, 77)
COCOA = (89, 45, 38)


def dots(g, points, color):
    for x, y in points:
        px(g, x, y, color)


def santa(g, *, dy=0, expression="open", gaze=0, arms="rest", hat=0):
    """A twelve-column silhouette with face and beard visible in every pose."""
    def box(x0, y0, x1, y1, color):
        rect(g, x0, y0 + dy, x1, y1 + dy, color)

    def points(coords, color):
        dots(g, [(x, y + dy) for x, y in coords], color)

    # Round red coat, cuffs, black belt and two chunky boots.
    box(4, 9, 11, 13, RED)
    box(3, 10, 12, 12, RED)
    box(4, 13, 11, 13, RED_SHADE)
    box(4, 12, 11, 12, INK)
    box(7, 12, 8, 12, GOLD)
    box(4, 14, 6, 14, INK)
    box(9, 14, 11, 14, INK)
    box(4, 15, 6, 15, BEARD)
    box(9, 15, 11, 15, BEARD)

    # A broad, completely unoccluded face framed by beard and hat brim.
    box(4, 4, 11, 7, SKIN)
    points(((3, 5), (12, 5)), SKIN)
    box(3, 7, 4, 8, WHITE)
    box(11, 7, 12, 8, WHITE)
    box(4, 8, 11, 9, WHITE)
    box(5, 10, 10, 10, WHITE)
    box(6, 11, 9, 11, BEARD)
    points(((4, 9), (11, 9)), BEARD)
    box(7, 7, 8, 7, NOSE)

    # Eyes have fixed spacing; expressiveness comes from blinks and gaze.
    if expression in ("sleep", "happy"):
        eye_y = 6 if expression == "sleep" else 5
        box(5, eye_y, 6, eye_y, INK)
        box(9, eye_y, 10, eye_y, INK)
        if expression == "happy":
            points(((5, 6), (10, 6)), INK)
    elif expression == "worried":
        points(((5, 5), (6, 6), (9, 6), (10, 5)), INK)
    else:
        points(((5 + gaze, 5), (9 + gaze, 5),
                (5 + gaze, 6), (9 + gaze, 6)), INK)
    if expression in ("shock", "worried"):
        box(7, 9, 8, 9, INK)
    elif expression == "happy":
        points(((6, 8), (7, 9), (8, 9), (9, 8)), INK)

    # Bent hat with a swinging two-pixel pompom and thick white brim.
    box(5, 1, 9, 1, RED)
    box(4, 2, 11, 2, RED)
    box(4, 3, 12, 3, RED)
    box(4, 4, 11, 4, WHITE)
    box(11, 2 + hat, 12, 3 + hat, WHITE)

    if arms == "up":
        points(((2, 9), (2, 8), (13, 9), (13, 8)), RED)
        box(1, 6, 2, 7, WHITE)
        box(13, 6, 14, 7, WHITE)
    elif arms == "wave":
        box(2, 10, 3, 11, WHITE)
        box(12, 8, 13, 9, RED)
        box(13, 6, 14, 7, WHITE)
    elif arms == "hug":
        box(2, 10, 3, 11, RED)
        box(12, 10, 13, 11, RED)
        box(3, 11, 4, 12, WHITE)
        box(11, 11, 12, 12, WHITE)
    else:
        box(2, 10, 3, 11, RED)
        box(12, 10, 13, 11, RED)
        box(2, 12, 3, 12, WHITE)
        box(12, 12, 13, 12, WHITE)


def gift(g, x=5, y=11, ribbon=True, bow=True, broken=False):
    rect(g, x, y + 1, x + 5, y + 3, GREEN)
    rect(g, x, y, x + 5, y, MINT)
    if ribbon:
        rect(g, x + 2, y, x + 3, y + 3, GOLD)
    if bow:
        dots(g, ((x + 1, y - 1), (x + 4, y - 1)), GOLD)
    if broken:
        dots(g, ((x + 3, y), (x + 2, y + 1),
                 (x + 3, y + 2), (x + 2, y + 3)), INK)


def bell(g, x, y, tilt=0):
    px(g, x + 1 + tilt, y, GOLD_SHADE)
    rect(g, x + tilt, y + 1, x + 2 + tilt, y + 2, GOLD)
    rect(g, x - 1, y + 3, x + 3, y + 3, GOLD)
    px(g, x + 1 - tilt, y + 4, WHITE)


def thinking_frames():
    frames = []
    for i in range(12):
        g = blank(BG)
        santa(g, gaze=(0, 0, 1, 1, 0, 0)[i % 6],
              expression="sleep" if i == 9 else "open", arms="hug")
        # Scroll hangs clear of the eyes and beard; its pointer scans lines.
        rect(g, 8, 10, 14, 14, PAPER)
        rect(g, 7, 9, 13, 9, WHITE)
        rect(g, 9, 15, 15, 15, WHITE)
        rect(g, 10, 11, 13, 11, WRITING)
        rect(g, 10, 13, 12, 13, WRITING)
        px(g, 9, 11 + (i // 3 % 2) * 2, RED)
        rect(g, 7, 11, 8, 12, WHITE)
        frames.append(g)
    return frames, [200] * 12


def working_frames():
    frames = []
    # Wrap, tie, pat, slide the completed gift away; the next box enters.
    for i in range(16):
        g = blank(BG)
        santa(g, arms="hug", hat=int(i % 8 >= 4))
        if i < 12:
            gift(g, ribbon=i >= 4, bow=i >= 8)
            hand_y = 11 if i % 4 < 2 else 12
            rect(g, 3 + int(i >= 4), hand_y, 4 + int(i >= 4), hand_y, WHITE)
            rect(g, 10 - int(i >= 4), hand_y, 11 - int(i >= 4), hand_y, WHITE)
        else:
            offset = (i - 11) * 3
            gift(g, x=5 + offset)
            gift(g, x=-10 + offset, ribbon=False, bow=False)
        frames.append(g)
    return frames, [150] * 16


def alert_frames(level):
    frames = []
    for i in range(12):
        # A gesture, then a readable rest. No full-screen flashing.
        raised = i in ((2, 3, 4) if level == 1 else (1, 2, 3, 7, 8, 9))
        g = blank(BG)
        santa(g, arms="up" if level == 3 and raised else "wave" if raised else "rest",
              expression="shock" if level == 3 else "open",
              hat=int(raised), dy=-int(level == 3 and raised))
        bell(g, 13, 8 if raised else 10, tilt=-int(raised))
        if level >= 2:
            rect(g, 0, 1, 1, 4, GOLD if level == 2 else RED)
            rect(g, 0, 6, 1, 6, GOLD if level == 2 else RED)
        if level == 3:
            bell(g, 1, 8 if raised else 10, tilt=int(raised))
            if raised:
                dots(g, ((0, 0), (2, 0), (14, 0), (15, 2),
                         (0, 15), (15, 15)), GOLD)
        elif raised:
            dots(g, ((14, 6), (15, 7)), GOLD)
        frames.append(g)
    return frames, [250 if level == 1 else 180 if level == 2 else 150] * 12


def compacting_frames():
    frames = []
    for i in range(16):
        g = blank(BG)
        santa(g, arms="hug", expression="sleep" if i in (9, 10) else "open")
        # Open sack, drop a parcel inside, compress, tie the neck, release.
        squeezed = 9 <= i <= 13
        rect(g, 9 if squeezed else 8, 12, 14, 14, SACK)
        rect(g, 10 if squeezed else 9, 11, 13, 15, SACK)
        rect(g, 10, 12, 10, 14, SACK_LIGHT)
        rect(g, 10, 10, 13, 10, GOLD if i >= 12 else SACK_LIGHT)
        if i < 8:
            y = 8 + i // 2
            rect(g, 11, y, 14, min(y + 2, 12), GREEN)
            rect(g, 12, y, 12, min(y + 2, 12), GOLD)
        if squeezed:
            rect(g, 8, 12, 9, 13, WHITE)
            rect(g, 14, 12, 15, 13, WHITE)
        frames.append(g)
    return frames, [160] * 16


def success_frames():
    frames = []
    for i in range(30):
        g = blank(BG)
        # Two little hops, then an extended proud hold for the six-second event.
        hop = int(i in (3, 4, 5, 11, 12, 13))
        santa(g, expression="happy", arms="up", dy=-hop, hat=i % 2)
        gift(g, y=12 - hop)
        for x, seed in ((0, 0), (2, 6), (13, 3), (15, 9)):
            y = (i + seed) % 15
            if y < 11:
                px(g, x, y, (GOLD, CYAN, MINT)[(i // 4 + seed) % 3])
        frames.append(g)
    return frames, [200] * 30


def error_frames():
    frames = []
    for i in range(30):
        g = blank(BG)
        santa(g, expression="worried", arms="up" if 5 <= i < 10 else "rest")
        if i < 5:
            gift(g, broken=True)
        else:
            # The two halves stay separated, keeping failure visible at rest.
            rect(g, 3, 13, 6, 15, GREEN)
            rect(g, 9, 12, 12, 14, GREEN)
            rect(g, 5, 13, 5, 15, GOLD)
            rect(g, 10, 12, 10, 14, GOLD)
            dots(g, ((6, 12), (8, 14)), MINT)
        if 3 <= i <= 8:
            dots(g, ((1, 10), (2, 8), (14, 8), (15, 10)), RED)
        dots(g, ((0, 1), (2, 1), (1, 2), (0, 3), (2, 3)), RED)
        frames.append(g)
    return frames, [200] * 30


def chilling_frames():
    frames = []
    for i in range(16):
        g = blank(BG)
        santa(g, expression="sleep", arms="hug", hat=int(i in (6, 7, 8)))
        rect(g, 9, 11, 12, 14, CYAN)
        rect(g, 10, 11, 12, 11, COCOA)
        dots(g, ((13, 12), (14, 12), (14, 13), (13, 14)), CYAN)
        rect(g, 8, 12, 9, 13, WHITE)
        steam = i % 8
        if steam < 6:
            dots(g, ((13, 9 - steam // 2), (14, 8 - steam // 2)), BEARD)
        if i in (4, 5, 6, 7):
            dots(g, ((0, 2), (1, 2), (1, 3), (0, 4), (1, 4)), CYAN)
        frames.append(g)
    return frames, [300] * 16


def off_frames():
    return [blank((0, 0, 0))], [500]


FACES = {
    "thinking": (thinking_frames, "CHECKING THE LIST -- reading and considering"),
    "working": (working_frames, "GIFT WRAPPING -- wrap, tie, pat and deliver"),
    "alerting": (lambda: alert_frames(1), "A LITTLE DING -- one gentle bell"),
    "alerting2": (lambda: alert_frames(2), "STILL HERE -- raised bell and exclamation"),
    "alerting3": (lambda: alert_frames(3), "JINGLE ALARM -- two bells and big gestures"),
    "compacting": (compacting_frames, "PACKING THE SACK -- squeeze and tie"),
    "success": (success_frames, "SPECIAL DELIVERY -- six-second gift celebration"),
    "error": (error_frames, "OH DEER -- six-second broken-present reaction"),
    "chilling": (chilling_frames, "COCOA BREAK -- dozing with a warm mug"),
    "off": (off_frames, "blank display"),
}
