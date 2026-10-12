"""Render the installed Clawd designs as a printable and animated reference."""
from pathlib import Path
from io import BytesIO
import json
import subprocess

from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output/pdf"
OUT.mkdir(parents=True, exist_ok=True)
FACES = ROOT / "integrations/claude-code/faces"
W, H = 842, 1191
MARGIN, GAP, CARD_H = 32, 14, 65
CARD_W = (W - 2 * MARGIN - 2 * GAP) / 3
PAPER, INK, MUTED, LINE = "#F6F2EA", "#292A2C", "#66645F", "#DCD5CA"
ACCENT = "#B75539"
FONTDIR = Path("/System/Library/Fonts/Supplemental")
for name, filename in [("Body", "Arial.ttf"), ("Bold", "Arial Bold.ttf"), ("Mono", "Andale Mono.ttf")]:
    pdfmetrics.registerFont(TTFont(name, str(FONTDIR / filename)))

GROUPS = [
    ("01", "THINKING + DOING", "One bold prop tells you the kind of work.", [
        ("starting", "Hello wave + heart", "Session starts or resumes."),
        ("thinking", "Still code + blinking cursor", "Considering; between actions."),
        ("reading", "Scanning an open book", "Reading files or task results."),
        ("searching", "Moving magnifying glass", "Searching files, web or tools."),
        ("planning", "Choosing between branches", "Planning or organizing tasks."),
        ("working", "Code scrolls in typing bursts", "General tool activity."),
        ("writing", "Pencil scribbles on paper", "Creating or editing files."),
        ("terminal", "Code scrolls on the laptop", "Running a shell command."),
        ("testing", "Light scans a test tray", "Running tests, lint or checks."),
        ("building", "Block drops onto a stack", "Building or compiling."),
        ("installing", "Arrow drops into a box", "Installing or updating packages."),
        ("reviewing", "Still code + blinking cursor", "Reviewing Git changes/history."),
        ("delegating", "Scrolling code + reading pauses", "Team working; a calm 24-second loop."),
        ("connecting", "Packets between two plugs", "Web fetch, MCP or network call."),
        ("responding", "Dots in a speech bubble", "Producing a reply."),
        ("configuring", "Little gear + moving lights", "Loading setup or config changes."),
        ("compacting", "Squeezing pages into a bundle", "Making room in conversation context."),
    ]),
    ("02", "NEEDS YOU", "Input requests take priority over ordinary work.", [
        ("alert-permission", "Closed padlock + patient wave", "Waiting for your permission."),
        ("alert-question", "Amber cursor + question cue", "Waiting for your answer."),
        ("alert-plan", "Amber cursor + document cue", "Waiting for plan review."),
        ("alerting", "Amber cursor + patient wave", "General request for attention."),
        ("alerting2", "Bigger, more frequent waves", "Still waiting after 60 seconds."),
        ("alerting3", "Two hands + red warning rails", "Still waiting after 5 minutes."),
    ]),
    ("03", "OUTCOMES", "A finished task is not always a finished turn.", [
        ("taskdone", "Green laptop check", "One task milestone finished."),
        ("done", "Happy face + green laptop check", "Short turn finished; shown for 3s."),
        ("success", "Laptop check + celebration", "Turn ends after 10+ minutes' work."),
        ("error", "Red laptop cross + sad eyes", "A tool or the turn failed."),
        ("cancelled", "Two amber pause bars", "Interrupted or permission denied."),
    ]),
    ("04", "REST + PRESENCE", "Presence scenes only fill an otherwise idle screen.", [
        ("chilling", "Dim laptop + sleepy eyes", "Idle and available."),
        ("meeting", "Headset + moving voice bars", "Calendar reports a meeting."),
        ("busy", "Headphones + red DND sign", "Your Focus mode is on; not tool work."),
        ("screensaver", "The runaway-cursor comedy", "Extended idle; default: 30 minutes."),
        ("off", "Completely black screen", "Display explicitly turned off."),
    ]),
]

def text(c, x, y, value, size=9, font="Body", color=INK):
    c.setFillColor(HexColor(color))
    c.setFont(font, size)
    c.drawString(x, y, value)

def fit(c, x, y, value, width, size=9, font="Body", color=INK):
    while pdfmetrics.stringWidth(value, font, size) > width:
        size -= .1
    assert size >= 7.5, (value, size)
    text(c, x, y, value, size, font, color)

def load_frames(name):
    frames, durations = [], []
    with Image.open(FACES / (name + ".gif")) as im:
        for i in range(im.n_frames):
            im.seek(i)
            frames.append(im.convert("RGB").copy())
            durations.append(im.info.get("duration", 100))
    return frames, durations

assets = {name: load_frames(name) for _, _, _, entries in GROUPS for name, _, _ in entries}
placements = []
pdf = OUT / "clawd-animation-cheat-sheet.pdf"
c = canvas.Canvas(str(pdf), pagesize=(W, H))
c.setTitle("Clawd - Ditoo animation cheat sheet")
c.setAuthor("Clawd / Ditoo controller")
c.setFillColor(HexColor(PAPER)); c.rect(0, 0, W, H, fill=1, stroke=0)
text(c, MARGIN, H-32, "DESK COMPANION / QUICK REFERENCE", 9, "Bold", ACCENT)
text(c, MARGIN, H-67, "What is Clawd up to?", 31, "Bold")
text(c, MARGIN, H-86, "32 animated scenes + display off  /  Divoom Ditoo Pro  /  native 16 x 16 artwork", 10, color=MUTED)
text(c, 656, H-32, "EDITION 08 OCT 2026", 8, "Mono", MUTED)

top = H - 116
for number, title, subtitle, entries in GROUPS:
    text(c, MARGIN, top, number, 10, "Mono", ACCENT)
    text(c, MARGIN+26, top, title, 10, "Bold")
    text(c, MARGIN+215, top, subtitle, 9, color=MUTED)
    c.setStrokeColor(HexColor(LINE)); c.setLineWidth(.65)
    c.line(MARGIN, top-8, W-MARGIN, top-8)
    row_top = top - 17
    for i, (name, visual, meaning) in enumerate(entries):
        x = MARGIN + (i % 3) * (CARD_W + GAP)
        y = row_top - (i // 3) * CARD_H - 48
        frames, _ = assets[name]
        # Representative beat: mid-gesture, with prop visible.
        pick = {"working": 17, "screensaver": 52, "success": 8, "error": 18,
                "alerting": 5, "alerting2": 5, "alerting3": 6}.get(name, 5)
        frame = frames[min(pick, len(frames)-1)]
        # Vector pixel blocks keep printed icons perfectly sharp.
        for py in range(16):
            for px in range(16):
                r,g,b = frame.getpixel((px,py))
                c.setFillColorRGB(r/255,g/255,b/255)
                c.rect(x+px*3, y+(15-py)*3, 3.02, 3.02, fill=1, stroke=0)
        placements.append((name, x, y, 48))
        tx, tw = x+58, CARD_W-58
        fit(c, tx, y+36, name, tw, 10, "Bold")
        fit(c, tx, y+21, visual, tw, 8.8)
        fit(c, tx, y+7, meaning, tw, 8.5, color=MUTED)
    top = row_top - ((len(entries)+2)//3)*CARD_H - 7

# Compact reference band: every colour is accompanied by a text label.
legend_top = top + 3
c.setFillColor(HexColor("#EAE3D8"))
c.roundRect(MARGIN-10, 37, W-2*MARGIN+20, legend_top-24, 8, fill=1, stroke=0)
text(c, MARGIN, legend_top-5, "READ THE LIGHTS", 10, "Bold", ACCENT)
text(c, MARGIN, legend_top-22, "TOP ROW", 8, "Bold")
text(c, MARGIN+66, legend_top-22, "Solo: travelling cyan dot = activity, not percentage. Parallel: fixed agent positions.", 8.5)
statuses = [("#1ECDF0", "Running"), ("#23AA41", "Finished"), ("#FFA00F", "Needs you"), ("#FF2323", "Failed")]
for i, (color, label) in enumerate(statuses):
    x = MARGIN+66+i*107
    c.setFillColor(HexColor(color)); c.rect(x, legend_top-37, 6, 6, fill=1, stroke=0)
    text(c, x+12, legend_top-37, label, 8.5)
text(c, MARGIN+66, legend_top-51, "7 individual slots + overflow marker. Clears at idle. Finished means stopped, not verified correct.", 8)
text(c, MARGIN, legend_top-67, "BOTTOM", 8, "Bold")
text(c, MARGIN+66, legend_top-67, "Optional context usage: green <60%, amber 60-84%, red 85%+. Not task progress.", 8.5)
text(c, MARGIN, legend_top-84, "KEYS", 8, "Bold")
text(c, MARGIN+66, legend_top-84, "Thinking: steady. Work: alternating effects. Waiting: faster. Finished: ripple. Error: two blinks.", 8.5)
text(c, MARGIN+66, legend_top-98, "Idle/presence: dark. Effects follow your chosen light pattern; exact RGB colours are not controlled.", 8)
text(c, MARGIN, legend_top-118, "SCREENSAVER", 8, "Bold")
text(c, MARGIN+84, legend_top-118, "Cursor chase > boop > sneeze > heart > coffee > nap. A 19.2-second loop.", 8.5)
text(c, MARGIN, legend_top-138, "TIMING NOTES", 8, "Bold")
text(c, MARGIN+84, legend_top-138, "Focus halves alert waits. Success/error loops are 6s; outcomes may stay visible while you are away.", 8)
text(c, MARGIN, 22, "Based on the current controller. Fast events can merge; props show activity, not measured completion.", 8, color=MUTED)
text(c, W-185, 22, "PRINT A3 / FIT TO A4", 8, "Mono", MUTED)
assert legend_top-138 > 40, legend_top
c.showPage(); c.save()

reader = PdfReader(pdf)
assert len(reader.pages) == 1
extracted = reader.pages[0].extract_text()
for name in assets:
    assert name in extracted, name

# The PNG is also the static backing for a genuinely animated companion sheet.
subprocess.run(["/opt/homebrew/bin/pdftoppm", "-png", "-r", "120", "-singlefile", str(pdf), str(OUT / "clawd-animation-cheat-sheet")], check=True)
base = Image.open(OUT / "clawd-animation-cheat-sheet.png").convert("RGB")
sx, sy = base.width/W, base.height/H
animated = []
preview_times = range(0, max(sum(delays) for _, delays in assets.values()), 200)
for ms in preview_times:
    sheet = base.copy()
    for name,x,y,size in placements:
        frames, durations = assets[name]
        phase = ms % sum(durations)
        index = 0
        while phase >= durations[index] and index < len(durations)-1:
            phase -= durations[index]; index += 1
        left, upper = round(x*sx), round((H-y-size)*sy)
        right, lower = round((x+size)*sx), round((H-y)*sy)
        icon = frames[index].resize((right-left, lower-upper), Image.Resampling.NEAREST)
        sheet.paste(icon, (left, upper))
    animated.append(sheet.quantize(colors=128, method=Image.Quantize.MEDIANCUT))
animated[0].save(OUT / "clawd-animation-cheat-sheet.gif", save_all=True, append_images=animated[1:], duration=200, loop=0, optimize=True, disposal=1)
with Image.open(OUT / "clawd-animation-cheat-sheet.gif") as check:
    assert check.n_frames == len(preview_times)
    assert check.size == base.size
print(json.dumps({"pdf":str(pdf), "states":len(assets), "pages":1, "image_size":base.size, "animated_frames":len(preview_times), "legend_top":legend_top}))
