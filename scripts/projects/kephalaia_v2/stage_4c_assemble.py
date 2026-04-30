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
  - output/projects/kephalaia_v2/core/p_NNN.json

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


def load_core_pages() -> dict[int, dict]:
    """Load all core page JSONs into a dict keyed by page number."""
    pages = {}
    for path in sorted(CORE_DIR.glob("p_*.json")):
        m = re.match(r"p_(\d+)\.json", path.name)
        if not m:
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        pages[int(m.group(1))] = data
    return pages


# ---------------------------------------------------------------------------
# Lacuna renumbering
# ---------------------------------------------------------------------------

LACUNA_RE = re.compile(r"\{(\d+)\}")


def renumber_lacunae(segments: list[dict], start_from: int = 0) -> tuple[list[dict], int]:
    """Renumber all {N} lacuna markers sequentially across segments.

    Returns (updated_segments, next_available_number).
    Operates on core_coptic and core_english fields.
    """
    counter = start_from
    result = []

    for seg in segments:
        new_seg = dict(seg)  # shallow copy

        for field in ("core_coptic", "core_english"):
            text = new_seg.get(field)
            if not text:
                continue

            # Find all {N} in order, replace with new sequential numbers
            def replace_lacuna(match):
                nonlocal counter
                replacement = f"{{{counter}}}"
                counter += 1
                return replacement

            new_seg[field] = LACUNA_RE.sub(replace_lacuna, text)

        result.append(new_seg)

    return result, counter


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def gather_teaching_segments(
    teaching_idx: int,
    teachings: list[dict],
    section_map: list[dict],
    core_pages: dict[int, dict],
) -> list[dict]:
    """Gather all segments for a teaching from core page files.

    Uses section_map to resolve §N → (page, line).
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
        page_num = map_entry["page"]
        line_idx = map_entry["line"]

        page_data = core_pages.get(page_num)
        if not page_data:
            # Page not in core (shouldn't happen but be safe)
            segments.append({
                "section": sec_num,
                "page": page_num,
                "line": line_idx,
                "classification": None,
                "core_coptic": None,
                "core_english": None,
                "removed_material": None,
                "temporal_note": None,
            })
            continue

        page_segments = page_data.get("segments", [])
        if line_idx < len(page_segments):
            seg = page_segments[line_idx]
            segments.append({
                "section": sec_num,
                "page": page_num,
                "line": line_idx,
                "classification": seg.get("classification"),
                "core_coptic": seg.get("core_coptic"),
                "core_english": seg.get("core_english"),
                "removed_material": seg.get("removed_material"),
                "temporal_note": seg.get("temporal_note"),
            })
        else:
            # Line index out of range
            segments.append({
                "section": sec_num,
                "page": page_num,
                "line": line_idx,
                "classification": None,
                "core_coptic": None,
                "core_english": None,
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
    print(f"  Output: {TEACHINGS_DIR}")

    # Load teaching index
    index = load_teaching_index()
    teachings = index["teachings"]
    section_map = index["section_map"]
    print(f"\n  Teachings: {len(teachings)}")
    print(f"  Section map: {len(section_map)} sections")

    # Load core pages
    core_pages = load_core_pages()
    print(f"  Core pages loaded: {len(core_pages)}")

    if args.dry_run:
        # Show what would be produced
        print(f"\n[DRY RUN] Would write {len(teachings)} files to {TEACHINGS_DIR}/")
        for i, t in enumerate(teachings[:5]):
            segs = gather_teaching_segments(i, teachings, section_map, core_pages)
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
        segments = gather_teaching_segments(i, teachings, section_map, core_pages)
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
