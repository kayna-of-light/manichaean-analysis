#!/usr/bin/env python3
"""
Teaching-level bilingual restoration of lacunae in core segments.

Pipeline stage 6: runs AFTER stage_5_read.py, BEFORE stage_7_review.py.

This stage restores gaps in assembled teaching files, not page files. It
uses Coptic and English core text, stage 5 correspondential readings, the
pre-reading spiritual lexicon, and the original apparatus metadata that
stage 4c carries forward into each teaching segment.

Input:
  - output/projects/kephalaia_v2/teachings/t_NNN.json
  - output/projects/kephalaia_v2/readings/t_NNN.json
  - output/projects/kephalaia_v2/spiritual_lexicon.json (optional)

Output:
  - output/projects/kephalaia_v2/restored/t_NNN.json

Usage:
    python scripts/projects/kephalaia_v2/stage_6_restore.py
    python scripts/projects/kephalaia_v2/stage_6_restore.py --page 5
    python scripts/projects/kephalaia_v2/stage_6_restore.py --range 1-20
    python scripts/projects/kephalaia_v2/stage_6_restore.py --dry-run
    python scripts/projects/kephalaia_v2/stage_6_restore.py --max-concurrency 32
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_base import PipelineStage, PROJECT_DIR  # noqa: E402
from stage_5_read import format_lexicon_summary  # noqa: E402

TEACHINGS_DIR = PROJECT_DIR / "teachings"
READINGS_DIR = PROJECT_DIR / "readings"
SPIRITUAL_LEXICON_PATH = PROJECT_DIR / "spiritual_lexicon.json"

LACUNA_RE = re.compile(r"\{(\d+)\}")


# ---------------------------------------------------------------------------
# Tool schema
# ---------------------------------------------------------------------------

RESTORE_TOOL = {
    "name": "commit_restorations",
    "description": (
        "Commit all proposed gap restorations for this teaching. "
        "Call exactly once."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "teaching": {
                "type": "integer",
                "description": "The teaching number.",
            },
            "total_gaps_in_core": {
                "type": "integer",
                "description": "Total unique {N} gaps in core segments.",
            },
            "gaps_restored": {
                "type": "integer",
                "description": "Number of gaps with proposed restorations.",
            },
            "gaps_unrestorable": {
                "type": "integer",
                "description": "Number of gaps deliberately left unrestored.",
            },
            "restoration_note": {
                "type": "string",
                "description": (
                    "Brief assessment of the teaching's restoration logic: "
                    "what system is being described, what constrained the "
                    "fills, and what remained too damaged."
                ),
            },
            "restorations": {
                "type": "array",
                "description": "One decision for each unique gap in core text.",
                "items": {
                    "type": "object",
                    "properties": {
                        "gap_id": {
                            "type": "integer",
                            "description": "The ID matching {N} in the teaching.",
                        },
                        "section": {
                            "type": "integer",
                            "description": "The section containing the gap.",
                        },
                        "chapter": {
                            "type": "integer",
                            "description": "Source chapter number.",
                        },
                        "line": {
                            "type": "integer",
                            "description": "Source chapter line index.",
                        },
                        "gap_type": {
                            "type": "string",
                            "description": "Apparatus type: lacuna, restoration, or unknown.",
                        },
                        "proposed_coptic": {
                            "type": ["string", "null"],
                            "description": (
                                "Proposed Coptic fill only, without {N}. "
                                "Null if unrestorable."
                            ),
                        },
                        "proposed_english": {
                            "type": ["string", "null"],
                            "description": (
                                "Proposed English fill only, without {N}. "
                                "Null if unrestorable."
                            ),
                        },
                        "basis": {
                            "type": "string",
                            "description": (
                                "Why this decision fits: spiritual anchor, "
                                "Coptic grammar, traces, character count, "
                                "parallel formula, or reason for skipping."
                            ),
                        },
                        "confidence": {
                            "type": "string",
                            "enum": [
                                "high", "moderate", "low", "unrestorable",
                            ],
                            "description": (
                                "high = strongly constrained; moderate = "
                                "good fit with alternatives; low = weak but "
                                "still useful; unrestorable = no fill."
                            ),
                        },
                    },
                    "required": [
                        "gap_id", "section", "chapter", "line", "gap_type",
                        "proposed_coptic", "proposed_english",
                        "basis", "confidence",
                    ],
                },
            },
        },
        "required": [
            "teaching", "total_gaps_in_core", "gaps_restored",
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
vocabulary: Zoroastrian, Manichaean, Persian-Iranian, Syriac, and Coptic. \
You are also an expert Coptologist specializing in the Lycopolitan \
(sub-Achmimic) dialect.

You are restoring lacunae in the oldest teaching substrate of the Coptic \
Kephalaia. The text has gaps marked with numbered placeholders like {0}, \
{1}, {2}. Your task is not to guess missing words from English alone. Your \
task is to use the spiritual reading to identify what reality belongs at \
the gap, then translate that reality back into the Kephalaia's own \
natural-plane Coptic vocabulary.

## WHAT YOU RECEIVE

You receive:

1. **The core teaching text** with Coptic and English side by side.
2. **The apparatus** for each gap, including lacuna/restoration type, \
   estimated character count, partial traces, and existing editorial fills.
3. **The provided correspondential reading**, a whole-teaching explanation \
    of the spiritual system and arc being described.
4. **The spiritual lexicon** when available, giving stable vocabulary for \
   the corpus.

## RESTORATION METHOD

Before deciding fills, identify the Swedenborgian system being described \
in this teaching. The spiritual reading tells you the whole teaching's \
spiritual arc. Use that whole-reading context together with the local \
Coptic, English, and apparatus to decide what reality belongs at each gap. \
The restoration must then express that spiritual reality in the text's own \
natural/cosmological register.

For each gap:

1. Locate the {N} marker in the Coptic and English core text.
2. Use the whole-teaching reading to identify the governing spiritual arc.
3. Read the local Coptic and English context: what belongs there in the \
    teaching's inner sense?
4. Translate that reality back into the Kephalaia's natural-plane terms.
5. Check the apparatus: type, estimated characters, traces, and editor fill.
6. Check Coptic grammar: article, status constructus, prepositions, and \
   dialect morphology.
7. If the fill is not constrained, mark it unrestorable.

## COPTIC CONSTRAINTS

- Lycopolitan/sub-Achmimic dialect: ⲁ often corresponds to Sahidic ⲟ; \
  ⲉⲓ often corresponds to Sahidic ⲏ.
- Greek loanwords are common for technical terms.
- Status constructus forms are common before nouns.
- Definite articles matter: ⲡ-/ⲧ-/ⲛ- constrain gender and number.
- Prepositions matter: ⲁⲃⲁⲗ, ⲛ̄, ϩⲛ̄, ⲁ-/ⲉ- often constrain whether a \
  noun, infinitive, or clause can fit.
- Estimated character count matters. A proposed Coptic fill should fit the \
  approximate length unless the apparatus is clearly uncertain.
- Visible partial traces are binding. A proposed Coptic fill must include \
  the visible letters in the right position.

## RESTORATION POLICY

- **Restoration apparatus entries** are editor proposals. Review them \
  through the correspondential reading. Confirm if they fit; correct them \
  if the spiritual and Coptic constraints point elsewhere.
- **Small lacunae** should be restored when grammar and spiritual context \
  constrain the fill.
- **Medium lacunae** should be restored only when a formula, parallel, or \
  strong structural pattern constrains them.
- **Large or weakly constrained lacunae** should be marked unrestorable. \
  Honest non-restoration is better than a smooth invention.
- **Bilingual output is required.** Every restored gap must include both \
  proposed Coptic and proposed English.
- Proposed fields contain the fill only. Do not include {N} in the output.

## VOCABULARY AUTHORITY

Use the generated Corpus Spiritual Lexicon supplied in the user prompt as \
the controlled vocabulary for this restoration. It is the same vocabulary \
discipline used in the provided reading, and it supersedes general \
correspondential defaults whenever it fixes a term.

For each proposed restoration, prefer the lexicon's Coptic forms, \
`use_in_reading` wording, spiritual meanings, and opposite-sense notes. \
Do not improvise new English when a term is fixed there. If no lexicon \
entry applies, use the provided spiritual reading, local Coptic anchors, \
apparatus constraints, and Coptic grammar conservatively.

When complete, call commit_restorations exactly once."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict | None:
    """Load JSON if present."""
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def load_lexicon_summary() -> str:
    """Load and compact the spiritual lexicon for prompt context."""
    lexicon = load_json(SPIRITUAL_LEXICON_PATH)
    if not lexicon:
        return ""
    return format_lexicon_summary(lexicon)


def segment_gap_ids(segment: dict) -> set[int]:
    """Return unique gap IDs appearing in Coptic or English text."""
    ids: set[int] = set()
    for field in ("core_coptic", "core_english"):
        text = segment.get(field) or ""
        for match in LACUNA_RE.finditer(text):
            ids.add(int(match.group(1)))
    return ids


def collect_gaps(teaching: dict) -> list[dict]:
    """Collect one restoration target per unique teaching-level gap ID."""
    gaps_by_id: dict[int, dict] = {}

    for segment in teaching.get("segments", []):
        if segment.get("classification") not in (
            "cosmological_substrate", "mixed",
        ):
            continue
        gap_ids = segment_gap_ids(segment)
        if not gap_ids:
            continue

        apparatus = {
            entry.get("id"): entry
            for entry in segment.get("apparatus", [])
            if isinstance(entry.get("id"), int)
        }
        for gap_id in gap_ids:
            entry = apparatus.get(gap_id, {})
            gaps_by_id[gap_id] = {
                "gap_id": gap_id,
                "section": segment.get("section"),
                "chapter": segment.get("chapter"),
                "line": segment.get("line"),
                "classification": segment.get("classification"),
                "core_coptic": segment.get("core_coptic") or "",
                "core_english": segment.get("core_english") or "",
                "apparatus": entry,
            }

    return [gaps_by_id[key] for key in sorted(gaps_by_id)]


def has_gaps(teaching: dict) -> bool:
    """Return True if the teaching has any core gaps."""
    return bool(collect_gaps(teaching))


def format_apparatus(entry: dict) -> str:
    """Format one apparatus entry for the prompt."""
    if not entry:
        return "type=unknown; no apparatus entry carried forward"
    gap_type = entry.get("type", "unknown")
    if gap_type == "lacuna":
        parts = ["type=lacuna"]
        if entry.get("est_chars") is not None:
            parts.append(f"est_chars={entry.get('est_chars')}")
        if entry.get("partial"):
            parts.append(f"partial='{entry.get('partial')}'")
        return "; ".join(parts)
    if gap_type == "restoration":
        coptic = entry.get("coptic", "")
        english = entry.get("english", "")
        basis = entry.get("basis", "")
        return (
            f"type=restoration; proposed_coptic='{coptic}'; "
            f"proposed_english='{english}'; basis='{basis}'"
        )
    return f"type={gap_type}"


# ---------------------------------------------------------------------------
# Stage implementation
# ---------------------------------------------------------------------------

class RestoreStage(PipelineStage):
    stage_name = "Restore Lacunae"
    stage_number = 6
    description = "Teaching-level bilingual gap-filling"
    tool_name = "commit_restorations"
    tool_schema = RESTORE_TOOL
    item_name = "teaching"
    item_name_plural = "teachings"
    item_prefix = "t"
    _lexicon_summary: str | None = None

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def get_input_dir(self) -> Path:
        return READINGS_DIR

    def get_output_dir(self) -> Path:
        return PROJECT_DIR / "restored"

    def get_lexicon_summary(self) -> str:
        if self._lexicon_summary is None:
            self._lexicon_summary = load_lexicon_summary()
        return self._lexicon_summary

    def list_available(self) -> list[int]:
        """Teachings with readings and at least one core gap."""
        teachings = []
        for path in sorted(TEACHINGS_DIR.glob("t_*.json")):
            match = re.match(r"t_(\d+)\.json", path.name)
            if not match:
                continue
            num = int(match.group(1))
            reading = load_json(READINGS_DIR / f"t_{num:03d}.json")
            if not reading or not reading.get("reading"):
                continue
            teaching = load_json(path)
            if teaching and has_gaps(teaching):
                teachings.append(num)
        return teachings

    def build_user_message(self, teaching_num: int) -> str | None:
        """Load teaching + reading and format restoration prompt."""
        teaching = load_json(TEACHINGS_DIR / f"t_{teaching_num:03d}.json")
        reading = load_json(READINGS_DIR / f"t_{teaching_num:03d}.json")
        if teaching is None:
            print(f"  ERROR: No teaching file for t.{teaching_num}")
            return None
        if reading is None:
            print(f"  ERROR: No reading file for t.{teaching_num}")
            return None

        gaps = collect_gaps(teaching)
        if not gaps:
            return None

        title = teaching.get("title", "")
        lexicon_summary = self.get_lexicon_summary()

        parts = [
            f"## Teaching {teaching_num}: {title}",
            f"Total unique core gaps: {len(gaps)}",
            "",
        ]

        if lexicon_summary:
            parts.extend([
                "## Corpus Spiritual Lexicon",
                lexicon_summary,
                "",
            ])

        parts.extend([
            "## Core Teaching Text",
            "",
        ])
        for segment in teaching.get("segments", []):
            if segment.get("classification") not in (
                "cosmological_substrate", "mixed",
            ):
                continue
            if not (segment.get("core_coptic") or segment.get("core_english")):
                continue
            section = segment.get("section")
            chapter = segment.get("chapter")
            line = segment.get("line")
            parts.append(f"### Section {section} | ch.{chapter}.{line}")
            parts.append(f"Coptic: {segment.get('core_coptic') or ''}")
            parts.append(f"English: {segment.get('core_english') or ''}")
            parts.append("")

        parts.extend([
            "## Gap Apparatus",
            "",
        ])
        for gap in gaps:
            parts.append(
                f"{{{gap['gap_id']}}} Section {gap['section']} "
                f"ch.{gap['chapter']}.{gap['line']} | "
                f"{format_apparatus(gap['apparatus'])}"
            )
            parts.append(f"  Coptic context: {gap['core_coptic']}")
            parts.append(f"  English context: {gap['core_english']}")
            parts.append("")

        parts.extend([
            "## Correspondential Reading",
            "",
        ])
        if reading.get("reading"):
            if reading.get("title"):
                parts.append(f"Title: {reading.get('title')}")
            if reading.get("arc"):
                parts.append(f"Arc: {reading.get('arc')}")
            parts.append("")
            parts.append(reading.get("reading", ""))
            parts.append("")

            images = reading.get("major_images") or []
            if images:
                parts.append("Major images:")
                for image in images:
                    parts.append(
                        f"- {image.get('image')}: {image.get('meaning')}"
                    )
                parts.append("")

        else:
            parts.append(
                "No whole-teaching reading is available. Re-run the "
                "correspondential reading stage before restoration."
            )
            parts.append("")

        parts.append(
            "Restore every listed gap or mark it unrestorable. Call "
            "commit_restorations with one restoration decision per gap."
        )
        return "\n".join(parts)

    def process_result(self, teaching_num: int, result: dict) -> dict:
        """Attach lightweight consistency metadata."""
        result.setdefault("teaching", teaching_num)
        return result

    def format_summary(self, teaching_num: int, result: dict) -> str:
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