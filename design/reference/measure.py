#!/usr/bin/env python3
"""Measurement helper for the «Волна» KDE Dolphin reference screenshots.

Run from the repo root:  python3 design/reference/measure.py
Prints the geometry (px) and sampled colours used in dolphin-spec.md.
All numbers are screenshot pixels (1:1 CSS px), not device px.

Helpers:
  runs_row/runs_col  - run-length colour scan of one scanline (transitions only)
  blocks             - 1-D projection -> [start,end] runs
  bright_bands       - row bands inside a box that contain "text-like" bright pixels
  color_bbox         - bounding box of an exact RGB value
  modal              - most common colours inside a box
"""
import numpy as np
from PIL import Image
from collections import Counter

REF = "reference/"
SHOT_A = REF + "Screenshot_20261113_183407.png"  # Columns view, size desc, no grouping
SHOT_B = REF + "Screenshot_20261113_183441.png"  # Columns view, grouped by mod. date
SHOT_C = REF + "Screenshot_20261113_183418.png"  # «Режим просмотра» dialog


def load(path):
    return np.asarray(Image.open(path).convert("RGB")).astype(int)


def hexc(c):
    return "#%02x%02x%02x" % (int(c[0]), int(c[1]), int(c[2]))


def runs_row(a, y, x0, x1, minrun=1):
    out, prev, s = [], tuple(a[y, x0]), x0
    for x in range(x0 + 1, x1):
        c = tuple(a[y, x])
        if c != prev:
            if x - s >= minrun:
                out.append((s, x - 1, hexc(prev), x - s))
            prev, s = c, x
    out.append((s, x1 - 1, hexc(prev), x1 - s))
    return out


def runs_col(a, x, y0, y1, minrun=1):
    out, prev, s = [], tuple(a[y0, x]), y0
    for y in range(y0 + 1, y1):
        c = tuple(a[y, x])
        if c != prev:
            if y - s >= minrun:
                out.append((s, y - 1, hexc(prev), y - s))
            prev, s = c, y
    out.append((s, y1 - 1, hexc(prev), y1 - s))
    return out


def blocks(v, thr=2, offset=0):
    out, s = [], None
    for i, x in enumerate(v):
        if x > thr and s is None:
            s = i
        elif x <= thr and s is not None:
            out.append((s + offset, i - 1 + offset))
            s = None
    if s is not None:
        out.append((s + offset, len(v) - 1 + offset))
    return out


def bright_bands(a, box, thr=330):
    x0, y0, x1, y1 = box
    lum = a[y0:y1, x0:x1].sum(axis=2)
    return [(y0 + s, y0 + e) for s, e in blocks((lum > thr).sum(axis=1), 0)]


def bright_bbox(a, box, thr=330):
    x0, y0, x1, y1 = box
    ys, xs = np.where(a[y0:y1, x0:x1].sum(axis=2) > thr)
    if not len(xs):
        return None
    return x0 + int(xs.min()), y0 + int(ys.min()), x0 + int(xs.max()), y0 + int(ys.max())


def color_bbox(a, color):
    m = np.all(a == np.array(color), axis=2)
    ys, xs = np.where(m)
    if not len(xs):
        return None
    return int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max()), int(m.sum())


def modal(a, box, minlum=0):
    x0, y0, x1, y1 = box
    sub = a[y0:y1, x0:x1].reshape(-1, 3)
    sub = sub[sub.sum(axis=1) >= minlum]
    return [(hexc(k), v) for k, v in Counter(map(tuple, sub)).most_common(4)]


def face_mask(a):
    """Folder-icon front-panel colour (exact #2d4f67)."""
    return (np.abs(a[:, :, 0] - 0x2D) < 6) & (np.abs(a[:, :, 1] - 0x4F) < 8) & (np.abs(a[:, :, 2] - 0x67) < 8)


def icons_x(a, y0, y1):
    return [(s, e, e - s + 1) for s, e in blocks(face_mask(a)[y0:y1, 331:1465].sum(axis=0), 5, 331)]


def shot_a(a):
    print("=" * 74)
    print("SHOT A  183407  Columns view / size desc / no grouping")
    print("=" * 74)
    b = color_bbox(a, (0x44, 0x43, 0x43))
    print("window frame #444343: x%d..%d y%d..%d -> window %dx%d" %
          (b[0], b[1], b[2], b[3], b[1] - b[0] + 1, b[3] - b[2] + 1))
    print("chrome bands (col x=1000):", runs_col(a, 1000, 50, 132, 2))
    print("chrome full width (col x=100):", runs_col(a, 100, 52, 132, 2))
    print("title '.cache — Dolphin' bbox:", bright_bbox(a, (600, 55, 1000, 85)))
    print("titlebar right controls bbox:", bright_bbox(a, (1340, 55, 1466, 85)))
    print("toolbar icon col blocks:", blocks((a[92:118, 64:1466].sum(axis=2) > 250).sum(axis=0), 1, 64))
    print("checked toggle #3c3b3b box (x192..217 y91..116):",
          "fill", hexc(a[100, 205]), "border", hexc(a[91, 205]))
    print("location field: top", hexc(a[89, 1000]), "fill", hexc(a[100, 1000]),
          "bottom", hexc(a[118, 1000]), "| field x329..1342 y89..118")
    print("path text bbox:", bright_bbox(a, (335, 96, 600, 116)))
    print("sidebar row y=500:", runs_row(a, 500, 64, 331, 1)[:8], "...")
    print("sidebar zebra #181616 rows:", [(s + 129, e + 129) for s, e in blocks(
        (np.all(a[129:790, 65:305] == [0x18, 0x16, 0x16], axis=2)).sum(axis=1), 100)])
    print("sidebar zebra #12120f rows:", [(s + 129, e + 129) for s, e in blocks(
        (np.all(a[129:790, 65:305] == [0x12, 0x12, 0x0F], axis=2)).sum(axis=1), 100)])
    print("sidebar scrollbar thumbs (x=315):", [r for r in runs_col(a, 315, 127, 790, 2) if r[2] == "#363534"])
    print("scene text bands, sidebar:", bright_bands(a, (90, 127, 300, 790)))
    print("view focus border:", hexc(a[128, 700]), "| fill", hexc(a[500, 900]))
    print("view box x330..1465 y128..790")
    print("icon x blocks (row1):", icons_x(a, 146, 224))
    print("icon vertical structure (x=380):", runs_col(a, 380, 128, 240, 1))
    print("item text lines (x=440..560):", bright_bands(a, (440, 140, 560, 225), 250))
    print("name colour:", modal(a, (441, 148, 470, 164), 300))
    print("size/date colour:", modal(a, (441, 170, 540, 200), 150))
    print("folder colours: face #2d4f67, tab", hexc(a[150, 360]), "bevel", hexc(a[152, 400]),
          "outline", hexc(a[200, 432]))
    print("h-scrollbar: ", [(s, e, c, w) for s, e, c, w in runs_row(a, 780, 331, 1465, 1) if c != "#0d0c0c"][:6])
    print("filter bar col x=1000:", runs_col(a, 1000, 788, 856, 1))
    print("status bar left text bbox:", bright_bbox(a, (331, 825, 600, 855), 250))
    print("status bar right: label", bright_bbox(a, (1060, 825, 1145, 855), 250),
          "| text", bright_bbox(a, (1340, 825, 1466, 855), 250))
    print("zoom slider row y=840:", [r for r in runs_row(a, 840, 1140, 1260, 1) if r[3] > 1])
    print("free-space bar #23333f:", color_bbox(a, (0x23, 0x33, 0x3F)))
    for name, col in (("window bg", "#181616"), ("chrome", "#282727"), ("view", "#0d0c0c"),
                      ("primary text", "#c5c9c5"), ("secondary text", "#8d9090"),
                      ("group/section grey", "#7f807c"), ("accent blue", "#23333f"),
                      ("salmon", "#c4746e"), ("border", "#444343")):
        print("  token %-20s %s" % (name, col))


def shot_b(b):
    print("=" * 74)
    print("SHOT B  183441  Columns view / grouped by modification date")
    print("=" * 74)
    print("group header text bboxes:",
          [bright_bbox(b, (x0, 135, x1, 160), 300) for x0, x1 in
           ((331, 470), (550, 700), (781, 930), (1015, 1160), (1249, 1450))])
    print("header colour:", modal(b, (340, 141, 420, 155), 150)[:3])
    print("column dividers (#292727 at y=500):",
          [(x, hexc(b[500, x])) for x in range(331, 1465) if hexc(b[500, x]) == "#292727"])
    print("divider extent (x=550):", runs_col(b, 550, 128, 790, 1))
    print("group header band:", bright_bands(b, (331, 129, 1465, 175), 250))
    print("icon x blocks (row1):", icons_x(b, 175, 253))
    print("icon row blocks col2 (x=565..650):", blocks(face_mask(b)[:, 565:651].sum(axis=1), 5))
    print("item text lines col1 row1:", bright_bands(b, (440, 170, 560, 260), 300))
    print("h-scrollbar:", [r for r in runs_row(b, 780, 331, 1465, 1) if r[2] != "#0d0c0c"][:6])


def dialog(c):
    print("=" * 74)
    print("SHOT C  183418  «Режим просмотра» dialog")
    print("=" * 74)
    b = color_bbox(c, (0x44, 0x43, 0x43))
    print("frame bbox: x%d..%d y%d..%d -> dialog %dx%d" %
          (b[0], b[1], b[2], b[3], b[1] - b[0] + 1, b[3] - b[2] + 1))
    print("titlebar col x=400:", runs_col(c, 400, 50, 130, 1))
    print("title 'Режим просмотра — Dolphin' bbox:", bright_bbox(c, (200, 55, 600, 85)))
    print("titlebar controls bbox:", bright_bbox(c, (620, 58, 710, 80)))
    print("row y=108:", runs_row(c, 108, 64, 710, 2))
    print("row y=146:", runs_row(c, 146, 64, 710, 2))
    print("combo1 box x285..396 y92..121 | combo2 x285..421 y130..159 | combo3 x432..606 y130..159")
    print("combo fill/border:", modal(c, (300, 98, 380, 116)), hexc(c[92, 330]), hexc(c[121, 330]))
    print("checkbox col x=295:", runs_col(c, 295, 180, 325, 1))
    print("checkbox rows y=196,224,252,280,308 (x283..305):",
          [runs_row(c, y, 283, 306, 1) for y in (196, 224, 252, 280, 308)])
    print("checkbox labels:", bright_bands(c, (303, 180, 700, 325), 300))
    print("param label:", bright_bbox(c, (66, 180, 285, 210), 300))
    print("expander row:", runs_row(c, 356, 64, 350, 2))
    print("buttons row y=380:", runs_row(c, 380, 64, 710, 2))
    print("button col x=450 (OK):", runs_col(c, 450, 360, 415, 1))
    print("OK fill/border:", modal(c, (415, 378, 485, 400)), hexc(c[372, 450]))
    print("Apply fill/border:", modal(c, (505, 378, 600, 400)), hexc(c[372, 550]))
    print("Cancel fill/border:", modal(c, (620, 378, 692, 400)), hexc(c[372, 650]))


def main():
    shot_a(load(SHOT_A))
    shot_b(load(SHOT_B))
    dialog(load(SHOT_C))


if __name__ == "__main__":
    main()
