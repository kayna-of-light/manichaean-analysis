"""Measurement tools for reading a Kephalaia page image. Every command reads the raw page extract.

usage:
  python measure.py zoom   PAGE NAME SCALE y0:y1:x0:x1 [...]   stacked crops -> temp/kephalaia_reading/crops/NAME.png
  python measure.py bands  PAGE                                text-line bands (y0 y1 centre)
  python measure.py dots   PAGE y0 y1 x0 x1                    small blobs: x/y/area (dot rows, sublinear dots)
  python measure.py assign PAGE y0 y1 x0 x1                    glyph boxes, '*' = blob below the glyph
  python measure.py strokes PAGE y0 y1 x0 x1                   glyph boxes with % covered by a supralinear stroke
  python measure.py reconcile PAGE                             dots per line on the image vs the EpiDoc reading
  python measure.py spaces PAGE                                blank runs >= 14 px per line vs spaces in the reading
  python measure.py joins  PAGE                                every line's x 880-1020 strip (where 4x halves meet)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from model import IMAGES, REPO, TEI_DIR

CROPS = REPO / "temp" / "kephalaia_reading" / "crops"
INK = 130


def gray(page: str) -> np.ndarray:
    return np.asarray(Image.open(IMAGES / f"keph_p{page}.jpg").convert("L"), dtype=np.float32)


def components(page, y0, y1, x0, x1):
    lab, _ = ndimage.label(gray(page)[y0:y1, x0:x1] < INK)
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        yield (x0 + sl[1].start, x0 + sl[1].stop, y0 + sl[0].start, y0 + sl[0].stop, int((lab[sl] == i).sum()))


def glyph_boxes(comps, small):
    boxes = sorted(c for c in comps if not small(c))
    merged = []
    for b in boxes:
        if merged and b[0] < merged[-1][1] - 2:
            m = merged[-1]
            merged[-1] = (m[0], max(m[1], b[1]), min(m[2], b[2]), max(m[3], b[3]), m[4] + b[4])
        else:
            merged.append(b)
    return merged


def zoom(page, name, scale, *specs):
    im = Image.open(IMAGES / f"keph_p{page}.jpg").convert("L")
    strips = []
    for spec in specs:
        y0, y1, x0, x1 = map(int, spec.split(":"))
        c = im.crop((x0, y0, x1, y1))
        strips.append((spec, c.resize((int(c.width * float(scale)), int(c.height * float(scale))), Image.LANCZOS)))
    sheet = Image.new("L", (max(c.width for _, c in strips) + 10, sum(c.height + 22 for _, c in strips)), 255)
    d, y = ImageDraw.Draw(sheet), 0
    for spec, c in strips:
        d.text((4, y + 4), spec, fill=0)
        sheet.paste(c, (5, y + 20))
        y += c.height + 22
    CROPS.mkdir(parents=True, exist_ok=True)
    sheet.save(CROPS / f"{name}.png")
    print(CROPS / f"{name}.png", sheet.size)


def bands(page):
    ink = (gray(page) < 140)[:, 480:1430].sum(axis=1) > 6
    start = None
    for y, r in enumerate(ink):
        if r and start is None:
            start = y
        elif not r and start is not None:
            if y - start > 12 and 150 < start < 2150:
                print(start, y, (start + y) // 2)
            start = None


def dots(page, y0, y1, x0, x1):
    found = sorted((c[0], c[2], c[4]) for c in components(page, y0, y1, x0, x1)
                   if c[4] <= 90 and c[1] - c[0] <= 11 and c[3] - c[2] <= 11)
    print(len(found), " ".join(f"{x}/{y}/{a}" for x, y, a in found))


def assign(page, y0, y1, x0, x1):
    comps = list(components(page, y0, y1, x0, x1))
    small = lambda c: c[4] <= 30 and c[1] - c[0] <= 9  # noqa: E731
    glyphs = glyph_boxes(comps, small)
    base = int(np.median([g[3] for g in glyphs]))
    out = []
    for g in glyphs:
        marks = [c for c in comps if small(c) and c[4] >= 6 and g[0] - 2 <= (c[0] + c[1]) / 2 <= g[1] + 2]
        out.append(f"{g[0]}-{g[1]}" + ("*" if any(c[2] >= base - 3 for c in marks) else "")
                   + ("^" if any(c[3] <= g[2] + 4 for c in marks) else ""))
    print("base", base, "|", " ".join(out))


def strokes(page, y0, y1, x0, x1):
    comps = list(components(page, y0, y1, x0, x1))
    bars = [c for c in comps if c[3] - c[2] <= 6 and c[1] - c[0] >= 8]
    glyphs = glyph_boxes([c for c in comps if c not in bars and c[4] > 30], lambda c: False)
    print("strokes", [(b[0], b[1]) for b in bars])
    print(" ".join(f"{g[0]}-{g[1]}" + (f"[{p}]" if (p := int(100 * sum(max(0, min(g[1], b[1]) - max(g[0], b[0]))
                                                                        for b in bars) / max(1, g[1] - g[0]))) else "")
                   for g in glyphs))


def reconcile(page):
    from layers import page_layers
    lay = page_layers(TEI_DIR / f"keph_p{page}.xml")
    g = gray(page)
    for line in lay["lines"]:
        y = (line["zone"][1] + line["zone"][3]) // 2
        lab, _ = ndimage.label(g[y - 22:y + 17, 470:1440] < INK)
        blobs = []
        for i, sl in enumerate(ndimage.find_objects(lab), 1):
            area = int((lab[sl] == i).sum())
            if 6 <= area <= 30 and sl[0].stop - sl[0].start <= 8 and sl[1].stop - sl[1].start <= 8 \
                    and y - 22 + sl[0].start >= y + 2:
                blobs.append((470 + sl[1].start, y - 22 + sl[0].start))
        want = sum(1 for l in lay["letters"] if l["line"] == line["n"] and l["status"] == "unclear") + sum(
            (gp["quantity"] or 0) for gp in lay["gaps"] if gp["line"] == line["n"])
        flag = "" if len(blobs) == want else "  <<< check: " + " ".join(f"{x}/{yy}" for x, yy in sorted(blobs))
        print(f"l.{line['n']:2} reading={want:2} image={len(blobs):2}{flag}")


def spaces(page):
    """Word division check. Blank runs >= 14 px in the x-height band (y-10..y+8) against the spaces of the
    Leiden line. Expected, explained differences: the legs of an enlarged letter (ⲡ, ⲙ) give one extra run;
    each dot of a dot run is separated by a run; an unmarked wide blank counts once; brackets can narrow a space below 14 px; margin numerals in title lines."""
    from layers import page_layers
    lay = page_layers(TEI_DIR / f"keph_p{page}.xml")
    g = gray(page)
    for line in lay["lines"]:
        y = (line["zone"][1] + line["zone"][3]) // 2
        ink = (g[y - 10:y + 8, 480:1440] < INK).any(axis=0)
        xs = np.where(ink)[0]
        runs = [(480 + a, int(b - a)) for a, b in zip(xs[:-1], xs[1:]) if b - a >= 14]
        want = len(line["leiden"].split()) - 1  # an unmarked blank (em space) counts as one separator
        flag = "" if len(runs) == want else "  <<< " + " ".join(f"{x}/{w}" for x, w in runs)
        print(f"l.{line['n']:2} reading={want:2} image={len(runs):2}{flag}")


def joins(page):
    """One sheet with each line's x 880-1020 strip at 2.2x, two columns. Letters at the edge of the left and
    right 4x halves are easily read twice or dropped; compare this sheet with the draft."""
    from layers import page_layers
    lay = page_layers(TEI_DIR / f"keph_p{page}.xml")
    im = Image.open(IMAGES / f"keph_p{page}.jpg").convert("L")
    strips = []
    for line in lay["lines"]:
        y = (line["zone"][1] + line["zone"][3]) // 2
        c = im.crop((880, y - 20, 1020, y + 16))
        strips.append((line["n"], c.resize((int(c.width * 2.2), int(c.height * 2.2)), Image.LANCZOS)))
    w, h = strips[0][1].width, strips[0][1].height + 16
    half = (len(strips) + 1) // 2
    sheet = Image.new("L", (2 * w + 20, half * h), 255)
    d = ImageDraw.Draw(sheet)
    for i, (n, c) in enumerate(strips):
        x0, y0 = (i // half) * (w + 20), (i % half) * h
        d.text((x0 + 2, y0), f"l.{n}", fill=0)
        sheet.paste(c, (x0, y0 + 14))
    CROPS.mkdir(parents=True, exist_ok=True)
    sheet.save(CROPS / f"joins_{page}.png")
    print(CROPS / f"joins_{page}.png", sheet.size)


if __name__ == "__main__":
    cmd, *args = sys.argv[1:]
    fn = {"zoom": zoom, "bands": bands, "dots": dots, "assign": assign, "strokes": strokes, "reconcile": reconcile,
          "spaces": spaces, "joins": joins}[cmd]
    fn(args[0], *(args[1:] if cmd in ("zoom",) else map(int, args[1:])))
