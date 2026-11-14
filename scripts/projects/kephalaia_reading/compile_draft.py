"""Compile a reading draft (compact markup, one printed line per row) into an EpiDoc TEI page file.

usage: python compile_draft.py DRAFT.txt [--force]

Draft rows:
  page 111                      edition page
  continues 42                  kephalaion in progress at the top of the page
  pagenum 208 | ⲣ[ⲓ]ⲁ           y-centre | markup   (framed manuscript page number)
  header 250 | >· ⲙ-ⲡⲥⲁϩ ·<     y-centre | markup   (running title)
  18 1008 number kephalaion=43 | ⲙ+ⲅ+     line y-centre flags | markup
  margin 19 1053 left | ⲙ+ⲅ+    marginal chapter number beside a line
  note 9 bracket | text         transcriber commentary for a line; category from the vocabulary's "tr" list
  app 13 conjecture | lem | rdg ¦ rdg | note
                                an editors' footnote: line (as fixed by the margin numerals; or header, bottom),
                                type from the vocabulary's "app" list, optional printed=N when the footnote
                                number differs; lemma and readings in reading markup; English note
Flags: ekthesis, number, title, kephalaion=N.
Editors' statements inside a line are written ⁅=ID⁆ (or ⁅=ID:line⁆ for the whole line), ID from the vocabulary's
"ed" list (data/kephalaia/editorial_vocabulary.json).
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from lxml import etree

from model import IMAGES, REPO, TEI_DIR, VOCAB_PATH, StrokeIds, atoms_to_tei, numeral_value, parse_markup, vocab

X0, X1, HALF = 440, 1430, 21


def zone(zid: str, y: int, x0: int = X0, x1: int = X1) -> str:
    return f'<zone xml:id="{zid}" ulx="{x0}" uly="{y - HALF}" lrx="{x1}" lry="{y + HALF}"/>'


def parse_draft(path: Path) -> dict:
    d = {"lines": [], "margins": [], "notes": [], "apps": []}
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
            d["notes"].append((int(parts[1]), parts[2] if len(parts) > 2 else None, body))
        elif parts[0] == "app":
            printed = next((p.split("=")[1] for p in parts[3:] if p.startswith("printed=")), None)
            _, lem, rdgs, note = (raw.split("|", 3) + ["", "", ""])[:4]
            d["apps"].append({"loc": parts[1], "type": parts[2], "printed": printed, "lem": lem.strip(),
                              "rdgs": [x.strip() for x in rdgs.split(" ¦ ") if x.strip()], "note": note.strip()})
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
    edition = "\n        ".join(body)
    notes = "".join(f'\n        <p n="{n}"' + (f' ana="#tr.{c}"' if c else "") + f'>{escape(t)}</p>'
                    for n, c, t in d["notes"])
    apps = []
    for a in d["apps"]:
        head = f'<app loc="{a["loc"]}"' + (f' n="{a["printed"]}"' if a["printed"] else "") + f' ana="#app.{a["type"]}">'
        inner = (f"<lem>{tei(a['lem'])}</lem>" if a["lem"] else "") + "".join(
            f'<rdg resp="#edition">{tei(x)}</rdg>' for x in a["rdgs"]) + (
            f"<note>{escape(a['note'])}</note>" if a["note"] else "")
        apps.append(head + inner + "</app>")
    apparatus = ("\n      <div type=\"apparatus\">\n      <listApp>\n        " + "\n        ".join(apps)
                 + "\n      </listApp>\n      </div>") if apps else ""
    used = {"ed": sorted(set(re.findall(r'ana="#ed\.([\w-]+)"', edition))),
            "app": sorted({a["type"] for a in d["apps"]}), "tr": sorted({c for _, c, _ in d["notes"] if c})}
    voc = vocab()
    taxa = "".join(f'\n        <taxonomy xml:id="{k}">' + "".join(
        f'<category xml:id="{k}.{i}"><catDesc>{escape(voc[k][i]["en"])}</catDesc></category>' for i in ids)
        + "</taxonomy>" for k, ids in used.items() if ids)
    class_decl = ("\n      <classDecl>" + taxa + "\n      </classDecl>") if taxa else ""
    image = IMAGES / f"keph_p{page}.jpg"
    for a in d["apps"]:
        for key, ids in (("app", [a["type"]]),):
            for i in ids:
                if i not in vocab()[key]:
                    raise ValueError(f"unknown apparatus type {i!r}")
    for _, c, _ in d["notes"]:
        if c and c not in vocab()["tr"]:
            raise ValueError(f"unknown note category {c!r}")
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
        Spaces are the edition's word division. Facsimile zones are measured line centres. The editors' German
        statements are not transcribed: each is mapped to an id of the controlled vocabulary
        {VOCAB_PATH.relative_to(REPO).as_posix()} and carried as @ana (ed: statements in the text, app: apparatus
        footnotes, tr: categories of the transcriber's commentary).</p>
      <tagsDecl>
        <rendition xml:id="oblique">supralinear stroke printed obliquely (over ⲥ and ϩ)</rendition>
      </tagsDecl>{class_decl}
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
      </div>{apparatus}
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
