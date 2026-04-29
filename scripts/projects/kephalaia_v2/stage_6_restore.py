#!/usr/bin/env python3
"""
Bilingual restoration of lacunae in core teaching segments.

Pipeline stage 6: runs AFTER stage_5_read.py, BEFORE stage_7_review.py.

This stage uses the correspondential reading (Stage 4) as semantic
context to propose restorations for gaps ({N} placeholders) in the
core teaching. Each restoration includes:
- Proposed Coptic
- Proposed English
- Basis (why this reading: spiritual context, traces, parallels)
- Confidence level

Only gaps in CORE segments (substrate/mixed) are restored.
Non-core gaps are irrelevant to the teaching and skipped.

Input:
  - output/projects/kephalaia_v2/pages/p_NNN.json    (translation)
  - output/projects/kephalaia_v2/core/p_NNN.json     (extraction)
  - output/projects/kephalaia_v2/readings/p_NNN.json (reading)

Output:
  - output/projects/kephalaia_v2/restored/p_NNN.json

Usage:
    python scripts/projects/kephalaia_v2/restore.py
    python scripts/projects/kephalaia_v2/restore.py --page 35
    python scripts/projects/kephalaia_v2/restore.py --range 10-50
    python scripts/projects/kephalaia_v2/restore.py --dry-run
    python scripts/projects/kephalaia_v2/restore.py --max-concurrency 4
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_base import (
    PipelineStage,
    PAGES_DIR,
    PROJECT_DIR,
)

CORE_DIR = PROJECT_DIR / "core"
READINGS_DIR = PROJECT_DIR / "readings"


# ---------------------------------------------------------------------------
# Tool schema
# ---------------------------------------------------------------------------

RESTORE_TOOL = {
    "name": "commit_restorations",
    "description": (
        "Commit all proposed gap restorations for this page. "
        "Call exactly once."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "page": {
                "type": "integer",
                "description": "The manuscript page number.",
            },
            "total_gaps_in_core": {
                "type": "integer",
                "description": (
                    "Total {N} placeholders found in core segments."
                ),
            },
            "gaps_restored": {
                "type": "integer",
                "description": (
                    "Number of gaps for which a restoration is "
                    "proposed (may be less than total if some are "
                    "unrestorable)."
                ),
            },
            "gaps_unrestorable": {
                "type": "integer",
                "description": (
                    "Gaps with insufficient context for restoration."
                ),
            },
            "restoration_note": {
                "type": "string",
                "description": (
                    "Brief assessment of overall restoration "
                    "confidence. Any patterns or challenges?"
                ),
            },
            "restorations": {
                "type": "array",
                "description": (
                    "Proposed restorations for each gap in core "
                    "segments."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "gap_id": {
                            "type": "integer",
                            "description": (
                                "The apparatus ID matching {N} in text."
                            ),
                        },
                        "segment_i": {
                            "type": "integer",
                            "description": (
                                "The segment index containing this gap."
                            ),
                        },
                        "proposed_coptic": {
                            "type": ["string", "null"],
                            "description": (
                                "Proposed Coptic restoration. Null if "
                                "unrestorable."
                            ),
                        },
                        "proposed_english": {
                            "type": ["string", "null"],
                            "description": (
                                "Proposed English restoration. Null if "
                                "unrestorable."
                            ),
                        },
                        "basis": {
                            "type": "string",
                            "description": (
                                "Why this reading is proposed: "
                                "spiritual context from the reading, "
                                "surviving letter traces (partial), "
                                "parallel passages, grammatical "
                                "constraints, formulaic patterns."
                            ),
                        },
                        "confidence": {
                            "type": "string",
                            "enum": [
                                "high", "moderate", "low", "unrestorable",
                            ],
                            "description": (
                                "'high' = strong constraints determine "
                                "the reading. 'moderate' = good fit but "
                                "alternatives possible. 'low' = best "
                                "guess only. 'unrestorable' = insufficient "
                                "context."
                            ),
                        },
                    },
                    "required": [
                        "gap_id", "segment_i",
                        "proposed_coptic", "proposed_english",
                        "basis", "confidence",
                    ],
                },
            },
        },
        "required": [
            "page", "total_gaps_in_core", "gaps_restored",
            "gaps_unrestorable", "restoration_note", "restorations",
        ],
    },
}


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert in the doctrine of correspondences as written by \
Emanuel Swedenborg, with deep specialization in ancient cosmological \
vocabulary — Zoroastrian, Manichaean, and Persian-Iranian traditions. \
You are also an expert Coptologist specializing in the Lycopolitan \
(sub-Achmimic) dialect.

You are restoring lacunae in the oldest teaching substrate of the \
Coptic Kephalaia. The text has gaps marked with numbered placeholders \
{0}, {1}, etc. Your task is to fill these gaps using:

1. **The correspondential reading** — a spiritual-sense translation that \
   shows WHAT spiritual reality each passage describes. The gaps appear \
   in the reading at their natural positions, anchoring the spiritual \
   context to the physical gap.

2. **The apparatus** — which tells you the TYPE of each gap:
   - **lacuna** (est_chars): text is physically lost. You know \
     approximately how many characters are missing.
   - **restoration** (coptic, english, basis): an editor already \
     proposed a reading. REVIEW it through the correspondential lens. \
     Confirm if it fits the spiritual sense, or propose a better word.

3. **Surviving traces** — when the apparatus includes "partial" text, \
   these are visible letter fragments that constrain the restoration.

4. **Grammatical constraints** — Coptic morphology limits what can fit. \
   A gap after ⲡ- must be a masculine singular noun. A gap after ⲉ- \
   must be an infinitive or circumstantial clause.

## RESTORATION METHOD

For each gap in a core segment:

1. Find the gap in the spiritual reading → understand what spiritual \
   reality belongs at this position
2. Check the apparatus → know the gap type, size, and any traces
3. Translate the spiritual reality BACK into the text's own vocabulary — \
   the natural-plane language of the Kephalaia
4. Verify: does the Coptic form fit grammatically? Does the character \
   count match est_chars? Do surviving traces match?
5. If multiple candidates exist, choose the one most consistent with \
   the teaching's register and the specific correspondential pattern

## COPTIC CONSTRAINTS

- Lycopolitan dialect (sub-Achmimic): ⲁ for Sahidic ⲟ, ⲉⲓ for Sahidic ⲏ
- Greek loanwords are common for technical terms
- Status constructus forms are common before nouns
- The definite article system: ⲡ-/ⲧ-/ⲛ- (m/f/pl)
- Conjugation bases: ⲁϥ- (past), ϥ- (present), ⲉϥⲉ- (future)

## RULES

1. **Bilingual output required.** Every restoration must include BOTH \
   proposed Coptic and proposed English.
2. **Character count matters.** For lacunae with est_chars, your Coptic \
   restoration should approximately match the character count.
3. **Traces constrain.** When partial text is given, your restoration \
   must include those visible letters at the correct position.
4. **Editor restorations are not sacred.** When the apparatus includes \
   a "restoration" type entry, the editor proposed a reading. Review it. \
   If it fits the spiritual sense, confirm it. If the spiritual reading \
   suggests something better, propose the better word with explanation.
5. **Unrestorable is honest.** If a gap has no constraining context \
   (isolated lacuna, no surrounding text, no reading), mark it as \
   unrestorable rather than guessing.
6. **Keep the register.** The teaching uses specific cosmic vocabulary — \
   do not substitute generic words when a specific cosmic term exists.
7. **Preserve {N} placeholders** in your thinking but fill them in the \
   output. The proposed_coptic and proposed_english fields contain the \
   FILL only, not the placeholder marker.

When complete, call commit_restorations exactly once."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_gaps_in_core(
    page_data: dict, core_data: dict,
) -> list[dict]:
    """Find all gaps (apparatus entries) that fall in core segments.

    Returns a list of apparatus entries whose segment is classified
    as substrate or mixed in the core extraction.
    """
    # Which segments are core?
    core_segments = set()
    for seg in core_data.get("segments", []):
        if seg.get("classification") in ("substrate", "mixed"):
            core_segments.add(seg["i"])

    # Filter apparatus to core segments only
    apparatus = page_data.get("apparatus", [])
    core_gaps = []
    for entry in apparatus:
        seg_i = entry.get("segment")
        if isinstance(seg_i, int) and seg_i in core_segments:
            core_gaps.append(entry)
        elif seg_i == "header":
            # Headers can be core too — include if any header content
            # was classified as core (rare but possible)
            pass

    return core_gaps


# ---------------------------------------------------------------------------
# Stage implementation
# ---------------------------------------------------------------------------

class RestoreStage(PipelineStage):
    stage_name = "Restore Lacunae"
    stage_number = 5
    description = "Bilingual gap-filling using correspondential context"
    tool_name = "commit_restorations"
    tool_schema = RESTORE_TOOL

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def get_input_dir(self) -> Path:
        return READINGS_DIR

    def get_output_dir(self) -> Path:
        return PROJECT_DIR / "restored"

    def list_available(self) -> list[int]:
        """Pages with readings output."""
        pages = []
        for path in sorted(READINGS_DIR.glob("p_*.json")):
            m = re.match(r"p_(\d+)\.json", path.name)
            if m:
                pages.append(int(m.group(1)))
        return pages

    def build_user_message(self, page_num: int) -> str:
        """Load page + core + reading and format prompt."""
        page_data = self.load_page_json(page_num, PAGES_DIR)
        core_data = self.load_page_json(page_num, CORE_DIR)
        reading_data = self.load_page_json(page_num, READINGS_DIR)

        if page_data is None:
            print(f"  ERROR: No page data for p.{page_num}")
            return None
        if core_data is None:
            print(f"  ERROR: No core data for p.{page_num}")
            return None
        if reading_data is None:
            print(f"  ERROR: No reading data for p.{page_num}")
            return None

        # Find gaps in core segments
        core_gaps = find_gaps_in_core(page_data, core_data)

        if not core_gaps:
            # No gaps in core — nothing to restore
            return None

        parts = [
            f"## Page {page_num} — Lacuna Restoration",
            f"({len(core_gaps)} gaps in core segments)",
            "",
        ]

        # Section 1: Core text with gaps highlighted
        parts.append("### Core Teaching Text (with gaps)")
        parts.append("")

        core_segments = {
            s["i"]: s for s in core_data.get("segments", [])
            if s.get("classification") in ("substrate", "mixed")
        }
        page_lines = {
            seg["i"]: seg for seg in page_data.get("lines", [])
        }

        for i in sorted(core_segments.keys()):
            seg = core_segments[i]
            orig = page_lines.get(i, {})
            coptic = seg.get("core_coptic") or orig.get("coptic") or ""
            english = seg.get("core_english") or orig.get("english") or ""
            parts.append(f"[i={i}] Coptic: {coptic}")
            parts.append(f"        English: {english}")
            parts.append("")

        # Section 2: Apparatus for core gaps
        parts.append("### Apparatus (gaps in core only)")
        parts.append("")
        for entry in core_gaps:
            gap_id = entry["id"]
            seg_i = entry.get("segment", "?")
            gap_type = entry["type"]
            if gap_type == "lacuna":
                est = entry.get("est_chars", "?")
                partial = entry.get("partial", "")
                parts.append(
                    f"  {{{gap_id}}} seg={seg_i} LACUNA ~{est}ch"
                    + (f" traces: '{partial}'" if partial else "")
                )
            else:
                cop = entry.get("coptic", "")
                eng = entry.get("english", "")
                basis = entry.get("basis", "")
                parts.append(
                    f"  {{{gap_id}}} seg={seg_i} RESTORATION: "
                    f"{cop} = '{eng}' (basis: {basis})"
                )
        parts.append("")

        # Section 3: Spiritual reading
        parts.append("### Correspondential Reading")
        parts.append("")
        reading_segs = {
            s["i"]: s for s in reading_data.get("segments", [])
        }
        for i in sorted(core_segments.keys()):
            if i in reading_segs:
                r = reading_segs[i]
                parts.append(f"[i={i}] {r.get('spiritual_sense', '')}")
                parts.append("")

        parts.append(
            "Restore each gap using the spiritual reading as context. "
            "Call commit_restorations with all proposed fills."
        )

        return "\n".join(parts)

    def process_result(self, page_num: int, result: dict) -> dict:
        """Pass through the raw result."""
        return result

    def format_summary(self, page_num: int, result: dict) -> str:
        """Format a one-line summary."""
        total = result.get("total_gaps_in_core", 0)
        restored = result.get("gaps_restored", 0)
        unrestorable = result.get("gaps_unrestorable", 0)
        return (
            f"OK — {restored}/{total} restored, "
            f"{unrestorable} unrestorable"
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    stage = RestoreStage()
    stage.run()
