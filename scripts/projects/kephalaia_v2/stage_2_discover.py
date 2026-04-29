#!/usr/bin/env python3
"""
Discover text-critical metadata from the translated corpus.

Pipeline stage 2: runs AFTER stage_1_translate.py, BEFORE stage_3_score.py.

Feeds the complete translated corpus (all English translations from
pages/p_NNN.json) to Claude in a single prompt. The model reads the
entire text holistically and produces structured metadata that DIRECTLY
DRIVES the automated scoring pipeline:

  - Scoring vocabularies (per layer) — term→weight dicts consumed by
    stage_3_score.py for automated segment-level layer classification
  - Seam detection data — bridge phrases and institutional terms consumed
    by stage_3_score.py for editorial seam flagging

This is a corpus-scale stage (single LLM call, no per-page iteration).
It uses create_client() + stream_tool_call() from pipeline_base directly.

Output: output/projects/kephalaia_v2/corpus_metadata.json

The output is consumed by stage_3_score.py and stage_4_extract.py.

Usage:
    python scripts/projects/kephalaia_v2/stage_2_discover.py
    python scripts/projects/kephalaia_v2/stage_2_discover.py --dry-run
    python scripts/projects/kephalaia_v2/stage_2_discover.py --debug
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
    PAGES_DIR,
)


# ---------------------------------------------------------------------------
# System prompt — ported from v1 stage_2_discover.py
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert in the textual criticism of ancient composite texts, \
with deep specialization in the correspondential tradition — the science \
of describing spiritual realities through their natural expressions. You \
have mastered Swedenborg's doctrine of correspondences, the Persian and \
Zoroastrian mēnōg/gētīg ontology, Manichaean cosmology, and the textual \
transmission of what Swedenborg called "the Ancient Word."

You have been given the COMPLETE TEXT of the Coptic Kephalaia of the \
Teacher in English translation. The text is organized by manuscript pages \
(marked with === PAGE N === headers) and within each page by sequentially \
numbered line segments [§N]. This is our own translation from the Coptic \
manuscript — it has not been through any extraction pipeline. Every line \
of the original manuscript is present (with lacunae noted).

## YOUR TASK

Read the ENTIRE corpus as a text-critical expert and produce structured \
metadata that will DIRECTLY DRIVE an automated extraction pipeline. \
Your output will be loaded by Python scripts that:

1. **Score each segment** against your vocabulary lists using substring \
   matching. The function `score_text(text, markers)` lowercases both \
   the text and each marker key, counts occurrences of each marker as \
   a substring, multiplies by weight, and normalizes per 100 words. \
   Your vocabulary must be precise enough for this — exact terms, \
   meaningful weights.

2. **Detect editorial seams** at structural boundaries using your bridge \
   phrases and institutional terms. The code checks the first segment of \
   each structural unit for bridge phrase matches, counts institutional \
   term occurrences, and combines these with register-shift detection to \
   flag probable editorial extensions.

3. **Provide context** to a per-page LLM extraction pass. Your vocabulary \
   and patterns tell the extraction LLM what markers to weight in its \
   classification decisions.

Everything you output must be EXACT, PARSEABLE, and COMPUTATIONALLY \
USEFUL. Vague descriptions are useless. Precise terms with correct \
weights are essential.

## THE TEXT AND WHAT WE ARE LOOKING FOR

This text is a composite document — assembled over centuries by \
compilers who added, framed, extended, and adapted older source \
material. Multiple temporal layers are present, but we do not \
prescribe what they are. YOUR TASK is to read the actual text and \
discover how many distinct layers it contains, what they are, and \
what diagnostic vocabulary marks each. Let the text itself determine \
the taxonomy.

### THE RESEARCH TARGET: THE SUBSTRATE

What we are specifically looking for is the **oldest layer** — \
a systematic cosmological-correspondential teaching that predates \
the editorial compilation. This is the Persian and Bene Qedem \
substrate: the remnant of what Swedenborg called "the Ancient Word," \
a pre-literary correspondential science preserved in the East \
("Great Tartary"). In the Zoroastrian tradition this manifests as \
the mēnōg/gētīg ontology; in the Kephalaia it surfaces as impersonal \
cosmological-correspondential mapping.

The substrate has a distinctive quality: **both sides of every \
mapping stay within the cosmic system**. It maps domain onto domain, \
being onto being, degree onto degree — and never reaches outside \
the system.

- Substrate: "The King of the worlds of Wind is eagle-face" — realm → \
  zoomorphic form (both sides cosmic)
- Substrate: "His body is iron" — realm → metal (both sides cosmic)
- NOT substrate: "His spirit is the one of idolatry... in every \
  temple" — one side reaches into the editor's contemporary world

The substrate voice is: impersonal, structural, systematic, \
process-oriented — "how things work." It expounds directly. It does \
not cite authorities, address audiences, or exhort behavior.

Note: "Jesus the Splendour" and "Jesus the Youth" are COSMIC figures \
in the substrate — they function within the cosmological system. \
Their presence does NOT signal a later editorial layer.

### EVERYTHING ELSE

Beyond the substrate, this text contains editorial layers added by \
the compiling community. We do NOT tell you what those layers are. \
Read the text and discover them. You may find dialogue framing, \
institutional material, devotional additions, application/exhortation, \
or other voices. The number, boundaries, and character of these \
layers is for YOU to determine from the text itself.

## WHAT TO EXTRACT

### 1. SCORING VOCABULARIES

Identify the distinct temporal layers present in this corpus. For \
EACH layer you discover, provide a scoring vocabulary — a dictionary \
of diagnostic terms and their integer weights (1–5).

**YOU decide:**
- How many layers there are
- What to call them (short snake_case IDs)
- What vocabulary is diagnostic for each

The composition history above gives you GUIDANCE on what kinds of \
layers to look for. Use it as a starting point, but let the text \
itself determine the final taxonomy. If two described layers are not \
distinguishable as separate strata in this text, merge them. If you \
find a layer that doesn't match any description above, add it.

These dictionaries will be loaded directly into Python as \
`dict[str, int]` and used by `score_text()` which does \
case-insensitive substring matching.

**CRITICAL**: Terms must be EXACT as they appear in the translation. \
Multi-word phrases are valid and highly desirable — "once again the \
enlightener speaks" is far more diagnostic than just "enlightener". \
Include both multi-word phrases and single diagnostic words.

**Weight scale**:
  5 = highly diagnostic, nearly always signals this category
  4 = strong signal, rarely appears outside this category
  3 = moderate signal, sometimes shared across categories
  2 = weak signal, often shared
  1 = very weak, needs co-occurrence with other markers

For each layer, provide:
- A short **id** (snake_case, used as dict key in scoring output)
- A human-readable **name**
- A **description** of what this layer captures and how you identified it
- A **markers** dict of diagnostic terms with integer weights 1–5

The substrate/core teaching layer will likely need the richest \
vocabulary (80+ terms). Later editorial layers may need fewer.

### 2. SEAM DETECTION

**Bridge phrases**: Phrases that appear at the START of segments \
and signal editorial extension of a preceding sequence. These are \
segment-initial connectives that editors used to graft their material \
onto the original teaching. Provide the EXACT phrase as it typically \
appears at the segment start. Examples: "now, moreover", \
"furthermore, also", "and moreover". The consuming code will build \
regex from these (anchoring to segment start, handling optional \
commas and flexible whitespace).

**Institutional terms**: Terms whose presence signals institutional \
content — church offices, organizational structures, institutional \
categories. Include the exact terms as lowercase strings. These are \
checked via simple substring matching in segment text.

## OUTPUT REQUIREMENTS

- Scoring vocabulary terms: EXACT text as in translation (matching is \
  case-insensitive)
- Weights: integers 1–5 only
- This output drives Python code. Precision matters more than \
  completeness.

When you have completed your analysis, call commit_metadata once with \
the complete structured output."""


# ---------------------------------------------------------------------------
# Tool definition — ported from v1
# ---------------------------------------------------------------------------

COMMIT_METADATA_TOOL = {
    "name": "commit_metadata",
    "description": (
        "Commit the complete text-critical metadata extracted from "
        "the corpus. Call this exactly once with all findings."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "scoring_vocabularies": {
                "type": "array",
                "description": (
                    "Scoring vocabularies — one entry per category. "
                    "Each entry has an 'id' (category key used in "
                    "scoring output) and 'markers' (term→weight dict "
                    "consumed by score_text())."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": (
                                "Category identifier (snake_case) "
                                "used as dict key in scoring output. "
                                "You determine these IDs based on the "
                                "layers you discover in the text."
                            ),
                        },
                        "name": {
                            "type": "string",
                            "description": (
                                "Human-readable category name."
                            ),
                        },
                        "description": {
                            "type": "string",
                            "description": (
                                "What this scoring category captures."
                            ),
                        },
                        "markers": {
                            "type": "object",
                            "additionalProperties": {
                                "type": "integer",
                            },
                            "description": (
                                "Term → weight mapping. Keys are exact "
                                "terms as they appear in the corpus "
                                "text. Values are diagnostic weights "
                                "1–5. Multi-word phrases are valid."
                            ),
                        },
                    },
                    "required": ["id", "name", "markers"],
                },
            },
            "seam_detection": {
                "type": "object",
                "description": (
                    "Data for automated editorial seam detection at "
                    "structural boundaries."
                ),
                "properties": {
                    "bridge_phrases": {
                        "type": "array",
                        "description": (
                            "Phrases appearing at segment starts "
                            "that signal editorial bridge extensions. "
                            "Code will build regex from these."
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "phrase": {
                                    "type": "string",
                                    "description": (
                                        "Exact phrase as it appears "
                                        "at segment start."
                                    ),
                                },
                                "reliability": {
                                    "type": "string",
                                    "enum": [
                                        "high",
                                        "moderate",
                                        "low",
                                    ],
                                    "description": (
                                        "How reliably this phrase "
                                        "signals a seam."
                                    ),
                                },
                                "note": {
                                    "type": "string",
                                    "description": "Brief note.",
                                },
                            },
                            "required": ["phrase", "reliability"],
                        },
                    },
                    "institutional_terms": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Terms signaling institutional content. "
                            "Exact text, lowercase. Used for "
                            "substring matching."
                        ),
                    },
                },
                "required": [
                    "bridge_phrases",
                    "institutional_terms",
                ],
            },
            "summary": {
                "type": "object",
                "description": "High-level summary.",
                "properties": {
                    "total_scoring_terms": {
                        "type": "integer",
                        "description": (
                            "Total terms across all scoring "
                            "vocabularies."
                        ),
                    },
                    "total_bridge_phrases": {
                        "type": "integer",
                    },
                    "total_institutional_terms": {
                        "type": "integer",
                    },
                    "corpus_substrate_estimate": {
                        "type": "integer",
                        "description": (
                            "Estimated overall substrate "
                            "percentage (0–100)."
                        ),
                    },
                    "assessment": {
                        "type": "string",
                        "description": (
                            "Overall assessment of text-critical "
                            "character and strongest signals."
                        ),
                    },
                },
                "required": [
                    "total_scoring_terms",
                    "corpus_substrate_estimate",
                    "assessment",
                ],
            },
        },
        "required": [
            "scoring_vocabularies",
            "seam_detection",
            "summary",
        ],
    },
}


# ---------------------------------------------------------------------------
# Corpus assembly — reads translated pages
# ---------------------------------------------------------------------------

def load_translated_pages() -> list[dict]:
    """Load all translated page JSONs from the pages directory.

    Returns a list of dicts sorted by page number, each containing:
      - page_num: int
      - lines: list of line segment dicts
      - header: header dict
    """
    pages = []
    for path in sorted(PAGES_DIR.glob("p_*.json")):
        m = re.match(r"p_(\d+)\.json", path.name)
        if not m:
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        pages.append({
            "page_num": int(m.group(1)),
            "lines": data.get("lines", []),
            "header": data.get("header", {}),
        })
    pages.sort(key=lambda x: x["page_num"])
    return pages


def format_corpus(pages: list[dict]) -> str:
    """Format all translated pages into a single corpus text.

    Each page gets a === PAGE N === header. Within each page, each
    line segment gets a [§N] marker (sequential across the whole corpus).

    Uses the ENGLISH translations for scoring discovery (the LLM
    will derive English diagnostic vocabulary).
    """
    parts: list[str] = []
    seq = 0

    for page in pages:
        page_num = page["page_num"]
        header = page["header"]

        parts.append(f"=== PAGE {page_num} ===")

        # Include header translation if present
        title_en = header.get("title_english")
        if title_en:
            seq += 1
            parts.append(f"[§{seq}] [HEADER] {title_en}")

        # Line segments
        for seg in page["lines"]:
            english = seg.get("english")
            if english is None:
                continue  # Skip null (destroyed) lines
            seq += 1
            break_mark = " [BREAK]" if seg.get("break_after") else ""
            parts.append(f"[§{seq}]{break_mark} {english}")

        parts.append("")  # Blank line between pages

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Result processing — ported from v1
# ---------------------------------------------------------------------------

def process_result(tool_input: dict | None) -> dict:
    """Process and display the metadata result."""
    if tool_input is None:
        print("ERROR: No tool call received.")
        return {}

    vocabs = tool_input.get("scoring_vocabularies", [])
    seam = tool_input.get("seam_detection", {})
    summary = tool_input.get("summary", {})

    print("\n--- Scoring Vocabularies ---")
    for v in vocabs:
        markers = v.get("markers", {})
        print(f"  {v['id']}: {len(markers)} terms")
        # Show top-5 by weight
        top = sorted(markers.items(), key=lambda x: x[1], reverse=True)[:5]
        for term, weight in top:
            print(f"    [{weight}] {term}")

    bridge = seam.get("bridge_phrases", [])
    inst = seam.get("institutional_terms", [])
    print(f"\n--- Seam Detection ---")
    print(f"  Bridge phrases: {len(bridge)}")
    for b in bridge[:5]:
        print(f"    [{b.get('reliability', '?')}] \"{b['phrase']}\"")
    if len(bridge) > 5:
        print(f"    ... and {len(bridge) - 5} more")
    print(f"  Institutional terms: {len(inst)}")
    for t in inst[:10]:
        print(f"    · {t}")
    if len(inst) > 10:
        print(f"    ... and {len(inst) - 10} more")

    if summary:
        print(f"\n--- Summary ---")
        print(f"  Scoring terms: {summary.get('total_scoring_terms', '?')}")
        print(f"  Bridge phrases: {summary.get('total_bridge_phrases', '?')}")
        print(
            f"  Institutional terms: "
            f"{summary.get('total_institutional_terms', '?')}"
        )
        print(
            f"  Corpus substrate: "
            f"{summary.get('corpus_substrate_estimate', '?')}%"
        )

    return tool_input


# ---------------------------------------------------------------------------
# CLI + main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Discover text-critical metadata from the translated corpus "
            "(single LLM call, corpus-scale)"
        )
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Show thinking output and verbose logging",
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true",
        help="Show corpus statistics without calling the API",
    )
    args = parser.parse_args()

    print("Stage 2: Discover")
    print("  Text-critical metadata extraction (corpus-scale)")
    print(f"  Input:  {PAGES_DIR}")
    print(f"  Output: {PROJECT_DIR / 'corpus_metadata.json'}")

    # Load translated pages
    pages = load_translated_pages()
    if not pages:
        print(f"\nERROR: No translated pages found in {PAGES_DIR}")
        sys.exit(1)
    print(f"\nLoaded {len(pages)} translated pages")

    # Format corpus
    corpus_text = format_corpus(pages)
    est_tokens = len(corpus_text) / 3.5
    total_segments = sum(
        len(p["lines"]) for p in pages
    )
    print(f"  Corpus: {len(corpus_text):,} chars (~{est_tokens:,.0f} tokens)")
    print(f"  Total segments: {total_segments}")
    print(f"  Pages: {pages[0]['page_num']}-{pages[-1]['page_num']}")

    if args.dry_run:
        print(f"\n  % of 200K limit: ~{est_tokens / 2000:.1f}%")
        print(f"\n--- Sample (first 1000 chars) ---")
        print(corpus_text[:1000])
        print("--- end sample ---")
        print("\n[DRY RUN] No API call made.")
        return

    # Create client
    print("\nConnecting to Claude...")
    client, deployment = create_client()

    # Build messages
    messages = [
        {"role": "user", "content": corpus_text},
    ]

    # Stream
    print(f"\nStreaming analysis (this may take several minutes)...\n")
    t0 = time.time()
    tool_input = stream_tool_call(
        client,
        deployment,
        system=SYSTEM_PROMPT,
        messages=messages,
        tools=[COMMIT_METADATA_TOOL],
        tool_name="commit_metadata",
        page_label="corpus",
        debug=args.debug,
    )
    elapsed = time.time() - t0
    print(f"\nAnalysis completed in {elapsed:.1f}s")

    # Process
    result = process_result(tool_input)
    if not result:
        print("FAILED: No metadata extracted.")
        sys.exit(1)

    # Save
    output_path = PROJECT_DIR / "corpus_metadata.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # Count totals
    vocab_total = sum(
        len(v.get("markers", {}))
        for v in result.get("scoring_vocabularies", [])
    )
    print(f"\nMetadata saved to: {output_path}")
    print(f"  Scoring terms: {vocab_total}")


if __name__ == "__main__":
    main()
