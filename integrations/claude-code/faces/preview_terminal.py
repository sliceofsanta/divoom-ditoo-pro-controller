"""Render a labeled comparison of the native laptop states, without resampling art."""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from clawd_faces import FACES

STATES = (
    ("delegating", "WORKING", "Code types and scrolls"),
    ("thinking", "THINKING", "Code holds; cursor blinks"),
    ("alerting", "NEEDS YOU", "Amber cursor pulses"),
    ("error", "ERROR", "Red cross; typing stops"),
    ("success", "FINISHED", "Green check + celebration"),
    ("chilling", "IDLE", "Dim screen; sleepy Clawd"),
)


def render(out):
    out.mkdir(parents=True, exist_ok=True)
    font_path = "/System/Library/Fonts/Supplemental/Arial.ttf"
    title = ImageFont.truetype(font_path, 15)
    body = ImageFont.truetype(font_path, 12)
    assets = {name: FACES[name][0]() for name, _, _ in STATES}
    sheets = []
    for ms in range(0, 24000, 200):
        sheet = Image.new("RGB", (624, 464), (246, 242, 234))
        draw = ImageDraw.Draw(sheet)
        for i, (name, label, meaning) in enumerate(STATES):
            frames, delays = assets[name]
            remaining = ms % sum(delays)
            index = 0
            while remaining >= delays[index]:
                remaining -= delays[index]
                index += 1
            native = Image.new("RGB", (16, 16))
            native.putdata([color for row in frames[index] for color in row])
            x, y = 24 + i % 3 * 204, 16 + i // 3 * 232
            sheet.paste(native.resize((160, 160), Image.Resampling.NEAREST), (x, y))
            draw.text((x, y+171), label, font=title, fill=(41, 42, 44))
            draw.text((x, y+193), meaning, font=body, fill=(94, 94, 94))
        sheets.append(sheet)
    sheets[8].save(out / "laptop-states.png")
    sheets[0].save(out / "laptop-states.gif", save_all=True,
                   append_images=sheets[1:], duration=200, loop=0, disposal=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    render(parser.parse_args().out)
