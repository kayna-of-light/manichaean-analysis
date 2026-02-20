#!/usr/bin/env python3
"""
Generate a structured book PDF of the Kephalaia of the Teacher.

Uses the discovered structure from compose_structure.py to organize
the teaching substrate (core text) and spiritual translations
(correspondential readings) into a coherent book.

The structure was discovered by Claude Opus 4.6 reading the entire
corpus without access to manuscript chapter divisions — only sequential
§-markers.  The resulting 12-part, ~30-chapter organization reflects
the text's own internal logic.

Dependencies: reportlab  (available in conda env 'manichaean')

Usage:
    conda run -n manichaean python scripts/tools/generate_book_pdf.py
"""

import json
import re
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
CORR_DIR = KEPH_DIR / "correspondential" / "chapters"
OUTPUT = PROJECT_ROOT / "output" / "pdfs" / "Kephalaia_Book.pdf"

PAGE_W, PAGE_H = A4

LACUNA_GRAY = "#999999"
RULE_COLOR = "#CCCCCC"
NOTE_COLOR = "#555555"
MUTED = "#888888"
DARK_MUTED = "#666666"
SR_COLOR = "#333333"

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
    # [GAP-N: REVIEW — ...] → [...]
    text = re.sub(r"\[GAP-\d+:\s*REVIEW\s*[—–-].*?\]", "[...]", text)
    # [GAP-N: text] → [text]
    text = re.sub(r"\[GAP-\d+:\s*(.+?)\]", r"[\1]", text)
    # [GAP-N] → [...]
    text = re.sub(r"\[GAP-\d+\]", "[...]", text)
    return text


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


def _render_sr_inline(text: str) -> str:
    """Convert inline markdown + lacunae in spiritual-reading text to XML."""
    text = _clean_gap_markers(text)
    text = _xml_esc(text)
    # Bold: **text**
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    # Italic: *text*
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    # Lacunae in gray
    text = re.sub(
        r"\[([^\]]*)\]",
        lambda m: f'<font color="{LACUNA_GRAY}">[{m.group(1)}]</font>',
        text,
    )
    return text


def _clean_core_text(text: str) -> str:
    """Strip manuscript page markers and leading paragraph numbers."""
    # Remove ⟨p.N⟩ prefix (and whitespace/newline after)
    text = re.sub(r"⟨p\.\d+⟩\s*", "", text)
    # Remove leading (N) at start of text
    text = re.sub(r"^\(\d+\)\s*", "", text)
    # Collapse multiple newlines to single space
    text = re.sub(r"\n+", " ", text)
    return text.strip()


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

        # --- Manuscript-chapter sub-headings ---
        ms_heading=ParagraphStyle(
            "MSH", fontName="Times-Bold", fontSize=10.5,
            alignment=TA_LEFT, leading=14,
            spaceBefore=16, spaceAfter=8,
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

        # --- Spiritual reading ---
        sr_heading=ParagraphStyle(
            "SRH", fontName="Times-Italic", fontSize=11,
            alignment=TA_CENTER, leading=15,
            spaceBefore=12, spaceAfter=8,
            textColor=HexColor(SR_COLOR),
        ),
        sr_subheading=ParagraphStyle(
            "SRSH", fontName="Times-Italic", fontSize=10,
            alignment=TA_CENTER, leading=14,
            spaceBefore=8, spaceAfter=6,
            textColor=HexColor(NOTE_COLOR),
        ),
        sr_body=ParagraphStyle(
            "SRB", fontName="Times-Roman", fontSize=10,
            alignment=TA_JUSTIFY, leading=14,
            spaceAfter=6, leftIndent=6 * mm, rightIndent=6 * mm,
            textColor=HexColor(SR_COLOR),
        ),
        sr_para_ref=ParagraphStyle(
            "SRP", fontName="Times-Bold", fontSize=9,
            alignment=TA_LEFT, leading=12,
            spaceAfter=2, leftIndent=6 * mm,
            textColor=HexColor(DARK_MUTED),
        ),
        sr_note=ParagraphStyle(
            "SRN", fontName="Times-Italic", fontSize=9,
            alignment=TA_JUSTIFY, leading=13,
            spaceAfter=6, leftIndent=10 * mm, rightIndent=10 * mm,
            textColor=HexColor("#777777"),
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


def load_core_chapter(ms_ch: int) -> dict | None:
    path = CORE_DIR / f"ch_{ms_ch:03d}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_corr_chapter(ms_ch: int) -> dict | None:
    path = CORR_DIR / f"ch_{ms_ch:03d}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Mapping: structural chapters ↔ manuscript chapters
# ---------------------------------------------------------------------------


def build_ms_chapter_assignment(structure: dict) -> dict[int, int]:
    """Map each ms_chapter → structural-chapter index.

    A ms_chapter is assigned to the structural chapter whose §-range
    contains the ms_chapter's section_start.  Empty ms_chapters
    (section_start > section_end) are silently skipped.
    """
    section_map = structure["_section_map"]
    chapters = structure["chapters"]
    assignment: dict[int, int] = {}

    for ms_entry in section_map:
        ms_ch = ms_entry["ms_chapter"]
        s_start = ms_entry["section_start"]
        s_end = ms_entry["section_end"]

        # Skip empty / fragmentary chapters
        if s_start > s_end:
            continue

        for ch_idx, ch in enumerate(chapters):
            if ch["section_start"] <= s_start <= ch["section_end"]:
                assignment[ms_ch] = ch_idx
                break

    return assignment


def group_by_structural_chapter(
    assignment: dict[int, int],
) -> dict[int, list[int]]:
    """For each structural-chapter index, list ms_chapters (sorted)."""
    result: dict[int, list[int]] = {}
    for ms_ch, ch_idx in sorted(assignment.items()):
        result.setdefault(ch_idx, []).append(ms_ch)
    return result


# ---------------------------------------------------------------------------
# Spiritual-reading parser
# ---------------------------------------------------------------------------


def parse_spiritual_reading(sr_text: str) -> list[dict]:
    """Parse the spiritual_reading markdown into renderable blocks.

    Handles three known formats:
      1. **¶N:** text on same line           (ch_000-style)
      2. ## ¶N  then text on following lines  (ch_001-style)
      3. **¶N** alone, text on following lines (ch_005/$prose-style)

    Returns list of dicts:
        type: 'heading' | 'para_ref' | 'body' | 'note' | 'rule'
        text: content
    """
    if not sr_text:
        return []

    blocks: list[dict] = []
    lines = sr_text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # --- Main heading: # Spiritual Translation[: Subtitle] ---
        if stripped.startswith("# ") and not stripped.startswith("## "):
            heading = stripped[2:].strip()
            if ":" in heading:
                subtitle = heading.split(":", 1)[1].strip()
                if subtitle:
                    blocks.append({"type": "heading", "text": subtitle})
            i += 1
            continue

        # --- Sub-heading: ## ¶N  or  ## Title ---
        if stripped.startswith("## "):
            h = stripped[3:].strip()
            if re.match(r"¶\d+", h):
                blocks.append({"type": "para_ref", "text": h})
            else:
                blocks.append({"type": "heading", "text": h})
            i += 1
            continue

        # --- Horizontal rule ---
        if stripped == "---":
            blocks.append({"type": "rule", "text": ""})
            i += 1
            continue

        # --- Bold paragraph marker on its own line: **¶N** ---
        m_solo = re.match(r"^\*\*¶(\d+)\*\*\s*$", stripped)
        if m_solo:
            blocks.append({"type": "para_ref", "text": f"¶{m_solo.group(1)}"})
            i += 1
            continue

        # --- Bold paragraph marker with inline text: **¶N:** text ---
        m_inline = re.match(r"^\*\*¶(\d+):\*\*\s*(.*)", stripped)
        if m_inline:
            para_num = m_inline.group(1)
            rest = m_inline.group(2).strip()
            blocks.append({"type": "para_ref", "text": f"¶{para_num}"})
            # Collect body text (rest of this line + continuation lines)
            body_parts = []
            if rest:
                body_parts.append(rest)
            i += 1
            while i < len(lines):
                s = lines[i].strip()
                if not s:
                    break
                if s.startswith("#") or s == "---":
                    break
                if re.match(r"^\*\*¶\d+", s):
                    break
                if s.startswith("*") and not s.startswith("**"):
                    break
                body_parts.append(s)
                i += 1
            if body_parts:
                blocks.append({"type": "body", "text": " ".join(body_parts)})
            continue

        # --- Translator note: *text* ---
        if stripped.startswith("*") and not stripped.startswith("**"):
            note_lines = [stripped]
            i += 1
            while i < len(lines):
                s = lines[i].strip()
                if not s or s.startswith("#") or s == "---":
                    break
                if re.match(r"^\*\*¶\d+", s):
                    break
                note_lines.append(s)
                i += 1
            note_text = " ".join(note_lines)
            # Strip enclosing *...*
            note_text = re.sub(r"^\*+\s*", "", note_text)
            note_text = re.sub(r"\s*\*+$", "", note_text)
            blocks.append({"type": "note", "text": note_text})
            continue

        # --- Regular body paragraph ---
        para_lines = [stripped]
        i += 1
        while i < len(lines):
            s = lines[i].strip()
            if not s:
                break
            if s.startswith("#") or s == "---":
                break
            if re.match(r"^\*\*¶\d+", s):
                break
            if s.startswith("*") and not s.startswith("**"):
                break
            para_lines.append(s)
            i += 1
        blocks.append({"type": "body", "text": " ".join(para_lines)})

    return blocks


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
            "Core teaching substrate with correspondential translations.<br/>"
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


def _build_reconstruction_map(corr_data: dict | None) -> dict[int, str]:
    """Build paragraph_number → reconstructed_text from correspondential data."""
    if not corr_data:
        return {}
    recons = corr_data.get("reconstructions", [])
    return {
        r["paragraph"]: r["reconstructed_text"]
        for r in recons
        if r.get("reconstructed_text")
    }


def _render_core_paragraphs(
    st: dict, core_data: dict, corr_data: dict | None,
) -> list:
    """Render text paragraphs from a manuscript chapter.

    Uses reconstructed (gap-filled) text from the correspondential file
    when available, falling back to raw core_text only for paragraphs
    without a reconstruction or chapters without a correspondential file.
    """
    elements: list = []

    if not core_data or "paragraphs" not in core_data:
        return elements

    core_paras = [
        p for p in core_data["paragraphs"]
        if p.get("classification") in ("core", "mixed")
    ]

    if not core_paras:
        return elements

    recon_map = _build_reconstruction_map(corr_data)

    for idx, para in enumerate(core_paras):
        pnum = para.get("paragraph_number")

        # Prefer reconstructed text
        text = recon_map.get(pnum, "")
        if not text:
            text = para.get("core_text", "")
        if not text:
            continue

        text = _clean_core_text(text)
        if not text:
            continue

        styled = _style_lacunae(text)
        style = st["body_first"] if idx == 0 else st["body"]
        try:
            elements.append(Paragraph(styled, style))
        except Exception as exc:
            print(f"  WARNING: skipped paragraph ({exc})")

    return elements


def _render_spiritual_reading(st: dict, corr_data: dict) -> list:
    """Render the spiritual translation for a manuscript chapter."""
    elements: list = []

    if not corr_data:
        return elements

    sr_text = corr_data.get("spiritual_reading", "")
    if not sr_text:
        return elements

    # Separator + heading
    elements.append(Spacer(1, 4 * mm))
    elements.append(
        HRFlowable(
            width="30%", thickness=0.5,
            color=HexColor(RULE_COLOR),
            spaceAfter=4 * mm, spaceBefore=0,
        )
    )
    elements.append(
        Paragraph("Spiritual Translation", st["sr_heading"])
    )

    blocks = parse_spiritual_reading(sr_text)

    for block in blocks:
        btype = block["type"]
        text = block["text"]

        if btype == "heading":
            elements.append(
                Paragraph(_render_sr_inline(text), st["sr_subheading"])
            )

        elif btype == "para_ref":
            elements.append(
                Paragraph(_xml_esc(text), st["sr_para_ref"])
            )

        elif btype == "body":
            styled = _render_sr_inline(text)
            try:
                elements.append(Paragraph(styled, st["sr_body"]))
            except Exception as exc:
                print(f"  WARNING: skipped SR paragraph ({exc})")

        elif btype == "note":
            elements.append(Spacer(1, 2 * mm))
            styled = _render_sr_inline(text)
            try:
                elements.append(Paragraph(styled, st["sr_note"]))
            except Exception as exc:
                print(f"  WARNING: skipped SR note ({exc})")

        elif btype == "rule":
            pass  # Skip internal rules — they just separate paragraphs

    return elements


def _render_chapter(
    st: dict,
    ch: dict,
    ms_chapters: list[int],
) -> list:
    """Render a full structural chapter (heading + ms_chapters content)."""
    elements: list = []

    # --- Chapter heading ---
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

    # --- Render each manuscript chapter ---
    show_ms_heading = len(ms_chapters) > 1

    for ms_ch in ms_chapters:
        core_data = load_core_chapter(ms_ch)
        corr_data = load_corr_chapter(ms_ch)

        # Manuscript chapter sub-heading (only when multiple in one chapter)
        if show_ms_heading and core_data:
            title = core_data.get("chapter_title", "")
            label = f"Chapter {ms_ch}"
            if title and title.lower() not in ("", f"chapter {ms_ch}"):
                label += f" \u2014 {title}"
            elements.append(
                Paragraph(_xml_esc(label), st["ms_heading"])
            )

        # Core text (using reconstructed/repaired text when available)
        core_elems = _render_core_paragraphs(st, core_data, corr_data)
        if core_elems:
            elements.extend(core_elems)

        # Spiritual reading
        sr_elems = _render_spiritual_reading(st, corr_data)
        if sr_elems:
            elements.extend(sr_elems)

        # Spacer between ms chapters within a structural chapter
        if show_ms_heading:
            elements.append(Spacer(1, 8 * mm))

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

    # Build the ms_chapter → structural-chapter mapping
    assignment = build_ms_chapter_assignment(structure)
    ch_to_ms = group_by_structural_chapter(assignment)

    assigned_ms = sum(len(v) for v in ch_to_ms.values())
    print(f"  {assigned_ms} manuscript chapters assigned")

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

        # Chapter content
        ms_chs = ch_to_ms.get(ch_idx, [])
        if not ms_chs:
            print(f"  WARNING: structural chapter {ch_idx} has no ms chapters")

        readable = ch["title"][:60]
        print(f"  Ch {ch_idx}: \"{readable}\" — {len(ms_chs)} ms ch(s)")
        elements.extend(_render_chapter(st, ch, ms_chs))

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
