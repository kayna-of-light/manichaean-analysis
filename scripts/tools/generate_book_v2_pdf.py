#!/usr/bin/env python3
"""
Generate the v2 book PDF: The Ancient Word in the Coptic Kephalaia.

The v2 build differs from v1 in three ways:

  1. Source data: kephalaia_v2 pipeline (104 teachings, 53 chapters,
     14 sections; spiritual-reading-first composition).
  2. Body layout: two columns, Coptic ↔ English, rendered segment by
     segment from the line-aligned teachings, with editor and pipeline
     restorations folded in.
  3. Each teaching is prefaced by its Stage 5 spiritual reading (what
     the cosmological language corresponds to in the science of
     correspondences).

Architecture mirrors v1: ReportLab Platypus, two-pass build with
_PageRecorder for TOC page numbers, A4 page size, Junicode for
Latin-script text, Noto Sans Coptic for Coptic.

Dependencies: reportlab  (available in conda env 'manichaean')

Usage:
    conda run -n manichaean python scripts/tools/generate_book_v2_pdf.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, HRFlowable,
    Flowable, Table, TableStyle, KeepTogether,
)
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

# ---------------------------------------------------------------------------
# Font registration
# ---------------------------------------------------------------------------

# Latin / English: Junicode (bundled in repo). Junicode is a serif font
# designed by Peter Baker for medievalists and classicists; it ships full
# coverage of the glyphs needed for a critical edition with Leiden
# apparatus — half-brackets U+2308/2309 (the Assyriological convention
# for editor restorations vs. AI/conjectural fills), all combining marks,
# Unicode superscript digits, smart quotes, em-dash. OFL-licensed so it
# can travel with the repo. We do NOT use Noto Sans Coptic for Latin
# because Noto Sans Coptic lacks square brackets, half-brackets, dashes,
# and superscripts.
_REPO_FONT_DIR = Path(__file__).resolve().parent / "fonts"

pdfmetrics.registerFont(TTFont("Latin", str(_REPO_FONT_DIR / "Junicode-Regular.ttf")))
pdfmetrics.registerFont(TTFont("Latin-Bold", str(_REPO_FONT_DIR / "Junicode-Bold.ttf")))
pdfmetrics.registerFont(TTFont("Latin-Italic", str(_REPO_FONT_DIR / "Junicode-Italic.ttf")))
pdfmetrics.registerFont(TTFont("Latin-BoldItalic", str(_REPO_FONT_DIR / "Junicode-BoldItalic.ttf")))
registerFontFamily(
    "Latin",
    normal="Latin", bold="Latin-Bold",
    italic="Latin-Italic", boldItalic="Latin-BoldItalic",
)

# Coptic: Noto Sans Coptic (bundled in repo). Designed with proper combining
# mark positioning so that overlines (U+0304 etc.) render visibly above the
# preceding letter. Segoe UI Historic has the glyphs but its mark positioning
# is unreliable in ReportLab, which does no GPOS shaping.
pdfmetrics.registerFont(
    TTFont("Coptic", str(_REPO_FONT_DIR / "NotoSansCoptic-Regular.ttf"))
)

FONT_ROMAN = "Latin"
FONT_BOLD = "Latin-Bold"
FONT_ITALIC = "Latin-Italic"
FONT_COPTIC = "Coptic"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

KEPH = PROJECT_ROOT / "output" / "projects" / "kephalaia_v2"
BOOK_FILE = KEPH / "book.json"
SECTIONS_DIR = KEPH / "sections"
CHAPTERS_DIR = SECTIONS_DIR / "chapters"
TEACHINGS_DIR = KEPH / "teachings"
READINGS_DIR = KEPH / "readings"
RESTORED_DIR = KEPH / "restored"
LEXICON_FILE = KEPH / "spiritual_lexicon.json"

OUTPUT = PROJECT_ROOT / "output" / "pdfs" / "The_Ancient_Word_v2.pdf"
OUTPUT_TMP = PROJECT_ROOT / "output" / "pdfs" / "The_Ancient_Word_v2_tmp.pdf"

PAGE_W, PAGE_H = A4

LACUNA_GRAY = "#999999"
RULE_COLOR = "#CCCCCC"
NOTE_COLOR = "#555555"
MUTED = "#888888"
DARK_MUTED = "#666666"
TOC_DOT_COLOR = "#BBBBBB"
TOC_PAGE_COLOR = "#888888"
FOOTER_RULE_COLOR = "#CCCCCC"
READING_RULE_COLOR = "#D0D0D0"
LINE_LABEL_COLOR = "#999999"

# Two-column body geometry
LEFT_MARGIN = 22 * mm
RIGHT_MARGIN = 22 * mm
TEXT_WIDTH = PAGE_W - LEFT_MARGIN - RIGHT_MARGIN  # ~17 cm on A4
COL_GUTTER = 4 * mm
COL_WIDTH = (TEXT_WIDTH - COL_GUTTER) / 2

# Global page-number registry for the two-pass TOC build
_page_registry: dict[str, int] = {}


# ---------------------------------------------------------------------------
# Custom flowables (identical to v1)
# ---------------------------------------------------------------------------

class _PageRecorder(Flowable):
    """Zero-size flowable that records its page number when drawn."""

    width = 0
    height = 0

    def __init__(self, key: str):
        super().__init__()
        self.key = key

    def draw(self):
        _page_registry[self.key] = self.canv.getPageNumber()


class _TocLine(Flowable):
    """TOC line: title, dot leader, right-aligned page number."""

    def __init__(self, title: str, page_num, *,
                 title_font: str, font_size: float, leading: float,
                 indent: float = 0,
                 dot_color: str = TOC_DOT_COLOR,
                 page_color: str = TOC_PAGE_COLOR):
        super().__init__()
        self.title = title
        self.page_num = str(page_num) if page_num else ""
        self.title_font = title_font
        self.font_size = font_size
        self._leading = leading
        self.indent = indent
        self.dot_color = dot_color
        self.page_color = page_color

    def wrap(self, availWidth, availHeight):
        self._avail_w = availWidth
        return (availWidth, self._leading)

    def draw(self):
        c = self.canv
        y = self._leading - self.font_size

        c.setFont(self.title_font, self.font_size)
        c.setFillColor(HexColor("#000000"))
        c.drawString(self.indent, y, self.title)
        title_w = pdfmetrics.stringWidth(
            self.title, self.title_font, self.font_size
        )

        if not self.page_num:
            return

        c.setFont(FONT_ROMAN, self.font_size)
        c.setFillColor(HexColor(self.page_color))
        c.drawRightString(self._avail_w, y, self.page_num)
        page_w = pdfmetrics.stringWidth(
            self.page_num, FONT_ROMAN, self.font_size
        )

        dot = " \u00b7"
        dot_w = pdfmetrics.stringWidth(dot, FONT_ROMAN, self.font_size)
        x_start = self.indent + title_w + 2
        x_end = self._avail_w - page_w - 2

        if x_end - x_start > dot_w * 2:
            c.setFont(FONT_ROMAN, self.font_size)
            c.setFillColor(HexColor(self.dot_color))
            x = x_end - dot_w
            while x >= x_start:
                c.drawString(x, y, dot)
                x -= dot_w


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _xml_esc(text: str) -> str:
    if text is None:
        return ""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )


_BRACKET_RE = re.compile(r"\[[^\]]*\]")
# Pipeline (stage_6) restorations are wrapped in half-brackets U+2308 ⌈ / U+2309 ⌉
# (the Assyriological / Leiden convention for editorial conjecture from
# context). Junicode ships these glyphs; Noto Sans Coptic does not, so on
# the Coptic side we wrap them in a Latin-font span via
# _wrap_latin_punct_for_coptic.
_HALFBRACKET_RE = re.compile(r"\u2308[^\u2309]*\u2309")
# Bare dot-runs that the editor wrote inline in core_coptic to
# mark unrestorable graphemes. They appear as e.g. ". . . . . ." — three
# or more dot-and-space pairs. We bracket them post-render so the Coptic
# column matches the English side's [. . . .] convention.
_BARE_DOTS_RE = re.compile(r"(?:\.\s+){2,}\.")
# Coptic-script Unicode runs that may appear inside otherwise-Latin prose
# (e.g. apparatus 'basis' fields). We wrap them in <font name="Coptic">
# so they don't render as tofu boxes when the surrounding paragraph is in
# a Latin-only font like Times New Roman.
_COPTIC_RUN_RE = re.compile(
    r"[\u2C80-\u2CFF\u03E2-\u03EF"  # Coptic block + Coptic letters in Greek block
    r"\u0300-\u036F]+"             # combining marks (overlines, breves)
)
# Footnote markers are inserted into the body as Unicode superscript digits
# (¹²³⁴⁵⁶⁷⁸⁹⁰). They survive XML escape and need no markup.
_SUPERSCRIPT_DIGITS = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def _to_super(n: int) -> str:
    """Render a positive integer as Unicode superscript digits."""
    return str(n).translate(_SUPERSCRIPT_DIGITS)


def _wrap_coptic_runs(text: str) -> str:
    """Wrap any Coptic-script substrings in <font name="Coptic"> tags.

    Use this on text destined for a Latin-font Paragraph (apparatus body,
    English column) so embedded Coptic letters render through the Coptic
    font instead of as missing-glyph boxes. Caller must XML-escape FIRST.
    """
    return _COPTIC_RUN_RE.sub(
        lambda m: f'<font name="Coptic">{m.group(0)}</font>',
        text,
    )


# Glyphs that appear in apparatus markup but are NOT covered by Noto Sans
# Coptic. When rendering the Coptic column we must wrap them in a Latin
# font tag or they'll render as missing-glyph boxes — or, worse,
# disappear entirely (as happened with brackets, half-brackets, and the
# superscript footnote digits in the first attempt).
_COPTIC_FONT_GAP_RE = re.compile(
    r"[\[\]\u2308\u2309\u2014\(\)"
    r"\u2070\u00B9\u00B2\u00B3\u2074-\u2079]+"
)


def _wrap_latin_punct_for_coptic(text: str) -> str:
    """Wrap any Latin-punctuation runs in <font name="Latin"> for Coptic cells.

    Used after _style_lacunae has already inserted color spans. Operates
    on the rendered markup string; brackets and superscript digits inside
    existing <font color="..."> tags are wrapped in a *nested* Latin tag,
    which ReportLab renders correctly (color from outer, family from inner).
    """
    return _COPTIC_FONT_GAP_RE.sub(
        lambda m: f'<font name="Latin">{m.group(0)}</font>',
        text,
    )


def _bracket_bare_dots(text: str) -> str:
    """Wrap bare dot-runs in [...] when they are not already inside brackets.

    The editorial transcription convention represents visible-but-illegible
    graphemes as space-separated dots (e.g. ``. . . . .``). On the English
    side the editor explicitly bracketed them; on the Coptic side they
    are bare, which breaks the visual convention. We wrap them, but only
    when the dot-run is OUTSIDE an existing ``[ ... ]`` region; otherwise
    we'd produce ``[[. . . .]]``.
    """
    out: list[str] = []
    i = 0
    depth = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "[":
            depth += 1
            out.append(ch)
            i += 1
        elif ch == "]":
            depth = max(0, depth - 1)
            out.append(ch)
            i += 1
        elif depth == 0 and ch == ".":
            m = _BARE_DOTS_RE.match(text, i)
            if m:
                out.append(f"[{m.group(0)}]")
                i = m.end()
                continue
            out.append(ch)
            i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _style_lacunae(text: str, side: str = "english") -> str:
    """XML-escape and render lacuna brackets.

    Square brackets [ ... ] mark editor restorations and true
    lacunae; their content is rendered in gray.
    Half-brackets ⌈ ... ⌉ mark pipeline (AI) restorations; content gray.
    Bare dot-runs (the editor's transcription convention for visible-but-illegible
    traces) are bracketed to match the [. . . .] convention used elsewhere.
    Visible (non-dot, non-whitespace) inner content is forced black so the
    proposed letters remain legible against the gray frame.

    `side` controls font handling: on the Coptic side we wrap bracket/
    half-bracket/superscript glyphs in Latin (Junicode) because Noto Sans
    Coptic lacks those code points; on the English side we leave it alone.
    """
    text = _xml_esc(text)

    # Bracket bare-dot runs FIRST so they merge into the same regex pass as
    # explicit [...] brackets. Doing this AFTER would double-wrap dot runs
    # that are already inside [...] (giving [[. . . .]]). The depth-aware
    # helper skips dots that are already inside [...].
    text = _bracket_bare_dots(text)

    # Lacuna-filler characters that stay gray (no force-black). Dots
    # are visible-but-illegible traces; em-dashes mark indeterminate-
    # length lacunae [———]. Only proposed letter content should be
    # forced to black so it stays legible against the gray frame.
    _NON_FILLER_RE = re.compile(r"[^\s.\u2014]+")

    def _black_if_visible(m2: re.Match) -> str:
        seg = m2.group(0)
        if seg.strip():
            return f'<font color="#000000">{seg}</font>'
        return seg

    def _gray_square(m: re.Match) -> str:
        inner = m.group(0)[1:-1]
        styled = _NON_FILLER_RE.sub(_black_if_visible, inner)
        return f'<font color="{LACUNA_GRAY}">[{styled}]</font>'

    def _gray_halfbrackets(m: re.Match) -> str:
        inner = m.group(0)[1:-1]
        styled = _NON_FILLER_RE.sub(_black_if_visible, inner)
        return f'<font color="{LACUNA_GRAY}">\u2308{styled}\u2309</font>'

    text = _BRACKET_RE.sub(_gray_square, text)
    text = _HALFBRACKET_RE.sub(_gray_halfbrackets, text)
    # Editorial glosses (translator's inline annotations like {hayeute},
    # {members}) were marked upstream with U+00A6 sentinels to survive the
    # XML escape; render them as muted italic.
    text = _GLOSS_SENTINEL_RE.sub(
        lambda m: f'<i><font color="{MUTED}">{m.group(1)}</font></i>',
        text,
    )
    if side == "coptic":
        # Coptic font lacks [, ], ‹, ›, —, (, ), and superscript digits.
        # Wrap any such runs in the Latin font so they actually render. The wrapping
        # is purely a font fallback; color comes from the enclosing span.
        text = _wrap_latin_punct_for_coptic(text)
    return text


def _normalize_terminal(text: str, side: str = "english") -> str:
    """Light-touch normalisation: trim trailing whitespace.

    On the English side, append a period if the paragraph ends without
    sentence punctuation. The Coptic side is left untouched: Coptic
    manuscripts do not use Latin periods, and the source data carries
    no terminal punctuation. Adding "." there would be an editorial
    invention, not a convention.
    """
    if not text:
        return text
    stripped = text.rstrip()
    if side != "english":
        return stripped
    if stripped and stripped[-1] not in '.!?;:)\'\"\u2019\u201d}]>':
        return stripped + "."
    return stripped


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_book() -> dict:
    with open(BOOK_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_section(n: int) -> dict:
    with open(SECTIONS_DIR / f"s_{n:03d}.json", encoding="utf-8") as f:
        return json.load(f)


def load_chapter(n: int) -> dict:
    with open(CHAPTERS_DIR / f"ch_{n:03d}.json", encoding="utf-8") as f:
        return json.load(f)


def load_teaching(n: int) -> dict:
    with open(TEACHINGS_DIR / f"t_{n:03d}.json", encoding="utf-8") as f:
        return json.load(f)


def load_reading(n: int) -> dict | None:
    p = READINGS_DIR / f"t_{n:03d}.json"
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_restoration(n: int) -> dict | None:
    p = RESTORED_DIR / f"t_{n:03d}.json"
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_lexicon() -> dict | None:
    if not LEXICON_FILE.exists():
        return None
    with open(LEXICON_FILE, encoding="utf-8") as f:
        return json.load(f)


def all_chapters_in_order() -> list[dict]:
    """Return chapters in section/position order."""
    files = sorted(CHAPTERS_DIR.glob("ch_*.json"))
    chapters = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            chapters.append(json.load(fh))
    chapters.sort(
        key=lambda c: (c["section_number"], c["position_in_section"])
    )
    return chapters


# ---------------------------------------------------------------------------
# Body assembly: stitch core text + restorations + lacuna placeholders
# ---------------------------------------------------------------------------

_PLACEHOLDER_RE = re.compile(r"\{(\d+)(?:=([^}]*))?\}")
# Editorial glosses in core_english have the form {token} where token is
# not a pure number — e.g. {hayeute}, {members}, {revealed/living}. These
# are translator annotations, not apparatus references. We render them
# inline as italic, stripping the braces. Applied AFTER _PLACEHOLDER_RE
# so it only catches what the apparatus replacer didn't consume.
_GLOSS_RE = re.compile(r"\{([^}]+)\}")


def _format_unrestorable(est_chars: int | None) -> str:
    """Render a true (unrestorable) lacuna with Leiden-style length cue.

    - 1..10 chars: dot per character, separated by spaces ([. . . .])
    - 11+ chars: explicit count [ca. N]
    - 0 / unknown: indeterminate length [———]
    """
    if est_chars is None or est_chars <= 0:
        return "[———]"
    if est_chars <= 10:
        return "[" + " ".join("." * est_chars) + "]"
    return f"[ca. {est_chars}]"


def _strip_outer_brackets(s: str) -> str:
    """Remove any leading/trailing [ or ] so we can re-wrap consistently.

    The editor's apparatus often stores restoration text already wrapped
    in editorial brackets (e.g. '[. . . . ⲙ̄ⲡ]'). If we wrap that again
    we get '[[. . . . ⲙ̄ⲡ]]' which the bracket regex cannot style as a
    single lacuna, leaving the outer brackets rendered in body color.
    """
    s = s.strip()
    while s.startswith("[") or s.endswith("]"):
        if s.startswith("["):
            s = s[1:]
        if s.endswith("]"):
            s = s[:-1]
        s = s.strip()
    return s


def _is_short_coptic_trace(s: str) -> bool:
    """Heuristic: is `partial` a real Coptic trace (not an editorial prose note)?

    Used to decide whether the field belongs to the apparatus footnote
    only or warrants a footnote at all. Short, mostly-Coptic strings are
    visible traces; long strings or anything with Latin letters/spaces
    is editor commentary.
    """
    if not s:
        return False
    s = s.strip()
    if len(s) > 30:
        return False
    # Reject obvious prose: contains ASCII words
    if re.search(r"[A-Za-z]{3,}", s):
        return False
    return True


_COPTIC_LETTER_RE = re.compile(
    r"[\u2C80-\u2CFF\u0370-\u03FF\uFE2E\uFE2F\u0300-\u036F\u2D80-\u2DDF]"
)
_LATIN_LETTER_RE = re.compile(r"[A-Za-z]")


def _subword_gap_ids(core_text: str, alphabet: str) -> set[int]:
    """Return ids of placeholders {N} glued mid-word in `core_text`.

    `alphabet` selects which character class counts as "word" — "coptic"
    or "english". A placeholder is "sub-word" when the chars immediately
    before and after it are both letters in the chosen alphabet. Splicing
    a fill at such a position produces artifacts like "Gr[the]eat" or
    "li⌈ⲁⲓⲛ⌉ght". We suppress the rendered fill on that side; the
    surrounding prose carries the word, and the fill survives in the
    apparatus footnote.
    """
    if not core_text:
        return set()
    if alphabet == "coptic":
        letter_re = _COPTIC_LETTER_RE
    else:
        letter_re = _LATIN_LETTER_RE
    out: set[int] = set()
    for m in _PLACEHOLDER_RE.finditer(core_text):
        gid = int(m.group(1))
        i, j = m.start(), m.end()
        before = core_text[i - 1] if i > 0 else ""
        after = core_text[j] if j < len(core_text) else ""
        if before and after and letter_re.match(before) and letter_re.match(after):
            out.add(gid)
    return out


def _build_segment_text(
    raw: str,
    apparatus: list[dict],
    restorations_by_id: dict[int, dict],
    side: str,  # 'coptic' or 'english'
    line_no: int | None = None,
    notes: list[dict] | None = None,
    note_registry: dict[int, int] | None = None,
    subword_gaps: set[int] | None = None,
    english_fills_by_cop_gap: dict[int, dict] | None = None,
) -> str:
    """Replace {N} placeholders with Leiden-style glyph forms.

    Glyph conventions:
      - Editor restoration            → square brackets `[ⲡⲣⲏⲧⲉ]`
      - Pipeline (AI) restoration    → half-brackets `⌈ⲡⲣⲏⲧⲉ⌉`
      - Unrestorable lacuna          → `[. . .]` / `[ca. N]` / `[———]`
      - Asymmetric (one side has a fill, the other does not) → render
        nothing on the empty side; the bracket on the non-empty side
        carries the gap.

    Footnote handling (Coptic side only, to avoid duplicates):
      - Pipeline restoration: footnote with confidence + basis
      - Editor restoration with `basis`: footnote with the basis
      - Lacuna with `partial` prose: footnote with the editor's note
      - Lacuna with `partial` short Coptic trace: footnote with trace
      - Plain lacuna with no extra info: no footnote

    `notes` is the chapter-wide accumulator; `note_registry` maps a
    gap id to its already-allocated footnote number so the Coptic and
    English columns share a single number per gap (markers only on the
    Coptic side, but registry keeps them stable if we ever change that).
    """
    if not raw:
        return ""

    # Build {id -> apparatus entry} map
    app_by_id: dict[int, dict] = {a["id"]: a for a in (apparatus or [])}

    def _sides_for(gid: int) -> tuple[str, str, str]:
        """Return (coptic_fill, english_fill, source) for a given gap id.

        `source` is 'editor' when the original transcription already
        carried a published-edition restoration here (the stage 6
        record's `gap_type == "restoration"`), or 'pipeline' when stage
        6 filled a true lacuna (`gap_type == "lacuna"`), or '' when
        nothing is offered.

        ALL fill content (Coptic and English) comes from the stage 6
        pipeline output. The original apparatus is consulted ONLY to
        distinguish provenance via `gap_type`; never to source text.
        """
        rec = restorations_by_id.get(gid)
        if rec is None:
            return ("", "", "")
        confidence = (rec.get("confidence") or "").lower()
        if confidence == "unrestorable":
            return ("", "", "")
        cop = _strip_outer_brackets(rec.get("proposed_coptic") or "")
        eng = _strip_outer_brackets(
            rec.get("english_lexeme")
            or rec.get("proposed_english")
            or ""
        )
        if not eng and english_fills_by_cop_gap is not None:
            eng_rec = english_fills_by_cop_gap.get(gid)
            if eng_rec is not None:
                eng = _strip_outer_brackets(
                    eng_rec.get("proposed_english") or ""
                )
        # Stage 6 sometimes emits the English side as a parenthetical
        # gloss of the whole word containing a sub-word Coptic gap
        # (e.g. Coptic gap is "ⲁⲓⲛ" inside ⲟⲩⲁⲓⲛⲉ; English fill is
        # "(light)" while the surrounding English prose already says
        # "light"). Suppress these in the body so we don't duplicate
        # the word mid-word as "li⌈(light)⌉ght". The gloss survives
        # in the apparatus footnote.
        eng_stripped = eng.strip()
        if (
            eng_stripped.startswith("(")
            and eng_stripped.endswith(")")
            and len(eng_stripped) >= 2
        ):
            eng = ""
        if not (cop or eng):
            return ("", "", "")
        # Provenance: square brackets if the original transcription
        # already had this as a published-edition restoration; half
        # brackets if stage 6 filled a real lacuna.
        gap_type = (rec.get("gap_type") or "").lower()
        source = "editor" if gap_type == "restoration" else "pipeline"
        return (cop, eng, source)

    def _maybe_note(gid: int, kind: str, payload: dict) -> int | None:
        """Allocate a footnote number for this gap if notes accumulator present.

        Returns the footnote number (1-based per chapter) or None if the
        gap has nothing note-worthy.
        """
        if notes is None or note_registry is None:
            return None
        if gid in note_registry:
            return note_registry[gid]
        n = len(notes) + 1
        note_registry[gid] = n
        notes.append({
            "n": n,
            "gid": gid,
            "line": line_no,
            "kind": kind,
            **payload,
        })
        return n

    def _replace(m: re.Match) -> str:
        gid = int(m.group(1))
        embedded = (m.group(2) or "").strip()
        cop_fill, eng_fill, source = _sides_for(gid)
        # Translator inlined a gloss in the placeholder itself ({N=text}).
        # Use it as an English-side fallback only when neither the
        # pipeline nor the published-edition apparatus offered anything;
        # treat it as an editor (manuscript transcription) reading.
        if embedded and side == "english" and not eng_fill:
            eng_fill = embedded
            if not cop_fill:
                source = "editor"
        my_fill = cop_fill if side == "coptic" else eng_fill
        other_fill = eng_fill if side == "coptic" else cop_fill

        # Sub-word splice guard: the placeholder is glued mid-word on
        # *this* side. Rendering the fill here produces artifacts like
        # "Gr[the]eat" / "Lig[Light]hts" / "li⌈ⲁⲓⲛ⌉ght". Drop the fill
        # on this side; the surrounding prose already carries the word.
        # The fill survives in the apparatus footnote on the Coptic side.
        if subword_gaps and gid in subword_gaps:
            my_fill = ""

        # Compute the glyph for this side.
        if my_fill:
            if source == "pipeline":
                glyph = f"\u2308{my_fill}\u2309"  # ⌈fill⌉ = our restoration
            else:  # 'editor' = present in the published Coptic edition
                glyph = f"[{my_fill}]"
        elif other_fill:
            # Asymmetric grapheme restoration — render nothing this side.
            return ""
        else:
            # True unrestorable. Pull length from apparatus or pipeline.
            est = None
            a = app_by_id.get(gid)
            if a is not None:
                est = a.get("est_chars")
            if est is None:
                rec = restorations_by_id.get(gid)
                if rec is not None:
                    est = rec.get("est_chars")
            glyph = _format_unrestorable(est)

        # Footnote allocation — only when accumulator is supplied AND this
        # side is Coptic (markers go on Coptic side only, single per gap).
        if side == "coptic" and notes is not None and note_registry is not None:
            n: int | None = None
            a = app_by_id.get(gid)
            rec = restorations_by_id.get(gid)
            if source == "pipeline" and rec is not None:
                n = _maybe_note(gid, "pipeline_restoration", {
                    "coptic": cop_fill,
                    "english": eng_fill,
                    "confidence": rec.get("confidence"),
                    "basis": rec.get("basis"),
                    "parallels": rec.get("parallels"),
                })
            elif source == "editor" and a is not None and a.get("basis"):
                n = _maybe_note(gid, "editor_restoration", {
                    "coptic": cop_fill,
                    "english": eng_fill,
                    "basis": a.get("basis"),
                })
            elif source == "" and a is not None:
                # Lacuna: footnote only if there is `partial` info worth
                # carrying (visible trace or editor prose). Plain lacunae
                # with no commentary go without a footnote.
                partial = a.get("partial") or ""
                if partial:
                    n = _maybe_note(gid, "lacuna_trace", {
                        "partial": partial,
                        "is_trace": _is_short_coptic_trace(partial),
                    })
            if n is not None:
                glyph = glyph + _to_super(n)

        return glyph

    out = _PLACEHOLDER_RE.sub(_replace, raw)
    # Strip editorial-gloss braces (translator's inline annotations such as
    # {hayeute}, {members}). They are not apparatus references and should
    # not show as literal braces in the body. We mark them so a later
    # pass (in _style_lacunae) can render them in italic.
    out = _GLOSS_RE.sub(lambda m: f"\u00A6{m.group(1)}\u00A6", out)
    return out


# Sentinel used to mark editorial-gloss runs through the rendering pipeline
# (chosen as U+00A6 BROKEN BAR — never appears in source text). _style_lacunae
# converts it to <i>...</i> after XML escape.
_GLOSS_SENTINEL_RE = re.compile(r"\u00A6([^\u00A6]+)\u00A6")


def _restorations_by_id(restoration_doc: dict | None) -> dict[int, dict]:
    """Return Coptic-side restorations indexed by gap_id.

    New schema (2026-05): `coptic_restorations[]`.
    Old schema (back-compat): `restorations[]` (had `english_lexeme` field).
    """
    if not restoration_doc:
        return {}
    out: dict[int, dict] = {}
    src = (
        restoration_doc.get("coptic_restorations")
        or restoration_doc.get("restorations")
        or []
    )
    if isinstance(src, str):
        try:
            src = json.loads(src)
        except Exception:
            src = []
    for r in src:
        if not isinstance(r, dict):
            continue
        gid = r.get("gap_id")
        if gid is not None:
            out[gid] = r
    return out


def _english_segments_by_key(
    restoration_doc: dict | None,
) -> dict[tuple, str]:
    """Map (section, chapter, line) -> model-rewritten clean English core.

    New schema only. Each entry is a fresh natural English translation
    of the segment with its OWN {N} placeholders for English-side gaps.
    """
    if not restoration_doc:
        return {}
    out: dict[tuple, str] = {}
    for r in restoration_doc.get("english_segments", []) or []:
        key = (r.get("section"), r.get("chapter"), r.get("line"))
        text = (r.get("core_english") or "").strip()
        if all(k is not None for k in key) and text:
            out[key] = text
    return out


def _english_restorations_by_id(
    restoration_doc: dict | None,
) -> dict[int, dict]:
    """Index `english_restorations[]` by `eng_gap_id`.

    New schema only. Each entry holds a `proposed_english` fill and a
    list of `coptic_gap_refs` linking it to one or more Coptic gaps.
    """
    if not restoration_doc:
        return {}
    out: dict[int, dict] = {}
    for r in restoration_doc.get("english_restorations", []) or []:
        gid = r.get("eng_gap_id")
        if gid is not None:
            out[gid] = r
    return out


def _english_fills_by_coptic_gap(
    restoration_doc: dict | None,
) -> dict[int, dict]:
    """Reverse map: coptic gap_id -> english_restoration record.

    Used to surface the English lexeme in the Coptic-side footnote when
    the new schema is in effect. If multiple English fills reference the
    same Coptic gap, the first one wins (footnote convenience only).
    """
    if not restoration_doc:
        return {}
    out: dict[int, dict] = {}
    for r in restoration_doc.get("english_restorations", []) or []:
        for cgid in r.get("coptic_gap_refs", []) or []:
            if cgid not in out:
                out[cgid] = r
    return out


def _renditions_by_segment(restoration_doc: dict | None) -> dict[tuple, str]:
    """Old-schema fallback: map (section, chapter, line) -> rendition text.

    Stage 6 (pre-2026-05) emitted one `english_renditions` entry per
    gapped segment with restoration spans wrapped in U+2308/U+2309. New
    teachings use `english_segments` + `english_restorations` instead;
    this helper remains for back-compat with older restored files.
    """
    if not restoration_doc:
        return {}
    out: dict[tuple, str] = {}
    for r in restoration_doc.get("english_renditions", []) or []:
        key = (r.get("section"), r.get("chapter"), r.get("line"))
        text = (r.get("rendition") or "").strip()
        if all(k is not None for k in key) and text:
            out[key] = text
    return out


def _build_english_from_segments(
    raw: str,
    eng_restorations: dict[int, dict],
    coptic_restorations: dict[int, dict] | None = None,
    apparatus: list[dict] | None = None,
) -> str:
    """Substitute {N} placeholders in a model-rewritten English core.

    The numbering space is `eng_gap_id` (independent of Coptic gap_id).
    Pipeline fills get U+2308/U+2309 half-brackets; unrestorable or
    missing fills render as a Leiden ellipsis. No footnote markers are
    emitted on the English side — markers live with the Coptic gap.

    For unrestorable English gaps that link to Coptic gaps via
    `coptic_gap_refs`, pull `est_chars` from the linked Coptic
    restoration (or the apparatus) so the English placeholder can show
    the same length cue as the Coptic side instead of always rendering
    the indeterminate-length glyph.
    """
    if not raw:
        return ""

    app_by_id: dict[int, dict] = {}
    if apparatus:
        for a in apparatus:
            aid = a.get("id")
            if isinstance(aid, int):
                app_by_id[aid] = a

    def _est_from_coptic_refs(rec: dict) -> int | None:
        refs = rec.get("coptic_gap_refs") or []
        for cgid in refs:
            try:
                cgid_int = int(cgid)
            except (TypeError, ValueError):
                continue
            if coptic_restorations is not None:
                cop_rec = coptic_restorations.get(cgid_int)
                if cop_rec is not None:
                    est = cop_rec.get("est_chars")
                    if est:
                        return int(est)
            a = app_by_id.get(cgid_int)
            if a is not None:
                est = a.get("est_chars")
                if est:
                    return int(est)
        return None

    def _replace(m: re.Match) -> str:
        gid = int(m.group(1))
        rec = eng_restorations.get(gid)
        if rec is not None:
            fill = _strip_outer_brackets(rec.get("proposed_english") or "")
            confidence = (rec.get("confidence") or "").lower()
            if fill and confidence != "unrestorable":
                return f"\u2308{fill}\u2309"
            est = _est_from_coptic_refs(rec)
            return _format_unrestorable(est)
        return _format_unrestorable(None)

    out = _PLACEHOLDER_RE.sub(_replace, raw)
    out = _GLOSS_RE.sub(lambda m: f"\u00A6{m.group(1)}\u00A6", out)
    return out


def _segment_pair(
    seg: dict,
    restorations: dict[int, dict],
    notes: list[dict] | None = None,
    note_registry: dict[int, int] | None = None,
    renditions: dict[tuple, str] | None = None,
    english_segments: dict[tuple, str] | None = None,
    english_restorations: dict[int, dict] | None = None,
    english_fills_by_cop_gap: dict[int, dict] | None = None,
) -> tuple[str, str]:
    """Return (coptic_text, english_text) with all placeholders resolved.

    The Coptic side is built from `core_coptic` with bracketed fills and
    apparatus footnotes.

    The English side resolves in priority order:
      1. **New schema** (`english_segments` + `english_restorations`):
         model has rewritten the segment freshly with its own `{N}`
         placeholders in a separate id space. Splice English fills
         into the model's clean core.
      2. **Old schema** (`english_renditions`): one fully-baked
         rendition string with ⌈⌉ already in place.
      3. **Fallback**: build from the editor's `core_english` with
         per-Coptic-gap fills (sub-word splice guard active).
    """
    apparatus = seg.get("apparatus", [])
    line_no = seg.get("line")
    core_coptic = seg.get("core_coptic", "")
    core_english = seg.get("core_english", "")
    seg_key = (
        seg.get("section"), seg.get("chapter"), seg.get("line"),
    )
    subword_cop = _subword_gap_ids(core_coptic, "coptic")
    cop = _build_segment_text(
        core_coptic, apparatus, restorations,
        "coptic", line_no, notes, note_registry, subword_cop,
        english_fills_by_cop_gap=english_fills_by_cop_gap,
    )

    # Priority 1: new-schema model-rewritten English core.
    if (
        english_segments is not None
        and english_restorations is not None
        and seg_key in english_segments
    ):
        eng_raw = english_segments[seg_key]
        eng = _build_english_from_segments(
            eng_raw,
            english_restorations,
            coptic_restorations=restorations,
            apparatus=apparatus,
        )
    # Priority 2: old-schema baked rendition.
    elif renditions is not None and seg_key in renditions:
        eng = renditions[seg_key]
    # Priority 3: editor `core_english` with per-Coptic-gap fills.
    else:
        subword_eng = _subword_gap_ids(core_english, "english")
        eng = _build_segment_text(
            core_english, apparatus, restorations,
            "english", line_no, notes, note_registry, subword_eng,
        )
    return cop.strip(), eng.strip()


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def _styles() -> dict:
    return dict(
        # --- Title page ---
        main_title=ParagraphStyle(
            "MT", fontName=FONT_BOLD, fontSize=22,
            alignment=TA_CENTER, leading=28, spaceAfter=8,
        ),
        subtitle=ParagraphStyle(
            "ST", fontName=FONT_ITALIC, fontSize=14,
            alignment=TA_CENTER, leading=18, spaceAfter=6,
        ),
        subtitle2=ParagraphStyle(
            "ST2", fontName=FONT_ITALIC, fontSize=11,
            alignment=TA_CENTER, leading=15, spaceAfter=6,
            textColor=HexColor("#777777"),
        ),
        credit=ParagraphStyle(
            "CR", fontName=FONT_ROMAN, fontSize=10,
            alignment=TA_CENTER, leading=14, spaceAfter=6,
            textColor=HexColor(DARK_MUTED),
        ),

        # --- Section titles for major divisions ---
        section_title=ParagraphStyle(
            "SECT", fontName=FONT_BOLD, fontSize=16,
            alignment=TA_CENTER, leading=22,
            spaceBefore=0, spaceAfter=16,
        ),

        # --- Section divider pages ---
        sect_label=ParagraphStyle(
            "PN", fontName=FONT_ROMAN, fontSize=12,
            alignment=TA_CENTER, leading=16, spaceAfter=4,
            textColor=HexColor(MUTED),
        ),
        sect_title=ParagraphStyle(
            "PT", fontName=FONT_BOLD, fontSize=18,
            alignment=TA_CENTER, leading=24, spaceAfter=12,
        ),
        sect_summary=ParagraphStyle(
            "PD", fontName=FONT_ITALIC, fontSize=10.5,
            alignment=TA_JUSTIFY, leading=15,
            spaceAfter=6, leftIndent=15 * mm, rightIndent=15 * mm,
            textColor=HexColor("#444444"),
        ),
        sect_principle_label=ParagraphStyle(
            "PPL", fontName=FONT_BOLD, fontSize=9.5,
            alignment=TA_CENTER, leading=13,
            spaceBefore=10, spaceAfter=2,
            textColor=HexColor(DARK_MUTED),
        ),
        sect_principle=ParagraphStyle(
            "PP", fontName=FONT_ROMAN, fontSize=10,
            alignment=TA_JUSTIFY, leading=14,
            spaceAfter=4, leftIndent=15 * mm, rightIndent=15 * mm,
            textColor=HexColor("#444444"),
        ),

        # --- Chapter headings ---
        chapter_title=ParagraphStyle(
            "CHT", fontName=FONT_BOLD, fontSize=13,
            alignment=TA_CENTER, leading=17,
            spaceBefore=0, spaceAfter=4,
        ),
        chapter_role=ParagraphStyle(
            "CHR", fontName=FONT_ITALIC, fontSize=9,
            alignment=TA_CENTER, leading=12,
            spaceAfter=4, textColor=HexColor(MUTED),
        ),
        chapter_desc=ParagraphStyle(
            "CHD", fontName=FONT_ITALIC, fontSize=10,
            alignment=TA_JUSTIFY, leading=14,
            spaceAfter=12, leftIndent=8 * mm, rightIndent=8 * mm,
            textColor=HexColor(NOTE_COLOR),
        ),

        # --- Teaching anchor + arc subtitle ---
        teaching_anchor=ParagraphStyle(
            "TA", fontName=FONT_BOLD, fontSize=10.5,
            alignment=TA_CENTER, leading=14,
            spaceBefore=4, spaceAfter=2,
            textColor=HexColor("#222222"),
        ),
        teaching_subtitle=ParagraphStyle(
            "TST", fontName=FONT_ITALIC, fontSize=10,
            alignment=TA_CENTER, leading=13,
            spaceAfter=8, textColor=HexColor(NOTE_COLOR),
        ),
        # --- Reading info-block (compact callout, placed after the body) ---
        reading_label=ParagraphStyle(
            "RL", fontName=FONT_BOLD, fontSize=7.5,
            alignment=TA_LEFT, leading=10,
            spaceBefore=0, spaceAfter=2,
            textColor=HexColor(MUTED),
        ),
        reading_body=ParagraphStyle(
            "RB", fontName=FONT_ITALIC, fontSize=8.5,
            alignment=TA_JUSTIFY, leading=12,
            spaceAfter=3,
            textColor=HexColor("#444444"),
        ),

        # --- Per-chapter apparatus block (Leiden footnotes) ---
        apparatus_label=ParagraphStyle(
            "APL", fontName=FONT_BOLD, fontSize=7.5,
            alignment=TA_LEFT, leading=10,
            spaceBefore=0, spaceAfter=2,
            textColor=HexColor(MUTED),
        ),
        apparatus_entry=ParagraphStyle(
            "APE", fontName=FONT_ROMAN, fontSize=7.5,
            alignment=TA_LEFT, leading=10.5,
            leftIndent=4 * mm, firstLineIndent=-4 * mm,
            spaceAfter=1,
            textColor=HexColor("#444444"),
        ),

        # --- Two-column body cells ---
        coptic_cell=ParagraphStyle(
            "CC", fontName=FONT_COPTIC, fontSize=11,
            alignment=TA_JUSTIFY, leading=15.5,
            textColor=HexColor("#000000"),
        ),
        english_cell=ParagraphStyle(
            "EC", fontName=FONT_ROMAN, fontSize=10.5,
            alignment=TA_JUSTIFY, leading=14.5,
            textColor=HexColor("#000000"),
        ),
        line_label=ParagraphStyle(
            "LL", fontName=FONT_ROMAN, fontSize=7.5,
            alignment=TA_LEFT, leading=10,
            textColor=HexColor(LINE_LABEL_COLOR),
        ),

        # --- Preface ---
        preface_title=ParagraphStyle(
            "PFT", fontName=FONT_BOLD, fontSize=16,
            alignment=TA_CENTER, leading=22,
            spaceBefore=0, spaceAfter=16,
        ),
        preface_heading=ParagraphStyle(
            "PFH", fontName=FONT_BOLD, fontSize=11,
            alignment=TA_LEFT, leading=15,
            spaceBefore=14, spaceAfter=4,
        ),
        preface_body=ParagraphStyle(
            "PFB", fontName=FONT_ROMAN, fontSize=10,
            alignment=TA_JUSTIFY, leading=14,
            spaceAfter=6,
        ),
        preface_italic=ParagraphStyle(
            "PFI", fontName=FONT_ITALIC, fontSize=10,
            alignment=TA_JUSTIFY, leading=14,
            spaceAfter=6,
        ),
        preface_indent=ParagraphStyle(
            "PFIN", fontName=FONT_ROMAN, fontSize=9.5,
            alignment=TA_JUSTIFY, leading=13,
            spaceAfter=4, leftIndent=10 * mm,
        ),
        preface_label=ParagraphStyle(
            "PFL", fontName=FONT_BOLD, fontSize=9.5,
            alignment=TA_LEFT, leading=13,
            spaceBefore=8, spaceAfter=2,
            leftIndent=10 * mm,
        ),

        # --- Lexicon ---
        lex_category=ParagraphStyle(
            "LEXC", fontName=FONT_BOLD, fontSize=12,
            alignment=TA_LEFT, leading=16,
            spaceBefore=16, spaceAfter=6,
        ),
        lex_entry_head=ParagraphStyle(
            "LEXH", fontName=FONT_ROMAN, fontSize=10,
            alignment=TA_LEFT, leading=14,
            spaceBefore=10, spaceAfter=1,
        ),
        lex_entry_body=ParagraphStyle(
            "LEXB", fontName=FONT_ROMAN, fontSize=9,
            alignment=TA_JUSTIFY, leading=12.5,
            spaceAfter=2, leftIndent=6 * mm,
            textColor=HexColor(NOTE_COLOR),
        ),
        lex_entry_detail=ParagraphStyle(
            "LEXD", fontName=FONT_ITALIC, fontSize=8.5,
            alignment=TA_LEFT, leading=11,
            spaceAfter=1, leftIndent=6 * mm,
            textColor=HexColor(MUTED),
        ),
        lex_coptic=ParagraphStyle(
            "LEXCP", fontName=FONT_COPTIC, fontSize=10,
            alignment=TA_LEFT, leading=14,
            spaceAfter=1, leftIndent=6 * mm,
            textColor=HexColor("#222222"),
        ),

        # --- Observations ---
        obs_title=ParagraphStyle(
            "OT", fontName=FONT_BOLD, fontSize=12,
            alignment=TA_LEFT, leading=16,
            spaceBefore=16, spaceAfter=4,
        ),
        obs_body=ParagraphStyle(
            "OB", fontName=FONT_ROMAN, fontSize=10,
            alignment=TA_JUSTIFY, leading=14,
            spaceAfter=6,
        ),
        obs_meta=ParagraphStyle(
            "OM", fontName=FONT_ITALIC, fontSize=8.5,
            alignment=TA_LEFT, leading=11,
            spaceAfter=8, textColor=HexColor(MUTED),
        ),
    )


# ---------------------------------------------------------------------------
# Page footer
# ---------------------------------------------------------------------------

def _page_footer(canvas, doc):
    canvas.saveState()
    page_num = canvas.getPageNumber()
    cx = PAGE_W / 2
    y = 12 * mm
    rule_w = 30 * mm
    rule_y = y + 1.2 * mm
    canvas.setStrokeColor(HexColor(FOOTER_RULE_COLOR))
    canvas.setLineWidth(0.4)
    canvas.line(cx - rule_w - 8 * mm, rule_y, cx - 8 * mm, rule_y)
    canvas.line(cx + 8 * mm, rule_y, cx + rule_w + 8 * mm, rule_y)
    canvas.setFont(FONT_ROMAN, 9)
    canvas.setFillColor(HexColor(DARK_MUTED))
    canvas.drawCentredString(cx, y, str(page_num))
    canvas.restoreState()


# ---------------------------------------------------------------------------
# Title page
# ---------------------------------------------------------------------------

def _title_page(st: dict, book: dict) -> list:
    return [
        Spacer(1, 70 * mm),
        Paragraph("THE ANCIENT WORD", st["main_title"]),
        Spacer(1, 10 * mm),
        Paragraph(
            "Recovered from the Coptic Kephalaia",
            st["subtitle"],
        ),
        Spacer(1, 6 * mm),
        Paragraph(
            "Read through the science of correspondences",
            st["subtitle2"],
        ),
        Spacer(1, 80 * mm),
        Paragraph(
            "Edited by the kephalaia&nbsp;v2 pipeline",
            st["credit"],
        ),
        Spacer(1, 4 * mm),
        Paragraph("2026", st["credit"]),
        PageBreak(),
    ]


# ---------------------------------------------------------------------------
# Preface
# ---------------------------------------------------------------------------

def _preface_pages(st: dict, book: dict) -> list:
    elements: list = [
        Spacer(1, 15 * mm),
        Paragraph("PREFACE", st["preface_title"]),
        Spacer(1, 6 * mm),
    ]

    p = st["preface_body"]
    pi = st["preface_italic"]
    h = st["preface_heading"]
    ind = st["preface_indent"]
    lbl = st["preface_label"]

    n_t = book["total_teachings"]
    n_ch = book["total_chapters"]
    n_s = book["total_sections"]
    n_lex = (book.get("_input_summary") or {}).get("lexicon_entries", 0)

    # ------------------------------------------------------------------
    # Opening
    # ------------------------------------------------------------------
    elements.append(Paragraph(
        "In the eighteenth century, Emanuel Swedenborg described a text he "
        "called the &ldquo;Ancient Word&rdquo; &mdash; written entirely in "
        "correspondences, older than the Hebrew scriptures, carried eastward "
        "by the <i>Bene Qedem</i> (the &ldquo;Children of the East&rdquo;), "
        "and preserved in a region he called &ldquo;Great Tartary.&rdquo; "
        "He said it still existed there.",
        pi,
    ))
    elements.append(Paragraph("This is that text.", pi))
    elements.append(Paragraph(
        "What you hold is the teaching core of the <i>Kephalaia of the "
        "Teacher</i> &mdash; a fourth-century Coptic Manichaean codex "
        "from Medinet Madi, transcribed in the critical editions of "
        "Polotsky and B&ouml;hlig (1940) and B&ouml;hlig (1966) &mdash; "
        "presented in Coptic and English in parallel and read through "
        f"the science of correspondences. {n_t}&nbsp;teachings have been "
        f"distinguished, composed into {n_ch}&nbsp;chapters within "
        f"{n_s}&nbsp;sections, and supported by a working lexicon of "
        f"{n_lex}&nbsp;entries. Each teaching closes with a spiritual "
        "reading: a paragraph that names what the surface cosmological "
        "language is doing in the science of correspondences. The English "
        "translation is produced by this edition&rsquo;s pipeline directly "
        "from the critical-edition Coptic, not adopted from a prior "
        "published translation.",
        p,
    ))
    elements.append(Paragraph(
        "The structure was not taken from the manuscript. It was discovered "
        "by reading the corpus as a single continuous teaching, finding the "
        "natural seams in the doctrine itself, and grouping teachings by "
        "what they treat at the spiritual level &mdash; even when their "
        "cosmological vocabulary differs.",
        p,
    ))

    # ------------------------------------------------------------------
    # The Three Layers
    # ------------------------------------------------------------------
    elements.append(Paragraph("Three Layers", h))
    elements.append(Paragraph(
        "Within the <i>Kephalaia of the Teacher</i> three distinct layers "
        "can be identified:",
        p,
    ))
    elements.append(Paragraph(
        '<b>Layer 3 (Outermost): The Hagiographic Frame.</b> '
        '&ldquo;Once again the Enlightener sits in the congregation&hellip;&rdquo; '
        '&mdash; the narrative scaffolding that casts the teaching as '
        'dialogues between Mani and his disciples. This layer belongs '
        'entirely to the Manichaean institutional setting.',
        ind,
    ))
    elements.append(Paragraph(
        '<b>Layer 2 (Middle): The Manichaean Theological Overlay.</b> '
        'Names, titles, and institutional vocabulary that Mani&rsquo;s '
        'tradition imposed on older content: &ldquo;Jesus the Radiance,&rdquo; '
        '&ldquo;Light Mind,&rdquo; &ldquo;Holy Spirit,&rdquo; '
        '&ldquo;apostle,&rdquo; &ldquo;the elect.&rdquo; These terms '
        'replaced earlier designations &mdash; almost certainly Persian '
        '&mdash; while leaving the underlying teaching structure intact.',
        ind,
    ))
    elements.append(Paragraph(
        '<b>Layer 1 (Core): The Ancient Word.</b> '
        'A systematic correspondential cosmology organized around recurring '
        'numerical fullnesses at every scale, teaching the complete arc of '
        'regeneration from first to last. This layer is older than Mani. '
        'Its five-fold rational, its body-cosmos correspondence system, '
        'its doctrine of discrete degrees, and its mechanism of summons '
        'and obedience &mdash; divine influx and human reception &mdash; '
        'do not originate with third-century Babylonia. They preserve the '
        'Ancient Word whose roots extend through Zoroastrian Persia into '
        'the proto-Indo-Iranian and ancient Near Eastern traditions of the '
        '<i>Bene Qedem</i>.',
        ind,
    ))
    elements.append(Paragraph(
        "This book is an extraction of Layer&nbsp;1 &mdash; the Ancient Word "
        "&mdash; from its Manichaean vessel.",
        pi,
    ))

    # ------------------------------------------------------------------
    # The Architecture
    # ------------------------------------------------------------------
    elements.append(Paragraph("The Architecture", h))
    elements.append(Paragraph(
        "Two numerical patterns articulate the doctrine through every "
        "transformation of vocabulary.",
        p,
    ))

    elements.append(Paragraph("The five-fold rational", lbl))
    elements.append(Paragraph(
        "The five-fold pattern is the rational in its complete articulation "
        "as five discrete degrees &mdash; mind, thought, teaching, counsel, "
        "reflection. The same fivefold structure articulates the rational "
        "that goes forth from the Divine Human (Five Sons of First&nbsp;Man), "
        "the rational that operates upward in regeneration (Five Sons of "
        "Living&nbsp;Spirit), the covenant gestures (Five Mysteries of "
        "First&nbsp;Man), the resurrection-work (Five Awakeners), and the "
        "Lord&rsquo;s complete outgoing (Five Great Greatnesses). It also "
        "organises the proprium against itself: Five Worlds of Darkness, "
        "five forms in archons, Five Worlds of Flesh that bind the soul&rsquo;s "
        "faculties. This single principle is the deepest grammar of the "
        "doctrine.",
        ind,
    ))

    elements.append(Paragraph("The twelve-fold complete circuit", lbl))
    elements.append(Paragraph(
        "The twelve-fold pattern is the complete circuit of states the soul "
        "passes through &mdash; the broadest order of completeness. In its "
        "positive register it is the Lord&rsquo;s outgoing operations "
        "articulated in twelve degrees (Twelve Aeons of Greatness, Twelve "
        "Hours of Day / Twelve Wisdoms, Twelve Judges, Twelve Greatnesses, "
        "Twelve Storehouses); in its negative register it is the proprium "
        "binding the natural mind in twelve fixed conditions (twelve "
        "dignities, twelve zodia bound in the sphere, twelve gates of body, "
        "twelve cities of the Watchers, twelve hours of night). The same "
        "twelvefold completeness articulates the divine summons going forth "
        "and the natural mind organised as if it were its own.",
        ind,
    ))

    elements.append(Paragraph("Bracketing by two substances", lbl))
    elements.append(Paragraph(
        "The corpus is bracketed by foundational teachings on the dualism "
        "between what is given by the Lord and what is claimed by the soul. "
        "T1 is the first opening of sight in Adam; T2 the Two Trees as "
        "five-membered organisms; T103 explicitly restates &ldquo;two "
        "substances from the beginning &mdash; light and darkness, the "
        "beautiful and the bitter, life and death&rdquo; as a coda after "
        "the long journey. The closing T104 names the liturgical Yes and "
        "Amen as the Calling and the Hearing &mdash; the Lord&rsquo;s "
        "summons and the soul&rsquo;s answer carrying the work upward. "
        "The doctrine begins and ends with the same foundation; everything "
        "between is elaboration of how the soul learns to discriminate the "
        "one from the other.",
        ind,
    ))

    elements.append(Paragraph("Light and darkness as gift and claim", lbl))
    elements.append(Paragraph(
        "Throughout the corpus, &ldquo;light&rdquo; and &ldquo;darkness&rdquo; "
        "function not as cosmic stuffs contending in some outer field but "
        "as the two conditions of the same soul. Light is what the Lord "
        "gives, recognised as the Lord&rsquo;s. Darkness is what the soul "
        "has claimed and not yet recognised as not its own. The "
        "&ldquo;mingling&rdquo; that pervades the text is the unregenerate "
        "state where what is given and what is claimed are not yet "
        "distinguished. Regeneration is everywhere the same operation: "
        "the Lord illumines, the soul learns to discriminate, what was "
        "claimed is laid off, what was given is recognised as given.",
        ind,
    ))

    elements.append(Paragraph(
        "The Lord at multiple registers is one Lord", lbl,
    ))
    elements.append(Paragraph(
        "The Lord is recognised at multiple registers &mdash; Father of "
        "Greatness, Mother of Life, First Man, Living Spirit, Beloved of "
        "Lights, Third Ambassador, Jesus the Radiance, Light Mind, Virgin "
        "of Light, King of Honor, Pillar of Glory, Great Builder. These "
        "are not separate divinities. They are the one Lord recognised at "
        "distinct depths of accommodation toward the soul. The whole "
        "apparatus of named principles is the one Lord articulated in the "
        "registers at which the soul can receive him.",
        ind,
    ))

    # ------------------------------------------------------------------
    # The Seven Movements (read against the Song of Solomon)
    # ------------------------------------------------------------------
    elements.append(Paragraph("The Seven Movements", h))
    elements.append(Paragraph(
        f"The corpus unfolds in {n_s}&nbsp;sections, each corresponding "
        "to one state of the regeneration cycle. The section titles are "
        "drawn from the Song of Solomon, which traces the same seven-state "
        "arc independently. The fit is not imposed: the section boundaries "
        "fall at the teaching numbers the corpus itself supplies, and the "
        "content of each section is what that state requires.",
        p,
    ))

    for n in range(1, n_s + 1):
        sec = load_section(n)
        title = (sec.get("title") or "").strip()
        summary = (sec.get("summary") or "").strip()
        # Escape HTML special chars in case any appear; em-dashes pass through.
        safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        safe_summary = summary.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        elements.append(Paragraph(
            f"<b>{n}. {safe_title}.</b> {safe_summary}", ind,
        ))

    # ------------------------------------------------------------------
    # Five lines of evidence (rewritten to match the actual data)
    # ------------------------------------------------------------------
    elements.append(Paragraph("Five Lines of Evidence", h))
    elements.append(Paragraph(
        "Swedenborg made five claims about the Ancient Word. Each can be "
        "set beside what stands in this text.",
        p,
    ))

    elements.append(Paragraph("1. Written entirely in correspondences", lbl))
    elements.append(Paragraph(
        "The teaching core of the <i>Kephalaia</i> is correspondential "
        "throughout. Section&nbsp;6 states the body-cosmos isomorphism "
        "directly &mdash; the cosmos above and below reflects the pattern "
        "of the human body &mdash; and then maps the cosmos onto the human "
        "form, organ by organ, with each correspondence grounded in function. "
        "Elsewhere, five storehouses map to five elements, to five trees, "
        "to five genera, to five worlds. The pattern repeats through realms, "
        "metals, and tastes. The body-cosmos isomorphism culminates in a "
        "soul-body binding formula in Section&nbsp;9. This is not scattered "
        "symbolic language. It is systematic correspondential architecture "
        "sustained across the whole corpus.",
        ind,
    ))

    elements.append(Paragraph("2. Complete from beginning to end", lbl))
    elements.append(Paragraph(
        f"The text contains the complete arc of regeneration. "
        f"Section&nbsp;1 establishes the foundational dualism. "
        f"Sections&nbsp;2 through {n_s - 1} systematically elaborate every "
        "phase: the Lord&rsquo;s coming, the cosmic and temporal architecture, "
        "the Father at his inmost, the Living&nbsp;Spirit&rsquo;s "
        "constructive operations, the body-cosmos correspondence, "
        "providential cycles of influx, naming and forming, compassion and "
        "the marks set on the human, the visible mysteries, the "
        "Apostle&rsquo;s daily working, the soul&rsquo;s journey through "
        f"the natural mind, generation and sight. Section&nbsp;{n_s} closes "
        "with consummation: the foundation restated as coda, the Yes and "
        "the Amen as the Calling and the Hearing. This is not a fragment. "
        "It is a complete text.",
        ind,
    ))

    elements.append(Paragraph(
        "3. Contains the Wars of the Lord and the Book of Jashar", lbl,
    ))
    elements.append(Paragraph(
        "The Hebrew Bible cites two lost texts by name: the &ldquo;Wars of "
        "the LORD&rdquo; (Numbers 21:14) and the &ldquo;Book of Jashar&rdquo; "
        "&mdash; the Book of the Upright (Joshua 10:13, 2&nbsp;Samuel 1:18). "
        "Swedenborg identified both as portions of the Ancient Word. Both "
        "are found here. A consonantal analysis of the Wars of the Lord "
        "shows that the quotation fragments, read at the three degrees "
        "Swedenborg specified (natural, spiritual, celestial), reveal a "
        "cosmic architecture &mdash; the Beloved, the Conflagration, "
        "Cosmic Trenches, the Seat of Watchers, the Border of the Father "
        "&mdash; that matches the macrocosmic narrative in this text "
        "exactly. The Book of Jashar &mdash; the practical manual of the "
        "upright life &mdash; matches the pedagogical content: how "
        "stillness defeats falsity, how the mind is regenerated faculty by "
        "faculty, how the divine call meets human obedience.",
        ind,
    ))

    elements.append(Paragraph(
        "4. Preserved in Great Tartary", lbl,
    ))
    elements.append(Paragraph(
        "In <i>Apocalypse Revealed</i> &sect;11 Swedenborg states that the "
        "Ancient Word is &ldquo;still reserved&hellip; among the people who "
        "are in Great Tartary,&rdquo; that their worship &ldquo;consists "
        "of mere correspondences,&rdquo; and that their books include the "
        "<i>Book of Jashar</i> and the <i>Wars of Jehovah</i>. The "
        "<i>Kephalaia</i> belongs to the Manichaean teaching tradition, "
        "which was officially adopted as state religion by the Uyghur "
        "Khaganate in 762/763&nbsp;CE; the Uyghur Kingdom of Qocho "
        "preserved Manichaean texts in cave temple-libraries at Turfan, "
        "within Great Tartary. The Medinet Madi codex underlying this "
        "edition is a Coptic recension of the same teaching whose Iranian "
        "and Old Turkic recensions survived in that region.",
        ind,
    ))

    elements.append(Paragraph(
        "5. Carried by the Sons of the East", lbl,
    ))
    elements.append(Paragraph(
        "Swedenborg identifies the bearers of the Ancient Word as the "
        "&ldquo;Sons of the East.&rdquo; They &ldquo;were in the science "
        "of correspondences and representations&hellip; therefore in the "
        "Word, by Arabia, Ethiopia, and the sons of the East&hellip; are "
        "meant those who are in the knowledges of heavenly things&rdquo; "
        "(<i>Arcana Coelestia</i> &sect;7226). He places them in Syria as "
        "the &ldquo;last remains of the Ancient Church&rdquo; (<i>AC</i> "
        "&sect;3249) and treats the magi who came to Jesus as inheritors "
        "of this same knowledge: &ldquo;the magicians of that time knew "
        "such things as belong to the spiritual world, which they learned "
        "from the correspondences and representatives of the church&rdquo; "
        "(<i>AC</i> &sect;3791). The <i>Kephalaia</i> stands within that "
        "transmission. It teaches by correspondence; it speaks of the East "
        "as the source of light; its divine register and its spiritual / "
        "natural ontology preserve the figures and the structure to which "
        "Swedenborg points.",
        ind,
    ))

    # ------------------------------------------------------------------
    # The Naming Overlays
    # ------------------------------------------------------------------
    elements.append(Paragraph("The Naming Overlays", h))
    elements.append(Paragraph(
        "No naming overlays have been corrected in the body. "
        "&ldquo;Jesus the Radiance&rdquo; has not been reverted to its "
        "Persian substrate; &ldquo;Light Mind&rdquo; has not been changed "
        "back to <i>Wahman</i>. Instead, the spiritual reading printed at "
        "the foot of each teaching does the translation that matters: it "
        "names what each cosmological figure corresponds to in the doctrine. "
        "The cosmological vocabulary stays where it is, in Coptic and "
        "English, and the reading recognises what wears it.",
        p,
    ))
    elements.append(Paragraph(
        "The names are garments. What wears them is the Ancient Word.",
        pi,
    ))
    elements.append(Paragraph(
        '<b>&ldquo;Jesus the Radiance&rdquo;</b> &mdash; the divine wisdom '
        'that proceeds into illumination, purification, and liberation of '
        'captive good. The substrate designation was almost certainly '
        '<i>Xradeshahr</i> (Glory of the Realm) or a form related to '
        'Avestan <i>xvar&euml;nah</i> (divine luminous glory).',
        ind,
    ))
    elements.append(Paragraph(
        '<b>&ldquo;Light Mind&rdquo; / &ldquo;Light-Nous&rdquo;</b> &mdash; '
        'the Good Mind that enters and awakens. The substrate designation '
        'was almost certainly <i>Wahman</i> &mdash; from Avestan '
        '<i>Vohu Manah</i> (Good Mind), one of the Amesha Spentas in '
        'Zoroastrian theology.',
        ind,
    ))
    elements.append(Paragraph(
        '<b>&ldquo;First Man&rdquo;</b> &mdash; the Divine Human descending '
        'into temptation-combat with falsity. <b>&ldquo;Living Spirit&rdquo;</b> '
        '&mdash; Divine Truth proceeding to order all things and to build '
        'spiritual structure within the natural mind. <b>&ldquo;Third '
        'Ambassador&rdquo;</b> &mdash; the manifestation of the Divine form '
        'that draws forth captive good. <b>&ldquo;Father of Greatness&rdquo;</b> '
        '&mdash; the Infinite Divine Love in which all things originate.',
        ind,
    ))
    elements.append(Paragraph(
        '<b>&ldquo;Cross of Light&rdquo;</b> &mdash; not a crucifixion '
        'metaphor but the substrate concept of divine light scattered and '
        'bound within matter; the Lord present in ultimates. '
        '<b>&ldquo;Matter&rdquo; / &ldquo;Hyle&rdquo;</b> &mdash; the '
        'proprium personified, &ldquo;the thought of death&rdquo;: not '
        'physical substance but the soul&rsquo;s claiming of what flows '
        'through it as its own.',
        ind,
    ))

    # ------------------------------------------------------------------
    # Deeper Transmission Evidence
    # ------------------------------------------------------------------
    elements.append(Paragraph("Deeper Transmission Evidence", h))
    elements.append(Paragraph(
        "Beyond the Manichaean overlay, material is preserved here that "
        "predates even the Persian-Zoroastrian vessel:",
        p,
    ))
    elements.append(Paragraph(
        "The five dark elements (smoke, fire, wind, water, darkness) do "
        "not match either classical Greek (four elements) or standard "
        "Zoroastrian categories. This sequence appears to preserve a "
        "<b>proto-Indo-Iranian or Mesopotamian elemental cosmology</b> "
        "older than the Persian formulation.",
        ind,
    ))
    elements.append(Paragraph(
        "The &ldquo;sea giant&rdquo; passage &mdash; a composite being "
        "formed from cosmic debris in a primordial sea, bearing the "
        "imprint of all celestial cycles upon its body &mdash; has "
        "parallels to Mesopotamian creation narratives and "
        "<b>Zurvanite cosmogony</b>, and may represent one of the oldest "
        "layers in the text.",
        ind,
    ))
    elements.append(Paragraph(
        "The water-reflection / inversion teaching &mdash; the upper "
        "world reflected inversely in the lower &mdash; appears across "
        "ancient Near Eastern and Vedic / Upanishadic traditions and "
        "expresses a law of correspondence more fundamental than any "
        "single cultural formulation.",
        ind,
    ))

    # ------------------------------------------------------------------
    # How This Edition Was Built
    # ------------------------------------------------------------------
    elements.append(Paragraph("How This Edition Was Built", h))
    elements.append(Paragraph(
        f"The corpus was processed through a multi-stage pipeline using "
        f"Claude Opus as the analytical instrument. Early stages translated "
        f"the Coptic body line by line, identified Layer&nbsp;3 (the "
        f"hagiographic frame) and Layer&nbsp;2 (the Manichaean theological "
        f"overlay), and stripped them, leaving the Layer&nbsp;1 substrate. "
        f"That substrate was then atomised into {n_t}&nbsp;teachings &mdash; "
        f"spiritually coherent units bounded where the doctrine&rsquo;s "
        f"subject changes &mdash; and a working lexicon of "
        f"{n_lex}&nbsp;entries was derived from the surviving teachings. "
        f"For each teaching, a correspondential reading was produced: "
        f"what the cosmological language refers to in the science of "
        f"correspondences. Lacunae in the Coptic core were then restored "
        f"under the constraint of surrounding context, the lexicon, and "
        f"the spiritual reading. Finally the corpus was composed into "
        f"{n_ch}&nbsp;chapters within {n_s}&nbsp;sections, grouped by "
        f"spiritual subject rather than by surface cosmological narrative.",
        p,
    ))
    elements.append(Paragraph(
        "The Coptic papyrus is damaged. Where gaps remained, those that "
        "could be constrained by surrounding context were restored; those "
        "too uncertain were left open. Two bracket conventions distinguish "
        "the provenance of every fill. <b>Square brackets</b> mark "
        "editor restorations preserved from the apparatus of the "
        "German critical editions &mdash; readings the original editors "
        "already proposed for visible damage. <b>Half-brackets</b> "
        "(&#x2308;&hellip;&#x2309;, the Assyriological convention) mark "
        "pipeline restorations of true lacunae &mdash; gaps for which no "
        "editor reading existed and which stage&nbsp;6 of the pipeline "
        "filled under the joint constraint of surrounding context, the "
        "working lexicon, and the spiritual reading. In both cases the "
        "brackets and any length cues are shown in <font color=\"" + LACUNA_GRAY + "\">"
        "light gray</font>, while the proposed letters remain in black so "
        "that the reader can see, at a glance, where the manuscript is "
        "intact, where the editors restored, where the pipeline restored, "
        "and where the surrounding doctrine has been left to mark its "
        "silences with empty brackets.",
        p,
    ))

    # ------------------------------------------------------------------
    # How to Read This Text
    # ------------------------------------------------------------------
    elements.append(Paragraph("How to Read This Text", h))
    elements.append(Paragraph(
        "Each teaching opens with a short subtitle naming its spiritual "
        "subject. Read the parallel text first &mdash; the English column "
        "gives you the translation; the Coptic column lets you see, where "
        "you can read even a little, how the doctrine is sitting in its "
        "own body. Then read the spiritual reading at the foot of the "
        "teaching: a tinted callout that names what the cosmological "
        "vocabulary is doing in the doctrine, registers the figures it "
        "actually treats, and connects the teaching to the corpus arc.",
        p,
    ))
    elements.append(Paragraph(
        "Where you see <font color=\"" + LACUNA_GRAY + "\">light gray "
        "brackets</font>, the manuscript is damaged or the wording has "
        "been supplied. Square brackets carry editor restorations from the "
        "critical-edition apparatus; half-brackets (&#x2308;&hellip;&#x2309;) "
        "carry pipeline restorations of true lacunae. Where the brackets "
        "contain only dots, the gap could not be safely filled. Where they "
        "contain letters in black, those letters have been chosen so that "
        "the surrounding doctrine can stand. They are not certain. They "
        "are coherent.",
        p,
    ))
    elements.append(Paragraph(
        "Through every transmission &mdash; through Persian rephrasing, "
        "Manichaean renaming, Coptic recopying, lacunae and restorations "
        "and translation &mdash; the teaching itself survived. The five-fold "
        "rational did not change. The body-cosmos correspondence did not "
        "change. The doctrine that reality proceeds through discrete "
        "degrees &mdash; celestial, spiritual, natural &mdash; did not "
        "change. The mechanism of divine influx and human reception "
        "(&ldquo;the summons and the obedience&rdquo;) did not change.",
        p,
    ))
    elements.append(Paragraph(
        "The names changed. The teaching did not.",
        pi,
    ))
    elements.append(Paragraph(
        "The correspondences are in the text. They have always been in "
        "the text. The Manichaean names are garments. What wears them "
        "is the Ancient Word.",
        pi,
    ))
    elements.append(PageBreak())
    return elements

# ---------------------------------------------------------------------------
# Table of contents
# ---------------------------------------------------------------------------

def _toc_pages(st: dict, book: dict, chapters: list[dict]) -> list:
    elements: list = [
        Spacer(1, 15 * mm),
        Paragraph("CONTENTS", st["section_title"]),
        Spacer(1, 6 * mm),
    ]
    indent = 8 * mm

    for sn in book["section_reading_order"]:
        s = load_section(sn)
        sect_key = f"sect_{sn}"
        sect_page = _page_registry.get(sect_key, "")
        sect_title = f"Section {sn} \u2014 {s['title']}"

        elements.append(Spacer(1, 10))
        elements.append(_TocLine(
            sect_title, sect_page,
            title_font=FONT_BOLD, font_size=11, leading=16,
        ))

        # Chapters belonging to this section, in position order
        ch_in_sect = [c for c in chapters if c["section_number"] == sn]
        ch_in_sect.sort(key=lambda c: c["position_in_section"])
        for ch in ch_in_sect:
            ch_key = f"ch_{ch['chapter_number']}"
            ch_page = _page_registry.get(ch_key, "")
            label = f'Ch. {ch["chapter_number"]}. {ch["title"]}'
            elements.append(_TocLine(
                label, ch_page,
                title_font=FONT_ROMAN, font_size=10, leading=14,
                indent=indent,
            ))

    # Back matter
    for key, label in (
        ("lexicon", "Spiritual Lexicon"),
        ("observations", "Architectural Observations"),
    ):
        page = _page_registry.get(key, "")
        if page:
            elements.append(Spacer(1, 10))
            elements.append(_TocLine(
                label, page,
                title_font=FONT_BOLD, font_size=11, leading=16,
            ))

    elements.append(PageBreak())
    return elements


# ---------------------------------------------------------------------------
# Section divider page
# ---------------------------------------------------------------------------

def _section_page(st: dict, s: dict) -> list:
    out: list = [
        _PageRecorder(f"sect_{s['section_number']}"),
        Spacer(1, 50 * mm),
        Paragraph(f'Section {s["section_number"]}', st["sect_label"]),
        Spacer(1, 4 * mm),
        Paragraph(_xml_esc(s["title"]), st["sect_title"]),
        Spacer(1, 10 * mm),
    ]
    if s.get("summary"):
        out.append(Paragraph(_xml_esc(s["summary"]), st["sect_summary"]))
    if s.get("organizing_principle"):
        out.append(Paragraph(
            _xml_esc(s["organizing_principle"]),
            st["sect_principle"],
        ))
    out.append(PageBreak())
    return out


# ---------------------------------------------------------------------------
# Chapter rendering: header → per-teaching (reading + 2-col body)
# ---------------------------------------------------------------------------


def _group_segments_into_paragraphs(
    segments: list[dict],
) -> list[list[dict]]:
    """Group segments into paragraphs using the explicit `break_after`
    flag set by stage 1 (the translator) on `leer` markers — the
    scribal section breaks visible in the manuscript.

    The pipeline is the source of truth. A new paragraph starts only
    when the previous segment carries `break_after = true`. Chapter
    and teaching boundaries are handled upstream by per-chapter /
    per-teaching rendering, so this function only honors `break_after`.

    No chunking, no caps, no contiguity heuristics. The table renderer
    is configured with `splitInRow=1` so a tall paragraph splits
    inside its row across pages naturally.
    """
    if not segments:
        return []
    paragraphs: list[list[dict]] = []
    current: list[dict] = [segments[0]]
    for seg in segments[1:]:
        if current[-1].get("break_after"):
            paragraphs.append(current)
            current = [seg]
        else:
            current.append(seg)
    if current:
        paragraphs.append(current)
    return paragraphs


def _paragraph_row(
    paragraph_segs: list[dict],
    restorations: dict[int, dict],
    st: dict,
    notes: list[dict] | None = None,
    note_registry: dict[int, int] | None = None,
    renditions: dict[tuple, str] | None = None,
    english_segments: dict[tuple, str] | None = None,
    english_restorations: dict[int, dict] | None = None,
    english_fills_by_cop_gap: dict[int, dict] | None = None,
) -> list:
    """Build a single 2-column row holding one paragraph of text."""
    cop_parts: list[str] = []
    eng_parts: list[str] = []
    for seg in paragraph_segs:
        cop_raw, eng_raw = _segment_pair(
            seg, restorations, notes, note_registry, renditions,
            english_segments=english_segments,
            english_restorations=english_restorations,
            english_fills_by_cop_gap=english_fills_by_cop_gap,
        )
        if cop_raw:
            cop_parts.append(cop_raw)
        if eng_raw:
            eng_parts.append(eng_raw)

    def _join_with_hyphen_splice(parts: list[str]) -> str:
        """Join segment fragments with spaces, but splice mid-word
        hyphens introduced by the editor at manuscript line breaks.

        Three patterns are handled:
          ['glori-',  'fied.']   →  'glorified.'         (trailing only)
          ['Li-',     '-fe.']    →  'Life.'              (trailing + leading)
          ['Li',      '-fe.']    →  'Life.'              (leading only)

        Editor practice in the source is inconsistent: sometimes only
        the line-end carries the hyphen, sometimes only the line-start,
        sometimes both. All three produce a single mid-word break that
        should be silently spliced.

        A hyphen is treated as a continuation only when adjacent to
        a lowercase letter or Coptic letter on the joining side.
        Other hyphens (between digits, capitals, brackets, punctuation)
        are preserved.
        """
        if not parts:
            return ""

        def _is_continuation_char(ch: str) -> bool:
            if not ch:
                return False
            return ch.islower() or bool(_COPTIC_RUN_RE.match(ch))

        out = [parts[0]]
        for nxt in parts[1:]:
            prev = out[-1]
            prev_strip = prev.rstrip()
            nxt_strip = nxt.lstrip()

            prev_hyphen = prev_strip.endswith("-")
            nxt_hyphen = nxt_strip.startswith("-")

            # Inner edges after stripping any joining hyphens.
            prev_inner = prev_strip[:-1] if prev_hyphen else prev_strip
            nxt_inner = nxt_strip[1:] if nxt_hyphen else nxt_strip

            # Continuation if either side carries a hyphen AND the
            # other-side first inner char is a continuation char.
            if (prev_hyphen or nxt_hyphen) and (
                (prev_hyphen and _is_continuation_char(nxt_inner[:1]))
                or (nxt_hyphen and _is_continuation_char(prev_inner[-1:]))
            ):
                out[-1] = prev_inner + nxt_inner
            else:
                out.append(nxt)
        return " ".join(out).strip()

    cop_text = _join_with_hyphen_splice(cop_parts)
    eng_text = _join_with_hyphen_splice(eng_parts)
    if not cop_text and not eng_text:
        return []

    cop_styled = _style_lacunae(_normalize_terminal(cop_text, side="coptic"), side="coptic") if cop_text else ""
    eng_styled = _style_lacunae(_normalize_terminal(eng_text, side="english"), side="english") if eng_text else ""
    # English body sometimes contains inline Coptic letters (e.g. inside
    # editor parentheticals — "(letter restored in ϸϸϸϸ 'milk')"). Wrap
    # any Coptic-script runs in the Coptic font so they don't render as
    # missing-glyph boxes against the surrounding Latin font.
    if eng_styled:
        eng_styled = _wrap_coptic_runs(eng_styled)

    cop_para = Paragraph(cop_styled or "&nbsp;", st["coptic_cell"])
    eng_para = Paragraph(eng_styled or "&nbsp;", st["english_cell"])

    t = Table(
        [[cop_para, eng_para]],
        colWidths=[COL_WIDTH, COL_WIDTH],
        splitByRow=1,
        splitInRow=1,
    )
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, 0), COL_GUTTER / 2),
        ("LEFTPADDING", (1, 0), (1, 0), COL_GUTTER / 2),
        ("RIGHTPADDING", (1, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return [t]


def _reading_info_block(
    reading: dict,
    st: dict,
) -> list:
    """Render the spiritual reading as a compact callout block.

    A multi-row Table with a soft tinted background and a left rule.
    Each paragraph is its own row so the block can split across pages.
    Smaller font than the body so it visually reads as an annotation,
    not as primary text.
    """
    body_text = reading.get("reading") or ""
    if not body_text.strip():
        return []

    rows: list[list] = [[Paragraph("SPIRITUAL READING", st["reading_label"])]]
    for para in body_text.split("\n\n"):
        para = para.strip()
        if para:
            rows.append([Paragraph(_xml_esc(para), st["reading_body"])])

    box_w = TEXT_WIDTH
    t = Table(rows, colWidths=[box_w], repeatRows=0)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#F6F4EE")),
        ("LINEBEFORE", (0, 0), (0, -1), 1.4, HexColor("#B0A990")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6 * mm),
        # First row top padding, last row bottom padding only
        ("TOPPADDING", (0, 0), (-1, 0), 4 * mm),
        ("TOPPADDING", (0, 1), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -2), 1.5 * mm),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 4 * mm),
    ]))
    t.splitByRow = 1
    return [Spacer(1, 4 * mm), t]


def _teaching_block(
    st: dict,
    teaching_n: int,
    notes: list[dict] | None = None,
    note_registry: dict[int, int] | None = None,
) -> list:
    """Render one teaching: anchor + arc + flowing 2-col body + reading info-block."""
    teaching = load_teaching(teaching_n)
    reading = load_reading(teaching_n)
    restoration = load_restoration(teaching_n)
    restorations = _restorations_by_id(restoration)
    renditions = _renditions_by_segment(restoration)
    english_segments = _english_segments_by_key(restoration)
    english_restorations = _english_restorations_by_id(restoration)
    english_fills_by_cop_gap = _english_fills_by_coptic_gap(restoration)

    out: list = []

    # --- Anchor: "Teaching N" ---
    out.append(Paragraph(
        f"Teaching {teaching_n}",
        st["teaching_anchor"],
    ))

    # --- Arc: short subtitle. Prefer the reading title (it captures the
    #     spiritual subject of the teaching), fall back to teaching title. ---
    arc = (reading or {}).get("title") or teaching.get("title") or ""
    if arc:
        out.append(Paragraph(_xml_esc(arc), st["teaching_subtitle"]))

    # --- Body: flowing 2-col paragraphs (notes accumulator threaded in) ---
    paragraphs = _group_segments_into_paragraphs(teaching.get("segments", []))
    for para_segs in paragraphs:
        out.extend(_paragraph_row(
            para_segs, restorations, st, notes, note_registry, renditions,
            english_segments=english_segments,
            english_restorations=english_restorations,
            english_fills_by_cop_gap=english_fills_by_cop_gap,
        ))

    # --- Spiritual reading info-block at the foot of the teaching ---
    if reading and reading.get("reading"):
        out.extend(_reading_info_block(reading, st))

    out.append(Spacer(1, 6 * mm))
    return out


def _format_apparatus_entry(note: dict) -> str:
    """Format a single footnote entry as XML-escaped Paragraph text.

    Layout: "<sup>N</sup> [line L] kind details"
    Coptic and English fragments are quoted in their own scripts.
    """
    parts: list[str] = []
    parts.append(f'<font color="{LACUNA_GRAY}"><super>{note["n"]}</super></font>')
    line = note.get("line")
    if line is not None:
        parts.append(f'<font color="{MUTED}">l.&nbsp;{line}</font>')

    kind = note.get("kind")
    if kind == "pipeline_restoration":
        cop = note.get("coptic", "")
        eng = note.get("english", "")
        conf = note.get("confidence") or "?"
        body_segs: list[str] = []
        if cop:
            piece = f'<font name="Coptic">\u2308{_xml_esc(cop)}\u2309</font>'
            if eng:
                piece += f' &mdash; &ldquo;{_xml_esc(eng)}&rdquo;'
            body_segs.append(piece)
        elif eng:
            body_segs.append(f'&ldquo;{_xml_esc(eng)}&rdquo;')
        body_segs.append(f'<i>pipeline restoration, confidence: {_xml_esc(conf)}</i>')
        basis = note.get("basis")
        if basis:
            # Editor's commentary may contain inline Coptic letters that
            # would render as tofu boxes in the surrounding Latin paragraph;
            # wrap any Coptic-script runs in the Coptic font.
            body_segs.append(_wrap_coptic_runs(_xml_esc(str(basis))))
        parts.append("; ".join(body_segs))
    elif kind == "editor_restoration":
        cop = note.get("coptic", "")
        eng = note.get("english", "")
        body_segs = []
        if cop:
            piece = f'<font name="Coptic">[{_xml_esc(cop)}]</font>'
            if eng:
                piece += f' &mdash; &ldquo;{_xml_esc(eng)}&rdquo;'
            body_segs.append(piece)
        elif eng:
            body_segs.append(f'&ldquo;{_xml_esc(eng)}&rdquo;')
        body_segs.append("<i>editor</i>")
        basis = note.get("basis")
        if basis:
            body_segs.append(_wrap_coptic_runs(_xml_esc(str(basis))))
        parts.append("; ".join(body_segs))
    elif kind == "lacuna_trace":
        partial = note.get("partial", "")
        is_trace = note.get("is_trace", False)
        if is_trace:
            parts.append(
                f'trace: <font name="Coptic">{_xml_esc(partial)}</font>'
            )
        else:
            # Editor prose (may contain inline Coptic runs).
            parts.append(_wrap_coptic_runs(_xml_esc(str(partial))))
    return " ".join(parts)


def _render_apparatus(notes: list[dict], st: dict) -> list:
    """Render the chapter-end apparatus block from accumulated footnotes."""
    if not notes:
        return []
    out: list = [
        Spacer(1, 4 * mm),
        HRFlowable(
            width="40%", thickness=0.4,
            color=HexColor(RULE_COLOR),
            spaceAfter=2 * mm, spaceBefore=0,
        ),
        Paragraph("APPARATUS", st["apparatus_label"]),
        Spacer(1, 1.5 * mm),
    ]
    for note in notes:
        out.append(Paragraph(_format_apparatus_entry(note), st["apparatus_entry"]))
    return out


def _render_chapter(st: dict, ch: dict) -> list:
    out: list = [
        _PageRecorder(f"ch_{ch['chapter_number']}"),
        Paragraph(_xml_esc(ch["title"]), st["chapter_title"]),
    ]
    if ch.get("role"):
        role = ch["role"].replace("_", " ").title()
        out.append(Paragraph(role, st["chapter_role"]))
    if ch.get("description"):
        out.append(Paragraph(_xml_esc(ch["description"]), st["chapter_desc"]))

    out.append(HRFlowable(
        width="50%", thickness=0.5,
        color=HexColor(RULE_COLOR),
        spaceAfter=6 * mm, spaceBefore=2 * mm,
    ))

    # Per-chapter apparatus accumulator. Footnote numbers reset per chapter.
    notes: list[dict] = []
    note_registry: dict[int, int] = {}

    for tn in ch.get("teaching_numbers", []):
        out.extend(_teaching_block(st, tn, notes, note_registry))

    # Chapter-end apparatus block (Leiden footnotes).
    out.extend(_render_apparatus(notes, st))

    out.append(PageBreak())
    return out


# ---------------------------------------------------------------------------
# Lexicon
# ---------------------------------------------------------------------------

_CATEGORY_LABELS = {
    "cosmological_entity": "Cosmological Entities",
    "cosmic_element": "Cosmic Elements & Substances",
    "structural_term": "Structural Terms",
    "body_anatomy": "Body & Anatomy",
    "natural_imagery": "Natural Imagery",
    "action_process": "Actions & Processes",
    "quality_state": "Qualities & States",
    "faculty": "Faculties of the Mind",
    "number": "Numerical Correspondences",
}

_CATEGORY_ORDER = [
    "cosmological_entity",
    "cosmic_element",
    "structural_term",
    "body_anatomy",
    "faculty",
    "natural_imagery",
    "action_process",
    "quality_state",
    "number",
]


def _render_lexicon(st: dict, lexicon: dict) -> list:
    out: list = [
        _PageRecorder("lexicon"),
        Spacer(1, 25 * mm),
        Paragraph("SPIRITUAL LEXICON", st["section_title"]),
        Spacer(1, 4 * mm),
        Paragraph(
            "A working lexicon derived from the surviving teachings. Each "
            "entry maps a Manichaean cosmological term to what it "
            "corresponds to in the doctrine. Coptic forms are given where "
            "attested. Where the same term carries an opposite sense, that "
            "is noted.",
            ParagraphStyle(
                "LI", fontName=FONT_ITALIC, fontSize=10,
                alignment=TA_CENTER, leading=14, spaceAfter=14,
                textColor=HexColor(NOTE_COLOR),
            ),
        ),
    ]

    entries = lexicon.get("entries", [])
    by_cat: dict[str, list] = {}
    for e in entries:
        by_cat.setdefault(e.get("category", "other"), []).append(e)

    for cat_key in _CATEGORY_ORDER:
        group = by_cat.get(cat_key, [])
        if not group:
            continue
        label = _CATEGORY_LABELS.get(cat_key, cat_key.replace("_", " ").title())
        out.append(Paragraph(
            _xml_esc(f"{label} ({len(group)})"),
            st["lex_category"],
        ))
        out.append(HRFlowable(
            width="100%", thickness=0.4,
            color=HexColor(RULE_COLOR), spaceAfter=4 * mm,
        ))

        for e in group:
            term = _xml_esc(e.get("english_term", ""))
            spi = _xml_esc(e.get("spiritual_meaning", ""))
            head = f'<b>{term}</b> \u2014 <i>{spi}</i>'
            variants = e.get("natural_variants") or []
            if variants:
                vlist = ", ".join(_xml_esc(v) for v in variants)
                head += f'  <font color="{MUTED}" size="8">({vlist})</font>'
            out.append(Paragraph(head, st["lex_entry_head"]))

            coptic_forms = e.get("coptic_forms") or []
            if coptic_forms:
                out.append(Paragraph(
                    " &nbsp;\u00b7&nbsp; ".join(_xml_esc(c) for c in coptic_forms),
                    st["lex_coptic"],
                ))

            defn = e.get("definition", "")
            if defn:
                out.append(Paragraph(_xml_esc(defn), st["lex_entry_body"]))
            opp = e.get("opposite_sense", "")
            if opp:
                out.append(Paragraph(
                    f'Opposite sense: {_xml_esc(opp)}',
                    st["lex_entry_detail"],
                ))
            use = e.get("use_in_reading", "")
            if use:
                out.append(Paragraph(
                    f'<i>In reading:</i> {_xml_esc(use)}',
                    st["lex_entry_detail"],
                ))

    out.append(PageBreak())
    return out


# ---------------------------------------------------------------------------
# Architectural observations
# ---------------------------------------------------------------------------

def _render_observations(st: dict, book: dict) -> list:
    obs = book.get("observations") or []
    if not obs:
        return []
    out: list = [
        _PageRecorder("observations"),
        Spacer(1, 25 * mm),
        Paragraph("ARCHITECTURAL OBSERVATIONS", st["section_title"]),
        Spacer(1, 4 * mm),
        Paragraph(
            "Structural patterns observed in the corpus across all "
            f'{book["total_teachings"]} teachings.',
            ParagraphStyle(
                "OI", fontName=FONT_ITALIC, fontSize=10,
                alignment=TA_CENTER, leading=14, spaceAfter=14,
                textColor=HexColor(NOTE_COLOR),
            ),
        ),
    ]
    if book.get("structural_overview"):
        out.append(Paragraph("Structural Overview", st["obs_title"]))
        out.append(Paragraph(
            _xml_esc(book["structural_overview"]),
            st["obs_body"],
        ))
    if book.get("reading_order_note"):
        out.append(Paragraph("Reading Order", st["obs_title"]))
        out.append(Paragraph(
            _xml_esc(book["reading_order_note"]),
            st["obs_body"],
        ))

    for o in obs:
        title = o.get("title", "")
        if title:
            out.append(Paragraph(_xml_esc(title), st["obs_title"]))
        content = o.get("content", "")
        if content:
            out.append(Paragraph(_xml_esc(content), st["obs_body"]))
        tn = o.get("teaching_numbers") or []
        if tn:
            preview = ", ".join(f"T{n}" for n in tn[:24])
            if len(tn) > 24:
                preview += f", and {len(tn) - 24} more"
            out.append(Paragraph(
                f"Teachings: {preview}",
                st["obs_meta"],
            ))

    out.append(PageBreak())
    return out


# ---------------------------------------------------------------------------
# Document build
# ---------------------------------------------------------------------------

def _build_story(book: dict, chapters: list[dict], lexicon: dict | None,
                 st: dict) -> list:
    story: list = []
    story.extend(_title_page(st, book))
    story.extend(_preface_pages(st, book))
    story.extend(_toc_pages(st, book, chapters))

    # Sections in reading order
    for sn in book["section_reading_order"]:
        s = load_section(sn)
        story.extend(_section_page(st, s))
        # Chapters in position order
        ch_in_sect = [c for c in chapters if c["section_number"] == sn]
        ch_in_sect.sort(key=lambda c: c["position_in_section"])
        for ch in ch_in_sect:
            story.extend(_render_chapter(st, ch))

    if lexicon:
        story.extend(_render_lexicon(st, lexicon))
    story.extend(_render_observations(st, book))
    return story


def _make_doc(path: Path) -> SimpleDocTemplate:
    return SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=LEFT_MARGIN,
        rightMargin=RIGHT_MARGIN,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title="The Ancient Word in the Coptic Kephalaia",
        author="Kephalaia v2 pipeline",
    )


def main() -> int:
    book = load_book()
    chapters = all_chapters_in_order()
    lexicon = load_lexicon()
    st = _styles()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    print(
        f"[v2] Building PDF: {book['total_sections']} sections, "
        f"{book['total_chapters']} chapters, "
        f"{book['total_teachings']} teachings"
    )

    # --- Pass 1: build to TMP, populate _page_registry ---
    print("[v2] Pass 1: recording page numbers...")
    doc1 = _make_doc(OUTPUT_TMP)
    story1 = _build_story(book, chapters, lexicon, st)
    doc1.build(
        story1,
        onFirstPage=_page_footer,
        onLaterPages=_page_footer,
    )

    # --- Pass 2: rebuild final document with TOC entries populated ---
    print("[v2] Pass 2: building final document with TOC...")
    doc2 = _make_doc(OUTPUT)
    story2 = _build_story(book, chapters, lexicon, st)
    doc2.build(
        story2,
        onFirstPage=_page_footer,
        onLaterPages=_page_footer,
    )

    # Clean up tmp
    try:
        OUTPUT_TMP.unlink()
    except FileNotFoundError:
        pass

    size_mb = OUTPUT.stat().st_size / (1024 * 1024)
    print(f"[v2] OK -> {OUTPUT} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
