"""
Stage 3b: Build chapter index from v1 cleaned chapter JSONs.

Reads Gardner's chapter structure from the v1 cleaned output and produces
a chapter_index.json with precise start/end page+line boundaries for each chapter.

Input:  output/projects/kephalaia/cleaned/chapters/ch_NNN.json
Output: output/projects/kephalaia_v2/chapter_index.json
"""
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
V1_CHAPTERS = PROJECT_ROOT / "output" / "projects" / "kephalaia" / "cleaned" / "chapters"
V2_OUTPUT = PROJECT_ROOT / "output" / "projects" / "kephalaia_v2"


def parse_ms_pages(ms_pages: str) -> tuple[int | None, int | None, int | None, int | None]:
    """
    Parse manuscript_pages like '25,7 - 27,31' or '(9,11 - 16,31)' into
    (start_page, start_line, end_page, end_line).
    """
    if not ms_pages:
        return None, None, None, None

    # Strip parentheses
    clean = ms_pages.strip().strip("()")

    # Pattern: PAGE,LINE - PAGE,LINE
    # Also handles: PAGE,LINE - ? or PAGE,LINE - LINE (same page)
    m = re.match(r"(\d+)\s*,\s*(\d+)\s*-\s*(\d+)?\s*,?\s*(\d+)?", clean)
    if not m:
        # Try simpler: just "PAGE - PAGE"
        m2 = re.match(r"(\d+)\s*-\s*(\d+)", clean)
        if m2:
            return int(m2.group(1)), None, int(m2.group(2)), None
        return None, None, None, None

    start_page = int(m.group(1))
    start_line = int(m.group(2))

    # Determine end_page and end_line
    g3 = m.group(3)
    g4 = m.group(4)

    if g3 and g4:
        # Full: PAGE,LINE - PAGE,LINE
        end_page = int(g3)
        end_line = int(g4)
    elif g3 and not g4:
        # Could be "166,17 - 30" (same page, line 30) or "282,7 - ?" parsed oddly
        val = int(g3)
        if val < start_page:
            # It's a line number on the same page
            end_page = start_page
            end_line = val
        else:
            end_page = val
            end_line = None
    else:
        end_page = None
        end_line = None

    return start_page, start_line, end_page, end_line


def main():
    files = sorted(V1_CHAPTERS.glob("ch_*.json"))
    if not files:
        print(f"ERROR: No chapter files found in {V1_CHAPTERS}")
        return

    chapters = []
    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as f:
            ch = json.load(f)

        num = ch["chapter_number"]
        title = ch["title"]
        ms_pages = ch.get("manuscript_pages", "")
        sp, sl, ep, el = parse_ms_pages(ms_pages)

        chapters.append({
            "chapter": num,
            "title": title,
            "manuscript_pages": ms_pages,
            "start_page": sp,
            "start_line": sl,
            "end_page": ep,
            "end_line": el,
        })

    # Manual fixes for edge cases the regex couldn't handle
    by_num = {ch["chapter"]: ch for ch in chapters}

    # Ch 117: "282,7 - ?" — end unknown; infer from Ch 118 start (283)
    if by_num[117]["end_page"] is None:
        by_num[117]["end_page"] = 283
        by_num[117]["end_line"] = None  # unknown line

    # Ch 119: "(284,? - 286,23)" — start line unknown
    if by_num[119]["start_line"] is None:
        by_num[119]["start_page"] = 284
        by_num[119]["start_line"] = None  # genuinely unknown

    # Validate
    problems = [ch for ch in chapters if ch["start_page"] is None or ch["end_page"] is None]
    if problems:
        print(f"WARNING: {len(problems)} chapters with incomplete boundaries:")
        for ch in problems:
            print(f"  Ch {ch['chapter']}: \"{ch['manuscript_pages']}\"")

    # Build output
    output = {
        "source": "Gardner, The Kephalaia of the Teacher (1995)",
        "total_chapters": len(chapters),
        "chapters": []
    }

    for ch in chapters:
        entry = {
            "chapter": ch["chapter"],
            "title": ch["title"],
            "start_page": ch["start_page"],
            "start_line": ch["start_line"],
            "end_page": ch["end_page"],
            "end_line": ch["end_line"],
        }
        output["chapters"].append(entry)

    # Write output
    V2_OUTPUT.mkdir(parents=True, exist_ok=True)
    outpath = V2_OUTPUT / "chapter_index.json"
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Written: {outpath}")
    print(f"  Total chapters: {len(chapters)}")
    valid = [ch for ch in chapters if ch["start_page"] is not None and ch["end_page"] is not None]
    print(f"  With complete boundaries: {len(valid)}")


if __name__ == "__main__":
    main()
