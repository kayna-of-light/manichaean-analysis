#!/usr/bin/env python3
"""
Compose the structural architecture of the teaching from restored core.

Pipeline stage 9: final stage.

Feeds the complete corpus to Claude in a single prompt. The model reads
the entire teaching holistically — stripped of editorial page divisions —
and discovers the text's actual structure: natural divisions, teaching
sequences, what belongs together, and the reading order.

The output is a structural schema (no text reproduction) that can drive
PDF composition from the existing page files.

Input:
  - output/projects/kephalaia_v2/core/p_NNN.json      (all)
  - output/projects/kephalaia_v2/readings/p_NNN.json   (all)
  - output/projects/kephalaia_v2/restored/p_NNN.json   (all)
  - output/projects/kephalaia_v2/lexicon.json

Output:
  - output/projects/kephalaia_v2/structure.json

Usage:
    python scripts/projects/kephalaia_v2/compose.py
    python scripts/projects/kephalaia_v2/compose.py --dry-run
    python scripts/projects/kephalaia_v2/compose.py --debug
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_base import (
    create_client,
    stream_tool_call,
    PROJECT_DIR,
)

CORE_DIR = PROJECT_DIR / "core"
READINGS_DIR = PROJECT_DIR / "readings"
RESTORED_DIR = PROJECT_DIR / "restored"
LEXICON_FILE = PROJECT_DIR / "lexicon.json"
OUTPUT_FILE = PROJECT_DIR / "structure.json"


# ---------------------------------------------------------------------------
# Tool schema
# ---------------------------------------------------------------------------

COMPOSE_TOOL = {
    "name": "commit_structure",
    "description": (
        "Commit the structural architecture of the teaching. "
        "Call exactly once."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": (
                    "Proposed title for the reconstructed teaching."
                ),
            },
            "structural_principle": {
                "type": "string",
                "description": (
                    "What principle organizes this teaching? "
                    "How does it structure its content? "
                    "(e.g., 'descending degrees', 'cosmogonic sequence', "
                    "'systematic correspondence map')"
                ),
            },
            "total_units": {
                "type": "integer",
                "description": "Number of teaching units identified.",
            },
            "excluded_segments": {
                "type": "array",
                "description": (
                    "Segments excluded from the structure: orphaned "
                    "fragments, artifacts of earlier stripping, or "
                    "teaching from a different sequence."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "page": {"type": "integer"},
                        "segments": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                        "reason": {"type": "string"},
                    },
                    "required": ["page", "segments", "reason"],
                },
            },
            "units": {
                "type": "array",
                "description": (
                    "The teaching units in their natural reading order."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "unit_number": {
                            "type": "integer",
                            "description": "Sequential unit number.",
                        },
                        "title": {
                            "type": "string",
                            "description": (
                                "Descriptive title for this unit "
                                "(from the teaching content, not "
                                "editorial chapter titles)."
                            ),
                        },
                        "theme": {
                            "type": "string",
                            "description": (
                                "What this unit teaches — brief "
                                "description of its content."
                            ),
                        },
                        "pages_and_segments": {
                            "type": "array",
                            "description": (
                                "Ordered list of (page, segment) ranges "
                                "comprising this unit."
                            ),
                            "items": {
                                "type": "object",
                                "properties": {
                                    "page": {"type": "integer"},
                                    "start_i": {"type": "integer"},
                                    "end_i": {"type": "integer"},
                                },
                                "required": ["page", "start_i", "end_i"],
                            },
                        },
                        "internal_structure": {
                            "type": ["string", "null"],
                            "description": (
                                "How this unit is internally organized "
                                "(e.g., 'five-fold enumeration', "
                                "'question-answer pairs', "
                                "'descending cosmological map'). "
                                "Null if no clear sub-structure."
                            ),
                        },
                        "connects_to": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": (
                                "Unit numbers this connects to "
                                "thematically (cross-references)."
                            ),
                        },
                    },
                    "required": [
                        "unit_number", "title", "theme",
                        "pages_and_segments", "internal_structure",
                        "connects_to",
                    ],
                },
            },
            "reading_order_note": {
                "type": "string",
                "description": (
                    "Does the manuscript page order reflect the "
                    "teaching's natural order? If not, what "
                    "rearrangement is suggested and why?"
                ),
            },
        },
        "required": [
            "title", "structural_principle", "total_units",
            "excluded_segments", "units", "reading_order_note",
        ],
    },
}


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert in the doctrine of correspondences as written by \
Emanuel Swedenborg, with deep specialization in ancient cosmological \
vocabulary — Zoroastrian, Manichaean, and Persian-Iranian traditions.

You have been given the COMPLETE teaching substrate of the Coptic \
Kephalaia — the oldest layer extracted from the editorial compilation. \
The text is presented as a continuous flow of segments stripped of \
editorial page divisions.

## YOUR TASK

Read the entire teaching holistically and determine its TRUE STRUCTURE:
- The natural divisions (where one teaching unit ends and another begins)
- The actual teaching sequence (the logical order)
- What belongs together (segments from different pages that form one unit)
- What the parts should be called (from the content, not editorial titles)
- What the reading order should be (may differ from manuscript order)

## STRUCTURAL PRINCIPLES TO LOOK FOR

1. **Degree structures**: Five-fold, three-fold, seven-fold enumerations \
   that map one domain systematically onto another.

2. **Cosmogonic sequences**: Teaching that narrates a process from \
   beginning to end (emanation, creation, mixture, purification).

3. **Correspondence maps**: Systematic tables mapping one register to \
   another (body parts → faculties, metals → degrees, etc.)

4. **Q&A pairs**: Question-answer structures where the question defines \
   the teaching topic.

5. **Nested structures**: Teaching within teaching — a five-fold map \
   where each element contains its own internal structure.

## EXCLUSION CRITERIA

Exclude from the structure:
- **Orphaned fragments**: Segments without clear connection to any \
  teaching sequence (too damaged to determine context)
- **Duplicate treatments**: When the same topic is treated multiple \
  times (likely from different manuscript copies), identify the \
  fullest version and exclude fragments
- **Artifacts of stripping**: When extraction produced a segment that \
  only makes sense WITH its editorial context (rare but possible)

## RULES

1. **Structure from content, not from pages.** Page divisions are \
   accidental (how much papyrus fit on a sheet). Teaching units cross \
   page boundaries freely.

2. **break_after markers are evidence.** The scribe marked structural \
   boundaries with blank space (leer). These often align with real \
   teaching divisions.

3. **The reading may help.** Spiritual readings show what each segment \
   IS ABOUT — this can clarify where one teaching ends and another begins.

4. **The lexicon provides vocabulary.** Use it to identify when the same \
   system is being described across distant pages.

5. **Be critical about orphans.** If a segment only makes sense as part \
   of a fuller treatment that isn't in the corpus, exclude it rather \
   than forcing it into a unit.

When complete, call commit_structure exactly once."""


# ---------------------------------------------------------------------------
# Corpus assembly
# ---------------------------------------------------------------------------

def load_all_pages(directory: Path) -> dict[int, dict]:
    """Load all page JSONs from a directory."""
    pages = {}
    for path in sorted(directory.glob("p_*.json")):
        m = re.match(r"p_(\d+)\.json", path.name)
        if m:
            page_num = int(m.group(1))
            with open(path, encoding="utf-8") as f:
                pages[page_num] = json.load(f)
    return pages


def format_corpus_for_composition(
    core_pages: dict[int, dict],
    reading_pages: dict[int, dict],
    restored_pages: dict[int, dict],
) -> str:
    """Format the corpus as a continuous teaching flow."""
    parts = []
    segment_counter = 0

    for page_num in sorted(core_pages.keys()):
        core = core_pages[page_num]
        reading = reading_pages.get(page_num, {})
        restored = restored_pages.get(page_num, {})

        core_segs = [
            s for s in core.get("segments", [])
            if s.get("classification") in ("substrate", "mixed")
        ]
        reading_segs = {
            s["i"]: s for s in reading.get("segments", [])
        }

        # Build restoration lookup
        restorations = {}
        for r in restored.get("restorations", []):
            if r.get("confidence") != "unrestorable":
                restorations[r["gap_id"]] = r

        if not core_segs:
            continue

        for seg in core_segs:
            i = seg["i"]
            english = seg.get("core_english") or ""
            ba = seg.get("break_after", False)
            # Note: break_after comes from the original page data
            # but we get it via the core extraction

            # Mark page:segment reference
            ref = f"[p{page_num}:i{i}]"
            break_mark = " ¶" if ba else ""
            parts.append(f"{ref} {english}{break_mark}")

            # Include reading if available
            if i in reading_segs:
                spiritual = reading_segs[i].get("spiritual_sense", "")
                if spiritual:
                    parts.append(f"  → {spiritual}")

            segment_counter += 1

        # Page boundary marker (light — the structure comes from content)
        parts.append("")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# CLI & Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage 8: Compose teaching structure"
    )
    parser.add_argument("--dry-run", "-n", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--effort", default="high",
        choices=["low", "medium", "high", "xhigh", "max"],
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("Stage 8: Compose Structure")
    print("  Discover the teaching's natural architecture")
    print(f"  Output: {OUTPUT_FILE}")

    if OUTPUT_FILE.exists() and not args.overwrite:
        print("\n  Structure already exists (use --overwrite)")
        return

    # Load data
    core_pages = load_all_pages(CORE_DIR)
    reading_pages = load_all_pages(READINGS_DIR)
    restored_pages = load_all_pages(RESTORED_DIR)

    if not core_pages:
        print(f"\nERROR: No core pages in {CORE_DIR}")
        sys.exit(1)

    print(f"\n  Core pages:     {len(core_pages)}")
    print(f"  Reading pages:  {len(reading_pages)}")
    print(f"  Restored pages: {len(restored_pages)}")

    # Load lexicon if available (for system prompt context)
    lexicon_summary = ""
    if LEXICON_FILE.exists():
        with open(LEXICON_FILE, encoding="utf-8") as f:
            lexicon = json.load(f)
        n_entries = lexicon.get("total_entries", 0)
        print(f"  Lexicon:        {n_entries} entries")
        # Include top entries as context
        entries = lexicon.get("entries", [])[:30]
        if entries:
            lex_lines = ["Key correspondences from the lexicon:"]
            for e in entries:
                lex_lines.append(
                    f"  {e['natural_term']} → "
                    f"{e['spiritual_correspondence']}"
                )
            lexicon_summary = "\n".join(lex_lines)
    else:
        print("  Lexicon:        not yet available")

    # Format corpus
    corpus_text = format_corpus_for_composition(
        core_pages, reading_pages, restored_pages
    )
    print(f"  Corpus size:    {len(corpus_text):,} chars")

    if args.dry_run:
        print("\n[DRY RUN] No API calls made.")
        return

    # Call LLM
    client, deployment = create_client()
    print(f"\n  Deployment: {deployment}")
    print(f"  Effort: {args.effort}")
    print("\n  Composing structure...", flush=True)

    user_parts = [
        f"## Complete Teaching Corpus ({len(core_pages)} pages)",
        "",
        "Segments marked ¶ have scribal break_after (structural boundary).",
        "Lines with → are spiritual readings (context only).",
        "",
        corpus_text,
    ]
    if lexicon_summary:
        user_parts.extend(["", "---", "", lexicon_summary])
    user_parts.extend([
        "",
        "Read the entire corpus and determine its true structure. "
        "Call commit_structure with the complete architectural schema.",
    ])

    user_msg = "\n".join(user_parts)

    result = stream_tool_call(
        client,
        deployment,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
        tools=[COMPOSE_TOOL],
        tool_name="commit_structure",
        effort=args.effort,
        max_tokens=64_000,
        page_label="structure",
        debug=args.debug,
    )

    if result is None:
        print("\nFAILED: No structure output.")
        sys.exit(1)

    # Save
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    n_units = result.get("total_units", len(result.get("units", [])))
    n_excluded = len(result.get("excluded_segments", []))
    print(
        f"\nStructure complete: {n_units} teaching units, "
        f"{n_excluded} excluded segments"
    )
    print(f"  Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
