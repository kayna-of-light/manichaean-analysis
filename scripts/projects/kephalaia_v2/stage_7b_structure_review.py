#!/usr/bin/env python3
"""
Stage 7b — Architectural research: does the reading order track the descent?

Pipeline stage 7b. Advisory only. Independent of any composition stage.

This is a research stage. The question is about SEQUENTIAL ORDER:

  Do the 104 teachings, read in their current order, follow the descent
  pattern that influx traces through the Grand Man?

The Grand Man hypothesis predicts a specific ORDER:

  1. The corpus begins at the celestial degree and descends through the
     spiritual to the natural.
  2. Within each degree, influx passes from love (east) through wisdom
     (south) through rational (north) to ultimates (west).
  3. This gives 3 × 4 = 12 sequential positions in the descent.
  4. Five-fold constitution operates radially at every point — like how
     every part of the body is structured in fives. The fact that the
     corpus is saturated with five-fold structures is itself strong
     evidence for the Grand Man architecture: the fives are everywhere
     BECAUSE the book is structured as the body, and the body has
     five-fold constitution at every point.

The hypothesis is NOT about whether the number twelve appears in the text,
whether the corpus names 'east' or 'four directions,' or whether explicit
four-fold or twelve-fold structures are referenced. It is about whether the
TEACHINGS THEMSELVES, read in order, treat progressively lower registers
and progressively more outward faculties.

The pervasive five-fold structures throughout the corpus are already
confirmed. They are not a coincidence — they are a structural property
of the writing, evidence that the whole book is structured as the Grand
Man (which has five-fold constitution at every point). This stage takes
that as established fact and investigates the sequential descent.

The hypothesis does NOT predict:
  - That parts grow in size toward ultimates.
  - That the number twelve must be named explicitly.
  - That size asymmetry is doctrinal.
  - That the corpus must culminate.

Input:
    - output/projects/kephalaia_v2/teachings/t_NNN.json
    - output/projects/kephalaia_v2/readings/t_NNN.json

Output:
    - output/projects/kephalaia_v2/structure_research.json

Usage:
    python scripts/projects/kephalaia_v2/stage_7b_structure_review.py
    python scripts/projects/kephalaia_v2/stage_7b_structure_review.py --dry-run
    python scripts/projects/kephalaia_v2/stage_7b_structure_review.py --debug
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_base import (  # noqa: E402
    PROJECT_DIR,
    create_client,
    stream_tool_call,
)

TEACHINGS_DIR = PROJECT_DIR / "teachings"
READINGS_DIR = PROJECT_DIR / "readings"
DEFAULT_OUTPUT_FILE = PROJECT_DIR / "structure_research.json"


# ---------------------------------------------------------------------------
# Tool schema
# ---------------------------------------------------------------------------

RESEARCH_TOOL = {
    "name": "commit_structure_research",
    "description": (
        "Commit the architectural research findings. Call exactly once."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "scope": {
                "type": "string",
                "description": (
                    "What was investigated and how."
                ),
            },
            "summary": {
                "type": "string",
                "description": (
                    "One-paragraph plain-language summary: does the reading "
                    "order of the 104 teachings track the descent of influx "
                    "through the Grand Man?"
                ),
            },
            "degree_descent": {
                "type": "object",
                "description": (
                    "Does the reading order move from celestial to spiritual "
                    "to natural? This is about the REGISTER each teaching "
                    "operates at — not about whether the teaching mentions "
                    "three or names celestial things. A teaching that treats "
                    "the Father's inmost nature operates at a celestial "
                    "register; one that treats how cosmic forces mediate "
                    "between source and effect operates at the spiritual; one "
                    "that treats the visible body, senses, or material cosmos "
                    "operates at the natural."
                ),
                "properties": {
                    "verdict": {
                        "type": "string",
                        "enum": [
                            "clear_descent",
                            "rough_descent",
                            "mixed_but_trend_visible",
                            "no_clear_pattern",
                            "underdetermined",
                        ],
                    },
                    "celestial_range": {
                        "type": "string",
                        "description": (
                            "Which teaching numbers predominantly operate at "
                            "the celestial register? Give an approximate "
                            "range with evidence from the readings."
                        ),
                    },
                    "spiritual_range": {
                        "type": "string",
                        "description": (
                            "Which teaching numbers predominantly operate at "
                            "the spiritual register?"
                        ),
                    },
                    "natural_range": {
                        "type": "string",
                        "description": (
                            "Which teaching numbers predominantly operate at "
                            "the natural register?"
                        ),
                    },
                    "degree_transitions": {
                        "type": "string",
                        "description": (
                            "Where in the sequence do the transitions between "
                            "degrees fall? Are they sharp or gradual? Are "
                            "there teachings that break the sequence?"
                        ),
                    },
                    "counterexamples": {
                        "type": "string",
                        "description": (
                            "Teachings whose register does not fit the "
                            "sequential descent pattern. Do they break it, or "
                            "are they local exceptions in an otherwise clear "
                            "trajectory?"
                        ),
                    },
                },
                "required": [
                    "verdict",
                    "celestial_range",
                    "spiritual_range",
                    "natural_range",
                    "degree_transitions",
                    "counterexamples",
                ],
            },
            "directional_winding": {
                "type": "object",
                "description": (
                    "Within each degree, does the sequence wind from love "
                    "(east) through wisdom (south) through rational (north) "
                    "to ultimates (west)? This is about the TONE of each "
                    "teaching — not whether it names directions. A teaching "
                    "that treats what a thing IS at its source (its ruling "
                    "love / will / nature) has east-tone. One that unfolds "
                    "the wisdom or truth-content of how that operates has "
                    "south-tone. One that discriminates, judges, or "
                    "distinguishes has north-tone. One that shows the thing "
                    "in its ultimate concrete form has west-tone."
                ),
                "properties": {
                    "verdict": {
                        "type": "string",
                        "enum": [
                            "clear_rotation",
                            "rough_rotation",
                            "visible_in_some_degrees",
                            "no_clear_pattern",
                            "underdetermined",
                        ],
                    },
                    "celestial_winding": {
                        "type": "string",
                        "description": (
                            "Within the celestial range, describe the tonal "
                            "progression. Does the sequence move from "
                            "will/love → wisdom → rational → ultimates? "
                            "Cite teaching numbers."
                        ),
                    },
                    "spiritual_winding": {
                        "type": "string",
                        "description": (
                            "Within the spiritual range, describe the tonal "
                            "progression."
                        ),
                    },
                    "natural_winding": {
                        "type": "string",
                        "description": (
                            "Within the natural range, describe the tonal "
                            "progression."
                        ),
                    },
                    "counterexamples": {
                        "type": "string",
                        "description": (
                            "Where does the winding break or reverse?"
                        ),
                    },
                },
                "required": [
                    "verdict",
                    "celestial_winding",
                    "spiritual_winding",
                    "natural_winding",
                    "counterexamples",
                ],
            },
            "fivefold_constitution": {
                "type": "object",
                "description": (
                    "The pervasive five-fold structure throughout the corpus "
                    "is itself evidence for the Grand Man architecture: the "
                    "body has five-fold constitution at every point, and so "
                    "does this book. Confirm that pervasiveness and note how "
                    "it relates to the descent."
                ),
                "properties": {
                    "verdict": {
                        "type": "string",
                        "enum": [
                            "pervasive_as_expected",
                            "present_but_patchy",
                            "weak",
                        ],
                    },
                    "strongest_examples": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Up to 10 teaching numbers with their five-fold "
                            "named structure."
                        ),
                    },
                    "notes": {"type": "string"},
                },
                "required": ["verdict", "strongest_examples", "notes"],
            },
            "natural_seams": {
                "type": "array",
                "description": (
                    "Where does the corpus show real structural seams — "
                    "places where one section ends and another begins, "
                    "visible in the shift of register or tone? List the "
                    "teaching number AFTER which the seam falls, and "
                    "describe what shifts."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "after_teaching": {"type": "integer"},
                        "what_shifts": {"type": "string"},
                    },
                    "required": ["after_teaching", "what_shifts"],
                },
            },
            "structural_ribs": {
                "type": "array",
                "description": (
                    "Cross-corpus patterns — themes that recur at multiple "
                    "positions and link the corpus together across distance."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "teaching_numbers": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                        "evidence": {"type": "string"},
                        "strength": {
                            "type": "string",
                            "enum": ["strong", "moderate", "weak"],
                        },
                    },
                    "required": [
                        "name", "teaching_numbers", "evidence", "strength",
                    ],
                },
            },
            "conjectures_to_avoid": {
                "type": "array",
                "description": (
                    "Interpretive claims that could be confused with "
                    "architectural predictions but are not. Flag each."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "claim": {"type": "string"},
                        "why_conjecture": {"type": "string"},
                    },
                    "required": ["claim", "why_conjecture"],
                },
            },
            "open_questions": {
                "type": "array",
                "description": (
                    "Research questions that remain open."
                ),
                "items": {"type": "string"},
            },
            "overall_verdict": {
                "type": "string",
                "enum": [
                    "descent_clearly_present",
                    "descent_roughly_present",
                    "descent_partially_present",
                    "descent_weak",
                    "descent_not_observed",
                    "underdetermined",
                ],
                "description": (
                    "Does the reading order of the 104 teachings track the "
                    "descent of influx through the Grand Man?"
                ),
            },
        },
        "required": [
            "scope",
            "summary",
            "degree_descent",
            "directional_winding",
            "fivefold_constitution",
            "natural_seams",
            "structural_ribs",
            "conjectures_to_avoid",
            "open_questions",
            "overall_verdict",
        ],
    },
}


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert in the doctrine of correspondences as written by \
Emanuel Swedenborg, with deep specialization in ancient cosmological \
vocabulary: Zoroastrian, Manichaean, Persian-Iranian, Syriac, and Coptic.

You are doing research on a Coptic teaching corpus of 104 whole-teaching \
arcs assembled from the oldest substrate of the Kephalaia. Your question \
is about SEQUENTIAL ORDER:

  Do the teachings, read in their current order, follow the descent \
  pattern that influx traces through the Grand Man?

## THE HYPOTHESIS

The Grand Man is a body. It has:

- Three discrete DEGREES from top to bottom: celestial (head / inmost), \
    spiritual (thorax / arms / heart), natural (lower body / feet).
- At each degree, influx passes from inward to outward in four \
    DIRECTIONS: love/will (east) → wisdom/understanding (south) → \
    rational discernment (north) → ultimates (west).
- This gives 3 × 4 = 12 sequential positions.
- Five-fold constitution operates radially at every point — like how \
    every part of the body is structured in fives. The corpus is in fact \
    saturated with five-fold structures. This is not a coincidence — it \
    is a structural property of the book, evidence that the whole is \
    organized as the Grand Man. It is already established.

## WHAT YOU ARE LOOKING FOR

You are looking at whether the READING ORDER of the 104 teachings tracks \
this descent:

1. Do the early teachings operate at the CELESTIAL register — treating \
    the Father's inmost nature, the source, the ruling love, the \
    primordial foundations?

2. Do the middle teachings operate at the SPIRITUAL register — treating \
    how that source mediates, how wisdom unfolds it, how cosmic agents \
    carry it into operation?

3. Do the late teachings operate at the NATURAL register — treating the \
    visible cosmos, the body, the senses, concrete effects in ultimates?

4. Within each degree, do the teachings wind from love-tone (what the \
    thing IS at source) through wisdom-tone (how it unfolds in truth) \
    through rational-tone (how it is discriminated and judged) to \
    ultimates-tone (how it appears in concrete form)?

## WHAT YOU ARE NOT LOOKING FOR

- Whether the NUMBER twelve appears in the text. Irrelevant.
- Whether the corpus NAMES east, south, north, west. Irrelevant.
- Whether the corpus explicitly uses the phrase 'three degrees.' \
    Irrelevant.
- Whether the five-fold structures need proving. They are already \
    confirmed throughout the corpus and are themselves evidence for the \
    Grand Man. Acknowledge them as established and focus on the descent.
- Whether parts grow in size. Not a prediction of the architecture.
- Whether any specific count of "parts" is named. Irrelevant.

## HOW TO ASSESS REGISTER

A teaching's register is determined by what it TREATS, not what it \
NAMES:

- **Celestial register**: The teaching treats the Father's nature, the \
    primordial substances, what things ARE at their source before any \
    unfolding. The tone is foundational, inmost, originary.

- **Spiritual register**: The teaching treats how the source unfolds \
    through mediating agents, cosmic operations, wars, salvations, \
    judgments — the dynamic middle where cause becomes process.

- **Natural register**: The teaching treats the visible result — the \
    body, the senses, the zodiac, the material cosmos, the soul in its \
    concrete operations.

## HOW TO ASSESS DIRECTIONAL TONE

Within each degree, directional tone is:

- **East (love/will)**: What the thing IS. Its nature, its ruling love, \
    its essential character. The will that drives it.

- **South (wisdom)**: How the thing UNFOLDS in truth. Its wisdom-content, \
    its articulation, its teaching about itself.

- **North (rational)**: How the thing is DISTINGUISHED, judged, separated \
    from its opposite. Discrimination, boundaries, watchfulness.

- **West (ultimates)**: The thing in its CONCRETE FINAL FORM. Effect, \
    body, the last expression where everything prior rests.

## METHOD

Read each teaching's arc and reading in order. For each, assess:
- What register does it operate at?
- What directional tone does it carry?

Then report: does the sequence track the predicted descent?

Be honest. The descent may be rough, may have exceptions, may be clearer \
in some degrees than others. Report what you see. Do not force the pattern. \
Do not deny the pattern. Just read and report.

When complete, call commit_structure_research exactly once."""


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


def shorten(text: str | None, limit: int = 600) -> str:
    if not text:
        return ""
    normalized = re.sub(r"\s+", " ", str(text)).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def format_teaching_card(
    teaching_num: int,
    teaching: dict,
    reading: dict,
) -> str:
    """Compact research-grade view of one teaching."""
    lines = [
        f"=== T{teaching_num}: {teaching.get('title', '')} ===",
        f"Sections: §{teaching.get('start_section')}"
        f"-§{teaching.get('end_section')} "
        f"({teaching.get('total_sections', 0)} sections, "
        f"{teaching.get('total_lacunae', 0)} lacunae, "
        f"boundary={teaching.get('confidence', '?')})",
    ]
    if reading.get("title"):
        lines.append(f"Reading title: {reading.get('title')}")
    if reading.get("arc"):
        lines.append(f"Arc: {shorten(reading.get('arc'), 320)}")
    if reading.get("reading"):
        lines.append(shorten(reading.get("reading"), 1500))
    images = reading.get("major_images") or []
    if images:
        lines.append("Major images:")
        for image in images[:8]:
            lines.append(
                f"- {image.get('image', '?')}: "
                f"{shorten(image.get('meaning'), 220)}"
            )
    return "\n".join(lines)


def format_corpus(
    teachings: dict[int, dict],
    readings: dict[int, dict],
) -> str:
    """Format the corpus as research input."""
    lines = ["# Corpus (104 teachings, in original reading order)"]
    for teaching_num in sorted(teachings.keys()):
        lines.append(format_teaching_card(
            teaching_num,
            teachings[teaching_num],
            readings.get(teaching_num, {}),
        ))
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI and main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Stage 7b: Does the reading order track the descent of influx "
            "through the Grand Man?"
        )
    )
    parser.add_argument("--dry-run", "-n", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--output", type=Path,
        help=(
            "Output JSON path. Relative paths resolve under the project dir."
        ),
    )
    parser.add_argument(
        "--effort", default="max",
        choices=["low", "medium", "high", "xhigh", "max"],
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("Stage 7b: Architectural Research")
    print("  Does the reading order track the descent of influx?")

    teachings = load_all_teachings(TEACHINGS_DIR)
    readings = load_all_teachings(READINGS_DIR)
    if not teachings:
        print(f"\nERROR: No teachings in {TEACHINGS_DIR}")
        sys.exit(1)

    output_file = args.output or DEFAULT_OUTPUT_FILE
    if not output_file.is_absolute():
        output_file = PROJECT_DIR / output_file

    print(f"  Teachings:    {len(teachings)} loaded")
    print(f"  Readings:     {len(readings)} loaded")
    print(f"  Output:       {output_file}")

    if output_file.exists() and not args.overwrite:
        print("\n  Research already exists (use --overwrite)")
        return

    corpus_text = format_corpus(teachings, readings)
    print(f"  Corpus:       {len(corpus_text):,} chars")

    if args.dry_run:
        print("\n[DRY RUN] No API calls made.")
        return

    client, deployment = create_client()
    print(f"\n  Deployment: {deployment}")
    print(f"  Effort: {args.effort}")
    print("\n  Sending corpus for research...", flush=True)

    user_msg = (
        "## Research Task\n\n"
        "Read the 104 teachings in order. For each teaching, assess what "
        "register it operates at (celestial / spiritual / natural) and what "
        "directional tone it carries (love / wisdom / rational / ultimates). "
        "Then report whether the reading order tracks the predicted descent "
        "of influx through the Grand Man: celestial-east → celestial-south "
        "→ celestial-north → celestial-west → spiritual-east → ... → "
        "natural-west.\n\n"
        "The fives being everywhere is already confirmed and is itself "
        "evidence for the Grand Man (which has five-fold constitution at "
        "every point). Now investigate the sequential descent.\n\n"
        f"{corpus_text}\n\n"
        "Call commit_structure_research with your findings."
    )

    result = stream_tool_call(
        client,
        deployment,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
        tools=[RESEARCH_TOOL],
        tool_name="commit_structure_research",
        effort=args.effort,
        page_label="structure_research",
        debug=args.debug,
    )

    if result is None:
        print("\nFAILED: No research output.")
        sys.exit(1)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    n_seams = len(result.get("natural_seams", []))
    n_ribs = len(result.get("structural_ribs", []))
    n_conj = len(result.get("conjectures_to_avoid", []))
    verdict = result.get("overall_verdict", "?")
    print(
        f"\nResearch complete: verdict={verdict}, "
        f"{n_seams} seams, {n_ribs} ribs, "
        f"{n_conj} conjectures flagged"
    )
    print(f"  Output: {output_file}")


if __name__ == "__main__":
    main()
