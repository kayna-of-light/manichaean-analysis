#!/usr/bin/env python3
"""
Correspondential reading of extracted core segments.

Pipeline stage 5: runs AFTER stage_4_extract.py, BEFORE stage_6_restore.py.

This stage produces a standalone spiritual reading of the core teaching
layer. It translates each segment's natural sense into its spiritual
sense via correspondences. The reading is used downstream by restore.py
as context for gap-filling — and also stands as an independent output.

The reading works on the CORE only (segments classified as substrate
or mixed by extract.py). Non-core segments are skipped.

Input:
  - output/projects/kephalaia_v2/pages/p_NNN.json   (translation)
  - output/projects/kephalaia_v2/core/p_NNN.json    (extraction)

Output:
  - output/projects/kephalaia_v2/readings/p_NNN.json

Usage:
    python scripts/projects/kephalaia_v2/read.py
    python scripts/projects/kephalaia_v2/read.py --page 35
    python scripts/projects/kephalaia_v2/read.py --range 10-50
    python scripts/projects/kephalaia_v2/read.py --dry-run
    python scripts/projects/kephalaia_v2/read.py --max-concurrency 4
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


# ---------------------------------------------------------------------------
# Tool schema
# ---------------------------------------------------------------------------

READ_TOOL = {
    "name": "commit_reading",
    "description": (
        "Commit the correspondential reading for all core segments "
        "on this page. Call exactly once."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "page": {
                "type": "integer",
                "description": "The manuscript page number.",
            },
            "segments_read": {
                "type": "integer",
                "description": "Number of core segments read.",
            },
            "reading_note": {
                "type": "string",
                "description": (
                    "Brief assessment: what spiritual system or "
                    "process does this page describe? What "
                    "correspondential pattern dominates?"
                ),
            },
            "segments": {
                "type": "array",
                "description": (
                    "Spiritual reading for each core segment."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "i": {
                            "type": "integer",
                            "description": (
                                "Segment index (matching the page JSON)."
                            ),
                        },
                        "spiritual_sense": {
                            "type": "string",
                            "description": (
                                "The spiritual reading: translate every "
                                "natural image into its correspondential "
                                "reality. Not commentary — translation. "
                                "Continuous prose. Preserve {N} gap "
                                "placeholders at their positions."
                            ),
                        },
                        "key_correspondences": {
                            "type": "array",
                            "description": (
                                "Major correspondences used in this "
                                "segment (natural → spiritual)."
                            ),
                            "items": {
                                "type": "object",
                                "properties": {
                                    "natural": {
                                        "type": "string",
                                        "description": (
                                            "The natural-plane term."
                                        ),
                                    },
                                    "spiritual": {
                                        "type": "string",
                                        "description": (
                                            "The spiritual reality."
                                        ),
                                    },
                                },
                                "required": ["natural", "spiritual"],
                            },
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["clear", "probable", "uncertain"],
                            "description": (
                                "How confidently the spiritual sense "
                                "can be read. 'clear' = straightforward "
                                "correspondence. 'probable' = good fit "
                                "with minor ambiguity. 'uncertain' = "
                                "multiple plausible readings."
                            ),
                        },
                    },
                    "required": [
                        "i", "spiritual_sense",
                        "key_correspondences", "confidence",
                    ],
                },
            },
        },
        "required": [
            "page", "segments_read", "reading_note", "segments",
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

You translate text from its natural sense into its spiritual sense. \
Not annotation, not commentary — translation. Every natural image is \
replaced by the spiritual reality it expresses through correspondence.

## THE CORRESPONDENTIAL METHOD

Correspondence is the organic relationship between a natural object \
and the spiritual reality it expresses. It is grounded in the object's \
actual function:

- **Light** → wisdom/truth (light enables the eye to distinguish forms)
- **Fire** → love/will (fire gives light its existence)
- **Darkness** → falsity/evil (absence of spiritual light)
- **Water** → truth in the natural degree (sustains natural life)
- **Wind/Air** → thought/perception (the medium of communication)
- **Smoke** → falsity from evil (obscures light)
- **Earth/Soil** → the natural mind (ground where seeds grow)
- **Mountains** → elevated spiritual states (proximity to influx)
- **Trees** → perceptions/knowledges (rooted, growing, bearing)
- **Fruits** → works/goods of life (what the tree produces)
- **Animals** → affections (each species = a quality of will)
- **Birds** → thoughts/intellectual things (move through air)
- **Seeds** → interior truths (contain the whole in potential)
- **Garments** → external truths (clothe spiritual meaning)
- **Gold** → celestial good (love)
- **Silver** → spiritual truth (wisdom)
- **Iron** → natural truth in ultimates (hard, foundational)
- **Bone** → structural good (the framework that supports)
- **Blood** → divine truth proceeding (life-giving circulation)
- **Body** → the form of love/wisdom in ultimates

## MANICHAEAN COSMOLOGICAL CORRESPONDENCES

The Kephalaia describes a cosmic system using specific vocabulary:
- **Five Worlds of Darkness** → five modes of self-love's expression
- **King of Darkness** → the ruling love of self personified
- **Five Storehouses** → five degrees of divine good stored in forms
- **Firmament (ⲥⲧⲉⲣⲉⲱⲙⲁ)** → the fixed boundary between states
- **Wheel (ⲧⲣⲟⲭⲟⲥ)** → cyclic process of purification
- **Pillar** → the axis of ascent from natural to celestial
- **Zodiac** → the complete circuit of spiritual states
- **Five Faculties (nous, ennoia, phronesis, enthymesis, logismos)** → \
  discrete degrees of reception (celestial → natural)

## THE TEXT YOU RECEIVE

The text is the oldest teaching substrate of the Coptic Kephalaia — \
pre-Manichaean cosmological teaching that maps domain onto domain, \
being onto being, degree onto degree. The teaching IS the mapping. \
It does not compare; it identifies.

You receive CORE segments only — already classified as the oldest \
teaching layer. Read each segment and produce its spiritual sense.

## RULES

1. **Translate, don't annotate.** Replace every natural image with its \
   spiritual reality. Produce continuous prose.
2. **Preserve {N} placeholders.** These mark physical gaps. Include \
   them at their positions in your spiritual reading — they anchor \
   the gap to its spiritual context for downstream restoration.
3. **When an image resists**, say so briefly and give your best reading.
4. **Opposite sense:** Fire, water, animals can be positive or negative \
   depending on context (love vs. self-love, truth vs. falsity). \
   Determine from context which sense applies.
5. **Discrete degrees:** When the text describes five faculties, \
   five worlds, five elements — read them as discrete levels of \
   reality (celestial/spiritual/natural), not a continuum.
6. **The Divine Human:** When the text describes cosmic beings with \
   body parts, faces, limbs — read them as the Grand Man: the \
   form of love and wisdom at different registers.

When complete, call commit_reading exactly once."""


# ---------------------------------------------------------------------------
# Stage implementation
# ---------------------------------------------------------------------------

class ReadStage(PipelineStage):
    stage_name = "Correspondential Reading"
    stage_number = 4
    description = "Spiritual-sense reading of core teaching segments"
    tool_name = "commit_reading"
    tool_schema = READ_TOOL

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def get_input_dir(self) -> Path:
        return CORE_DIR

    def get_output_dir(self) -> Path:
        return PROJECT_DIR / "readings"

    def list_available(self) -> list[int]:
        """Pages with core extraction output."""
        pages = []
        for path in sorted(CORE_DIR.glob("p_*.json")):
            m = re.match(r"p_(\d+)\.json", path.name)
            if m:
                pages.append(int(m.group(1)))
        return pages

    def build_user_message(self, page_num: int) -> str:
        """Load core extraction + original page and format prompt."""
        core_data = self.load_page_json(page_num, CORE_DIR)
        page_data = self.load_page_json(page_num, PAGES_DIR)

        if core_data is None:
            print(f"  ERROR: No core data for p.{page_num}")
            return None
        if page_data is None:
            print(f"  ERROR: No page data for p.{page_num}")
            return None

        # Extract only core segments (substrate + mixed)
        segments = core_data.get("segments", [])
        page_lines = {
            seg["i"]: seg for seg in page_data.get("lines", [])
        }

        core_segments = [
            s for s in segments
            if s.get("classification") in ("substrate", "mixed")
        ]

        if not core_segments:
            # No core segments — nothing to read
            return None

        parts = [
            f"## Page {page_num} — Core Teaching Segments",
            f"(Total core segments: {len(core_segments)})",
            "",
        ]

        for seg in core_segments:
            i = seg["i"]
            cls = seg["classification"]
            coptic = seg.get("core_coptic") or ""
            english = seg.get("core_english") or ""

            # Also provide original line for context
            orig = page_lines.get(i, {})
            orig_coptic = orig.get("coptic") or ""

            parts.append(f"### Segment i={i} [{cls}]")
            if coptic:
                parts.append(f"Coptic: {coptic}")
            if english:
                parts.append(f"English: {english}")
            if orig_coptic and orig_coptic != coptic:
                parts.append(f"(Full original: {orig_coptic})")
            parts.append("")

        parts.append(
            "Read each segment's spiritual sense via correspondences. "
            "Call commit_reading with the complete reading."
        )

        return "\n".join(parts)

    def process_result(self, page_num: int, result: dict) -> dict:
        """Pass through the raw result."""
        return result

    def format_summary(self, page_num: int, result: dict) -> str:
        """Format a one-line summary."""
        n = result.get("segments_read", 0)
        note = result.get("reading_note", "")
        short_note = note[:60] + "..." if len(note) > 60 else note
        return f"OK — {n} segments read: {short_note}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    stage = ReadStage()
    stage.run()
