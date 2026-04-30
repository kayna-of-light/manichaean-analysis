"""
Stage 3a: Assemble v2 page-level data into chapter-level files.

Reads chapter_index.json and combines page-level JSON files into per-chapter
JSON files with the same structure as page files:
chapter/range/header/lines/apparatus/notes.

Input:
    - output/projects/kephalaia_v2/chapter_index.json
    - output/projects/kephalaia_v2/pages/p_NNN.json

Output:
    - output/projects/kephalaia_v2/chapters/ch_NNN.json
"""
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
V2_OUTPUT = PROJECT_ROOT / "output" / "projects" / "kephalaia_v2"
PAGES_DIR = V2_OUTPUT / "pages"
CHAPTERS_DIR = V2_OUTPUT / "chapters"

# Our v2 corpus page range
V2_FIRST_PAGE = 10
V2_LAST_PAGE = 291
MARKER_RE = re.compile(r"\{(\d+)\}")


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


def renumber_markers(text: str | None, marker_map: dict[int, int], next_id: list[int]) -> str | None:
    """Renumber {N} markers in one line, preserving order of appearance."""
    if text is None:
        return None

    def repl(match: re.Match) -> str:
        old_id = int(match.group(1))
        if old_id not in marker_map:
            marker_map[old_id] = next_id[0]
            next_id[0] += 1
        return "{" + str(marker_map[old_id]) + "}"

    return MARKER_RE.sub(repl, text)


def assemble_chapter(pages_data: list[tuple[int, dict]], ch: dict) -> dict:
    """Build chapter JSON with page-file structure and renumbered apparatus."""
    lines: list[dict] = []
    apparatus: list[dict] = []
    notes: list[dict] = []
    page_ranges: list[dict] = []
    marker_maps: dict[int, dict[int, int]] = {}
    segment_maps: dict[tuple[int, int], int] = {}
    next_marker_id = [0]

    for page_num, page in pages_data:
        filtered = filter_lines(page.get("lines", []), page_num, ch)
        if not filtered:
            continue

        page_ranges.append({
            "page": page_num,
            "start_line": filtered[0].get("n"),
            "end_line": filtered[-1].get("n"),
        })

        page_marker_map: dict[int, int] = {}
        marker_maps[page_num] = page_marker_map

        for line in filtered:
            new_i = len(lines)
            old_i = line.get("i")
            segment_maps[(page_num, old_i)] = new_i
            lines.append({
                "i": new_i,
                "n": line.get("n"),
                "coptic": renumber_markers(
                    line.get("coptic"), page_marker_map, next_marker_id
                ),
                "english": renumber_markers(
                    line.get("english"), page_marker_map, next_marker_id
                ),
            })

        for entry in page.get("apparatus", []):
            old_segment = entry.get("segment")
            if (page_num, old_segment) not in segment_maps:
                continue
            old_id = entry.get("id")
            if old_id not in page_marker_map:
                continue
            updated = dict(entry)
            updated["id"] = page_marker_map[old_id]
            updated["segment"] = segment_maps[(page_num, old_segment)]
            apparatus.append(updated)

        for note in page.get("notes", []):
            old_segment = note.get("segment")
            if (page_num, old_segment) not in segment_maps:
                continue
            updated = dict(note)
            updated["segment"] = segment_maps[(page_num, old_segment)]
            notes.append(updated)

    return {
        "chapter": ch["chapter"],
        "range": {
            "start_page": ch["start_page"],
            "start_line": ch.get("start_line"),
            "end_page": ch["end_page"],
            "end_line": ch.get("end_line"),
            "pages": page_ranges,
        },
        "header": {
            "chapter_number": ch["chapter"],
            "title_coptic": None,
            "title_english": ch["title"],
        },
        "lines": lines,
        "apparatus": apparatus,
        "notes": notes,
    }


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

        output = assemble_chapter(pages_data, ch)
        if missing_pages:
            output["range"]["missing_pages"] = missing_pages

        outpath = CHAPTERS_DIR / f"ch_{ch_num:03d}.json"
        with open(outpath, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        assembled += 1

    print(f"Assembled {assembled} chapter files to {CHAPTERS_DIR}")
    if skipped:
        print(f"Skipped {skipped} chapters (outside v2 corpus range)")


if __name__ == "__main__":
    main()
