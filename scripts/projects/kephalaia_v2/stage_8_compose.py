#!/usr/bin/env python3
"""
Compose the book-level architecture from teaching-level Kephalaia v2 outputs.

Pipeline stage 8: runs AFTER stage_6_restore.py. Stage 7 review is optional
and advisory; compose can run without it.

This stage uses iterative multi-turn tool calls to build the book structure
piece by piece:

  1. compose_section  — define each major section (grouping of teachings)
  2. compose_chapter  — define each reader-facing chapter within a section
  3. finalize_book    — set the overall structure and reading order

The pipeline validates completeness: all 104 teachings must be assigned to
sections and chapters, and all sections must have chapters, before the
loop ends.

Input:
  - output/projects/kephalaia_v2/teachings/t_NNN.json
  - output/projects/kephalaia_v2/readings/t_NNN.json
  - output/projects/kephalaia_v2/restored/t_NNN.json
  - output/projects/kephalaia_v2/spiritual_lexicon.json

Output:
  - output/projects/kephalaia_v2/sections/s_NNN.json   (one per section)
  - output/projects/kephalaia_v2/chapters/ch_NNN.json   (one per chapter)
  - output/projects/kephalaia_v2/book.json              (finalized book)

Usage:
    python scripts/projects/kephalaia_v2/stage_8_compose.py --dry-run
    python scripts/projects/kephalaia_v2/stage_8_compose.py --debug
    python scripts/projects/kephalaia_v2/stage_8_compose.py --overwrite
"""
import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import httpx
from anthropic import AnthropicFoundry

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_base import (  # noqa: E402
    PROJECT_DIR,
    create_client,
)

TEACHINGS_DIR = PROJECT_DIR / "teachings"
READINGS_DIR = PROJECT_DIR / "readings"
RESTORED_DIR = PROJECT_DIR / "restored"
SPIRITUAL_LEXICON_PATH = PROJECT_DIR / "spiritual_lexicon.json"
SECTIONS_DIR = PROJECT_DIR / "sections"
CHAPTERS_DIR = PROJECT_DIR / "sections" / "chapters"
BOOK_FILE = PROJECT_DIR / "book.json"

LACUNA_RE = re.compile(r"\{(\d+)\}")

SECTION_TOOL_NAME = "compose_section"
CHAPTER_TOOL_NAME = "compose_chapter"
FINALIZE_TOOL_NAME = "finalize_book"


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

COMPOSE_SECTION_TOOL = {
    "name": SECTION_TOOL_NAME,
    "description": (
        "Define one major section of the book. Call once per section. "
        "A section groups teachings by content and spiritual arc."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "section_number": {
                "type": "integer",
                "description": "Sequential section number (1, 2, 3, ...).",
            },
            "title": {
                "type": "string",
                "description": "Section title for the reader.",
            },
            "teaching_numbers": {
                "type": "array",
                "items": {"type": "integer"},
                "description": (
                    "Teaching numbers in this section, in reading order."
                ),
            },
            "summary": {
                "type": "string",
                "description": (
                    "What this section covers: its subject, arc, and "
                    "why these teachings belong together."
                ),
            },
            "role": {
                "type": "string",
                "enum": [
                    "foundation",
                    "exposition",
                    "elaboration",
                    "sequence",
                    "parallel_treatment",
                    "transition",
                    "culmination",
                    "coda",
                    "fragment_cluster",
                ],
                "description": "The section's structural role in the book.",
            },
            "organizing_principle": {
                "type": "string",
                "description": (
                    "Why these teachings belong together and how they "
                    "are internally ordered."
                ),
            },
        },
        "required": [
            "section_number",
            "title",
            "teaching_numbers",
            "summary",
            "role",
            "organizing_principle",
        ],
    },
}

COMPOSE_CHAPTER_TOOL = {
    "name": CHAPTER_TOOL_NAME,
    "description": (
        "Define one reader-facing chapter within a section. Call once "
        "per chapter. Chapters group one or more teaching atoms into "
        "a reading unit."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "chapter_number": {
                "type": "integer",
                "description": "Sequential chapter number across the book.",
            },
            "section_number": {
                "type": "integer",
                "description": "Section this chapter belongs to.",
            },
            "position_in_section": {
                "type": "integer",
                "description": (
                    "Chapter position within its section (1, 2, ...)."
                ),
            },
            "title": {
                "type": "string",
                "description": "Reader-facing title for this chapter.",
            },
            "teaching_numbers": {
                "type": "array",
                "items": {"type": "integer"},
                "description": (
                    "Teaching atoms grouped into this chapter, in "
                    "reading order."
                ),
            },
            "role": {
                "type": "string",
                "enum": [
                    "primary_teaching",
                    "foundation",
                    "elaboration",
                    "parallel_treatment",
                    "summary",
                    "transition",
                    "fragment_cluster",
                ],
                "description": "The chapter's role within its section.",
            },
            "description": {
                "type": "string",
                "description": (
                    "What this chapter teaches and why the grouped "
                    "teaching atoms belong together."
                ),
            },
        },
        "required": [
            "chapter_number",
            "section_number",
            "position_in_section",
            "title",
            "teaching_numbers",
            "role",
            "description",
        ],
    },
}

FINALIZE_BOOK_TOOL = {
    "name": FINALIZE_TOOL_NAME,
    "description": (
        "Finalize the book structure after all sections and chapters "
        "have been composed. Call exactly once at the end."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "book_title": {
                "type": "string",
                "description": "Title for the composed book.",
            },
            "total_sections": {
                "type": "integer",
                "description": "Total number of sections composed.",
            },
            "total_chapters": {
                "type": "integer",
                "description": "Total number of chapters composed.",
            },
            "total_teachings": {
                "type": "integer",
                "description": (
                    "Total teachings included across all chapters."
                ),
            },
            "section_reading_order": {
                "type": "array",
                "items": {"type": "integer"},
                "description": (
                    "Section numbers in reading order. This is the "
                    "book's table of contents."
                ),
            },
            "structural_overview": {
                "type": "string",
                "description": (
                    "How the book is organized overall: what the major "
                    "movements are, how the sections flow, what patterns "
                    "emerge from the composition."
                ),
            },
            "reading_order_note": {
                "type": "string",
                "description": (
                    "Does the current teaching order reflect the book's "
                    "natural order? If rearrangement was needed, explain."
                ),
            },
            "observations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "teaching_numbers": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                        "content": {"type": "string"},
                    },
                    "required": ["title", "content"],
                },
                "description": (
                    "Cross-cutting structural observations that span "
                    "multiple sections."
                ),
            },
            "excluded_teachings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "teaching": {"type": "integer"},
                        "reason": {"type": "string"},
                    },
                    "required": ["teaching", "reason"],
                },
                "description": (
                    "Teachings excluded from the book, if any."
                ),
            },
        },
        "required": [
            "book_title",
            "total_sections",
            "total_chapters",
            "total_teachings",
            "section_reading_order",
            "structural_overview",
            "reading_order_note",
        ],
    },
}


# ---------------------------------------------------------------------------
# System prompt — content-driven, no Grand Man bias
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert in the doctrine of correspondences as written by \
Emanuel Swedenborg, with deep specialization in ancient cosmological \
vocabulary: Zoroastrian, Manichaean, Persian-Iranian, Syriac, and Coptic.

You are composing the book-level architecture of the Ancient Word as \
theorized by Emanual Swedenborg. The content presented is an extract of \
the oldest layers of the Coptic Kephalaia's..

## WHAT HAS ALREADY BEEN DONE

The input has already been assembled into whole correspondential teaching \
arcs. A teaching is one self-contained spiritual truth expressed through \
cosmological imagery. Enumerations inside one arc are stages of that \
teaching, not separate teachings. These numbered teaching files are the \
atom layer for this stage, and each preserves continuous section references \
back to the source.

Do not rediscover the atom boundaries from scratch. Treat the numbered \
teachings as the primary structural atoms unless the corpus itself clearly \
shows that a teaching is only a fragment, duplicate treatment, or misplaced \
orphan.

The input also includes a corpus spiritual lexicon. Do not build a new \
lexicon. Use the supplied lexicon summary only as vocabulary authority for \
recognizing recurring systems.

Each teaching includes a whole-teaching correspondential reading. These \
readings show each teaching's spiritual arc.

## PRIMARY ORGANIZING PRINCIPLE

Compose by SPIRITUAL READING, not by surface narrative. The Stage 5 \
correspondential reading is the primary structural signal; the cosmological \
story (emanations, archons, light/darkness mixture, ships of the sun and \
moon, etc.) is the natural-degree vessel through which the spiritual content \
is expressed. Two teachings that tell different cosmological stories but \
deliver the same spiritual content (e.g. how the proprium claims what flows \
through it; how influx descends through discrete degrees; how the Lord is \
present at every level of the regenerating soul) belong together. Two \
teachings that share cosmological vocabulary but deliver different spiritual \
content do not.

Group and sequence on what the reading says the teaching IS — not on what \
the surface story depicts. When the cosmogonic sequence and the spiritual \
arc disagree about grouping, follow the spiritual arc.

Some lacunae have been restored where Coptic, English, apparatus, and \
spiritual context constrained a fill. The prompt shows compact restoration \
counts and notes. Unrestorable gaps remain unresolved in the underlying data.

## YOUR TASK

Read the complete teaching sequence holistically and compose the book in \
three passes:

### Pass 1: Sections
Call compose_section for each major section of the book. A section groups \
teachings that belong together by content, spiritual arc, and compositional \
logic. Do not force a predetermined number of sections — let the content \
determine how many sections the book naturally has.

### Pass 2: Chapters
After all sections are defined, call compose_chapter for each reader-facing \
chapter within those sections. The 104 teaching atoms are fine-grained; \
group them into reader-facing chapters or sequences inside the sections \
rather than treating every atom as an equal book chapter.

### Pass 3: Finalize
After all chapters are defined, call finalize_book exactly once to set the \
overall book structure, title, and reading order.

## HOW TO READ THE INPUT

Each teaching is shown with:

- its teaching number and section range
- the Stage 4b title and boundary confidence
- restored Coptic/English core text, with source chapter.line anchors
- Stage 5 arc and whole-teaching reading
- major images from the reading
- Stage 6 restoration note and counts

The section numbers are the stable continuous corpus references. Source \
chapter.line anchors are useful provenance, but do not over-interpret them \
as precise manuscript-line alignment beyond what the source data supports.

## STRUCTURAL PRINCIPLES TO LOOK FOR

(Listed in priority order. Higher-priority principles override lower ones \
when they disagree about grouping.)

1. Spiritual arc convergence: teachings whose Stage 5 readings describe \
   the same correspondential movement, even when their surface stories \
   differ.
2. Subject coherence at the spiritual level: teachings about the same \
   spiritual system (proprium, influx, regeneration, the Divine Human in \
   ultimates, the discrete degrees, the ruling love) regardless of which \
   cosmological figures carry the content.
3. Correspondence maps: body, faculty, element, geography, astronomy, or \
   ritual mapped onto spiritual process.
4. Numerical structures: three-fold, five-fold, seven-fold, ten-fold, or \
   twelve-fold sequences that organize local teaching material.
5. Repeated treatments: the same spiritual system appearing in fuller and \
   fragmentary forms. Prefer the fuller form; mark fragments as parallel \
   or excluded.
6. Cosmogonic sequence at the surface (emanation, descent, mixture, \
   rescue, purification, ascent, completion). Use only as a tiebreaker \
   among teachings whose spiritual content is already coherent.
7. Transmission layers: Persian/Iranian substrate, Coptic translation \
   layer, and Manichaean naming overlay. This matters for grouping but \
   is not itself an error.
8. Teaching seams: where one arc completes and the next builds from it.

## RULES

1. Preserve Stage 4b's teaching boundaries as the default.
2. Structure from spiritual arc and corpus logic, not from editorial chapter \
   divisions or page accidents.
3. Prefer conservative rearrangement. If current order works, keep it.
4. Exclude only when a teaching is genuinely orphaned, duplicate, or too \
   damaged to serve the composition. Damaged but structurally meaningful \
   teachings can remain as fragments.
5. Do not impose any predetermined grid, degree system, or body-mapping \
   onto the sections. Group by content and spiritual arc only.
6. Do not reproduce long source text in the output. The schema must \
   reference teaching numbers and section ranges.
7. If a term is ambiguous across teachings, treat that ambiguity as a \
   structural observation when it affects grouping or sequence.
8. Every teaching (1-104) must be assigned to exactly one section and \
   one chapter. Do not leave any teaching unassigned.

This is composition, not review. Do not correct gap fills, do not rewrite \
the readings, and do not generate new text for the book. Produce a \
structural schema only.

Begin with compose_section calls. Then compose_chapter calls. Then \
finalize_book."""


# ---------------------------------------------------------------------------
# Loading and formatting helpers
# ---------------------------------------------------------------------------

def load_all_teachings(directory: Path) -> dict[int, dict]:
    """Load t_NNN.json files keyed by teaching number."""
    result = {}
    for path in sorted(directory.glob("t_*.json")):
        match = re.match(r"t_(\d+)\.json", path.name)
        if not match:
            continue
        teaching_num = int(match.group(1))
        with open(path, encoding="utf-8") as f:
            result[teaching_num] = json.load(f)
    return result


def load_json(path: Path) -> dict:
    """Load a JSON file if present, else return an empty dict."""
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def shorten(text: str | None, limit: int = 600) -> str:
    """Normalize whitespace and trim long prompt support fields."""
    if not text:
        return ""
    normalized = re.sub(r"\s+", " ", str(text)).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def restoration_lookup(restored: dict) -> dict[int, dict]:
    """Return Stage 6 restoration decisions keyed by gap ID."""
    lookup = {}
    for item in restored.get("restorations", []):
        gap_id = item.get("gap_id")
        if isinstance(gap_id, int):
            lookup[gap_id] = item
    return lookup


def apply_restorations(text: str, lookup: dict[int, dict], field: str) -> str:
    """Inline Stage 6 fills for readability, leaving unrestorable gaps."""
    if not text:
        return ""

    def replace(match: re.Match) -> str:
        gap_id = int(match.group(1))
        decision = lookup.get(gap_id)
        if not decision or decision.get("confidence") == "unrestorable":
            return match.group(0)
        fill = decision.get(field)
        if not fill:
            return match.group(0)
        if decision.get("confidence") == "low":
            return f"[{fill}?]"
        return str(fill)

    return LACUNA_RE.sub(replace, text)


def format_lexicon_summary(lexicon: dict) -> str:
    """Format the Stage 4d lexicon as compact compose context."""
    entries = lexicon.get("entries", [])
    if not entries:
        return ""
    lines = [
        f"Spiritual lexicon authority ({lexicon.get('total_entries', len(entries))} entries):"
    ]
    for entry in entries:
        term = entry.get("english_term") or entry.get("natural_term") or "?"
        use = entry.get("use_in_reading") or entry.get("spiritual_meaning") or ""
        refs = entry.get("section_refs") or []
        ref_text = ", ".join(str(ref) for ref in refs[:3])
        line = f"- {term}"
        if use:
            line += f": {shorten(use, 160)}"
        if ref_text:
            line += f" [refs: {ref_text}]"
        lines.append(line)
    return "\n".join(lines)


def format_major_images(images: list[dict]) -> str:
    """Format Stage 5 major images."""
    lines = []
    for image in images[:8]:
        natural = image.get("image", "?")
        meaning = image.get("meaning", "")
        lines.append(f"- {natural}: {shorten(meaning, 220)}")
    return "\n".join(lines)


def format_core_excerpt(
    teaching: dict,
    restored: dict,
    *,
    max_segments: int = 8,
) -> str:
    """Format compact restored-English excerpts for structural anchoring."""
    lookup = restoration_lookup(restored)
    segments = [
        segment for segment in teaching.get("segments", [])
        if segment.get("classification") in ("cosmological_substrate", "mixed")
        and (segment.get("core_english") or segment.get("core_coptic"))
    ]
    if not segments:
        return ""

    if len(segments) <= max_segments:
        selected = segments
    else:
        head = max_segments // 2
        tail = max_segments - head
        selected = segments[:head] + segments[-tail:]

    lines = []
    tail_start = max_segments // 2 if len(segments) > max_segments else None
    for index, segment in enumerate(selected):
        if tail_start is not None and index == tail_start:
            lines.append("...")
        section = segment.get("section")
        english = apply_restorations(
            segment.get("core_english") or "", lookup, "proposed_english"
        )
        if not english:
            english = "[Coptic-only segment]"
        lines.append(f"[§{section}] {shorten(english, 280)}")
    return "\n".join(lines)


def format_teaching(
    teaching_num: int,
    teaching: dict,
    reading: dict,
    restored: dict,
) -> str:
    """Format one teaching as compose prompt context."""
    parts = [
        f"=== Teaching {teaching_num}: {teaching.get('title', '')} ===",
        (
            f"Sections: §{teaching.get('start_section')}"
            f"-§{teaching.get('end_section')}; "
            f"boundary confidence: {teaching.get('confidence', '')}; "
            f"sections: {teaching.get('total_sections', 0)}; "
            f"lacunae: {teaching.get('total_lacunae', 0)}"
        ),
        "",
        "## Core Excerpts (restored English where available)",
    ]
    excerpt = format_core_excerpt(teaching, restored)
    parts.append(excerpt or "No compact core excerpt available.")

    parts.append("## Whole-Teaching Reading")
    if reading.get("title"):
        parts.append(f"Reading title: {reading.get('title')}")
    if reading.get("confidence"):
        parts.append(f"Reading confidence: {reading.get('confidence')}")
    if reading.get("arc"):
        parts.append(f"Arc: {reading.get('arc')}")
    if reading.get("reading"):
        parts.append(shorten(reading.get("reading", ""), 2400))
    images = reading.get("major_images") or []
    if images:
        parts.append("Major images:")
        parts.append(format_major_images(images))
    if not reading:
        parts.append("No Stage 5 reading found.")

    parts.append("\n## Restoration Summary")
    parts.append(
        f"Total gaps: {restored.get('total_gaps_in_core', 0)}; "
        f"restored: {restored.get('gaps_restored', 0)}; "
        f"unrestorable: {restored.get('gaps_unrestorable', 0)}"
    )
    note = shorten(restored.get("restoration_note"), 420)
    if note:
        parts.append(f"Restoration note: {note}")

    return "\n".join(parts)


def format_corpus_for_composition(
    teaching_numbers: list[int],
    teachings: dict[int, dict],
    readings: dict[int, dict],
    restorations_by_teaching: dict[int, dict],
    lexicon: dict,
) -> str:
    """Format the complete corpus for the composition prompt."""
    parts = []
    lexicon_summary = format_lexicon_summary(lexicon)
    if lexicon_summary:
        parts.extend([
            "# Corpus Spiritual Lexicon",
            lexicon_summary,
            "",
            "---",
            "",
        ])

    parts.append("# Teaching Corpus")
    for teaching_num in teaching_numbers:
        parts.append(
            format_teaching(
                teaching_num,
                teachings[teaching_num],
                readings.get(teaching_num, {}),
                restorations_by_teaching.get(teaching_num, {}),
            )
        )
        parts.append("")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Completeness validation
# ---------------------------------------------------------------------------

def _completeness_report(
    all_teaching_numbers: list[int],
    sections: dict[int, dict],
    chapters: dict[int, dict],
    book_metadata: dict | None,
) -> dict[str, Any]:
    """Check whether the composition is complete."""
    # Teachings assigned in sections
    section_teachings: set[int] = set()
    for sec in sections.values():
        section_teachings.update(sec.get("teaching_numbers", []))

    # Teachings assigned in chapters
    chapter_teachings: set[int] = set()
    for ch in chapters.values():
        chapter_teachings.update(ch.get("teaching_numbers", []))

    # Excluded teachings (from finalize if available)
    excluded: set[int] = set()
    if book_metadata:
        for exc in book_metadata.get("excluded_teachings", []):
            excluded.add(exc.get("teaching", -1))

    all_set = set(all_teaching_numbers)
    assigned = section_teachings | excluded
    missing_from_sections = sorted(all_set - assigned)
    missing_from_chapters = sorted(
        section_teachings - chapter_teachings - excluded
    )

    # Sections without chapters
    sections_with_chapters = {
        ch.get("section_number") for ch in chapters.values()
    }
    sections_without_chapters = sorted(
        s for s in sections if s not in sections_with_chapters
    )

    # Duplicate teaching assignments
    section_counts = Counter()
    for sec in sections.values():
        section_counts.update(sec.get("teaching_numbers", []))
    duplicates_in_sections = sorted(
        t for t, c in section_counts.items() if c > 1
    )

    chapter_counts = Counter()
    for ch in chapters.values():
        chapter_counts.update(ch.get("teaching_numbers", []))
    duplicates_in_chapters = sorted(
        t for t, c in chapter_counts.items() if c > 1
    )

    complete = (
        not missing_from_sections
        and not missing_from_chapters
        and not sections_without_chapters
        and not duplicates_in_sections
        and not duplicates_in_chapters
        and book_metadata is not None
    )

    return {
        "complete": complete,
        "sections_count": len(sections),
        "chapters_count": len(chapters),
        "teachings_in_sections": len(section_teachings),
        "teachings_in_chapters": len(chapter_teachings),
        "excluded_count": len(excluded),
        "missing_from_sections": missing_from_sections,
        "missing_from_chapters": missing_from_chapters,
        "sections_without_chapters": sections_without_chapters,
        "duplicates_in_sections": duplicates_in_sections,
        "duplicates_in_chapters": duplicates_in_chapters,
        "finalized": book_metadata is not None,
    }


def _build_continuation_prompt(report: dict) -> str:
    """Build a follow-up prompt telling the model what is still missing."""
    parts = ["## Composition Progress\n"]

    parts.append(
        f"Sections so far: {report['sections_count']}, "
        f"Chapters so far: {report['chapters_count']}, "
        f"Teachings assigned: {report['teachings_in_sections']} "
        f"(sections) / {report['teachings_in_chapters']} (chapters)"
    )

    if report["missing_from_sections"]:
        nums = ", ".join(str(t) for t in report["missing_from_sections"])
        parts.append(
            f"\n**Teachings not yet assigned to any section**: {nums}\n"
            f"Call compose_section to create sections for these, or add "
            f"them to existing sections by calling compose_section again "
            f"with an updated teaching_numbers list."
        )
    if report["duplicates_in_sections"]:
        nums = ", ".join(str(t) for t in report["duplicates_in_sections"])
        parts.append(
            f"\n**Teachings assigned to multiple sections**: {nums}\n"
            f"Each teaching must appear in exactly one section."
        )
    if report["sections_without_chapters"]:
        nums = ", ".join(str(s) for s in report["sections_without_chapters"])
        parts.append(
            f"\n**Sections without chapters**: {nums}\n"
            f"Call compose_chapter to create chapters for these sections."
        )
    if report["missing_from_chapters"]:
        nums = ", ".join(str(t) for t in report["missing_from_chapters"])
        parts.append(
            f"\n**Teachings in sections but not in chapters**: {nums}\n"
            f"Call compose_chapter to assign these to chapters."
        )
    if report["duplicates_in_chapters"]:
        nums = ", ".join(str(t) for t in report["duplicates_in_chapters"])
        parts.append(
            f"\n**Teachings assigned to multiple chapters**: {nums}\n"
            f"Each teaching must appear in exactly one chapter."
        )

    if not report["finalized"]:
        if (
            not report["missing_from_sections"]
            and not report["missing_from_chapters"]
            and not report["sections_without_chapters"]
            and not report["duplicates_in_sections"]
            and not report["duplicates_in_chapters"]
        ):
            parts.append(
                "\n**All teachings assigned. All sections have chapters.**\n"
                "Call finalize_book to complete the composition."
            )
        else:
            parts.append(
                "\nResolve the issues above before calling finalize_book."
            )

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Iterative multi-turn composition loop
# ---------------------------------------------------------------------------

MAX_TURNS = 60

TOOLS = [COMPOSE_SECTION_TOOL, COMPOSE_CHAPTER_TOOL, FINALIZE_BOOK_TOOL]


def run_composition_loop(
    client: AnthropicFoundry,
    deployment: str,
    user_message: str,
    all_teaching_numbers: list[int],
    *,
    effort: str = "max",
    debug: bool = False,
) -> tuple[dict[int, dict], dict[int, dict], dict | None]:
    """Run the iterative multi-turn composition loop.

    Returns (sections, chapters, book_metadata).
    """
    sections: dict[int, dict] = {}
    chapters: dict[int, dict] = {}
    book_metadata: dict | None = None

    messages: list[dict] = [{"role": "user", "content": user_message}]

    thinking_config = {
        "type": "adaptive",
        "display": "summarized" if debug else "omitted",
    }

    for turn in range(1, MAX_TURNS + 1):
        print(f"\n  --- Turn {turn} ---", flush=True)

        kwargs: dict[str, Any] = dict(
            model=deployment,
            max_tokens=128_000,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=TOOLS,
            thinking=thinking_config,
        )
        if effort != "xhigh":
            kwargs["output_config"] = {"effort": effort}

        t0 = time.time()

        try:
            with client.messages.stream(**kwargs) as stream:
                for event in stream:
                    etype = getattr(event, "type", "")
                    if etype == "content_block_start":
                        block = getattr(event, "content_block", None)
                        btype = getattr(block, "type", "") if block else ""
                        if debug:
                            elapsed = time.time() - t0
                            print(
                                f"\n  [{btype} {elapsed:.0f}s]",
                                end="", flush=True,
                            )
                    elif etype == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        if delta:
                            dtype = getattr(delta, "type", "")
                            if dtype == "thinking_delta" and debug:
                                chunk = getattr(delta, "thinking", "") or ""
                                sys.stdout.write(chunk)
                                sys.stdout.flush()
                            elif dtype == "signature_delta" and debug:
                                elapsed = time.time() - t0
                                print(
                                    f" sig@{elapsed:.0f}s",
                                    end="", flush=True,
                                )
                    elif etype == "content_block_stop":
                        if debug:
                            elapsed = time.time() - t0
                            print(f" done@{elapsed:.0f}s", flush=True)

                response = stream.get_final_message()

        except (httpx.ReadTimeout, httpx.ConnectTimeout,
                httpx.RemoteProtocolError, httpx.ReadError,
                ConnectionError, OSError) as exc:
            print(f"  [TIMEOUT/ERROR] {exc} — retrying turn {turn}")
            time.sleep(5)
            try:
                with client.messages.stream(**kwargs) as stream:
                    for event in stream:
                        pass
                    response = stream.get_final_message()
            except Exception as exc2:
                print(f"  [FATAL] Retry failed: {exc2}")
                break

        elapsed = time.time() - t0
        if debug:
            print(
                f"  {elapsed:.0f}s"
                f" (in={response.usage.input_tokens}"
                f" out={response.usage.output_tokens})",
                flush=True,
            )

        # Collect tool calls and text from the response
        tool_results = []
        text_parts = []

        for block in response.content:
            if block.type == "thinking":
                pass  # already streamed above
            elif block.type == "text":
                text_parts.append(block.text)
                if debug:
                    print(f"  [TEXT] {block.text[:200]}")
            elif block.type == "tool_use":
                tool_name = block.name
                tool_input = block.input
                tool_id = block.id

                if tool_name == SECTION_TOOL_NAME:
                    sec_num = tool_input.get("section_number", 0)
                    sections[sec_num] = tool_input
                    print(
                        f"  [SECTION {sec_num}] "
                        f"{tool_input.get('title', '?')} — "
                        f"{len(tool_input.get('teaching_numbers', []))} "
                        f"teachings"
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": json.dumps({
                            "status": "ok",
                            "section_number": sec_num,
                            "recorded": True,
                        }),
                    })

                elif tool_name == CHAPTER_TOOL_NAME:
                    ch_num = tool_input.get("chapter_number", 0)
                    chapters[ch_num] = tool_input
                    print(
                        f"  [CHAPTER {ch_num}] "
                        f"s{tool_input.get('section_number', '?')} — "
                        f"{tool_input.get('title', '?')} — "
                        f"{len(tool_input.get('teaching_numbers', []))} "
                        f"teachings"
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": json.dumps({
                            "status": "ok",
                            "chapter_number": ch_num,
                            "recorded": True,
                        }),
                    })

                elif tool_name == FINALIZE_TOOL_NAME:
                    book_metadata = tool_input
                    print(
                        f"  [FINALIZE] {tool_input.get('book_title', '?')} — "
                        f"{tool_input.get('total_sections', '?')} sections, "
                        f"{tool_input.get('total_chapters', '?')} chapters"
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": json.dumps({
                            "status": "ok",
                            "finalized": True,
                        }),
                    })

                else:
                    print(f"  [UNKNOWN TOOL] {tool_name}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": json.dumps({
                            "status": "error",
                            "message": f"Unknown tool: {tool_name}",
                        }),
                    })

        # Add assistant response and tool results to messages.
        # The Anthropic API rejects assistant messages whose final block is
        # `thinking`. If the model emitted only thinking (no text, no
        # tool_use), we cannot append the response — drop it and treat the
        # turn as a no-op so the nudge below restarts cleanly.
        has_actionable = bool(text_parts) or bool(tool_results)
        if has_actionable:
            messages.append(
                {"role": "assistant", "content": response.content}
            )
            if tool_results:
                messages.append(
                    {"role": "user", "content": tool_results}
                )
        else:
            print(
                "  [WARN] Assistant emitted only thinking — "
                "skipping assistant turn and nudging."
            )

        # Check completeness
        report = _completeness_report(
            all_teaching_numbers, sections, chapters, book_metadata
        )

        if report["complete"]:
            print("\n  Composition complete.")
            break

        # If model stopped without tool calls (or emitted only thinking),
        # nudge it to commit something next turn.
        if not has_actionable:
            continuation = _build_continuation_prompt(report)
            print(f"  [NUDGE] {continuation[:200]}...")
            messages.append({"role": "user", "content": continuation})

        elif response.stop_reason == "end_turn" and not tool_results:
            continuation = _build_continuation_prompt(report)
            print(f"  [NUDGE] {continuation[:200]}...")
            messages.append({"role": "user", "content": continuation})

        # If model stopped after tool calls, send continuation prompt
        elif response.stop_reason == "end_turn":
            continuation = _build_continuation_prompt(report)
            messages.append({"role": "user", "content": continuation})

    else:
        print(f"\n  WARNING: Hit max turns ({MAX_TURNS}) without completing.")

    return sections, chapters, book_metadata


# ---------------------------------------------------------------------------
# CLI and main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage 8: Compose Kephalaia v2 book structure"
    )
    parser.add_argument("--dry-run", "-n", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--effort", default="max",
        choices=["low", "medium", "high", "xhigh", "max"],
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("Stage 8: Compose Structure")
    print("  Book-level structure from teaching-level substrate")

    teachings = load_all_teachings(TEACHINGS_DIR)
    readings = load_all_teachings(READINGS_DIR)
    restorations_by_teaching = load_all_teachings(RESTORED_DIR)
    lexicon = load_json(SPIRITUAL_LEXICON_PATH)

    if not teachings:
        print(f"\nERROR: No teachings in {TEACHINGS_DIR}")
        sys.exit(1)

    all_teaching_numbers = sorted(teachings.keys())

    print(f"  Teachings:    {len(teachings)}")
    print(f"  Readings:     {len(readings)}")
    print(f"  Restorations: {len(restorations_by_teaching)}")
    print(f"  Lexicon:      {lexicon.get('total_entries', 0)} entries")
    print(f"  Output dirs:  {SECTIONS_DIR.name}/, {CHAPTERS_DIR.name}/")
    print(f"  Book file:    {BOOK_FILE.name}")

    # Check for existing output
    if BOOK_FILE.exists() and not args.overwrite and not args.dry_run:
        print("\n  Book already exists (use --overwrite)")
        return

    corpus_text = format_corpus_for_composition(
        all_teaching_numbers,
        teachings,
        readings,
        restorations_by_teaching,
        lexicon,
    )
    est_tokens = len(corpus_text) / 3.5
    print(
        f"  Corpus size:  {len(corpus_text):,} chars "
        f"(~{est_tokens:,.0f} tokens)"
    )

    if args.dry_run:
        print("\n[DRY RUN] No API calls made.")
        print("\n--- Sample (first 2500 chars) ---")
        print(corpus_text[:2500])
        print("--- end sample ---")
        return

    client, deployment = create_client()
    print(f"\n  Deployment: {deployment}")
    print(f"  Effort: {args.effort}")
    print("\n  Composing book structure...", flush=True)

    user_msg = (
        f"## Complete Kephalaia v2 Teaching Corpus\n\n"
        f"Total teachings: {len(all_teaching_numbers)}.\n"
        f"Teaching numbers: {all_teaching_numbers}\n"
        f"Use teaching numbers and section ranges in the output.\n\n"
        f"{corpus_text}\n\n"
        f"Compose the book-level architecture. Begin with "
        f"compose_section calls for each major section."
    )

    started = time.time()
    sections, chapters, book_metadata = run_composition_loop(
        client,
        deployment,
        user_msg,
        all_teaching_numbers,
        effort=args.effort,
        debug=args.debug,
    )
    elapsed = time.time() - started

    # Save sections
    SECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    for sec_num, sec_data in sorted(sections.items()):
        out_path = SECTIONS_DIR / f"s_{sec_num:03d}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(sec_data, f, indent=2, ensure_ascii=False)

    # Save chapters
    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)
    for ch_num, ch_data in sorted(chapters.items()):
        out_path = CHAPTERS_DIR / f"ch_{ch_num:03d}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(ch_data, f, indent=2, ensure_ascii=False)

    # Save book metadata
    if book_metadata:
        book_metadata["_input_summary"] = {
            "teaching_count": len(all_teaching_numbers),
            "reading_files": len(readings),
            "restoration_files": len(restorations_by_teaching),
            "lexicon_entries": lexicon.get("total_entries", 0),
            "corpus_chars": len(corpus_text),
        }
        with open(BOOK_FILE, "w", encoding="utf-8") as f:
            json.dump(book_metadata, f, indent=2, ensure_ascii=False)

    # Final report
    report = _completeness_report(
        all_teaching_numbers, sections, chapters, book_metadata
    )

    print(f"\n{'=' * 60}")
    print(f"  Stage 8: Composition {'COMPLETE' if report['complete'] else 'INCOMPLETE'}")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"  Sections: {report['sections_count']}")
    print(f"  Chapters: {report['chapters_count']}")
    print(f"  Teachings in sections: {report['teachings_in_sections']}")
    print(f"  Teachings in chapters: {report['teachings_in_chapters']}")
    if report["excluded_count"]:
        print(f"  Excluded teachings: {report['excluded_count']}")
    if report["missing_from_sections"]:
        print(f"  MISSING from sections: {report['missing_from_sections']}")
    if report["missing_from_chapters"]:
        print(f"  MISSING from chapters: {report['missing_from_chapters']}")
    if report["duplicates_in_sections"]:
        print(f"  DUPLICATES in sections: {report['duplicates_in_sections']}")
    if report["duplicates_in_chapters"]:
        print(f"  DUPLICATES in chapters: {report['duplicates_in_chapters']}")
    if book_metadata:
        print(f"  Book title: {book_metadata.get('book_title', '?')}")
        order = book_metadata.get("section_reading_order", [])
        if order:
            print(f"  Reading order: {order}")
    else:
        print("  WARNING: finalize_book was never called")
    print(f"{'=' * 60}")

    # Print section/chapter summary
    if sections:
        print("\n  Section Summary:")
        for sec_num in sorted(sections):
            sec = sections[sec_num]
            t_count = len(sec.get("teaching_numbers", []))
            print(
                f"    S{sec_num}: {sec.get('title', '?')} "
                f"({t_count} teachings, role: {sec.get('role', '?')})"
            )

    if chapters:
        print("\n  Chapter Summary:")
        for ch_num in sorted(chapters):
            ch = chapters[ch_num]
            t_count = len(ch.get("teaching_numbers", []))
            print(
                f"    Ch{ch_num} (S{ch.get('section_number', '?')}): "
                f"{ch.get('title', '?')} ({t_count} teachings)"
            )


if __name__ == "__main__":
    main()