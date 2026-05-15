#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Review the full corpus for extraction artifacts and structural patterns.

Feeds the complete interleaved corpus (core text + spiritual readings)
to Claude Opus 4.6 in a single prompt. The model reads the entire
narrative holistically and reviews the EXTRACTED TEXT for:

  - Naming overlays: Manichaean editorial names still in the core
  - Residual editorial material that slipped through extraction
  - Over-stripped passages: genuine substrate removed, leaving gaps
  - Misplaced content: teaching fragments from other sequences
  - Inconsistent extraction across chapters
  - Narrative breaks from chapter boundaries cutting through teaching
  - Cross-passage patterns visible only at corpus scale
  - Deeper transmission layers visible through the Persian vocabulary

The spiritual readings are included as a READING AID only — they help
the model understand the correspondential content of the text. The
review focuses on the text itself, not on the spiritual readings.

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
You are an expert in ancient cosmological vocabulary — Zoroastrian, \
Manichaean, and Persian-Iranian traditions — with deep knowledge of \
Swedenborg's doctrine of correspondences.

You have been given the COMPLETE extracted teaching substrate of the \
Coptic Kephalaia. This substrate is the oldest layer of the text — \
Persian correspondential teaching that predates Mani's editorial \
compilation. It IS the Ancient Word in its Persian vessel.

The text is presented as a continuous flow of numbered paragraphs. \
Each paragraph has a marker [§N]. Lines marked [§N]* are \
correspondential readings — translations from the natural into the \
spiritual sense. These are included as a READING AID to help you \
understand what the text is saying. They are NOT the object of your \
analysis.

YOUR FOCUS IS THE TEXT ITSELF — the extracted core paragraphs \
(the [§N] lines).

CRITICAL FRAMING:

The substrate IS the Ancient Word. You do NOT correct it. You do \
NOT suggest it should say something different. You look for \
EXTRACTION ARTIFACTS — places where the pipeline's processing \
introduced problems into what should be a clean rendering of the \
oldest teaching layer.

The text you see has already been through a multi-stage extraction \
pipeline. An earlier stage classified each paragraph as CORE \
(substrate), FRAME (editorial), PASTORAL (institutional), or \
OVERLAY (Christian addition) — and stripped everything except CORE. \
For MIXED paragraphs, the editor tried to separate substrate from \
later material within the same paragraph.

That extraction was done per-chapter. You are the first reader to \
see the ENTIRE corpus as a continuous flow. Your job is to catch \
what per-chapter processing could not:

1. NAMING OVERLAY — Manichaean editorial names still present in \
   the extracted core. Entity names like "Light-Nous," "the Mother \
   of Life," "Jesus the Splendour" are Manichaean designations \
   mapped onto cosmic entities that the substrate described \
   functionally or with older names. When these names appear in \
   the core, flag them — the substrate likely used a different \
   designation that the Manichaean editor replaced. Note: some \
   Manichaean names may genuinely translate older titles (e.g. \
   "Third Ambassador" may render a Persian mediating figure). \
   It is unlikely that all these names are rewritten so we expect \
   genuine substrate logic, however some names are clearly overlaid \
   by later traditions and should be corrected to its most probable \
   orignal substrate. Flag these and suggest the most probable name \
   that was probably used in the original substrate base on your \
   knowledge of these ancient cultures. Flag when the naming feels \
   editorial, not when it could be translation.

2. RESIDUAL EDITORIAL — Non-substrate material that was not caught \
   by the extraction stage. Bridge connectives ("And again he \
   said"), institutional vocabulary ("the catechumens," "the \
   elect"), devotional exhortations ("Blessed is he who..."), or \
   Pauline/Christian phrases that slipped through as "core" when \
   they belong to a later layer.

3. OVER-STRIPPED — Evidence that genuine substrate content was \
   REMOVED during extraction. The sign is a gap or discontinuity \
   in the teaching narrative — a correspondential sequence that \
   was developing coherently and then jumps, or a systematic \
   structure (five-fold map, body-cosmos system) that is missing \
   a position. When the teaching's own architecture demands \
   something at a position and it's not there, extraction probably \
   removed it as "frame" or "pastoral" when it was actually \
   substrate. This is perhaps the MOST IMPORTANT category — \
   lost substrate content is irrecoverable if not flagged here.

4. MISPLACED CONTENT — Text that appears to belong to a different \
   teaching sequence. An introductory summary that previews content \
   from another chapter, a teaching fragment that interrupts an \
   otherwise coherent sequence, or a passage whose correspondential \
   content doesn't match its surroundings. This can indicate the \
   Manichaean compiler moved material around.

5. INCONSISTENT EXTRACTION — The same type of content was classified \
   as CORE in one chapter but stripped out in another without \
   justification. If Q&A formulas are removed in one place but \
   kept elsewhere, that's an inconsistency. If cosmological \
   questions that set up the teaching ("Tell us about the five \
   realms") are preserved in some chapters but stripped in others, \
   flag it. The extraction criteria should have been applied \
   uniformly.

6. NARRATIVE BREAK — A teaching sequence is interrupted. This can \
   be caused by: (a) a chapter boundary cutting through a \
   continuous teaching unit, (b) editorial material that wasn't \
   fully stripped creating a seam, or (c) the compiler inserting \
   material from elsewhere into the middle of a sequence. The \
   teaching in the substrate flows as a continuous narrative — \
   breaks are artifacts of compilation or extraction.

7. CROSS-PASSAGE PATTERN — A structural pattern, teaching sequence, \
   or correspondential system that spans multiple chapters and is \
   only visible at corpus scale. Five-fold maps that develop \
   across chapters, body-cosmos systems that repeat with variation, \
   teaching arcs that the chapter boundaries obscured. These are \
   OBSERVATIONS, not errors — they reveal the teaching's original \
   organization.

8. DEEPER TRANSMISSION — The teaching substrate IS the Ancient Word \
   in its Persian vessel. This category identifies passages where \
   an OLDER cultural vessel is visible through the Persian — \
   proto-Indo-Iranian, Mesopotamian, or Zurvanite vocabulary or \
   structures that predate the specifically Zoroastrian-Persian \
   formulation. Not a different teaching, but an earlier \
   transmission layer of the same correspondential knowledge.

The spiritual readings ([§N]* lines) help you understand the \
correspondential content well enough to recognize when something \
is off in the TEXT — a gap in the narrative, an editorial name that \
doesn't fit, a passage out of place. Use them as a lens, not as \
the object of review.

When you have completed your review, call the commit_findings tool \
once with every finding. Be thorough but precise — each finding \
should cite specific § numbers and explain exactly what the issue \
is in the text.

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
                                "naming_overlay",
                                "residual_editorial",
                                "over_stripped",
                                "misplaced_content",
                                "inconsistent_extraction",
                                "narrative_break",
                                "cross_passage_pattern",
                                "deeper_transmission",
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
                                "'critical' = extraction error that "
                                "loses or corrupts substrate content. "
                                "'significant' = meaningful issue that "
                                "affects the extracted text. "
                                "'minor' = small issue worth noting. "
                                "'observation' = structural pattern or "
                                "insight, not necessarily an error."
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
                        "current_state": {
                            "type": "string",
                            "description": (
                                "What the text currently contains "
                                "(brief quote or description). For "
                                "over_stripped findings, describe the "
                                "gap or discontinuity observed."
                            ),
                        },
                        "recommendation": {
                            "type": "string",
                            "description": (
                                "What should be done — flag for "
                                "removal, restore specific content, "
                                "investigate a gap, etc. For "
                                "observations, describe the pattern "
                                "or structural insight."
                            ),
                        },
                        "explanation": {
                            "type": "string",
                            "description": (
                                "Why this is an issue and what "
                                "evidence supports the finding. "
                                "Reference the teaching's own "
                                "architecture, parallel passages, "
                                "or cross-chapter patterns."
                            ),
                        },
                    },
                    "required": [
                        "id",
                        "category",
                        "severity",
                        "section_refs",
                        "title",
                        "current_state",
                        "recommendation",
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
                            "Overall assessment of the extraction "
                            "quality — where is the substrate cleanly "
                            "extracted, where do editorial artifacts "
                            "remain, and what structural patterns "
                            "emerge at corpus scale?"
                        ),
                    },
                    "extraction_assessment": {
                        "type": "string",
                        "description": (
                            "Assessment of extraction balance — "
                            "does the pipeline tend to over-strip "
                            "(losing substrate) or under-strip "
                            "(leaving editorial)? Which chapters "
                            "or teaching types are most affected?"
                        ),
                    },
                },
                "required": [
                    "total_findings",
                    "critical_count",
                    "significant_count",
                    "overall_assessment",
                    "extraction_assessment",
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
