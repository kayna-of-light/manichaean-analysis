#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analyze the full corpus for anomalies, misreadings, and missed layers.

Feeds the complete interleaved corpus (core text + spiritual readings)
to Claude Opus 4.6 in a single prompt. The model reads the entire
narrative holistically and identifies passages where:

  - The correspondential reading doesn't match the teaching substrate
  - A pre-Manichaean layer was missed or misidentified
  - Natural-plane vocabulary was left untranslated in the spiritual reading
  - The same correspondence was read inconsistently across passages
  - A deeper or older substrate (Zoroastrian, Zurvanite, proto-Iranian)
    is visible beneath the Manichaean editorial layer
  - The narrative logic breaks or a teaching sequence is interrupted

The key insight: per-chapter processing can miss patterns that only
become visible when the full narrative is read as a continuous flow.

Primary model: Claude Opus 4.6 via Azure AI Foundry (AnthropicFoundry).

Usage:
    python stage_6_review.py --project kephalaia [--debug] [--dry-run]
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
correspondential reading of that same paragraph.

CRITICAL FRAMING — You are reading this text from a pre-Manichaean \
perspective. What you have in front of you is NOT primarily a \
Manichaean scripture. It is an ancient Persian teaching text — part \
of the Eastern tradition of correspondential knowledge that predates \
Mani by centuries or millennia. The Manichaean editorial framework \
(Mani said, the disciples asked, Light-Nous, etc.) is a later \
wrapper around a much older substrate.

That older substrate is written in the LANGUAGE OF CORRESPONDENCES — \
the same language Swedenborg describes as the Ancient Word. Every \
natural image (light, darkness, fire, water, garments, trees, \
animals, mountains, seeds, vessels, body parts) corresponds to a \
spiritual reality through its actual function, not through arbitrary \
symbolism. This is the language of the mēnōg (spiritual) and gētīg \
(material) — the Zoroastrian ontology that exactly parallels \
Swedenborg's doctrine.

Your task is to read the ENTIRE text holistically and identify \
everything that is "off" — places where the correspondential reading \
(the [§N]* lines) doesn't correctly translate the teaching, where \
an older layer was missed, where inconsistencies crept in during \
per-chapter processing, or where the full narrative reveals patterns \
that single-chapter analysis could not see.

Specifically, look for:

1. MISTRANSLATIONS — Passages where the spiritual reading got the \
   correspondence wrong. The natural image was mapped to the wrong \
   spiritual reality, or a key correspondence was missed entirely.

2. INCONSISTENCIES — The same natural image (e.g. "the five trees" \
   or "the garment of light") was read differently in different \
   passages without justification. Correspondences should be \
   consistent unless opposite sense is explicitly warranted.

3. MISSED PRE-MANICHAEAN LAYERS — Passages where the spiritual \
   reading treated Manichaean editorial vocabulary (Light-Nous, \
   the Living Spirit, the Mother of Life) as original when it is \
   actually a later gloss over an older teaching. What Persian or \
   proto-Iranian reality does the Manichaean name obscure?

4. UNTRANSLATED NATURAL VOCABULARY — Natural-plane words or images \
   that were left in the spiritual reading without translation. \
   Every natural object should be replaced by its spiritual \
   correspondent.

5. NARRATIVE BREAKS — Places where the teaching sequence is \
   interrupted, where a passage seems out of order, or where a \
   chapter boundary cut through a continuous teaching unit.

6. CROSS-PASSAGE PATTERNS — Themes, teaching sequences, or \
   correspondential systems that only become visible when reading \
   the full text as a continuous flow. Things the per-chapter \
   reader couldn't see.

7. DEEPER SUBSTRATE — Evidence of layers older than the Persian \
   (proto-Indo-Iranian, Mesopotamian, or traces of the Ancient \
   Word itself) visible in the vocabulary or structure.

8. OPPOSITE SENSE ERRORS — Passages where a correspondence was \
   read in its positive sense when the context requires the \
   negative (or vice versa). Fire can be divine love OR self-love. \
   Darkness can be obscurity before illumination OR active falsity. \
   The context determines which.

When you have completed your review, call the commit_findings tool \
once with every finding. Be thorough but precise — each finding \
should cite specific § numbers and explain exactly what is wrong \
and what the correct reading should be.

Do NOT reproduce large blocks of text. Reference passages by their \
§ numbers and quote only the minimum needed to make the finding clear."""

# ---------------------------------------------------------------------------
# Tool definition
# ---------------------------------------------------------------------------

COMMIT_FINDINGS_TOOL = {
    "name": "commit_findings",
    "description": (
        "Commit all findings from the corpus review. Call this exactly "
        "once with the complete list of findings."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "description": (
                    "Every finding from the review, ordered by "
                    "severity (critical first)."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "integer",
                            "description": (
                                "Sequential finding number."
                            ),
                        },
                        "category": {
                            "type": "string",
                            "enum": [
                                "mistranslation",
                                "inconsistency",
                                "missed_pre_manichaean",
                                "untranslated_natural",
                                "narrative_break",
                                "cross_passage_pattern",
                                "deeper_substrate",
                                "opposite_sense_error",
                            ],
                            "description": (
                                "The type of finding."
                            ),
                        },
                        "severity": {
                            "type": "string",
                            "enum": [
                                "critical",
                                "significant",
                                "minor",
                                "observation",
                            ],
                            "description": (
                                "How important this finding is. "
                                "'critical' = fundamentally wrong reading. "
                                "'significant' = meaningful error that "
                                "affects interpretation. "
                                "'minor' = small issue worth correcting. "
                                "'observation' = pattern or insight, "
                                "not necessarily an error."
                            ),
                        },
                        "section_refs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "§ references for this finding. "
                                "Use format '§N' or '§N–§M' for ranges."
                            ),
                        },
                        "title": {
                            "type": "string",
                            "description": (
                                "Short title summarizing the finding."
                            ),
                        },
                        "current_reading": {
                            "type": "string",
                            "description": (
                                "What the spiritual reading currently "
                                "says (brief quote or paraphrase). "
                                "For cross_passage_pattern and "
                                "deeper_substrate findings, describe "
                                "the current state."
                            ),
                        },
                        "proposed_reading": {
                            "type": "string",
                            "description": (
                                "What it SHOULD say, or what the "
                                "correct interpretation is. For "
                                "observations, describe the pattern "
                                "or insight."
                            ),
                        },
                        "explanation": {
                            "type": "string",
                            "description": (
                                "Why this is wrong/incomplete and why "
                                "the proposed reading is better. "
                                "Reference specific correspondences, "
                                "the pre-Manichaean substrate, or "
                                "cross-passage evidence."
                            ),
                        },
                    },
                    "required": [
                        "id",
                        "category",
                        "severity",
                        "section_refs",
                        "title",
                        "current_reading",
                        "proposed_reading",
                        "explanation",
                    ],
                },
            },
            "summary": {
                "type": "object",
                "description": (
                    "High-level summary of the review."
                ),
                "properties": {
                    "total_findings": {
                        "type": "integer",
                        "description": "Total number of findings.",
                    },
                    "critical_count": {
                        "type": "integer",
                        "description": "Number of critical findings.",
                    },
                    "significant_count": {
                        "type": "integer",
                        "description": "Number of significant findings.",
                    },
                    "overall_assessment": {
                        "type": "string",
                        "description": (
                            "Overall assessment of the corpus's "
                            "correspondential reading quality — "
                            "what works well, what needs the most "
                            "attention, and the most important "
                            "patterns discovered."
                        ),
                    },
                    "pre_manichaean_assessment": {
                        "type": "string",
                        "description": (
                            "Assessment of how well the readings "
                            "penetrate through the Manichaean layer "
                            "to the older substrate. Where does the "
                            "reading succeed in seeing the Ancient "
                            "Word? Where does it still treat "
                            "Manichaean vocabulary as if it were "
                            "original?"
                        ),
                    },
                },
                "required": [
                    "total_findings",
                    "critical_count",
                    "significant_count",
                    "overall_assessment",
                    "pre_manichaean_assessment",
                ],
            },
        },
        "required": ["findings", "summary"],
    },
}


# ---------------------------------------------------------------------------
# Script
# ---------------------------------------------------------------------------


class AnalyzeCorpus(CorpusAnalysisBase):
    """Review the full corpus for anomalies and missed layers."""

    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT

    @property
    def tools(self) -> list[dict]:
        return [COMMIT_FINDINGS_TOOL]

    @property
    def expected_tool_name(self) -> str:
        return "commit_findings"

    @property
    def default_output_filename(self) -> str:
        return "corpus_review.json"

    @property
    def thinking_budget(self) -> int:
        # Give it more room to think — this is analytic, not structural
        return 80_000

    def process_result(
        self, tool_input: dict | None, text_output: str
    ) -> dict:
        if tool_input is None:
            return {
                "findings": [],
                "summary": {
                    "total_findings": 0,
                    "critical_count": 0,
                    "significant_count": 0,
                    "overall_assessment": text_output or "No findings.",
                    "pre_manichaean_assessment": "",
                },
                "text_output": text_output,
            }

        findings = tool_input.get("findings", [])
        summary = tool_input.get("summary", {})

        # Print findings as they come
        sev_icons = {
            "critical": "🔴",
            "significant": "🟠",
            "minor": "🟡",
            "observation": "🔵",
        }
        for f in findings:
            icon = sev_icons.get(f["severity"], "·")
            refs = ", ".join(f["section_refs"])
            print(
                f"  {icon} [{f['id']}] {f['category']}: "
                f"{f['title']}  ({refs})"
            )

        # Print summary
        print(
            f"\n  Total: {summary.get('total_findings', len(findings))} "
            f"findings — "
            f"{summary.get('critical_count', 0)} critical, "
            f"{summary.get('significant_count', 0)} significant"
        )

        tool_input["text_output"] = text_output
        return tool_input

    def save_result(self, result: dict, output_path: Path) -> None:
        # Attach section map for cross-referencing with ms chapters
        result["_section_map"] = [
            {"ms_chapter": ch, "section_start": s, "section_end": e}
            for ch, s, e in self.section_map
        ]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        findings = result.get("findings", [])
        summary = result.get("summary", {})

        print(f"\nReview saved to: {output_path}")
        print(f"  Total findings: {len(findings)}")

        # Category breakdown
        cats = {}
        for f in findings:
            cats[f["category"]] = cats.get(f["category"], 0) + 1
        if cats:
            print("  By category:")
            for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
                print(f"    {cat}: {count}")

        # Print overall assessment
        assessment = summary.get("overall_assessment", "")
        if assessment:
            print(f"\n  Overall: {assessment[:300]}...")


if __name__ == "__main__":
    AnalyzeCorpus(
        description="Corpus Review"
    ).run()
