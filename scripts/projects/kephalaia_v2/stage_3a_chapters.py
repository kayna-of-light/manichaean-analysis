"""
Stage 3a: Assemble v2 page-level data into chapter-level files.

Reads chapter_index.json and combines page-level text (pages/) into
per-chapter JSON files. Text is trimmed to exact line boundaries.

Scoring happens in stage_3b_score_chapters.py AFTER assembly.

Input:
  - output/projects/kephalaia_v2/chapter_index.json
  - output/projects/kephalaia_v2/pages/p_NNN.json

Output:
  - output/projects/kephalaia_v2/chapters/ch_NNN.json
"""
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
V2_OUTPUT = PROJECT_ROOT / "output" / "projects" / "kephalaia_v2"
PAGES_DIR = V2_OUTPUT / "pages"
CHAPTERS_DIR = V2_OUTPUT / "chapters"

# Our v2 corpus page range
V2_FIRST_PAGE = 10
V2_LAST_PAGE = 291


def load_json(path: Path) -> dict | None:
    """Load a JSON file, returning None if it doesn't exist."""
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_chapter_pages(ch: dict) -> list[int]:
    """Compute which v2 page files a chapter spans, clamped to corpus range."""
    sp = ch.get("start_page")
    ep = ch.get("end_page")
    if sp is None or ep is None:
        return []
    first = max(sp, V2_FIRST_PAGE)
    last = min(ep, V2_LAST_PAGE)
    if first > last:
        return []
    return list(range(first, last + 1))


def filter_lines(lines: list[dict], page_num: int, ch: dict) -> list[dict]:
    """
    Filter lines on a page to only those belonging to this chapter,
    based on start/end line boundaries.

    Line numbers in the page JSON are 1-indexed in field 'n'.
    """
    start_page = ch["start_page"]
    start_line = ch.get("start_line")
    end_page = ch["end_page"]
    end_line = ch.get("end_line")

    filtered = []
    for line in lines:
        ln = line.get("n", 0)

        # On the start page, skip lines before start_line
        if page_num == start_page and start_line is not None:
            if ln < start_line:
                continue

        # On the end page, skip lines after end_line
        if page_num == end_page and end_line is not None:
            if ln > end_line:
                continue

        filtered.append(line)

    return filtered


def assemble_chapter_text(pages_data: list[tuple[int, dict]], ch: dict) -> str:
    """Combine page-level line data into a single running English text for the chapter."""
    parts = []
    for page_num, page in pages_data:
        lines = filter_lines(page.get("lines", []), page_num, ch)
        if not lines:
            continue
        parts.append(f"⟨p.{page_num}⟩")
        for line in lines:
            eng = line.get("english", "")
            if eng:
                parts.append(eng)
    return "\n".join(parts)


def assemble_chapter_lines(pages_data: list[tuple[int, dict]], ch: dict) -> list[dict]:
    """Return the filtered lines (with page attribution) for scoring use."""
    result = []
    for page_num, page in pages_data:
        lines = filter_lines(page.get("lines", []), page_num, ch)
        for line in lines:
            result.append({**line, "_page": page_num})
    return result


def main():
    index_path = V2_OUTPUT / "chapter_index.json"
    if not index_path.exists():
        print(f"ERROR: {index_path} not found. Run build_chapter_index.py first.")
        return

    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)

    chapters = index["chapters"]
    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)

    assembled = 0
    skipped = 0

    for ch in chapters:
        ch_num = ch["chapter"]
        page_nums = get_chapter_pages(ch)

        if not page_nums:
            skipped += 1
            continue

        # Load page data
        pages_data = []  # list of (page_num, page_dict)
        missing_pages = []

        for p in page_nums:
            page_file = PAGES_DIR / f"p_{p:03d}.json"
            pd = load_json(page_file)
            if pd is not None:
                pages_data.append((p, pd))
            else:
                missing_pages.append(p)

        # Assemble chapter text (with line-level trimming)
        chapter_text = assemble_chapter_text(pages_data, ch)

        # Also store the raw filtered lines for stage_3b scoring
        chapter_lines = assemble_chapter_lines(pages_data, ch)

        # Build output
        output = {
            "chapter": ch_num,
            "title": ch["title"],
            "start_page": ch["start_page"],
            "start_line": ch.get("start_line"),
            "end_page": ch["end_page"],
            "end_line": ch.get("end_line"),
            "missing_pages": missing_pages if missing_pages else None,
            "text": chapter_text,
            "lines": chapter_lines,
        }

        outpath = CHAPTERS_DIR / f"ch_{ch_num:03d}.json"
        with open(outpath, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        assembled += 1

    print(f"Assembled {assembled} chapter files to {CHAPTERS_DIR}")
    if skipped:
        print(f"Skipped {skipped} chapters (outside v2 corpus range)")


if __name__ == "__main__":
    main()
