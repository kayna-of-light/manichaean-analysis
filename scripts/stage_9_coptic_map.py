#!/usr/bin/env python3
"""
Build a paragraph -> Coptic map for Kephalaia core chapters.

Each paragraph is mapped to its specific Coptic lines, using:
- manuscript_pages metadata (e.g. "125,25 - 126,29") for chapter line ranges
- ⟨p.NNN⟩ markers in teaching_text for page transitions
- Proportional line distribution when multiple paragraphs share a page

Output:
- output/projects/kephalaia/coptic/mapping/ch_NNN.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from project_config import load_project


PAGE_MARKER_RE = re.compile(r"⟨p\.(\d+)⟩")
COPTIC_LINE_RE = re.compile(r"^(\d+)\s", re.MULTILINE)


def split_paragraphs(text: str) -> list[str]:
    """Match the existing extraction pipeline paragraph splitting."""
    parts = re.split(r"\n\s*\n|\n(?=⟨p\.\d+⟩)", text)
    return [part.strip() for part in parts if part.strip() and len(part.split()) >= 3]


def parse_manuscript_range(ms_pages: str) -> tuple[int, int, int, int]:
    """Parse manuscript_pages into (start_page, start_line, end_page, end_line).

    Handles formats:
      "125,25 - 126,29"  → (125, 25, 126, 29)
      "155,6-29"          → (155, 6, 155, 29)  single page
      "(166,17 - 30)"     → (166, 17, 166, 30) single page
      "283 - 284"         → (283, 1, 284, 99)  page-only
      "282,7 - ?"         → (282, 7, 282, 99)  incomplete

    Returns (0, 1, 0, 99) if unparseable.
    """
    cleaned = ms_pages.strip().strip("()")
    parts = cleaned.split("-")
    if len(parts) < 2:
        return (0, 1, 0, 99)

    left = parts[0].strip()
    right = parts[1].strip()

    # Parse left side (always has page)
    left_parts = left.split(",")
    start_page = int(left_parts[0].strip()) if left_parts[0].strip().isdigit() else 0
    start_line = 1
    if len(left_parts) > 1 and left_parts[1].strip().isdigit():
        start_line = int(left_parts[1].strip())

    # Parse right side — could be "page,line", "line-only", or "?"
    right_parts = right.split(",")
    if right_parts[0].strip() == "?" or not right_parts[0].strip():
        # Incomplete — assume same page
        return (start_page, start_line, start_page, 99)

    right_first = right_parts[0].strip()
    if not right_first.isdigit():
        return (start_page, start_line, start_page, 99)

    right_first_int = int(right_first)

    if len(right_parts) > 1 and right_parts[1].strip().isdigit():
        # Format: "page,line" on the right
        end_page = right_first_int
        end_line = int(right_parts[1].strip())
    elif right_first_int < start_page:
        # Right number is smaller than start page — it's a line number on the same page
        # e.g., "155,6-29" → end_line=29
        end_page = start_page
        end_line = right_first_int
    elif right_first_int <= 35:
        # Small number likely a line on same page (e.g. "166,17 - 30")
        end_page = start_page
        end_line = right_first_int
    else:
        # Larger number is a page (e.g. "283 - 284")
        end_page = right_first_int
        end_line = 99  # unknown, use all lines

    return (start_page, start_line, end_page, end_line)


def parse_manuscript_start_page(ms_pages: str, teaching_text: str) -> int:
    """Get the chapter start page."""
    sp, _, _, _ = parse_manuscript_range(ms_pages)
    if sp:
        return sp
    markers = PAGE_MARKER_RE.findall(teaching_text)
    if markers:
        return int(markers[0])
    return 0


def assign_pages_to_paragraphs(
    teaching_text: str,
    paragraphs: list[str],
    ms_pages: str,
) -> list[dict]:
    """Assign manuscript page(s) to each paragraph."""
    current_page = parse_manuscript_start_page(ms_pages, teaching_text)
    results: list[dict] = []

    for index, para in enumerate(paragraphs, start=1):
        marker_match = PAGE_MARKER_RE.match(para)
        if marker_match:
            current_page = int(marker_match.group(1))

        inner_markers = [int(marker) for marker in PAGE_MARKER_RE.findall(para)]
        pages = [current_page] if current_page else []
        for marker_page in inner_markers:
            if marker_page not in pages:
                pages.append(marker_page)

        results.append({
            "paragraph_number": index,
            "pages": pages,
            "word_count": len(para.split()),
        })

    return results


def parse_coptic_lines(coptic_text: str) -> list[tuple[int, str]]:
    """Parse a Coptic page transcription into [(line_number, coptic_text_only), ...].

    Line numbers are stripped; only the Coptic content (including lacunae
    markers, editorial notes, etc.) is kept.
    """
    result: list[tuple[int, str]] = []
    for line in coptic_text.split("\n"):
        m = re.match(r"^(\d+)\s(.*)$", line)
        if m:
            result.append((int(m.group(1)), m.group(2)))
    return result


def load_coptic_page(coptic_dir: Path, page_number: int) -> str | None:
    path = coptic_dir / f"keph_p{page_number:03d}_pass2.txt"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def get_max_line(coptic_text: str) -> int:
    """Get the highest numbered line in a Coptic page."""
    nums = [int(m) for m in COPTIC_LINE_RE.findall(coptic_text)]
    return max(nums) if nums else 35


def build_chapter_lines(
    coptic_dir: Path,
    start_page: int,
    start_line: int,
    end_page: int,
    end_line: int,
) -> list[tuple[int, int, str]]:
    """Build a flat ordered list of (page, line_num, line_text) for the whole chapter."""
    chapter_lines: list[tuple[int, int, str]] = []

    for pg in range(start_page, end_page + 1):
        coptic_text = load_coptic_page(coptic_dir, pg)
        if coptic_text is None:
            continue
        parsed = parse_coptic_lines(coptic_text)
        for line_num, line_text in parsed:
            # Apply chapter boundaries
            if pg == start_page and line_num < start_line:
                continue
            if pg == end_page and line_num > end_line:
                continue
            chapter_lines.append((pg, line_num, line_text))

    return chapter_lines


def map_chapter(cleaned_path: Path, coptic_dir: Path) -> dict | None:
    data = json.loads(cleaned_path.read_text(encoding="utf-8"))
    teaching_text = data.get("teaching_text", "")
    if not teaching_text.strip():
        return None

    ms_pages = data.get("manuscript_pages", "")
    start_page, start_line, end_page, end_line = parse_manuscript_range(ms_pages)

    paragraphs = split_paragraphs(teaching_text)
    if not paragraphs:
        return None

    # Build the flat list of all Coptic lines for this chapter
    chapter_lines = build_chapter_lines(coptic_dir, start_page, start_line, end_page, end_line)

    if not chapter_lines:
        # No Coptic available — still produce the map with null coptic_text
        mapped_paragraphs = []
        para_pages = assign_pages_to_paragraphs(teaching_text, paragraphs, ms_pages)
        for item in para_pages:
            mapped_paragraphs.append({
                "paragraph_number": item["paragraph_number"],
                "pages": item["pages"],
                "coptic_files": [],
                "coptic_text": None,
            })
        return {
            "chapter_number": data["chapter_number"],
            "source_core_file": f"ch_{data['chapter_number']:03d}.json",
            "paragraphs": mapped_paragraphs,
        }

    # Distribute chapter_lines proportionally among paragraphs by word count
    word_counts = [len(p.split()) for p in paragraphs]
    total_words = sum(word_counts) or 1
    total_lines = len(chapter_lines)

    mapped_paragraphs = []
    line_cursor = 0

    for idx, para in enumerate(paragraphs):
        para_num = idx + 1
        wc = word_counts[idx]

        if idx == len(paragraphs) - 1:
            # Last paragraph gets all remaining lines
            assigned = chapter_lines[line_cursor:]
        else:
            share = max(1, round(total_lines * wc / total_words))
            # Don't consume so many lines that the last paragraph gets nothing
            remaining_paras = len(paragraphs) - idx - 1
            max_take = max(1, len(chapter_lines) - line_cursor - remaining_paras)
            share = min(share, max_take)
            assigned = chapter_lines[line_cursor:line_cursor + share]
            line_cursor += share

        if assigned:
            # Determine pages and files
            pages_seen: list[int] = []
            for pg, _, _ in assigned:
                if pg not in pages_seen:
                    pages_seen.append(pg)
            coptic_files = [f"keph_p{pg:03d}_pass2.txt" for pg in pages_seen]

            # Group lines by page for output
            page_groups: dict[int, list[str]] = {}
            for pg, _, line_text in assigned:
                page_groups.setdefault(pg, []).append(line_text)

            coptic_parts = []
            for pg in pages_seen:
                coptic_parts.append("\n".join(page_groups[pg]))
            coptic_text = "\n\n--- PAGE BREAK ---\n\n".join(coptic_parts)
        else:
            pages_seen = []
            coptic_files = []
            coptic_text = None

        mapped_paragraphs.append({
            "paragraph_number": para_num,
            "pages": pages_seen,
            "coptic_files": coptic_files,
            "coptic_text": coptic_text,
        })

    return {
        "chapter_number": data["chapter_number"],
        "source_core_file": f"ch_{data['chapter_number']:03d}.json",
        "paragraphs": mapped_paragraphs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build minimal paragraph-to-Coptic maps")
    parser.add_argument("--project", default="kephalaia")
    parser.add_argument("--chapter", type=int)
    args = parser.parse_args()

    project = load_project(args.project)
    cleaned_dir = project.paths.cleaned_chapters
    coptic_dir = project.paths.project_dir / "coptic" / "transcriptions"
    output_dir = project.paths.project_dir / "coptic" / "mapping"
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.chapter is not None:
        chapter_files = [cleaned_dir / f"ch_{args.chapter:03d}.json"]
    else:
        chapter_files = sorted(cleaned_dir.glob("ch_*.json"))

    processed = 0
    for cleaned_path in chapter_files:
        if not cleaned_path.exists():
            continue
        mapped = map_chapter(cleaned_path, coptic_dir)
        if mapped is None:
            continue
        out_path = output_dir / f"ch_{mapped['chapter_number']:03d}.json"
        out_path.write_text(json.dumps(mapped, indent=2, ensure_ascii=False), encoding="utf-8")
        processed += 1

    print(f"Built {processed} chapter maps in {output_dir}")


if __name__ == "__main__":
    main()
