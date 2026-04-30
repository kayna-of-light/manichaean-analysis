#!/usr/bin/env python3
"""
Assemble teaching-level files from page-level core extractions.

Pipeline stage 4c: runs AFTER stage_4b_teachings.py, BEFORE stage_5_read.py.

Groups core segments by teaching boundary (from teaching_index.json),
renumbers lacuna markers {N} sequentially within each teaching, and
writes one file per teaching.

No LLM calls — pure data assembly.

Input:
  - output/projects/kephalaia_v2/teaching_index.json
    - output/projects/kephalaia_v2/core/ch_NNN.json
    - output/projects/kephalaia_v2/chapters/ch_NNN.json

Output:
  - output/projects/kephalaia_v2/teachings/t_NNN.json

Usage:
    python scripts/projects/kephalaia_v2/stage_4c_assemble.py
    python scripts/projects/kephalaia_v2/stage_4c_assemble.py --dry-run
"""
import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PROJECT_DIR = REPO_ROOT / "output" / "projects" / "kephalaia_v2"
CORE_DIR = PROJECT_DIR / "core"
CHAPTERS_DIR = PROJECT_DIR / "chapters"
TEACHINGS_DIR = PROJECT_DIR / "teachings"
INDEX_PATH = PROJECT_DIR / "teaching_index.json"


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

def load_teaching_index() -> dict:
    """Load teaching_index.json."""
    if not INDEX_PATH.exists():
        print(f"ERROR: teaching_index.json not found at {INDEX_PATH}")
        print("       Run stage_4b_teachings.py first.")
        sys.exit(1)
    with open(INDEX_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_core_chapters() -> dict[int, dict]:
    """Load all core chapter JSONs into a dict keyed by chapter number."""
    chapters = {}
    for path in sorted(CORE_DIR.glob("ch_*.json")):
        m = re.match(r"ch_(\d+)\.json", path.name)
        if not m:
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        chapters[int(m.group(1))] = data
    return chapters


def load_source_chapters() -> dict[int, dict]:
    """Load assembled chapter JSONs, including lines and apparatus."""
    chapters = {}
    for path in sorted(CHAPTERS_DIR.glob("ch_*.json")):
        m = re.match(r"ch_(\d+)\.json", path.name)
        if not m:
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        chapters[int(m.group(1))] = data
    return chapters


# ---------------------------------------------------------------------------
# Lacuna renumbering
# ---------------------------------------------------------------------------

LACUNA_RE = re.compile(r"\{(\d+)\}")


def renumber_lacunae(
    segments: list[dict],
    start_from: int = 0,
) -> tuple[list[dict], int]:
    """Renumber lacuna markers sequentially across a teaching.

    Coptic, English, and apparatus must share the same new ID for the
    same physical gap. Original IDs are only unique inside a chapter, so
    the mapping key is (chapter, old_id).
    """
    counter = start_from
    result = []
    marker_map: dict[tuple[int, int], int] = {}

    def get_new_id(chapter: int, old_id: int) -> int:
        nonlocal counter
        key = (chapter, old_id)
        if key not in marker_map:
            marker_map[key] = counter
            counter += 1
        return marker_map[key]

    for seg in segments:
        new_seg = dict(seg)  # shallow copy
        chapter = int(new_seg.get("chapter", -1))
        segment_marker_ids: set[int] = set()

        for field in ("core_coptic", "core_english"):
            text = new_seg.get(field)
            if not text:
                continue

            def replace_lacuna(match):
                old_id = int(match.group(1))
                segment_marker_ids.add(old_id)
                return f"{{{get_new_id(chapter, old_id)}}}"

            new_seg[field] = LACUNA_RE.sub(replace_lacuna, text)

        updated_apparatus = []
        for entry in new_seg.get("apparatus", []):
            old_id = entry.get("id")
            if old_id is None or int(old_id) not in segment_marker_ids:
                continue
            updated = dict(entry)
            updated["source_id"] = old_id
            updated["id"] = marker_map[(chapter, int(old_id))]
            updated["section"] = new_seg.get("section")
            updated_apparatus.append(updated)
        new_seg["apparatus"] = sorted(
            updated_apparatus,
            key=lambda item: item["id"],
        )

        result.append(new_seg)

    return result, counter


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def gather_teaching_segments(
    teaching_idx: int,
    teachings: list[dict],
    section_map: list[dict],
    core_chapters: dict[int, dict],
    source_chapters: dict[int, dict],
) -> list[dict]:
    """Gather all segments for a teaching from core chapter files.

    Uses section_map to resolve §N → (chapter, line).
    """
    start_section = teachings[teaching_idx]["section"]

    # End section: start of next teaching - 1, or last section
    if teaching_idx + 1 < len(teachings):
        end_section = teachings[teaching_idx + 1]["section"] - 1
    else:
        end_section = len(section_map)  # last section in corpus

    segments = []
    for sec_num in range(start_section, end_section + 1):
        # section_map is 0-indexed (§1 is at index 0)
        map_entry = section_map[sec_num - 1]
        chapter_num = map_entry["chapter"]
        line_idx = map_entry["line"]

        chapter_data = core_chapters.get(chapter_num)
        source_chapter = source_chapters.get(chapter_num, {})
        apparatus_by_segment: dict[int, list[dict]] = {}
        for entry in source_chapter.get("apparatus", []):
            segment = entry.get("segment")
            if isinstance(segment, int):
                apparatus_by_segment.setdefault(segment, []).append(entry)

        if not chapter_data:
            segments.append({
                "section": sec_num,
                "chapter": chapter_num,
                "line": line_idx,
                "classification": None,
                "core_coptic": None,
                "core_english": None,
                "apparatus": apparatus_by_segment.get(line_idx, []),
                "removed_material": None,
                "temporal_note": None,
            })
            continue

        ch_segments = chapter_data.get("segments", [])
        if line_idx < len(ch_segments):
            seg = ch_segments[line_idx]
            segments.append({
                "section": sec_num,
                "chapter": chapter_num,
                "line": line_idx,
                "classification": seg.get("classification"),
                "core_coptic": seg.get("core_coptic"),
                "core_english": seg.get("core_english"),
                "apparatus": apparatus_by_segment.get(line_idx, []),
                "removed_material": seg.get("removed_material"),
                "temporal_note": seg.get("temporal_note"),
            })
        else:
            # Line index out of range
            segments.append({
                "section": sec_num,
                "chapter": chapter_num,
                "line": line_idx,
                "classification": None,
                "core_coptic": None,
                "core_english": None,
                "apparatus": apparatus_by_segment.get(line_idx, []),
                "removed_material": None,
                "temporal_note": None,
            })

    return segments


def assemble_teaching(
    teaching_num: int,
    teaching_entry: dict,
    segments: list[dict],
) -> dict:
    """Assemble a single teaching file with renumbered lacunae."""
    # Renumber lacunae from 0
    renumbered, total_lacunae = renumber_lacunae(segments)

    start_section = segments[0]["section"] if segments else None
    end_section = segments[-1]["section"] if segments else None

    return {
        "teaching": teaching_num,
        "title": teaching_entry["title"],
        "confidence": teaching_entry["confidence"],
        "start_section": start_section,
        "end_section": end_section,
        "total_sections": len(renumbered),
        "total_lacunae": total_lacunae,
        "segments": renumbered,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Assemble teaching files from core pages (no LLM)"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("Stage 4c: Teaching Assembly")
    print("  Group core segments by teaching, renumber lacunae")
    print(f"  Input:  {INDEX_PATH}")
    print(f"          {CORE_DIR}")
    print(f"          {CHAPTERS_DIR}")
    print(f"  Output: {TEACHINGS_DIR}")

    # Load teaching index
    index = load_teaching_index()
    teachings = index["teachings"]
    section_map = index["section_map"]
    print(f"\n  Teachings: {len(teachings)}")
    print(f"  Section map: {len(section_map)} sections")

    # Load core chapters
    core_chapters = load_core_chapters()
    source_chapters = load_source_chapters()
    print(f"  Core chapters loaded: {len(core_chapters)}")
    print(f"  Source chapters loaded: {len(source_chapters)}")

    if args.dry_run:
        # Show what would be produced
        print(f"\n[DRY RUN] Would write {len(teachings)} files to {TEACHINGS_DIR}/")
        for i, t in enumerate(teachings[:5]):
            segs = gather_teaching_segments(
                i, teachings, section_map, core_chapters, source_chapters
            )
            _, lacunae = renumber_lacunae(segs)
            print(f"  t_{i+1:03d}.json — §{t['section']:>4d} — {len(segs):>3d} sections, "
                  f"{lacunae:>3d} lacunae — {t['title'][:50]}")
        if len(teachings) > 5:
            print(f"  ... and {len(teachings) - 5} more")
        return

    # Create output directory
    TEACHINGS_DIR.mkdir(parents=True, exist_ok=True)

    # Assemble each teaching
    total_lacunae = 0
    for i, teaching_entry in enumerate(teachings):
        segments = gather_teaching_segments(
            i, teachings, section_map, core_chapters, source_chapters
        )
        result = assemble_teaching(i + 1, teaching_entry, segments)
        total_lacunae += result["total_lacunae"]

        output_path = TEACHINGS_DIR / f"t_{i+1:03d}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\nAssembly complete:")
    print(f"  Teachings written: {len(teachings)}")
    print(f"  Output directory:  {TEACHINGS_DIR}")
    print(f"  Total lacunae:     {total_lacunae}")


if __name__ == "__main__":
    main()
