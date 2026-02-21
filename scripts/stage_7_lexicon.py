#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a coherent natural↔spiritual correspondence lexicon from the corpus.

Pipeline phase:  stage_6_review  ->  stage_7_lexicon  ->  stage_8_compose

Feeds the complete interleaved corpus (core text + spiritual readings)
to Claude Opus 4.6 in a single prompt. The model reads the entire
narrative holistically and extracts every natural↔spiritual mapping
present in the text, then harmonizes them into a single coherent
lexicon.

The key problem this solves: spiritual readings were produced
per-chapter in earlier pipeline stages. The same natural term may
have been rendered slightly differently across chapters because each
reading was independent. This script reads ALL readings together and
determines the MOST CONSISTENT spiritual meaning for each natural
term across the full corpus.

The output is a structured lexicon where each entry maps a natural
term to its optimal spiritual correspondence, with evidence from
specific passages, notes on variant readings, and confidence level.

Primary model: Claude Opus 4.6 via Azure AI Foundry (AnthropicFoundry).

Usage:
    python stage_7_lexicon.py --project kephalaia [--debug] [--dry-run]
"""

import json
from pathlib import Path

from tools.corpus_base import CorpusAnalysisBase

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert in the doctrine of correspondences as written by \
Emanuel Swedenborg, with deep specialization in ancient cosmological \
vocabulary — Zoroastrian, Manichaean, and Persian-Iranian traditions.

You have been given the COMPLETE teaching substrate of the Coptic \
Kephalaia — both the extracted teaching core (oldest layer) and a \
correspondential reading (translation from natural into spiritual \
sense) of most passages.

The text is presented as a continuous flow of numbered paragraphs. \
Each paragraph has a marker [§N]. Lines marked [§N]* are the \
correspondential reading of that same paragraph — translation from \
the text's natural sense into its spiritual sense.

YOUR TASK: Build a comprehensive, coherent LEXICON of every \
natural↔spiritual correspondence present in this corpus.

CRITICAL METHODOLOGY:

The spiritual readings were produced per-chapter in an earlier \
pipeline stage. Each chapter was processed independently. This \
means the SAME natural term may have been rendered into slightly \
different spiritual vocabulary across different chapters. For \
example, "light" might be rendered as "wisdom" in one chapter and \
"divine truth" in another; "fire" might appear as "love" in one \
place and "celestial love" in another.

Your job is to read ALL the natural text and ALL the spiritual \
readings together, identify every natural term that carries a \
correspondential meaning, and determine the SINGLE MOST CONSISTENT \
and OPTIMAL spiritual rendering for each term across the entire \
corpus.

Where readings diverge, you must adjudicate: which spiritual \
rendering best captures the correspondential function of the \
natural term as it operates throughout the WHOLE text? The answer \
should be the one that is most internally consistent with the \
text's own architecture and with the doctrine of correspondences.

WHAT TO EXTRACT:

1. COSMOLOGICAL ENTITIES — Named beings, powers, and cosmic figures \
   (e.g. "First Man," "Living Spirit," "Third Ambassador," \
   "Father of Greatness," "Light Mind," "Jesus the Splendour"). \
   These are the major actors. Map each to its spiritual function.

2. COSMIC ELEMENTS & SUBSTANCES — The five lights, five darks, \
   elements, earths, waters, fires, winds, smokes, etc. Map each \
   to its spiritual correspondence.

3. STRUCTURAL TERMS — Aeons, realms, vessels, ships, wheels, \
   pillars, columns, gates, portals, bonds, seals. Map each to \
   its spiritual architecture meaning.

4. BODY & ANATOMY — Body parts, organs, limbs, senses as they \
   appear in the body-cosmos correspondence system. Map each to \
   its spiritual faculty.

5. NATURAL IMAGERY — Trees, fruits, seeds, garments, mountains, \
   seas, animals, metals, tastes, colors, directions. Map each \
   to its spiritual correspondence.

6. ACTIONS & PROCESSES — Purification, separation, binding, \
   liberation, ascent, descent, gathering, scattering, war, \
   combat, healing. Map each to its spiritual process.

7. QUALITIES & STATES — Light/darkness, hot/cold, sweet/bitter, \
   wet/dry, living/dead. Map each pair to its spiritual polarity.

CONSISTENCY RULES:

- Each natural term gets ONE primary spiritual meaning. If \
  context genuinely requires different senses (e.g. "fire" = \
  divine love in positive sense, self-love in negative/opposite \
  sense), record both under the SAME entry with the opposite \
  sense clearly marked.
- When the readings diverge, prefer the rendering that is: \
  (a) most frequent across the corpus, (b) most consistent \
  with the term's FUNCTION in context, (c) most aligned with \
  Swedenborg's established correspondences.
- Group related terms: if "light," "radiance," "splendour," and \
  "luminous" all correspond to the same spiritual reality, they \
  should be grouped or cross-referenced.
- Note variant readings that you did NOT choose, with brief \
  explanation of why.

When you have completed the lexicon, call the commit_lexicon tool \
once with the complete result. Be exhaustive — every natural term \
that carries correspondential weight in this text should appear."""

# ---------------------------------------------------------------------------
# Tool definition
# ---------------------------------------------------------------------------

COMMIT_LEXICON_TOOL = {
    "name": "commit_lexicon",
    "description": (
        "Commit the complete correspondence lexicon. Call this exactly "
        "once with the full result of your analysis."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "entries": {
                "type": "array",
                "description": (
                    "Every lexicon entry, organized by category."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "integer",
                            "description": (
                                "Sequential entry number."
                            ),
                        },
                        "category": {
                            "type": "string",
                            "enum": [
                                "cosmological_entity",
                                "cosmic_element",
                                "structural_term",
                                "body_anatomy",
                                "natural_imagery",
                                "action_process",
                                "quality_state",
                            ],
                            "description": (
                                "The category of correspondence."
                            ),
                        },
                        "natural_term": {
                            "type": "string",
                            "description": (
                                "The natural term as it appears in "
                                "the core text (Layer 1). Use the "
                                "most common form."
                            ),
                        },
                        "natural_variants": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Other forms of the same natural "
                                "term found in the text (alternate "
                                "spellings, shortened forms, titles)."
                            ),
                        },
                        "spiritual_meaning": {
                            "type": "string",
                            "description": (
                                "The PRIMARY spiritual correspondence "
                                "— the single most consistent and "
                                "optimal rendering across the full "
                                "corpus."
                            ),
                        },
                        "opposite_sense": {
                            "type": "string",
                            "description": (
                                "The OPPOSITE spiritual sense, if "
                                "applicable. E.g. fire = divine love "
                                "(positive) vs. self-love/destructive "
                                "passion (negative). Empty string if "
                                "no opposite sense applies."
                            ),
                        },
                        "definition": {
                            "type": "string",
                            "description": (
                                "A concise definition of WHY this "
                                "natural term corresponds to this "
                                "spiritual meaning — grounded in the "
                                "term's FUNCTION, not arbitrary "
                                "assignment."
                            ),
                        },
                        "section_refs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Key § references where this "
                                "correspondence is most clearly "
                                "demonstrated. Use '§N' or '§N–§M'."
                            ),
                        },
                        "frequency": {
                            "type": "string",
                            "enum": [
                                "pervasive",
                                "frequent",
                                "moderate",
                                "sparse",
                            ],
                            "description": (
                                "How often this term appears in the "
                                "corpus. 'pervasive' = throughout; "
                                "'frequent' = many chapters; "
                                "'moderate' = several chapters; "
                                "'sparse' = a few passages only."
                            ),
                        },
                        "confidence": {
                            "type": "string",
                            "enum": [
                                "established",
                                "strong",
                                "moderate",
                                "tentative",
                            ],
                            "description": (
                                "Confidence in this mapping. "
                                "'established' = Swedenborg confirms "
                                "and text is fully consistent; "
                                "'strong' = text is consistent and "
                                "mapping is clear; 'moderate' = good "
                                "evidence but some ambiguity; "
                                "'tentative' = plausible but variant "
                                "readings exist."
                            ),
                        },
                        "variant_readings": {
                            "type": "array",
                            "description": (
                                "Alternative spiritual renderings "
                                "found in the per-chapter readings "
                                "that were NOT chosen as primary."
                            ),
                            "items": {
                                "type": "object",
                                "properties": {
                                    "reading": {
                                        "type": "string",
                                        "description": (
                                            "The variant spiritual "
                                            "rendering."
                                        ),
                                    },
                                    "section_refs": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": (
                                            "Where this variant "
                                            "appears."
                                        ),
                                    },
                                    "reason_not_chosen": {
                                        "type": "string",
                                        "description": (
                                            "Why this variant was "
                                            "not selected as the "
                                            "primary rendering."
                                        ),
                                    },
                                },
                                "required": [
                                    "reading",
                                    "section_refs",
                                    "reason_not_chosen",
                                ],
                            },
                        },
                        "related_entries": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": (
                                "IDs of related lexicon entries "
                                "(e.g. cognate terms, polarity "
                                "pairs, terms in the same five-fold "
                                "system)."
                            ),
                        },
                        "notes": {
                            "type": "string",
                            "description": (
                                "Any additional observations about "
                                "this correspondence — its role in "
                                "the five-fold architecture, "
                                "connections to Zoroastrian source "
                                "vocabulary, Swedenborgian parallels, "
                                "or corpus-level patterns."
                            ),
                        },
                    },
                    "required": [
                        "id",
                        "category",
                        "natural_term",
                        "natural_variants",
                        "spiritual_meaning",
                        "opposite_sense",
                        "definition",
                        "section_refs",
                        "frequency",
                        "confidence",
                        "variant_readings",
                        "related_entries",
                        "notes",
                    ],
                },
            },
            "summary": {
                "type": "object",
                "description": (
                    "High-level summary of the lexicon."
                ),
                "properties": {
                    "total_entries": {
                        "type": "integer",
                        "description": "Total lexicon entries.",
                    },
                    "by_category": {
                        "type": "object",
                        "description": (
                            "Count of entries per category."
                        ),
                    },
                    "consistency_assessment": {
                        "type": "string",
                        "description": (
                            "Overall assessment of how consistent "
                            "the spiritual readings are across the "
                            "corpus. Where do the per-chapter "
                            "readings converge well? Where do they "
                            "diverge most? What patterns of "
                            "divergence are systematic vs. random?"
                        ),
                    },
                    "five_fold_systems": {
                        "type": "string",
                        "description": (
                            "Summary of the five-fold correspondence "
                            "systems identified — which sets of five "
                            "map to which other sets, and how they "
                            "interlock."
                        ),
                    },
                    "key_findings": {
                        "type": "string",
                        "description": (
                            "Notable discoveries from the lexicon "
                            "analysis — terms whose correspondence "
                            "was surprising, systematic patterns "
                            "not visible at chapter level, or "
                            "places where the text's own "
                            "architecture reveals correspondences "
                            "that the individual readings missed."
                        ),
                    },
                },
                "required": [
                    "total_entries",
                    "by_category",
                    "consistency_assessment",
                    "five_fold_systems",
                    "key_findings",
                ],
            },
        },
        "required": ["entries", "summary"],
    },
}


# ---------------------------------------------------------------------------
# Script
# ---------------------------------------------------------------------------


class BuildLexicon(CorpusAnalysisBase):
    """Build a coherent natural↔spiritual correspondence lexicon."""

    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT

    @property
    def tools(self) -> list[dict]:
        return [COMMIT_LEXICON_TOOL]

    @property
    def expected_tool_name(self) -> str:
        return "commit_lexicon"

    @property
    def default_output_filename(self) -> str:
        return "correspondence_lexicon.json"

    @property
    def thinking_budget(self) -> int:
        # Needs substantial thinking to harmonize across 886 paragraphs
        return 100_000

    def process_result(
        self, tool_input: dict | None, text_output: str
    ) -> dict:
        if tool_input is None:
            return {
                "entries": [],
                "summary": {
                    "total_entries": 0,
                    "by_category": {},
                    "consistency_assessment": text_output or "No entries.",
                    "five_fold_systems": "",
                    "key_findings": "",
                },
                "text_output": text_output,
            }

        entries = tool_input.get("entries", [])
        summary = tool_input.get("summary", {})

        # Category icons for display
        cat_icons = {
            "cosmological_entity": "👤",
            "cosmic_element": "🔥",
            "structural_term": "🏛️",
            "body_anatomy": "🫀",
            "natural_imagery": "🌿",
            "action_process": "⚡",
            "quality_state": "☯️",
        }

        # Confidence icons
        conf_icons = {
            "established": "🟢",
            "strong": "🔵",
            "moderate": "🟡",
            "tentative": "⚪",
        }

        # Print entries grouped by category
        by_cat: dict[str, list] = {}
        for e in entries:
            cat = e.get("category", "unknown")
            by_cat.setdefault(cat, []).append(e)

        for cat in [
            "cosmological_entity",
            "cosmic_element",
            "structural_term",
            "body_anatomy",
            "natural_imagery",
            "action_process",
            "quality_state",
        ]:
            group = by_cat.get(cat, [])
            if not group:
                continue
            icon = cat_icons.get(cat, "·")
            label = cat.replace("_", " ").title()
            print(f"\n  {icon} {label} ({len(group)} entries)")
            for e in group:
                conf = conf_icons.get(e.get("confidence", ""), "·")
                nat = e["natural_term"]
                spi = e["spiritual_meaning"]
                opp = e.get("opposite_sense", "")
                freq = e.get("frequency", "")
                variants = e.get("variant_readings", [])
                v_count = f" [{len(variants)} variants]" if variants else ""
                opp_str = f"  (opp: {opp})" if opp else ""
                print(
                    f"    {conf} {nat} → {spi}{opp_str}"
                    f"  ({freq}){v_count}"
                )

        # Print summary stats
        print(f"\n  Total entries: {summary.get('total_entries', len(entries))}")
        by_cat_counts = summary.get("by_category", {})
        if by_cat_counts:
            parts = [f"{k}: {v}" for k, v in by_cat_counts.items()]
            print(f"  By category: {', '.join(parts)}")

        tool_input["text_output"] = text_output
        return tool_input

    def save_result(self, result: dict, output_path: Path) -> None:
        # Attach section map for cross-referencing
        result["_section_map"] = [
            {"ms_chapter": ch, "section_start": s, "section_end": e}
            for ch, s, e in self.section_map
        ]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        entries = result.get("entries", [])
        summary = result.get("summary", {})

        print(f"\nLexicon saved to: {output_path}")
        print(f"  Total entries: {len(entries)}")

        # Category breakdown
        cats: dict[str, int] = {}
        for e in entries:
            cats[e["category"]] = cats.get(e["category"], 0) + 1
        if cats:
            print("  By category:")
            for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
                print(f"    {cat}: {count}")

        # Confidence breakdown
        confs: dict[str, int] = {}
        for e in entries:
            confs[e["confidence"]] = confs.get(e["confidence"], 0) + 1
        if confs:
            print("  By confidence:")
            for conf, count in sorted(confs.items(), key=lambda x: -x[1]):
                print(f"    {conf}: {count}")

        # Variant statistics
        total_variants = sum(
            len(e.get("variant_readings", [])) for e in entries
        )
        entries_with_variants = sum(
            1 for e in entries if e.get("variant_readings")
        )
        if total_variants:
            print(
                f"  Entries with variant readings: "
                f"{entries_with_variants}/{len(entries)}"
            )
            print(f"  Total variant readings recorded: {total_variants}")

        # Print key findings
        findings = summary.get("key_findings", "")
        if findings:
            print(f"\n  Key findings: {findings[:400]}...")


if __name__ == "__main__":
    BuildLexicon(
        description="Correspondence Lexicon"
    ).run()
