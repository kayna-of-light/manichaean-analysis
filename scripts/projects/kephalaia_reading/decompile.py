"""Write the reading draft for a canonical EpiDoc page (the inverse of compile_draft.py).

usage: python decompile.py PAGE [...] [--out DIR]

The TEI is canonical once compiled. To correct a page through the draft markup, decompile it, edit the draft,
and recompile with --force; validate.py then proves draft -> TEI -> Leiden is unchanged where nothing was edited.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from model import REPO, TEI, TEI_DIR, XML, read_tei

HALF = 21
MARKS = {"supplied-lost": ("[", "]"), "supplied-omitted": ("⟨", "⟩"), "surplus": ("{", "}"), "add": ("\\", "/"),
         "sic": ("«", "»"), "del": ("⟦", "⟧")}
SIGNS = {"diple": ">", "diple-reversed": "<", "middot": "·", "dicolon-dash": "§", "unpaired-bracket": "‡"}


def _key(c) -> str:
    tag, attrs = c
    attrs = dict(attrs)
    return f"{tag}-{attrs['reason']}" if tag == "supplied" else tag


def markup(atoms) -> str:
    """Draft markup for a run of atoms (one line, or a page-furniture part)."""
    out, cur = [], ()
    runs: dict = {}
    for a in atoms:
        if a.kind == "letter" and a.stroke is not None:
            runs[a.stroke] = runs.get(a.stroke, 0) + 1
    prev_stroke = None
    for a in atoms:
        target = a.containers if a.kind in ("letter", "ws", "g") else ()
        k = 0
        while k < min(len(cur), len(target)) and cur[k] == target[k]:
            k += 1
        for c in reversed(cur[k:]):
            cert = dict(c[1]).get("cert") == "low"
            out.append(("(?)" if cert else "") + MARKS[_key(c)][1])
        for c in target[k:]:
            out.append(MARKS[_key(c)][0])
        cur = target
        if a.kind == "letter":
            t = ("^" if a.large else "") + a.text + ("_" if a.unclear else "") + ("*" if a.diaeresis else "")
            if a.stroke is not None:
                if a.stroke_kind == "oblique":
                    t += "'"
                elif runs[a.stroke] == 1:
                    t += "-"
                else:
                    if prev_stroke is not None and prev_stroke != a.stroke and runs.get(prev_stroke, 0) > 1 \
                            and out and out[-1].endswith("+"):
                        raise ValueError("two adjacent stroke runs cannot be expressed in draft markup")
                    t += "+"
            out.append(t)
            prev_stroke = a.stroke
            continue
        prev_stroke = None
        if a.kind == "ws":
            out.append(" ")
        elif a.kind == "gap":
            if a.attrs.get("ana"):
                tok = "⁅=" + a.attrs["ana"] + (":line" if a.attrs.get("unit") == "line" else "") + "⁆"
                lost_by_default = a.attrs.get("default_reason") == "lost"
                out.append(f"[{tok}]" if a.attrs["reason"] == "lost" and not lost_by_default else tok)
            else:
                dots = "." * a.attrs["quantity"]
                out.append(f"[{dots}]" if a.attrs["reason"] == "lost" else dots)
        elif a.kind == "space":
            out.append("vac." if a.attrs["type"] == "vacat" else "%")
        elif a.kind == "g":
            out.append(SIGNS.get(a.attrs["type"], a.text))
        elif a.kind == "note":
            out.append(f"⁅{a.text}⁆")
    for c in reversed(cur):
        cert = dict(c[1]).get("cert") == "low"
        out.append(("(?)" if cert else "") + MARKS[_key(c)][1])
    s = "".join(out)
    for pair in ("][", "⟩⟨", "}{", "/\\", "»«", "⟧⟦"):
        s = s.replace(pair, "")
    return s


def decompile(path: Path) -> str:
    tree, atoms = read_tei(path)
    root = tree.getroot()
    ns = {"t": TEI}
    zone = {z.get(f"{{{XML}}}id"): int(z.get("uly")) + HALF for z in root.iter(f"{{{TEI}}}zone")}
    page = path.stem[-3:]
    rows = [f"page {page}"]
    cont = next(a for a in atoms if a.kind == "milestone" and a.attrs.get("type") == "continued")
    rows.append(f"continues {cont.attrs['n']}")
    rows.append(f"pagenum {zone['z-pagenum']} | " + markup([a for a in atoms if a.role == "page-number"]))
    rows.append(f"header {zone['z-header']} | " + markup([a for a in atoms if a.role == "running-head"]))
    flags_next = []
    lines: dict[int, list] = {}
    order, lbs, margins = [], {}, []
    for a in atoms:
        if a.kind == "milestone" and a.attrs.get("unit") == "kephalaion" and a.attrs.get("type") != "continued":
            flags_next.append(f"kephalaion={a.attrs['n']}")
        elif a.kind == "milestone" and a.attrs.get("tag") == "margin":
            margins.append(a)
        elif a.kind == "lb":
            n = a.line
            order.append(n)
            lbs[n] = (a, flags_next)
            flags_next = []
        elif a.line is not None and a.role in ("text", "kephalaion-number", "kephalaion-title"):
            lines.setdefault(a.line, []).append(a)
    for n in order:
        lb, extra = lbs[n]
        part = lines.get(n, [])
        kind = next((a.role for a in part if a.role != "text"), "text")
        flags = (["ekthesis"] if lb.attrs.get("rend") == "ekthesis" else []) + \
                (["number"] if kind == "kephalaion-number" else ["title"] if kind == "kephalaion-title" else []) + extra
        y = zone[lb.attrs["facs"][1:]]
        rows.append(f"{n} {y}{''.join(' ' + f for f in flags)} | " + markup(part))
    for m in margins:
        side = m.attrs["place"].split("-")[1]
        here = [a for a in atoms if a.role == m.attrs["place"] and a.line == m.line]
        rows.append(f"margin {m.line} {zone[m.attrs['facs'][1:]]} {side} | " + markup(here))
    for p in root.iterfind(".//t:div[@type='commentary']/t:p", ns):
        cat = p.get("ana", "")[1:].split(".", 1)[-1]
        rows.append(f"note {p.get('n')}{' ' + cat if cat else ''} | {p.text}")
    for app in root.iterfind(".//t:div[@type='apparatus']//t:app", ns):
        rows.append(app_row(app))
    return "\n".join(rows) + "\n"


def app_row(app) -> str:
    from model import read_atoms
    ns = {"t": TEI}
    head = f"app {app.get('loc')} {app.get('ana')[1:].split('.', 1)[1]}"
    if app.get("n"):
        head += f" printed={app.get('n')}"
    lem = app.find("t:lem", ns)
    rdgs = app.findall("t:rdg", ns)
    note = app.find("t:note", ns)
    lem_m = markup(read_atoms(lem)) if lem is not None else ""
    rdg_m = " ¦ ".join(markup(read_atoms(r)) for r in rdgs)
    return f"{head} | {lem_m} | {rdg_m} | {note.text if note is not None and note.text else ''}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pages", nargs="+")
    ap.add_argument("--out", type=Path, default=REPO / "temp" / "kephalaia_reading" / "drafts")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for p in args.pages:
        out = args.out / f"keph_p{p}.txt"
        out.write_text(decompile(TEI_DIR / f"keph_p{p}.xml"), encoding="utf-8")
        print(out.relative_to(REPO))


if __name__ == "__main__":
    main()
