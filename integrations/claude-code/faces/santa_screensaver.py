"""Santa versus the bottomless sack: a 25.6-second, 16x16 silent comedy.

Drag the sack in, tug at the knot, unleash a present fountain, get buried,
shake the presents off, enjoy cocoa, fall asleep, and discover the sack again.
The final frame matches the opening frame so the story loops without a cut.
"""

from mascot import blank, px, rect
from santa_faces import (
    BG, RED, WHITE, BEARD, GOLD, GREEN, MINT, CYAN,
    SACK, SACK_LIGHT, COCOA, santa, dots,
)


SCENES = (
    ("Heavy delivery", 0, 16),
    ("One stubborn knot", 16, 32),
    ("Present fountain!", 32, 48),
    ("Where did Santa go?", 48, 64),
    ("Shake it off", 64, 80),
    ("Earned cocoa", 80, 96),
    ("A tiny nap", 96, 112),
    ("Oh, another sack…", 112, 128),
)


def actor(g, dx=0, dy=0, **pose):
    """Translate the established Santa rig without resampling any pixels."""
    sprite = blank(BG)
    santa(sprite, dy=dy, **pose)
    for y, row in enumerate(sprite):
        for x, color in enumerate(row):
            if color != BG:
                px(g, x + dx, y, color)


def sack(g, x=8, y=10, wide=False, open_top=False, shake=0):
    width = 7 if wide else 5
    x += shake
    rect(g, x + 1, y, x + width - 1, 15, SACK)
    rect(g, x, y + 2, x + width, 14, SACK)
    rect(g, x + 1, y + 2, x + 2, 13, SACK_LIGHT)
    if open_top:
        rect(g, x, y, x + width, y, SACK_LIGHT)
        rect(g, x + 1, y + 1, x + width - 1, y + 1, BG)
    else:
        rect(g, x + 2, y - 1, x + width - 2, y, GOLD)
        dots(g, ((x + 1, y - 2), (x + width - 1, y - 2)), SACK_LIGHT)


def parcel(g, x, y, color=GREEN, bow=True):
    """Four-pixel box: saturated paper plus a contrasting ribbon."""
    rect(g, x, y, x + 3, y + 3, color)
    rect(g, x + 1, y, x + 1, y + 3, GOLD)
    rect(g, x, y + 1, x + 3, y + 1, GOLD)
    if bow:
        dots(g, ((x, y - 1), (x + 2, y - 1)), WHITE)


def cocoa(g, y=11, steam=0):
    rect(g, 9, y, 12, y + 3, CYAN)
    rect(g, 10, y, 12, y, COCOA)
    dots(g, ((13, y + 1), (14, y + 1), (14, y + 2), (13, y + 3)), CYAN)
    rect(g, 8, y + 1, 9, y + 2, WHITE)
    if steam < 3:
        dots(g, ((13, y - 2 - steam), (14, y - 3 - steam)), BEARD)


def snow(g, tick):
    # Only the quiet opening/closing scenes use ambient snow. The exact
    # 128-frame period preserves the seam, even for different flake speeds.
    for x, speed, start in ((0, 1, 2), (15, 2, 9), (2, 1, 12)):
        y = (start + tick * speed // 8) % 16
        px(g, x, y, BEARD)


def scene_frame(tick):
    g = blank(BG)
    act, t = divmod(tick, 16)

    if act == 0:
        # He pulls a visibly heavy sack in from the right, then gets a grip.
        snow(g, tick)
        actor(g, dx=-2, arms="hug", gaze=1, hat=(t // 2) % 2)
        x = 14 - min(6, t // 2)
        sack(g, x=x, y=10)
        rect(g, 10, 11, min(14, x + 2), 11, GOLD)
        rect(g, 9, 10, 10, 11, WHITE)
        if t % 4 < 2:
            rect(g, 2, 14, 3, 15, BG)

    elif act == 1:
        # Three exaggerated tugs and a long anticipatory pause.
        tug = t in (2, 3, 6, 7, 10, 11)
        actor(g, dx=-2, arms="hug", expression="sleep" if tug else "open",
              hat=int(tug))
        sack(g, x=7, y=10, wide=True, shake=int(tug))
        rect(g, 9, 9 if tug else 10, 11, 9 if tug else 10, WHITE)
        if tug:
            dots(g, ((1, 7), (0, 8)), CYAN)

    elif act == 2:
        actor(g, arms="up", expression="shock", dy=-int(t in (0, 1, 2)))
        sack(g, x=5, y=12, wide=True, open_top=True)
        # Different arcs produce a fountain around the face. Nothing crosses
        # the eyes; parcels use the two edges, not the middle of the head.
        arcs = ((1, 0, CYAN), (12, 3, GREEN), (0, 7, RED), (12, 10, MINT))
        for x, launch, color in arcs:
            age = t - launch
            if 0 <= age < 10:
                y = (11, 8, 5, 2, 0, 0, 2, 5, 8, 11)[age]
                parcel(g, x, y, color)

    elif act == 3:
        # The mound rises to his beard. A last parcel lands on his hat.
        actor(g, dy=2, expression="shock" if t < 8 else "worried", arms="up")
        for x, y, color in ((0, 12, RED), (4, 12, CYAN), (8, 12, GREEN),
                            (12, 12, CYAN), (0, 9, GREEN), (12, 9, RED)):
            parcel(g, x, y, color)
        if t >= 4:
            parcel(g, 6, min(0, t - 8), GREEN, bow=False)
        if t >= 11:
            # Two little waving mittens peeking out of the mountain.
            rect(g, 1, 8 - t % 2, 2, 8 - t % 2, WHITE)
            rect(g, 13, 8 - t % 2, 14, 8 - t % 2, WHITE)

    elif act == 4:
        # A springy hop sends the pile flying away in both directions.
        jump = (0, 1, 2, 2, 1, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0)[t]
        actor(g, dy=-jump, expression="happy", arms="up", hat=int(t % 4 < 2))
        if t < 8:
            for x, direction, color in ((0, -1, RED), (4, -1, CYAN),
                                         (8, 1, GREEN), (12, 1, CYAN)):
                parcel(g, x + direction * t * 2, 12 - min(t, 3), color)
        if t < 6:
            parcel(g, 6 + t * 2, -t, GREEN, bow=False)
        if t in (8, 9, 10, 11):
            dots(g, ((0, 3), (2, 1), (13, 1), (15, 3)), GOLD)

    elif act == 5:
        actor(g, expression="happy" if t < 5 else "sleep", arms="hug")
        # Lift, sip, hold, lower: the mug never hides Santa's eyes.
        lift = (0, 0, 0, 0, 1, 1, 2, 2, 2, 2, 1, 1, 0, 0, 0, 0)[t]
        cocoa(g, y=11 - lift, steam=(t // 2) % 4)

    elif act == 6:
        actor(g, expression="sleep", arms="hug", hat=int(t >= 8))
        cocoa(g, steam=(t // 2) % 4)
        if 3 <= t < 13:
            y = 5 - (t - 3) // 4
            dots(g, ((0, y), (1, y), (1, y + 1), (0, y + 2), (1, y + 2)), CYAN)

    else:
        # The sack sneaks back. Santa notices, puts the cup down and reaches
        # for it. Finish at the exact opening pose for a seamless restart.
        if t < 6:
            actor(g, expression="sleep" if t < 3 else "open", arms="hug", gaze=int(t >= 3))
            cocoa(g, y=11 + t // 2, steam=3)
            sack(g, x=17 - t // 2, y=10)
        elif t < 15:
            snow(g, tick)
            actor(g, dx=-min(2, (t - 5) // 2), arms="hug", gaze=1)
            sack(g, x=14, y=10)
            rect(g, 10, 11, 14, 11, GOLD)
            rect(g, 9, 10, 10, 11, WHITE)
        else:
            return scene_frame(0)
    return g


def build():
    return [scene_frame(t) for t in range(128)], [200] * 128
