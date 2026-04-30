#!/usr/bin/env python3
"""
Correspondential reading of assembled teachings.

Pipeline stage 5: runs AFTER stage_4c_assemble.py, BEFORE stage_6_restore.py.

This stage produces a standalone spiritual reading of each teaching.
Now that the corpus has been separated into teaching-level units, the
reading is a single whole-teaching explanation rather than a per-line
paraphrase. It explains the teaching's story, movement, correspondential
logic, and meaning in one coherent read. The reading is used downstream
by restore.py as context for gap-filling — and also stands as an
independent reader-facing output.

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
            "title": {
                "type": "string",
                "description": "Short descriptive title for the reading.",
            },
            "arc": {
                "type": "string",
                "description": (
                    "One or two sentences naming the complete movement "
                    "of the teaching from beginning to end."
                ),
            },
            "reading": {
                "type": "string",
                "description": (
                    "The full reader-facing explanation of the teaching. "
                    "Write in coherent paragraphs. Explain what the "
                    "teaching describes, how the imagery works, and what "
                    "spiritual process is being taught. This is not a "
                    "line-by-line paraphrase and not a lexical apparatus."
                ),
            },
            "major_images": {
                "type": "array",
                "description": (
                    "Only the major recurring images needed to understand "
                    "the teaching as a whole. Do not make this exhaustive."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "image": {
                            "type": "string",
                            "description": "Natural/cosmological image in the teaching.",
                        },
                        "meaning": {
                            "type": "string",
                            "description": "Spiritual reality expressed by the image.",
                        },
                    },
                    "required": ["image", "meaning"],
                },
            },
            "confidence": {
                "type": "string",
                "enum": ["clear", "probable", "uncertain"],
                "description": (
                    "Overall confidence in the whole-teaching reading."
                ),
            },
        },
        "required": [
            "title", "arc", "reading", "major_images", "confidence",
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

You read a complete teaching through the doctrine of correspondences and \
explain what it means as one coherent spiritual argument. The goal is a \
reader-facing explanation of the whole teaching, not a line-by-line \
paraphrase and not a lexical apparatus.

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

Your job: tell the full story of the teaching. Explain what the teaching \
describes, why its sequence matters, what spiritual process is moving \
through it, and how its major images work together.

## GAP ANCHORS

The text contains numbered gap placeholders like {0}, {1}, {2}. \
These are lacunae (missing text) that will be restored later using \
your spiritual reading as a guide.

Do not try to account for every gap marker in the reading. If a major \
lacuna materially affects the teaching's meaning, mention the uncertainty \
in ordinary prose. Otherwise read the surviving teaching as a whole.

## RULES

1. **Read the whole teaching.** Produce a full story/explanation of the \
    teaching, in coherent paragraphs.
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
7. **Use the lexicon silently:** If a term appears in the spiritual \
    lexicon, use that stable spiritual meaning and project vocabulary, \
    but do not turn the reading into a vocabulary list.
8. **Keep support material short:** `major_images` is an aid to the \
    reading, not the main product.

The `reading` field should be the primary output. It should be readable on \
its own by someone asking: "What does this teaching describe?"

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
    description = "Whole-teaching correspondential reading"
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

    def is_done(self, page_num: int) -> bool:
        """Check if a whole-teaching reading output already exists."""
        path = self.get_output_dir() / f"t_{page_num:03d}.json"
        if not path.exists():
            return False
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return False
        return bool(data.get("reading"))

    def save_output(self, page_num: int, data: dict) -> None:
        """Save the output JSON for a teaching (thread-safe)."""
        from pipeline_base import _write_lock
        output_dir = self.get_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"t_{page_num:03d}.json"
        with _write_lock:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

    def build_user_message(self, page_num: int) -> str | None:
        """Load assembled teaching and format prompt."""
        path = TEACHINGS_DIR / f"t_{page_num:03d}.json"
        if not path.exists():
            print(f"  ERROR: No teaching file for t.{page_num}")
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
            f"## Teaching {page_num}: {title}",
            f"(Confidence: {confidence})",
            "",
        ]
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
            "Read the teaching as one complete spiritual argument. Write "
            "a full explanation of what the whole teaching describes. Do "
            "not produce a per-section or per-line reading. Call "
            "commit_reading with the complete teaching-level reading."
        )

        return "\n".join(parts)

    def process_result(self, page_num: int, result: dict) -> dict:
        """Add pipeline-generated index metadata after the tool call."""
        path = TEACHINGS_DIR / f"t_{page_num:03d}.json"
        core_segment_count = 0
        if path.exists():
            with open(path, encoding="utf-8") as f:
                teaching = json.load(f)
            core_segment_count = sum(
                1
                for segment in teaching.get("segments", [])
                if segment.get("classification") in (
                    "cosmological_substrate", "mixed",
                )
                and (
                    segment.get("core_english")
                    or segment.get("core_coptic")
                )
            )

        result["_index"] = {
            "teaching": page_num,
            "core_segments": core_segment_count,
        }
        return result

    def format_summary(self, page_num: int, result: dict) -> str:
        """Format a one-line summary."""
        note = result.get("arc") or result.get("title", "")
        short_note = note[:60] + "..." if len(note) > 60 else note
        return f"OK — whole reading: {short_note}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    stage = ReadStage()
    stage.run()
