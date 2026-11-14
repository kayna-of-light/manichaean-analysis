"""Validate EpiDoc page files; optionally prove the round trip against the reading drafts.

usage: python validate.py [PAGE ...] [--drafts DIR]
"""
from __future__ import annotations

import argparse
import sys
import unicodedata
from pathlib import Path

from compile_draft import parse_draft
from model import TEI, TEI_DIR, XML, leiden, lines_of, markup_to_plain, numeral_value, read_atoms, read_tei, vocab

ALLOWED = {"TEI", "teiHeader", "fileDesc", "titleStmt", "title", "publicationStmt", "p", "sourceDesc", "bibl",
           "biblScope", "encodingDesc", "tagsDecl", "rendition", "revisionDesc", "change", "facsimile", "surface",
           "graphic", "zone", "text", "body", "div", "ab", "pb", "milestone", "fw", "lb", "seg", "note", "num",
           "hi", "unclear", "supplied", "surplus", "add", "sic", "gap", "space", "g", "del", "classDecl", "taxonomy",
           "category", "catDesc", "listApp", "app", "lem", "rdg"}


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
    voc = vocab()
    cats = {c.get(f"{{{XML}}}id") for c in root.iter(f"{{{TEI}}}category")}
    for c in cats:
        k, _, i = c.partition(".")
        if i not in voc.get(k, {}):
            errs.append(f"category {c} is not in the vocabulary")
    for el in root.iter():
        if isinstance(el.tag, str) and el.get("ana") and el.get("ana")[1:] not in cats:
            errs.append(f"@ana {el.get('ana')} has no category in the header")
    for a in atoms:
        if a.kind == "note":
            errs.append(f"l.{a.line}: free-text note {a.text!r} in the edition; use a vocabulary id")
    for p in root.iterfind(f".//{{{TEI}}}div[@type='commentary']/{{{TEI}}}p"):
        if not p.get("ana"):
            errs.append(f"commentary l.{p.get('n')} has no category")
    zones = {z.get(f"{{{XML}}}id") for z in root.iter(f"{{{TEI}}}zone")}
    for el in root.iter():
        if isinstance(el.tag, str) and el.get("facs") and el.get("facs")[1:] not in zones | {"surface"}:
            errs.append(f"facs {el.get('facs')} has no zone")
    by = lines_of(atoms)
    ns = sorted(by)
    if ns != list(range(1, len(ns) + 1)):
        errs.append(f"lines not contiguous: {ns}")
    apps = list(root.iterfind(f".//{{{TEI}}}app"))
    for app in apps:
        if app.get("loc") not in {str(n) for n in ns} | {"header", "bottom"}:
            errs.append(f"apparatus loc {app.get('loc')} is not a line of the page")
    if drafts:
        d = parse_draft(drafts / f"{path.stem}.txt")
        for n, _, _, markup in d["lines"]:
            want, got = markup_to_plain(markup), leiden(by.get(n, []))
            if want != got:
                errs.append(f"l.{n} round trip differs:\n   draft {want}\n   tei   {got}")
        if len(d["apps"]) != len(apps):
            errs.append(f"{len(d['apps'])} apparatus rows in the draft, {len(apps)} in the TEI")
        for a, app in zip(d["apps"], apps):
            lem = app.find(f"{{{TEI}}}lem")
            got = [leiden(read_atoms(lem)) if lem is not None else ""] + [
                leiden(read_atoms(x)) for x in app.findall(f"{{{TEI}}}rdg")]
            want = [markup_to_plain(a["lem"]) if a["lem"] else ""] + [markup_to_plain(x) for x in a["rdgs"]]
            if got != want:
                errs.append(f"apparatus {a['loc']} round trip differs: {want} / {got}")
        notes = [(p.get("n"), p.get("ana"), p.text) for p in
                 root.iterfind(f".//{{{TEI}}}div[@type='commentary']/{{{TEI}}}p")]
        if notes != [(str(n), f"#tr.{c}" if c else None, t) for n, c, t in d["notes"]]:
            errs.append("commentary differs from the draft notes")
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
