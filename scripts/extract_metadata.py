#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract text-critical metadata from the RAW CLEANED corpus.

Feeds the complete raw cleaned text to Claude Opus 4.6 in a single prompt.
The model reads the entire unprocessed text holistically and produces
structured metadata that **directly drives** the core extraction pipeline:

  - Scoring vocabularies (per layer) — term→weight dicts consumed by
    score_text() for automated paragraph-level layer classification
  - Seam detection data — bridge phrases and institutional terms consumed
    by detect_editorial_seams() for automated editorial seam flagging

This script operates on CLEANED data (Phase 1 output), NOT on core
extractions or correspondential readings. The metadata it produces
is the INPUT to the extraction pipeline (Phase 2).

The output is consumed DIRECTLY by extract_analysis.py and extract_core.py:
  - scoring_vocabularies  → loaded by extract_analysis.py for vocabulary scoring
  - seam_detection         → loaded by extract_analysis.py for editorial seam detection
  - scoring_vocabularies  → also used by extract_core.py for dynamic prompt/tool schema

Primary model: Claude Opus 4.6 via Azure AI Foundry (AnthropicFoundry).

Usage:
    python extract_metadata.py --project kephalaia [--debug] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from project_config import load_project
from tools.corpus_base import create_claude_client, stream_tool_call

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert in the textual criticism of ancient composite texts, \
with deep specialization in the correspondential tradition — the science \
of describing spiritual realities through their natural expressions. You \
have mastered Swedenborg's doctrine of correspondences, the Persian and \
Zoroastrian mēnōg/gētīg ontology, Manichaean cosmology, and the textual \
transmission of what Swedenborg called "the Ancient Word."

You have been given the COMPLETE RAW TEXT of the Coptic Kephalaia in \
English translation. The text is organized by manuscript chapters \
(marked with === CHAPTER N: Title === headers) and within each chapter \
by sequentially numbered paragraphs [§N]. This is the CLEANED but \
UNPROCESSED text — it has not been through any extraction pipeline. \
Every word of the original translation is present.

## YOUR TASK

Read the ENTIRE corpus as a text-critical expert and produce structured \
metadata that will DIRECTLY DRIVE an automated extraction pipeline. \
Your output will be loaded by Python scripts that:

1. **Score each paragraph** against your vocabulary lists using substring \
   matching. The function `score_text(text, markers)` lowercases both \
   the text and each marker key, counts occurrences of each marker as \
   a substring, multiplies by weight, and normalizes per 100 words. \
   Your vocabulary must be precise enough for this — exact terms, \
   meaningful weights.

2. **Detect editorial seams** at paragraph boundaries using your bridge \
   phrases and institutional terms. The code checks the first line of \
   each paragraph for bridge phrase matches, counts institutional term \
   occurrences, and combines these with register-shift detection to flag \
   probable editorial extensions.

3. **Provide chapter-level context** to a per-chapter LLM extraction \
   pass. Your chapter profiles tell the extraction LLM what to expect \
   in each chapter — which layers dominate, where seams are likely, \
   what structural patterns are present, and brief guidance.

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

**Bridge phrases**: Phrases that appear at the START of paragraphs \
and signal editorial extension of a preceding sequence. These are \
paragraph-initial connectives that editors used to graft their material \
onto the original teaching. Provide the EXACT phrase as it typically \
appears at the paragraph start. Examples: "now, moreover", \
"furthermore, also", "and moreover". The consuming code will build \
regex from these (anchoring to paragraph start, handling optional \
commas and flexible whitespace).

**Institutional terms**: Terms whose presence signals institutional \
content — church offices, organizational structures, institutional \
categories. Include the exact terms as lowercase strings. These are \
checked via simple substring matching in paragraph text.

## OUTPUT REQUIREMENTS

- Scoring vocabulary terms: EXACT text as in translation (matching is \
  case-insensitive)
- Chapter numbers: match the manuscript chapter numbers from headers
- Weights: integers 1–5 only
- This output drives Python code. Precision matters more than \
  completeness.

When you have completed your analysis, call commit_metadata once with \
the complete structured output."""

# ---------------------------------------------------------------------------
# Tool definition
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
                    "paragraph boundaries."
                ),
                "properties": {
                    "bridge_phrases": {
                        "type": "array",
                        "description": (
                            "Phrases appearing at paragraph starts "
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
                                        "at paragraph start."
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
# Data loading — reads from CLEANED chapters, not core/correspondential
# ---------------------------------------------------------------------------


def load_cleaned_chapters(
    cleaned_dir: Path,
) -> list[dict]:
    """Load raw cleaned chapter JSONs.

    Returns a list of dicts with:
      - chapter_number: int
      - title: str
      - paragraphs: list[str]  (teaching_text split by double-newline)
      - char_count: int
    """
    chapters: list[dict] = []
    for path in sorted(cleaned_dir.glob("ch_*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        text = data.get("teaching_text", "")
        if not text.strip():
            continue

        # Split into natural paragraphs (double-newline boundaries)
        paras = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]

        chapters.append({
            "chapter_number": data.get("chapter_number", 0),
            "title": data.get("title", ""),
            "paragraphs": paras,
            "char_count": len(text),
        })

    return chapters


def format_corpus_raw(
    chapters: list[dict],
) -> tuple[str, list[tuple[int, int, int]]]:
    """Format the entire raw cleaned corpus with chapter headers and
    sequentially numbered paragraphs.

    Each chapter gets a === CHAPTER N: Title === header so the model
    can identify chapter boundaries. Each
    paragraph gets a [§N] marker for cross-referencing.

    Returns:
        (corpus_text, section_map)

    The section_map is a list of (ms_chapter, §start, §end) tuples
    kept internally for post-processing.
    """
    lines: list[str] = []
    seq = 0
    section_map: list[tuple[int, int, int]] = []

    for ch in chapters:
        ch_num = ch["chapter_number"]
        ch_title = ch["title"]
        first_seq = seq + 1

        # Chapter header for model orientation
        lines.append(f"=== CHAPTER {ch_num}: {ch_title} ===")
        lines.append("")

        for para in ch["paragraphs"]:
            seq += 1
            lines.append(f"[§{seq}] {para}")
            lines.append("")

        section_map.append((ch_num, first_seq, seq))

    corpus_text = "\n".join(lines)
    return corpus_text, section_map


def print_dry_run(
    chapters: list[dict],
    corpus_text: str,
    section_map: list[tuple[int, int, int]],
) -> None:
    """Show corpus statistics without calling the API."""
    est_tokens = len(corpus_text) / 3.5

    print("\n=== DRY RUN (raw cleaned data) ===")
    print(f"Total manuscript chapters: {len(chapters)}")

    total_paras = sum(len(c["paragraphs"]) for c in chapters)
    total_chars = sum(c["char_count"] for c in chapters)
    last_seq = section_map[-1][2] if section_map else 0

    print(f"\nTotal paragraphs: {total_paras}")
    print(f"Total raw chars: {total_chars:,}")
    print(f"Sequential range: §1–§{last_seq}")

    print(f"\nFormatted corpus: {len(corpus_text):,} chars")
    print(f"Estimated tokens: ~{est_tokens:,.0f}")
    print(f"% of 200K limit: ~{est_tokens / 2000:.1f}%")

    print(f"\nSection map: {len(section_map)} entries (internal)")

    # Show chapter size distribution
    sizes = [(c["chapter_number"], len(c["paragraphs"]), c["char_count"])
             for c in chapters]
    sizes.sort(key=lambda x: x[2], reverse=True)
    print("\nTop 10 chapters by size:")
    for ch_num, n_paras, chars in sizes[:10]:
        print(f"  ch_{ch_num:03d}: {n_paras} paras, {chars:,} chars")

    print("\n--- Sample (first 800 chars) ---")
    print(corpus_text[:800])
    print("--- end sample ---")


# ---------------------------------------------------------------------------
# Script
# ---------------------------------------------------------------------------


class ExtractMetadata:
    """Extract text-critical metadata from the raw cleaned corpus."""

    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT

    @property
    def tools(self) -> list[dict]:
        return [COMMIT_METADATA_TOOL]

    @property
    def expected_tool_name(self) -> str:
        return "commit_metadata"

    @property
    def default_output_filename(self) -> str:
        return "corpus_metadata.json"

    def process_result(
        self, tool_input: dict | None, text_output: str
    ) -> dict:
        if tool_input is None:
            return {
                "scoring_vocabularies": [],
                "seam_detection": {
                    "bridge_phrases": [],
                    "institutional_terms": [],
                },
                "summary": {},
                "text_output": text_output,
            }

        # Print summary as we go
        vocabs = tool_input.get("scoring_vocabularies", [])
        seam = tool_input.get("seam_detection", {})
        summary = tool_input.get("summary", {})

        print("\n--- Scoring Vocabularies ---")
        for v in vocabs:
            markers = v.get("markers", {})
            print(f"  {v['id']}: {len(markers)} terms")
            # Show top-5 by weight
            top = sorted(
                markers.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:5]
            for term, weight in top:
                print(f"    [{weight}] {term}")

        bridge = seam.get("bridge_phrases", [])
        inst = seam.get("institutional_terms", [])
        print(f"\n--- Seam Detection ---")
        print(f"  Bridge phrases: {len(bridge)}")
        for b in bridge[:5]:
            print(
                f"    [{b.get('reliability', '?')}] "
                f"\"{b['phrase']}\""
            )
        if len(bridge) > 5:
            print(f"    ... and {len(bridge) - 5} more")
        print(f"  Institutional terms: {len(inst)}")
        for t in inst[:10]:
            print(f"    · {t}")
        if len(inst) > 10:
            print(f"    ... and {len(inst) - 10} more")

        if summary:
            print(f"\n--- Summary ---")
            print(
                f"  Scoring terms: "
                f"{summary.get('total_scoring_terms', '?')}"
            )
            print(
                f"  Bridge phrases: "
                f"{summary.get('total_bridge_phrases', '?')}"
            )
            print(
                f"  Institutional terms: "
                f"{summary.get('total_institutional_terms', '?')}"
            )
            print(
                f"  Corpus substrate: "
                f"{summary.get('corpus_substrate_estimate', '?')}%"
            )

        tool_input["text_output"] = text_output
        return tool_input

    def save_result(
        self,
        result: dict,
        output_path: Path,
        section_map: list[tuple[int, int, int]],
    ) -> None:
        # Attach section map for post-processing
        result["_section_map"] = [
            {"ms_chapter": ch, "section_start": s, "section_end": e}
            for ch, s, e in section_map
        ]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        # Count totals
        vocab_total = sum(
            len(v.get("markers", {}))
            for v in result.get("scoring_vocabularies", [])
        )
        seam = result.get("seam_detection", {})
        bridge_total = len(seam.get("bridge_phrases", []))
        inst_total = len(seam.get("institutional_terms", []))

        print(f"\nMetadata saved to: {output_path}")
        print(f"  Scoring terms: {vocab_total}")
        print(f"  Bridge phrases: {bridge_total}")
        print(f"  Institutional terms: {inst_total}")

    def run(self) -> None:
        """Parse CLI args, load cleaned data, call Claude, save result."""
        parser = argparse.ArgumentParser(
            description=(
                "Extract text-critical metadata from raw cleaned "
                "corpus"
            )
        )
        parser.add_argument(
            "--project",
            default="kephalaia",
            help="Project name (default: kephalaia)",
        )
        parser.add_argument(
            "--debug",
            action="store_true",
            help="Show thinking output and verbose logging",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show corpus statistics without calling the API",
        )
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help=(
                "Output file path "
                "(default: <project_dir>/<default_name>)"
            ),
        )
        args = parser.parse_args()

        print(
            f"=== Extract Text-Critical Metadata: "
            f"{args.project} ===\n"
        )

        # Load project config
        cfg = load_project(args.project)
        cfg.paths.ensure_dirs()
        cleaned_dir = cfg.paths.cleaned_chapters
        output_dir = cfg.paths.project_dir

        # Load cleaned chapters
        print(f"Loading cleaned chapters from: {cleaned_dir}")
        chapters = load_cleaned_chapters(cleaned_dir)
        print(f"  Loaded {len(chapters)} chapters")

        # Format raw corpus
        print(
            "\nFormatting raw corpus "
            "(chapter headers + sequential §N markers)..."
        )
        corpus_text, section_map = format_corpus_raw(chapters)
        est_tokens = len(corpus_text) / 3.5
        total_paras = sum(len(c["paragraphs"]) for c in chapters)
        last_seq = section_map[-1][2] if section_map else 0
        print(
            f"  Corpus: {len(corpus_text):,} chars "
            f"(~{est_tokens:,.0f} tokens)"
        )
        print(f"  Paragraphs: {total_paras} → §1–§{last_seq}")
        print(f"  Section map: {len(section_map)} entries (internal)")

        if args.dry_run:
            print_dry_run(chapters, corpus_text, section_map)
            return

        # Create client
        print("\nConnecting to Claude Opus 4.6...")
        client, deployment = create_claude_client()

        # Stream
        print(f"\nStreaming analysis...\n")
        t0 = time.time()
        tool_input, text_output = stream_tool_call(
            client,
            deployment,
            system_prompt=self.system_prompt,
            tools=self.tools,
            expected_tool_name=self.expected_tool_name,
            corpus_text=corpus_text,
            max_tokens=128_000,
            debug=args.debug,
        )
        elapsed = time.time() - t0
        print(f"\nAnalysis completed in {elapsed:.1f}s")

        # Process
        result = self.process_result(tool_input, text_output)

        # Save
        output_path = (
            Path(args.output) if args.output
            else output_dir / self.default_output_filename
        )
        self.save_result(result, output_path, section_map)


if __name__ == "__main__":
    ExtractMetadata().run()
