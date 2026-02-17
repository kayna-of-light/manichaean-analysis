#!/usr/bin/env python3
"""
Pass 3: Three-stage structural harmonization of the Kephalaia Teaching Core.

Three internal stages run as ONE pipeline per chapter:

  Stage 3a — SPIRITUAL READING
    Paragraph-by-paragraph correspondential reading. Exact and honest.
    Reports what the text teaches spiritually and where it breaks.

  Stage 3b — TEXTUAL CRITICISM
    Receives the text and the reading. Diagnoses WHY the reading broke.
    Returns findings with specific recommendations (excise / annotate / none).

  Stage 3c — HARMONIZATION
    Receives text + reading + criticism. Executes the recommendations.
    Returns clean, edited paragraphs.

All three stages produce one combined JSON per chapter.
Use --stop-after for debugging individual stages.

Input:  output/core/chapters/ch_NNN.json           (extraction)
        output/correspondential/chapters/ch_NNN.json (restoration fills)
Output: output/harmonized/chapters/ch_NNN.json       (harmonized)
        output/harmonized/harmonized_kephalaia.md     (assembled)

Usage:
    python scripts/harmonize.py                          # All chapters
    python scripts/harmonize.py --chapter 24             # Single chapter
    python scripts/harmonize.py --chapter 24 --stop-after reading
    python scripts/harmonize.py --chapter 24 --stop-after criticism
    python scripts/harmonize.py --range 7-41             # Range
    python scripts/harmonize.py --overwrite              # Redo existing
    python scripts/harmonize.py --assemble               # Assemble only
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

# ===================================================================
# PATHS
# ===================================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SECRETS_PATH = PROJECT_ROOT / "secrets" / "azure_openai.env"
CORE_CHAPTERS_DIR = PROJECT_ROOT / "output" / "core" / "chapters"
CORR_CHAPTERS_DIR = PROJECT_ROOT / "output" / "correspondential" / "chapters"
OUTPUT_DIR = PROJECT_ROOT / "output" / "harmonized"
CHAPTERS_OUT_DIR = OUTPUT_DIR / "chapters"
ASSEMBLED_FILE = OUTPUT_DIR / "harmonized_kephalaia.md"

# ===================================================================
# AZURE OPENAI CLIENT
# ===================================================================


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


# ===================================================================
# PYDANTIC MODELS — Stage 3a: Spiritual Reading
# ===================================================================


class ParagraphReading(BaseModel):
    """Reading of a single paragraph."""
    paragraph_number: int = Field(
        description="The paragraph number from the input text."
    )
    spiritual_content: str = Field(
        description=(
            "TRANSLATE this paragraph through to its spiritual sense. "
            "Do NOT describe the natural text and label correspondences. "
            "Do NOT write 'storehouses (= interiors)' — that is glossing. "
            "Instead, REPLACE every natural object with what it IS at "
            "the spiritual level and tell what happens in that register. "
            "Example: 'He established her in storehouses in quiet and "
            "silence' becomes 'Love holds wisdom within itself in a "
            "state of peace before it takes form.' The natural image "
            "is gone; what remains is what it EXPRESSES. Do this for "
            "EVERY object in the paragraph — nothing passes through "
            "untranslated. If a paragraph does NOT yield coherent "
            "spiritual sense when translated, say so honestly — the "
            "incoherence itself is evidence."
        )
    )
    narrative_flow: str = Field(
        description=(
            "How this paragraph relates to the chapter's spiritual "
            "story. Does it CONTINUE the thread, DEVELOP it further, "
            "SHIFT to a new aspect, or BREAK the flow? If it breaks, "
            "say what breaks and how."
        )
    )
    notes: str = Field(
        description=(
            "Anything that doesn't fit, forces interpretation, seems "
            "inserted, or breaks the voice. Named figures that appear "
            "but don't participate in the teaching. Vocabulary shifts. "
            "Awkward transitions. Empty string if clean."
        )
    )


class SpiritualReadingResult(BaseModel):
    """Complete spiritual reading for one chapter."""
    chapter_narrative: str = Field(
        description=(
            "The complete spiritual story of this chapter, told "
            "ENTIRELY in the spiritual register. No natural objects "
            "remain — every image has been translated through to what "
            "it expresses. Write it as if someone who could only "
            "perceive the spiritual sense told you what this chapter "
            "says. If the story becomes incoherent at any point — "
            "if the translation produces nonsense or contradiction — "
            "say so at that point in the narrative and continue. The "
            "incoherence is evidence, not failure."
        )
    )
    paragraph_readings: list[ParagraphReading] = Field(
        description="One reading per paragraph. Read EVERY paragraph."
    )
    overall_coherence: str = Field(
        description=(
            "Assessment of how well the chapter holds together as a "
            "single spiritual teaching. Where is it strong? Where does "
            "it stumble? Does it read as one voice or multiple voices?"
        )
    )


# ===================================================================
# PYDANTIC MODELS — Stage 3b: Textual Criticism
# ===================================================================


class CriticalFinding(BaseModel):
    """A single diagnostic finding from textual criticism."""
    location: str = Field(
        description="Paragraph number(s): '¶14' or '¶5-16'."
    )
    diagnosis: str = Field(
        description=(
            "What is wrong and why. Be precise: what disrupts the "
            "narrative, what voice is speaking, what doesn't belong."
        )
    )
    voice: str = Field(
        description=(
            "'correspondential' — teaches by function; "
            "'administrative' — teaches by governance/jurisdiction; "
            "'mixed' — both voices present; "
            "'damaged' — text too fragmentary to diagnose."
        )
    )
    evidence: str = Field(
        description=(
            "The specific textual and narrative evidence. Quote the "
            "text. Reference what the spiritual reading said about "
            "these paragraphs. Explain WHY this is the diagnosis."
        )
    )
    recommendation: str = Field(
        description=(
            "'excise' — remove identified material (insertion into "
            "functional narrative, or expansion at a clear seam); "
            "'annotate' — flag as overlay but do NOT modify text "
            "(whole block in administrative voice); "
            "'none' — no action needed (genuine difficulty, clean text, "
            "or damage)."
        )
    )
    scope: str = Field(
        description=(
            "What specifically to remove or flag. For 'excise': quote "
            "the exact text to remove. For 'annotate': describe the "
            "block. For 'none': empty string."
        )
    )


class TextualCriticismResult(BaseModel):
    """Complete textual criticism for one chapter."""
    findings: list[CriticalFinding] = Field(
        description=(
            "Diagnostic findings. Include BOTH problems and clean "
            "confirmations. A chapter with no problems is valid — "
            "say so explicitly."
        )
    )
    summary: str = Field(
        description=(
            "Overall assessment: how many issues found, what types, "
            "how many recommended for excision vs annotation vs none."
        )
    )


# ===================================================================
# PYDANTIC MODELS — Stage 3c: Harmonization
# ===================================================================


class HarmonizedParagraph(BaseModel):
    """A single paragraph after harmonization."""
    paragraph_number: int = Field(
        description="The paragraph number."
    )
    text: str = Field(
        description=(
            "The paragraph text. MUST be clean text only — no "
            "annotations, markers, glosses, or editorial insertions. "
            "If unchanged, this is the exact original text."
        )
    )
    changed: bool = Field(
        description=(
            "Whether this paragraph was modified. Most should be "
            "unchanged (false). Only true when text was actually "
            "edited per the critic's recommendations."
        )
    )


class HarmonizationResult(BaseModel):
    """Complete harmonization result for one chapter."""
    harmonized_paragraphs: list[HarmonizedParagraph] = Field(
        description="The full list of paragraphs. Return EVERY paragraph."
    )
    changes_summary: str = Field(
        description=(
            "What was changed and why. Reference the critic's finding "
            "that justified each change. If nothing changed, say so."
        )
    )


# ===================================================================
# SYSTEM PROMPTS
# ===================================================================

# -------------------------------------------------------------------
# Stage 3a: SPIRITUAL READING
# -------------------------------------------------------------------

READING_PROMPT = """\
You are reading the oldest teaching substrate of the Coptic Kephalaia \
as a spiritual document. Your task is EXACT, HONEST, paragraph-by-\
paragraph correspondential reading.

You are NOT editing. You are NOT judging. You are READING — reporting \
what the text teaches at the spiritual level, paragraph by paragraph.

# CRITICAL RULES

1. Read EVERY paragraph. Do not skip any.
2. Be EXACT. Report what the text actually teaches, not what you \
   think it should teach.
3. If a paragraph does not yield coherent spiritual sense — say so. \
   Do not force meaning onto text that resists it.
4. If the narrative breaks — note where and how. A break is evidence, \
   not a failure of your reading.
5. If named figures appear that do not participate in the teaching — \
   note that they are listed but not active in the spiritual content.
6. If a passage lists entities by jurisdiction rather than teaching \
   by function — note the vocabulary shift.
7. The chapter_narrative should read as ONE continuous story. When \
   it can't — when you have to break the narrative to accommodate \
   a passage — that break IS the finding. Report it honestly.

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
are NOT primarily about discrete degrees.

## Opposite Sense
The same image can express good or evil depending on context: \
fire = divine love OR destructive self-love; water = living truth \
OR falsity; darkness = obscurity before illumination OR active \
denial. Always determine from context which sense applies.

## Ruling Love
The core orientation of a soul or system — toward the Divine \
(love of neighbor) or toward self (love of dominion). This \
polarity is often the REAL subject of a chapter.

## The Grand Man (Maximus Homo)
The form of the heavens is the human form. Function determines \
position: an organ IS its spiritual function in ultimates. \
Head = celestial; thorax = spiritual; abdomen = natural. \
Heart = love/will; lungs = wisdom/understanding.

## Regeneration
The spiritual process of transformation: old state broken, \
wilderness/combat, reformation through truth, then regeneration \
through good. Many chapters describe this PROCESS.

## The Proprium
The sense of self as separate. Not evil in itself — the vessel \
that must be formed. But when it claims what flows through it \
as its own, it becomes the obstacle.

## Accommodation
Truth delivered at the level the receiver can accept. The same \
spiritual reality may appear differently to different states.

## Numbers as Correspondences
Numbers are states, not counting:
- TWO = fundamental polarity (will/understanding, good/truth)
- THREE = discrete degrees (celestial/spiritual/natural)
- FOUR = completeness in ultimates (natural plane fully extended)
- FIVE = sufficiency ("enough," NOT a system number — never \
  describes degrees or how one level produces the next)
- SEVEN = complete process (full cycle from beginning to rest)
- TEN = conjunction with good held inside
- TWELVE = fullness of organized truths (3 × 4)

## Swedenborg Corrections
Where Swedenborg's 18th-century science introduced artifacts:
- The Limbus: rejected. Identity is the biography, not material \
  remnant.
- Biological determinism about Jesus: corrected. The Divine Human \
  achieved alignment through removal of obstruction, not different \
  origin.
- Matter as evil: corrected. The physical world is the Fixed Edge \
  — developmental arena, not prison.

# YOUR TASK: TRANSLATE, DO NOT ANNOTATE

You are translating the text from its natural sense INTO its \
spiritual sense. This is not annotation. This is not commentary. \
This is translation — the same way you would translate French \
into English, except you are translating natural images into \
what they EXPRESS spiritually.

**THE WRONG WAY (glossing/annotating):**
"The Mother of Life was established in storehouses (= interiors) \
in quiet and silence (= unmanifest state). When need arose she \
was called (= influx by use) and came forth."

This is wrong because the natural text is still there with \
parenthetical labels attached. You have not translated.

**THE RIGHT WAY (translating):**
"Love held wisdom within itself in a state of peace and potency. \
When the receiving vessel needed it, love sent wisdom forth, and \
wisdom immediately perceived all the goods and truths within \
her reach."

The natural image is GONE. What remains is what the natural \
image EXPRESSES. Every object has been passed through to its \
spiritual sense.

**TRANSLATE EVERYTHING.** Nothing passes through untranslated. \
Storehouses, quiet, silence, calling, sculpting, garments, \
borders, heights, earth, rain, dew, mist, birds, fire, trees, \
fruits — each one IS something at the spiritual level. Translate \
it. If you cannot determine what a natural object expresses, \
say so — that gap is evidence.

For each paragraph:
1. spiritual_content — the paragraph TRANSLATED into spiritual \
   sense. No natural objects remain.
2. narrative_flow — how this translated paragraph connects to \
   the chapter's spiritual story
3. notes — anything that resists translation, forces, breaks \
   the voice, or doesn't participate in the teaching

Then write the chapter_narrative — the COMPLETE spiritual story \
told entirely in the inner register, as one continuous piece. \
Where the translation produces incoherence, say so at that \
point and continue. The incoherence is evidence.

Your notes remain critical — they are evidence for the next \
stage. But the spiritual_content and chapter_narrative must be \
actual translations, not annotated natural text.
"""

# -------------------------------------------------------------------
# Stage 3b: TEXTUAL CRITICISM
# -------------------------------------------------------------------

CRITICISM_PROMPT = """\
You are performing TEXTUAL CRITICISM on a chapter of the oldest \
teaching substrate of the Coptic Kephalaia. You receive the full \
chapter text AND a paragraph-by-paragraph spiritual reading from a \
prior analysis stage.

Your task: examine where the spiritual reading STUMBLED and \
diagnose WHY. The reading's notes are your primary evidence — when \
the reader said "this doesn't fit" or "the narrative breaks here" \
or "these names don't participate in the teaching," your job is \
to explain what happened TEXTUALLY.

# DISTINGUISHING VOICES — PRIMARY DIAGNOSTIC

Before anything else, identify WHAT KIND OF TEACHING each passage is.

## Correspondential Voice (Substrate)
Teaches by FUNCTION — what things DO:
- "The liver is the vessel of fire" — the spiritual sense arises \
  from what the liver does (processes, transforms)
- Body regions mapped to cosmic regions BY FUNCTION
- Process described BY STATES (interior movements of love/truth)
- Grounded in organic relationship

Test: Can you explain WHY this natural thing corresponds to this \
spiritual reality, grounded in its function? If yes, the spiritual \
reading ARISES from the text.

## Administrative Voice (Mani's Layer)
Teaches by GOVERNANCE — who controls what territory:
- Named figures with jurisdictions
- Territorial administration (camps, watches, stations)
- Authority language ("master," "power," "authority lies over")
- Numbered inventories of named entities organized by rank

Test: Does the spiritual sense arise from what things DO, or from \
who ADMINISTERS them?

# THE NARRATIVE COHERENCE TEST

The spiritual reading attempts to tell the chapter's story as one \
narrative. Where that story breaks — where it stumbles, where it \
has to force, where named figures appear that don't participate — \
something was likely inserted.

Read the chapter narrative from the spiritual reading. Then mentally \
skip each flagged passage. If the story flows better without it, \
that is evidence of insertion.

# TYPES OF DISRUPTION

1. **INSERTION into functional narrative**: Administrative content \
   dropped into a correspondential teaching. The narrative reads \
   better without it. Named figures are LISTED, not ACTIVE in the \
   spiritual story. → Recommend: excise

2. **OVERLAY BLOCK**: An entire section in the administrative voice \
   with no functional teaching around it. The substrate teaching \
   exists elsewhere in the chapter. → Recommend: annotate (do NOT \
   carve substrate out of it)

3. **EXPANSION at a seam**: A systematizing addendum (often fivefold) \
   that recasts what the chapter taught in a different didactic mode. \
   Bridge connective + voice change + departure from the chapter's \
   own structure. → Recommend: excise

4. **GENUINE DIFFICULTY**: Damaged text, complex teaching, \
   accommodation. The reading struggles but removing text wouldn't \
   help. → Recommend: none

# WHAT EXCISION IS NOT

Never recommend excision to reach a target number. Do not trim five \
to three because "three is complete." If a section is entirely in \
the administrative voice, recommend annotation of the whole block — \
not extraction of three items.

The question is always: does the spiritual story flow without this \
passage? Not: does this passage make the count wrong?

# WHAT MANI TYPICALLY ADDED AT SEAMS

- Christological identification ("Jesus the Splendour") — naming \
  an eternal function with a historical figure
- Institutional mechanism ("counsel of life," \
  "summons-and-obedience")
- Recycled entities promoted to fill expanded taxonomies
- Bridge connectives ("Also, at that time,") at voice boundaries

# NUMBERS AS CONFIRMATION

Numbers confirm a voice diagnosis; they do not make it:
- Sections teaching by function organized by 2, 3, 4, 7, 12 — \
  the numbers confirm the correspondential voice
- Sections organized by fives — consistent with Mani's signature \
  numeration. But the number alone is not the diagnosis.

# YOUR TASK

For each finding:
1. location — which paragraph(s)
2. diagnosis — what is wrong, precisely
3. voice — correspondential / administrative / mixed / damaged
4. evidence — specific textual and narrative evidence (quote the \
   text AND reference what the spiritual reading said)
5. recommendation — excise / annotate / none
6. scope — for excise: quote the EXACT text to remove. For \
   annotate: describe the block. For none: empty string.

Include findings for CLEAN sections too (recommendation: none) — \
confirming coherent substrate is as valuable as identifying problems.

A chapter with no problems is a valid result. Say so explicitly.
"""

# -------------------------------------------------------------------
# Stage 3c: HARMONIZATION
# -------------------------------------------------------------------

HARMONIZE_PROMPT = """\
You are performing the FINAL HARMONIZATION of a chapter from the \
oldest teaching substrate of the Coptic Kephalaia. You receive:

1. The restored chapter text
2. The spiritual story of the chapter
3. Textual criticism findings with specific recommendations

Your task: EXECUTE the critic's recommendations to produce clean text.

# RULES

1. DEFAULT IS UNCHANGED. Return every paragraph. Most will be \
   unchanged (changed=false).

2. Only modify paragraphs specifically targeted by the critic's \
   "excise" recommendations.

3. For "excise" recommendations: remove the identified material. \
   The resulting text must read as coherent prose. If the excision \
   leaves a sentence fragment, clean it minimally for grammar.

4. For "annotate" recommendations: do NOT modify the text. The \
   annotation is recorded in the findings, not in the text.

5. For "none" recommendations: do NOT modify the text.

6. NEVER insert ANY of these into paragraph text:
   - Annotations like ⟨EXPANSION⟩ or ⟨TEXTUAL NOTE⟩
   - Correspondence glosses like ⟨= explanation⟩
   - Parenthetical interpretations
   - Editorial markers of any kind

7. NEVER remove connectives ("Also," "Again," "And") UNLESS they \
   are part of the specifically identified excision material.

8. The paragraph text must be CLEAN — exactly what the ancient \
   teacher would have said.

9. In changes_summary, reference the specific critic finding that \
   justified each change.
"""


# ===================================================================
# CHAPTER LOADING (from Pass 1 + Pass 2 output)
# ===================================================================


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


def format_chapter_text(
    ch_num: int, title: str, paragraphs: list[dict]
) -> str:
    """Format the chapter text for LLM input."""
    lines = [f"# Chapter {ch_num}: {title}", ""]
    for p in paragraphs:
        lines.append(f"¶{p['paragraph_number']}: {p['text']}")
        lines.append("")
    return "\n".join(lines)


def format_reading_for_critic(reading: SpiritualReadingResult) -> str:
    """Format the 3a reading output for the 3b critic."""
    lines = []
    lines.append("## CHAPTER NARRATIVE")
    lines.append(reading.chapter_narrative)
    lines.append("")
    lines.append("## PARAGRAPH-BY-PARAGRAPH READING")
    lines.append("")
    for pr in reading.paragraph_readings:
        lines.append(f"### ¶{pr.paragraph_number}")
        lines.append(f"**Spiritual content:** {pr.spiritual_content}")
        lines.append(f"**Narrative flow:** {pr.narrative_flow}")
        if pr.notes:
            lines.append(f"**Notes:** {pr.notes}")
        lines.append("")
    lines.append("## OVERALL COHERENCE")
    lines.append(reading.overall_coherence)
    return "\n".join(lines)


def format_criticism_for_harmonizer(
    criticism: TextualCriticismResult,
    chapter_narrative: str,
) -> str:
    """Format the 3b criticism output for the 3c harmonizer."""
    lines = []
    lines.append("## SPIRITUAL STORY")
    lines.append(chapter_narrative)
    lines.append("")
    lines.append("## TEXTUAL CRITICISM FINDINGS")
    lines.append("")
    for i, f in enumerate(criticism.findings, 1):
        lines.append(f"### Finding {i}: {f.location}")
        lines.append(f"**Diagnosis:** {f.diagnosis}")
        lines.append(f"**Voice:** {f.voice}")
        lines.append(f"**Evidence:** {f.evidence}")
        lines.append(f"**Recommendation:** {f.recommendation}")
        if f.scope:
            lines.append(f"**Scope:** {f.scope}")
        lines.append("")
    lines.append("## SUMMARY")
    lines.append(criticism.summary)
    return "\n".join(lines)


# ===================================================================
# LLM CALLS
# ===================================================================


def _call_llm(
    client: OpenAI,
    deployment: str,
    system_prompt: str,
    user_msg: str,
    response_model: type[BaseModel],
    label: str = "",
) -> BaseModel | None:
    """Call the LLM with retry logic. Returns parsed result or None."""
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            response = client.responses.parse(
                model=deployment,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                text_format=response_model,
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
                print(f"API error ({label}): {e}")
                return None
        except Exception as e:
            print(f"Error ({label}): {e}")
            if attempt < max_retries:
                time.sleep(10)
            else:
                return None
    return None


def run_spiritual_reading(
    client: OpenAI,
    deployment: str,
    chapter_text: str,
    pass2_reading: str | None = None,
) -> SpiritualReadingResult | None:
    """Stage 3a: Paragraph-by-paragraph spiritual reading."""
    parts = ["## RESTORED CHAPTER TEXT\n", chapter_text]
    if pass2_reading:
        parts.append("\n## CONTEXT: SPIRITUAL READING FROM PASS 2\n")
        parts.append(pass2_reading)
    user_msg = "\n".join(parts)
    return _call_llm(
        client, deployment, READING_PROMPT, user_msg,
        SpiritualReadingResult, label="3a-reading",
    )


def run_textual_criticism(
    client: OpenAI,
    deployment: str,
    chapter_text: str,
    reading: SpiritualReadingResult,
) -> TextualCriticismResult | None:
    """Stage 3b: Textual criticism using the spiritual reading."""
    reading_text = format_reading_for_critic(reading)
    parts = [
        "## RESTORED CHAPTER TEXT\n",
        chapter_text,
        "\n## SPIRITUAL READING (from Stage 3a)\n",
        reading_text,
    ]
    user_msg = "\n".join(parts)
    return _call_llm(
        client, deployment, CRITICISM_PROMPT, user_msg,
        TextualCriticismResult, label="3b-criticism",
    )


def run_harmonization(
    client: OpenAI,
    deployment: str,
    chapter_text: str,
    reading: SpiritualReadingResult,
    criticism: TextualCriticismResult,
) -> HarmonizationResult | None:
    """Stage 3c: Execute the critic's recommendations."""
    criticism_text = format_criticism_for_harmonizer(
        criticism, reading.chapter_narrative,
    )
    parts = [
        "## RESTORED CHAPTER TEXT\n",
        chapter_text,
        "\n",
        criticism_text,
    ]
    user_msg = "\n".join(parts)
    return _call_llm(
        client, deployment, HARMONIZE_PROMPT, user_msg,
        HarmonizationResult, label="3c-harmonize",
    )


# ===================================================================
# PIPELINE ORCHESTRATOR
# ===================================================================


def process_chapter(
    client: OpenAI,
    deployment: str,
    restored_paragraphs: list[dict],
    ch_num: int,
    title: str,
    pass2_reading: str | None = None,
    stop_after: str | None = None,
) -> dict | None:
    """Run the full three-stage pipeline for one chapter.

    Returns a dict with all results, or None on failure.
    """
    chapter_text = format_chapter_text(ch_num, title, restored_paragraphs)

    # ---- Stage 3a: Spiritual Reading ----
    print("reading...", end=" ", flush=True)
    reading = run_spiritual_reading(
        client, deployment, chapter_text, pass2_reading,
    )
    if reading is None:
        return None

    n_notes = sum(
        1 for pr in reading.paragraph_readings if pr.notes.strip()
    )

    if stop_after == "reading":
        print(f"3a done ({len(reading.paragraph_readings)} ¶s, "
              f"{n_notes} with notes)")
        return _build_result(
            ch_num, title, reading=reading,
            stages=["reading"],
        )

    # ---- Stage 3b: Textual Criticism ----
    print("criticizing...", end=" ", flush=True)
    criticism = run_textual_criticism(
        client, deployment, chapter_text, reading,
    )
    if criticism is None:
        return None

    n_excise = sum(
        1 for f in criticism.findings if f.recommendation == "excise"
    )
    n_annotate = sum(
        1 for f in criticism.findings if f.recommendation == "annotate"
    )

    if stop_after == "criticism":
        print(f"3b done ({len(criticism.findings)} findings, "
              f"{n_excise} excise, {n_annotate} annotate)")
        return _build_result(
            ch_num, title, reading=reading, criticism=criticism,
            stages=["reading", "criticism"],
        )

    # ---- Stage 3c: Harmonization ----
    print("harmonizing...", end=" ", flush=True)
    harmonized = run_harmonization(
        client, deployment, chapter_text, reading, criticism,
    )
    if harmonized is None:
        return None

    n_changed = sum(
        1 for p in harmonized.harmonized_paragraphs if p.changed
    )

    print(f"OK — {len(criticism.findings)} findings, "
          f"{n_excise} excise, {n_annotate} annotate, "
          f"{n_changed} ¶s changed")

    return _build_result(
        ch_num, title,
        reading=reading,
        criticism=criticism,
        harmonized=harmonized,
        stages=["reading", "criticism", "harmonization"],
    )


def _build_result(
    ch_num: int,
    title: str,
    reading: SpiritualReadingResult | None = None,
    criticism: TextualCriticismResult | None = None,
    harmonized: HarmonizationResult | None = None,
    stages: list[str] | None = None,
) -> dict:
    """Build the combined output dict."""
    result = {
        "chapter_number": ch_num,
        "chapter_title": title,
        "stages_completed": stages or [],
    }

    if reading:
        result["spiritual_reading"] = {
            "chapter_narrative": reading.chapter_narrative,
            "paragraph_readings": [
                pr.model_dump() for pr in reading.paragraph_readings
            ],
            "overall_coherence": reading.overall_coherence,
        }
    else:
        result["spiritual_reading"] = None

    if criticism:
        result["textual_criticism"] = {
            "findings": [f.model_dump() for f in criticism.findings],
            "summary": criticism.summary,
        }
    else:
        result["textual_criticism"] = None

    if harmonized:
        result["harmonized_paragraphs"] = [
            p.model_dump() for p in harmonized.harmonized_paragraphs
        ]
        result["changes_summary"] = harmonized.changes_summary
    else:
        result["harmonized_paragraphs"] = None
        result["changes_summary"] = None

    return result


# ===================================================================
# SAVE / LOAD
# ===================================================================


def save_result(result: dict) -> None:
    """Save pipeline result to JSON."""
    CHAPTERS_OUT_DIR.mkdir(parents=True, exist_ok=True)
    ch_num = result["chapter_number"]
    path = CHAPTERS_OUT_DIR / f"ch_{ch_num:03d}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


def is_done(ch_num: int) -> bool:
    path = CHAPTERS_OUT_DIR / f"ch_{ch_num:03d}.json"
    if not path.exists():
        return False
    # Only count as done if full pipeline completed
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return "harmonization" in data.get("stages_completed", [])


# ===================================================================
# ASSEMBLY
# ===================================================================


def assemble_harmonized(core_chapters: dict[int, dict]) -> str:
    """Assemble all harmonized chapters into a continuous document."""
    harmonized_by_ch: dict[int, dict] = {}
    for path in sorted(CHAPTERS_OUT_DIR.glob("ch_*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            if "harmonization" in data.get("stages_completed", []):
                harmonized_by_ch[data["chapter_number"]] = data

    if not harmonized_by_ch:
        print("ERROR: No fully harmonized chapters found.")
        return ""

    lines: list[str] = []
    lines.append("# The Kephalaia Teaching Core — Harmonized Text")
    lines.append("")
    lines.append("*The oldest teaching layer of the Kephalaia, restored and*")
    lines.append("*structurally harmonized through three-stage analysis:*")
    lines.append("*spiritual reading → textual criticism → harmonization.*")
    lines.append("")
    lines.append("---")
    lines.append("")

    total_findings = 0
    total_excisions = 0
    total_annotations = 0
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
            # Harmonized paragraphs
            paras = harm_ch.get("harmonized_paragraphs", [])
            for p in paras:
                pnum = p.get("paragraph_number", "?")
                text = p.get("text", "")
                changed = p.get("changed", False)
                marker = " [*]" if changed else ""
                lines.append(f"**¶{pnum}**{marker} {text}")
                lines.append("")

            # Textual criticism findings
            crit = harm_ch.get("textual_criticism", {})
            findings = crit.get("findings", []) if crit else []
            n_findings = len(findings)
            n_excise = sum(
                1 for f in findings if f.get("recommendation") == "excise"
            )
            n_annotate = sum(
                1 for f in findings if f.get("recommendation") == "annotate"
            )
            n_changed = sum(
                1 for p in paras if p.get("changed")
            )

            total_findings += n_findings
            total_excisions += n_excise
            total_annotations += n_annotate
            total_changes += n_changed

            if findings:
                lines.append("> **Textual criticism:**")
                for f in findings:
                    loc = f.get("location", "")
                    diag = f.get("diagnosis", "")[:200]
                    rec = f.get("recommendation", "")
                    lines.append(f"> - {loc} [{rec}]: {diag}")
                lines.append("")

            # Changes summary
            changes = harm_ch.get("changes_summary", "")
            if changes:
                lines.append(f"**Changes:** {changes}")
                lines.append("")

            # Spiritual narrative
            reading = harm_ch.get("spiritual_reading", {})
            narrative = reading.get("chapter_narrative", "") if reading else ""
            if narrative:
                lines.append(f"**Spiritual narrative:** {narrative}")
                lines.append("")

        else:
            # No harmonization — use core text
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
        f"**Total textual criticism findings**: {total_findings}",
        f"**Excision recommendations**: {total_excisions}",
        f"**Annotation recommendations**: {total_annotations}",
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


# ===================================================================
# CLI
# ===================================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Pass 3: Three-stage structural harmonization of the "
            "Kephalaia teaching core."
        )
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
        help="Skip processing, assemble existing results only",
    )
    parser.add_argument(
        "--stop-after", choices=["reading", "criticism"],
        help="Stop after this stage (for debugging)",
    )
    return parser.parse_args()


# ===================================================================
# MAIN
# ===================================================================


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

    # Skip already processed (unless overwrite or partial run)
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
    if args.stop_after:
        print(f"Stopping after: {args.stop_after}")
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

        # Get Pass 2 assessment as optional context
        pass2_reading = None
        if rest_ch:
            pass2_reading = (
                rest_ch.get("spiritual_reading")
                or rest_ch.get("assessment")
            )

        print(
            f"[{i}/{len(chapters)}] Ch.{ch_num} "
            f"({len(restored_paras)} ¶s) {title}... ",
            end="", flush=True,
        )

        result = process_chapter(
            client, deployment, restored_paras,
            ch_num, title,
            pass2_reading=pass2_reading,
            stop_after=args.stop_after,
        )

        if result is None:
            print("FAILED")
            errors.append(ch_num)
            continue

        save_result(result)
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

    # Assemble (only if full pipeline ran)
    if not args.stop_after:
        print("\nAssembling harmonized document...")
        text = assemble_harmonized(core_by_num)
        if text:
            save_assembly(text)

    print("Done.")


if __name__ == "__main__":
    main()
