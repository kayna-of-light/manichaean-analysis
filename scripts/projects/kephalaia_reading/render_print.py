"""Render the reading print from the EpiDoc pages: page image left, Leiden text right, line for line.

usage: python render_print.py [PAGE ...]   (default: every page in data/kephalaia/epidoc)
"""
from __future__ import annotations

import html
import sys
from pathlib import Path

from lxml import etree
from PIL import Image
from playwright.sync_api import sync_playwright

from layers import page_layers
from model import IMAGES, OUT, TEI, TEI_DIR, XML, leiden, lines_of, read_tei

ASSETS = Path(__file__).parent / "assets"
PRINT = OUT / "print"
Y0, Y1, X0, X1 = 105, 1915, 330, 1480
K = 190 / (Y1 - Y0)
TOP = 10
APPARATUS = {"surplus": "{%s} surplus (dittography)", "omitted": "⟨%s⟩ omitted by the scribe",
             "added-above": "\\%s/ written above the line", "sic": "%s sic", "expunged": "⟦%s⟧ expunged by the scribe"}


def ymm(y: float) -> float:
    return TOP + (y - Y0) * K


def centre(zone) -> float:
    return (int(zone.get("uly")) + int(zone.get("lry"))) / 2


def page_html(path: Path) -> str:
    tree, atoms = read_tei(path)
    root = tree.getroot()
    lay = page_layers(path)
    zones = {z.get(f"{{{XML}}}id"): z for z in root.iter(f"{{{TEI}}}zone")}
    img = Image.open(IMAGES / f"{path.stem}.jpg").convert("L").crop((X0, Y0, X1, Y1))
    PRINT.mkdir(parents=True, exist_ok=True)
    img.save(PRINT / f"scan_{path.stem}.jpg", quality=92)
    w = (X1 - X0) * K
    keph = " → ".join(str(k["n"]) for k in lay["kephalaia"])
    rows = [f'<div class="row head" style="top:{ymm(133):.2f}mm">Kephalaia, edition p. {lay["page"]}'
            f' · kephalaion {keph}</div>']
    for role, zid, cls in (("page-number", "z-pagenum", "pno"), ("running-head", "z-header", "run")):
        part = leiden([a for a in atoms if a.role == role], html=True)
        inner = f'<span class="frame">{part}</span>' if role == "page-number" else part
        rows.append(f'<div class="row {cls}" style="top:{ymm(centre(zones[zid])):.2f}mm">{inner}</div>')
    by = lines_of(atoms)
    titles = []
    for line in lay["lines"]:
        n, y = line["n"], ymm((line["zone"][1] + line["zone"][3]) / 2)
        cls = {"kephalaion-number": " ctr", "kephalaion-title": " hd"}.get(line["type"], "")
        cls += " ek" if line["ekthesis"] else ""
        text = leiden(by[n], html=True)
        if line["type"] == "kephalaion-title":
            titles.append(text)
        rows.append(f'<div class="row{cls}" style="top:{y:.2f}mm"><span class="no">{n}</span>'
                    f'<span class="tx">{text}</span></div><div class="guide" style="top:{y:.2f}mm"></div>')
    widest = max(titles, key=lambda t: len(etree.fromstring(f"<x>{t}</x>").xpath("string()")), default="")
    for z in {m["line"]: m for m in lay["margin_numbers"]}:
        left = leiden([a for a in atoms if a.role == "margin-left" and a.line == z], html=True)
        right = leiden([a for a in atoms if a.role == "margin-right" and a.line == z], html=True)
        y = ymm(centre(zones[f"z{z}-left"]))
        rows.append(f'<div class="row marg" style="top:{y:.2f}mm"><span class="ml">{left}</span>'
                    f'<span class="ghost">{widest}</span><span class="mr">{right}</span></div>')
    app = [f"{c['line']} " + APPARATUS[c["type"]] % c["text"] for c in lay["corrections"]]
    if app:
        rows.append(f'<div class="row foot" style="top:{ymm(1862):.2f}mm">{html.escape(" · ".join(app))}</div>')
    return f"""
<section class="sheet">
  <img class="scan" src="scan_{path.stem}.jpg" style="width:{w:.2f}mm">
  <div class="col" style="left:{8 + w + 6:.2f}mm">{''.join(rows)}</div>
</section>"""


def legend_html(files: list[Path]) -> str:
    notes = ""
    for f in files:
        lay = page_layers(f)
        items = [f"<li>{html.escape(a['loc'])}: <i>{html.escape(a['en'])}</i> "
                 + html.escape(" · ".join(filter(None, [a["lem"], " ¦ ".join(a["readings"]), a["note"]]))) + "</li>"
                 for a in lay["apparatus"]]
        items += [f"<li>l. {n['line']} [{html.escape(n['category'] or '')}]: {html.escape(n['text'])}</li>"
                  for n in lay["notes"]]
        if items:
            notes += f"<h3>p. {lay['page']}</h3><ul>" + "".join(items) + "</ul>"
    pages = ", ".join(str(page_layers(f)["page"]) for f in files)
    return f"""
<section class="sheet legend">
  <h1>Kephalaia of the Teacher: pages {pages}</h1>
  <p class="sub">Polotsky/Böhlig edition, read from the page images. Each transcription line sits at the height of the
  printed line it renders. Source: <code>data/kephalaia/epidoc/</code> (EpiDoc TEI); analysis tables:
  <code>output/projects/kephalaia_reading/layers/</code>.</p>
  <div class="cols">
  <div>
  <h2>Conventions</h2>
  <table>
    <tr><th>Leiden</th><th>EpiDoc</th><th>meaning</th></tr>
    <tr><td>[ⲁⲃⲅ]</td><td>&lt;supplied reason="lost"&gt;</td><td>lost, restored by the editors</td></tr>
    <tr><td>[....]</td><td>&lt;gap reason="lost" quantity="4"&gt;</td><td>lost, one dot per letter</td></tr>
    <tr><td>....</td><td>&lt;gap reason="illegible"&gt;</td><td>traces of illegible letters</td></tr>
    <tr><td>ⲁ̣</td><td>&lt;unclear&gt;</td><td>uncertain letter</td></tr>
    <tr><td>⟨ⲁ⟩</td><td>&lt;supplied reason="omitted"&gt;</td><td>omitted by the scribe</td></tr>
    <tr><td>{{ⲁ}}</td><td>&lt;surplus&gt;</td><td>superfluous (dittography)</td></tr>
    <tr><td>\\ⲁ/</td><td>&lt;add place="above"&gt;</td><td>written above the line</td></tr>
    <tr><td>ⲁ</td><td>&lt;sic&gt;</td><td>kept although judged an error (apparatus)</td></tr>
    <tr><td>(?)</td><td>@cert="low"</td><td>uncertain restoration</td></tr>
    <tr><td>⟦ⲁ⟧</td><td>&lt;del rend="expunction"&gt;</td><td>expunged by the scribe</td></tr>
    <tr><td>[---] · ---</td><td>&lt;gap extent="unknown" ana="#ed.…"&gt;</td><td>editors' statement (destroyed, illegible, traces …), extent not counted</td></tr>
    <tr><td>[------]</td><td>&lt;gap quantity="1" unit="line"&gt;</td><td>the whole line</td></tr>
    <tr><td><span class="vac">vac.</span></td><td>&lt;space/&gt;</td><td>blank in the manuscript</td></tr>
    <tr><td>ⲛ̄ · ⲙ̅ⲛ̅</td><td>&lt;hi rend="supraline"&gt;</td><td>stroke over one letter · over several (≥ half a letter's width)</td></tr>
    <tr><td>ⲥ̀</td><td>@rendition="#oblique"</td><td>stroke printed obliquely</td></tr>
    <tr><td>ⲓ̈</td><td>&lt;hi rend="diaeresis"&gt;</td><td>diaeresis</td></tr>
    <tr><td><span class="big">ⲡ</span></td><td>&lt;hi rend="large"&gt;, &lt;lb rend="ekthesis"&gt;</td><td>enlarged letter; outdented line</td></tr>
    <tr><td>ⲙ̅ⲅ̅</td><td>&lt;num value="43"&gt;, &lt;milestone unit="kephalaion"&gt;</td><td>numeral; start of a kephalaion</td></tr>
    <tr><td>&gt;· ·&lt; :—</td><td>&lt;g type="diple"&gt; …</td><td>printed signs</td></tr>
  </table>
  </div>
  <div>
  <h2>Apparatus and transcriber's notes</h2>{notes}
  <h2>Verification</h2>
  <p>Letters read by eye from 1.6–8× zooms. Gap counts, every sublinear dot and every stroke extent measured on the image;
  undotted ϩ/ϥ/ϣ/ⲣ used as controls for descender ends. The EpiDoc round trip is checked against the reading drafts.
  Remaining risk: a missed or extra stroke over a single letter, or a diaeresis.</p>
  </div>
  </div>
</section>"""


CSS = (ASSETS / "print.css").read_text(encoding="utf-8")


def main() -> None:
    files = [TEI_DIR / f"keph_p{p}.xml" for p in sys.argv[1:]] or sorted(TEI_DIR.glob("keph_p*.xml"))
    PRINT.mkdir(parents=True, exist_ok=True)
    font = (ASSETS / "NotoSansCoptic-Regular.ttf").as_uri()
    doc = (f"<!doctype html><html><head><meta charset='utf-8'><style>@font-face {{ font-family: Cop; src: url('{font}'); }}"
           f"{CSS}</style></head><body>{legend_html(files)}{''.join(page_html(f) for f in files)}</body></html>")
    html_path = PRINT / "reading.html"
    html_path.write_text(doc, encoding="utf-8")
    pdf = PRINT / ("kephalaia_p" + "-".join(f.stem[6:] for f in files) + ".pdf")
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1123, "height": 794}, device_scale_factor=2)
        page.goto(html_path.as_uri())
        page.wait_for_load_state("networkidle")
        page.pdf(path=str(pdf), prefer_css_page_size=True, print_background=True)
        for i, el in enumerate(page.query_selector_all("section.sheet")):
            el.screenshot(path=str(PRINT / f"preview_{i}.png"))
        browser.close()
    print(pdf)


if __name__ == "__main__":
    main()
