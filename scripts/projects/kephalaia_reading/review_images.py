"""Review images for direct visual inspection, rendered from the layers JSON: scan left, reading right, line for line.

usage: python review_images.py [PAGE ...]   (default: every page in layers/pages)
Writes data/kephalaia/review/keph_pNNN.jpg. Run layers.py first.
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

from model import IMAGES, OUT, REPO

ASSETS = Path(__file__).parent / "assets"
PAGES = OUT / "layers" / "pages"
REVIEW = REPO / "data" / "kephalaia" / "review"
Y0, Y1, X0, X1 = 105, 1915, 330, 1480
SCAN_H = 1300
K = SCAN_H / (Y1 - Y0)
APPARATUS = {"surplus": "{%s} surplus", "omitted": "⟨%s⟩ omitted", "added-above": "\\%s/ above the line", "sic": "%s sic",
             "expunged": "⟦%s⟧ expunged by the scribe"}

CSS = """
body { margin: 0; background: #fff; font-family: Cop, 'Segoe UI Historic', serif; color: #111; }
.sheet { position: relative; width: 1740px; padding: 0 0 18px; }
.bar { font: 15px Georgia, serif; padding: 10px 16px; background: #f3f1ec; border-bottom: 1px solid #ddd; }
.bar b { font-size: 17px; }
.body { position: relative; height: %dpx; }
.scan { position: absolute; left: 12px; top: 10px; height: %dpx; border: 1px solid #bbb; }
.col { position: absolute; top: 10px; left: %dpx; width: 820px; height: %dpx; }
.row { position: absolute; left: 0; right: 0; transform: translateY(-50%%); white-space: nowrap; font-size: 18px; line-height: 1; }
.no { display: inline-block; width: 34px; color: #999; font: 12px Georgia, serif; }
.ek .tx { margin-left: -14px; }
.ctr { text-align: center; }
.ctr .no { position: absolute; left: 0; }
.hd .tx { margin-left: 150px; }
.guide { position: absolute; left: -26px; width: 20px; border-top: 1px dotted #c33; }
.side { color: #555; font-size: 15px; }
.frame { border-top: 2px solid #111; border-bottom: 2px solid #111; padding: 1px 3px; }
.notes { margin: 6px 16px 0; font: 14px Georgia, Cop, serif; line-height: 1.45; }
.notes b { font-weight: normal; color: #777; }
.notes i { font-style: normal; color: #2a5d8f; }
.ed { font: italic 13px Georgia, serif; color: #2a5d8f; margin-left: 6px; }
"""


def ypx(y: float) -> float:
    return 10 + (y - Y0) * K


def page_html(lay: dict) -> str:
    stem = f"keph_p{lay['page']:03d}"
    crop = OUT / "review_tmp" / f"{stem}.jpg"
    crop.parent.mkdir(parents=True, exist_ok=True)
    Image.open(IMAGES / f"{stem}.jpg").convert("L").crop((X0, Y0, X1, Y1)).save(crop, quality=92)
    scan_w = int((X1 - X0) * K)
    esc = html.escape
    rows = [f'<div class="row side" style="top:{ypx(215):.0f}px;padding-left:34px">page number '
            f'<span class="frame">{esc(lay["page_number"]["leiden"])}</span> &nbsp;·&nbsp; running title '
            f'{esc(lay["running_head"]["leiden"])}</div>']
    margins = {}
    for m in lay["margin_numbers"]:
        margins.setdefault(m["line"], []).append(f'{m["side"]} {esc(m["leiden"])}')
    for line in lay["lines"]:
        y = ypx((line["zone"][1] + line["zone"][3]) / 2)
        cls = {"kephalaion-number": " ctr", "kephalaion-title": " hd"}.get(line["type"], "")
        cls += " ek" if line["ekthesis"] else ""
        side = (f' <span class="side">&nbsp; ‖ margin: {" · ".join(margins[line["n"]])}</span>'
                if line["n"] in margins else "")
        ed = "".join(f'<span class="ed">{esc(e["en"])}</span>' for e in lay["editorial"]
                     if e["line"] == line["n"] and e["id"] != "vacat")
        rows.append(f'<div class="row{cls}" style="top:{y:.0f}px"><span class="no">{line["n"]}</span>'
                    f'<span class="tx">{esc(line["leiden"])}</span>{ed}{side}</div>'
                    f'<div class="guide" style="top:{y:.0f}px"></div>')
    keph = " → ".join(str(k["n"]) for k in lay["kephalaia"])
    stats = (f'{len(lay["lines"])} lines · {len(lay["letters"])} letters · '
             f'{sum(l["status"] == "unclear" for l in lay["letters"])} unclear · '
             f'{sum(l["status"] == "restored" for l in lay["letters"])} restored · {len(lay["gaps"])} gaps · '
             f'{len(lay["strokes"])} strokes')
    notes = [f"<b>l. {c['line']}</b> " + esc(APPARATUS[c["type"]] % c["text"]) for c in lay["corrections"]]
    for a in lay["apparatus"]:
        where = {"header": "title", "bottom": "below"}.get(a["loc"], f"l. {a['loc']}")
        where += f" (printed {a['printed_loc']})" if a["printed_loc"] else ""
        body = " · ".join(filter(None, [esc(a["lem"]), " ¦ ".join(esc(x) for x in a["readings"]), esc(a["note"])]))
        notes.append(f"<b>{where}</b> <i>{esc(a['en'])}</i> {body}")
    notes += [f"<b>l. {n['line']}</b> <b>[{esc(n['category'] or '')}]</b> {esc(n['text'])}" for n in lay["notes"]]
    return f"""<section class="sheet">
<div class="bar"><b>Kephalaia, edition p. {lay['page']}</b> &nbsp;·&nbsp; kephalaion {keph} &nbsp;·&nbsp; {stats}</div>
<div class="body"><img class="scan" src="{crop.as_uri()}" style="width:{scan_w}px">
<div class="col" style="left:{12 + scan_w + 46}px">{''.join(rows)}</div></div>
<div class="notes">{'<br>'.join(notes) or '<b>no apparatus or notes</b>'}</div></section>"""


def main() -> None:
    files = [PAGES / f"keph_p{p}.json" for p in sys.argv[1:]] or sorted(PAGES.glob("keph_p*.json"))
    REVIEW.mkdir(parents=True, exist_ok=True)
    font = (ASSETS / "NotoSansCoptic-Regular.ttf").as_uri()
    css = CSS % (SCAN_H + 20, SCAN_H, 0, SCAN_H)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1740, "height": 1000}, device_scale_factor=1.4)
        for f in files:
            lay = json.loads(f.read_text(encoding="utf-8"))
            doc = (f"<!doctype html><html><head><meta charset='utf-8'><style>@font-face {{ font-family: Cop; "
                   f"src: url('{font}'); }}{css}</style></head><body>{page_html(lay)}</body></html>")
            tmp = OUT / "review_tmp" / f"{f.stem}.html"
            tmp.write_text(doc, encoding="utf-8")
            page.goto(tmp.as_uri())
            page.wait_for_load_state("networkidle")
            png = OUT / "review_tmp" / f"{f.stem}.png"
            page.query_selector("section.sheet").screenshot(path=str(png))
            out = REVIEW / f"{f.stem}.jpg"
            Image.open(png).convert("RGB").save(out, quality=85, optimize=True)
            print(out.relative_to(REPO), out.stat().st_size // 1024, "KB")
        browser.close()


if __name__ == "__main__":
    main()
