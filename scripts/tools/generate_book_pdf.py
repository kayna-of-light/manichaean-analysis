#!/usr/bin/env python3
"""
Generate a structured book PDF: The Ancient Word.

Extracts the correspondential substrate (the Ancient Word) from
the Kephalaia of the Teacher, organized by its own internal
structure rather than manuscript chapter divisions.

The structure was discovered by Claude Opus 4.6 reading the entire
corpus as a continuous flow of §-numbered paragraphs — without
access to manuscript chapter divisions.  Each structural chapter
defines a §-range; only paragraphs within that range appear.

All titles come from book_structure.json.  No manuscript titles
are used.

Dependencies: reportlab  (available in conda env 'manichaean')

Usage:
    conda run -n manichaean python scripts/tools/generate_book_pdf.py
"""

import json
import re
import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, HRFlowable,
    Flowable,
)
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ---------------------------------------------------------------------------
# Font registration — use TTF Times New Roman for full Unicode support
# (Greek, macrons, schwa, etc.)
# ---------------------------------------------------------------------------

_FONT_DIR = Path(r"C:\Windows\Fonts")
pdfmetrics.registerFont(TTFont("TNR", str(_FONT_DIR / "times.ttf")))
pdfmetrics.registerFont(TTFont("TNR-Bold", str(_FONT_DIR / "timesbd.ttf")))
pdfmetrics.registerFont(TTFont("TNR-Italic", str(_FONT_DIR / "timesi.ttf")))
pdfmetrics.registerFont(TTFont("TNR-BoldItalic", str(_FONT_DIR / "timesbi.ttf")))

from reportlab.pdfbase.pdfmetrics import registerFontFamily
registerFontFamily(
    "TNR",
    normal="TNR",
    bold="TNR-Bold",
    italic="TNR-Italic",
    boldItalic="TNR-BoldItalic",
)

# Shorthand constants for font names
FONT_ROMAN = "TNR"
FONT_BOLD = "TNR-Bold"
FONT_ITALIC = "TNR-Italic"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # scripts/tools/ → project root

KEPH_DIR = PROJECT_ROOT / "output" / "projects" / "kephalaia"
STRUCTURE_FILE = KEPH_DIR / "book_structure.json"
LEXICON_FILE = KEPH_DIR / "correspondence_lexicon.json"
CORE_DIR = KEPH_DIR / "core" / "chapters"
RESTORED_DIR = KEPH_DIR / "restored" / "chapters"
OUTPUT = PROJECT_ROOT / "output" / "pdfs" / "The_Ancient_Word.pdf"
OUTPUT_TMP = PROJECT_ROOT / "output" / "pdfs" / "The_Ancient_Word_tmp.pdf"

PAGE_W, PAGE_H = A4

LACUNA_GRAY = "#999999"
RULE_COLOR = "#CCCCCC"
NOTE_COLOR = "#555555"
MUTED = "#888888"
DARK_MUTED = "#666666"
TOC_DOT_COLOR = "#BBBBBB"
TOC_PAGE_COLOR = "#888888"
FOOTER_RULE_COLOR = "#CCCCCC"

# Global page-number registry used by the two-pass build
_page_registry: dict[str, int] = {}


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
    """Single TOC line: title, extending dot leader, right-aligned page number."""

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
        y = self._leading - self.font_size  # baseline offset

        # --- Title (left) ---
        c.setFont(self.title_font, self.font_size)
        c.setFillColor(HexColor("#000000"))
        c.drawString(self.indent, y, self.title)
        title_w = pdfmetrics.stringWidth(
            self.title, self.title_font, self.font_size
        )

        if not self.page_num:
            return

        # --- Page number (right, always roman / non-bold) ---
        c.setFont(FONT_ROMAN, self.font_size)
        c.setFillColor(HexColor(self.page_color))
        c.drawRightString(self._avail_w, y, self.page_num)
        page_w = pdfmetrics.stringWidth(
            self.page_num, FONT_ROMAN, self.font_size
        )

        # --- Dot leaders (filling the gap) ---
        dot = " \u00b7"  # space + middle dot
        dot_w = pdfmetrics.stringWidth(dot, FONT_ROMAN, self.font_size)
        x_start = self.indent + title_w + 2
        x_end = self._avail_w - page_w - 2

        if x_end - x_start > dot_w * 2:  # only draw if room for ≥2 dots
            c.setFont(FONT_ROMAN, self.font_size)
            c.setFillColor(HexColor(self.dot_color))
            # Draw right-to-left so dots always align at the page-number edge
            x = x_end - dot_w
            while x >= x_start:
                c.drawString(x, y, dot)
                x -= dot_w


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _xml_esc(text: str) -> str:
    """Escape XML entities for reportlab Paragraph markup."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _clean_gap_markers(text: str) -> str:
    """Normalize [GAP-N] and [GAP-N: text] markers for display.

    - [GAP-N]           → [...]
    - [GAP-N: text]     → [text]
    - [GAP-N: REVIEW …] → [...]  (review flags become plain lacunae)
    """
    text = re.sub(r"\[GAP-\d+:\s*REVIEW\s*[—–-].*?\]", "[...]", text)
    text = re.sub(r"\[GAP-\d+:\s*(.+?)\]", r"[\1]", text)
    text = re.sub(r"\[GAP-\d+\]", "[...]", text)
    return text


# ---------------------------------------------------------------------------
# Global §-indexed paragraph store
# ---------------------------------------------------------------------------


def build_paragraph_lookup() -> dict[int, str]:
    """Build a global mapping from sequential §N → paragraph text.

    This reproduces exactly the same numbering that
    format_corpus_interleaved() uses, so the §-ranges in
    book_structure.json select the right paragraphs.
    """
    lookup: dict[int, str] = {}
    seq = 0

    core_files = sorted(CORE_DIR.glob("ch_*.json"))
    for core_path in core_files:
        with open(core_path, encoding="utf-8") as f:
            core_data = json.load(f)

        ch_num = core_data["chapter_number"]

        # Build reconstruction map from restored layer
        recon_map: dict[int, str] = {}
        restored_path = RESTORED_DIR / f"ch_{ch_num:03d}.json"
        if restored_path.exists():
            with open(restored_path, encoding="utf-8") as f:
                restored_data = json.load(f)
            for rec in restored_data.get("reconstructions", []):
                pnum = rec.get("paragraph")
                rtext = rec.get("reconstructed_text", "")
                if pnum is not None and rtext:
                    recon_map[pnum] = rtext

        for para in core_data.get("paragraphs", []):
            raw_text = para.get("core_text", "")
            if not raw_text:
                continue
            pnum = para["paragraph_number"]
            # Prefer reconstructed (gap-filled) text
            text = recon_map.get(pnum, raw_text)
            seq += 1
            lookup[seq] = text

    return lookup


def _style_lacunae(text: str) -> str:
    """XML-escape text and render [...] brackets in gray."""
    text = _xml_esc(text)

    def _gray_bracket(m: re.Match) -> str:
        inner = m.group(0)[1:-1]

        def _black_if_visible(m2: re.Match) -> str:
            seg = m2.group(0)
            if seg.strip():
                return f'<font color="#000000">{seg}</font>'
            return seg

        styled = re.sub(r"[^.]+", _black_if_visible, inner)
        return f'<font color="{LACUNA_GRAY}">[{styled}]</font>'

    return re.sub(r"\[[^\]]*\]", _gray_bracket, text)


def _clean_core_text(text: str) -> str:
    """Strip manuscript page markers and leading paragraph numbers."""
    # Remove ⟨p.N⟩ prefix (and whitespace/newline after)
    text = re.sub(r"⟨p\.\d+⟩\s*", "", text)
    # Remove leading (N) at start of text
    text = re.sub(r"^\(\d+\)\s*", "", text)
    # Collapse multiple newlines to single space
    text = re.sub(r"\n+", " ", text)
    return text.strip()


# --- Sentence starters: words that reliably signal a new sentence --------
# Conservative list — only words that almost never appear mid-sentence
# after a lowercase word without preceding punctuation.
_SENTENCE_STARTERS = frozenset({
    "The", "This", "That", "These", "Those",
    "It", "He", "She", "They", "We", "I",
    "And", "But", "For", "So", "Yet", "Or", "Nor",
    "Now", "Then", "When", "If", "After", "Before",
    "Again", "Also", "As", "Because", "Each", "Every",
    "From", "How", "In", "Let", "No", "Not", "On",
    "One", "Only", "Out", "Since", "Some", "Such",
    "There", "Thus", "What", "Who", "Why", "While",
})


def _normalize_text(text: str) -> str:
    """Apply safe micro-normalizations to a paragraph.

    1. Capitalize the first alphabetic character.
    2. Ensure the paragraph ends with terminal punctuation.
    3. Insert a missing period before obvious sentence starters
       (only when the preceding character is a lowercase letter,
        so "the Light Mind" is never touched).

    Bracket content ([GAP-N: ...] and [...]) is protected —
    normalization skips everything inside square brackets.
    """
    if not text:
        return text

    # --- 1. Capitalize first letter ---
    for i, ch in enumerate(text):
        if ch.isalpha():
            text = text[:i] + ch.upper() + text[i + 1:]
            break

    # --- 2. Terminal punctuation ---
    stripped = text.rstrip()
    if stripped and stripped[-1] not in '.!?;:)\'\"\u2019\u201d':
        text = stripped + '.'

    # --- 3. Missing period before sentence starters ---
    # Strategy: split text into bracket-protected and free regions,
    # only apply the regex to free regions.
    parts = re.split(r'(\[[^\]]*\])', text)
    result: list[str] = []
    for j, part in enumerate(parts):
        if part.startswith('['):
            # Inside brackets — pass through unchanged
            result.append(part)
        else:
            # Free text — insert period where needed
            def _insert_period(m: re.Match) -> str:
                before, space, word = m.group(1), m.group(2), m.group(3)
                if word in _SENTENCE_STARTERS:
                    return before + '.' + space + word
                return m.group(0)

            part = re.sub(
                r'([a-z])(\s+)([A-Z][a-z]+\b)', _insert_period, part,
            )
            result.append(part)
    text = ''.join(result)

    return text


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------


def _styles() -> dict:
    return dict(
        # --- Title page ---
        main_title=ParagraphStyle(
            "MT", fontName=FONT_BOLD, fontSize=24,
            alignment=TA_CENTER, leading=30, spaceAfter=8,
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

        # --- Table of Contents ---
        toc_part=ParagraphStyle(
            "TOCP", fontName=FONT_BOLD, fontSize=11,
            alignment=TA_LEFT, leading=16,
            spaceBefore=10, spaceAfter=2,
        ),
        toc_chapter=ParagraphStyle(
            "TOCC", fontName=FONT_ROMAN, fontSize=10,
            alignment=TA_LEFT, leading=14,
            spaceAfter=1, leftIndent=8 * mm,
        ),

        # --- Section titles (CONTENTS, OBSERVATIONS, etc.) ---
        section_title=ParagraphStyle(
            "SECT", fontName=FONT_BOLD, fontSize=16,
            alignment=TA_CENTER, leading=22,
            spaceBefore=0, spaceAfter=16,
        ),

        # --- Part divider pages ---
        part_number=ParagraphStyle(
            "PN", fontName=FONT_ROMAN, fontSize=12,
            alignment=TA_CENTER, leading=16, spaceAfter=4,
            textColor=HexColor(MUTED),
        ),
        part_title=ParagraphStyle(
            "PT", fontName=FONT_BOLD, fontSize=18,
            alignment=TA_CENTER, leading=24, spaceAfter=12,
        ),
        part_desc=ParagraphStyle(
            "PD", fontName=FONT_ITALIC, fontSize=10.5,
            alignment=TA_JUSTIFY, leading=15,
            spaceAfter=6, leftIndent=15 * mm, rightIndent=15 * mm,
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

        # --- Core (substrate) text ---
        body=ParagraphStyle(
            "B", fontName=FONT_ROMAN, fontSize=10.5,
            alignment=TA_JUSTIFY, leading=14.5,
            spaceAfter=6, firstLineIndent=18,
        ),
        body_first=ParagraphStyle(
            "B1", fontName=FONT_ROMAN, fontSize=10.5,
            alignment=TA_JUSTIFY, leading=14.5,
            spaceAfter=6, firstLineIndent=0,
        ),

        # --- Observations ---
        obs_title=ParagraphStyle(
            "OT", fontName=FONT_BOLD, fontSize=12,
            alignment=TA_LEFT, leading=16,
            spaceBefore=16, spaceAfter=6,
        ),
        obs_body=ParagraphStyle(
            "OB", fontName=FONT_ROMAN, fontSize=10,
            alignment=TA_JUSTIFY, leading=14,
            spaceAfter=10,
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
            spaceAfter=4,
            leftIndent=10 * mm,
        ),
        preface_indent_italic=ParagraphStyle(
            "PFII", fontName=FONT_ITALIC, fontSize=9.5,
            alignment=TA_JUSTIFY, leading=13,
            spaceAfter=4,
            leftIndent=10 * mm,
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
    )


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_structure() -> dict:
    with open(STRUCTURE_FILE, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# PDF content builders
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


def _title_page(st: dict) -> list:
    return [
        Spacer(1, 55 * mm),
        Paragraph(
            "THE ANCIENT WORD",
            st["main_title"],
        ),
        Spacer(1, 10 * mm),
        Paragraph(
            "Recovered from the Kephalaia of the Teacher",
            st["subtitle"],
        ),
        Spacer(1, 4 * mm),
        Paragraph(
            "The correspondential teaching described by Emanuel Swedenborg,<br/>"
            "extracted from its Manichaean vessel<br/>"
            "and organized by its own internal structure",
            st["subtitle2"],
        ),
        Spacer(1, 30 * mm),
        Paragraph(
            "Based on the translation by Iain Gardner (1995)<br/>"
            "<i>The Kephalaia of the Teacher: The Edited Coptic<br/>"
            "Manichaean Texts in Translation with Commentary</i>",
            st["credit"],
        ),
        Spacer(1, 8 * mm),
        Paragraph(
            "Ancient teaching substrate extracted and organized by discovered structure.<br/>"
            "Structure discovered by Claude Opus 4.6 from the text alone,<br/>"
            "without access to manuscript chapter divisions.",
            st["credit"],
        ),
        Spacer(1, 6 * mm),
        Paragraph(
            f'Lacunae markers shown in <font color="{LACUNA_GRAY}">light gray</font>.',
            st["credit"],
        ),
        PageBreak(),
    ]


def _preface_pages(st: dict) -> list:
    """Generate the preface pages for the book."""
    elements: list = [
        Spacer(1, 15 * mm),
        Paragraph("PREFACE", st["preface_title"]),
        Spacer(1, 6 * mm),
    ]

    p = st["preface_body"]
    pi = st["preface_italic"]
    h = st["preface_heading"]
    ind = st["preface_indent"]
    indi = st["preface_indent_italic"]
    lbl = st["preface_label"]

    # --- Opening: The Ancient Word ---
    elements.append(Paragraph(
        "In the eighteenth century, Emanuel Swedenborg described a text he "
        "called the &ldquo;Ancient Word&rdquo; &mdash; written entirely in "
        "correspondences, older than the Hebrew scriptures, carried eastward "
        "by the <i>Bene Qedem</i> (the &ldquo;Children of the East&rdquo;), "
        "and preserved in a region he called &ldquo;Great Tartary.&rdquo; "
        "He said it still existed there.",
        pi,
    ))
    elements.append(Paragraph(
        "This is that text.",
        pi,
    ))
    elements.append(Paragraph(
        "What you hold is the teaching core of the <i>Kephalaia of the "
        "Teacher</i>, a third- or fourth-century Coptic Manichaean "
        "manuscript translated by Iain Gardner in 1995. Within this "
        "manuscript lies a complete correspondential cosmology that matches "
        "Swedenborg&rsquo;s description of the Ancient Word in every "
        "particular: written entirely in correspondences, complete from "
        "beginning to end, containing the content the Bible attributes to "
        "now-lost texts, found in the exact region Swedenborg identified, "
        "and tracing back through the exact transmission path he described.",
        p,
    ))

    # --- What Swedenborg Described ---
    elements.append(Paragraph("What Swedenborg Described", h))
    elements.append(Paragraph(
        "Swedenborg made five specific claims about the Ancient Word. "
        "(1)&nbsp;It was written entirely in the style of correspondences "
        "&mdash; natural images expressing spiritual realities through "
        "organic, functional relationships, not arbitrary symbolism. "
        "(2)&nbsp;It contained a complete teaching from beginning to end. "
        "(3)&nbsp;The biblical references to the &ldquo;Wars of the "
        "LORD&rdquo; (Numbers 21:14) and the &ldquo;Book of "
        "Jashar&rdquo; (Joshua 10:13, 2&nbsp;Samuel 1:18) were citations "
        "from this text. (4)&nbsp;It was preserved in &ldquo;Great "
        "Tartary&rdquo; &mdash; the vast Central Asian interior. "
        "(5)&nbsp;It was carried there by the <i>Bene Qedem</i>, the "
        "ancient bearers of correspondential knowledge.",
        p,
    ))
    elements.append(Paragraph(
        "All five claims can be independently verified against the "
        "text extracted here.",
        pi,
    ))

    # --- Five Lines of Evidence ---
    elements.append(Paragraph("Five Lines of Evidence", h))

    elements.append(Paragraph("1. Written entirely in correspondences", lbl))
    elements.append(Paragraph(
        "The teaching core extracted from the <i>Kephalaia</i> is "
        "correspondential throughout. &sect;490&ndash;&sect;507 "
        "(identified as 90% ancient substrate) state the organizing "
        "principle directly: &ldquo;This whole universe, above and below, "
        "reflects the pattern of the human body.&rdquo; The text then "
        "systematically maps the cosmos onto the human form &mdash; head "
        "to feet, organ by organ &mdash; with each correspondence "
        "grounded in function. Elsewhere, five storehouses map to five "
        "elements, to five trees, to five genera, to five worlds &mdash; "
        "and the pattern repeats through realms, metals, and tastes. "
        "A body-cosmos isomorphism culminates in a soul-body binding "
        "formula. This is not scattered symbolic language. It is "
        "systematic correspondential architecture sustained across "
        "934&nbsp;paragraphs.",
        ind,
    ))

    elements.append(Paragraph("2. Complete from beginning to end", lbl))
    elements.append(Paragraph(
        "The text contains the complete arc of regeneration. "
        "&sect;1&ndash;&sect;9 present the primordial cosmogonic "
        "narrative: the separation of light and darkness, the descent "
        "of the Divine Human into combat with falsity, the ordering of "
        "recaptured good, and the final restoration &mdash; "
        "&ldquo;a single God comes to be over the totality.&rdquo; "
        "Parts&nbsp;2 through 12 systematically elaborate every phase: the "
        "dual architecture of reality, the descent of influx, redemptive "
        "combat, the interior of the Divine, the anatomy of evil, the "
        "ordering of the spiritual world, purification of mind, the "
        "architecture of influx, the formation of the human being, the "
        "correspondences of heaven and earth, and the dynamics of "
        "spiritual life. The final vision (&sect;899&ndash;&sect;934) "
        "closes with three entreaties, the two fundamental essences, "
        "and the portals of divine conjunction. This is not a fragment. "
        "It is a complete text.",
        ind,
    ))

    elements.append(Paragraph(
        "3. Contains the Wars of the Lord and the Book of Jashar",
        lbl,
    ))
    elements.append(Paragraph(
        "The Hebrew Bible cites two lost texts by name: the "
        "&ldquo;Wars of the LORD&rdquo; (Numbers 21:14) and the "
        "&ldquo;Book of Jashar&rdquo; &mdash; the Book of the Upright "
        "(Joshua 10:13, 2&nbsp;Samuel 1:18). Swedenborg identified both as "
        "portions of the Ancient Word. Both are found here. "
        "A consonantal analysis of the "
        "Wars of the LORD demonstrates that the quotation fragments, "
        "read at the three degrees Swedenborg specified (natural, "
        "spiritual, celestial), reveal a cosmic architecture &mdash; "
        "the Beloved, the Conflagration, Cosmic Trenches, the Seat of "
        "Watchers, the Border of the Father &mdash; that matches the "
        "macrocosmic narrative in this text exactly. "
        "The Book of Jashar &mdash; the practical manual of the upright "
        "life &mdash; matches the pedagogical content: how stillness "
        "defeats falsity, how the mind is regenerated faculty by faculty, "
        "how the divine call meets human obedience. The cosmological "
        "text and the pedagogical text, the macrocosm and the microcosm "
        "&mdash; both reside together in the same teaching.",
        ind,
    ))

    elements.append(Paragraph("4. Found exactly where Swedenborg said", lbl))
    elements.append(Paragraph(
        "Swedenborg located the Ancient Word in &ldquo;Great "
        "Tartary&rdquo; &mdash; the vast interior of Central Asia. "
        "The <i>Kephalaia</i> was transmitted through the Manichaean "
        "tradition, which was officially adopted as state religion by "
        "the Uyghur Khaganate in 762/763&nbsp;CE. The Kingdom of Qocho "
        "preserved Manichaean texts in cave temple-libraries at Turfan "
        "&mdash; in the heart of Swedenborg&rsquo;s &ldquo;Great "
        "Tartary.&rdquo; The Coptic manuscript translated by Gardner is "
        "a sister text of these Central Asian recensions. The text was "
        "found where Swedenborg said it would be.",
        ind,
    ))

    elements.append(Paragraph(
        "5. Traces back through the transmission path Swedenborg described",
        lbl,
    ))
    elements.append(Paragraph(
        "Swedenborg said the Ancient Word was carried eastward by the "
        "<i>Bene Qedem</i> &mdash; the Children of the East &mdash; "
        "the ancient bearers of correspondential knowledge. The "
        "substrate teaching in the <i>Kephalaia</i> predates its "
        "Manichaean frame. Its five-fold architecture, body-cosmos "
        "correspondence system, and doctrine of discrete degrees are "
        "rooted in Zoroastrian cosmology &mdash; specifically the "
        "tradition of <i>Vohu Manah</i> (Good Mind), the "
        "<i>Amesha Spentas</i>, and the "
        "<i>mēnōg/gētīg</i> (spiritual/material) ontology. The "
        "Apocryphon of John, a related text, explicitly cites "
        "&ldquo;the book of Zoroaster&rdquo; as its source for "
        "the body-creation angel list &mdash; a correspondential "
        "catalogue in exactly the form of <i>Bene Qedem</i> tradition. "
        "The teaching did not originate with Mani. He received it from "
        "the Persian-Zoroastrian tradition, which received it from the "
        "Children of the East.",
        ind,
    ))

    # --- Three Layers ---
    elements.append(Paragraph("Three Layers", h))
    elements.append(Paragraph(
        "Within the <i>Kephalaia of the Teacher</i>, three distinct "
        "layers can be identified:",
        p,
    ))

    elements.append(Paragraph(
        '<b>Layer 3 (Outermost): The Hagiographic Frame.</b> '
        '&ldquo;Once again the Enlightener sits in the congregation&hellip;&rdquo; '
        '&mdash; the narrative scaffolding that casts the teaching as dialogues '
        'between Mani and his disciples. This layer belongs entirely to the '
        'Manichaean institutional setting.',
        ind,
    ))
    elements.append(Paragraph(
        '<b>Layer 2 (Middle): The Manichaean Theological Overlay.</b> '
        'Names, titles, and institutional vocabulary that Mani&rsquo;s tradition '
        'imposed upon older content: &ldquo;Jesus the Splendour,&rdquo; '
        '&ldquo;Light Mind,&rdquo; &ldquo;Holy Spirit,&rdquo; '
        '&ldquo;apostle,&rdquo; &ldquo;the elect.&rdquo; These terms '
        'replaced earlier designations &mdash; almost certainly Persian &mdash; '
        'while leaving the underlying teaching structure intact.',
        ind,
    ))
    elements.append(Paragraph(
        '<b>Layer 1 (Core): The Ancient Word.</b> '
        'A systematic correspondential cosmology organized around five degrees '
        'at every scale, teaching the complete arc of regeneration from first '
        'to last. This layer is older than Mani. Its five-fold architecture, '
        'its body-cosmos correspondence system, its doctrine of discrete '
        'degrees, its &ldquo;summons and obedience&rdquo; mechanism (divine '
        'influx and human reception) &mdash; these do not originate with '
        'third-century Babylonia. They preserve the Ancient Word whose '
        'roots extend through Zoroastrian Persia into the proto-Indo-Iranian '
        'and ancient Near Eastern traditions of the <i>Bene Qedem</i>.',
        ind,
    ))
    elements.append(Paragraph(
        "This book is an extraction of Layer 1 &mdash; the Ancient "
        "Word &mdash; from its Manichaean vessel.",
        pi,
    ))

    # --- What Was Extracted ---
    elements.append(Paragraph("What Was Extracted", h))
    elements.append(Paragraph(
        "The extraction was performed using the methods of textual "
        "criticism, with Claude Opus 4.6 &mdash; an advanced language "
        "model &mdash; serving as the primary analytical instrument. "
        "The entire <i>Kephalaia</i> corpus was read as a continuous "
        "flow of 934 sequentially numbered paragraphs. Each passage "
        "was analyzed for editorial layering: separating the "
        "hagiographic frame (Layer&nbsp;3) from the Manichaean "
        "theological overlay (Layer&nbsp;2) and the ancient teaching "
        "core (Layer&nbsp;1). The model read the text as a philologist "
        "would &mdash; attending to vocabulary shifts, structural seams, "
        "and correspondential consistency &mdash; but across the full "
        "corpus as a single sustained reading. The structure of this "
        "book &mdash; its twelve parts and forty-four chapters &mdash; "
        "was not imposed from the manuscript&rsquo;s chapter divisions. "
        "It was discovered by reading the text as a single continuous "
        "teaching and identifying where the natural structural seams fall.",
        p,
    ))
    elements.append(Paragraph(
        "The reader will notice that the number five recurs at every "
        "scale. The text itself teaches this: five elements, five "
        "faculties, five trees, five storehouses, five wars, five "
        "liberations, five modes of conjunction, five works of fire, "
        "five watch-stations. Chapter 48 makes the principle explicit "
        "&mdash; &ldquo;In each one of these five garments there are "
        "five powers&hellip; the summons with the obedience constitute "
        "twenty-five characteristics in their twenty-five limbs.&rdquo; "
        "This is not a numerological coincidence. The five-fold "
        "principle is the teaching&rsquo;s own organizing architecture: "
        "five degrees through which the one reality makes itself "
        "receivable, repeated at every level from cosmic emanation to "
        "human anatomy. It is visible on every page.",
        p,
    ))

    # --- What Was Not Changed ---
    elements.append(Paragraph("What Was Not Changed", h))
    elements.append(Paragraph(
        "No naming overlays have been corrected. No institutional vocabulary "
        "has been replaced. &ldquo;Jesus the Splendour&rdquo; has not been "
        "reverted to its Persian substrate; &ldquo;Light Mind&rdquo; has not "
        "been changed back to <i>Wahman</i>. This was a deliberate choice. "
        "The text is presented as it has come down to us &mdash; layered, "
        "evolved, carrying the marks of every tradition through which "
        "it passed.",
        p,
    ))
    elements.append(Paragraph(
        "The Coptic papyrus is damaged. Where gaps remained in the extracted "
        "text, those that could be constrained by correspondential logic and "
        "surrounding context were restored; those too large or uncertain were "
        "left open. Square brackets mark both the original lacunae and the "
        "restorations throughout. The restoration method was the same "
        "correspondences that organize the text itself: a spiritual reading "
        "of each chapter identified what must belong in each gap, and the "
        "fill was written in the text&rsquo;s own vocabulary.",
        p,
    ))
    elements.append(Paragraph(
        "But the reader should know what the naming marks are, so they can "
        "see through them to the teaching beneath.",
        pi,
    ))

    # --- The Naming Overlays ---
    elements.append(Paragraph("The Naming Overlays", h))
    elements.append(Paragraph(
        "A systematic review of the extracted corpus identified the "
        "following naming patterns that belong to the Manichaean "
        "editorial layer (Layer 2), not to the ancient teaching core:",
        p,
    ))

    elements.append(Paragraph(
        '<b>&ldquo;Jesus the Splendour&rdquo;</b> appears in at least eighteen '
        'passages, always designating the same cosmic function: the divine '
        'wisdom that proceeds into illumination, purification, and liberation '
        'of captive good. This is a Manichaean-Christian name mapped onto a '
        'pre-existing Persian cosmic figure. The substrate designation was '
        'almost certainly <i>Xradeshahr</i> (Splendor of the Realm) or a '
        'form related to Avestan <i>xvarənah</i> (divine luminous '
        'glory). The entity&rsquo;s consistent function &mdash; radiant '
        'divine wisdom that illuminates, separates truth from falsity, and '
        'liberates &mdash; maps precisely onto this pre-Manichaean Iranian '
        'concept. There is nothing specifically Christian about this entity '
        'in any of its eighteen appearances.',
        ind,
    ))
    elements.append(Paragraph(
        '<b>&ldquo;Light Mind&rdquo; / &ldquo;Light-Nous&rdquo;</b> appears '
        'in at least eleven passages. This is Greek philosophical vocabulary '
        '(νοῦς) entering through Hellenistic '
        'synthesis. The substrate designation was almost certainly '
        '<i>Wahman</i> &mdash; from Avestan <i>Vohu Manah</i> (Good Mind), '
        'one of the Amesha Spentas in Zoroastrian theology. The '
        'entity&rsquo;s consistent function &mdash; entering the human '
        'person, awakening from spiritual torpor, gathering what is scattered, '
        'enlightening the understanding &mdash; matches the Zoroastrian '
        'Vohu Manah&rsquo;s role precisely.',
        ind,
    ))

    elements.append(Paragraph(
        '<b>&ldquo;Saklas&rdquo;</b> (&sect;592) is Aramaic for &ldquo;fool&rdquo; '
        '&mdash; a distinctly Gnostic/Sethian name for the malformed creator, '
        'imported from texts like the Apocryphon of John. The substrate likely '
        'used Persian demonological designations, possibly <i>Az</i> (the '
        'demon of concupiscence) and <i>Jeh</i> (the demoness), both from '
        'Zoroastrian tradition.',
        ind,
    ))
    elements.append(Paragraph(
        '<b>&ldquo;Cross of Light&rdquo; / &ldquo;crucified&rdquo;</b> appears '
        'in at least eleven passages (&sect;4, &sect;32, &sect;35, &sect;327, '
        '&sect;394, &sect;571, &sect;640, &sect;694, &sect;703, &sect;771, '
        '&sect;773), mapping Christian crucifixion vocabulary onto the substrate '
        'concept of divine light scattered and bound within matter. The substrate '
        'likely described this as the dispersion or captivity of luminous '
        'elements &mdash; a concept native to Zoroastrian and Zurvanite cosmology '
        'that required no crucifixion metaphor.',
        ind,
    ))
    elements.append(Paragraph(
        '<b>&ldquo;Matter&rdquo; / &ldquo;Hylē&rdquo;</b> appears throughout '
        'as a personified feminine entity (&sect;31, &sect;33, &sect;35, '
        '&sect;52, &sect;252, &sect;530), consistently paired with the '
        'substrate epithet &ldquo;the thought of death.&rdquo; This is Greek '
        'philosophical vocabulary '
        '(ὕλη) replacing what was almost '
        'certainly a Persian demonological name &mdash; probably <i>Āz</i> '
        '(the demon of concupiscence) or <i>Jeh</i> (the demoness) from '
        'Zurvanite tradition.',
        ind,
    ))
    elements.append(Paragraph(
        '<b>&ldquo;Holy Spirit&rdquo;</b> (&sect;427, &sect;617) overlays what '
        'was almost certainly <i>Spenta Mainyu</i> (Holy/Bounteous Spirit) '
        'from Zoroastrian theology &mdash; not identical to the Christian '
        'Third Person of the Trinity.',
        ind,
    ))
    elements.append(Paragraph(
        '<b>&ldquo;Apostle&rdquo;</b> (&sect;78, &sect;197, &sect;291, &sect;313) '
        'is Greek Christian institutional vocabulary '
        '(ἀπόστολος). '
        'The substrate likely used a Persian term for the transmitter of '
        'sacred knowledge, possibly related to <i>frēstag</i> '
        '(messenger/envoy).',
        ind,
    ))
    elements.append(Paragraph(
        '<b>&ldquo;The elect one&rdquo;</b> (&sect;106) and '
        '<b>&ldquo;holy church&rdquo;</b> (&sect;11) are Manichaean '
        'institutional vocabulary replacing what were cosmic entity names '
        'in the five-fold correspondential architecture.',
        ind,
    ))
    elements.append(Paragraph(
        '<b>&ldquo;Good news&rdquo;</b> (&sect;162) is '
        'εὐαγγέλιον '
        '&mdash; distinctly Christian vocabulary with strong Pauline associations.',
        ind,
    ))

    # --- Deeper Transmission Evidence ---
    elements.append(Paragraph("Deeper Transmission Evidence", h))
    elements.append(Paragraph(
        "Beyond the Manichaean overlay, the review also identified material "
        "that predates even the Persian-Zoroastrian vessel:",
        p,
    ))
    elements.append(Paragraph(
        "The five dark elements (smoke, fire, wind, water, darkness) do not "
        "match either classical Greek (four elements) or standard Zoroastrian "
        "categories. This sequence appears to preserve a "
        "<b>proto-Indo-Iranian or Mesopotamian elemental cosmology</b> older "
        "than the Persian formulation.",
        ind,
    ))
    elements.append(Paragraph(
        "The &ldquo;sea giant&rdquo; passage (&sect;437&ndash;441) &mdash; "
        "a composite being formed from cosmic debris in a primordial sea, "
        "bearing the imprint of all celestial cycles upon its body &mdash; "
        "has parallels to Mesopotamian creation narratives and "
        "<b>Zurvanite cosmogony</b>, and may represent one of the oldest "
        "layers in the text.",
        ind,
    ))
    elements.append(Paragraph(
        "The water-reflection/inversion teaching (&sect;804&ndash;808) "
        "&mdash; the upper world reflected inversely in the lower &mdash; "
        "appears across ancient Near Eastern and Vedic/Upanishadic traditions "
        "and expresses a law of correspondence more fundamental than any "
        "single cultural formulation.",
        ind,
    ))
    elements.append(Paragraph(
        "The medical/healing analogy (&sect;393&ndash;397) &mdash; cosmic "
        "healing through three medicines applied in three directions &mdash; "
        "has strong parallels to Mesopotamian therapeutic traditions, "
        "suggesting an ancient Near Eastern substrate beneath the "
        "Persian vessel.",
        ind,
    ))

    # --- How to Read This Text ---
    elements.append(Paragraph("How to Read This Text", h))
    elements.append(Paragraph(
        "You are reading the Ancient Word &mdash; and it has traveled far "
        "to reach you. It was given systematic form in the "
        "Persian-Zoroastrian tradition, where it acquired its five-fold "
        "architecture, its body-cosmos correspondence map, and its doctrine "
        "of discrete degrees. It was received by Mani in third-century "
        "Babylonia, who translated its Persian entities into a mixed "
        "vocabulary of Christian, Greek, and Gnostic terms. It was recorded "
        "in Coptic by Manichaean scribes in Egypt. It was translated into "
        "English by Iain Gardner in 1995. And it was extracted from its "
        "manuscript frame and organized by its own internal structure here.",
        p,
    ))
    elements.append(Paragraph(
        "Through all these transmissions, the teaching itself survived. "
        "The five-fold architecture did not change. The body-cosmos "
        "correspondence did not change. The doctrine that reality proceeds "
        "through discrete degrees &mdash; celestial, spiritual, natural "
        "&mdash; did not change. The mechanism of divine influx and human "
        "reception (&ldquo;the summons and the obedience&rdquo;) did not "
        "change. The complete arc of regeneration &mdash; from the primordial "
        "separation of wisdom and falsity through divine descent, combat, "
        "purification, and final restoration &mdash; did not change.",
        p,
    ))
    elements.append(Paragraph(
        "The names changed. The teaching did not.",
        pi,
    ))
    elements.append(Paragraph(
        "When you encounter &ldquo;Jesus the Splendour,&rdquo; read: "
        "divine wisdom proceeding into illumination. When you encounter "
        "&ldquo;Light Mind,&rdquo; read: the Good Mind that enters and "
        "awakens. When you encounter &ldquo;First Man,&rdquo; read: "
        "the Divine Human descending into temptation-combat. When you "
        "encounter &ldquo;Living Spirit,&rdquo; read: Divine Truth "
        "proceeding to order all things. When you encounter &ldquo;Third "
        "Ambassador,&rdquo; read: the manifestation of the Divine form "
        "that draws forth captive good. When you encounter &ldquo;the "
        "Father of Greatness,&rdquo; read: the Infinite Divine Love in "
        "which all things originate.",
        p,
    ))
    elements.append(Paragraph(
        "The correspondences are in the text. They have always been in "
        "the text. The Manichaean names are garments. What wears them "
        "is the Ancient Word.",
        pi,
    ))
    elements.append(PageBreak())
    return elements


def _toc_page(st: dict, structure: dict) -> list:
    elements: list = [
        Spacer(1, 15 * mm),
        Paragraph("CONTENTS", st["section_title"]),
        Spacer(1, 6 * mm),
    ]

    indent = 8 * mm  # chapter indent

    for part in structure["parts"]:
        pn = part["part_number"]
        part_key = f"part_{pn}"
        part_page = _page_registry.get(part_key, "")
        part_title = f"Part {pn} \u2014 {part['title']}"

        elements.append(Spacer(1, 10))   # spaceBefore
        elements.append(_TocLine(
            part_title, part_page,
            title_font=FONT_BOLD, font_size=11, leading=16,
        ))

        for ch in structure["chapters"]:
            if ch["part_number"] == pn:
                ch_key = f"ch_{ch['section_start']}"
                ch_page = _page_registry.get(ch_key, "")

                elements.append(_TocLine(
                    ch["title"], ch_page,
                    title_font=FONT_ROMAN, font_size=10, leading=14,
                    indent=indent,
                ))

    # --- Back matter entries ---
    lex_page = _page_registry.get("lexicon", "")
    if lex_page:
        elements.append(Spacer(1, 10))
        elements.append(_TocLine(
            "Correspondence Lexicon", lex_page,
            title_font=FONT_BOLD, font_size=11, leading=16,
        ))

    elements.append(PageBreak())
    return elements


def _part_page(st: dict, part: dict) -> list:
    return [
        _PageRecorder(f"part_{part['part_number']}"),
        Spacer(1, 60 * mm),
        Paragraph(f'Part {part["part_number"]}', st["part_number"]),
        Spacer(1, 4 * mm),
        Paragraph(_xml_esc(part["title"]), st["part_title"]),
        Spacer(1, 12 * mm),
        Paragraph(_xml_esc(part["description"]), st["part_desc"]),
        PageBreak(),
    ]


def _render_chapter(
    st: dict,
    ch: dict,
    para_lookup: dict[int, str],
) -> list:
    """Render a structural chapter using §-range from book_structure.json.

    All titles come from the structure.  Paragraph text is selected
    by the §-range (section_start – section_end).
    """
    elements: list = []

    # Bookmark for TOC page number
    elements.append(_PageRecorder(f"ch_{ch['section_start']}"))

    # --- Chapter heading (from structure only) ---
    elements.append(
        Paragraph(_xml_esc(ch["title"]), st["chapter_title"])
    )
    if ch.get("role"):
        role_label = ch["role"].replace("_", " ").title()
        elements.append(Paragraph(role_label, st["chapter_role"]))

    # --- Chapter description (from the model's analysis) ---
    if ch.get("description"):
        elements.append(
            Paragraph(_xml_esc(ch["description"]), st["chapter_desc"])
        )

    # Thin rule after description
    elements.append(
        HRFlowable(
            width="50%", thickness=0.5,
            color=HexColor(RULE_COLOR),
            spaceAfter=8 * mm, spaceBefore=4 * mm,
        )
    )

    # --- Select paragraphs by §-range ---
    s_start = ch["section_start"]
    s_end = ch["section_end"]
    first = True
    para_count = 0

    for seq_n in range(s_start, s_end + 1):
        text = para_lookup.get(seq_n)
        if not text:
            continue

        text = _clean_core_text(text)
        if not text:
            continue

        text = _normalize_text(text)
        text = _clean_gap_markers(text)
        styled = _style_lacunae(text)
        style = st["body_first"] if first else st["body"]
        first = False
        para_count += 1

        try:
            elements.append(Paragraph(styled, style))
        except Exception as exc:
            print(f"  WARNING: skipped §{seq_n} ({exc})")

    if para_count == 0:
        elements.append(
            Paragraph(
                f'<font color="{LACUNA_GRAY}">[No surviving text in this section]</font>',
                st["body_first"],
            )
        )

    elements.append(PageBreak())
    return elements


# ---------------------------------------------------------------------------
# Lexicon renderer
# ---------------------------------------------------------------------------

_CATEGORY_LABELS = {
    "cosmological_entity": "Cosmological Entities",
    "cosmic_element": "Cosmic Elements & Substances",
    "structural_term": "Structural Terms",
    "body_anatomy": "Body & Anatomy",
    "natural_imagery": "Natural Imagery",
    "action_process": "Actions & Processes",
    "quality_state": "Qualities & States",
    "numerical_correspondence": "Numerical Correspondences",
}

_CATEGORY_ORDER = [
    "cosmological_entity",
    "cosmic_element",
    "structural_term",
    "body_anatomy",
    "natural_imagery",
    "action_process",
    "quality_state",
    "numerical_correspondence",
]


def _load_lexicon() -> dict | None:
    """Load the correspondence lexicon JSON, or None if absent."""
    if not LEXICON_FILE.exists():
        return None
    with open(LEXICON_FILE, encoding="utf-8") as f:
        return json.load(f)


def _section_to_chapters(section_refs: list[str],
                         chapters: list[dict]) -> list[int]:
    """Convert §N / §N\u2013§M references to sorted, unique chapter indices."""
    import re
    sec_nums: set[int] = set()
    for ref in section_refs:
        # Match §N or §N–§M (en-dash or hyphen)
        for m in re.finditer(r'§(\d+)(?:[–\-](\d+))?', ref):
            lo = int(m.group(1))
            hi = int(m.group(2)) if m.group(2) else lo
            sec_nums.update(range(lo, hi + 1))
    if not sec_nums:
        return []
    ch_indices: set[int] = set()
    for idx, ch in enumerate(chapters):
        s, e = ch["section_start"], ch["section_end"]
        if any(s <= n <= e for n in sec_nums):
            ch_indices.add(idx)
    return sorted(ch_indices)


def _render_lexicon(st: dict, lexicon: dict, chapters: list[dict]) -> list:
    """Render the correspondence lexicon as PDF flowables."""
    elements: list = [
        _PageRecorder("lexicon"),
        Spacer(1, 30 * mm),
        Paragraph("CORRESPONDENCE LEXICON", st["section_title"]),
        Spacer(1, 4 * mm),
        Paragraph(
            "A comprehensive mapping of every natural term in the Ancient "
            "Word to its spiritual correspondence. Entries are organized "
            "by category. Where the same natural image carries both a "
            "positive and a negative sense, the opposite sense is noted.",
            ParagraphStyle(
                "LI", fontName=FONT_ITALIC, fontSize=10,
                alignment=TA_CENTER, leading=14, spaceAfter=16,
                textColor=HexColor(NOTE_COLOR),
            ),
        ),
    ]

    entries = lexicon.get("entries", [])
    by_cat: dict[str, list] = {}
    for e in entries:
        by_cat.setdefault(e["category"], []).append(e)

    for cat_key in _CATEGORY_ORDER:
        group = by_cat.get(cat_key, [])
        if not group:
            continue

        label = _CATEGORY_LABELS.get(cat_key, cat_key.replace("_", " ").title())
        elements.append(Paragraph(
            _xml_esc(f"{label} ({len(group)})"),
            st["lex_category"],
        ))
        elements.append(HRFlowable(
            width="100%", thickness=0.4,
            color=HexColor(RULE_COLOR),
            spaceAfter=4 * mm,
        ))

        for e in group:
            # --- Entry heading: term → spiritual meaning ---
            nat = _xml_esc(e["natural_term"])
            spi = _xml_esc(e["spiritual_meaning"])
            head = f'<b>{nat}</b> \u2014 <i>{spi}</i>'

            # Variants
            variants = e.get("natural_variants", [])
            if variants:
                vlist = ", ".join(_xml_esc(v) for v in variants)
                head += f'  <font color="{MUTED}" size="8">({vlist})</font>'

            elements.append(Paragraph(head, st["lex_entry_head"]))

            # --- Definition ---
            defn = e.get("definition", "")
            if defn:
                elements.append(Paragraph(_xml_esc(defn), st["lex_entry_body"]))

            # --- Opposite sense ---
            opp = e.get("opposite_sense", "")
            if opp:
                elements.append(Paragraph(
                    f'Opposite sense: {_xml_esc(opp)}',
                    st["lex_entry_detail"],
                ))

            # --- Notes (replaces old detail line) ---
            notes = e.get("notes", "")
            ch_refs = _section_to_chapters(
                e.get("section_refs", []), chapters
            )
            ch_label = ""
            if ch_refs:
                ch_label = "Ch. " + ", ".join(str(c + 1) for c in ch_refs)

            if notes and ch_label:
                elements.append(Paragraph(
                    f'{_xml_esc(notes)}  '
                    f'<font color="{MUTED}">({ch_label})</font>',
                    st["lex_entry_detail"],
                ))
            elif notes:
                elements.append(Paragraph(
                    _xml_esc(notes), st["lex_entry_detail"],
                ))
            elif ch_label:
                elements.append(Paragraph(
                    f'<font color="{MUTED}">({ch_label})</font>',
                    st["lex_entry_detail"],
                ))

    elements.append(PageBreak())
    return elements


def _render_observations(st: dict, observations: list[dict]) -> list:
    """Render the structural observations section."""
    elements: list = [
        Spacer(1, 30 * mm),
        Paragraph("STRUCTURAL OBSERVATIONS", st["section_title"]),
        Spacer(1, 8 * mm),
        Paragraph(
            "Patterns and principles identified by reading the entire "
            "corpus as a single continuous text, without manuscript "
            "chapter divisions.",
            ParagraphStyle(
                "OI", fontName=FONT_ITALIC, fontSize=10,
                alignment=TA_CENTER, leading=14, spaceAfter=16,
                textColor=HexColor(NOTE_COLOR),
            ),
        ),
    ]

    for obs in observations:
        elements.append(
            Paragraph(_xml_esc(obs["title"]), st["obs_title"])
        )
        elements.append(
            Paragraph(_xml_esc(obs["content"]), st["obs_body"])
        )

    return elements


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def build_pdf():
    print("Loading structure ...")
    structure = load_structure()

    parts = structure["parts"]
    chapters = structure["chapters"]
    observations = structure["observations"]

    print(
        f"  {len(parts)} parts, {len(chapters)} chapters, "
        f"{len(observations)} observations"
    )

    # Build the global §N → paragraph text lookup
    print("\nBuilding paragraph lookup ...")
    para_lookup = build_paragraph_lookup()
    print(f"  {len(para_lookup)} paragraphs indexed (§1–§{max(para_lookup)})")

    # PDF setup
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    st = _styles()

    # Use temp file to avoid viewer lock, then rename
    build_target = OUTPUT_TMP
    doc = SimpleDocTemplate(
        str(build_target),
        pagesize=A4,
        leftMargin=25 * mm,
        rightMargin=25 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title="The Ancient Word \u2014 Recovered from the Kephalaia of the Teacher",
        author="Manichaean Analysis Project",
    )

    elements: list = []

    # ---- Title page ----
    elements.extend(_title_page(st))

    # ---- Preface ----
    elements.extend(_preface_pages(st))

    # ---- Table of contents ----
    elements.extend(_toc_page(st, structure))

    # ---- Parts & chapters ----
    current_part = None
    for ch_idx, ch in enumerate(chapters):
        pn = ch["part_number"]

        # Part divider page
        if pn != current_part:
            current_part = pn
            part = next(p for p in parts if p["part_number"] == pn)
            elements.extend(_part_page(st, part))

        # Chapter content — selected by §-range
        s_start = ch["section_start"]
        s_end = ch["section_end"]
        n_paras = sum(1 for n in range(s_start, s_end + 1) if n in para_lookup)
        readable = ch["title"][:60]
        print(f"  Ch {ch_idx}: §{s_start}–§{s_end} ({n_paras} ¶)  \"{readable}\"")
        elements.extend(_render_chapter(st, ch, para_lookup))

    # ---- Correspondence Lexicon (back matter) ----
    lexicon = _load_lexicon()
    if lexicon:
        elements.extend(_render_lexicon(st, lexicon, chapters))
        n_lex = len(lexicon.get("entries", []))
        print(f"\n  Lexicon: {n_lex} entries")

    # Build — two passes: first to collect page numbers, second with TOC
    print(f"\n  Pass 1: collecting page numbers ({len(elements)} flowables) ...")
    _page_registry.clear()
    doc.build(list(elements), onLaterPages=_page_footer)

    print(f"  Pass 2: rebuilding with page numbers ...")
    # Rebuild TOC with recorded page numbers
    elements_pass2: list = []
    elements_pass2.extend(_title_page(st))
    elements_pass2.extend(_preface_pages(st))
    elements_pass2.extend(_toc_page(st, structure))
    current_part = None
    for ch in chapters:
        pn = ch["part_number"]
        if pn != current_part:
            current_part = pn
            part = next(p for p in parts if p["part_number"] == pn)
            elements_pass2.extend(_part_page(st, part))
        elements_pass2.extend(_render_chapter(st, ch, para_lookup))

    if lexicon:
        elements_pass2.extend(_render_lexicon(st, lexicon, chapters))

    doc2 = SimpleDocTemplate(
        str(build_target),
        pagesize=A4,
        leftMargin=25 * mm,
        rightMargin=25 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title="The Ancient Word \u2014 Recovered from the Kephalaia of the Teacher",
        author="Manichaean Analysis Project",
    )
    doc2.build(elements_pass2, onLaterPages=_page_footer)

    # Rename temp → final (handles viewer-locked file on retry)
    import shutil
    try:
        shutil.move(str(build_target), str(OUTPUT))
    except PermissionError:
        print(f"  \u26a0 Could not overwrite {OUTPUT.name} (file locked).")
        print(f"  Output written to: {build_target}")

    final = OUTPUT if OUTPUT.exists() else build_target
    size_kb = final.stat().st_size / 1024
    print(f"  Saved to {final}")
    print(f"  Size: {size_kb:,.0f} KB")


def main():
    if not STRUCTURE_FILE.exists():
        import sys
        sys.exit(f"Structure file not found: {STRUCTURE_FILE}")

    build_pdf()
    print("\nDone.")


if __name__ == "__main__":
    main()
