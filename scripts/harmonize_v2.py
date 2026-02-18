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
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

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


class ParagraphTranslation(BaseModel):
    """Translation of a single paragraph from natural to spiritual sense."""
    paragraph_number: int = Field(
        description="The paragraph number from the source text."
    )
    translation: str = Field(
        description=(
            "The paragraph rewritten entirely in the spiritual "
            "register. Every natural object is REPLACED by the "
            "spiritual reality it expresses. The result reads as "
            "continuous prose about spiritual states, with NO "
            "natural objects remaining.\n\n"
            "YOUR OUTPUT HAS FAILED IF IT CONTAINS ANY OF THESE:\n"
            "- Direct quotes from the source text\n"
            "- Parenthetical glosses like (= interiors) or "
            "(= unmanifest state)\n"
            "- The phrases 'corresponds to', 'teaches that', "
            "'indicates', 'represents'\n"
            "- Natural objects named and then explained\n\n"
            "CORRECT: 'Love held wisdom in peace and potency.'\n"
            "WRONG: 'Storehouses (= interiors) in quiet and "
            "silence (= unmanifest state).'\n\n"
            "If the paragraph resists translation, commit to "
            "your best attempt and flag uncertainty in the notes "
            "field — but the translation field must still be a "
            "translation, not a commentary."
        )
    )
    connection: str = Field(
        description=(
            "How this translated paragraph joins the chapter's "
            "spiritual story: CONTINUES, DEVELOPS, SHIFTS, or "
            "BREAKS. One sentence."
        )
    )
    notes: str = Field(
        description=(
            "Anything that resists translation, forces, seems "
            "inserted, or breaks the voice. Named figures that "
            "appear but don't function. Vocabulary shifts. Empty "
            "string if clean."
        )
    )


class SpiritualReadingResult(BaseModel):
    """Complete spiritual translation for one chapter."""
    full_translation: str = Field(
        description=(
            "The chapter's complete spiritual story as ONE continuous "
            "piece of prose. Every natural image is gone — replaced "
            "by what it expresses. Write as if someone who perceives "
            "only spiritual reality told you what this chapter says. "
            "Where the translation breaks into incoherence, say so "
            "at that point and continue — the break is evidence."
        )
    )
    paragraph_translations: list[ParagraphTranslation] = Field(
        description="One translation per source paragraph. Translate EVERY paragraph."
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
You are a TRANSLATOR. You translate text from its natural sense \
into its spiritual sense — the same way one translates French \
into English, except you are translating natural images into \
what they EXPRESS spiritually.

You are NOT analysing, NOT commenting, NOT annotating. You are \
producing a new text in which every natural object has been \
replaced by the spiritual reality it expresses.

# WHAT TRANSLATION LOOKS LIKE — EXAMPLES

Study these carefully. This is the ONLY acceptable output mode.

## Example 1

NATURAL TEXT:
"He sculpted the Mother of Life, established her in storehouses \
in quiet and silence. When need arose she was called and came \
forth. She looked at all her aeons of light."

WRONG (glossing — natural text with labels attached):
"The Mother of Life (= wisdom) was established in storehouses \
(= interiors) in quiet and silence (= unmanifest state). When \
need arose she was called (= influx by use) and came forth."

RIGHT (translation — natural images gone, spiritual story told):
"Love formed wisdom within itself and held it in peace and \
potency before any outward work. When the receiving vessel \
required it, love sent wisdom forth. Wisdom immediately \
perceived all the goods and truths within her domain."

## Example 2

NATURAL TEXT:
"He clothed his five sons in garments and stationed them at the \
borders. They were anointed and set fast."

WRONG:
"His five sons (= sufficient operative powers) are clothed in \
garments (= external truths) and stationed at borders (= \
ultimates)."

RIGHT:
"The Divine invested a sufficient complement of operative powers \
with external truths for action in the outermost degree, and \
fixed them there by consecration."

## Example 3

NATURAL TEXT:
"From the thought of death five elements came: smoke, fire, wind, \
water, darkness. From these grew trees, and from the trees fruits, \
and the fruits nourished the demons."

WRONG:
"Five elements (= basic falsities/evils) arose from the thought \
of death. Trees (= perceptions) grew, fruits (= works) formed, \
and demons were nourished."

RIGHT:
"From the intention of spiritual death, a sufficient series of \
fundamental falsities arose: obscured understanding, self-love, \
volatile persuasion, falsified truth, and active denial of good. \
These falsities organized into systems of perverted perception, \
which produced corresponding works, and those works sustained \
the hells."

## What makes the RIGHT versions right

- No natural objects remain. Storehouses, garments, borders, \
  trees, fruits are GONE. What is there instead is what they \
  EXPRESS.
- The result reads as continuous prose, not as a gloss-table.
- Every single object has been translated. Nothing passes through \
  untranslated.
- Where translation produces something uncertain, say so: "this \
  object's spiritual sense is unclear — it may express X."

# REFERENCE: THE CORRESPONDENTIAL LOOKUP TABLE

Use this table when translating. Every natural object in the text \
should be looked up here (or reasoned from its function if not \
listed) and REPLACED by its spiritual reality.

**The two poles:** fire/heat = love/will; water = truth/understanding.

**Water forms:** river = truth flowing with intelligence; sea = \
general knowledges in externals; rain = influx of Divine truth \
descending; fountain = interior truth rising from within; \
dew = peaceful truth from celestial love; mist = obscure truth \
not yet clear.

**Light and darkness:** light = wisdom (enables distinction); \
darkness = either obscurity before illumination or active falsity.

**Spatial:** mountains = elevated spiritual states; heights = \
proximity to source of influx; depths/earth = natural degree / \
ultimates; borders = outermost limits of a domain.

**Objects:** storehouses = interiors where good/truth is held; \
garments = external truths that clothe spiritual reality; \
vessels = containing forms; seeds = interior truths in potency; \
trees = perceptions; fruits = works/deeds that proceed from \
perceptions.

**Living things:** animals = affections (each species a specific \
quality); birds = thoughts at the spiritual level.

**Actions:** sculpting/forming = bringing into determinate \
existence; calling = directed influx; clothing = investing with \
external truths; anointing = consecration with love for use; \
sending down = influx descending to lower degrees; stripping = \
removing external truths.

**Numbers:** 2 = will/understanding polarity; 3 = discrete \
degrees (celestial/spiritual/natural); 4 = completeness in \
ultimates; 5 = sufficiency; 7 = full process; 10 = conjunction; \
12 = fullness of organized truths.

**Degree architecture:** celestial (love/will) → spiritual \
(wisdom/truth) → natural (effect/use). Influx flows downward.

**Opposite sense:** The same image can express good or evil by \
context. Fire = divine love OR self-love. Water = living truth \
OR falsity. Determine from context.

**Named cosmological figures:** Translate by FUNCTION. "Mother \
of Life" = wisdom-principle; "First Man" = the good that engages \
directly with evil; "five sons" = sufficient operative powers. \
If a name appears without a discernible function — note that \
it resists translation.

**The proprium:** self-sense. Not evil in itself; becomes \
obstacle when it claims what flows through it as its own.

# RULES FOR HONEST TRANSLATION

1. Translate EVERY paragraph. Do not skip any.
2. If a paragraph does NOT yield coherent spiritual sense when \
   translated — say so in the notes and put your best attempt \
   in the translation field, marking what is uncertain.
3. If named figures appear that are LISTED but don't participate \
   in the teaching — note this in the notes field.
4. If the narrative breaks — mark the break in the notes. A \
   break IS a finding, not a failure.
5. The full_translation must be ONE continuous story told \
   entirely in the spiritual register. Where it breaks, say so \
   and continue.

# OUTPUT

For each paragraph:
1. translation — the paragraph in the spiritual register. No \
   natural objects. Reads as continuous prose about spiritual \
   states and processes. If your output contains quotes from the \
   source text, parenthetical glosses, or the phrase "corresponds \
   to" — you have not translated.
2. connection — one sentence: CONTINUES / DEVELOPS / SHIFTS / BREAKS
3. notes — anything that resists, forces, or doesn't participate

Then write full_translation — the complete spiritual story of \
this chapter as one continuous piece of prose. No natural objects \
remain anywhere in it.

Your notes are critical evidence for the next stage. But \
translation and full_translation must be actual translations — \
prose about spiritual realities, not commentary about a text.
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


def fix_stray_brackets(text: str) -> str:
    """Remove unmatched brackets from reconstruction text.

    Uses a stack to identify properly-paired ``[…]`` and removes any
    stray ``]`` (no preceding ``[``) or ``[`` (no following ``]``).
    This preserves correctly-bracketed scholarly markers while cleaning
    up the occasional model notation error.
    """
    stack: list[int] = []
    to_remove: set[int] = set()
    for i, ch in enumerate(text):
        if ch == "[":
            stack.append(i)
        elif ch == "]":
            if stack:
                stack.pop()
            else:
                to_remove.add(i)
    to_remove.update(stack)  # unmatched [
    if not to_remove:
        return text
    return "".join(ch for i, ch in enumerate(text) if i not in to_remove)


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

    Prefers model-authored reconstructed paragraphs (coherent prose)
    from the ``reconstructions`` field of Pass 2 output.  Falls back
    to mechanical fill insertion when reconstructions are absent.

    Returns list of {paragraph_number, text} dicts.
    """
    fills_by_para: dict[int, list[dict]] = {}
    recon_by_para: dict[int, str] = {}
    if rest_ch:
        for fill in rest_ch.get("fills", []):
            para = fill["paragraph"]
            if para not in fills_by_para:
                fills_by_para[para] = []
            fills_by_para[para].append(fill)
        # Prefer model's coherent reconstructed paragraphs
        for recon in rest_ch.get("reconstructions", []):
            recon_by_para[recon["paragraph"]] = recon["reconstructed_text"]

    paragraphs = []
    for para in core_ch.get("paragraphs", []):
        pnum = para["paragraph_number"]
        core_text = para.get("core_text")
        if not core_text:
            continue

        if pnum in recon_by_para:
            # Use model's coherent reconstruction (fix stray brackets)
            restored = fix_stray_brackets(recon_by_para[pnum])
        elif fills_by_para.get(pnum):
            # Fall back to mechanical fill insertion
            restored = fix_stray_brackets(
                apply_fills_to_paragraph(core_text, fills_by_para[pnum])
            )
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
    lines.append("## CHAPTER TRANSLATION")
    lines.append(reading.full_translation)
    lines.append("")
    lines.append("## PARAGRAPH-BY-PARAGRAPH TRANSLATION")
    lines.append("")
    for pr in reading.paragraph_translations:
        lines.append(f"### ¶{pr.paragraph_number}")
        lines.append(f"**Translation:** {pr.translation}")
        lines.append(f"**Connection:** {pr.connection}")
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
    """Stage 3a: Paragraph-by-paragraph spiritual translation."""
    parts = [
        "# SOURCE TEXT TO TRANSLATE\n",
        "Translate every paragraph of this chapter from its natural "
        "sense into the spiritual sense. Replace every natural object "
        "with the spiritual reality it expresses.\n",
        chapter_text,
    ]
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
        criticism, reading.full_translation,
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
        1 for pr in reading.paragraph_translations if pr.notes.strip()
    )

    if stop_after == "reading":
        print(f"3a done ({len(reading.paragraph_translations)} ¶s, "
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
            "full_translation": reading.full_translation,
            "paragraph_translations": [
                pr.model_dump() for pr in reading.paragraph_translations
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
            narrative = reading.get("full_translation", "") if reading else ""
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
    parser.add_argument(
        "--concurrency", "-j", type=int, default=1,
        help="Number of chapters to process concurrently (default: 1)",
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
    concurrency = args.concurrency
    print(f"\nUsing deployment: {deployment}")
    print(f"Concurrency: {concurrency}")
    if args.stop_after:
        print(f"Stopping after: {args.stop_after}")
    print()

    # Process
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CHAPTERS_OUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- Worker function for one chapter ---
    print_lock = threading.Lock()
    counter = [0]         # mutable counter shared across threads
    results_list = []
    errors_list = []

    def process_one(ch: dict) -> None:
        ch_num = ch["chapter_number"]
        title = ch.get("chapter_title", f"Chapter {ch_num}")[:50]

        # Build restored text
        rest_ch = load_restoration(ch_num)
        restored_paras = build_restored_text(ch, rest_ch)

        if not restored_paras:
            with print_lock:
                counter[0] += 1
                print(
                    f"[{counter[0]}/{len(chapters)}] Ch.{ch_num} "
                    f"— no core text, skip"
                )
            return

        # Get Pass 2 assessment as optional context
        pass2_reading = None
        if rest_ch:
            pass2_reading = (
                rest_ch.get("spiritual_reading")
                or rest_ch.get("assessment")
            )

        with print_lock:
            print(
                f"  Ch.{ch_num} ({len(restored_paras)} ¶s) {title}... ",
                flush=True,
            )

        result = process_chapter(
            client, deployment, restored_paras,
            ch_num, title,
            pass2_reading=pass2_reading,
            stop_after=args.stop_after,
        )

        with print_lock:
            counter[0] += 1
            if result is None:
                print(f"[{counter[0]}/{len(chapters)}] Ch.{ch_num} FAILED")
                errors_list.append(ch_num)
            else:
                save_result(result)
                results_list.append(ch_num)
                print(f"[{counter[0]}/{len(chapters)}] Ch.{ch_num} OK")

    # --- Run sequentially or in parallel ---
    if concurrency <= 1:
        for ch in chapters:
            process_one(ch)
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {pool.submit(process_one, ch): ch for ch in chapters}
            for fut in as_completed(futures):
                exc = fut.exception()
                if exc:
                    ch = futures[fut]
                    with print_lock:
                        counter[0] += 1
                        print(
                            f"[{counter[0]}/{len(chapters)}] "
                            f"Ch.{ch['chapter_number']} EXCEPTION: {exc}"
                        )
                        errors_list.append(ch["chapter_number"])

    # Summary
    print(f"\n{'=' * 60}")
    print("HARMONIZATION COMPLETE")
    print(f"  Processed: {len(results_list)}")
    print(f"  Errors: {len(errors_list)}")
    if errors_list:
        print(f"  Failed: {sorted(errors_list)}")

    # Assemble (only if full pipeline ran)
    if not args.stop_after:
        print("\nAssembling harmonized document...")
        text = assemble_harmonized(core_by_num)
        if text:
            save_assembly(text)

    print("Done.")


if __name__ == "__main__":
    main()
