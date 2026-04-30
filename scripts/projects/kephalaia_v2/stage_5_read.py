#!/usr/bin/env python3
"""
Correspondential reading of assembled teachings.

Pipeline stage 5: runs AFTER stage_4c_assemble.py, BEFORE stage_6_restore.py.

This stage produces a standalone spiritual reading of each teaching.
It translates the natural sense into its spiritual sense via
correspondences. The reading is used downstream by restore.py as
context for gap-filling — and also stands as an independent output.

Input:
  - output/projects/kephalaia_v2/teachings/t_NNN.json  (from stage 4c)
    - output/projects/kephalaia_v2/spiritual_lexicon.json  (from stage 4d, optional)

Output:
  - output/projects/kephalaia_v2/readings/t_NNN.json

Usage:
    python scripts/projects/kephalaia_v2/stage_5_read.py
    python scripts/projects/kephalaia_v2/stage_5_read.py --page 1
    python scripts/projects/kephalaia_v2/stage_5_read.py --range 1-20
    python scripts/projects/kephalaia_v2/stage_5_read.py --dry-run
    python scripts/projects/kephalaia_v2/stage_5_read.py --max-concurrency 4
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_base import (
    PipelineStage,
    PROJECT_DIR,
)

TEACHINGS_DIR = PROJECT_DIR / "teachings"
SPIRITUAL_LEXICON_PATH = PROJECT_DIR / "spiritual_lexicon.json"


# ---------------------------------------------------------------------------
# Tool schema
# ---------------------------------------------------------------------------

READ_TOOL = {
    "name": "commit_reading",
    "description": (
        "Commit the correspondential reading for this teaching. "
        "Call exactly once."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "teaching": {
                "type": "integer",
                "description": "The teaching number.",
            },
            "segments_read": {
                "type": "integer",
                "description": "Number of core segments read.",
            },
            "reading_note": {
                "type": "string",
                "description": (
                    "Brief assessment: what spiritual process does "
                    "this teaching describe from beginning to end? "
                    "What is the single arc?"
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
                                "Section number for this teaching segment."
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
                        "coptic_anchors": {
                            "type": "array",
                            "description": (
                                "Important Coptic words or phrases that "
                                "controlled the reading. Empty if no "
                                "specific Coptic anchor is identifiable."
                            ),
                            "items": {
                                "type": "object",
                                "properties": {
                                    "coptic": {
                                        "type": "string",
                                        "description": "The Coptic form.",
                                    },
                                    "english": {
                                        "type": "string",
                                        "description": (
                                            "The project vocabulary English "
                                            "term for this form."
                                        ),
                                    },
                                    "spiritual": {
                                        "type": "string",
                                        "description": (
                                            "The spiritual meaning used in "
                                            "the segment reading."
                                        ),
                                    },
                                },
                                "required": ["coptic", "english", "spiritual"],
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
                        "key_correspondences", "coptic_anchors", "confidence",
                    ],
                },
            },
        },
        "required": [
            "teaching", "segments_read", "reading_note", "segments",
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
- **First Man** → the divine truth sent into the realm of self-love
- **Mother of Life** → the matrix of spiritual life from which truth is born
- **Living Spirit** → the operative power that builds spiritual structure
- **Ambassador/Third Messenger** → the call that awakens trapped light
- **Jesus the Splendour** → divine truth descending to rescue what fell
- **Virgin of Light** → purity of reception; truth uncorrupted
- **Pillar of Glory** → the path of ascent that light travels home
- **Column of Glory** → accumulated truth rising from natural to celestial

## THE TEXT YOU RECEIVE

You receive a COMPLETE TEACHING — one spiritual arc from beginning to \
end. The teaching uses cosmological imagery as its vehicle, but the \
imagery is the outer shell. Inside is a spiritual process being taught.

You also receive the corpus-level spiritual lexicon when it exists. \
That lexicon controls vocabulary. Use its `use_in_reading` wording and \
spiritual meanings unless a local passage clearly requires an opposite \
sense or narrower application. Do not improvise alternative English for \
terms already fixed by the lexicon.

Read Coptic and English together. The English is helpful, but the \
Coptic controls when vocabulary matters. Preserve this project's \
translation decisions: ⲧⲥⲃⲱ is teaching, not insight; ⲡⲉⲓⲛⲉ is \
likeness; Jesus ⲡⲡⲣⲓ̈ⲉ is Jesus the Radiance.

Your job: translate the shell into what it contains. Read through the \
imagery to the spiritual reality being expressed.

## GAP ANCHORS

The text contains numbered gap placeholders like {0}, {1}, {2}. \
These are lacunae (missing text) that will be restored later using \
your spiritual reading as a guide.

As you translate each passage, PRESERVE these gap markers inline in \
your spiritual prose at the corresponding position. When you reach \
a gap, write what the spiritual sense requires at that point and \
embed the marker so a restorer can see exactly what spiritual \
reality belongs there.

Example:
  Original: "the great {3}, the battle that the Darkness spread"
  Spiritual: "the great {3} assault that falsity from evil propagated"

## RULES

1. **Translate, don't annotate.** Replace every natural image with its \
   spiritual reality. Produce continuous prose.
2. **When an image resists**, say so briefly and give your best reading.
3. **Opposite sense:** Fire, water, animals can be positive or negative \
   depending on context (love vs. self-love, truth vs. falsity). \
   Determine from context which sense applies.
4. **Discrete degrees:** When the text describes five faculties, \
   five worlds, five elements — read them as discrete levels of \
   reality (celestial/spiritual/natural), not a continuum.
5. **The Divine Human:** When the text describes cosmic beings with \
   body parts, faces, limbs — read them as the Grand Man: the \
   form of love and wisdom at different registers.
6. **Follow the arc:** The teaching has a beginning, middle, and end. \
   Your reading should reveal the spiritual process flowing through it.
7. **Use the lexicon:** If a term appears in the spiritual lexicon, use \
   that stable spiritual meaning and project vocabulary.
8. **Name Coptic anchors:** For each segment, record the important \
   Coptic forms that shaped the reading in `coptic_anchors`.

When complete, call commit_reading exactly once."""


def format_lexicon_summary(lexicon: dict) -> str:
    """Format spiritual_lexicon.json as compact prompt context."""
    entries = lexicon.get("entries", [])
    total = lexicon.get("total_entries", len(entries))
    lines = [f"Spiritual lexicon ({total} entries):"]

    for entry in entries:
        term = entry.get("english_term") or entry.get("natural_term") or "?"
        category = entry.get("category", "?")
        coptic_forms = entry.get("coptic_forms") or []
        if isinstance(coptic_forms, str):
            coptic_forms = [coptic_forms]
        coptic = ", ".join(coptic_forms)
        meaning = (
            entry.get("spiritual_meaning")
            or entry.get("spiritual_correspondence")
            or ""
        )
        use = entry.get("use_in_reading") or meaning
        opposite = entry.get("opposite_sense") or ""
        confidence = entry.get("confidence", "")

        prefix = f"- {term} [{category}"
        if confidence:
            prefix += f", {confidence}"
        prefix += "]"
        if coptic:
            prefix += f" (Coptic: {coptic})"
        line = f"{prefix}: {meaning}"
        if use and use != meaning:
            line += f" Use: {use}"
        elif use:
            line += f" Use: {use}"
        if opposite:
            line += f" Opposite sense: {opposite}"
        lines.append(line)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Stage implementation
# ---------------------------------------------------------------------------

class ReadStage(PipelineStage):
    stage_name = "Correspondential Reading"
    stage_number = 5
    description = "Spiritual-sense reading of assembled teachings"
    tool_name = "commit_reading"
    tool_schema = READ_TOOL
    item_name = "teaching"
    item_name_plural = "teachings"
    item_prefix = "t"
    _lexicon_summary: str | None = None

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def get_input_dir(self) -> Path:
        return TEACHINGS_DIR

    def get_output_dir(self) -> Path:
        return PROJECT_DIR / "readings"

    def get_lexicon_summary(self) -> str:
        """Load the pre-reading lexicon once and format it for prompts."""
        if self._lexicon_summary is not None:
            return self._lexicon_summary
        if not SPIRITUAL_LEXICON_PATH.exists():
            self._lexicon_summary = ""
            return self._lexicon_summary
        with open(SPIRITUAL_LEXICON_PATH, encoding="utf-8") as f:
            lexicon = json.load(f)
        self._lexicon_summary = format_lexicon_summary(lexicon)
        return self._lexicon_summary

    def list_available(self) -> list[int]:
        """List available teaching numbers."""
        teachings = []
        for path in sorted(TEACHINGS_DIR.glob("t_*.json")):
            m = re.match(r"t_(\d+)\.json", path.name)
            if m:
                teachings.append(int(m.group(1)))
        return teachings

    def is_done(self, num: int) -> bool:
        """Check if reading output already exists for this teaching."""
        return (self.get_output_dir() / f"t_{num:03d}.json").exists()

    def save_output(self, num: int, data: dict) -> None:
        """Save the output JSON for a teaching (thread-safe)."""
        from pipeline_base import _write_lock
        output_dir = self.get_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"t_{num:03d}.json"
        with _write_lock:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

    def build_user_message(self, teaching_num: int) -> str:
        """Load assembled teaching and format prompt."""
        path = TEACHINGS_DIR / f"t_{teaching_num:03d}.json"
        if not path.exists():
            print(f"  ERROR: No teaching file for t.{teaching_num}")
            return None
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        title = data.get("title", "")
        confidence = data.get("confidence", "")
        segments = data.get("segments", [])
        lexicon_summary = self.get_lexicon_summary()

        # Filter to only core segments (with content)
        core_segments = [
            s for s in segments
            if s.get("classification") in ("cosmological_substrate", "mixed")
            and (s.get("core_english") or s.get("core_coptic"))
        ]

        if not core_segments:
            return None

        parts = [
            f"## Teaching {teaching_num}: {title}",
            f"(Confidence: {confidence} | Core segments: {len(core_segments)})",
            "",
        ]
        parts.append("Use each section number (the § value) as the segment `i` in your output.")
        parts.append("")

        if lexicon_summary:
            parts.extend([
                "## Corpus Spiritual Lexicon",
                lexicon_summary,
                "",
                "Use this lexicon as the vocabulary authority for the "
                "reading below. The local Coptic and English still control "
                "which entries apply in each segment.",
                "",
            ])

        for seg in core_segments:
            sec = seg.get("section", "?")
            cls = seg["classification"]
            coptic = seg.get("core_coptic") or ""
            english = seg.get("core_english") or ""

            parts.append(f"### §{sec} [{cls}]")
            if coptic:
                parts.append(f"Coptic: {coptic}")
            if english:
                parts.append(f"English: {english}")
            parts.append("")

        parts.append(
            "Read each segment's spiritual sense via correspondences. "
            "Call commit_reading with the complete reading."
        )

        return "\n".join(parts)

    def process_result(self, teaching_num: int, result: dict) -> dict:
        """Normalize segment IDs to source section numbers.

        The prompt asks the model to use section numbers as `i`, but some
        large teachings may be tempting to number from zero. Stage 6 joins
        readings to teaching segments by section, so enforce that contract
        mechanically when the segment count matches the teaching file.
        """
        result.setdefault("teaching", teaching_num)

        path = TEACHINGS_DIR / f"t_{teaching_num:03d}.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                teaching = json.load(f)
            expected_sections = [
                segment.get("section")
                for segment in teaching.get("segments", [])
                if segment.get("classification") in (
                    "cosmological_substrate", "mixed",
                )
                and (
                    segment.get("core_english")
                    or segment.get("core_coptic")
                )
            ]
        else:
            expected_sections = []

        reading_segments = result.get("segments", [])
        for segment in reading_segments:
            segment.setdefault("coptic_anchors", [])

        if len(reading_segments) == len(expected_sections):
            for segment, section in zip(reading_segments, expected_sections):
                segment["i"] = section
            result["segments_read"] = len(reading_segments)

        return result

    def format_summary(self, teaching_num: int, result: dict) -> str:
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
