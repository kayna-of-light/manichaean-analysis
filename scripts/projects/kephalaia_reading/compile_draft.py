"""Compile a reading draft (compact markup, one printed line per row) into an EpiDoc TEI page file.

usage: python compile_draft.py DRAFT.txt [--force]

Draft rows:
  page 111                      edition page
  continues 42                  kephalaion in progress at the top of the page
  pagenum 208 | ⲣ[ⲓ]ⲁ           y-centre | markup   (framed manuscript page number)
  header 250 | >· ⲙ-ⲡⲥⲁϩ ·<     y-centre | markup   (running title)
  18 1008 number kephalaion=43 | ⲙ+ⲅ+     line y-centre flags | markup
  margin 19 1053 left | ⲙ+ⲅ+    marginal chapter number beside a line
  note 9 | text                 transcriber commentary for a line (plain text)
Flags: ekthesis, number, title, kephalaion=N.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from lxml import etree

from model import IMAGES, REPO, TEI_DIR, StrokeIds, atoms_to_tei, numeral_value, parse_markup

X0, X1, HALF = 440, 1430, 21


def zone(zid: str, y: int, x0: int = X0, x1: int = X1) -> str:
    return f'<zone xml:id="{zid}" ulx="{x0}" uly="{y - HALF}" lrx="{x1}" lry="{y + HALF}"/>'


def parse_draft(path: Path) -> dict:
    d = {"lines": [], "margins": [], "notes": []}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.startswith("#"):
            continue
        head, _, body = raw.partition(" | ")
        parts = head.split()
        if parts[0] == "page":
            d["page"] = parts[1]
        elif parts[0] == "continues":
            d["continues"] = int(parts[1])
        elif parts[0] in ("pagenum", "header"):
            d[parts[0]] = (int(parts[1]), body)
        elif parts[0] == "margin":
            d["margins"].append((int(parts[1]), int(parts[2]), parts[3], body))
        elif parts[0] == "note":
            d["notes"].append((int(parts[1]), body))
        else:
            flags = dict((f.split("=") + [True])[:2] for f in parts[2:])
            d["lines"].append((int(parts[0]), int(parts[1]), flags, body))
    nums = [n for n, *_ in d["lines"]]
    if nums != list(range(1, len(nums) + 1)):
        raise ValueError(f"{path.name}: line numbers are not 1..{len(nums)}")
    return d


def compile_draft(d: dict) -> str:
    page = d["page"]
    ids = StrokeIds()
    zones, body = [], []

    def tei(markup: str) -> str:
        return atoms_to_tei(parse_markup(markup, ids))

    def num(markup: str) -> str:
        letters = "".join(a.text for a in parse_markup(markup, StrokeIds()) if a.kind == "letter")
        return f'<num value="{numeral_value(letters)}">{tei(markup)}</num>'

    body.append(f'<pb n="{int(page)}" facs="#surface"/>')
    body.append(f'<milestone unit="kephalaion" n="{d["continues"]}" type="continued"/>')
    y, m = d["pagenum"]
    zones.append(zone("z-pagenum", y, 1150, 1430))
    body.append(f'<fw type="pageNum" rend="framed" facs="#z-pagenum">{num(m)}</fw>')
    y, m = d["header"]
    zones.append(zone("z-header", y, 700, 1150))
    body.append(f'<fw type="header" facs="#z-header">{tei(m)}</fw>')
    margins = {}
    for n, y, side, m in d["margins"]:
        margins.setdefault(n, []).append((y, side, m))
    for n, y, flags, m in d["lines"]:
        if "kephalaion" in flags:
            body.append(f'<milestone unit="kephalaion" n="{flags["kephalaion"]}"/>')
        zones.append(zone(f"z{n}", y))
        rend = ' rend="ekthesis"' if flags.get("ekthesis") else ""
        row = f'<lb n="{n}" facs="#z{n}"{rend}/>'
        for my, side, mm in margins.get(n, []):
            zones.append(zone(f"z{n}-{side}", my, 300 if side == "left" else 1100, 480 if side == "left" else 1300))
            row += (f'<note type="kephalaion-number" place="margin-{side}" facs="#z{n}-{side}">{num(mm)}</note>')
        if flags.get("number"):
            row += f'<seg type="kephalaion-number">{num(m)}</seg>'
        elif flags.get("title"):
            row += f'<seg type="kephalaion-title">{tei(m)}</seg>'
        else:
            row += tei(m)
        body.append(row)
    notes = "".join(f'\n        <p n="{n}">{escape(t)}</p>' for n, t in d["notes"])
    image = IMAGES / f"keph_p{page}.jpg"
    edition = "\n        ".join(body)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0" xml:lang="en">
  <teiHeader>
    <fileDesc>
      <titleStmt>
        <title>Kephalaia of the Teacher, edition page {int(page)}: diplomatic and Leiden transcription</title>
      </titleStmt>
      <publicationStmt><p>manichaean-analysis working transcription.</p></publicationStmt>
      <sourceDesc>
        <bibl xml:id="edition">Kephalaia (Manichäische Handschriften der Staatlichen Museen Berlin), ed. H. J. Polotsky and
          A. Böhlig, Stuttgart: Kohlhammer, <biblScope unit="page">{int(page)}</biblScope>. Restorations, sublinear dots,
          gap counts and corrections are the editors'.</bibl>
      </sourceDesc>
    </fileDesc>
    <encodingDesc>
      <p>EpiDoc. Read by eye from the page image; gap counts, sublinear dots and supralinear stroke extents verified by
        measurement on the image. A supralinear stroke is marked on every letter it covers by at least half its width.
        Spaces are the edition's word division. Facsimile zones are measured line centres.</p>
      <tagsDecl>
        <rendition xml:id="oblique">supralinear stroke printed obliquely (over ⲥ and ϩ)</rendition>
      </tagsDecl>
    </encodingDesc>
    <revisionDesc>
      <change when="{date.today().isoformat()}">Compiled from reading draft.</change>
    </revisionDesc>
  </teiHeader>
  <facsimile>
    <surface xml:id="surface" ulx="0" uly="0" lrx="1553" lry="2258">
      <graphic url="{image.relative_to(REPO).as_posix()}"/>
      {chr(10).join("      " + z for z in zones).strip()}
    </surface>
  </facsimile>
  <text>
    <body>
      <div type="edition" xml:lang="cop" xml:space="preserve">
      <ab>
        {edition}
      </ab>
      </div>
      <div type="commentary">{notes}
      </div>
    </body>
  </text>
</TEI>
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("draft", type=Path)
    ap.add_argument("--force", action="store_true", help="overwrite an existing TEI file")
    args = ap.parse_args()
    d = parse_draft(args.draft)
    out = TEI_DIR / f"keph_p{d['page']}.xml"
    if out.exists() and not args.force:
        sys.exit(f"{out} exists; the TEI is canonical once compiled. Edit it directly or pass --force.")
    xml = compile_draft(d)
    etree.fromstring(xml.encode("utf-8"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(xml, encoding="utf-8")
    print(out.relative_to(REPO))


if __name__ == "__main__":
    main()
