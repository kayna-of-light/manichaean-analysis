#!/usr/bin/env python3
"""
Advisory review of teaching-level extraction, readings, and restorations.

Pipeline stage 7: runs AFTER stage_6_restore.py, before downstream
synthesis. This stage is ADVISORY: its output informs but does not bind.

Feeds one or more complete teachings to Claude in a single prompt. The
model reviews for:
- Naming overlays or residual editorial material still in core text
- Over-stripped passages where genuine substrate may have been removed
- Misplaced content or inconsistent extraction across teachings
- Whole-reading problems in the Stage 5 spiritual explanation
- Restoration-quality problems in the Stage 6 lacuna decisions
- Cross-teaching patterns visible only at corpus scale
- Deeper transmission layers visible through Persian vocabulary

Input:
    - output/projects/kephalaia_v2/teachings/t_NNN.json
    - output/projects/kephalaia_v2/readings/t_NNN.json
    - output/projects/kephalaia_v2/restored/t_NNN.json

Output:
    - output/projects/kephalaia_v2/review.json for a full run
    - output/projects/kephalaia_v2/review_tNNN.json or review_sample.json for
        selected teaching runs

Usage:
        python scripts/projects/kephalaia_v2/stage_7_review.py
        python scripts/projects/kephalaia_v2/stage_7_review.py --dry-run
        python scripts/projects/kephalaia_v2/stage_7_review.py --page 12 --debug
        python scripts/projects/kephalaia_v2/stage_7_review.py --range 1-10
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

TEACHINGS_DIR = PROJECT_DIR / "teachings"
READINGS_DIR = PROJECT_DIR / "readings"
RESTORED_DIR = PROJECT_DIR / "restored"
DEFAULT_OUTPUT_FILE = PROJECT_DIR / "review.json"


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
            "total_teachings_reviewed": {
                "type": "integer",
                "description": "Number of teachings in the review corpus.",
            },
            "scope": {
                "type": "string",
                "description": (
                    "Short description of the review scope, e.g. "
                    "'all teachings' or 'teaching 12 smoke test'."
                ),
            },
            "overall_assessment": {
                "type": "string",
                "description": (
                    "High-level assessment of extraction quality. "
                    "Are the teachings coherent as teaching units? "
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
                                "cross_teaching_pattern",
                                "transmission_layer",
                                "reading_quality",
                                "restoration_quality",
                                "schema_artifact",
                            ],
                            "description": "Category of finding.",
                        },
                        "teachings": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": (
                                "Teaching numbers affected by this finding."
                            ),
                        },
                        "sections": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": (
                                "Section numbers affected, if specific."
                            ),
                        },
                        "gaps": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": (
                                "Gap IDs affected, if this concerns "
                                "restoration quality."
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
                        "type", "teachings", "sections", "gaps",
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
                            "description": "Deprecated; use teachings.",
                        },
                        "teachings": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Relevant teachings.",
                        },
                    },
                    "required": ["observation", "teachings"],
                },
            },
        },
        "required": [
            "total_teachings_reviewed", "scope", "overall_assessment",
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

You have been given teaching-level outputs from the Coptic Kephalaia \
pipeline. Each teaching may include core Coptic/English text, notes on \
material removed during extraction, a whole-teaching correspondential \
reading, and lacuna restoration decisions.

Your task is REVIEW — reading the entire corpus holistically to \
identify problems that local processing cannot catch. Do not assume \
anything about earlier pipeline stages beyond what is explicitly shown \
in the prompt.

## WHAT TO LOOK FOR

1. **Naming overlays**: Manichaean editorial names still present in \
    text classified as core substrate. E.g., "the Apostle of Light" is \
    a Manichaean title for Mani — if it appears in core text, it may \
    have been missed by extraction.

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

6. **Cross-teaching patterns**: Teaching sequences that span multiple \
    teaching units. Do the transitions work? Are structural units coherent?

7. **Transmission layers**: Evidence of Persian/Iranian vocabulary or \
   concepts visible through the Coptic translation. These are not \
   problems — they are observations about the text's prehistory.

8. **Reading quality**: Where the whole-teaching reading overclaims, \
    misses the obvious spiritual arc, imports a system not present in \
    the text, or contradicts the Coptic/English core.

9. **Restoration quality**: Where gap restorations seem inconsistent \
    with the surrounding teaching, visible traces, Coptic grammar, or \
    corpus-scale context. Do not penalize honest non-restoration. Do \
    flag restored gaps whose English fill is empty or merely a fragment \
    if that makes the restoration unusable for review.

## OUTPUT

Produce a structured review with:
- Overall assessment of extraction quality
- Individual findings categorized with teaching, section, and gap IDs
- Structural observations visible at teaching or corpus scale

This review is ADVISORY. The human will decide which findings to act on.

When complete, call commit_review exactly once."""


# ---------------------------------------------------------------------------
# Corpus assembly
# ---------------------------------------------------------------------------

def load_all_teachings(directory: Path) -> dict[int, dict]:
    """Load all teaching JSONs from a directory, keyed by teaching number."""
    teachings = {}
    for path in sorted(directory.glob("t_*.json")):
        match = re.match(r"t_(\d+)\.json", path.name)
        if not match:
            continue
        teaching_num = int(match.group(1))
        with open(path, encoding="utf-8") as f:
            teachings[teaching_num] = json.load(f)
    return teachings


def parse_range(range_text: str) -> list[int]:
    """Parse a CLI range like 1-10 into teaching numbers."""
    match = re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*", range_text)
    if not match:
        raise ValueError(f"Invalid range '{range_text}'. Use START-END.")
    start = int(match.group(1))
    end = int(match.group(2))
    if start > end:
        raise ValueError(f"Invalid range '{range_text}': start > end.")
    return list(range(start, end + 1))


def select_teaching_numbers(
    available: list[int],
    *,
    teaching: int | None = None,
    range_text: str | None = None,
    limit: int | None = None,
) -> list[int]:
    """Apply CLI selection flags to available teaching numbers."""
    if teaching is not None and range_text is not None:
        raise ValueError("Use --teaching/--page or --range, not both.")

    available_set = set(available)
    if teaching is not None:
        selected = [teaching]
    elif range_text:
        selected = parse_range(range_text)
    else:
        selected = list(available)

    missing = [num for num in selected if num not in available_set]
    if missing:
        raise ValueError(
            "Selected teachings are unavailable: "
            + ", ".join(str(num) for num in missing)
        )

    if limit is not None:
        if limit < 1:
            raise ValueError("--limit must be >= 1")
        selected = selected[:limit]

    return selected


def shorten(text: str | None, limit: int = 260) -> str:
    """Trim long note text for compact prompt formatting."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", str(text)).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def default_output_file(selected: list[int], all_count: int) -> Path:
    """Choose a safe output path for full vs sample reviews."""
    if len(selected) == all_count:
        return DEFAULT_OUTPUT_FILE
    if len(selected) == 1:
        return PROJECT_DIR / f"review_t{selected[0]:03d}.json"
    first = selected[0]
    last = selected[-1]
    if selected == list(range(first, last + 1)):
        return PROJECT_DIR / f"review_t{first:03d}-t{last:03d}.json"
    return PROJECT_DIR / "review_sample.json"


def format_restoration_decision(restoration: dict) -> str:
    """Format one Stage 6 restoration decision compactly."""
    gap_id = restoration.get("gap_id", "?")
    section = restoration.get("section", "?")
    confidence = restoration.get("confidence", "?")
    coptic = restoration.get("proposed_coptic") or ""
    english = restoration.get("proposed_english") or ""
    basis = shorten(restoration.get("basis"), 220)

    parts = [f"gap {gap_id}", f"section {section}", f"confidence={confidence}"]
    if coptic:
        parts.append(f"coptic={coptic}")
    if english:
        parts.append(f"english={english}")
    if basis:
        parts.append(f"basis={basis}")
    return " | ".join(parts)


def format_corpus_for_review(
    teaching_numbers: list[int],
    teachings: dict[int, dict],
    readings: dict[int, dict],
    restorations_by_teaching: dict[int, dict],
) -> str:
    """Format the entire corpus into a single review prompt."""
    parts = []

    for teaching_num in teaching_numbers:
        teaching = teachings[teaching_num]
        reading = readings.get(teaching_num, {})
        restored = restorations_by_teaching.get(teaching_num, {})
        title = teaching.get("title", "")

        parts.append(f"=== Teaching {teaching_num}: {title} ===")
        parts.append(f"Extraction confidence: {teaching.get('confidence', '')}")

        parts.append("\n## Core Text")
        for segment in teaching.get("segments", []):
            if segment.get("classification") not in (
                "cosmological_substrate", "mixed",
            ):
                continue
            coptic = segment.get("core_coptic") or ""
            english = segment.get("core_english") or ""
            if not (coptic or english):
                continue
            section = segment.get("section")
            chapter = segment.get("chapter")
            line = segment.get("line")
            classification = segment.get("classification", "")
            parts.append(
                f"[t{teaching_num}:s{section} ch.{chapter}.{line} "
                f"{classification}]"
            )
            if coptic:
                parts.append(f"Coptic: {coptic}")
            if english:
                parts.append(f"English: {english}")
            removed = shorten(segment.get("removed_material"), 220)
            if removed:
                parts.append(f"Removed note: {removed}")
            temporal = shorten(segment.get("temporal_note"), 220)
            if temporal:
                parts.append(f"Temporal note: {temporal}")
            parts.append("")

        parts.append("## Whole-Teaching Correspondential Reading")
        if reading.get("title"):
            parts.append(f"Reading title: {reading.get('title')}")
        if reading.get("arc"):
            parts.append(f"Arc: {reading.get('arc')}")
        if reading.get("reading"):
            parts.append(reading.get("reading", ""))
        images = reading.get("major_images") or []
        if images:
            parts.append("Major images:")
            for image in images:
                parts.append(
                    f"- {image.get('image')}: {image.get('meaning')}"
                )
        if not reading:
            parts.append("No reading file found for this teaching.")

        parts.append("\n## Stage 6 Restoration Decisions")
        total = restored.get("total_gaps_in_core", 0)
        restored_count = restored.get("gaps_restored", 0)
        unrestorable_count = restored.get("gaps_unrestorable", 0)
        parts.append(
            f"Total gaps: {total}; restored: {restored_count}; "
            f"unrestorable: {unrestorable_count}"
        )
        note = shorten(restored.get("restoration_note"), 500)
        if note:
            parts.append(f"Restoration note: {note}")
        decisions = restored.get("restorations", [])
        if decisions:
            for decision in decisions:
                parts.append(f"- {format_restoration_decision(decision)}")
        else:
            parts.append("No restoration file or no restoration decisions found.")

        parts.append("")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# CLI & Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage 7: Advisory teaching-level corpus review"
    )
    parser.add_argument("--dry-run", "-n", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--teaching", "--page", dest="teaching", type=int,
        help="Review a single teaching number (alias --page kept for pipeline consistency).",
    )
    parser.add_argument(
        "--range", dest="range_text",
        help="Review an inclusive teaching range, e.g. 1-10.",
    )
    parser.add_argument(
        "--limit", type=int,
        help="Review only the first N selected teachings.",
    )
    parser.add_argument(
        "--output", type=Path,
        help="Output JSON path. Relative paths are resolved under the project directory.",
    )
    parser.add_argument(
        "--effort", default="max",
        choices=["low", "medium", "high", "xhigh", "max"],
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("Stage 7: Advisory Review")
    print("  Teaching-level review of extraction + reading + restoration quality")

    # Load all data
    teachings = load_all_teachings(TEACHINGS_DIR)
    readings = load_all_teachings(READINGS_DIR)
    restorations_by_teaching = load_all_teachings(RESTORED_DIR)

    if not teachings:
        print(f"\nERROR: No teachings in {TEACHINGS_DIR}")
        sys.exit(1)

    try:
        selected = select_teaching_numbers(
            sorted(teachings.keys()),
            teaching=args.teaching,
            range_text=args.range_text,
            limit=args.limit,
        )
    except ValueError as exc:
        print(f"\nERROR: {exc}")
        sys.exit(1)

    output_file = args.output or default_output_file(selected, len(teachings))
    if not output_file.is_absolute():
        output_file = PROJECT_DIR / output_file

    print(f"  Output: {output_file}")

    if output_file.exists() and not args.overwrite:
        print("\n  Review already exists (use --overwrite)")
        return

    missing_readings = [num for num in selected if num not in readings]
    missing_restored = [
        num for num in selected if num not in restorations_by_teaching
    ]

    print(f"\n  Teachings:      {len(teachings)} available")
    print(f"  Readings:       {len(readings)} available")
    print(f"  Restorations:   {len(restorations_by_teaching)} available")
    print(f"  Selected:       {len(selected)} teaching(s)")
    if missing_readings:
        print(
            "  WARNING: Missing readings for: "
            + ", ".join(str(num) for num in missing_readings)
        )
    if missing_restored:
        print(
            "  WARNING: Missing restorations for: "
            + ", ".join(str(num) for num in missing_restored)
        )

    # Format corpus
    corpus_text = format_corpus_for_review(
        selected, teachings, readings, restorations_by_teaching
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

    if len(selected) == len(teachings):
        scope = "all teachings"
    elif len(selected) == 1:
        scope = f"teaching {selected[0]}"
    else:
        scope = f"teachings {selected[0]}-{selected[-1]}"

    user_msg = (
        f"## Review Scope: {scope}\n\n"
        f"Selected teachings: {', '.join(str(num) for num in selected)}\n\n"
        f"{corpus_text}\n\n"
        f"Review this corpus holistically. Look for extraction, reading, "
        f"and restoration artifacts, inconsistencies, and structural patterns. "
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
        page_label=scope,
        debug=args.debug,
    )

    if result is None:
        print("\nFAILED: No review output.")
        sys.exit(1)

    # Save
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    n_findings = len(result.get("findings", []))
    n_observations = len(result.get("structural_observations", []))
    print(
        f"\nReview complete: {n_findings} findings, "
        f"{n_observations} structural observations"
    )
    print(f"  Output: {output_file}")


if __name__ == "__main__":
    main()
