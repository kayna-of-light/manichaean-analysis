#!/usr/bin/env python3
"""
Advisory review of the full extracted/restored corpus.

Pipeline stage 6: runs AFTER restore.py, BEFORE lexicon.py.
This stage is ADVISORY — its output informs but does not bind.

Feeds the complete corpus (all core + restored pages) to Claude in a
single prompt. The model reads the entire teaching holistically and
reviews for:
- Naming overlays: Manichaean editorial names still in core
- Residual editorial material that slipped through extraction
- Over-stripped passages: genuine substrate removed
- Misplaced content: teaching fragments from other sequences
- Inconsistent extraction across pages
- Cross-page patterns visible only at corpus scale
- Deeper transmission layers visible through Persian vocabulary

Output is a single JSON file (not per-page).

Input:
  - output/projects/kephalaia_v2/core/p_NNN.json     (all)
  - output/projects/kephalaia_v2/readings/p_NNN.json  (all)
  - output/projects/kephalaia_v2/restored/p_NNN.json  (all)

Output:
  - output/projects/kephalaia_v2/review.json

Usage:
    python scripts/projects/kephalaia_v2/review.py
    python scripts/projects/kephalaia_v2/review.py --dry-run
    python scripts/projects/kephalaia_v2/review.py --debug
"""
import argparse
import json
import re
import sys
import time
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
OUTPUT_FILE = PROJECT_DIR / "review.json"


# ---------------------------------------------------------------------------
# Tool schema
# ---------------------------------------------------------------------------

REVIEW_TOOL = {
    "name": "commit_review",
    "description": (
        "Commit the corpus-scale review findings. Call exactly once."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "total_pages_reviewed": {
                "type": "integer",
                "description": "Number of pages in the review corpus.",
            },
            "overall_assessment": {
                "type": "string",
                "description": (
                    "High-level assessment of extraction quality. "
                    "Is the core coherent as a continuous teaching? "
                    "Are there systematic problems?"
                ),
            },
            "findings": {
                "type": "array",
                "description": "Individual review findings.",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": [
                                "naming_overlay",
                                "residual_editorial",
                                "over_stripped",
                                "misplaced_content",
                                "inconsistency",
                                "cross_page_pattern",
                                "transmission_layer",
                                "restoration_quality",
                            ],
                            "description": "Category of finding.",
                        },
                        "pages": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": (
                                "Page numbers affected by this finding."
                            ),
                        },
                        "segments": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": (
                                "Segment indices affected (if specific)."
                            ),
                        },
                        "description": {
                            "type": "string",
                            "description": (
                                "What the finding is: what was observed, "
                                "what it means, what action to consider."
                            ),
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["critical", "moderate", "minor"],
                            "description": (
                                "How important is this finding? "
                                "'critical' = affects teaching integrity. "
                                "'moderate' = noticeable but not distorting. "
                                "'minor' = aesthetic or borderline."
                            ),
                        },
                        "suggestion": {
                            "type": ["string", "null"],
                            "description": (
                                "Suggested correction or action. "
                                "Null if observation only."
                            ),
                        },
                    },
                    "required": [
                        "type", "pages", "segments",
                        "description", "severity", "suggestion",
                    ],
                },
            },
            "structural_observations": {
                "type": "array",
                "description": (
                    "Observations about the teaching's structure "
                    "visible only at corpus scale."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "observation": {
                            "type": "string",
                            "description": "What was observed.",
                        },
                        "pages": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Relevant pages.",
                        },
                    },
                    "required": ["observation", "pages"],
                },
            },
        },
        "required": [
            "total_pages_reviewed", "overall_assessment",
            "findings", "structural_observations",
        ],
    },
}


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert in ancient cosmological vocabulary — Zoroastrian, \
Manichaean, and Persian-Iranian traditions — with deep knowledge of \
Swedenborg's doctrine of correspondences.

You have been given the COMPLETE extracted and restored teaching \
substrate of the Coptic Kephalaia. This substrate is the oldest \
layer of the text — Persian correspondential teaching that predates \
Mani's editorial compilation.

Your task is REVIEW — reading the entire corpus holistically to \
identify problems that per-page processing cannot catch:

## WHAT TO LOOK FOR

1. **Naming overlays**: Manichaean editorial names still present in \
   text classified as "substrate." E.g., "the Apostle of Light" is a \
   Manichaean title for Mani — if it appears in core text, it was \
   missed by extraction.

2. **Residual editorial material**: Exhortations, audience address, \
   institutional vocabulary that slipped through the layer filter.

3. **Over-stripped passages**: Places where genuine substrate teaching \
   was removed (classified as non-core) leaving a gap in the logical \
   flow. Look for narrative breaks or teaching sequences that feel \
   incomplete.

4. **Misplaced content**: Teaching fragments that belong to a different \
   sequence (cosmological digression inserted into an anatomical map, etc.)

5. **Inconsistency**: The same entity/concept treated differently on \
   different pages without justification.

6. **Cross-page patterns**: Teaching sequences that span page boundaries — \
   does the transition work? Are structural units coherent?

7. **Transmission layers**: Evidence of Persian/Iranian vocabulary or \
   concepts visible through the Coptic translation. These are not \
   problems — they are observations about the text's prehistory.

8. **Restoration quality**: Where gap restorations seem inconsistent \
   with the surrounding teaching, or where better restorations are \
   suggested by corpus-scale context.

## OUTPUT

Produce a structured review with:
- Overall assessment of extraction quality
- Individual findings (categorized, with page references)
- Structural observations about the teaching visible at corpus scale

This review is ADVISORY. The human will decide which findings to act on.

When complete, call commit_review exactly once."""


# ---------------------------------------------------------------------------
# Corpus assembly
# ---------------------------------------------------------------------------

def load_all_pages(directory: Path) -> dict[int, dict]:
    """Load all page JSONs from a directory, keyed by page number."""
    pages = {}
    for path in sorted(directory.glob("p_*.json")):
        m = re.match(r"p_(\d+)\.json", path.name)
        if m:
            page_num = int(m.group(1))
            with open(path, encoding="utf-8") as f:
                pages[page_num] = json.load(f)
    return pages


def format_corpus_for_review(
    core_pages: dict[int, dict],
    reading_pages: dict[int, dict],
    restored_pages: dict[int, dict],
) -> str:
    """Format the entire corpus into a single review prompt."""
    parts = []

    for page_num in sorted(core_pages.keys()):
        core = core_pages[page_num]
        reading = reading_pages.get(page_num, {})
        restored = restored_pages.get(page_num, {})

        parts.append(f"═══ Page {page_num} ═══")

        # Core segments
        core_segs = [
            s for s in core.get("segments", [])
            if s.get("classification") in ("substrate", "mixed")
        ]
        reading_segs = {
            s["i"]: s for s in reading.get("segments", [])
        }

        for seg in core_segs:
            i = seg["i"]
            coptic = seg.get("core_coptic") or ""
            english = seg.get("core_english") or ""
            parts.append(f"  [p{page_num}:i{i}] {english}")
            # Include spiritual reading as context
            if i in reading_segs:
                spiritual = reading_segs[i].get("spiritual_sense", "")
                if spiritual:
                    parts.append(f"    → {spiritual}")

        # Restoration summary
        restorations = restored.get("restorations", [])
        if restorations:
            filled = [
                r for r in restorations
                if r.get("confidence") != "unrestorable"
            ]
            if filled:
                parts.append(
                    f"  [{len(filled)} gaps restored on this page]"
                )

        parts.append("")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# CLI & Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage 6: Advisory corpus-scale review"
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

    print("Stage 6: Advisory Review")
    print("  Corpus-scale review of extraction + restoration quality")
    print(f"  Output: {OUTPUT_FILE}")

    if OUTPUT_FILE.exists() and not args.overwrite:
        print("\n  Review already exists (use --overwrite)")
        return

    # Load all data
    core_pages = load_all_pages(CORE_DIR)
    reading_pages = load_all_pages(READINGS_DIR)
    restored_pages = load_all_pages(RESTORED_DIR)

    if not core_pages:
        print(f"\nERROR: No core pages in {CORE_DIR}")
        sys.exit(1)

    print(f"\n  Core pages:     {len(core_pages)}")
    print(f"  Reading pages:  {len(reading_pages)}")
    print(f"  Restored pages: {len(restored_pages)}")

    # Format corpus
    corpus_text = format_corpus_for_review(
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
    print("\n  Sending corpus for review...", flush=True)

    user_msg = (
        f"## Complete Teaching Corpus ({len(core_pages)} pages)\n\n"
        f"{corpus_text}\n\n"
        f"Review this corpus holistically. Look for extraction "
        f"artifacts, inconsistencies, and structural patterns. "
        f"Call commit_review with your findings."
    )

    result = stream_tool_call(
        client,
        deployment,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
        tools=[REVIEW_TOOL],
        tool_name="commit_review",
        effort=args.effort,
        max_tokens=64_000,
        page_label="corpus",
        debug=args.debug,
    )

    if result is None:
        print("\nFAILED: No review output.")
        sys.exit(1)

    # Save
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    n_findings = len(result.get("findings", []))
    n_observations = len(result.get("structural_observations", []))
    print(
        f"\nReview complete: {n_findings} findings, "
        f"{n_observations} structural observations"
    )
    print(f"  Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
