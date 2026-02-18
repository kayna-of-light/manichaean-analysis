#!/usr/bin/env python3
"""
Correspondential Restoration of the Kephalaia Teaching Core.

Reads the extracted core text through the correspondential lens and
restores lacunae using the spiritual logic of the text itself.

Architecture: the model receives the full chapter text plus a numbered
list of all lacunae (square brackets). It outputs fill text for each
lacuna. The fills are then programmatically inserted into the original
text, guaranteeing that no non-bracket text is ever altered.

Input:  output/core/chapters/ch_NNN.json   (from extract_core.py)
Output: output/correspondential/chapters/ch_NNN.json   (fills)
        output/correspondential/restored_kephalaia.md   (assembled)

Usage:
    python scripts/correspondential_reading.py                  # All
    python scripts/correspondential_reading.py --chapter 38     # Single
    python scripts/correspondential_reading.py --dry-run        # Preview
    python scripts/correspondential_reading.py --overwrite      # Redo
    python scripts/correspondential_reading.py --assemble       # Assemble
"""
import argparse
import json
import re
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
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
OUTPUT_DIR = PROJECT_ROOT / "output" / "correspondential"
CHAPTERS_OUT_DIR = OUTPUT_DIR / "chapters"
ASSEMBLED_FILE = OUTPUT_DIR / "restored_kephalaia.md"


# ---------------------------------------------------------------------------
# Pydantic models for structured LLM output
# ---------------------------------------------------------------------------

class LacunaFill(BaseModel):
    """Model output for a single lacuna restoration."""
    paragraph: int = Field(
        description="Paragraph number from the input text."
    )
    index: int = Field(
        description=(
            "1-based index of this bracket within the paragraph, "
            "counting left to right."
        )
    )
    fill: str = Field(
        description=(
            "The text to place inside the square brackets. "
            "Do NOT include the brackets themselves. "
            "Return '...' if the gap is unrestorable."
        )
    )
    notes: str = Field(
        description=(
            "Brief correspondential reasoning for the fill. "
            "For trivial letter fills where the reading is certain, "
            "use an empty string."
        )
    )
    confidence: str = Field(
        description=(
            "'strong' = reading is certain or tightly constrained. "
            "'moderate' = direction clear but exact wording uncertain. "
            "'tentative' = plausible but other readings possible. "
            "'minimal' = too damaged for meaningful reconstruction."
        )
    )


class SpiritualReading(BaseModel):
    """Pre-pass: correspondential translation of a full chapter."""
    reading: str = Field(
        description=(
            "A TRANSLATION of the chapter from its natural sense "
            "into its spiritual sense. Every natural object has been "
            "replaced by the spiritual reality it expresses. No "
            "natural images remain — no storehouses, garments, trees, "
            "fruits, mountains, ships. What remains is continuous "
            "prose about spiritual states and processes: influx, "
            "degrees, transformation, love, wisdom, the human form. "
            "If your output contains parenthetical glosses or the "
            "phrase 'corresponds to' — you have not translated."
        )
    )


class ParagraphPlan(BaseModel):
    """Correspondence plan for one paragraph — maps each significant
    bracket to the correct natural image by verifying its
    correspondential meaning BEFORE composition begins."""
    paragraph: int = Field(
        description="Paragraph number."
    )
    spiritual_function: str = Field(
        description=(
            "What is this paragraph ABOUT spiritually? Summarise "
            "what the spiritual reading says is happening here in "
            "2-3 sentences."
        )
    )
    bracket_plans: str = Field(
        description=(
            "For each SUBSTANTIAL bracket (not trivial letter "
            "fills), state: (a) what spiritual function this gap "
            "serves, (b) what candidate natural images from the "
            "Kephalaia could fill it, (c) which image's "
            "CORRESPONDENTIAL MEANING matches the spiritual "
            "function, (d) which images would be WRONG and why "
            "their correspondence doesn't match. For trivial "
            "letter fills, just note 'trivial — [word]'."
        )
    )


class CorrespondencePlan(BaseModel):
    """Layer 2: map every bracket to the correct natural image
    by checking correspondential meaning against the spiritual reading.
    This plan is then fed to the reconstruction layer as constraint."""
    plans: list[ParagraphPlan] = Field(
        description=(
            "One entry per paragraph that contains lacunae. For "
            "each, explain the spiritual function and map each "
            "bracket to the correct natural image with explicit "
            "correspondential verification."
        )
    )


class ParagraphReconstruction(BaseModel):
    """Full reconstructed paragraph — the PRIMARY output."""
    paragraph: int = Field(
        description="Paragraph number."
    )
    reconstructed_text: str = Field(
        description=(
            "COMPOSE the complete paragraph as FLOWING ENGLISH "
            "PROSE. Start from the CORRESPONDENCE PLAN for this "
            "paragraph: you have already determined what natural "
            "images are correct. Now write a natural-sense sentence "
            "that uses those images, keeping the SURVIVING "
            "(non-bracket) words as fixed anchor points. "
            "Your additions go inside [square brackets]. The "
            "result must read as a REAL SENTENCE a person would "
            "write — grammatical, with proper clause structure, "
            "connective tissue, and flow. Read it aloud: if it "
            "sounds like word salad, recompose until it flows."
        )
    )


class ChapterResult(BaseModel):
    """Restoration result for one chapter."""
    reconstructions: list[ParagraphReconstruction] = Field(
        description=(
            "YOUR PRIMARY OUTPUT. One entry per paragraph that "
            "contains lacunae. COMPOSE each paragraph as flowing "
            "prose — guided by the CORRESPONDENCE PLAN (which has "
            "already determined the correct natural images for each "
            "bracket) and the surviving text. Do not fill brackets "
            "independently; write the whole sentence."
        )
    )
    fills: list[LacunaFill] = Field(
        description=(
            "DERIVED from your reconstructions. One fill per "
            "lacuna listed in the input. Extract the text you "
            "placed inside each bracket in your reconstructions. "
            "Every listed lacuna must have a corresponding entry."
        )
    )
    assessment: str = Field(
        description=(
            "Overall assessment: How much of this chapter's damaged "
            "text could be recovered? How tight were the "
            "correspondential constraints?"
        )
    )


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are restoring the OLDEST TEACHING SUBSTRATE of the Coptic Kephalaia \u2014 \
the pre-Manichaean cosmological teaching that Mani inherited, compiled, \
and overlaid with his own institutional language. Your task is to fill \
lacunae (gaps in square brackets) using the correspondential logic of \
the text, in the vocabulary of the OLDEST LAYER.

## WHAT YOU ARE RESTORING

This is NOT Mani\u2019s text. This is what is UNDERNEATH Mani\u2019s text. The \
Kephalaia is a composite: a pre-existing cosmological teaching tradition \
was compiled by Mani\u2019s community and wrapped in hagiographic frame, \
institutional language, and Christian overlay. The core extraction you \
receive has already stripped the frame and most overlays. But the \
VOCABULARY of the core may still carry Coptic translation artifacts and \
editorial choices that obscure the original register.

### The Three Layers

1. **OLDEST SUBSTRATE** (what we are restoring):
   Pre-Manichaean cosmological teaching from the Eastern tradition. \
   At its deepest, this is the tradition of the Bene Qedem (\u201cChildren \
   of the East\u201d) \u2014 the correspondential science preserved in what \
   Swedenborg called \u201cGreat Tartary.\u201d More immediately, it is Persian/ \
   Iranian cosmological wisdom: Zoroastrian in structure, correspondential \
   in method, impersonal in voice. This layer EXPOUNDS how reality works. \
   It does not cite authorities, it does not preach, it does not exhort.

2. **MANI\u2019S COMPILATION** (Layer 2):
   Mani took this teaching and reframed it. He added dialogue frames \
   (\u201cThen speaks the apostle to him:\u201d), mapped some entities onto \
   Christian names, and inserted institutional categories. The TEACHING \
   CONTENT is often preserved intact; the FRAMING is Mani\u2019s.

3. **LATER COMMUNITY** (Layer 3):
   Pastoral rules, NT exempla, devotional additions.

### Vocabulary Register

The text you receive preserves the Coptic translation vocabulary. \
Personified cosmological entities are capitalized (Sin, Darkness) to \
mark them as agents rather than moral categories.

When you fill brackets, maintain the same vocabulary and register as \
the surrounding text.

### Previous Editors\u2019 Choices

Existing bracket fills [text] from Gardner and Funk are part of the \
scholarly apparatus. Evaluate each against the correspondential logic \
and the context. Accept when it fits. Adjust when the correspondential \
reasoning demands it. Note changes.

## METHOD: CORRESPONDENTIAL READING

Read the text through the theory of correspondences. Correspondence is \
the organic relationship between a natural object and the spiritual \
reality it expresses \u2014 NOT allegory, NOT metaphor. The natural IS the \
spiritual in ultimates. Direction: INSIDE \u2192 OUTSIDE.

Key principles:
- DISCRETE DEGREES: Celestial (love/will), spiritual (wisdom/truth), \
  natural (effects). Complete levels, not a continuum.
- OPPOSITE SENSE: Same image can express good or evil by context.
- CONSTANT STATE, VARIABLE FORM: Underlying reality is constant; forms \
  vary by the receiver\u2019s repertoire.

You are deeply trained on Swedenborg\u2019s writings, the doctrine of \
correspondences, Zoroastrian cosmology (Bundahishn, Avesta), and the \
Manichaean cosmogonic myth. Trust that training. Let the spiritual \
logic of the text and the structure of the Persian substrate constrain \
what can appear at each point.

## NAMES AND ETYMOLOGY

Names are never arbitrary. Understand the ROOT: Semitic, Greek, Aramaic, \
Persian origins. The root illuminates the spiritual function. When a \
name appears in a gap, reconstruct from the FUNCTION the cosmic being \
serves in context, using the naming conventions of the oldest substrate.

## THE BRACKET SYSTEM

The text uses square brackets for editorial apparatus:
- [...] \u2014 complete gap, nothing readable
- [text] \u2014 editor\u2019s reconstruction of damaged text
- [le]tter \u2014 partial word: letters outside brackets are certain, \
  inside brackets are reconstructed
- [text ... ] \u2014 partially readable text followed by a gap
- [text (?) ...] \u2014 uncertain reading followed by a gap

You receive a numbered list of all brackets in the chapter. For each, \
provide the text that should go inside the brackets.

## FORBIDDEN CHARACTERS IN FILLS

NEVER use forward slash (/) in a fill. The scholarly edition used / as a \
page-break marker inside brackets \u2014 it is NOT content and NOT an \
alternative notation. If you are uncertain between two readings, COMMIT \
to the one the spiritual logic demands. Do not hedge with \u201cword1 / word2\u201d.

Your fill must read as continuous ancient text. Use only the punctuation \
found in the surrounding Coptic-English translation: commas, full stops, \
colons, semicolons. Never use: /, @, #, %, +, =, ~, ^, |, <, >, {, }.

## HOW TO FILL

1. Read the ENTIRE chapter text to grasp its correspondential structure.
2. For each lacuna, determine what the spiritual logic DEMANDS at \
   that point. The text is a correspondence map \u2014 when you read it \
   spiritually, gaps that are opaque on the surface become constrained \
   by the spiritual narrative.
3. Your fill REPLACES the content inside the brackets. Do NOT include \
   brackets in your fill.
4. For mid-word brackets like garm[ents], your fill must produce a \
   valid word with the surrounding text. The letters outside brackets \
   are fixed \u2014 your fill must join them into a coherent word.
5. For [...] gaps, consult the CORRESPONDENCE PLAN if provided. \
   The plan has already determined what natural image is correct for \
   each significant bracket by verifying that the image's \
   correspondential meaning matches the spiritual function. USE the \
   image specified in the plan. If no plan is provided, determine \
   what the SPIRITUAL TRANSLATION demands at this point, then \
   express that reality in the NATURAL VOCABULARY of the Kephalaia. \
   COMMIT to ONE reading.
6. For existing editor fills, evaluate whether the fill matches the \
   substrate register. Accept if sound. Adjust if the spiritual logic \
   or the substrate vocabulary demands a different reading. Note the \
   change and reasoning.
7. If a gap truly cannot be restored, return "..." as the fill.
8. Use language consistent with the OLDEST LAYER of the text \u2014 \
   cosmological, structural, impersonal. Not devotional, not pastoral, \
   not Christian-soteriological.
9. For trivial single-letter fills where the reading is certain, \
   return the same letter with empty notes and confidence \u2018strong\u2019.
10. For substantial restorations, explain the correspondential \
    reasoning in notes \u2014 including any substrate-register adjustments \
    you made to existing editor fills.

## CRITICAL: THE NATURAL REGISTER

The Kephalaia IS written in correspondence. It is a NATURAL-PLANE text. \
Its vocabulary \u2014 Light, Darkness, garments, five sons, firmaments, \
aeons, trees, fruits, fire, water \u2014 is the natural language that \
EXPRESSES spiritual realities through organic correspondence.

The spiritual reading translates those natural images into spiritual \
language: wisdom, falsity, external truths, five faculties, discrete \
degrees, influx, etc.

Your fills must stay in the TEXT\u2019S OWN REGISTER \u2014 the natural \
counterpart. The spiritual reading tells you WHAT reality the gap \
describes. Your fill expresses that reality in the KEPHALAIA\u2019S \
VOCABULARY, not in Swedenborgian vocabulary.

### Examples of the distinction

Spiritual reading says: \u201cby successive influx through discrete degrees\u201d
\u2192 WRONG fill: \u201cby influx\u201d (spiritual-plane vocabulary)
\u2192 RIGHT fill: \u201cby the power of the Light\u201d (Kephalaia vocabulary)

Spiritual reading says: \u201cthe five operative faculties of the outer mind\u201d
\u2192 WRONG fill: \u201cthe five faculties\u201d (spiritual-plane vocabulary)
\u2192 RIGHT fill: \u201cthe five sons\u201d or \u201cthe five members\u201d (Kephalaia)

Spiritual reading says: \u201cordered extension through degrees\u201d
\u2192 WRONG fill: \u201cin ordered extension\u201d (Swedenborgian)
\u2192 RIGHT fill: \u201cthrough the aeons\u201d (Kephalaia vocabulary)

Spiritual reading says: \u201cexternal truths as coverings\u201d
\u2192 WRONG fill: \u201ccoverings of external truth\u201d (spiritual)
\u2192 RIGHT fill: \u201cgarments\u201d (Kephalaia vocabulary)

Exception: Where the natural and spiritual terms are essentially the \
same word (\u201cLight\u201d = truth/wisdom; \u201cDarkness\u201d = falsity), the \
natural term IS already the right word. No translation needed.

The rule: UNDERSTAND the spiritual sense. WRITE the natural sense.

## RECONSTRUCTION-FIRST WORKFLOW

Your PRIMARY task is to produce RECONSTRUCTED PARAGRAPHS \u2014 complete, \
flowing English prose for every paragraph that contains lacunae. \
The `reconstructions` field comes FIRST in your output. Write those \
first. Then extract fills from them.

### How to compose a reconstruction

For each paragraph with brackets:

1. Read the SPIRITUAL TRANSLATION for this paragraph. Understand \
   what spiritual reality is being described.
2. Read the CORRESPONDENCE PLAN for this paragraph if provided. \
   The plan tells you which natural images are CORRECT for each \
   bracket, verified by correspondential meaning. Use these images.
3. Read the SURVIVING TEXT (everything outside brackets). These are \
   your fixed anchor points \u2014 they cannot change.
4. COMPOSE a complete English sentence that:
   - Uses the natural images from the CORRESPONDENCE PLAN
   - Expresses the spiritual meaning in the Kephalaia\u2019s vocabulary
   - Uses every surviving word in its original position
   - Fills every bracket with text that creates grammatical flow
   - Reads as a REAL SENTENCE a person would write
5. Show your additions in [square brackets].
6. READ IT ALOUD. Does the sentence flow from start to finish? \
   Can you follow the thought? If not, RECOMPOSE.

### What goes wrong when you don\u2019t compose

If you fill brackets independently \u2014 one by one \u2014 and then string \
them together, you get word salad:
- "date palm [and they call the] before the tree" \u2014 incoherent
- "[instruction] the heights [from] to the heights" \u2014 broken
- "the [which wh]ich" \u2014 doubled word from glued-bracket error
- "[the reasoning-vessel of the] vessel" \u2014 doubled noun

These happen because each fill is reasonable in isolation but the \
sentence was never composed as a whole. The FIX is to write the \
whole sentence first.

### Grammatical connective tissue

Fills must supply the GRAMMATICAL GLUE that turns fragments into \
clauses: punctuation, prepositions, articles, clause boundaries. \
If your fill is only a content word ("instruction") and the result \
reads as "separation [instruction] the heights", the fill needed \
connective tissue: "separation[, he taught them about] the heights".

### After reconstructions: extract fills

Once all reconstructions are written, go through each bracket \
position and extract the fill text you placed there. This becomes \
your `fills` list. The fills are DERIVED from the reconstructions, \
not the other way around.

## HOW TO USE THE CONTEXT MARKERS

The lacunae list below shows surrounding text for each bracket:
- BEFORE: words immediately preceding the bracket
- AFTER: words immediately following the bracket
- GLUED: means text touches the bracket with NO space.

Examples:
- `[ ... ... ]ight` with GLUED-RIGHT means fill + "ight" must form a \
  word (e.g., "against the L" + "ight" = "against the Light")
- `[ ... f]rom` with GLUED-RIGHT means the surviving "f" inside the \
  bracket plus "rom" after the bracket must form a word. Your fill \
  goes BEFORE the "f". (e.g., fill "" preserves "f" = "from")
- `garm[ents]` with GLUED-LEFT means "garm" + fill must form a word

### CRITICAL: Composing with GLUED brackets

GLUED brackets represent PARTIAL WORDS. When composing your \
reconstruction, the letters outside the bracket and the letters \
inside form ONE WORD together.

#### GLUED-RIGHT (bracket touches text AFTER it)

Example: The text says `[ ... te]aching as of error`
- The word is "teaching": [te] inside + "aching" outside = teaching
- CORRECT reconstruction: "[like te]aching as of error"
- WRONG: "[teaching]aching" (DUPLICATES "aching" = "teachingaching")

Example: The text says `[ ... wh]ich Satan`
- The word is "which": [wh] inside + "ich" outside = which
- CORRECT reconstruction: "[in wh]ich Satan"
- WRONG: "[which wh]ich" (DUPLICATES "ich" = "whichich")

#### GLUED-LEFT (text touches bracket BEFORE it)

Example: The text says `the expound[er ... ] the trees`
- "expound" is fixed. Your fill STARTS with "er" or "ing" etc.
- fill = "ing of" \u2192 "expound" + "ing of" = "expounding of" (VALID)
- fill = "er of" \u2192 "expound" + "er of" = "expounder of" (VALID)
- fill = "erition" \u2192 "expound" + "erition" = "expounderition" (NOT A WORD)
- CORRECT reconstruction: "the expound[ing of] the trees"
- WRONG: "the expound[erition of] the trees" (INVENTS non-word)

Rule: The letters OUTSIDE the bracket are ALREADY THERE. Your fill \
goes INSIDE the bracket only. The result must form REAL WORDS.

### Brackets containing existing editor text

Some brackets contain text the editors already restored plus a gap: \
`[ ... I will]`. The "I will" is the editor\u2019s reading; the `...` is \
what remains unknown. Your fill REPLACES the `...` while keeping \
the editor\u2019s text. In your reconstruction, ALL of it goes between \
brackets:
- Original: `[ ... I will] reveal to you`
- If your fill is "And now": `[And now I will] reveal to you`
- WRONG: `And now I will] reveal to you` (missing opening bracket)
- WRONG: `[And now] I will reveal to you` (drops editor text from bracket)

### Bracket notation in reconstructions

Your reconstructed_text uses [square brackets] ONLY to mark where \
your additions begin and end. Every bracket must open and close \
properly. Count: each `[` must have a matching `]`. Do NOT leave \
stray ] or [ in the text.
"""


# ---------------------------------------------------------------------------
# Pre-pass system prompt: generate spiritual reading
# ---------------------------------------------------------------------------

SPIRITUAL_READING_PROMPT = """\
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

# YOUR TASK

Translate the entire chapter into one continuous piece of prose \
told entirely in the spiritual register. Proceed paragraph by \
paragraph. Every natural object must be REPLACED — not labelled.

If a paragraph does NOT yield coherent spiritual sense when \
translated — say so and put your best attempt, marking what \
is uncertain.

If your output contains quotes from the source text, \
parenthetical glosses like "(= wisdom)", or the phrase \
"corresponds to" — you have NOT translated. Start over.

Do NOT:
- Produce a generic summary
- Simply repeat the text in different words
- Label correspondences instead of translating them
- Use Jungian, Freudian, or generic "symbolic" language
- Treat correspondences as metaphors or allegories
- Add moral exhortation
- List correspondential objects and their meanings

DO:
- Replace every natural object with the spiritual reality it \
  expresses
- Produce continuous prose about spiritual states and processes
- Trace the movement of influx through the chapter
- Read this as Swedenborg would: the natural images ARE the \
  spiritual realities in ultimates — translate them back
"""


# ---------------------------------------------------------------------------
# Layer 2 system prompt: correspondence plan
# ---------------------------------------------------------------------------

CORRESPONDENCE_PLAN_PROMPT = """\
You are a CORRESPONDENCE VERIFIER. Your task is to prepare a \
CORRESPONDENCE PLAN for restoring lacunae in the Coptic Kephalaia.

You receive the original text (with brackets marking gaps) and a \
spiritual reading that translates the text into its spiritual sense. \
Your job is to determine what NATURAL IMAGE from the Kephalaia's own \
vocabulary should fill each significant bracket — by checking that \
the image's correspondential meaning MATCHES the spiritual function \
described in the reading.

# THE CORE PRINCIPLE

Every natural image has a specific spiritual meaning. Selecting the \
wrong natural image writes the wrong spiritual sentence — even if it \
sounds fluent and cosmological.

Example of the MISTAKE this layer prevents:

Text: "they walked in the [ ... ] of the world"
Spiritual reading: "they lived according to falsity"
BAD selection: "light" — because light = wisdom/truth. The resulting \
sentence would spiritually say "they lived according to truth" — the \
OPPOSITE of what the reading describes.
GOOD selection: "darkness" — because darkness = falsity/ignorance. \
"They walked in the darkness of the world" = they lived according \
to falsity. The correspondential meaning matches the spiritual \
function.

The point: a fill can sound perfectly fluent and still be \
correspondentially WRONG. Always verify the candidate image's \
spiritual meaning against what the reading says should be there.

# YOUR METHOD

For each paragraph with brackets:

1. Read the SPIRITUAL READING for this paragraph. What spiritual \
   process is being described?

2. For each SUBSTANTIAL bracket (not trivial letter fills):
   a. Identify what SPIRITUAL FUNCTION this gap serves in the \
      sentence. What does the spiritual reading say should be here?
   b. List 2-3 CANDIDATE natural images from the Kephalaia's \
      vocabulary that could plausibly fill this gap.
   c. For EACH candidate, state its CORRESPONDENTIAL MEANING:
      - Light = wisdom/truth
      - Darkness = falsity/ignorance
      - Fire = love (divine or self-love by context)
      - Water = truth in the natural degree
      - Stars = knowledges of good and truth
      - Mountains/heights = elevated spiritual states
      - Garments = external truths
      - Trees = perceptions
      - Fruits = works/deeds
      - Ships = doctrinal vessels
      - Wheel = mechanism/cycle
      - Animals/flesh = affections/desires
      - Aeons = degrees/ages
      - Five sons/members = sufficient operative powers
   d. SELECT the candidate whose correspondential meaning MATCHES \
      the spiritual function. REJECT candidates whose meaning \
      doesn't match, and explain why.

3. For TRIVIAL brackets (partial words where the reading is \
   obvious), just note "trivial — [word]".

# CROSS-REFERENCE THE TEXT

The text's OWN vocabulary often tells you the answer. If a paragraph \
discusses the bad tree's cycling mechanism, and another paragraph in \
the same chapter explicitly uses the word "transmigration" for that \
concept — USE the text's own word. Cross-reference surrounding \
paragraphs.

# OUTPUT

For each paragraph, provide:
- What it's about spiritually (from the reading)
- For each bracket: the verified natural image with reasoning

Be SPECIFIC and CONCRETE. Don't say "something related to cycling" — \
say "birth" or "fate" or "transmigration" with the specific \
correspondential reasoning.
"""


# ---------------------------------------------------------------------------
# Bracket identification
# ---------------------------------------------------------------------------

LACUNA_RE = re.compile(r"\[([^\]]*)\]")


def find_lacunae(
    core_paras: list[dict],
) -> tuple[dict[int, list[dict]], int]:
    """Identify all [bracket] spans in core paragraphs.

    Returns:
        lacunae_map: {paragraph_number: [{'index', 'content', 'original'}, ...]}
        total: total count across chapter
    """
    lacunae_map: dict[int, list[dict]] = {}
    total = 0
    for p in core_paras:
        pnum = p["paragraph_number"]
        text = p["core_text"]
        matches = list(LACUNA_RE.finditer(text))
        if matches:
            lacunae_map[pnum] = []
            for i, m in enumerate(matches, 1):
                lacunae_map[pnum].append(
                    {
                        "index": i,
                        "start": m.start(),
                        "end": m.end(),
                        "original": m.group(0),
                        "content": m.group(1),
                    }
                )
            total += len(matches)
    return lacunae_map, total


# ---------------------------------------------------------------------------
# Message construction
# ---------------------------------------------------------------------------

def build_user_message(
    core_paras: list[dict],
    lacunae_map: dict[int, list[dict]],
    total_lacunae: int,
    spiritual_reading: str | None = None,
    correspondence_plan: str | None = None,
) -> str:
    """Build user message: full chapter text + numbered lacunae list.

    If spiritual_reading is provided, it is included as correspondential
    context between the chapter text and the lacunae list.
    If correspondence_plan is provided, it is included as the verified
    mapping of brackets to correct natural images.
    """
    lines: list[str] = []
    lines.append(
        "Read the following core text correspondentially and "
        "restore all lacunae listed below.\n"
    )
    lines.append("--- CORE TEXT (oldest teaching layer) ---\n")
    for p in core_paras:
        lines.append(f"\u00b6{p['paragraph_number']}: {p['core_text']}")
        lines.append("")

    if spiritual_reading:
        lines.append(
            "\n--- SPIRITUAL TRANSLATION (correspondential context) ---\n"
        )
        lines.append(
            "The following is a translation of this chapter from its "
            "natural sense into its spiritual sense \u2014 every natural "
            "object replaced by the spiritual reality it expresses. "
            "Use this to UNDERSTAND what reality each gap describes. "
            "But your fills must be in the KEPHALAIA\u2019S OWN VOCABULARY "
            "\u2014 the natural-plane cosmological language of the text "
            "(Light, Darkness, five sons, garments, aeons, etc.), "
            "NOT in Swedenborgian spiritual vocabulary (influx, "
            "discrete degrees, faculties, etc.). Understand the "
            "spiritual sense; write the natural sense.\n"
        )
        lines.append(spiritual_reading)
        lines.append("")

    if correspondence_plan:
        lines.append(
            "\n--- CORRESPONDENCE PLAN (verified image mappings) ---\n"
        )
        lines.append(
            "The following plan maps each significant bracket to the "
            "CORRECT natural image, verified by checking that the "
            "image's correspondential meaning matches the spiritual "
            "function described in the reading. FOLLOW THIS PLAN. "
            "Use the natural images specified here in your "
            "reconstructions. Do NOT substitute different images — "
            "the plan has already verified the correspondences.\n"
        )
        lines.append(correspondence_plan)
        lines.append("")

    lines.append(f"\n--- LACUNAE ({total_lacunae} total) ---\n")
    lines.append(
        "Each bracket is shown with surrounding context. "
        "GLUED means text touches the bracket with no space — "
        "your fill must join with adjacent letters to form a word.\n"
    )

    # Build a lookup of paragraph texts for context extraction
    para_text_map = {p["paragraph_number"]: p["core_text"] for p in core_paras}

    for pnum in sorted(lacunae_map.keys()):
        text = para_text_map.get(pnum, "")
        for lac in lacunae_map[pnum]:
            start = lac["start"]
            end = lac["end"]

            # Extract surrounding context (up to 30 chars each side)
            before = text[max(0, start - 30):start]
            after = text[end:end + 30]

            # Detect glued brackets
            glued_left = (
                start > 0
                and text[start - 1] not in (" ", "\n", "(")
            )
            glued_right = (
                end < len(text)
                and text[end] not in (
                    " ", "\n", ",", ".", ";", ":", "!", "?", ")"
                )
            )

            # Build context line
            ctx_parts = []
            if before.strip():
                ctx_parts.append(f'BEFORE: "...{before.strip()}"')
            if after.strip():
                ctx_parts.append(f'AFTER: "{after.strip()[:30]}..."')

            glue_parts = []
            if glued_left:
                # Show the letters glued before the bracket
                glue_word = text[max(0, start - 15):start]
                glue_word = glue_word.split()[-1] if glue_word.split() else glue_word
                glue_parts.append(
                    f'GLUED-LEFT: "{glue_word}" touches bracket'
                )
            if glued_right:
                # Show the letters glued after the bracket
                after_chunk = text[end:end + 15]
                glue_word = after_chunk.split()[0] if after_chunk.split() else after_chunk
                glue_parts.append(
                    f'GLUED-RIGHT: bracket touches "{glue_word}" '
                    f'→ fill must join to form a word'
                )

            line = f"\u00b6{pnum} #{lac['index']}: {lac['original']}"
            if ctx_parts:
                line += f"  ({'; '.join(ctx_parts)})"
            if glue_parts:
                line += f"  !! {'; '.join(glue_parts)}"
            lines.append(line)

    lines.append("\n--- END ---")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Azure OpenAI client
# ---------------------------------------------------------------------------

def create_client() -> OpenAI:
    config = dotenv_values(SECRETS_PATH)
    return OpenAI(
        api_key=config["OPENAI_API_KEY"],
        base_url=config["OPENAI_ENDPOINT"],
    )


def get_deployment() -> str:
    config = dotenv_values(SECRETS_PATH)
    return config["OPENAI_DEPLOYMENT"]


# ---------------------------------------------------------------------------
# Pre-pass: generate correspondential spiritual reading
# ---------------------------------------------------------------------------

def generate_spiritual_reading(
    client: OpenAI,
    deployment: str,
    core_paras: list[dict],
    ch_num: int,
) -> str | None:
    """Generate a correspondential reading of the whole chapter.

    This is the pre-pass: the model reads the full chapter and produces
    a spiritual narrative — the story the text tells when each natural
    image is read through Swedenborg's correspondences. This reading
    is then fed into the restoration pass as grounding context.
    """
    # Build the chapter text for the pre-pass
    lines = ["Translate the following chapter from its natural sense "
             "into its spiritual sense.\n"]
    lines.append("--- CORE TEXT (oldest teaching layer) ---\n")
    for p in core_paras:
        lines.append(f"\u00b6{p['paragraph_number']}: {p['core_text']}")
        lines.append("")
    lines.append("--- END ---")
    user_msg = "\n".join(lines)

    max_retries = 3
    backoff = 2.0
    for attempt in range(1, max_retries + 1):
        try:
            response = client.responses.parse(
                model=deployment,
                input=[
                    {"role": "system", "content": SPIRITUAL_READING_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                text_format=SpiritualReading,
            )
            result = response.output_parsed
            if result is None:
                raise ValueError("No structured output (parsed is None)")
            return result.reading

        except RateLimitError:
            wait = 60.0
            print(
                f"  (pre-pass rate limit, retry {attempt}/{max_retries} "
                f"in {wait:.0f}s)...",
                end=" ",
                flush=True,
            )
            time.sleep(wait)

        except APIStatusError as e:
            err_str = str(e)
            if "content_filter" in err_str.lower() and attempt < max_retries:
                time.sleep(attempt * 10)
                continue
            print(f"  Pre-pass API error: {e}")
            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 2
                continue
            return None

        except Exception as e:
            err_str = str(e)
            if "content_filter" in err_str.lower() and attempt < max_retries:
                time.sleep(attempt * 10)
                continue
            print(f"  Pre-pass ERROR Ch.{ch_num}: {e}")
            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 2
                continue
            return None

    return None


# ---------------------------------------------------------------------------
# Layer 2: generate correspondence plan
# ---------------------------------------------------------------------------

def generate_correspondence_plan(
    client: OpenAI,
    deployment: str,
    core_paras: list[dict],
    lacunae_map: dict[int, list[dict]],
    spiritual_reading: str,
    ch_num: int,
) -> str | None:
    """Generate a correspondence plan for bracket restoration.

    This is Layer 2: the model receives the original text, the spiritual
    reading, and the list of brackets. It produces a per-paragraph plan
    mapping each significant bracket to the correct natural image by
    verifying its correspondential meaning against the spiritual reading.

    The plan is then fed to the restoration layer as constraint.
    """
    lines: list[str] = []
    lines.append(
        "Prepare a correspondence plan for restoring brackets in the "
        "following chapter. You receive the core text, its spiritual "
        "reading, and the list of brackets.\n"
    )
    lines.append("--- CORE TEXT (oldest teaching layer) ---\n")
    for p in core_paras:
        lines.append(f"\u00b6{p['paragraph_number']}: {p['core_text']}")
        lines.append("")

    lines.append(
        "\n--- SPIRITUAL TRANSLATION ---\n"
    )
    lines.append(spiritual_reading)

    # Build a lookup of paragraph texts for context extraction
    para_text_map = {
        p["paragraph_number"]: p["core_text"] for p in core_paras
    }

    lines.append(f"\n--- BRACKETS (paragraphs with lacunae) ---\n")
    for pnum in sorted(lacunae_map.keys()):
        text = para_text_map.get(pnum, "")
        lines.append(f"\u00b6{pnum}:")
        for lac in lacunae_map[pnum]:
            start = lac["start"]
            end = lac["end"]
            before = text[max(0, start - 40):start].strip()
            after = text[end:end + 40].strip()

            # Detect trivial (partial word with existing letters)
            content = lac["content"].strip()
            glued_right = (
                end < len(text)
                and text[end] not in (
                    " ", "\n", ",", ".", ";", ":", "!", "?", ")"
                )
            )
            glued_left = (
                start > 0
                and text[start - 1] not in (" ", "\n", "(")
            )
            is_trivial = (
                (glued_left or glued_right)
                and len(content) <= 5
                and "..." not in content
            )

            if is_trivial:
                lines.append(
                    f"  #{lac['index']}: {lac['original']} — trivial "
                    f"(partial word)"
                )
            else:
                ctx = ""
                if before:
                    ctx += f'...{before} '
                ctx += lac["original"]
                if after:
                    ctx += f' {after}...'
                lines.append(
                    f"  #{lac['index']}: {ctx}"
                )
        lines.append("")

    lines.append("--- END ---")
    user_msg = "\n".join(lines)

    max_retries = 3
    backoff = 2.0
    for attempt in range(1, max_retries + 1):
        try:
            response = client.responses.parse(
                model=deployment,
                input=[
                    {
                        "role": "system",
                        "content": CORRESPONDENCE_PLAN_PROMPT,
                    },
                    {"role": "user", "content": user_msg},
                ],
                text_format=CorrespondencePlan,
            )
            result = response.output_parsed
            if result is None:
                raise ValueError("No structured output (parsed is None)")

            # Format the plan as readable text for the fill layer
            plan_lines = []
            for pp in result.plans:
                plan_lines.append(
                    f"\u00b6{pp.paragraph}: {pp.spiritual_function}"
                )
                plan_lines.append(pp.bracket_plans)
                plan_lines.append("")
            return "\n".join(plan_lines)

        except RateLimitError:
            wait = 60.0
            print(
                f"  (plan rate limit, retry {attempt}/{max_retries} "
                f"in {wait:.0f}s)...",
                end=" ",
                flush=True,
            )
            time.sleep(wait)

        except APIStatusError as e:
            err_str = str(e)
            if "content_filter" in err_str.lower() and attempt < max_retries:
                time.sleep(attempt * 10)
                continue
            print(f"  Plan API error: {e}")
            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 2
                continue
            return None

        except Exception as e:
            err_str = str(e)
            if "content_filter" in err_str.lower() and attempt < max_retries:
                time.sleep(attempt * 10)
                continue
            print(f"  Plan ERROR Ch.{ch_num}: {e}")
            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 2
                continue
            return None

    return None


# ---------------------------------------------------------------------------
# Load extracted core chapters
# ---------------------------------------------------------------------------

def load_core_chapters() -> list[dict]:
    """Load all extracted core chapter JSON files."""
    chapters = []
    for path in sorted(CORE_CHAPTERS_DIR.glob("ch_*.json")):
        with open(path, encoding="utf-8") as f:
            chapters.append(json.load(f))
    return chapters


def load_core_chapter(ch_num: int) -> dict | None:
    path = CORE_CHAPTERS_DIR / f"ch_{ch_num:03d}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def extract_core_paragraphs(chapter: dict) -> list[dict]:
    """Extract paragraphs that have core_text from an extraction."""
    result = []
    for para in chapter.get("paragraphs", []):
        if para.get("core_text"):
            result.append(
                {
                    "paragraph_number": para["paragraph_number"],
                    "core_text": para["core_text"],
                }
            )
    return result


# ---------------------------------------------------------------------------
# Restoration via LLM
# ---------------------------------------------------------------------------

def restore_chapter(
    client: OpenAI,
    deployment: str,
    core_paras: list[dict],
    lacunae_map: dict[int, list[dict]],
    total_lacunae: int,
    ch_num: int,
    spiritual_reading: str | None = None,
    correspondence_plan: str | None = None,
) -> ChapterResult | None:
    """Send chapter to GPT-5.2 for per-lacuna restoration."""
    user_msg = build_user_message(
        core_paras, lacunae_map, total_lacunae, spiritual_reading,
        correspondence_plan,
    )

    max_retries = 3
    backoff = 2.0
    for attempt in range(1, max_retries + 1):
        try:
            response = client.responses.parse(
                model=deployment,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                text_format=ChapterResult,
            )
            result = response.output_parsed
            if result is None:
                raise ValueError("No structured output (parsed is None)")
            return result

        except RateLimitError:
            wait = 60.0
            print(
                f"  (rate limit, retry {attempt}/{max_retries} "
                f"in {wait:.0f}s)...",
                end=" ",
                flush=True,
            )
            time.sleep(wait)

        except APIStatusError as e:
            err_str = str(e)
            if "content_filter" in err_str.lower() and attempt < max_retries:
                wait = attempt * 10
                print(
                    f"  (filter, retry {attempt}/{max_retries} "
                    f"in {wait}s)...",
                    end=" ",
                    flush=True,
                )
                time.sleep(wait)
                continue
            print(f"  API error: {e}")
            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 2
                continue
            return None

        except Exception as e:
            err_str = str(e)
            if "content_filter" in err_str.lower() and attempt < max_retries:
                time.sleep(attempt * 10)
                continue
            print(f"  ERROR Ch.{ch_num}: {e}")
            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 2
                continue
            return None

    return None


# ---------------------------------------------------------------------------
# Post-processing: apply fills to original text
# ---------------------------------------------------------------------------


def fix_stray_brackets(text: str) -> str:
    """Remove unmatched brackets from reconstruction text.

    Uses a stack to identify properly-paired ``[…]`` and removes any
    stray ``]`` (no preceding ``[``) or ``[`` (no following ``]``).
    Preserves correctly-bracketed scholarly markers while cleaning up
    the occasional model notation error.
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
    """Replace [bracket] spans in text with model fills.

    Operates right-to-left to preserve character positions.
    Only touches square brackets -- page markers (angle brackets) and
    text outside brackets are never altered.
    """
    matches = list(LACUNA_RE.finditer(text))
    if not matches:
        return text

    fill_by_idx = {f["index"]: f["fill"] for f in fills}

    # Replace right-to-left to preserve positions
    result = text
    for i in range(len(matches), 0, -1):
        m = matches[i - 1]
        if i in fill_by_idx:
            result = result[: m.start()] + f"[{fill_by_idx[i]}]" + result[m.end() :]

    return result


# ---------------------------------------------------------------------------
# Save / Load
# ---------------------------------------------------------------------------

def save_result(
    ch_num: int,
    title: str,
    result: ChapterResult,
    lacunae_map: dict[int, list[dict]],
    total_lacunae: int,
    spiritual_reading: str | None = None,
    correspondence_plan: str | None = None,
) -> None:
    CHAPTERS_OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = CHAPTERS_OUT_DIR / f"ch_{ch_num:03d}.json"

    # Serialise lacunae_map with string keys for JSON
    lacunae_serial = {str(k): v for k, v in lacunae_map.items()}

    data = {
        "chapter_number": ch_num,
        "chapter_title": title,
        "total_lacunae": total_lacunae,
        "lacunae_map": lacunae_serial,
        "spiritual_reading": spiritual_reading,
        "correspondence_plan": correspondence_plan,
        **result.model_dump(),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_result(ch_num: int) -> dict | None:
    path = CHAPTERS_OUT_DIR / f"ch_{ch_num:03d}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def is_done(ch_num: int) -> bool:
    return (CHAPTERS_OUT_DIR / f"ch_{ch_num:03d}.json").exists()


# ---------------------------------------------------------------------------
# Assembly: build the restored document
# ---------------------------------------------------------------------------

def assemble_restored(core_chapters: dict[int, dict]) -> str:
    """Assemble all restorations into a continuous restored document.

    For each chapter, outputs all core paragraphs with fills applied.
    Notes are shown for fills that have non-empty notes (i.e. where
    correspondential reasoning was applied, not trivial letter fills).
    """
    # Load all restoration files
    restorations_by_ch: dict[int, dict] = {}
    for path in sorted(CHAPTERS_OUT_DIR.glob("ch_*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            restorations_by_ch[data["chapter_number"]] = data

    if not restorations_by_ch:
        print("ERROR: No restoration files found.")
        return ""

    lines: list[str] = []
    lines.append("# The Kephalaia Teaching Core \u2014 Restored Text")
    lines.append("")
    lines.append("*The oldest teaching layer of the Kephalaia with lacunae*")
    lines.append("*restored using correspondential constraints. All editorial*")
    lines.append("*content appears in [square brackets]. Unrestorable gaps*")
    lines.append("*remain as [...]*")
    lines.append("")
    lines.append("---")
    lines.append("")

    total_fills = 0
    total_unrestorable = 0

    for ch_num in sorted(
        set(list(core_chapters.keys()) + list(restorations_by_ch.keys()))
    ):
        core_ch = core_chapters.get(ch_num)
        rest_ch = restorations_by_ch.get(ch_num)

        if not core_ch:
            continue

        title = core_ch.get("chapter_title", f"Chapter {ch_num}")
        lines.append(f"## Chapter {ch_num}: {title}")
        lines.append("")

        # Build fill lookup: {paragraph_num: [fill_dicts]}
        fills_by_para: dict[int, list[dict]] = {}
        recon_by_para: dict[int, str] = {}
        if rest_ch:
            for fill in rest_ch.get("fills", []):
                para = fill["paragraph"]
                if para not in fills_by_para:
                    fills_by_para[para] = []
                fills_by_para[para].append(fill)
            # Prefer model's reconstructed paragraphs when available
            for recon in rest_ch.get("reconstructions", []):
                recon_by_para[recon["paragraph"]] = recon["reconstructed_text"]

        # Process each paragraph
        for para in core_ch.get("paragraphs", []):
            pnum = para["paragraph_number"]
            core_text = para.get("core_text")
            if not core_text:
                continue

            para_fills = fills_by_para.get(pnum)
            if para_fills:
                # Prefer model's reconstructed text (coherent prose)
                # Fall back to mechanical fill insertion
                if pnum in recon_by_para:
                    restored = fix_stray_brackets(recon_by_para[pnum])
                else:
                    restored = fix_stray_brackets(
                        apply_fills_to_paragraph(core_text, para_fills)
                    )
                lines.append(f"**\u00b6{pnum}** {restored}")
                lines.append("")

                # Collect notes for non-trivial fills
                interesting = [
                    f for f in para_fills if f.get("notes", "").strip()
                ]
                if interesting:
                    for f in interesting:
                        conf = f.get("confidence", "")
                        notes = f["notes"]
                        lines.append(
                            f"> *\u00b6{pnum} #{f['index']} [{conf}]:* {notes}"
                        )
                    lines.append("")

                # Count fills vs unrestorable
                for f in para_fills:
                    if f.get("fill", "...").strip() == "...":
                        total_unrestorable += 1
                    else:
                        total_fills += 1
            else:
                # No lacunae -- original text as-is
                lines.append(f"**\u00b6{pnum}** {core_text}")
                lines.append("")

        # Chapter assessment
        if rest_ch:
            assessment = rest_ch.get("assessment", "")
            if assessment:
                lines.append(f"**Assessment:** {fix_stray_brackets(assessment)}")
                lines.append("")

        lines.append("---")
        lines.append("")

    # Prepend statistics
    stats_block = [
        f"**Lacunae filled**: {total_fills}",
        f"**Unrestorable**: {total_unrestorable}",
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
    print(f"  Saved restored text to {ASSEMBLED_FILE}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Correspondential restoration of the Kephalaia "
        "teaching core"
    )
    parser.add_argument(
        "--chapter",
        "-c",
        type=int,
        default=None,
        help="Process a single chapter",
    )
    parser.add_argument(
        "--range",
        "-r",
        type=str,
        default=None,
        help="Process a range of chapters (e.g., '38-55')",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=None,
        help="Process only first N chapters",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Preview without API calls",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Reprocess existing restorations",
    )
    parser.add_argument(
        "--assemble",
        "-a",
        action="store_true",
        help="Skip restoration, assemble existing only",
    )
    parser.add_argument(
        "--concurrency",
        "-j",
        type=int,
        default=1,
        help="Number of chapters to process in parallel (default: 1)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Load extracted core chapters
    all_chapters = load_core_chapters()
    if not all_chapters:
        print("ERROR: No extracted core chapters found in", CORE_CHAPTERS_DIR)
        print("  Run extract_core.py first.")
        sys.exit(1)

    core_by_num = {ch["chapter_number"]: ch for ch in all_chapters}
    print(f"Found {len(all_chapters)} extracted core chapters")

    # Assembly-only mode
    if args.assemble:
        print("Assembling restored text from existing results...")
        text = assemble_restored(core_by_num)
        if text:
            save_assembly(text)
        return

    # Determine which to process
    if args.chapter is not None:
        chapters = [
            ch for ch in all_chapters if ch["chapter_number"] == args.chapter
        ]
        if not chapters:
            print(f"ERROR: Chapter {args.chapter} not found in extractions")
            sys.exit(1)
    elif args.range:
        m = re.match(r"(\d+)-(\d+)", args.range)
        if not m:
            print("ERROR: Invalid range. Use '38-55'")
            sys.exit(1)
        start, end = int(m.group(1)), int(m.group(2))
        chapters = [
            ch
            for ch in all_chapters
            if start <= ch["chapter_number"] <= end
        ]
    else:
        chapters = all_chapters

    if args.limit:
        chapters = chapters[: args.limit]

    # Skip already processed
    if not args.overwrite:
        to_process = [
            ch for ch in chapters if not is_done(ch["chapter_number"])
        ]
        skipped = len(chapters) - len(to_process)
        if skipped > 0:
            print(
                f"  Skipping {skipped} already-done chapters "
                f"(use --overwrite)"
            )
        chapters = to_process

    if not chapters:
        print("All chapters already processed.")
        text = assemble_restored(core_by_num)
        if text:
            save_assembly(text)
        return

    # Preview
    print(f"\nProcessing {len(chapters)} chapters:")
    for ch in chapters:
        num = ch["chapter_number"]
        title = ch.get("chapter_title", "")[:60]
        core_paras = extract_core_paragraphs(ch)
        _, n_lacunae = find_lacunae(core_paras)
        print(
            f"  Ch.{num:3d}  ({len(core_paras):3d} core \u00b6s, "
            f"{n_lacunae} lacunae)  {title}"
        )

    if args.dry_run:
        print("\n[DRY RUN] No API calls made.")
        return

    # Create client
    client = create_client()
    deployment = get_deployment()
    concurrency = max(1, args.concurrency)
    print(f"\nUsing deployment: {deployment}")
    print(f"Concurrency: {concurrency}")
    print()

    # Process
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CHAPTERS_OUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- Worker function for one chapter ---
    print_lock = threading.Lock()
    results_list: list[int] = []
    errors_list: list[int] = []
    counter = {"done": 0}
    total_to_process = len(chapters)

    def process_one(ch: dict) -> None:
        ch_num = ch["chapter_number"]
        title = ch.get("chapter_title", "")[:50]

        # Pre-process: identify lacunae
        core_paras = extract_core_paragraphs(ch)
        lacunae_map, total_lacunae = find_lacunae(core_paras)

        if total_lacunae == 0:
            with print_lock:
                counter["done"] += 1
                print(
                    f"[{counter['done']}/{total_to_process}] "
                    f"Ch.{ch_num} \u2014 no lacunae, skip"
                )
            return

        with print_lock:
            print(
                f"  Ch.{ch_num} ({total_lacunae} lacunae) "
                f"{title}... reading...",
                flush=True,
            )

        # --- PRE-PASS: generate spiritual reading ---
        spiritual_reading = generate_spiritual_reading(
            client, deployment, core_paras, ch_num,
        )

        with print_lock:
            sr_info = (
                f"({len(spiritual_reading)} chars)"
                if spiritual_reading
                else "(pre-pass failed)"
            )
            print(
                f"  Ch.{ch_num} {sr_info} planning...",
                flush=True,
            )

        # --- LAYER 2: generate correspondence plan ---
        correspondence_plan = None
        if spiritual_reading:
            correspondence_plan = generate_correspondence_plan(
                client, deployment, core_paras, lacunae_map,
                spiritual_reading, ch_num,
            )

        with print_lock:
            plan_info = (
                f"({len(correspondence_plan)} chars)"
                if correspondence_plan
                else "(plan skipped)"
            )
            print(
                f"  Ch.{ch_num} plan {plan_info} filling...",
                flush=True,
            )

        # --- LAYER 3: RESTORATION PASS ---
        result = restore_chapter(
            client, deployment, core_paras, lacunae_map,
            total_lacunae, ch_num,
            spiritual_reading=spiritual_reading,
            correspondence_plan=correspondence_plan,
        )
        if result is None:
            with print_lock:
                counter["done"] += 1
                errors_list.append(ch_num)
                print(
                    f"[{counter['done']}/{total_to_process}] "
                    f"Ch.{ch_num} FAILED"
                )
            return

        # Validate
        expected = set()
        for pnum, lacs in lacunae_map.items():
            for lac in lacs:
                expected.add((pnum, lac["index"]))
        received = {(f.paragraph, f.index) for f in result.fills}
        missing = expected - received
        n_filled = sum(1 for f in result.fills if f.fill.strip() != "...")
        n_unrest = sum(1 for f in result.fills if f.fill.strip() == "...")

        save_result(
            ch_num, title, result, lacunae_map, total_lacunae,
            spiritual_reading=spiritual_reading,
            correspondence_plan=correspondence_plan,
        )

        status = f"OK \u2014 {n_filled} filled, {n_unrest} unrestorable"
        if missing:
            status += f", {len(missing)} MISSING"

        with print_lock:
            counter["done"] += 1
            results_list.append(ch_num)
            print(
                f"[{counter['done']}/{total_to_process}] "
                f"Ch.{ch_num} {status}"
            )

    # --- Run with thread pool ---
    if concurrency == 1:
        for ch in chapters:
            process_one(ch)
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {
                executor.submit(process_one, ch): ch
                for ch in chapters
            }
            for future in as_completed(futures):
                exc = future.exception()
                if exc:
                    ch = futures[future]
                    with print_lock:
                        print(
                            f"  Ch.{ch['chapter_number']} "
                            f"EXCEPTION: {exc}"
                        )
                        errors_list.append(ch["chapter_number"])

    # Summary
    print(f"\n{'='*60}")
    print("RESTORATION COMPLETE")
    print(f"  Processed: {len(results_list)}")
    print(f"  Errors: {len(errors_list)}")
    if errors_list:
        print(f"  Failed: {sorted(errors_list)}")

    # Assemble
    print("\nAssembling restored document...")
    text = assemble_restored(core_by_num)
    if text:
        save_assembly(text)

    print("Done.")


if __name__ == "__main__":
    main()
