#!/usr/bin/env python3
"""
Process Azure AI Document Intelligence OCR JSON files into clean markdown.

Reads .pdf.json files from data/ and outputs structured markdown to output/texts/.
Each PDF becomes one markdown file with:
  - Title and metadata header
  - Page break markers
  - Cleaned-up OCR text
"""

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output" / "texts"

# Map PDF filenames to output names and metadata
PDF_CATALOG = {
    "DB-Antholog.-1-Hist..pdf": {
        "output": "DB_Anthology_1_Historical_Texts.md",
        "title": "Database of Manichaean Texts — Anthology I: Historical Texts",
        "description": "Historical texts relating to Mani's life, mission, and the Manichaean community.",
        "editor": "Samuel N.C. Lieu FBA",
    },
    "DB-Antholog.-2-Canon.pdf": {
        "output": "DB_Anthology_2_Canonical_Texts.md",
        "title": "Database of Manichaean Texts — Anthology II: Canonical Texts",
        "description": "Fragments from Mani's canonical works (Living Gospel, Treasure of Life, Epistles, Book of Giants, etc.).",
        "editor": "Samuel N.C. Lieu FBA",
    },
    "DB-Antholog.-3-Sab..pdf": {
        "output": "DB_Anthology_3_Shabuhragan.md",
        "title": "Database of Manichaean Texts — Anthology III: Šābuhragān",
        "description": "Mani's Middle Persian cosmogonic and eschatological work composed for King Shapur I.",
        "editor": "Samuel N.C. Lieu FBA",
    },
    "DB-Antholog.-4-Hymns.pdf": {
        "output": "DB_Anthology_4_Hymns.md",
        "title": "Database of Manichaean Texts — Anthology IV: Hymns",
        "description": "Middle Iranian hymns and liturgical texts from the Manichaean tradition.",
        "editor": "Samuel N.C. Lieu FBA",
    },
    "ArtMS1.1-Cosmog.-Texts-17.9.2024.pdf": {
        "output": "ArtMS_1_Cosmogonic_Texts.md",
        "title": "Manichaean Cosmogonic Texts",
        "description": "Texts concerning Manichaean cosmogony: the creation myth, five elements, realm of light and darkness.",
        "editor": "Samuel N.C. Lieu FBA",
    },
    "ArtMS2-Book-of-Giants-18.9.2024.pdf": {
        "output": "ArtMS_2_Book_of_Giants.md",
        "title": "The Book of Giants — Critical Edition",
        "description": "Mani's Book of Giants: fragments in Middle Persian, Sogdian, Uyghur, Coptic, and Parthian. "
                       "Critical edition with original scripts and translations.",
        "editor": "Samuel N.C. Lieu FBA",
    },
    "ArtMS3-Old-Turkic-Texts-21.8.2024.pdf": {
        "output": "ArtMS_3_Old_Turkic_Texts.md",
        "title": "Old Turkic Manichaean Texts",
        "description": "Manichaean texts in Old Turkic (Uyghur) from the Kingdom of Qocho and Turfan. "
                       "Includes confessional, liturgical, and didactic material.",
        "editor": "Samuel N.C. Lieu FBA",
    },
    "ArtMS4-Xuastvanift-21.8.2024.pdf": {
        "output": "ArtMS_4_Xuastvanift.md",
        "title": "The Xuāstvānīft — Uyghur Manichaean Confession Prayer",
        "description": "The Xuāstvānīft (Confession of Sins): the central Uyghur Manichaean liturgical text "
                       "from the Kingdom of Qocho.",
        "editor": "Samuel N.C. Lieu FBA",
    },
    "ArtMS5-Sogdian-Tales-21.8.2024.pdf": {
        "output": "ArtMS_5_Sogdian_Tales.md",
        "title": "Sogdian Manichaean Tales",
        "description": "Narrative and didactic tales in Sogdian from the Central Asian Manichaean tradition.",
        "editor": "Samuel N.C. Lieu FBA",
    },
    "eDbMT-2.1-Fihrist-26.5.2022.pdf": {
        "output": "Fihrist_Extract.md",
        "title": "The Fihrist of Ibn al-Nadim — Manichaean Section",
        "description": "Ibn al-Nadim's catalog of Mani's writings and Manichaean doctrine from the Kitāb al-Fihrist (c. 987 CE).",
        "editor": "Samuel N.C. Lieu FBA",
    },
    "Cologne-Mani-Codex-25.9.24.pdf": {
        "output": "Cologne_Mani_Codex.md",
        "title": "The Cologne Mani-Codex",
        "description": "Greek miniature codex containing an autobiographical account of Mani's youth "
                       "among the Elcesaites and his early revelations.",
        "editor": "Samuel N.C. Lieu FBA (after Henrichs & Koenen)",
    },
    "The Kephalaia of the Teacher.pdf": {
        "output": "Kephalaia_of_the_Teacher.md",
        "title": "The Kephalaia of the Teacher",
        "description": "The Discourses of Mani: ~350 chapters of instructional teaching on correspondences, "
                       "cosmogony, soteriology, and the nature of the soul. Translated by Iain Gardner (Brill, 1995).",
        "editor": "Iain Gardner",
    },
}


def load_ocr_json(json_path: Path) -> dict:
    """Load and return the analyzeResult from a Document Intelligence JSON."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("analyzeResult", data)


def get_page_spans(result: dict) -> list[tuple[int, int]]:
    """Extract (offset, length) spans for each page from the pages array."""
    spans = []
    for page in result.get("pages", []):
        page_spans = page.get("spans", [])
        if page_spans:
            # Pages can have multiple spans; take the full range
            first = page_spans[0]
            last = page_spans[-1]
            start = first["offset"]
            end = last["offset"] + last["length"]
            spans.append((start, end))
    return spans


def insert_page_breaks(content: str, page_spans: list[tuple[int, int]]) -> str:
    """Insert page break markers into the content based on page span boundaries."""
    if not page_spans:
        return content

    # Build list of insertion points (end of each page except last)
    breaks = []
    for i, (start, end) in enumerate(page_spans[:-1]):
        breaks.append(end)

    # Insert from end to start to preserve offsets
    result = content
    for pos in reversed(breaks):
        # Find nearest newline to insert page break cleanly
        newline_pos = result.rfind("\n", max(0, pos - 5), pos + 5)
        if newline_pos == -1:
            newline_pos = pos
        result = result[:newline_pos] + "\n\n---\n" + result[newline_pos:]

    return result


def clean_content(content: str) -> str:
    """Clean up OCR artifacts in the content text."""
    # Normalize line endings
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    # Remove trailing whitespace from lines
    lines = content.split("\n")
    lines = [line.rstrip() for line in lines]

    # Collapse 3+ consecutive blank lines to 2
    cleaned = []
    blank_count = 0
    for line in lines:
        if line == "":
            blank_count += 1
            if blank_count <= 2:
                cleaned.append(line)
        else:
            blank_count = 0
            cleaned.append(line)

    return "\n".join(cleaned)


def build_markdown(meta: dict, content: str, page_count: int) -> str:
    """Build the final markdown document."""
    header = f"""# {meta['title']}

> **Source**: Database of Manichaean Texts (DbMT 2025) — manichaeism.de
> **Editor**: {meta['editor']}
> **Pages**: {page_count}
>
> {meta['description']}

---

"""
    return header + content + "\n"


def process_one(pdf_name: str, meta: dict, dry_run: bool = False) -> bool:
    """Process a single PDF's OCR JSON into markdown."""
    json_path = DATA_DIR / f"{pdf_name}.json"
    output_path = OUTPUT_DIR / meta["output"]

    if not json_path.exists():
        print(f"  SKIP: {json_path.name} not found")
        return False

    print(f"  Loading {json_path.name} ({json_path.stat().st_size / 1024 / 1024:.1f} MB)...")
    result = load_ocr_json(json_path)

    content = result.get("content", "")
    if not content:
        print(f"  SKIP: No content in {json_path.name}")
        return False

    pages = result.get("pages", [])
    page_count = len(pages)
    page_spans = get_page_spans(result)

    print(f"  Pages: {page_count}, Content: {len(content):,} chars")

    # Process
    content = insert_page_breaks(content, page_spans)
    content = clean_content(content)

    if dry_run:
        print(f"  DRY RUN: Would write {output_path.name} ({len(content):,} chars)")
        return True

    md = build_markdown(meta, content, page_count)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"  -> {output_path.name} ({len(md):,} chars, {len(md.splitlines()):,} lines)")
    return True


def main():
    dry_run = "--dry-run" in sys.argv
    single = None
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            single = arg
            break

    if dry_run:
        print("DRY RUN MODE\n")

    print(f"Data dir: {DATA_DIR}")
    print(f"Output dir: {OUTPUT_DIR}\n")

    # Find available JSON files
    available = sorted(DATA_DIR.glob("*.pdf.json"))
    print(f"Found {len(available)} OCR JSON files\n")

    success = 0
    skipped = 0

    for pdf_name, meta in sorted(PDF_CATALOG.items()):
        if single and single not in pdf_name:
            continue

        print(f"[{pdf_name}]")
        if process_one(pdf_name, meta, dry_run):
            success += 1
        else:
            skipped += 1
        print()

    print(f"\nDone: {success} processed, {skipped} skipped")


if __name__ == "__main__":
    main()
