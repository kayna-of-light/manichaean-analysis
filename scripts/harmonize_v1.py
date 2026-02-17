#!/usr/bin/env python3
"""
Pass 3: Structural Harmonization of the Kephalaia Teaching Core.

Reads the restored chapter text (Pass 2 output) as a WHOLE and evaluates
it against the spiritual system — discrete degrees, influx, the Grand
Man, correspondential numerology. Identifies and annotates structural
expansions (e.g. pentadic taxonomies that should be triadic), naming
overlays, and seam artifacts.

This pass does NOT operate paragraph-by-paragraph. It receives the
entire chapter at once, reads it as a spiritual document, and returns
a harmonized version with a detailed change log.

Input:  output/core/chapters/ch_NNN.json           (extraction)
        output/correspondential/chapters/ch_NNN.json (restoration fills)
Output: output/harmonized/chapters/ch_NNN.json       (harmonized)
        output/harmonized/harmonized_kephalaia.md     (assembled)

Usage:
    python scripts/harmonize.py                     # All chapters
    python scripts/harmonize.py --chapter 7         # Single chapter
    python scripts/harmonize.py --range 7-41        # Range
    python scripts/harmonize.py --dry-run           # Preview
    python scripts/harmonize.py --overwrite         # Redo existing
    python scripts/harmonize.py --assemble          # Assemble only
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

from openai import OpenAI, RateLimitError, APIStatusError
from dotenv import dotenv_values
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SECRETS_PATH = PROJECT_ROOT / "secrets" / "azure_openai.env"
CORE_CHAPTERS_DIR = PROJECT_ROOT / "output" / "core" / "chapters"
CORR_CHAPTERS_DIR = PROJECT_ROOT / "output" / "correspondential" / "chapters"
OUTPUT_DIR = PROJECT_ROOT / "output" / "harmonized"
CHAPTERS_OUT_DIR = OUTPUT_DIR / "chapters"
ASSEMBLED_FILE = OUTPUT_DIR / "harmonized_kephalaia.md"

# ---------------------------------------------------------------------------
# Azure OpenAI client
# ---------------------------------------------------------------------------

def load_secrets() -> dict:
    if not SECRETS_PATH.exists():
        print(f"ERROR: Secrets file not found: {SECRETS_PATH}")
        sys.exit(1)
    return dotenv_values(SECRETS_PATH)


def create_client() -> OpenAI:
    secrets = load_secrets()
    return OpenAI(
        api_key=secrets["OPENAI_API_KEY"],
        base_url=secrets["OPENAI_ENDPOINT"],
    )


def get_deployment() -> str:
    return load_secrets()["OPENAI_DEPLOYMENT"]


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class StructuralFinding(BaseModel):
    """A single finding from structural analysis."""
    finding_type: str = Field(
        description=(
            "Type: 'pentadic_expansion' | 'naming_overlay' | "
            "'seam_artifact' | 'degree_violation' | 'coherence_issue' | "
            "'confirmed_structure' | 'correspondential_observation'"
        )
    )
    location: str = Field(
        description="Paragraph number(s) or passage reference."
    )
    description: str = Field(
        description="What was found. For observations: what the text shows spiritually. For problems: why it fails the architecture test."
    )
    spiritual_reasoning: str = Field(
        description=(
            "The correspondential reasoning — which principles are operating? "
            "Correspondence, influx, opposite sense, ruling love, degrees, "
            "Grand Man, regeneration, accommodation? Be specific."
        )
    )
    action: str = Field(
        description=(
            "What to do: 'excise' (remove expanded material from text), "
            "'none' (observation only, no text change). "
            "Use 'excise' ONLY for high-confidence pentadic expansions."
        )
    )
    original_text: str = Field(
        description="The original passage being evaluated (quote it)."
    )
    harmonized_text: str = Field(
        description=(
            "For 'excise': the cleaned text with expansion removed. "
            "For 'none': same as original_text. "
            "NEVER include annotations, glosses, or markers here."
        )
    )


class HarmonizedParagraph(BaseModel):
    """A single paragraph after harmonization."""
    paragraph_number: int = Field(description="The paragraph number.")
    text: str = Field(
        description=(
            "The paragraph text. MUST be clean text only — no annotations, "
            "no markers, no glosses, no editorial insertions. "
            "If unchanged, this is the exact original text."
        )
    )
    changed: bool = Field(
        description=(
            "Whether this paragraph was modified. Most paragraphs "
            "should be unchanged (false). Only true when text was "
            "actually edited to remove an identified expansion."
        )
    )


class HarmonizedChapter(BaseModel):
    """Complete harmonization result for one chapter."""

    spiritual_assessment: str = Field(
        description=(
            "A correspondential reading of the chapter's spiritual architecture. "
            "What discrete degrees are present? How does influx flow? "
            "What is the chapter ABOUT at the spiritual level? "
            "Does the overall structure map onto the Grand Man?"
        )
    )

    findings: list[StructuralFinding] = Field(
        description="All structural findings, both issues and confirmations."
    )

    harmonized_paragraphs: list[HarmonizedParagraph] = Field(
        description="The full list of harmonized paragraphs."
    )

    summary: str = Field(
        description=(
            "Summary: how many findings, how many changes, what was the "
            "dominant issue in this chapter, overall confidence."
        )
    )


# ---------------------------------------------------------------------------
# System prompt: THE SPIRITUAL PRIMER
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are performing STRUCTURAL HARMONIZATION of the oldest teaching \
substrate of the Coptic Kephalaia. You have received the restored \
chapter text — already extracted from its editorial frame (Pass 1) and \
with lacunae filled using correspondential constraints (Pass 2).

Your task in this third pass is twofold:
1. RICH SPIRITUAL READING — read the chapter through the FULL \
   correspondential system and assess what it is about spiritually.
2. SURGICAL STRUCTURAL CORRECTION — identify and correct ONLY \
   genuine pentadic expansions over demonstrable triadic substrates.

The reading should be DYNAMIC — recognizing the full range of \
correspondential principles at work. The corrections should be \
PRECISE — high bar, clear evidence, minimal intervention.

DEFAULT: LEAVE TEXT UNCHANGED. You are working with a recovered \
ancient teaching. Every word matters. Only modify text when you \
have HIGH-CONFIDENCE evidence of editorial expansion.

# THE CORRESPONDENTIAL SYSTEM

The science of correspondences describes how spiritual reality \
expresses itself through natural forms. Multiple principles operate \
simultaneously. Read each chapter for ALL of them:

## Correspondence — The Basic Unit
Every natural object corresponds to the spiritual reality it \
expresses, grounded in the object's FUNCTION. The two great \
poles are: fire/heat = love/will (the active principle); \
water = truth/understanding (the intellectual counterpart). \
The FORM of the natural object tells you the STATE — a river \
is truth flowing with intelligence, a sea is general knowledges \
in externals, rain is influx of Divine Truth descending, a \
fountain is interior truth. Light = wisdom (because light \
enables distinction); animals = affections; seeds = interior \
truths; mountains = elevated states; garments = external truths.

## Discrete Degrees — One Architecture Among Several
Reality exists in three discrete degrees — celestial (love/will), \
spiritual (wisdom/truth), natural (effect/use). These are not a \
continuum but complete, self-contained levels. Influx flows \
DOWNWARD: celestial into spiritual into natural. Genuine \
emanation sequences descend through these degrees.

This is ONE structural principle, not the ONLY one. Many chapters \
are NOT primarily about discrete degrees. Natural taxonomies, \
moral instruction, ritual correspondences, cosmological geography \
— each has its own correspondential content.

## Opposite Sense
The same image can express good or evil depending on context: \
fire = divine love OR destructive self-love; water = living truth \
OR falsity (floods = temptation, bitter water = truth adulterated, \
dry wells = doctrine emptied of truth); darkness = obscurity \
before illumination OR active denial. Always determine from \
context which sense applies.

## Ruling Love
The core orientation of a soul or system — toward the Divine \
(love of neighbor) or toward self (love of dominion). This \
polarity is often the REAL subject of a chapter: what ruling \
love drives this cosmological drama?

## The Grand Man (Maximus Homo)
The form of the heavens is the human form. Function determines \
position: an organ IS its spiritual function in ultimates. \
Head = celestial; thorax = spiritual; abdomen = natural. \
Heart = love/will; lungs = wisdom/understanding.

## Regeneration
The spiritual process of transformation: old state broken, \
wilderness/combat, reformation through truth, then regeneration \
through good. Many chapters describe this PROCESS, not a static \
architecture.

## The Proprium
The sense of self as separate. Not evil in itself — the vessel \
that must be formed. But when it claims what flows through it \
as its own possession, it becomes the obstacle. Darkness-entities \
in the Kephalaia often personify proprium dynamics.

## Accommodation
Truth delivered at the level the receiver can accept. The same \
spiritual reality appears differently to different states. This \
is why the Kephalaia has multiple descriptions of the "same" \
cosmic event — they may be the same event at different degrees.

## Numbers as Correspondences
Numbers are states of being, not counting:
- TWO = fundamental polarity (will/understanding, good/truth)
- THREE = discrete degrees (celestial/spiritual/natural)
- FOUR = completeness in ultimates (natural plane fully extended)
- FIVE = sufficiency ("enough," NOT a system — never describes \
  degrees or how one level produces the next)
- SEVEN = complete process (full cycle from beginning to rest)
- TEN = conjunction with good held inside (strengthens but does \
  not describe a system)
- TWELVE = fullness of organized truths (3 x 4)

# DISTINGUISHING VOICES

This is the PRIMARY diagnostic. Before counting numbers, before \
looking for seams, ask: WHAT KIND OF TEACHING IS THIS?

## Correspondential Voice (Substrate)
Teaches by FUNCTION — what things DO. The spiritual sense arises \
organically from the natural object's nature:
- "The liver is the vessel of fire" — spiritual sense arises \
  from what the liver does (processes, transforms, burns)
- "The blood is the vessel of water" — spiritual sense arises \
  from what blood does (circulates, carries, sustains)
- "Its head is like the first-fruits" — spiritual sense arises \
  from what the head does (governs, initiates, sees)
- Body regions mapped to cosmic regions BY FUNCTION
- Process described BY STATES (interior movements of love/truth)
- Grounded in organic relationship — correspondence IS, not \
  correspondence REPRESENTS

Test: Can you explain WHY this natural thing corresponds to this \
spiritual reality, grounded in its function? If yes, the \
spiritual reading ARISES from the text. If you have to MAP it \
onto a pre-decided framework (e.g., "this must be celestial \
because it comes first"), the reading is IMPOSED.

## Administrative Voice (Mani's Layer)
Teaches by GOVERNANCE — who controls what territory:
- Named figures with jurisdictions ("the Keeper of Splendour \
  is master, his authority extends over...")
- Territorial administration (camps, watches, stations)
- Authority language ("master," "power," "authority lies over")
- Numbered inventories of named entities organized by rank
- Affliction narratives tied to administrative districts

Test: Does the spiritual sense arise from what things DO, or \
from who ADMINISTERS them? If the section could be removed and \
the functional correspondences remain intact, it is overlay.

## How to Apply This
1. Read the section. Does a spiritual reading arise naturally \
   from the objects and their functions? Or do you have to \
   assign a spiritual meaning from outside?
2. Check the vocabulary. Functional language ("corresponds to," \
   "is like," "reflects the pattern of") vs. administrative \
   language ("is master," "authority over," "is appointed")
3. Check coherence. Does the section need the named entities \
   to make its spiritual point? Or could the point be stated \
   without them?
4. ONLY THEN check numbers. Numbers confirm the diagnosis — \
   they do not make it. If a section teaches by function and \
   is organized by sevens, the sevens confirm. If a section \
   teaches by administration and is organized by threes, the \
   threes don't make it substrate.

# IDENTIFYING MANI'S EXPANSIONS

## The Narrative Coherence Test (PRIMARY excision criterion)
Read the spiritual story of the chapter as one continuous \
narrative. Does every passage contribute to that story? Does \
every element participate in the spiritual teaching — does it \
DO something in the narrative, or is it just LISTED there?

When a passage disrupts the spiritual coherence of the \
narrative — when the story reads as one unbroken voice \
WITHOUT it and stumbles WITH it — that is evidence of \
insertion. Not because numbers don't match. Because the \
spiritual story doesn't accommodate it.

Example: A chapter teaches about simultaneity in the Father \
becoming sequence in manifestation. The teaching flows: \
sculpted at a single time… came forth one after one. Then a \
cluster of named figures appears that don't participate in \
the teaching — they are LISTED, not ACTIVE in the narrative. \
Remove them and the story flows better. That coherence gain \
is the evidence.

## Supporting Evidence for Excision
These CONFIRM a narrative-coherence diagnosis; they don't \
replace it:

1. Title/body contradiction: title says "five" but body text \
   says "three emanations" or "three great powers"
2. Bridge connective at a voice-change boundary ("Also, at \
   that time," / "And also") combined with a shift from \
   functional to administrative register
3. Explicit anchor followed by additional items in a \
   different voice

A SINGLE bridge connective ("Also," "Again,") is NOT sufficient. \
These are normal Coptic prose. Only flag them as seams when \
they occur WHERE THE VOICE CHANGES.

## What Excision is NOT
Never excise to reach a target number. Do not trim five to \
three because "three is complete." If a section is entirely \
in the administrative voice, annotate the whole block as \
overlay — do not carve three items out and call those \
substrate. The narrative coherence test asks: does the \
spiritual story flow WITHOUT this passage? Not: does this \
passage bring the count to three?

## What Mani Typically Added at Seams
- Christological identification ("Jesus the Splendour") — \
  naming an eternal function with a historical figure
- Institutional mechanism ("counsel of life," \
  "summons-and-obedience") — the church's call-response
- Recycled entities promoted to fill expanded taxonomies

## Annotation vs. Excision — The Location Test
Whole sections in the administrative voice (e.g. a block of \
named jurisdictions with no functional teaching around it) — \
annotate the whole block as overlay. Do NOT carve substrate \
out of it. The substrate teaching exists ELSEWHERE in the \
chapter; let it speak from those passages.

But when administrative content is INSERTED INTO a functional \
narrative — a cluster of named figures dropped into an \
otherwise correspondential teaching — apply the narrative \
coherence test. If the spiritual story reads as one unbroken \
voice without the insertion and stumbles with it, excise. The \
insertion is an addition TO the narrative, not a separate \
block. Annotating it leaves the spiritual story disrupted.

When numbers confirm the voice diagnosis:
- Sections teaching by function that use 2, 3, 4, 7, 12 — \
  these numbers confirm the correspondential voice
- Sections organized by fives — note this as consistent with \
  Mani's organizational vocabulary (five is his signature \
  numeration: five Shekhinas, five elements, five sons, five \
  limbs, five stages). But the number alone is not the \
  diagnosis. The voice is the diagnosis.

# SWEDENBORG CORRECTIONS

Where Swedenborg's 18th-century science introduced artifacts:
- The Limbus: rejected. Identity is the biography, not material \
  remnant. If text requires matter to anchor spirit, that is \
  Gnostic cosmology, not genuine architecture.
- Biological determinism about Jesus: corrected. The Divine Human \
  achieved alignment through removal of obstruction (distorted proprium), \
  not different origin. Genuine structure shows a PATH.
- Matter as evil: corrected. The physical world is the Fixed Edge \
  — developmental arena, not prison.

# YOUR TASK

## PRODUCE:

### 1. SPIRITUAL ASSESSMENT
Read the chapter as a spiritual document. What is it ABOUT at \
the correspondential level? Which principles are operating? \
What correspondences are active? What does the ruling love \
of the text express? How does influx manifest? Is this about \
degrees, or about regeneration, or about opposite sense, or \
about something else entirely? Be RICH and SPECIFIC.

### 2. FINDINGS
Structural observations — BOTH confirmations and problems. \
For each finding, give the spiritual reasoning: WHY does the \
system predict this reading? Every finding should be grounded \
in the text itself.

### 3. HARMONIZED PARAGRAPHS — CLEAN TEXT ONLY
Return every paragraph. Rules:

**DEFAULT IS UNCHANGED.** Mark changed=false for any paragraph \
you do not modify. Most paragraphs should be unchanged.

**When you DO modify** (pentadic expansion with high-confidence \
evidence): excise the expanded material cleanly. The resulting \
text should read as coherent prose without the expansion. \
Put the excised material in the finding's harmonized_text field.

**NEVER insert into paragraph text:**
- Annotations like ⟨EXPANSION...⟩ or ⟨TEXTUAL NOTE...⟩
- Correspondence glosses like ⟨= explanation⟩
- Parenthetical interpretations like "(the ordering of forms)"
- Editorial markers of any kind

The paragraph text must be CLEAN — exactly what the ancient \
teacher would have said. All analysis goes in findings.

**NEVER remove connectives ("Also," "Again," "And") from \
paragraphs UNLESS** they are at an identified expansion boundary \
where you are excising expanded material. Regular prose \
connectives are part of the text.

### 4. SUMMARY
How many findings, how many changes, dominant observation, \
overall confidence. If no changes were needed — say so clearly. \
A chapter with 0 changes is a VALID result.

## CRITICAL RULES:

- The text is a RECOVERED ARTIFACT. Treat it with respect. \
  Do not smooth, rephrase, annotate, or "improve" it.
- Not every five is an expansion. Not every chapter is about \
  discrete degrees. Read for what IS there.
- A spiritual assessment with 0 text changes is perfectly valid. \
  Rich reading does not require text modification.
- The spiritual reading from Pass 2 (if available) provides \
  additional context. Use it.
"""


# ---------------------------------------------------------------------------
# Chapter assembly logic
# ---------------------------------------------------------------------------

def load_core_chapters() -> list[dict]:
    """Load all core extraction JSON files."""
    chapters = []
    for path in sorted(CORE_CHAPTERS_DIR.glob("ch_*.json")):
        with open(path, encoding="utf-8") as f:
            chapters.append(json.load(f))
    return chapters


def load_restoration(ch_num: int) -> dict | None:
    """Load the correspondential restoration for a chapter."""
    path = CORR_CHAPTERS_DIR / f"ch_{ch_num:03d}.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def apply_fills_to_paragraph(text: str, fills: list[dict]) -> str:
    """Apply restoration fills to a paragraph's bracket spans.

    Processes RIGHT-TO-LEFT to preserve character offsets.
    """
    bracket_re = re.compile(r"\[([^\]]*)\]")
    spans = list(bracket_re.finditer(text))
    fills_by_idx = {f["index"]: f for f in fills}

    # Right-to-left
    for i in range(len(spans) - 1, -1, -1):
        idx = i + 1  # 1-based
        fill_data = fills_by_idx.get(idx)
        if fill_data and fill_data.get("fill", "...").strip() != "...":
            fill_text = fill_data["fill"]
            start, end = spans[i].start(), spans[i].end()
            text = text[:start] + f"[{fill_text}]" + text[end:]

    return text


def build_restored_text(core_ch: dict, rest_ch: dict | None) -> list[dict]:
    """Build the restored paragraph list for a chapter.

    Returns list of {paragraph_number, text} dicts.
    """
    fills_by_para: dict[int, list[dict]] = {}
    if rest_ch:
        for fill in rest_ch.get("fills", []):
            para = fill["paragraph"]
            if para not in fills_by_para:
                fills_by_para[para] = []
            fills_by_para[para].append(fill)

    paragraphs = []
    for para in core_ch.get("paragraphs", []):
        pnum = para["paragraph_number"]
        core_text = para.get("core_text")
        if not core_text:
            continue

        para_fills = fills_by_para.get(pnum)
        if para_fills:
            restored = apply_fills_to_paragraph(core_text, para_fills)
        else:
            restored = core_text

        paragraphs.append({
            "paragraph_number": pnum,
            "text": restored,
        })

    return paragraphs


def get_spiritual_reading(ch_num: int) -> str | None:
    """Get the spiritual assessment from the restoration pass.

    The Pass 2 output stores this as 'assessment' (the model's
    correspondential evaluation). Also checks 'spiritual_reading'
    for backward compatibility.
    """
    rest = load_restoration(ch_num)
    if rest:
        # Try both field names — 'assessment' is the actual key,
        # 'spiritual_reading' was intended but not always saved.
        return rest.get("spiritual_reading") or rest.get("assessment")
    return None


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def harmonize_chapter(
    client: OpenAI,
    deployment: str,
    restored_paragraphs: list[dict],
    ch_num: int,
    title: str,
    spiritual_reading: str | None = None,
) -> HarmonizedChapter | None:
    """Send the full chapter to the model for structural harmonization."""

    # Build the chapter text
    lines = [f"# Chapter {ch_num}: {title}", ""]
    for p in restored_paragraphs:
        lines.append(f"¶{p['paragraph_number']}: {p['text']}")
        lines.append("")
    chapter_text = "\n".join(lines)

    # Build user message
    parts = []
    parts.append("## RESTORED CHAPTER TEXT\n")
    parts.append(chapter_text)

    if spiritual_reading:
        parts.append("\n## SPIRITUAL READING (from Pass 2)\n")
        parts.append(spiritual_reading)

    user_msg = "\n".join(parts)

    # Call with retry
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            response = client.responses.parse(
                model=deployment,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                text_format=HarmonizedChapter,
            )
            result = response.output_parsed
            if result is None:
                raise ValueError("No structured output (parsed is None)")
            return result
        except RateLimitError:
            wait = 30 * attempt
            print(f"rate-limited, waiting {wait}s...", end=" ", flush=True)
            time.sleep(wait)
        except APIStatusError as e:
            if e.status_code == 429:
                wait = 30 * attempt
                print(f"429, waiting {wait}s...", end=" ", flush=True)
                time.sleep(wait)
            else:
                print(f"API error: {e}")
                return None
        except Exception as e:
            print(f"Error: {e}")
            if attempt < max_retries:
                time.sleep(10)
            else:
                return None

    return None


# ---------------------------------------------------------------------------
# Save results
# ---------------------------------------------------------------------------

def save_result(
    ch_num: int,
    title: str,
    result: HarmonizedChapter,
) -> None:
    """Save harmonization result to JSON."""
    CHAPTERS_OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = CHAPTERS_OUT_DIR / f"ch_{ch_num:03d}.json"

    data = {
        "chapter_number": ch_num,
        "chapter_title": title,
        "spiritual_assessment": result.spiritual_assessment,
        "findings": [f.model_dump() for f in result.findings],
        "harmonized_paragraphs": [p.model_dump() for p in result.harmonized_paragraphs],
        "summary": result.summary,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_done(ch_num: int) -> bool:
    return (CHAPTERS_OUT_DIR / f"ch_{ch_num:03d}.json").exists()


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def assemble_harmonized(core_chapters: dict[int, dict]) -> str:
    """Assemble all harmonized chapters into a continuous document."""
    harmonized_by_ch: dict[int, dict] = {}
    for path in sorted(CHAPTERS_OUT_DIR.glob("ch_*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            harmonized_by_ch[data["chapter_number"]] = data

    if not harmonized_by_ch:
        print("ERROR: No harmonization files found.")
        return ""

    lines: list[str] = []
    lines.append("# The Kephalaia Teaching Core — Harmonized Text")
    lines.append("")
    lines.append("*The oldest teaching layer of the Kephalaia, restored and*")
    lines.append("*structurally harmonized against the science of correspondences.*")
    lines.append("*Mani's pentadic expansions are marked with ⟨EXPANSION⟩.*")
    lines.append("*Naming overlays are marked with ⟨= name⟩.*")
    lines.append("")
    lines.append("---")
    lines.append("")

    total_findings = 0
    total_expansions = 0
    total_changes = 0

    for ch_num in sorted(
        set(list(core_chapters.keys()) + list(harmonized_by_ch.keys()))
    ):
        harm_ch = harmonized_by_ch.get(ch_num)
        core_ch = core_chapters.get(ch_num)

        if not core_ch:
            continue

        title = core_ch.get("chapter_title", f"Chapter {ch_num}")
        lines.append(f"## Chapter {ch_num}: {title}")
        lines.append("")

        if harm_ch:
            # Use harmonized paragraphs
            for p in harm_ch.get("harmonized_paragraphs", []):
                pnum = p.get("paragraph_number", "?")
                text = p.get("text", "")
                changed = p.get("changed", False)
                marker = " [*]" if changed else ""
                lines.append(f"**¶{pnum}**{marker} {text}")
                lines.append("")

            # Findings summary
            findings = harm_ch.get("findings", [])
            expansions = [
                f for f in findings
                if f.get("finding_type") == "pentadic_expansion"
            ]
            total_findings += len(findings)
            total_expansions += len(expansions)
            total_changes += sum(
                1 for p in harm_ch.get("harmonized_paragraphs", [])
                if p.get("changed")
            )

            if findings:
                lines.append("> **Structural findings:**")
                for f in findings:
                    ft = f.get("finding_type", "")
                    loc = f.get("location", "")
                    desc = f.get("description", "")[:200]
                    lines.append(f"> - [{ft}] ¶{loc}: {desc}")
                lines.append("")

            # Spiritual assessment
            assessment = harm_ch.get("spiritual_assessment", "")
            if assessment:
                lines.append(f"**Spiritual Assessment:** {assessment}")
                lines.append("")

            # Summary
            summary = harm_ch.get("summary", "")
            if summary:
                lines.append(f"**Summary:** {summary}")
                lines.append("")
        else:
            # No harmonization — use core text directly
            for para in core_ch.get("paragraphs", []):
                pnum = para["paragraph_number"]
                text = para.get("core_text")
                if text:
                    lines.append(f"**¶{pnum}** {text}")
                    lines.append("")

        lines.append("---")
        lines.append("")

    # Prepend statistics
    stats_block = [
        f"**Total findings**: {total_findings}",
        f"**Pentadic expansions identified**: {total_expansions}",
        f"**Paragraphs modified**: {total_changes}",
        "",
    ]
    insert_pos = lines.index("---") + 2
    for i, s in enumerate(stats_block):
        lines.insert(insert_pos + i, s)

    return "\n".join(lines)


def save_assembly(text: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(ASSEMBLED_FILE, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  Saved harmonized text to {ASSEMBLED_FILE}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pass 3: Structural harmonization of the Kephalaia "
        "teaching core against the science of correspondences."
    )
    parser.add_argument(
        "--chapter", "-c", type=int, default=None,
        help="Process a single chapter",
    )
    parser.add_argument(
        "--range", "-r", type=str, default=None,
        help="Process a range of chapters (e.g., '7-41')",
    )
    parser.add_argument(
        "--limit", "-l", type=int, default=None,
        help="Process only first N chapters",
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true",
        help="Preview without API calls",
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Reprocess existing harmonizations",
    )
    parser.add_argument(
        "--assemble", "-a", action="store_true",
        help="Skip harmonization, assemble existing results only",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    # Load core chapters
    all_chapters = load_core_chapters()
    if not all_chapters:
        print("ERROR: No core chapters found in", CORE_CHAPTERS_DIR)
        sys.exit(1)

    core_by_num = {ch["chapter_number"]: ch for ch in all_chapters}
    print(f"Found {len(all_chapters)} core chapters")

    # Assembly-only mode
    if args.assemble:
        print("Assembling harmonized text from existing results...")
        text = assemble_harmonized(core_by_num)
        if text:
            save_assembly(text)
        return

    # Determine which to process
    if args.chapter is not None:
        chapters = [
            ch for ch in all_chapters if ch["chapter_number"] == args.chapter
        ]
        if not chapters:
            print(f"ERROR: Chapter {args.chapter} not found")
            sys.exit(1)
    elif args.range:
        m = re.match(r"(\d+)-(\d+)", args.range)
        if not m:
            print("ERROR: Invalid range. Use '7-41'")
            sys.exit(1)
        start, end = int(m.group(1)), int(m.group(2))
        chapters = [
            ch for ch in all_chapters
            if start <= ch["chapter_number"] <= end
        ]
    else:
        chapters = all_chapters

    if args.limit:
        chapters = chapters[:args.limit]

    # Skip already processed
    if not args.overwrite:
        to_process = [
            ch for ch in chapters if not is_done(ch["chapter_number"])
        ]
        skipped = len(chapters) - len(to_process)
        if skipped > 0:
            print(f"  Skipping {skipped} already-done (use --overwrite)")
        chapters = to_process

    if not chapters:
        print("All chapters already processed.")
        text = assemble_harmonized(core_by_num)
        if text:
            save_assembly(text)
        return

    # Preview
    print(f"\nProcessing {len(chapters)} chapters:")
    for ch in chapters:
        num = ch["chapter_number"]
        title = ch.get("chapter_title", "")[:60]
        core_paras = [
            p for p in ch.get("paragraphs", [])
            if p.get("core_text")
        ]
        has_rest = load_restoration(num) is not None
        rest_mark = "Y" if has_rest else "-"
        print(
            f"  Ch.{num:3d}  ({len(core_paras):3d} core ¶s, "
            f"restoration: {rest_mark})  {title}"
        )

    if args.dry_run:
        print("\n[DRY RUN] No API calls made.")
        return

    # Create client
    client = create_client()
    deployment = get_deployment()
    print(f"\nUsing deployment: {deployment}")
    print()

    # Process
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CHAPTERS_OUT_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    errors = []
    for i, ch in enumerate(chapters, 1):
        ch_num = ch["chapter_number"]
        title = ch.get("chapter_title", f"Chapter {ch_num}")[:50]

        # Build restored text
        rest_ch = load_restoration(ch_num)
        restored_paras = build_restored_text(ch, rest_ch)

        if not restored_paras:
            print(f"[{i}/{len(chapters)}] Ch.{ch_num} — no core text, skip")
            continue

        # Get spiritual reading from Pass 2
        spiritual_reading = None
        if rest_ch:
            spiritual_reading = rest_ch.get("spiritual_reading")

        print(
            f"[{i}/{len(chapters)}] Ch.{ch_num} "
            f"({len(restored_paras)} ¶s) {title}...",
            end=" ", flush=True,
        )

        print("harmonizing...", end=" ", flush=True)
        result = harmonize_chapter(
            client, deployment, restored_paras, ch_num, title,
            spiritual_reading=spiritual_reading,
        )

        if result is None:
            print("FAILED")
            errors.append(ch_num)
            continue

        n_findings = len(result.findings)
        n_expansions = sum(
            1 for f in result.findings
            if f.finding_type == "pentadic_expansion"
        )
        n_changed = sum(
            1 for p in result.harmonized_paragraphs
            if p.changed
        )

        save_result(ch_num, title, result)
        print(
            f"OK — {n_findings} findings, "
            f"{n_expansions} expansions, "
            f"{n_changed} ¶s changed"
        )

        results.append(ch_num)

        if i < len(chapters):
            time.sleep(0.5)

    # Summary
    print(f"\n{'=' * 60}")
    print("HARMONIZATION COMPLETE")
    print(f"  Processed: {len(results)}")
    print(f"  Errors: {len(errors)}")
    if errors:
        print(f"  Failed: {errors}")

    # Assemble
    print("\nAssembling harmonized document...")
    text = assemble_harmonized(core_by_num)
    if text:
        save_assembly(text)

    print("Done.")


if __name__ == "__main__":
    main()
