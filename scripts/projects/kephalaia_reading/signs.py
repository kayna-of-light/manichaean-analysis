"""Register of printed signs that are not letters, across every read page (ledger §7).

usage: python signs.py [TYPE ...]      (default: every type except the routine diples)

For each occurrence: page.line, the word before and after, whether it ends the line or the kephalaion, and the
blank before it. The point is to let a pattern show itself over many pages: where a sign stands (line end,
chapter end, mid-line, after a wide blank) and next to what. The meaning is not decided here; record what the
pattern suggests in ledger §7 once there are enough occurrences.
"""
from __future__ import annotations

import sys
from collections import defaultdict

from model import TEI_DIR, read_tei

ROUTINE = {"diple", "diple-reversed", "dicolon-dash", "unpaired-bracket"}


def atoms_after(atoms, start, stop):
    """Atoms strictly between two atoms of the page (by identity)."""
    out, on = [], False
    for b in atoms:
        if b is stop:
            break
        if on:
            out.append(b)
        if b is start:
            on = True
    return out


def occurrences():
    for path in sorted(TEI_DIR.glob("keph_p*.xml")):
        page = path.stem.removeprefix("keph_p")
        _, atoms = read_tei(path)
        line, kephalaion, words, prev_blank = None, None, [], False
        seq = []
        for a in atoms:
            if a.kind == "lb":
                line = a.attrs.get("n")
            elif a.kind == "milestone" and a.attrs.get("unit") == "kephalaion":
                kephalaion = a.attrs.get("n")
            if a.role != "text" or line is None:
                continue
            seq.append((line, kephalaion, a))
        for i, (ln, keph, a) in enumerate(seq):
            if a.kind != "g":
                continue

            def word(step):
                j, w, seen = i + step, "", False
                while 0 <= j < len(seq) and seq[j][0] == ln:
                    b = seq[j][2]
                    if b.kind == "letter":
                        w = (b.text + w) if step < 0 else (w + b.text)
                        seen = True
                    elif seen and b.kind in ("ws", "space", "g"):
                        break
                    j += step
                return w

            rest = [b for l2, _, b in seq[i + 1:] if l2 == ln]
            line_end = not any(b.kind in ("letter", "gap", "g") for b in rest)
            k = i - 1
            while k >= 0 and seq[k][0] == ln and seq[k][2].kind == "ws":
                k -= 1
            after_blank = k >= 0 and seq[k][0] == ln and seq[k][2].kind == "space"
            nxt = next((b for _, _, b in seq[i + 1:] if b.kind in ("letter", "gap")), None)
            chapter_end = nxt is None or any(
                b.kind == "milestone" and b.attrs.get("unit") == "kephalaion" for b in atoms_after(atoms, a, nxt))
            yield {"type": a.attrs.get("type"), "page": page, "line": ln, "kephalaion": keph,
                   "before": word(-1), "after": word(1), "line_end": line_end,
                   "after_blank": after_blank, "chapter_end": chapter_end}


def main():
    want = set(sys.argv[1:])
    by_type = defaultdict(list)
    for o in occurrences():
        if (o["type"] in want) if want else (o["type"] not in ROUTINE):
            by_type[o["type"]].append(o)
    for t in sorted(by_type):
        print(f"== {t} ({len(by_type[t])})")
        for o in by_type[t]:
            flags = ", ".join(f for f, on in (("line end", o["line_end"]), ("end of kephalaion", o["chapter_end"]),
                                                    ("after a blank", o["after_blank"])) if on)
            print(f"  {int(o['page'])}.{o['line']:<3} keph. {o['kephalaion'] or '?':<3} "
                  f"{o['before'] or '—'} ‹{t}› {o['after'] or '—'}" + (f"   [{flags}]" if flags else ""))


if __name__ == "__main__":
    main()
