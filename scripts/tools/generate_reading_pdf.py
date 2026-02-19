#!/usr/bin/env python3
"""
Generate a clean reading edition PDF of the Kephalaia of the Teacher.

Strips Gardner's scholarly commentary, footnotes, page markers, line numbers,
and manuscript apparatus.  Keeps only the original translated text with
chapter headings.  Lacunae markers ([...]) are rendered in light gray.

Dependencies: reportlab  (available in conda env 'manichaean')

Usage:
    conda run -n manichaean python scripts/generate_reading_pdf.py
"""

import re
import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
SOURCE = PROJECT_ROOT / "output" / "texts" / "Kephalaia_of_the_Teacher.md"
OUTPUT = PROJECT_ROOT / "output" / "pdfs" / "Kephalaia_Reading_Edition.pdf"

LACUNA_GRAY = "#999999"

# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------


def is_chapter_marker(line: str) -> bool:
    """Return True if *line* is a chapter divider (e.g. ··· 16 ···)."""
    s = line.strip()
    if len(s) > 80 or len(s) < 3:
        return False
    if "[" in s or "]" in s:          # original text, not a marker
        return False
    if not re.match(r"^[·.]{2,}", s):
        return False
    if "Introduction" in s:
        return True
    # ··· . ··· is Chapter 1  (OCR renders '1' as '.')
    if re.match(r"^[·.]{2,}\s*\.\s*[·.]*$", s):
        return True
    if re.search(r"\b\d{1,3}\b", s):
        return True
    return False


def chapter_id(line: str) -> str:
    """Extract the chapter number / label from a marker line."""
    s = line.strip()
    if "Introduction" in s:
        return "Introduction"
    if re.match(r"^[·.]{2,}\s*\.\s*[·.]*$", s):
        return "1"
    m = re.search(r"\b(\d{1,3})\b", s)
    return m.group(1) if m else "?"


def _is_meta(line: str) -> bool:
    """True for print-page headers, standalone page numbers, rules, footnotes."""
    s = line.strip()
    if not s:
        return False
    if s == "---":
        return True
    if s == "THE KEPHALAIA OF THE TEACHER":
        return True
    if re.match(r"^CHAPTER\s+", s):
        return True
    if re.match(r"^\d{1,3}$", s):               # standalone print page no.
        return True
    if re.match(r"^\*\d+", s):                   # footnote definition
        return True
    return False


def _has_text_markers(paragraph: str) -> bool:
    """True when *paragraph* contains manuscript artefacts typical of the
    original translated text (lacunae, line-break slashes, ms-page numbers)."""
    if re.search(r"\[[\s./·]*\.{3}", paragraph):        # lacuna
        return True
    if re.search(r"\w\s*/\s*\w", paragraph):            # line-break slash
        return True
    for m in re.finditer(r"\((\d{1,3})\)", paragraph):  # ms-page (NN)
        if 1 <= int(m.group(1)) <= 295:
            return True
    return False


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _extract_title(lines: list[str]) -> tuple[str, list[str]]:
    """Pull out the chapter title (/ delimited) from the first few lines.

    Returns (title_text, remaining_lines).
    """
    title_parts: list[str] = []
    consumed = 0

    for i, raw in enumerate(lines):
        s = raw.strip()

        # skip blanks, page-ranges, metadata
        if not s or re.match(r"^\(?\s*\d+\s*,", s) or _is_meta(s):
            consumed = i + 1
            continue

        # title lines start with /
        if s.startswith("/"):
            t = s.strip("/ ").strip()
            t = re.sub(r"\b(?:5|10|15|20|25|30|35)\b", "", t)   # line nums
            t = t.replace("/", " ")
            t = re.sub(r"\s{2,}", " ", t).strip()
            if t:
                title_parts.append(t)
            consumed = i + 1
            if s.rstrip().endswith((".", "/")):
                break
        elif title_parts:
            break                    # title ended
        elif i > 12:
            break                    # too far without finding title

    title = " ".join(title_parts)
    title = re.sub(r"\s{2,}", " ", title).strip()
    return title, lines[consumed:]


def _split_commentary(lines: list[str]) -> list[str]:
    """Return only the original-text lines, skipping Gardner's commentary
    that sits at the head of each chapter section."""

    # group into paragraphs (blank-line separated)
    paragraphs: list[list[str]] = []
    buf: list[str] = []
    for line in lines:
        if line.strip() and not _is_meta(line):
            buf.append(line)
        else:
            if buf:
                paragraphs.append(buf)
                buf = []
    if buf:
        paragraphs.append(buf)
    if not paragraphs:
        return []

    # first paragraph with text markers = start of original text
    text_start = 0
    for i, para in enumerate(paragraphs):
        joined = " ".join(l.strip() for l in para)
        if _has_text_markers(joined):
            text_start = i
            break
    else:
        text_start = 0                # no clear markers → keep everything

    result: list[str] = []
    for para in paragraphs[text_start:]:
        result.extend(para)
        result.append("")              # paragraph break
    return result


def parse(source: str) -> list[tuple[str, str, list[str]]]:
    """Parse the full markdown into (chapter_id, title, text_lines) tuples."""

    # cut off at INDICES / back matter (the concordance starts before the
    # INDICES header with "THE LIGHT AND THE DARKNESS")
    for pattern in (
        r"^THE LIGHT AND THE DARKNESS\s*$",
        r"^INDICES\s*$",
    ):
        m = re.search(pattern, source, re.MULTILINE)
        if m:
            source = source[: m.start()]
            break

    lines = source.split("\n")
    markers = [i for i, l in enumerate(lines) if is_chapter_marker(l)]
    if not markers:
        sys.exit("ERROR: no chapter markers found")

    chapters: list[tuple[str, str, list[str]]] = []
    for idx, start in enumerate(markers):
        cid = chapter_id(lines[start])
        end = markers[idx + 1] if idx + 1 < len(markers) else len(lines)
        section = lines[start + 1 : end]
        title, remaining = _extract_title(section)
        text_lines = _split_commentary(remaining)
        chapters.append((cid, title, text_lines))

    return chapters


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------


def _clean_line(line: str) -> str:
    """Clean one line of original text."""
    s = line.strip()
    if _is_meta(s) or not s:
        return ""

    # normalise lacunae: [ ... / ... ] → [...]
    s = re.sub(r"\[[\s./·]*\.{2,}[\s./·]*\]", "[...]", s)

    # remove ms-page numbers (NN)
    s = re.sub(r"\(\d{1,3}\)", "", s)

    # remove inline footnote markers  *NN
    s = re.sub(r"\*\d+", "", s)

    # remove empty parens () and OCR braces {}
    s = s.replace("()", "").replace("{}", "")

    # mid-word line-break join:  pr/eaching → preaching
    s = re.sub(r"(\w)/(\w)", r"\1\2", s)

    # remaining slashes → space
    s = re.sub(r"\s*/\s*", " ", s)

    # embedded ms line numbers  (5 10 15 20 25 30 35)
    s = re.sub(r"(?<=\s)(?:5|10|15|20|25|30|35)(?=\s)", "", s)
    s = re.sub(r"^(?:5|10|15|20|25|30|35)\s+", "", s)

    # OCR degree variants  1º → 10  etc.
    s = re.sub(r"(?<=\s)\dº(?=\s)", "", s)

    # tidy whitespace
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s


def _clean_paragraph(lines: list[str]) -> str:
    """Join and clean a paragraph of text lines."""
    cleaned = [c for l in lines if (c := _clean_line(l))]
    if not cleaned:
        return ""
    text = " ".join(cleaned)
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)   # space before punctuation
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------


def _xml_esc(text: str) -> str:
    """Escape XML entities (but NOT our own <font> tags)."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _style_lacunae(text: str) -> str:
    """Escape text for XML and render bracket/dot apparatus in gray,
    while keeping any letters inside brackets in normal colour.

    Strategy: wrap the entire [...] in a gray <font> tag, then
    override non-dot runs that contain visible characters back to
    black with a nested <font> tag.  This keeps spaces inside the
    gray outer tag, avoiding tag-boundary rendering artefacts."""
    text = _xml_esc(text)

    def _style_bracket(m: re.Match) -> str:
        inner = m.group(0)[1:-1]            # strip [ and ]

        def _black_if_visible(m2: re.Match) -> str:
            seg = m2.group(0)
            if seg.strip():                 # has letters / punctuation
                return f'<font color="#000000">{seg}</font>'
            return seg                      # pure whitespace → stays gray

        styled = re.sub(r"[^.]+", _black_if_visible, inner)
        return f'<font color="{LACUNA_GRAY}">[{styled}]</font>'

    return re.sub(r"\[[^\]]*\]", _style_bracket, text)


def _styles() -> dict:
    """Build the paragraph style dictionary."""
    return dict(
        title=ParagraphStyle(
            "T", fontName="Times-Bold", fontSize=22,
            alignment=TA_CENTER, leading=28, spaceAfter=12,
        ),
        subtitle=ParagraphStyle(
            "ST", fontName="Times-Italic", fontSize=14,
            alignment=TA_CENTER, leading=18, spaceAfter=8,
        ),
        credit=ParagraphStyle(
            "CR", fontName="Times-Roman", fontSize=10,
            alignment=TA_CENTER, leading=14, spaceAfter=6,
            textColor="#666666",
        ),
        chapter=ParagraphStyle(
            "CH", fontName="Times-Bold", fontSize=13,
            alignment=TA_CENTER, leading=17,
            spaceBefore=28, spaceAfter=16,
        ),
        body=ParagraphStyle(
            "B", fontName="Times-Roman", fontSize=10.5,
            alignment=TA_JUSTIFY, leading=14.5,
            spaceAfter=6, firstLineIndent=18,
        ),
        body1=ParagraphStyle(
            "B1", fontName="Times-Roman", fontSize=10.5,
            alignment=TA_JUSTIFY, leading=14.5,
            spaceAfter=6, firstLineIndent=0,
        ),
        frag=ParagraphStyle(
            "FR", fontName="Times-Italic", fontSize=9,
            alignment=TA_CENTER, leading=12,
            spaceAfter=6, textColor="#888888",
        ),
    )


def _page_footer(canvas, doc):
    """Draw a centered page number at the bottom of each page."""
    canvas.saveState()
    canvas.setFont("Times-Roman", 9)
    canvas.drawCentredString(A4[0] / 2, 12 * mm, str(canvas.getPageNumber()))
    canvas.restoreState()


def _title_page(st: dict) -> list:
    """Build the title-page flowables."""
    return [
        Spacer(1, 80 * mm),
        Paragraph("THE KEPHALAIA<br/>OF THE TEACHER", st["title"]),
        Spacer(1, 10 * mm),
        Paragraph("A Reading Edition", st["subtitle"]),
        Spacer(1, 15 * mm),
        Paragraph(
            "Based on the translation by Iain Gardner (1995)<br/>"
            "<i>The Kephalaia of the Teacher: The Edited Coptic<br/>"
            "Manichaean Texts in Translation with Commentary</i>",
            st["credit"],
        ),
        Spacer(1, 30 * mm),
        Paragraph(
            "Commentary, footnotes, and manuscript apparatus removed.<br/>"
            f'Lacunae markers shown in <font color="{LACUNA_GRAY}">light gray</font>.',
            st["credit"],
        ),
        PageBreak(),
    ]


def _chapter_elements(
    cid: str, title: str, text_lines: list[str], st: dict
) -> list:
    """Build PDF flowables for one chapter."""
    els: list = []

    # ---- heading ----
    if cid == "Introduction":
        heading = "Introduction"
    else:
        heading = f"Chapter {cid}"
        if title:
            heading += (
                f'<br/><font size="10"><i>{_xml_esc(title)}</i></font>'
            )
    els.append(Paragraph(heading, st["chapter"]))

    # ---- group text into paragraphs ----
    paragraphs: list[list[str]] = []
    buf: list[str] = []
    for line in text_lines:
        stripped = line.strip()
        if stripped and not _is_meta(stripped):
            buf.append(stripped)
        else:
            if buf:
                paragraphs.append(buf)
                buf = []
    if buf:
        paragraphs.append(buf)

    # ---- render each paragraph ----
    first = True
    for para_lines in paragraphs:
        text = _clean_paragraph(para_lines)
        if not text or len(text) < 4:
            continue
        styled = _style_lacunae(text)
        try:
            els.append(Paragraph(styled, st["body1"] if first else st["body"]))
            first = False
        except Exception as exc:
            print(f"  WARNING  Ch {cid}: skipped paragraph ({exc})")

    # if chapter produced no body text, note that it is too fragmentary
    if first:
        els.append(
            Paragraph("(text too fragmentary to reproduce)", st["frag"])
        )

    return els


def build_pdf(chapters: list[tuple[str, str, list[str]]]):
    """Compose and write the full PDF."""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    st = _styles()

    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=25 * mm,
        rightMargin=25 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title="The Kephalaia of the Teacher — A Reading Edition",
        author="Iain Gardner (trans.)",
    )

    elements: list = _title_page(st)
    for cid, title, tlines in chapters:
        elements.extend(_chapter_elements(cid, title, tlines, st))

    print(f"  Building PDF ({len(elements)} flowables) ...")
    doc.build(elements, onLaterPages=_page_footer)
    print(f"  Saved to {OUTPUT}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    if not SOURCE.exists():
        sys.exit(f"Source not found: {SOURCE}")

    print(f"Reading {SOURCE.name} ...")
    src = SOURCE.read_text(encoding="utf-8")
    print(f"  {len(src):,} chars  ·  {src.count(chr(10)):,} lines")

    print("Parsing chapters ...")
    chapters = parse(src)
    print(f"  Found {len(chapters)} chapters")

    for cid, title, _ in chapters[:5]:
        print(f"    {cid:>12s}  {title[:65]}")
    if len(chapters) > 5:
        print(f"    ... and {len(chapters) - 5} more")

    print("Generating PDF ...")
    build_pdf(chapters)
    print("Done.")


if __name__ == "__main__":
    main()
