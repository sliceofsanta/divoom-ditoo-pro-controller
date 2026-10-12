"""Clawd: a flat terracotta desk companion for a native 16x16 LED screen.

Large body, four little feet, black eyes, one prop per action. Row zero stays
free for agent pips and row fifteen for the optional context gauge. Runtime
events choose the state; these frames animate its behaviour, not task progress.
"""

from mascot import blank, px, rect

BG = (18, 19, 25)
BODY = (213, 113, 82)
INK = (10, 9, 13)
CREAM = (255, 226, 175)
GOLD = (255, 202, 79)
CYAN = (87, 214, 228)
MINT = (84, 224, 164)
RED = (245, 83, 103)
PURPLE = (187, 153, 243)
STEEL = (108, 127, 149)
SCREEN = (38, 55, 74)
PAPER = (225, 225, 218)
COFFEE = (110, 67, 42)


def dots(g, points, color):
    for x, y in points:
        px(g, x, y, color)


def clawd(g, y=6, gaze=0, blink=False, mood="normal", arms="rest", squash=0, step=0):
    """Clawd's single-color body; four distinct feet, no costume or face panel."""
    top = y + squash
    bottom = y + 5
    rect(g, 3, top, 12, top, BODY)
    rect(g, 2, top + 1, 13, bottom, BODY)
    eyes = top + 2
    if blink:
        dots(g, ((5, eyes + 1), (6, eyes + 1), (9, eyes + 1), (10, eyes + 1)), INK)
    elif mood == "happy":
        dots(g, ((4, eyes + 1), (5, eyes), (6, eyes + 1),
                 (9, eyes + 1), (10, eyes), (11, eyes + 1)), INK)
    elif mood == "sad":
        dots(g, ((4, eyes), (5, eyes + 1), (10, eyes + 1), (11, eyes)), INK)
    else:
        for x in (5 + gaze, 10 + gaze):
            rect(g, x, eyes, x, eyes + 1, INK)
    if mood == "shock":
        px(g, 8, bottom - 1, INK)
    # Hands stay attached even when raised.
    if arms == "up":
        dots(g, ((0, top + 1), (1, top + 2), (2, top + 3),
                 (15, top + 1), (14, top + 2), (13, top + 3)), BODY)
    elif arms == "wave":
        rect(g, 0, top + 3, 1, top + 3, BODY)
        dots(g, ((14, top + 2), (15, top + 1), (15, top)), BODY)
    elif arms == "hug":
        dots(g, ((0, bottom - 1), (1, bottom), (14, bottom), (15, bottom - 1)), BODY)
    else:
        rect(g, 0, top + 3, 1, top + 3, BODY)
        rect(g, 14, top + 3, 15, top + 3, BODY)
    for i, x in enumerate((3, 5, 10, 12)):
        length = 1 if step and i % 2 == step % 2 else 2
        rect(g, x, bottom + 1, x, bottom + length, BODY)


def laptop(g, phase=0, failed=False, mode="working", code_phase=None):
    """Six by three pixels of terminal; marks show activity, never progress.

    code_phase can stop independently of the cursor during reading pauses.
    Keep the original bezel and base fixed in every state.
    """
    rect(g, 7, 9, 14, 13, STEEL)
    rect(g, 8, 10, 13, 12, SCREEN)
    rect(g, 5, 14, 15, 14, STEEL)
    if failed:
        mode = "error"
    if mode == "error":
        dots(g, ((9, 10), (11, 10), (10, 11), (9, 12), (11, 12)), RED)
    elif mode == "done":
        dots(g, ((9, 11), (10, 12), (11, 11), (12, 10)), MINT)
    elif mode == "waiting":
        # A slow brightness pulse, never full-screen flashing.
        color = (GOLD, (180, 127, 45), (117, 82, 37), (180, 127, 45))[phase//2 % 4]
        rect(g, 10, 10, 11, 12, color)
    elif mode == "idle":
        rect(g, 8, 10, 13, 12, (22, 29, 38))
        if phase % 24 in (0, 1, 2):
            rect(g, 9, 12, 10, 12, STEEL)
    else:
        code = phase if code_phase is None else code_phase
        beat = code % 16 if mode == "working" else 8
        # Two separated strokes stay legible: a blank row between code lines
        # avoids turning the tiny display into a solid cyan blob.
        upper = 3 if beat < 12 else 4
        rect(g, 8, 10, 7+upper, 10, CYAN)
        length = min(4, beat//3) if beat < 12 else 0
        if length:
            rect(g, 8, 12, 7+length, 12, CYAN)
        if phase % 6 < 3:
            px(g, 8+length, 12, CREAM)


def desk_frames(mode, count=16, delay=220, level=1, reason=None):
    """One recognisable desk scene for reading, attention, outcomes and rest."""
    frames = []
    for t in range(count):
        g = blank(BG)
        waiting, happy = mode == "waiting", mode == "done"
        celebrating = happy and count == 30
        wave = waiting and t % (8 if level == 1 else 4) in (1, 2)
        lift = int(celebrating and t < 18 and t % 6 in (2, 3))
        clawd(g, y=4-lift, gaze=0 if waiting or happy else 1,
              blink=t % 16 == 14 or (mode == "idle" and t >= 6),
              mood="happy" if happy else "sad" if mode == "error" else "normal",
              arms="up" if celebrating or (wave and level == 3) else "wave" if wave else "hug")
        laptop(g, t, mode=mode)
        # Resting paws do not fake typing while blocked or considering.
        dots(g, ((5, 12), (6, 12)), BODY)
        if waiting:
            if reason == "permission":
                dots(g, ((2, 1), (3, 1), (1, 2), (4, 2)), CREAM)
                rect(g, 1, 3, 4, 3, GOLD)
            elif reason == "question":
                dots(g, ((1, 1), (2, 1), (3, 1), (3, 2), (2, 3)), GOLD)
            elif reason == "plan":
                rect(g, 1, 1, 4, 3, PURPLE)
                rect(g, 2, 2, 3, 2, CREAM)
            else:
                px(g, 7, 1, GOLD if level < 3 else RED)
                px(g, 7, 3, GOLD if level < 3 else RED)
            if level >= 2:
                dots(g, ((0, 2), (15, 2)), GOLD)
            if level == 3:
                rect(g, 0, 1, 0, 4, RED)
                rect(g, 15, 1, 15, 4, RED)
        if celebrating:
            for x, seed in ((0, 2), (2, 6), (13, 1), (15, 7)):
                px(g, x, 1+(t+seed)%7, (MINT, GOLD, CYAN)[(t//3+seed)%3])
        frames.append(g)
    return frames, [delay] * count


def steam_mug(g, t=0):
    rect(g, 11, 10, 13, 13, CYAN)
    rect(g, 11, 10, 13, 10, COFFEE)
    dots(g, ((14, 11), (15, 11), (15, 12), (14, 13)), CYAN)
    if t % 6 < 4:
        dots(g, ((13, 8 - t % 3), (14, 7 - t % 3)), CREAM)


def bang(g, big=False, color=GOLD):
    rect(g, 7 if not big else 6, 1, 8 if not big else 9, 3, color)
    rect(g, 7, 5, 8, 5, color)


def question(g, color=GOLD):
    dots(g, ((6, 2), (7, 1), (8, 1), (9, 2),
             (8, 3), (7, 4), (7, 6)), color)


def heart(g, x, y):
    dots(g, ((x, y), (x + 2, y), (x, y + 1), (x + 1, y + 1),
             (x + 2, y + 1), (x + 1, y + 2)), RED)


def cursor(g, x, y):
    dots(g, ((x, y), (x, y + 1), (x + 1, y + 1),
             (x, y + 2), (x + 1, y + 2), (x + 2, y + 2),
             (x + 1, y + 3)), CREAM)


def thinking_frames():
    return desk_frames("thinking")


def working_frames():
    return workstation_frames()


def alert_frames(level):
    return desk_frames("waiting", delay=240 if level == 1 else 170 if level == 2 else 150, level=level)


def compacting_frames():
    frames = []
    for t in range(16):
        g = blank(BG)
        squeezing = 5 <= t < 12
        clawd(g, y=5, squash=int(squeezing), blink=squeezing, arms="hug")
        layers = 4 if t < 4 else 3 if t < 7 else 2 if t < 10 else 1
        for row in range(layers):
            y = 14 - row
            rect(g, 4 + row % 2, y, 11 - row % 2, y, PAPER if row % 2 else CYAN)
        if t >= 10:
            rect(g, 7, 13, 8, 14, PURPLE)
        rect(g, 3, 12 + int(squeezing), 4, 12 + int(squeezing), BODY)
        rect(g, 11, 12 + int(squeezing), 12, 12 + int(squeezing), BODY)
        frames.append(g)
    return frames, [180] * 16


def success_frames():
    return desk_frames("done", count=30, delay=200)


def error_frames():
    return desk_frames("error", count=30, delay=200)


def chilling_frames():
    return desk_frames("idle", count=24, delay=250)


def permission_frames():
    return desk_frames("waiting", reason="permission")


def question_frames():
    return desk_frames("waiting", delay=240, reason="question")


def plan_frames():
    return desk_frames("waiting", delay=230, reason="plan")


def headset(g, mic=True):
    rect(g, 3, 3, 12, 3, STEEL)
    rect(g, 2, 4, 3, 8, STEEL)
    rect(g, 12, 4, 13, 8, STEEL)
    if mic:
        rect(g, 12, 9, 14, 9, CYAN)
        rect(g, 10, 10, 13, 10, CYAN)


def meeting_frames():
    frames = []
    for t in range(16):
        g = blank(BG)
        clawd(g, y=5, arms="wave" if t in (4, 5, 6) else "rest", blink=t == 13)
        headset(g)
        for x in (6, 8, 10):
            rect(g, x, 2-int((t+x)%6 < 3), x, 2, CYAN)
        frames.append(g)
    return frames, [200] * 16


def busy_frames():
    frames = []
    for t in range(16):
        g = blank(BG)
        clawd(g, y=5, gaze=1, blink=t in (6, 14), arms="hug")
        headset(g, mic=False)
        # Do-not-disturb placard: a steady red bar, no conversational gesture.
        rect(g, 5, 11, 11, 14, SCREEN)
        rect(g, 6, 12, 10, 13, RED)
        frames.append(g)
    return frames, [300] * 16


def screensaver_frames():
    """Clawd meets a runaway cursor: track, boop, sneeze, love, coffee, nap."""
    frames = []
    for t in range(96):
        act, beat = divmod(t, 16)
        g = blank(BG)
        if act == 0:
            clawd(g, gaze=1 if beat < 8 else -1)
            cursor(g, 12-beat//2, 1)
        elif act == 1:
            clawd(g, mood="shock" if beat >= 8 else "normal", gaze=0)
            cursor(g, 5+min(2, beat//4), 1+min(3, beat//4))
        elif act == 2:
            clawd(g, y=5 if 5 <= beat < 10 else 6, blink=beat < 5,
                  squash=int(beat < 5), arms="up" if beat >= 5 else "rest", mood="shock")
            if beat >= 5:
                for x, offset in ((0, 1), (2, 3), (13, 0), (15, 5)):
                    px(g, x, 1+(beat+offset)%12, CYAN if x%2 else GOLD)
            else:
                cursor(g, 7, 4)
        elif act == 3:
            clawd(g, mood="happy", arms="up", y=6-int(beat in (4, 5, 10, 11)))
            heart(g, 6, 2-int(beat%8 >= 4))
        elif act == 4:
            clawd(g, blink=beat >= 5, arms="hug")
            steam_mug(g, beat)
        else:
            clawd(g, blink=beat < 12, gaze=1 if beat >= 12 else 0)
            if beat < 10:
                dots(g, ((2, 2), (3, 2), (3, 3), (2, 4), (3, 4)), CYAN)
            if beat >= 10:
                cursor(g, 15-(beat-10)//2, 1)
        frames.append(g)
    frames[-1] = [row[:] for row in frames[0]]
    return frames, [200] * 96


def off_frames():
    return [blank((0, 0, 0))], [500]


def workshop_frames():
    """A continuous 19.2-second workbench story, not a completion meter.

    One large Clawd and one persistent bench. Parts enter left and leave right;
    the big hammer, anticipation, recoil and inspection carry the motion.
    Rows zero and fifteen remain reserved for the live status overlays.
    """
    frames = []
    for t in range(96):
        act, beat = divmod(t, 16)
        hammer = act in (1, 2)
        swing = beat % 8
        impact = hammer and swing in (4, 5)
        windup = hammer and swing in (1, 2, 3)
        inspect = act == 3
        wipe = act == 4 and 4 <= beat <= 10
        g = blank(BG)
        clawd(g, y=3 + int(impact), gaze=-1 if act == 0 and beat < 7 else 1,
              blink=impact or (inspect and beat in (7, 8)) or (act == 4 and beat in (2, 3)),
              arms="hug", mood="shock" if act == 2 and swing == 6 else "normal")

        # The bench never changes position: a continuous, readable setting.
        rect(g, 1, 13, 14, 13, STEEL)
        dots(g, ((2, 14), (13, 14)), STEEL)
        rect(g, 3, 14, 12, 14, SCREEN)

        # A single gold workpiece, large enough to read as a solid object.
        bx, by = 7, 10
        if act == 0:
            bx = min(7, max(0, beat-3))
        elif inspect:
            by = 9 if 3 <= beat < 13 else 10
        elif act == 5:
            bx = 7 + max(0, beat-2)
        rect(g, bx, by, bx+2, by+2, GOLD)
        px(g, bx+1, by+1, COFFEE)
        if inspect:
            # Both hands lift the SAME part for a squint, no success symbol.
            dots(g, ((bx-1, by+1), (bx+3, by+1)), BODY)
            if 9 <= beat <= 11:
                px(g, bx+1, by, CREAM)
        elif act == 0:
            dots(g, ((max(0,bx-1),11), (max(0,bx-1),12)), BODY)

        if hammer:
            if impact:
                # Rotated hammer: substantial vertical head, horizontal haft.
                rect(g, 8, 8, 9, 10, CREAM)
                rect(g, 10, 9, 13, 9, COFFEE)
                rect(g, 13, 8, 14, 9, BODY)
                if swing == 4:
                    dots(g, ((5,10), (11,11)), CREAM)
            else:
                hy = 2 if windup else 5
                rect(g, 12, hy+2, 12, 9, COFFEE)
                rect(g, 10, hy, 14, hy+1, CREAM)
                rect(g, 13, 8, 14, 9, BODY)
            if act == 2 and swing == 6:
                # A tiny recoil wobble, instead of an explosion or error cue.
                dots(g, ((1,2), (2,1)), CYAN)
        else:
            # Hammer parks on the right edge of the bench between actions.
            rect(g, 11, 11, 14, 11, COFFEE)
            rect(g, 13, 10, 14, 12, CREAM)
            if wipe:
                # Hand wipes brow; a single sweat bead falls beside Clawd.
                rect(g, 11, 4, 14, 4, BODY)
                px(g, 14, 2 + (beat-4)//3, CYAN)
            elif act == 4 and beat >= 12:
                # A quick stretch, still wide awake and at the bench.
                dots(g, ((0,5), (1,6), (14,6), (15,5)), BODY)

        # The next part is fed in before the old part leaves the frame.
        if act == 5 and beat >= 10:
            nx = -3 + (beat-10)//2
            rect(g, nx, 10, nx+2, 12, GOLD)
        frames.append(g)
    frames[-1] = [row[:] for row in frames[0]]
    return frames, [200] * len(frames)


def workstation_frames():
    """The original working pose, extended into a calm 24-second typing loop.

    Preserve its silhouette and laptop position. Code scrolls in bursts and
    freezes during reading pauses; the cursor keeps blinking. No other scenes.
    """
    frames = []
    code_tick = 0
    for t in range(120):
        pause = 29 <= t <= 35 or 91 <= t <= 97
        pace = t if t < 64 or t >= 100 else t//2
        hand = 0 if pause else pace % 2
        g = blank(BG)
        clawd(g, y=4, gaze=0 if 70 <= t <= 75 else 1,
              blink=t in (10, 22, 34, 48, 49, 83, 96, 113, 114),
              arms="hug", step=1+hand)
        laptop(g, t, code_phase=code_tick)
        if not pause:
            code_tick += 1
        px(g, 5+hand, 12, BODY)
        px(g, 6, 13 if hand else 12, BODY)
        if t in (16, 17, 18, 54, 55, 56):
            dots(g, ((2, 2), (1, 3)), CYAN)
        frames.append(g)
    frames[-1] = [row[:] for row in frames[0]]
    return frames, [200] * len(frames)


def activity_frames(kind):
    """Tool-level actions: a consistent Clawd, one bold animated prop.

    Dots and moving marks indicate activity, never measured task completion.
    Both overlay rows stay clear, just as in the original nine states.
    """
    if kind == "reviewing":
        return desk_frames("thinking", delay=180)
    if kind in ("done", "taskdone"):
        return desk_frames("done", delay=180)
    if kind == "terminal":
        return workstation_frames()
    frames = []
    for t in range(16):
        g = blank(BG)
        clawd(g, y=3, gaze=1 if t % 8 < 4 else 0, blink=t == 14,
              arms="wave" if kind == "starting" else "hug",
              mood="happy" if kind in ("done", "taskdone") else "normal")
        if kind == "reading":
            rect(g, 2, 10, 7, 13, PAPER)
            rect(g, 9, 10, 14, 13, PAPER)
            rect(g, 8, 11, 8, 14, PURPLE)
            rect(g, 3, 11+t//6, 6, 11+t//6, STEEL)
            rect(g, 10, 11, 13, 11, STEEL)
        elif kind in ("searching", "reviewing"):
            if kind == "reviewing":
                rect(g, 2, 10, 7, 14, PAPER)
                rect(g, 3, 11, 6, 11, STEEL)
                rect(g, 3, 13, 5, 13, STEEL)
            x = 9 + (t//4 % 2)
            dots(g, ((x, 10), (x+1, 10), (x-1, 11), (x+2, 11),
                     (x-1, 12), (x+2, 12), (x, 13), (x+1, 13),
                     (x+2, 14), (x+3, 14)), GOLD)
        elif kind == "writing":
            rect(g, 3, 10, 11, 14, PAPER)
            rect(g, 4, 12, 5+t//4, 12, STEEL)
            x = 6+t//4
            dots(g, ((x, 12), (x+1, 11), (x+2, 10), (x+3, 9)), GOLD)
            px(g, x, 12, INK)
        elif kind == "terminal":
            laptop(g, t)
        elif kind == "testing":
            rect(g, 2, 10, 14, 14, SCREEN)
            for i in range(3):
                x = 3 + 4*i
                rect(g, x, 11, x+2, 13, STEEL)
                rect(g, x+1, 12, x+1, 12, CYAN if t//3 % 3 == i else SCREEN)
        elif kind == "building":
            for x,y in ((3,13), (7,13), (11,13), (5,10), (9,10)):
                rect(g, x, y, x+2, y+1, GOLD if y==13 else CYAN)
            rect(g, 7, 7 + min(t//4, 3), 9, 8 + min(t//4, 3), PURPLE)
        elif kind == "installing":
            rect(g, 4, 12, 12, 14, COFFEE)
            rect(g, 4, 11, 5, 13, GOLD)
            rect(g, 11, 11, 12, 13, GOLD)
            y = 8+t//4
            rect(g, 8, y, 8, y+1, CYAN)
            dots(g, ((7,y+1), (9,y+1), (8,y+2)), CYAN)
        elif kind == "planning":
            rect(g, 7, 10, 9, 11, PURPLE)
            rect(g, 8, 12, 8, 13, STEEL)
            rect(g, 3, 13, 12, 13, STEEL)
            rect(g, 2, 13, 4, 14, CYAN if t < 8 else STEEL)
            rect(g, 11, 13, 13, 14, GOLD if t >= 8 else STEEL)
        elif kind == "connecting":
            rect(g, 1, 12, 4, 12, STEEL)
            rect(g, 11, 12, 15, 12, STEEL)
            rect(g, 4, 11, 6, 13, CYAN)
            rect(g, 9, 11, 11, 13, CYAN)
            px(g, 7, 11+t//6, GOLD)
            px(g, 8, 13-t//6, GOLD)
        elif kind == "responding":
            rect(g, 4, 10, 14, 13, PAPER)
            dots(g, ((5,14), (6,14)), PAPER)
            for i in range(3):
                px(g, 6+i*3, 11, BODY if i == t//3 % 3 else STEEL)
        elif kind == "configuring":
            rect(g, 6, 10, 11, 14, STEEL)
            rect(g, 8, 11, 9, 13, SCREEN)
            for x,y in (((5,11),(12,13)) if t%8 < 4 else ((5,13),(12,11))):
                px(g, x, y, CYAN)
        elif kind == "cancelled":
            rect(g, 5, 11, 6, 14, GOLD)
            rect(g, 10, 11, 11, 14, GOLD)
        elif kind in ("done", "taskdone"):
            if kind == "taskdone":
                rect(g, 4, 10, 12, 14, SCREEN)
            dots(g, ((5,12), (6,13), (7,14), (8,13), (9,12), (10,11), (11,10)), MINT)
        elif kind == "starting":
            y = 12-int(t%8 < 4)
            heart(g, 7, y)
        frames.append(g)
    return frames, [180] * 16


FACES = {
    "thinking": (thinking_frames, "Thinking -- still code, resting paws and a blinking cursor"),
    "working": (working_frames, "Coding -- cyan code scrolls in typing bursts, with reading pauses"),
    "alerting": (lambda: alert_frames(1), "Hey -- a little wave and an exclamation"),
    "alerting2": (lambda: alert_frames(2), "Still waiting -- bigger wave, bigger exclamation"),
    "alerting3": (lambda: alert_frames(3), "Need you -- amber terminal, two hands and persistent red rails"),
    "compacting": (compacting_frames, "Tidying up -- squeeze loose pages into a bound bundle"),
    "success": (success_frames, "Nailed it -- green laptop check, six-second celebration and confetti"),
    "error": (error_frames, "Oops -- red laptop cross and sad eyes; six seconds"),
    "chilling": (chilling_frames, "Desk nap -- dim laptop with an occasional cursor"),
    "alert-permission": (permission_frames, "Permission -- closed padlock and a patient wave"),
    "alert-question": (question_frames, "Question -- amber cursor, question cue and a patient wave"),
    "alert-plan": (plan_frames, "Review my plan -- amber cursor and purple document cue"),
    "meeting": (meeting_frames, "In a meeting -- headset, microphone and voice bars"),
    "busy": (busy_frames, "Focus time -- headphones and a do-not-disturb placard"),
    "screensaver": (screensaver_frames, "The runaway cursor -- 19.2-second idle comedy"),
    "off": (off_frames, "Display off"),
}

for _name, _description in {
    "starting": "Hello -- wave and a little heart",
    "reading": "Reading -- scanning an open book",
    "searching": "Searching -- moving magnifying glass",
    "writing": "Editing -- pencil scribbles on a page",
    "terminal": "Terminal -- cyan code scrolls on the laptop",
    "testing": "Running checks -- scanning a test tray, not a result count",
    "building": "Building -- lowering a block onto a stack",
    "installing": "Installing -- parcels drop into a box",
    "reviewing": "Reviewing -- still code and a blinking cursor",
    "planning": "Planning -- considering two branches",
    "connecting": "External tool -- packets between two plugs",
    "responding": "Replying -- moving dots in a speech bubble",
    "configuring": "Setup -- turning a little gear",
    "taskdone": "Task milestone -- a green laptop check",
    "done": "Turn complete -- a quiet green laptop check",
    "cancelled": "Paused or denied -- amber pause bars",
}.items():
    FACES[_name] = (lambda name=_name: activity_frames(name), _description)

FACES["delegating"] = (workstation_frames, "Team working -- steady laptop scene, scrolling code and reading pauses; 24s")
