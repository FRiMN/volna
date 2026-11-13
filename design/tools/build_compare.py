#!/usr/bin/env python3
"""Build the design-variants comparison board from the three screenshots."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SCREENS = ROOT / "screens"
OUT = SCREENS / "compare.png"

VARIANTS = [
    ("A", "Dolphin Breeze", "референс-верный Dolphin: тот же хром, вид «Столбцы», диалог «Режим просмотра»", "variant-a.png"),
    ("B", "JetBrains Workbench", "файловый менеджер как IDE New UI: рейлы, панели, табы, инспектор, консоль, light/dark", "variant-b.png"),
    ("C", "Dolphin × JetBrains", "гибрид: шасси JetBrains + колонки по датам, Places, фильтр и зум Dolphin", "variant-c.png"),
]

W = 1600
PAD = 28
LABEL_H = 92
TITLE_H = 132


def load_font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            try:
                return ImageFont.truetype(c, size)
            except OSError:
                continue
    return ImageFont.load_default()


f_title = load_font(34, bold=True)
f_sub = load_font(17)
f_chip = load_font(20, bold=True)
f_label = load_font(26, bold=True)
f_desc = load_font(17)


def draw_text_fit(draw, text, x, y, font, fill, max_w):
    if draw.textlength(text, font=font) <= max_w:
        draw.text((x, y), text, font=font, fill=fill)
        return
    cut = text
    while cut and draw.textlength(cut + "…", font=font) > max_w:
        cut = cut[:-1]
    draw.text((x, y), cut + "…", font=font, fill=fill)


def main():
    shots = []
    for letter, name, desc, fname in VARIANTS:
        p = SCREENS / fname
        im = Image.open(p).convert("RGB")
        ratio = W / im.width
        im = im.resize((W, int(im.height * ratio)), Image.LANCZOS)
        shots.append((letter, name, desc, im))

    height = TITLE_H + sum(LABEL_H + im.height + 30 for *_, im in shots) + 40
    canvas = Image.new("RGB", (W + 2 * PAD, height), (12, 13, 16))
    d = ImageDraw.Draw(canvas)

    d.text((PAD, 36), "«Волна» — файловый менеджер: варианты дизайна", font=f_title, fill=(235, 238, 242))
    d.text((PAD, 84), "OpenDesign · 3 направления по референсам KDE Dolphin и JetBrains New UI", font=f_sub, fill=(150, 156, 166))

    y = TITLE_H
    accents = {"A": (108, 156, 196), "B": (88, 124, 240), "C": (110, 170, 230)}
    for letter, name, desc, im in shots:
        accent = accents.get(letter, (150, 200, 255))
        d.rounded_rectangle((PAD, y, PAD + 44, y + 32), radius=8, fill=accent)
        d.text((PAD + 14, y + 6), letter, font=f_chip, fill=(12, 13, 16))
        d.text((PAD + 58, y + 1), name, font=f_label, fill=(235, 238, 242))
        draw_text_fit(d, desc, PAD + 58, y + 36, f_desc, (150, 156, 166), W - 120)
        yy = y + LABEL_H
        d.rectangle((PAD - 2, yy - 2, PAD + im.width + 2, yy + im.height + 2), outline=(45, 48, 54))
        canvas.paste(im, (PAD, yy))
        y = yy + im.height + 30

    canvas.save(OUT, "PNG")
    print("saved", OUT, canvas.size)


if __name__ == "__main__":
    main()
