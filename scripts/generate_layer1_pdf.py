#!/usr/bin/env python3
"""
Generate a styled PDF of the Kephalaia Layer 1 Extract.

Reads the markdown document and produces a clean reading PDF with
chapter headings, italic contextual notes, and body text with
lacunae markers rendered in light gray.

Dependencies: reportlab  (available in conda env 'manichaean')

Usage:
    conda run -n manichaean python scripts/generate_layer1_pdf.py
"""

import re
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, HRFlowable,
)
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.colors import HexColor

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
SOURCE = PROJECT_ROOT / "output" / "Kephalaia_Layer_1_Extract.md"
OUTPUT = PROJECT_ROOT / "output" / "pdfs" / "Kephalaia_Layer_1_Extract.pdf"

LACUNA_GRAY = "#999999"
RULE_COLOR = "#CCCCCC"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _xml_esc(text: str) -> str:
    """Escape XML entities."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _style_lacunae(text: str) -> str:
    """Escape text for XML and render [...] apparatus in gray."""
    text = _xml_esc(text)

    def _style_bracket(m: re.Match) -> str:
        inner = m.group(0)[1:-1]

        def _black_if_visible(m2: re.Match) -> str:
            seg = m2.group(0)
            if seg.strip():
                return f'<font color="#000000">{seg}</font>'
            return seg

        styled = re.sub(r"[^.]+", _black_if_visible, inner)
        return f'<font color="{LACUNA_GRAY}">[{styled}]</font>'

    return re.sub(r"\[[^\]]*\]", _style_bracket, text)


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------


def _styles() -> dict:
    return dict(
        main_title=ParagraphStyle(
            "MT", fontName="Times-Bold", fontSize=22,
            alignment=TA_CENTER, leading=28, spaceAfter=8,
        ),
        subtitle=ParagraphStyle(
            "ST", fontName="Times-Italic", fontSize=13,
            alignment=TA_CENTER, leading=17, spaceAfter=6,
        ),
        credit=ParagraphStyle(
            "CR", fontName="Times-Roman", fontSize=10,
            alignment=TA_CENTER, leading=14, spaceAfter=6,
            textColor="#666666",
        ),
        intro_body=ParagraphStyle(
            "IB", fontName="Times-Roman", fontSize=10,
            alignment=TA_JUSTIFY, leading=14,
            spaceAfter=6, leftIndent=12 * mm, rightIndent=12 * mm,
            textColor="#444444",
        ),
        chapter=ParagraphStyle(
            "CH", fontName="Times-Bold", fontSize=13,
            alignment=TA_CENTER, leading=17,
            spaceBefore=24, spaceAfter=6,
        ),
        chapter_ref=ParagraphStyle(
            "CHREF", fontName="Times-Roman", fontSize=9,
            alignment=TA_CENTER, leading=12,
            spaceAfter=12, textColor="#888888",
        ),
        context=ParagraphStyle(
            "CTX", fontName="Times-Italic", fontSize=10,
            alignment=TA_JUSTIFY, leading=14,
            spaceAfter=12, leftIndent=6 * mm, rightIndent=6 * mm,
            textColor="#555555",
        ),
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
    )


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_markdown(text: str) -> list[dict]:
    """Parse the Layer 1 Extract markdown into structured blocks.

    Returns a list of dicts with keys:
        type: 'header' | 'chapter' | 'context' | 'rule' | 'paragraph' | 'complete'
        text: the content
    """
    blocks: list[dict] = []
    lines = text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            i += 1
            continue

        # Document complete marker
        if stripped.startswith("*[Document complete"):
            blocks.append({"type": "complete", "text": ""})
            i += 1
            continue

        # Document continues marker (skip)
        if stripped.startswith("*[Document continues"):
            i += 1
            continue

        # Main title (# heading)
        if stripped.startswith("# ") and not stripped.startswith("## "):
            blocks.append({"type": "main_title", "text": stripped[2:].strip()})
            i += 1
            continue

        # Chapter heading (## heading)
        if stripped.startswith("## "):
            # Parse: ## Chapter NN — Title (K.xxx–yyy)
            heading = stripped[3:].strip()
            blocks.append({"type": "chapter", "text": heading})
            i += 1
            continue

        # Horizontal rule
        if stripped == "---":
            blocks.append({"type": "rule", "text": ""})
            i += 1
            continue

        # Italic context note (*text*)
        if stripped.startswith("*") and stripped.endswith("*") and not stripped.startswith("**"):
            ctx = stripped.strip("*").strip()
            blocks.append({"type": "context", "text": ctx})
            i += 1
            continue

        # Regular paragraph — collect until blank line
        para_lines = []
        while i < len(lines):
            ln = lines[i]
            s = ln.strip()
            if not s:
                break
            if s.startswith("## ") or s == "---" or s.startswith("# "):
                break
            if s.startswith("*[Document"):
                break
            if s.startswith("*") and s.endswith("*") and not s.startswith("**") and len(para_lines) == 0:
                break
            para_lines.append(s)
            i += 1

        if para_lines:
            blocks.append({"type": "paragraph", "text": " ".join(para_lines)})
        else:
            i += 1

    return blocks


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------


def _page_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Times-Roman", 9)
    canvas.drawCentredString(A4[0] / 2, 12 * mm, str(canvas.getPageNumber()))
    canvas.restoreState()


def _title_page(st: dict) -> list:
    return [
        Spacer(1, 60 * mm),
        Paragraph(
            "THE KEPHALAIA<br/>OF THE TEACHER",
            st["main_title"],
        ),
        Spacer(1, 8 * mm),
        Paragraph("Layer 1 Extract", st["subtitle"]),
        Spacer(1, 6 * mm),
        Paragraph(
            "The Correspondential Substrate",
            ParagraphStyle(
                "ST2", fontName="Times-Italic", fontSize=11,
                alignment=TA_CENTER, leading=15, spaceAfter=6,
                textColor="#777777",
            ),
        ),
        Spacer(1, 20 * mm),
        Paragraph(
            "Based on the translation by Iain Gardner (1995)<br/>"
            "<i>The Kephalaia of the Teacher: The Edited Coptic<br/>"
            "Manichaean Texts in Translation with Commentary</i>",
            st["credit"],
        ),
        Spacer(1, 10 * mm),
        Paragraph(
            "Verbatim passages preserving Layer 1 content:<br/>"
            "the correspondential and cosmological teaching substrate.<br/>"
            "Layers 2 (Pauline theological frame) and 3 (hagiographic frame) removed.<br/>"
            f'Lacunae markers shown in <font color="{LACUNA_GRAY}">light gray</font>.',
            st["credit"],
        ),
        PageBreak(),
    ]


def build_pdf(blocks: list[dict]):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    st = _styles()

    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=25 * mm,
        rightMargin=25 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title="The Kephalaia of the Teacher — Layer 1 Extract",
        author="Layer 1 Extraction",
    )

    elements: list = _title_page(st)

    first_in_chapter = True
    in_intro = True  # before the first chapter heading

    for block in blocks:
        btype = block["type"]
        text = block["text"]

        if btype == "main_title":
            # Skip — handled in title page
            continue

        elif btype == "chapter":
            in_intro = False
            first_in_chapter = True
            # Parse chapter heading
            # Format: "Chapter NN — Title (K.xxx–yyy)"
            m = re.match(
                r"Chapter\s+(\d+)\s*[—–-]\s*(.*?)(?:\s*\(K\.\s*[\d–\-,\s]+\))?\s*$",
                text,
            )
            if m:
                ch_num = m.group(1)
                ch_title = m.group(2).strip()
                # Extract K reference
                k_match = re.search(r"\(K\.\s*([\d–\-,\s]+)\)", text)
                k_ref = k_match.group(1).strip() if k_match else ""

                heading_xml = _xml_esc(f"Chapter {ch_num}")
                if ch_title:
                    heading_xml += f'<br/><font size="10"><i>{_xml_esc(ch_title)}</i></font>'
                elements.append(Paragraph(heading_xml, st["chapter"]))
                if k_ref:
                    elements.append(
                        Paragraph(f"K. {_xml_esc(k_ref)}", st["chapter_ref"])
                    )
            else:
                elements.append(Paragraph(_xml_esc(text), st["chapter"]))

        elif btype == "context":
            styled = _style_lacunae(text)
            elements.append(Paragraph(styled, st["context"]))

        elif btype == "rule":
            if not in_intro:
                elements.append(Spacer(1, 4 * mm))
                elements.append(
                    HRFlowable(
                        width="30%",
                        thickness=0.5,
                        color=HexColor(RULE_COLOR),
                        spaceAfter=4 * mm,
                        spaceBefore=0,
                    )
                )

        elif btype == "paragraph":
            if in_intro:
                # Intro paragraphs before first chapter
                styled = _style_lacunae(text)
                elements.append(Paragraph(styled, st["intro_body"]))
            else:
                styled = _style_lacunae(text)
                style = st["body_first"] if first_in_chapter else st["body"]
                try:
                    elements.append(Paragraph(styled, style))
                except Exception as exc:
                    print(f"  WARNING: skipped paragraph ({exc})")
                first_in_chapter = False

        elif btype == "complete":
            pass

    print(f"  Building PDF ({len(elements)} flowables) ...")
    doc.build(elements, onLaterPages=_page_footer)
    print(f"  Saved to {OUTPUT}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    if not SOURCE.exists():
        import sys
        sys.exit(f"Source not found: {SOURCE}")

    print(f"Reading {SOURCE.name} ...")
    src = SOURCE.read_text(encoding="utf-8")
    print(f"  {len(src):,} chars  ·  {src.count(chr(10)):,} lines")

    print("Parsing blocks ...")
    blocks = parse_markdown(src)
    print(f"  Found {len(blocks)} blocks")

    # Summary
    types = {}
    for b in blocks:
        types[b["type"]] = types.get(b["type"], 0) + 1
    for t, c in sorted(types.items()):
        print(f"    {t}: {c}")

    print("Generating PDF ...")
    build_pdf(blocks)
    print("Done.")


if __name__ == "__main__":
    main()
