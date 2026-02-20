#!/usr/bin/env python3
"""
Generate a structured book PDF of the Kephalaia of the Teacher.

Uses the discovered structure from stage_8_compose.py to organize
the teaching substrate (core text) into a coherent book.

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
)
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.colors import HexColor

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # scripts/tools/ → project root

KEPH_DIR = PROJECT_ROOT / "output" / "projects" / "kephalaia"
STRUCTURE_FILE = KEPH_DIR / "book_structure.json"
CORE_DIR = KEPH_DIR / "core" / "chapters"
RESTORED_DIR = KEPH_DIR / "restored" / "chapters"
OUTPUT = PROJECT_ROOT / "output" / "pdfs" / "Kephalaia_Book.pdf"

PAGE_W, PAGE_H = A4

LACUNA_GRAY = "#999999"
RULE_COLOR = "#CCCCCC"
NOTE_COLOR = "#555555"
MUTED = "#888888"
DARK_MUTED = "#666666"

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
            "MT", fontName="Times-Bold", fontSize=24,
            alignment=TA_CENTER, leading=30, spaceAfter=8,
        ),
        subtitle=ParagraphStyle(
            "ST", fontName="Times-Italic", fontSize=14,
            alignment=TA_CENTER, leading=18, spaceAfter=6,
        ),
        subtitle2=ParagraphStyle(
            "ST2", fontName="Times-Italic", fontSize=11,
            alignment=TA_CENTER, leading=15, spaceAfter=6,
            textColor=HexColor("#777777"),
        ),
        credit=ParagraphStyle(
            "CR", fontName="Times-Roman", fontSize=10,
            alignment=TA_CENTER, leading=14, spaceAfter=6,
            textColor=HexColor(DARK_MUTED),
        ),

        # --- Table of Contents ---
        toc_part=ParagraphStyle(
            "TOCP", fontName="Times-Bold", fontSize=11,
            alignment=TA_LEFT, leading=16,
            spaceBefore=10, spaceAfter=2,
        ),
        toc_chapter=ParagraphStyle(
            "TOCC", fontName="Times-Roman", fontSize=10,
            alignment=TA_LEFT, leading=14,
            spaceAfter=1, leftIndent=8 * mm,
        ),

        # --- Section titles (CONTENTS, OBSERVATIONS, etc.) ---
        section_title=ParagraphStyle(
            "SECT", fontName="Times-Bold", fontSize=16,
            alignment=TA_CENTER, leading=22,
            spaceBefore=0, spaceAfter=16,
        ),

        # --- Part divider pages ---
        part_number=ParagraphStyle(
            "PN", fontName="Times-Roman", fontSize=12,
            alignment=TA_CENTER, leading=16, spaceAfter=4,
            textColor=HexColor(MUTED),
        ),
        part_title=ParagraphStyle(
            "PT", fontName="Times-Bold", fontSize=18,
            alignment=TA_CENTER, leading=24, spaceAfter=12,
        ),
        part_desc=ParagraphStyle(
            "PD", fontName="Times-Italic", fontSize=10.5,
            alignment=TA_JUSTIFY, leading=15,
            spaceAfter=6, leftIndent=15 * mm, rightIndent=15 * mm,
            textColor=HexColor("#444444"),
        ),

        # --- Chapter headings ---
        chapter_title=ParagraphStyle(
            "CHT", fontName="Times-Bold", fontSize=13,
            alignment=TA_CENTER, leading=17,
            spaceBefore=0, spaceAfter=4,
        ),
        chapter_role=ParagraphStyle(
            "CHR", fontName="Times-Italic", fontSize=9,
            alignment=TA_CENTER, leading=12,
            spaceAfter=4, textColor=HexColor(MUTED),
        ),
        chapter_desc=ParagraphStyle(
            "CHD", fontName="Times-Italic", fontSize=10,
            alignment=TA_JUSTIFY, leading=14,
            spaceAfter=12, leftIndent=8 * mm, rightIndent=8 * mm,
            textColor=HexColor(NOTE_COLOR),
        ),

        # --- Core (substrate) text ---
        body=ParagraphStyle(
            "B", fontName="Times-Roman", fontSize=10.5,
            alignment=TA_JUSTIFY, leading=14.5,
            spaceAfter=6, firstLineIndent=18,
        ),
        body_first=ParagraphStyle(
            "B1", fontName="Times-Roman", fontSize=10.5,
            alignment=TA_JUSTIFY, leading=14.5,
            spaceAfter=6, firstLineIndent=0,
        ),

        # --- Observations ---
        obs_title=ParagraphStyle(
            "OT", fontName="Times-Bold", fontSize=12,
            alignment=TA_LEFT, leading=16,
            spaceBefore=16, spaceAfter=6,
        ),
        obs_body=ParagraphStyle(
            "OB", fontName="Times-Roman", fontSize=10,
            alignment=TA_JUSTIFY, leading=14,
            spaceAfter=10,
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
    canvas.setFont("Times-Roman", 9)
    canvas.drawCentredString(PAGE_W / 2, 12 * mm, str(canvas.getPageNumber()))
    canvas.restoreState()


def _title_page(st: dict) -> list:
    return [
        Spacer(1, 55 * mm),
        Paragraph(
            "THE KEPHALAIA<br/>OF THE TEACHER",
            st["main_title"],
        ),
        Spacer(1, 10 * mm),
        Paragraph("The Discovered Structure", st["subtitle"]),
        Spacer(1, 4 * mm),
        Paragraph(
            "The teaching substrate organized by its own internal logic",
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
            "Core teaching substrate organized by discovered structure.<br/>"
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


def _toc_page(st: dict, structure: dict) -> list:
    elements: list = [
        Spacer(1, 15 * mm),
        Paragraph("CONTENTS", st["section_title"]),
        Spacer(1, 6 * mm),
    ]

    for part in structure["parts"]:
        pn = part["part_number"]
        elements.append(
            Paragraph(
                f'Part {pn} &mdash; {_xml_esc(part["title"])}',
                st["toc_part"],
            )
        )
        for ch in structure["chapters"]:
            if ch["part_number"] == pn:
                elements.append(
                    Paragraph(_xml_esc(ch["title"]), st["toc_chapter"])
                )

    elements.append(Spacer(1, 12 * mm))
    elements.append(
        Paragraph("Structural Observations", st["toc_part"])
    )
    elements.append(PageBreak())
    return elements


def _part_page(st: dict, part: dict) -> list:
    return [
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
                "OI", fontName="Times-Italic", fontSize=10,
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

    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=25 * mm,
        rightMargin=25 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title="The Kephalaia of the Teacher \u2014 The Discovered Structure",
        author="Manichaean Analysis Project",
    )

    elements: list = []

    # ---- Title page ----
    elements.extend(_title_page(st))

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

    # ---- Observations ----
    elements.extend(_render_observations(st, observations))

    # Build
    print(f"\n  Building PDF ({len(elements)} flowables) ...")
    doc.build(elements, onLaterPages=_page_footer)

    size_kb = OUTPUT.stat().st_size / 1024
    print(f"  Saved to {OUTPUT}")
    print(f"  Size: {size_kb:,.0f} KB")


def main():
    if not STRUCTURE_FILE.exists():
        import sys
        sys.exit(f"Structure file not found: {STRUCTURE_FILE}")

    build_pdf()
    print("\nDone.")


if __name__ == "__main__":
    main()
