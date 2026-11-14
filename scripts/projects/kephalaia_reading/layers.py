"""Derive analysis layers from the EpiDoc pages: one JSON per page plus corpus-wide CSV tables.

usage: python layers.py [PAGE ...]
Every record carries page and line; letters carry their index in the line, and gaps, blanks and
signs carry the index of the letter they precede, so all layers join back to the text.
"""
from __future__ import annotations

import csv
import json
import sys

from model import OUT, TEI, TEI_DIR, XML, leiden, lines_of, read_atoms, read_tei, vocab

DOT = "·"


def status(a) -> tuple[str, str | None]:
    tags = {t: dict(at) for t, at in a.containers}
    if "surplus" in tags:
        return "surplus", None
    if "add" in tags:
        return "added-above", None
    if "del" in tags:
        return "expunged", None
    if "supplied" in tags:
        s = tags["supplied"]
        if s["reason"] == "omitted":
            return "omitted", None
        return "restored", s.get("cert")
    return ("unclear" if a.unclear else "certain"), None


def page_layers(path):
    tree, atoms = read_tei(path)
    root = tree.getroot()
    page = int(root.find(f".//{{{TEI}}}pb").get("n"))
    zones = {z.get(f"{{{XML}}}id"): [int(z.get(k)) for k in ("ulx", "uly", "lrx", "lry")]
             for z in root.iter(f"{{{TEI}}}zone")}
    lb = {int(e.get("n")): e for e in root.iter(f"{{{TEI}}}lb")}
    out = {"page": page, "image": root.find(f".//{{{TEI}}}graphic").get("url"), "lines": [], "words": [],
           "letters": [], "strokes": [], "gaps": [], "blanks": [], "signs": [], "corrections": [],
           "kephalaia": [], "margin_numbers": [], "notes": [], "editorial": [], "apparatus": []}

    for role, key in (("page-number", "page_number"), ("running-head", "running_head")):
        part = [a for a in atoms if a.role == role]
        out[key] = {"leiden": leiden(part), "letters": "".join(a.text for a in part if a.kind == "letter"),
                    "value": next((a.num for a in part if a.num), None)}

    keph, line_keph = None, {}
    for a in atoms:
        if a.kind == "milestone" and a.attrs.get("unit") == "kephalaion":
            keph = int(a.attrs["n"])
            out["kephalaia"].append({"n": keph, "continued": a.attrs.get("type") == "continued",
                                     "from_line": None, "number_line": None, "title_lines": [], "title": ""})
        if a.kind == "lb":
            line_keph[a.line] = keph
            if out["kephalaia"][-1]["from_line"] is None:
                out["kephalaia"][-1]["from_line"] = a.line
    for role in ("margin-left", "margin-right"):
        part = [a for a in atoms if a.role == role and a.kind == "letter"]
        for n in sorted({a.line for a in part}):
            here = [a for a in part if a.line == n]
            out["margin_numbers"].append({"line": n, "side": role[7:], "leiden": leiden(here),
                                          "letters": "".join(a.text for a in here), "value": here[0].num})

    strokes = {}
    for n, line_atoms in lines_of(atoms).items():
        kind = next((a.role for a in line_atoms if a.role != "text"), "text")
        letters, diplo, reading, words, word = [], [], [], [], []

        def close_word():
            if word:
                w = [letters[i] for i in word]
                words.append({"page": page, "line": n, "i": len(words),
                              "reading": "".join(l["char"] for l in w if l["status"] not in ("surplus", "expunged")),
                              "diplomatic": "".join(l["char"] if l["status"] in ("certain", "unclear", "surplus",
                                                                                 "added-above", "expunged") else DOT
                                                    for l in w),
                              "complete": all(l["status"] in ("certain", "unclear") for l in w),
                              "first_letter": word[0], "last_letter": word[-1]})
                word.clear()

        for a in line_atoms:
            at = len(letters)
            if a.kind == "letter":
                st, cert = status(a)
                sic = any(t == "sic" for t, _ in a.containers)
                rec = {"page": page, "line": n, "i": at, "char": a.text, "status": st, "cert": cert,
                       "word": len(words), "stroke": a.stroke, "stroke_kind": a.stroke_kind,
                       "diaeresis": a.diaeresis, "large": a.large, "sic": sic, "kephalaion": line_keph.get(n),
                       "role": a.role}
                letters.append(rec)
                word.append(at)
                if a.stroke is not None:
                    strokes.setdefault(a.stroke, {"page": page, "line": n, "kind": a.stroke_kind, "letters": []})[
                        "letters"].append(at)
                diplo.append(a.text if st in ("certain", "unclear", "surplus", "added-above", "expunged") else DOT)
                if st not in ("surplus", "expunged"):
                    reading.append(a.text)
            elif a.kind == "ws":
                close_word()
                reading.append(" ")
            elif a.kind == "gap":
                g = {k: v for k, v in a.attrs.items() if k != "default_reason"}
                out["gaps"].append({"page": page, "line": n, "before_letter": at, "quantity": None, "unit": "character",
                                    "extent": None, "ana": None, **g})
                if a.attrs.get("ana"):
                    out["gaps"][-1]["extent"] = None if a.attrs["unit"] == "line" else "unknown"
                    out["gaps"][-1]["quantity"] = 1 if a.attrs["unit"] == "line" else None
                    e = vocab()["ed"][a.attrs["ana"]]
                    out["editorial"].append({"page": page, "line": n, "before_letter": at, "id": a.attrs["ana"],
                                             "en": e["en"], "de": " / ".join(e["de"]), "reason": a.attrs["reason"],
                                             "scope": "whole line" if a.attrs["unit"] == "line" else "in line"})
                    diplo.append("…")
                    reading.append("…")
                else:
                    diplo.append(DOT * a.attrs["quantity"])
                    reading.append(DOT * a.attrs["quantity"])
            elif a.kind == "space":
                close_word()
                out["blanks"].append({"page": page, "line": n, "before_letter": at, "type": a.attrs["type"]})
                if a.attrs["type"] == "vacat":
                    out["editorial"].append({"page": page, "line": n, "before_letter": at, "id": "vacat",
                                             "en": "blank (vacat)", "de": "leer", "reason": None, "scope": "in line"})
            elif a.kind == "g":
                out["signs"].append({"page": page, "line": n, "before_letter": at, **a.attrs, "text": a.text})
        close_word()
        for st, typ in (("surplus", "surplus"), ("omitted", "omitted"), ("added-above", "added-above"),
                        ("expunged", "expunged")):
            run = [l for l in letters if l["status"] == st]
            if run:
                out["corrections"].append({"page": page, "line": n, "type": typ,
                                           "text": "".join(l["char"] for l in run), "letters": [l["i"] for l in run]})
        if any(l["sic"] for l in letters):
            out["corrections"].append({"page": page, "line": n, "type": "sic",
                                       "text": "".join(l["char"] for l in letters if l["sic"]),
                                       "letters": [l["i"] for l in letters if l["sic"]]})
        e = lb[n]
        out["lines"].append({"page": page, "n": n, "type": kind, "kephalaion": line_keph.get(n),
                             "ekthesis": e.get("rend") == "ekthesis", "zone": zones.get(e.get("facs", "#")[1:]),
                             "leiden": leiden(line_atoms), "diplomatic": "".join(diplo),
                             "reading": " ".join("".join(reading).split()), "letters": len(letters)})
        out["letters"] += letters
        out["words"] += words
        for k in out["kephalaia"]:
            if k["n"] == line_keph.get(n) and kind == "kephalaion-number":
                k["number_line"] = n
            if k["n"] == line_keph.get(n) and kind == "kephalaion-title":
                k["title_lines"].append(n)
                k["title"] = " ".join(filter(None, [k["title"], "".join(reading).strip()]))
    out["strokes"] = [{"id": i, **s} for i, s in sorted(strokes.items())]
    out["notes"] = [{"page": page, "line": int(p.get("n")), "category": (p.get("ana") or "#tr.")[4:] or None,
                     "text": p.text} for p in root.iterfind(f".//{{{TEI}}}div[@type='commentary']/{{{TEI}}}p")]
    voc = vocab()["app"]
    for app in root.iterfind(f".//{{{TEI}}}app"):
        typ = app.get("ana")[5:]
        lem = app.find(f"{{{TEI}}}lem")
        note = app.find(f"{{{TEI}}}note")
        out["apparatus"].append({"page": page, "loc": app.get("loc"), "printed_loc": app.get("n"), "type": typ,
                                 "en": voc[typ]["en"], "lem": leiden(read_atoms(lem)) if lem is not None else "",
                                 "readings": [leiden(read_atoms(x)) for x in app.findall(f"{{{TEI}}}rdg")],
                                 "note": note.text if note is not None else ""})
    return out


TABLES = ("lines", "words", "letters", "strokes", "gaps", "blanks", "signs", "corrections", "notes", "editorial",
          "apparatus")


def main() -> None:
    files = [TEI_DIR / f"keph_p{p}.xml" for p in sys.argv[1:]] or sorted(TEI_DIR.glob("keph_p*.xml"))
    pages_dir = OUT / "layers" / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    corpus = {t: [] for t in TABLES}
    for f in files:
        lay = page_layers(f)
        (pages_dir / f"{f.stem}.json").write_text(json.dumps(lay, ensure_ascii=False, indent=1), encoding="utf-8")
        for t in TABLES:
            corpus[t] += lay[t]
        print(f"{f.stem}: {len(lay['lines'])} lines, {len(lay['letters'])} letters, {len(lay['gaps'])} gaps, "
              f"{len(lay['strokes'])} strokes, kephalaia {[k['n'] for k in lay['kephalaia']]}")
    for t, rows in corpus.items():
        if not rows:
            continue
        cols = list(dict.fromkeys(k for r in rows for k in r))
        with open(OUT / "layers" / f"{t}.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, cols)
            w.writeheader()
            w.writerows({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v) for k, v in r.items()} for r in rows)
    print(OUT / "layers")


if __name__ == "__main__":
    main()
