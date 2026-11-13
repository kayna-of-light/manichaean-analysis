"""Kephalaia page readings: reading markup -> atoms -> EpiDoc TEI, and TEI -> atoms -> Leiden / layers.

An atom is one element of the reading in page order: a letter, a word space, a counted gap,
a blank (vacat), a printed sign, a transcriber note, or a structural marker (lb, milestone).
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from lxml import etree

REPO = Path(__file__).resolve().parents[3]
IMAGES = REPO / "output" / "projects" / "kephalaia_v2" / "coptic" / "images"
TEI_DIR = REPO / "data" / "kephalaia" / "epidoc"
OUT = REPO / "output" / "projects" / "kephalaia_reading"
TEI = "http://www.tei-c.org/ns/1.0"
XML = "http://www.w3.org/XML/1998/namespace"

UNDERDOT, MACRON, OVERLINE, GRAVE, DIAERESIS, EMSPACE = "\u0323", "\u0304", "\u0305", "\u0300", "\u0308", "\u2003"

NUMERALS = dict(zip("ⲁⲃⲅⲇⲉⲋⲍⲏⲑⲓⲕⲗⲙⲛⲝⲟⲡϥⲣⲥⲧⲩⲫⲭⲯⲱ",
                    [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20, 30, 40, 50, 60, 70, 80, 90,
                     100, 200, 300, 400, 500, 600, 700, 800]))

# markup: X_ dot below | X- one stroke on this letter | X+ continuous stroke (run) | X' oblique stroke
# X* diaeresis | ^X enlarged | [ ] lost+restored | ⟨ ⟩ omitted | { } surplus | \ / above the line
# «X» sic | . counted letter (lost inside [ ], illegible outside) | vac. blank | % unmarked blank
# > < · printed signs | § end mark :— | ‡ printed bracket with no partner | ⁅text⁆ transcriber note | (?) before ] = uncertain restoration
OPEN = {"[": ("supplied", (("reason", "lost"),)), "⟨": ("supplied", (("reason", "omitted"),)),
        "{": ("surplus", (("reason", "repeated"),)), "\\": ("add", (("place", "above"),)), "«": ("sic", ())}
CLOSE = {"]": "[", "⟩": "⟨", "}": "{", "/": "\\", "»": "«"}
SIGNS = {">": "diple", "<": "diple-reversed", "·": "middot"}


def is_coptic(ch: str) -> bool:
    return "\u2c80" <= ch <= "\u2cff" or "\u03e2" <= ch <= "\u03ef"


def numeral_value(letters: str) -> int:
    return sum(NUMERALS[c] for c in letters if c in NUMERALS)


@dataclass
class Atom:
    kind: str  # letter | ws | gap | space | g | note | lb | milestone
    text: str = ""
    unclear: bool = False
    diaeresis: bool = False
    large: bool = False
    stroke: int | None = None
    stroke_kind: str | None = None  # single | run | oblique
    containers: tuple = ()  # ((tag, ((attr, value), ...)), ...) outer -> inner
    attrs: dict = field(default_factory=dict)
    role: str = "text"
    line: int | None = None
    num: int | None = None


# ---------------------------------------------------------------- markup -> atoms

def _close_of(s: str, i: int) -> int:
    depth, j = 0, i
    while j < len(s):
        if s[j] == "⁅":
            j = s.index("⁆", j)
        elif s[j] == "[":
            depth += 1
        elif s[j] == "]":
            depth -= 1
            if depth == 0:
                return j
        j += 1
    raise ValueError(f"unclosed [ in {s!r}")


class StrokeIds:
    def __init__(self):
        self.n = 0

    def next(self) -> int:
        self.n += 1
        return self.n


def parse_markup(s: str, ids: StrokeIds, role: str = "text") -> list[Atom]:
    atoms: list[Atom] = []
    stack: list[tuple] = []
    i, big, run = 0, False, None
    cont = lambda: tuple((t, a) for t, a, _ in stack)  # noqa: E731
    while i < len(s):
        ch = s[i]
        if ch == "⁅":
            j = s.index("⁆", i)
            atoms.append(Atom("note", s[i + 1:j], attrs={"type": "transcriber"}, role=role))
            i = j + 1
            continue
        if s.startswith("vac.", i):
            atoms.append(Atom("space", attrs={"type": "vacat"}, role=role))
            i, run = i + 4, None
            continue
        if s.startswith("(?)", i):
            i += 3
            continue
        if ch in OPEN:
            tag, attrs = OPEN[ch]
            if ch == "[":
                close = _close_of(s, i)
                if s[close - 3:close] == "(?)":
                    attrs = attrs + (("cert", "low"),)
            stack.append((tag, attrs, ch))
            i += 1
            continue
        if ch in CLOSE:
            if not stack or stack[-1][2] != CLOSE[ch]:
                raise ValueError(f"unbalanced {ch!r} at {i} in {s!r}")
            stack.pop()
            i += 1
            continue
        if ch == ".":
            j = i
            while j < len(s) and s[j] == ".":
                j += 1
            lost = any(t == "supplied" and dict(a)["reason"] == "lost" for t, a, _ in stack)
            atoms.append(Atom("gap", attrs={"reason": "lost" if lost else "illegible", "quantity": j - i}, role=role))
            i, run = j, None
            continue
        if ch == " ":
            atoms.append(Atom("ws", " ", containers=cont(), role=role))
            i, run = i + 1, None
            continue
        if ch == "%":
            atoms.append(Atom("space", attrs={"type": "unmarked"}, role=role))
            i, run = i + 1, None
            continue
        if ch == "§":
            atoms.append(Atom("g", ":—", containers=cont(), attrs={"type": "dicolon-dash"}, role=role))
            i, run = i + 1, None
            continue
        if ch == "‡":
            atoms.append(Atom("g", "]", containers=cont(), attrs={"type": "unpaired-bracket"}, role=role))
            i, run = i + 1, None
            continue
        if ch in SIGNS:
            atoms.append(Atom("g", ch, containers=cont(), attrs={"type": SIGNS[ch]}, role=role))
            i, run = i + 1, None
            continue
        if ch == "^":
            big, i = True, i + 1
            continue
        if is_coptic(ch):
            a = Atom("letter", ch, large=big, containers=cont(), role=role)
            big, j = False, i + 1
            marks = ""
            while j < len(s) and s[j] in "_-+'*":
                marks += s[j]
                j += 1
            for m in marks:
                if m == "_":
                    a.unclear = True
                elif m == "*":
                    a.diaeresis = True
                elif m in "-'":
                    a.stroke, a.stroke_kind = ids.next(), "single" if m == "-" else "oblique"
                elif m == "+":
                    run = run or ids.next()
                    a.stroke, a.stroke_kind = run, "run"
            if "+" not in marks:
                run = None
            atoms.append(a)
            i = j
            continue
        raise ValueError(f"unexpected {ch!r} at {i} in {s!r}")
    if stack:
        raise ValueError(f"unclosed {stack[-1][2]!r} in {s!r}")
    return atoms


def markup_to_plain(s: str) -> str:
    """Leiden string straight from markup, used to prove the TEI round trip is lossless."""
    out = []
    s = re.sub(r"⁅[^⁆]*⁆", "", s).replace("«", "").replace("»", "")
    marks = {"_": UNDERDOT, "-": MACRON, "+": OVERLINE, "'": GRAVE, "*": DIAERESIS}
    for ch in s:
        if ch in marks and out and (is_coptic(out[-1][-1]) or "\u0300" <= out[-1][-1] <= "\u036f"):
            out[-1] += marks[ch]
        elif ch == "^":
            continue
        elif ch == "%":
            out.append(EMSPACE)
        elif ch == "§":
            out.append(":—")
        elif ch == "‡":
            out.append("]")
        else:
            out.append(ch)
    return unicodedata.normalize("NFD", "".join(out))


# ---------------------------------------------------------------- atoms -> TEI

def _wrappers(a: Atom, idx: int) -> list:
    w = []
    if a.kind == "letter" and a.stroke is not None:
        w.append(("stroke", a.stroke, a.stroke_kind))
    if a.kind in ("letter", "ws", "g"):
        w += [("c",) + c for c in a.containers]
    if a.kind == "letter":
        if a.unclear:
            w.append(("unclear",))
        if a.diaeresis:
            w.append(("diaeresis", idx))
        if a.large:
            w.append(("large", idx))
    return w


def _open(key) -> str:
    kind = key[0]
    if kind == "stroke":
        return '<hi rend="supraline"' + (' rendition="#oblique"' if key[2] == "oblique" else "") + ">"
    if kind == "c":
        return f"<{key[1]}" + "".join(f" {k}={quoteattr(v)}" for k, v in key[2]) + ">"
    if kind == "unclear":
        return "<unclear>"
    return f'<hi rend="{kind}">'


def _close(key) -> str:
    return {"stroke": "</hi>", "unclear": "</unclear>", "diaeresis": "</hi>", "large": "</hi>"}.get(
        key[0], f"</{key[1]}>" if key[0] == "c" else "")


def _leaf(a: Atom) -> str:
    if a.kind == "letter":
        return a.text
    if a.kind == "ws":
        return " "
    if a.kind == "gap":
        return f'<gap reason="{a.attrs["reason"]}" quantity="{a.attrs["quantity"]}" unit="character"/>'
    if a.kind == "space":
        typ = ' type="unmarked"' if a.attrs["type"] == "unmarked" else ""
        return f'<space{typ} extent="unknown" unit="character"/>'
    if a.kind == "g":
        return f'<g type="{a.attrs["type"]}">{escape(a.text)}</g>'
    if a.kind == "note":
        return f'<note type="transcriber">{escape(a.text)}</note>'
    raise ValueError(a.kind)


def atoms_to_tei(atoms: list[Atom]) -> str:
    items = [(a, _wrappers(a, i)) for i, a in enumerate(atoms)]

    def emit(group, depth):
        out, i = [], 0
        key_at = lambda it: it[1][depth] if len(it[1]) > depth else None  # noqa: E731
        while i < len(group):
            key = key_at(group[i])
            if key is None:
                out.append(_leaf(group[i][0]))
                i += 1
                continue
            j = i + 1
            while j < len(group) and key_at(group[j]) == key:
                j += 1
            out.append(_open(key) + emit(group[i:j], depth + 1) + _close(key))
            i = j
        return "".join(out)

    return emit(items, 0)


# ---------------------------------------------------------------- TEI -> atoms

def _local(el) -> str:
    return etree.QName(el).localname


def read_tei(path: Path) -> tuple[etree._ElementTree, list[Atom]]:
    tree = etree.parse(str(path))
    ab = tree.find(f".//{{{TEI}}}div[@type='edition']/{{{TEI}}}ab")
    atoms: list[Atom] = []
    ids = StrokeIds()
    ctx = {"containers": (), "unclear": False, "diaeresis": False, "large": False, "stroke": None,
           "stroke_kind": None, "role": "text", "line": None, "num": None}

    def text(t, c):
        for ch in re.sub(r"\n\s*", "", t or ""):
            if ch == " ":
                atoms.append(Atom("ws", " ", containers=c["containers"], role=c["role"], line=c["line"]))
            elif is_coptic(ch):
                atoms.append(Atom("letter", ch, c["unclear"], c["diaeresis"], c["large"], c["stroke"],
                                  c["stroke_kind"], c["containers"], role=c["role"], line=c["line"], num=c["num"]))
            else:
                raise ValueError(f"{path.name}: stray character {ch!r} in line {c['line']}")

    def walk(el, c):
        text(el.text, c)
        for ch in el:
            visit(ch, c)
            text(ch.tail, c)

    def visit(el, c):
        tag = _local(el)
        c = dict(c)
        if tag == "lb":
            ctx["line"] = int(el.get("n"))
            atoms.append(Atom("lb", attrs=dict(el.attrib), line=ctx["line"]))
            return
        if tag in ("pb", "milestone"):
            atoms.append(Atom("milestone", attrs={"tag": tag, **dict(el.attrib)}, line=ctx["line"]))
            return
        c["line"] = ctx["line"]
        if tag == "gap":
            atoms.append(Atom("gap", attrs={"reason": el.get("reason"), "quantity": int(el.get("quantity"))},
                              role=c["role"], line=c["line"]))
            return
        if tag == "space":
            atoms.append(Atom("space", attrs={"type": el.get("type", "vacat")}, role=c["role"], line=c["line"]))
            return
        if tag == "g":
            atoms.append(Atom("g", el.text or "", containers=c["containers"], attrs={"type": el.get("type")},
                              role=c["role"], line=c["line"]))
            return
        if tag == "note" and el.get("type") == "transcriber":
            atoms.append(Atom("note", el.text or "", attrs={"type": "transcriber"}, role=c["role"], line=c["line"]))
            return
        if tag == "fw":
            c["role"] = "page-number" if el.get("type") == "pageNum" else "running-head"
            c["line"] = None
        elif tag == "seg":
            c["role"] = el.get("type")
        elif tag == "note":
            c["role"] = el.get("place")
            atoms.append(Atom("milestone", attrs={"tag": "margin", **dict(el.attrib)}, line=c["line"]))
        elif tag == "num":
            c["num"] = int(el.get("value"))
        elif tag == "hi" and el.get("rend") == "supraline":
            c["stroke"] = ids.next()
            c["stroke_kind"] = "oblique" if el.get("rendition") == "#oblique" else "stroke"
        elif tag == "hi":
            c[el.get("rend")] = True
        elif tag == "unclear":
            c["unclear"] = True
        elif tag in ("supplied", "surplus", "add", "sic"):
            attrs = tuple((k, el.get(k)) for k in ("reason", "place", "cert") if el.get(k))
            c["containers"] = c["containers"] + ((tag, attrs),)
        else:
            raise ValueError(f"{path.name}: unsupported element <{tag}>")
        walk(el, c)

    walk(ab, ctx)
    counts = Counter(a.stroke for a in atoms if a.kind == "letter" and a.stroke is not None)
    for a in atoms:
        if a.stroke_kind == "stroke":
            a.stroke_kind = "single" if counts[a.stroke] == 1 else "run"
    return tree, atoms


# ---------------------------------------------------------------- atoms -> Leiden

def _sign(c, opening: bool) -> str:
    tag, attrs = c
    attrs = dict(attrs)
    if tag == "supplied" and attrs["reason"] == "lost":
        return "[" if opening else ("(?)]" if attrs.get("cert") == "low" else "]")
    pair = {"supplied": "⟨⟩", "surplus": "{}", "add": "\\/", "sic": "  "}[tag]
    return pair[0 if opening else 1].strip()


def leiden(atoms: list[Atom], html: bool = False) -> str:
    out, cur = [], ()
    strokes = Counter(a.stroke for a in atoms if a.kind == "letter" and a.stroke is not None)
    for a in atoms:
        target = a.containers if a.kind in ("letter", "ws", "g") else ()
        k = 0
        while k < min(len(cur), len(target)) and cur[k] == target[k]:
            k += 1
        out += [_sign(c, False) for c in reversed(cur[k:])] + [_sign(c, True) for c in target[k:]]
        cur = target
        if a.kind == "letter":
            t = a.text + (UNDERDOT if a.unclear else "") + (DIAERESIS if a.diaeresis else "")
            if a.stroke is not None:
                t += GRAVE if a.stroke_kind == "oblique" else (MACRON if strokes[a.stroke] == 1 else OVERLINE)
            out.append(f'<span class="big">{t}</span>' if html and a.large else t)
        elif a.kind == "ws":
            out.append(" ")
        elif a.kind == "gap":
            dots = "." * a.attrs["quantity"]
            out.append(f"[{dots}]" if a.attrs["reason"] == "lost" else dots)
        elif a.kind == "space":
            if a.attrs["type"] == "vacat":
                out.append('<span class="vac">vac.</span>' if html else "vac.")
            else:
                out.append('<span class="gap"></span>' if html else EMSPACE)
        elif a.kind == "g":
            out.append(escape(a.text) if html else a.text)
    out += [_sign(c, False) for c in reversed(cur)]
    s = "".join(out)
    for pair in ("][", "⟩⟨", "}{", "/\\"):
        s = s.replace(pair, "")
    return s if html else unicodedata.normalize("NFD", s)


def lines_of(atoms: list[Atom]) -> dict[int, list[Atom]]:
    """Body lines only: page furniture and marginal chapter numbers are kept out."""
    by: dict[int, list[Atom]] = {}
    for a in atoms:
        if a.line is not None and a.kind not in ("lb", "milestone") and a.role in ("text", "kephalaion-number",
                                                                                     "kephalaion-title"):
            by.setdefault(a.line, []).append(a)
    return by
