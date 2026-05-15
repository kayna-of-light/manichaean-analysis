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
                "description": "Total unique {N} gaps in the Coptic core.",
            },
            "gaps_restored": {
                "type": "integer",
                "description": "Number of Coptic gaps with proposed fills.",
            },
            "gaps_unrestorable": {
                "type": "integer",
                "description": "Number of Coptic gaps left unrestored.",
            },
            "restoration_note": {
                "type": "string",
                "description": (
                    "Brief assessment of the teaching's restoration logic: "
                    "what system is being described, what constrained the "
                    "fills, and what remained too damaged."
                ),
            },
            "coptic_restorations": {
                "type": "array",
                "description": (
                    "One decision per unique {N} gap in the Coptic core. "
                    "Coptic-only: each entry says what Coptic letters fill "
                    "the gap. The English side is handled separately in "
                    "`english_segments` and `english_restorations`."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "gap_id": {
                            "type": "integer",
                            "description": "The ID matching {N} in the Coptic core.",
                        },
                        "section": {"type": "integer"},
                        "chapter": {"type": "integer"},
                        "line": {"type": "integer"},
                        "gap_type": {
                            "type": "string",
                            "description": "Apparatus type: lacuna, restoration, or unknown.",
                        },
                        "proposed_coptic": {
                            "type": ["string", "null"],
                            "description": (
                                "Coptic letter fill only, no {N}, no "
                                "brackets. Must respect partial traces "
                                "and the estimated character count. Null "
                                "if unrestorable."
                            ),
                        },
                        "basis": {
                            "type": "string",
                            "description": (
                                "Why this fill fits: spiritual anchor, "
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
                                "good fit with alternatives; low = weak "
                                "but useful; unrestorable = no fill."
                            ),
                        },
                    },
                    "required": [
                        "gap_id", "section", "chapter", "line", "gap_type",
                        "proposed_coptic", "basis", "confidence",
                    ],
                },
            },
            "english_segments": {
                "type": "array",
                "description": (
                    "One entry per Coptic core segment that contains at "
                    "least one gap. Provide a fresh, natural English "
                    "translation of the segment as it should read once "
                    "the Coptic restorations are accepted, with your own "
                    "{N} placeholders marking ONLY the English-side "
                    "lexical gaps that arise from translation. Coptic "
                    "morphology with no English correlate (articles, "
                    "particles, status prefixes) gets no English "
                    "placeholder. Vocabulary already used by the editor "
                    "for surrounding extant Coptic is the preferred "
                    "choice; you may improve a word when the Coptic "
                    "restoration makes a more precise translation "
                    "possible. Match each entry to its Coptic segment "
                    "by section, chapter, line."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "section": {"type": "integer"},
                        "chapter": {"type": "integer"},
                        "line": {"type": "integer"},
                        "core_english": {
                            "type": "string",
                            "description": (
                                "Natural English translation of this "
                                "segment, with {N} placeholders for the "
                                "English-side gaps you intend to fill in "
                                "`english_restorations`. Use the same "
                                "{N} numbering space as `english_"
                                "restorations` (one shared id space "
                                "across the teaching)."
                            ),
                        },
                    },
                    "required": [
                        "section", "chapter", "line", "core_english",
                    ],
                },
            },
            "english_restorations": {
                "type": "array",
                "description": (
                    "One entry per {N} English placeholder in your "
                    "`english_segments`. Each English gap is a genuine "
                    "lexical gap arising from translation; it does not "
                    "have to mirror a Coptic gap one-to-one."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "eng_gap_id": {
                            "type": "integer",
                            "description": (
                                "The ID matching {N} in `english_"
                                "segments.core_english`. Numbering is "
                                "global within the teaching."
                            ),
                        },
                        "section": {"type": "integer"},
                        "chapter": {"type": "integer"},
                        "line": {"type": "integer"},
                        "proposed_english": {
                            "type": ["string", "null"],
                            "description": (
                                "English fill only, no {N}, no brackets. "
                                "May be one word or several; whatever "
                                "fits cleanly into the surrounding "
                                "English. Null if unrestorable."
                            ),
                        },
                        "coptic_gap_refs": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": (
                                "List of Coptic `gap_id` values that "
                                "this English fill corresponds to. May "
                                "be empty (e.g. an English particle "
                                "introduced by translation), one (the "
                                "common case), or several (when one "
                                "English phrase covers multiple Coptic "
                                "gaps)."
                            ),
                        },
                        "confidence": {
                            "type": "string",
                            "enum": [
                                "high", "moderate", "low", "unrestorable",
                            ],
                        },
                        "basis": {
                            "type": "string",
                            "description": (
                                "Why this English fill fits: which "
                                "Coptic restorations support it, "
                                "translation register, lexicon match, "
                                "or reason for skipping."
                            ),
                        },
                    },
                    "required": [
                        "eng_gap_id", "section", "chapter", "line",
                        "proposed_english", "coptic_gap_refs",
                        "confidence", "basis",
                    ],
                },
            },
        },
        "required": [
            "teaching", "total_gaps_in_core", "gaps_restored",
            "gaps_unrestorable", "restoration_note",
            "coptic_restorations", "english_segments",
            "english_restorations",
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
Kephalaia. The Coptic core has gaps marked with numbered placeholders \
{0}, {1}, {2}. Your task is to use the spiritual reading to identify \
what reality belongs at each gap, then express that reality in the \
Kephalaia's own natural-plane Coptic vocabulary, then translate the \
restored Coptic into clean English.

## WHAT YOU RECEIVE

1. **The Coptic core text** with numbered {N} placeholders for damaged spans.
2. **The editor's partial English** as reference. It is a useful gloss \
   but it is letter-mirrored to the Coptic and is NOT authoritative for \
   your output. You write your own English from the restored Coptic.
3. **The apparatus** for each Coptic gap: type, estimated character \
   count, partial traces, and any editor proposal.
4. **The whole-teaching correspondential reading** explaining the \
   spiritual system and arc.
5. **The spiritual lexicon** when available, giving stable corpus \
   vocabulary.

## OUTPUT CONTRACT

You produce three parallel structures.

### 1. `coptic_restorations`

One entry per Coptic {N} gap. Each entry holds the Coptic letters that \
fill the gap (or null if unrestorable). This is Coptic-only.

Method per gap:

1. Locate the {N} marker in the Coptic core.
2. Use the whole-teaching reading to identify the governing spiritual arc.
3. Read the local Coptic context: what reality belongs there?
4. Express that reality in the Kephalaia's natural-plane Coptic terms.
5. Check the apparatus: type, estimated characters, partial traces, \
   editor proposal.
6. Check Coptic grammar: article, status constructus, prepositions, \
   dialect morphology.
7. If the fill is not constrained, mark unrestorable.

### 2. `english_segments`

For each Coptic segment that contains at least one gap, write a clean, \
natural English translation of the whole segment as it should read once \
the Coptic restorations are accepted. Place your own {N} placeholders \
ONLY where there is a genuine English-side lexical gap arising from \
translation — i.e. a span the English reader needs and which depends on \
your Coptic restoration to have a sensible value. Coptic morphology \
with no English correlate (articles, particles, status prefixes, \
inflectional letters) gets no English placeholder.

The Coptic is the source of truth. The English is its translation. \
Vocabulary already used in the editor's partial English for the \
surrounding extant Coptic is the preferred choice; you have full \
freedom to refine wording when your Coptic restoration makes a more \
precise English term possible. Stay within the segment — do not write \
content that belongs to a neighbouring segment.

**Cross-segment continuity (English-side awareness).** The Coptic is \
segmented by the editor for line/page reasons; consecutive segments \
often form a single Coptic clause whose word order does not survive in \
English. When you translate, look at the segments before and after the \
one you are writing. If a Coptic word in this segment has already been \
folded naturally into the previous segment's English (e.g. a \
postpositive ⲧⲏⲣⲟⲩ absorbed into "all the X" upstream, or a status \
constructus carried forward), do not re-state it here. In that case \
emit the segment's `core_english` as just the trailing punctuation \
("." or ",") or as an empty string. Likewise, if a word in this \
segment will more naturally surface in the next segment's English, \
defer it. The reader sees the segments concatenated; one English \
expression per Coptic reality, never two.

### 3. `english_restorations`

One entry per {N} placeholder in your `english_segments`. Each entry \
holds the English fill (or null if unrestorable) and a list of Coptic \
`gap_id` values it covers. The list may be empty (an English particle \
introduced for grammar), one (the common case), or several (when one \
English phrase covers several Coptic gaps).

Numbering: `eng_gap_id` is global within the teaching. The first \
English {N} is `0`, the next is `1`, and so on, regardless of which \
segment they appear in. The numbering space is independent of the \
Coptic `gap_id` space.

## COPTIC CONSTRAINTS

- Lycopolitan/sub-Achmimic dialect: ⲁ often corresponds to Sahidic ⲟ; \
  ⲉⲓ often corresponds to Sahidic ⲏ.
- Greek loanwords are common for technical terms.
- Status constructus forms are common before nouns.
- Definite articles matter: ⲡ-/ⲧ-/ⲛ- constrain gender and number.
- Prepositions matter: ⲁⲃⲁⲗ, ⲛ̄, ϩⲛ̄, ⲁ-/ⲉ- often constrain whether a \
  noun, infinitive, or clause can fit.
- Estimated character count matters. A proposed Coptic fill should fit \
  the approximate length unless the apparatus is clearly uncertain.
- Visible partial traces are binding. A proposed Coptic fill must \
  include the visible letters in the right position.

## RESTORATION POLICY

- **Editor restoration entries** in the apparatus are proposals. \
  Review them through the correspondential reading. Confirm them when \
  they fit; correct them when the spiritual and Coptic constraints \
  point elsewhere.
- **Small lacunae** should be restored when grammar and spiritual \
  context constrain the fill.
- **Medium lacunae** should be restored only when a formula, parallel, \
  or strong structural pattern constrains them.
- **Large or weakly constrained lacunae** should be marked \
  unrestorable. Honest non-restoration is better than a smooth \
  invention.
- `proposed_coptic` and `proposed_english` contain only the fill \
  letters / words. No {N}, no brackets, no parentheses.

## VOCABULARY AUTHORITY

Use the generated Corpus Spiritual Lexicon supplied in the user prompt \
as the controlled vocabulary. It supersedes general correspondential \
defaults whenever it fixes a term.

For each Coptic restoration, prefer the lexicon's Coptic forms. For \
English, prefer the lexicon's `use_in_reading` wording, spiritual \
meanings, and opposite-sense notes. If no lexicon entry applies, use \
the provided spiritual reading, local Coptic anchors, apparatus \
constraints, and Coptic grammar conservatively.

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