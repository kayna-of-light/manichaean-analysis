"""Validate EpiDoc page files; optionally prove the round trip against the reading drafts.

usage: python validate.py [PAGE ...] [--drafts DIR]
"""
from __future__ import annotations

import argparse
import sys
import unicodedata
from pathlib import Path

from compile_draft import parse_draft
from model import TEI, TEI_DIR, XML, leiden, lines_of, markup_to_plain, numeral_value, read_tei

ALLOWED = {"TEI", "teiHeader", "fileDesc", "titleStmt", "title", "publicationStmt", "p", "sourceDesc", "bibl",
           "biblScope", "encodingDesc", "tagsDecl", "rendition", "revisionDesc", "change", "facsimile", "surface",
           "graphic", "zone", "text", "body", "div", "ab", "pb", "milestone", "fw", "lb", "seg", "note", "num",
           "hi", "unclear", "supplied", "surplus", "add", "sic", "gap", "space", "g"}


def check(path: Path, drafts: Path | None) -> list[str]:
    errs = []
    tree, atoms = read_tei(path)
    root = tree.getroot()
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        name = el.tag.split("}")[1]
        if name not in ALLOWED:
            errs.append(f"element <{name}> not in the encoding profile")
        if name == "num":
            letters = "".join(t for t in el.itertext() if t.strip())
            if numeral_value(unicodedata.normalize("NFD", letters)) != int(el.get("value")):
                errs.append(f"<num value={el.get('value')}> does not match its letters {letters!r}")
    zones = {z.get(f"{{{XML}}}id") for z in root.iter(f"{{{TEI}}}zone")}
    for el in root.iter():
        if isinstance(el.tag, str) and el.get("facs") and el.get("facs")[1:] not in zones | {"surface"}:
            errs.append(f"facs {el.get('facs')} has no zone")
    by = lines_of(atoms)
    ns = sorted(by)
    if ns != list(range(1, len(ns) + 1)):
        errs.append(f"lines not contiguous: {ns}")
    if drafts:
        d = parse_draft(drafts / f"{path.stem}.txt")
        for n, _, _, markup in d["lines"]:
            want, got = markup_to_plain(markup), leiden(by.get(n, []))
            if want != got:
                errs.append(f"l.{n} round trip differs:\n   draft {want}\n   tei   {got}")
    return errs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pages", nargs="*")
    ap.add_argument("--drafts", type=Path)
    args = ap.parse_args()
    files = [TEI_DIR / f"keph_p{p}.xml" for p in args.pages] or sorted(TEI_DIR.glob("keph_p*.xml"))
    bad = 0
    for f in files:
        errs = check(f, args.drafts)
        bad += bool(errs)
        print(f"{f.name}: {'ok' if not errs else str(len(errs)) + ' problem(s)'}")
        for e in errs:
            print("  -", e)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
