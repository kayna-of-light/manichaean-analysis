#!/usr/bin/env python3
"""
Build a coherent natural↔spiritual correspondence lexicon.

Pipeline stage 8: runs AFTER stage_7_review.py, BEFORE stage_9_compose.py.

Feeds the complete corpus (core segments + spiritual readings) to
Claude in a single prompt. The model reads all readings together and
extracts every natural↔spiritual mapping, harmonizing per-page
readings into a single coherent lexicon.

The key problem: spiritual readings were produced per-page independently.
The same natural term may have been rendered differently across pages.
This stage determines the MOST CONSISTENT spiritual meaning for each
term across the full corpus.

Input:
  - output/projects/kephalaia_v2/core/p_NNN.json     (all)
  - output/projects/kephalaia_v2/readings/p_NNN.json  (all)

Output:
  - output/projects/kephalaia_v2/lexicon.json

Usage:
    python scripts/projects/kephalaia_v2/lexicon.py
    python scripts/projects/kephalaia_v2/lexicon.py --dry-run
    python scripts/projects/kephalaia_v2/lexicon.py --debug
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
OUTPUT_FILE = PROJECT_DIR / "lexicon.json"


# ---------------------------------------------------------------------------
# Tool schema
# ---------------------------------------------------------------------------

LEXICON_TOOL = {
    "name": "commit_lexicon",
    "description": (
        "Commit the complete correspondence lexicon. Call exactly once."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "total_entries": {
                "type": "integer",
                "description": "Number of entries in the lexicon.",
            },
            "methodology_note": {
                "type": "string",
                "description": (
                    "Brief note on methodology: how were entries "
                    "selected? What principles governed harmonization?"
                ),
            },
            "entries": {
                "type": "array",
                "description": (
                    "The correspondence lexicon. Each entry maps "
                    "a natural term to its spiritual correspondence."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "natural_term": {
                            "type": "string",
                            "description": (
                                "The natural-plane term as it appears "
                                "in the Kephalaia (English)."
                            ),
                        },
                        "coptic_form": {
                            "type": ["string", "null"],
                            "description": (
                                "The Coptic form if identifiable."
                            ),
                        },
                        "spiritual_correspondence": {
                            "type": "string",
                            "description": (
                                "The spiritual reality this term "
                                "corresponds to."
                            ),
                        },
                        "basis": {
                            "type": "string",
                            "description": (
                                "Why this correspondence holds: "
                                "function of the natural object, "
                                "Swedenborg reference, textual usage."
                            ),
                        },
                        "occurrences": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": (
                                "Page numbers where this term appears "
                                "in the core teaching."
                            ),
                        },
                        "opposite_sense": {
                            "type": ["string", "null"],
                            "description": (
                                "The opposite-sense reading (if the "
                                "term appears in both positive and "
                                "negative contexts). Null if only one "
                                "sense is attested."
                            ),
                        },
                        "variant_readings": {
                            "type": ["string", "null"],
                            "description": (
                                "Any per-page variation in how this "
                                "was read. Null if consistent."
                            ),
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["established", "strong", "probable", "uncertain"],
                            "description": (
                                "'established' = confirmed by Swedenborg "
                                "and consistently used. 'strong' = clear "
                                "functional basis. 'probable' = good fit. "
                                "'uncertain' = possible but ambiguous."
                            ),
                        },
                        "domain": {
                            "type": "string",
                            "enum": [
                                "element", "animal", "body", "metal",
                                "plant", "celestial", "geographic",
                                "faculty", "sense", "substance", "other",
                            ],
                            "description": "Category of natural term.",
                        },
                    },
                    "required": [
                        "natural_term", "coptic_form",
                        "spiritual_correspondence", "basis",
                        "occurrences", "opposite_sense",
                        "variant_readings", "confidence", "domain",
                    ],
                },
            },
        },
        "required": [
            "total_entries", "methodology_note", "entries",
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
Kephalaia — both the extracted core (oldest teaching layer) and the \
correspondential readings (spiritual-sense translations) for each page.

## YOUR TASK

Build a comprehensive, coherent LEXICON of every natural↔spiritual \
correspondence present in this corpus.

## METHODOLOGY

1. **Read ALL spiritual readings together.** The per-page readings were \
   produced independently. The same natural term may have been rendered \
   slightly differently on different pages. Your job is to determine \
   the SINGLE BEST spiritual correspondence for each term.

2. **Harmonization principle:** When the same natural term got different \
   spiritual readings on different pages, determine which reading is:
   - Most consistent with the term's FUNCTION (correspondence is grounded \
     in what the object DOES)
   - Most consistent with Swedenborg's documented correspondences
   - Most consistent across all occurrences in this corpus

3. **Opposite sense:** Many terms have both positive and negative \
   correspondences depending on context (fire = divine love OR self-love; \
   water = truth OR falsity). Document BOTH senses when attested.

4. **Coptic forms:** Where possible, identify the Coptic word underlying \
   the English term. This anchors the correspondence to the actual text.

5. **Evidence:** For each entry, cite the pages where the term appears \
   in the core teaching. This grounds the lexicon in attestation.

6. **Confidence levels:**
   - 'established': confirmed by Swedenborg + consistently used in text
   - 'strong': clear functional basis, consistent usage
   - 'probable': good fit, limited attestation
   - 'uncertain': possible but ambiguous or single occurrence

## WHAT TO INCLUDE

- Every natural object that carries spiritual meaning in the teaching
- Cosmic geography (worlds, firmaments, spheres) → spiritual architecture
- Body parts (bone, blood, flesh) → spiritual faculties
- Metals (gold, silver, iron) → degrees of good/truth
- Animals (eagle, lion, fish) → qualities of will
- Elements (fire, water, wind, smoke, darkness) → spiritual substances
- Faculties (nous, ennoia, phronesis) → degrees of reception
- Sensory qualities (bitter, sweet, sharp) → spiritual qualities

## WHAT TO EXCLUDE

- Pure proper nouns (names of divine beings) unless they carry \
  correspondential meaning through their etymology
- Editorial vocabulary (church, catechumen, elect) — these are not \
  part of the correspondential system
- Frame formulas — not correspondential content

When complete, call commit_lexicon exactly once."""


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


def format_corpus_for_lexicon(
    core_pages: dict[int, dict],
    reading_pages: dict[int, dict],
) -> str:
    """Format the corpus as interleaved core + readings."""
    parts = []

    for page_num in sorted(core_pages.keys()):
        core = core_pages[page_num]
        reading = reading_pages.get(page_num, {})

        core_segs = [
            s for s in core.get("segments", [])
            if s.get("classification") in ("substrate", "mixed")
        ]
        reading_segs = {
            s["i"]: s for s in reading.get("segments", [])
        }

        if not core_segs:
            continue

        parts.append(f"═══ Page {page_num} ═══")

        for seg in core_segs:
            i = seg["i"]
            english = seg.get("core_english") or ""
            coptic = seg.get("core_coptic") or ""

            parts.append(f"  [p{page_num}:i{i}] {english}")
            if coptic:
                parts.append(f"    Coptic: {coptic}")
            if i in reading_segs:
                spiritual = reading_segs[i].get("spiritual_sense", "")
                if spiritual:
                    parts.append(f"    → {spiritual}")
                corrs = reading_segs[i].get("key_correspondences", [])
                if corrs:
                    corr_str = "; ".join(
                        f"{c['natural']}={c['spiritual']}" for c in corrs
                    )
                    parts.append(f"    Correspondences: {corr_str}")

        parts.append("")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# CLI & Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage 7: Build correspondence lexicon"
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

    print("Stage 7: Correspondence Lexicon")
    print("  Build coherent natural↔spiritual mapping from corpus")
    print(f"  Output: {OUTPUT_FILE}")

    if OUTPUT_FILE.exists() and not args.overwrite:
        print("\n  Lexicon already exists (use --overwrite)")
        return

    # Load data
    core_pages = load_all_pages(CORE_DIR)
    reading_pages = load_all_pages(READINGS_DIR)

    if not core_pages:
        print(f"\nERROR: No core pages in {CORE_DIR}")
        sys.exit(1)

    print(f"\n  Core pages:    {len(core_pages)}")
    print(f"  Reading pages: {len(reading_pages)}")

    # Format corpus
    corpus_text = format_corpus_for_lexicon(core_pages, reading_pages)
    print(f"  Corpus size:   {len(corpus_text):,} chars")

    if args.dry_run:
        print("\n[DRY RUN] No API calls made.")
        return

    # Call LLM
    client, deployment = create_client()
    print(f"\n  Deployment: {deployment}")
    print(f"  Effort: {args.effort}")
    print("\n  Building lexicon...", flush=True)

    user_msg = (
        f"## Complete Teaching Corpus ({len(core_pages)} pages)\n\n"
        f"{corpus_text}\n\n"
        f"Build a comprehensive correspondence lexicon from this "
        f"corpus. Call commit_lexicon with the complete lexicon."
    )

    result = stream_tool_call(
        client,
        deployment,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
        tools=[LEXICON_TOOL],
        tool_name="commit_lexicon",
        effort=args.effort,
        max_tokens=64_000,
        page_label="lexicon",
        debug=args.debug,
    )

    if result is None:
        print("\nFAILED: No lexicon output.")
        sys.exit(1)

    # Save
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    n_entries = result.get("total_entries", len(result.get("entries", [])))
    print(f"\nLexicon complete: {n_entries} entries")
    print(f"  Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
