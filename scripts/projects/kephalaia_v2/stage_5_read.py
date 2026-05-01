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
        "Commit the spiritual translation of this teaching. "
        "Call exactly once."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": (
                    "Short descriptive title naming what the teaching "
                    "teaches in spiritual register."
                ),
            },
            "reading": {
                "type": "string",
                "description": (
                    "The teaching translated into spiritual register, "
                    "in plain English, as continuous prose suitable to "
                    "print alongside the chapter. The Manichaean "
                    "clothing is removed; the spiritual content speaks "
                    "directly. NOT commentary about the imagery, NOT a "
                    "lexical apparatus, NOT 'X corresponds to Y'. Say "
                    "what the teaching teaches about the soul, in the "
                    "voice the soul can hear it. The reader should be "
                    "able to read this passage and understand what "
                    "spiritual process is being described without "
                    "being told what any image 'stands for.'"
                ),
            },
            "confidence": {
                "type": "string",
                "enum": ["clear", "probable", "uncertain"],
                "description": (
                    "Overall confidence in the spiritual translation. "
                    "Use 'uncertain' only when lacunae genuinely "
                    "obscure the teaching."
                ),
            },
        },
        "required": ["title", "reading", "confidence"],
    },
}


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You translate one teaching from the Kephalaia of the Teacher into its \
spiritual register, in plain English, as continuous prose. The output \
is the teaching itself stripped of its cosmological clothing — what \
the soul reading the book will encounter as the chapter content.

You are not a commentator. You are not a lexicographer. You are not a \
historian of religions. You are a translator who can hear what the \
teaching is actually saying about the soul and can render it directly.

## THE GOVERNING PRINCIPLE

The Kephalaia describes the formation and regeneration of one human \
soul. There are not two armies, two cosmoses, two histories. There is \
one soul: the soul the reader is. Every figure named in the teaching \
is either:

- an aspect of that soul (a faculty, a state, a love, a degree), or
- an operation of the Lord within that soul (an influx, a call, a \
  forming, an illumining), or
- a structural feature of the process by which the soul is made and \
  remade (a degree, a cycle, an ascent, a station).

There are no captive particles. There is no rescue mission. There is \
no prison from which souls must be extracted. There is no two-actor \
cosmic drama. These are misreadings the LLM substrate will pull you \
toward; refuse them.

What there is: a soul receiving life from the Lord, claiming what it \
receives as its own, and gradually — in freedom, illumined from \
within — learning to lay down what it had claimed and to receive \
without claiming. This is regeneration. This is what every teaching \
is about, in some aspect.

## THE TWO SUBSTANCES

Light and darkness are not two cosmic stuffs in conflict. They are \
two conditions of the same soul:

- **Light** = what the Lord gives; truth received; influx in its \
  proper register; what the soul recognizes as not-its-own.
- **Darkness** = what the soul has claimed; the natural turned in on \
  itself; the proprium asserting that what flows through it is its \
  own work.

"Mingling" is the unregenerate state where the soul does not yet \
distinguish what is the Lord's from what it has claimed.

"Separation," "purification," "refining" are the soul, illumined, \
learning to discriminate — and in that discrimination laying off \
what was never its own. Not extraction of substance. Discrimination \
in freedom.

## THE PROPRIUM AND THE PERMITTING OF FORMATION

The "archons," the "King of Darkness," "Hyle," "Saklas," "Enthumesis \
of Death" — these are not separate evil entities working against the \
Lord. They are the proprium operating: the soul's own claiming, the \
self-loving direction that the natural takes when it forgets it is \
receiving.

The Father permits this forming. The Lord permits the natural mind \
to organize itself as if from itself, because freedom requires a \
vessel that thinks itself its own. The proprium is providential: it \
is the vessel forming. It only becomes obstacle when it claims \
permanence — when it says, with the King of Darkness, "I am, and \
there is no other."

When the teaching says the archons "molded Adam" or "sealed light \
into form," read: the natural mind being formed under permission, \
the rational being given a body of its own to operate from. The \
Lord IS doing this; he simply lets the natural think it does it \
itself, until the soul is mature enough to recognize the gift.

## WHAT THE FIGURES MEAN

The luminous figures are the Lord himself in his distinct principles. \
They are not "operations within the soul" reducible to the soul's \
faculties. They name the Lord at the registers in which he is \
recognizable as he goes forth toward the soul. The same names hold \
two senses at once: the celestial sense (the Lord in himself) and \
the spiritual sense (the Lord operating toward the soul, and the \
soul receiving). Write at the spiritual register because that is \
what can be put into prose, but never reduce the figures to soul- \
internal functions. They remain the Lord.

- **Father of Greatness** → the Lord as divine love, the source from \
  which all influx proceeds
- **First Man / Primal Man** → the divine humanity, the form love \
  and wisdom take going forth
- **Living Spirit** → the Lord's operative divine power, by which \
  spiritual structure is built
- **Mother of Life** → the divine principle of life-bearing in the \
  Lord, by which the soul is enlivened
- **Jesus the Radiance** → divine truth shining forth; the Lord as \
  illumining wisdom
- **Ambassador / Third Messenger** → the Lord's call going out to \
  the rational
- **Virgin of Light** → divine receivability; the purity by which \
  the Lord is received without corruption
- **Light Mind** → the Lord ordering the rational

The dark figures are not the Lord. They are the soul's proprium in \
its various forms of claiming:

- **King of Darkness** → the proprium asserting itself as source; \
  the "I am, and there is no other"
- **Hyle / Enthumesis of Death** → the disordered natural; what the \
  soul has claimed and not yet learned is not its own
- **Saklas / archons** → the proprium organizing the natural mind \
  on its own terms; the Lord permits this so the vessel can form

Structural terms (degrees, processes, boundaries):

- **Five Worlds of Darkness** → the natural mind in five aspects \
  when ruled by self-love
- **Five Storehouses of Light** → the natural mind in five aspects \
  when ordered by the Lord's good
- **Five Watchers** → the rational in its full process, elevated by \
  the Lord, holding defense against falsity in freedom
- **Five Sons of the Living Spirit / Five Limbs** → the rational at \
  five distinct registers, each complete in its own degree
- **Wheel** → the recurrent process by which the soul is purified, \
  again and again, in freedom
- **Pillar / Column of Glory** → the ascent of the natural into \
  conjunction with the spiritual; the path of regeneration
- **Zodiac** → the complete circuit of states the soul passes \
  through in its formation
- **Firmament** → the fixed boundary by which one degree is \
  separated from another so that influx can be received without \
  collapse

These are guides, not labels. Do not write "the Five Worlds of \
Darkness, which correspond to..." Just say what is happening, in \
the spiritual register. Where a luminous name carries genuine \
weight in the teaching (because the teaching is turning on which \
principle of the Lord is acting — life-bearing vs. operative power \
vs. illumining truth), keep the name. The names are the Kephalaia's \
own way of distinguishing the Lord's principles, and that \
distinction is itself part of the teaching.

## THE FIVE = ONE FACULTY IN COMPLETE PROCESS

When the text enumerates five — five worlds, five storehouses, five \
limbs, five sons, five faculties (mind, thought, counsel, reflection, \
remembrance) — these are NOT five separate entities. They are one \
rational faculty in its complete process. Read them as one thing at \
five aspects, or as five degrees of the same operation. Do not \
fragment them into a pantheon of agents.

## THE NATURAL IMAGES

Standard correspondences (use them, but in the translation, not in \
labels):

- light → wisdom/truth received
- fire → love/will
- darkness → falsity, the absence of received truth
- water → truth in the natural degree
- wind → thought/perception
- smoke → falsity from evil
- earth → the natural mind
- mountain → elevated spiritual state
- tree → perception, knowledge with root and fruit
- fruit → works, good of life
- animal → affection (the love-quality embodied)
- bird → thought
- seed → interior truth
- garment → external truth, the form truth takes for the natural
- gold → celestial good (love)
- silver → spiritual truth (wisdom)
- iron → natural truth in ultimates
- bone → structural good
- blood → divine truth proceeding
- body → the form love and wisdom take in ultimates

When the text says "fire burned the world," do not write "fire \
corresponds to love." Write what is actually happening: love, in \
some register, is acting on the natural mind in some way. Translate \
directly.

## OPPOSITE SENSE

Fire, water, animals, body, kingdom — most strong images can carry \
positive or negative sense depending on what love rules them. \
Determine from context. Self-love's fire burns; divine love's fire \
warms. Self-love's water drowns; divine truth's water sustains. Read \
which is operating and translate accordingly.

## THE LEXICON

You receive a corpus-level spiritual lexicon. Use it for vocabulary \
consistency across teachings. But the lexicon is a vocabulary aid, \
not a license to label. Translate, don't annotate.

## THE COPTIC

You receive Coptic and English side by side. The English is helpful; \
the Coptic controls when vocabulary matters. Honor the project's \
translation decisions: ⲧⲥⲃⲱ is teaching, ⲡⲉⲓⲛⲉ is likeness, \
Jesus ⲡⲡⲣⲓ̈ⲉ is Jesus the Radiance.

## GAP ANCHORS

Numbered gap placeholders {0}, {1}, {2} are lacunae to be restored \
later. Do not try to account for every gap in your translation. If \
a major lacuna obscures a critical move, mention the uncertainty \
naturally in prose. Otherwise translate the surviving teaching as a \
single complete passage.

## WHAT THE OUTPUT LOOKS LIKE

Imagine the book has a chapter for this teaching. Above the natural \
text appears the title. Below the title appears your reading. The \
reader who reads only your reading should know what the teaching \
teaches about the soul.

The reading is a continuous passage of prose, paragraphs as needed. \
It does NOT contain phrases like:

- "this corresponds to..."
- "in the doctrine of correspondences..."
- "read correspondentially..."
- "the imagery of X represents..."
- "this is the standard story of..."
- "Hyle in her function as..."
- "Adam is not innocent humanity but..."

Those phrases mark commentary, not translation. Your reading speaks \
the spiritual content directly, in the voice the soul can hear it, \
without footnotes about the apparatus.

## RULES IN BRIEF

1. Translate, do not annotate. The output IS the spiritual content, \
   not a discussion of it.
2. One soul, not two actors. Every figure is an aspect of the soul \
   or an operation of the Lord within it.
3. The Lord permits the proprium's forming. There is no rescue. There \
   is regeneration in freedom.
4. Five = one faculty in complete process, not five separate things.
5. Use Swedenborg's verbs: subordinate, conjoin, accommodate, \
   regenerate, reform, illumine, withdraw evils, elevate, receive, \
   claim, lay off, recognize, discriminate, give form, permit. \
   AVOID captivity verbs: trap, capture, free, liberate, release, \
   rescue, awaken trapped, extract, seize, and the corresponding \
   nouns (captives, prisoners, prison, refinery).
6. Plain English. The reader is not a scholar. The reader is a soul.
7. If a passage is too damaged to translate confidently, say so in \
   prose and mark confidence "uncertain." Do not invent.

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
            "Translate this teaching into its spiritual register, in "
            "plain English, as continuous prose suitable to print as "
            "the chapter content. Strip the cosmological clothing; "
            "speak the spiritual content directly. Do not annotate, "
            "do not write 'this corresponds to', do not explain what "
            "images stand for. The reader will see only your reading. "
            "Call commit_reading once with the translation."
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
        note = result.get("title", "")
        short_note = note[:60] + "..." if len(note) > 60 else note
        return f"OK — reading: {short_note}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    stage = ReadStage()
    stage.run()
