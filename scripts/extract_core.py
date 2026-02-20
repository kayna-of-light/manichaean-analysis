#!/usr/bin/env python3
"""
Extract the core teaching layer from the Kephalaia of the Teacher.

This script performs textual criticism to recover the oldest teaching layer
from the composite Kephalaia text. It does NOT impose any narrative scheme
or reorganize content. It works chapter by chapter in textual order:

  1. Loads pre-computed text-critical analysis (vocabulary scores, seam flags)
     produced by extract_analysis.py
  2. Sends the chapter to Claude Opus 4.6 WITH the analysis data as guidance
  3. The LLM classifies each paragraph as CORE / FRAME / PASTORAL / OVERLAY / MIXED
  4. For MIXED paragraphs, the LLM extracts the core teaching and notes what was removed
  5. The result preserves textual order — chapter by chapter, paragraph by paragraph

The "core" is not defined thematically. It is defined temporally:
  - CORE: Teaching content that predates the editorial compilation.
    This includes correspondential maps, cosmological narrative, body-universe
    systems, five-fold degree structures, named cosmic beings AND their
    correspondential descriptions — all of it. The distinction is not between
    "correspondential" and "cosmological" — the distinction is between OLD
    TEACHING and LATER ADDITIONS.
  - FRAME: Hagiographic editorial apparatus added by the compiling community.
    Q&A formulas, closing praise, biographical claims about Mani.
  - PASTORAL: Church institutional material — fasting rules, alms, catechumen
    instruction, behavioral ethics without cosmological grounding.
  - OVERLAY: Explicit NT/Christian additions — Gospel citations, Pauline
    vocabulary used devotionally, Christian titles in non-cosmic contexts.
  - MIXED: Paragraphs where core and later material are interwoven.
    The LLM extracts the core and notes removals.

Primary model: Claude Opus 4.6 via Azure AI Foundry (AnthropicFoundry).

Output: output/core/
  - ch_NNN.json         Per-chapter extraction results
  - restored_core.md    The assembled core text in chapter order
  - core_data.json      Summary statistics

Usage:
    python scripts/extract_core.py                     # Process all chapters
    python scripts/extract_core.py --chapter 38        # Single chapter
    python scripts/extract_core.py --range 0-20        # Range of chapters
    python scripts/extract_core.py --dry-run            # Preview without API calls
    python scripts/extract_core.py --overwrite          # Reprocess existing
    python scripts/extract_core.py --assemble           # Skip extraction, assemble only
    python scripts/extract_core.py --limit 5            # First N chapters only
    python scripts/extract_core.py --max-concurrency 4  # 4 parallel API calls
"""
import argparse
import json
import re
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

import httpx
from anthropic import AnthropicFoundry
from dotenv import dotenv_values

from extract_analysis import (
    load_corpus_metadata,
    split_paragraphs,
    load_analysis,
)
from project_config import load_project, list_projects, SECRETS_PATH

# ---------------------------------------------------------------------------
# Paths — set by configure_paths() at startup
# ---------------------------------------------------------------------------

PROJECT_CFG = None                 # ProjectConfig — set by configure_paths()
CHAPTERS_DIR: Path | None = None   # input: cleaned chapters
OUTPUT_DIR: Path | None = None     # output: core/
SEGMENTS_DIR: Path | None = None   # output: core/chapters/
ASSEMBLED_FILE: Path | None = None # output: restored_core.md
DATA_FILE: Path | None = None      # output: core_data.json


def configure_paths(project_name: str) -> None:
    """Set module-level path variables from project config."""
    global PROJECT_CFG
    global CHAPTERS_DIR
    global OUTPUT_DIR, SEGMENTS_DIR, ASSEMBLED_FILE, DATA_FILE

    cfg = load_project(project_name)
    cfg.paths.ensure_dirs()
    PROJECT_CFG = cfg

    CHAPTERS_DIR = cfg.paths.cleaned_chapters
    OUTPUT_DIR = cfg.paths.core
    SEGMENTS_DIR = cfg.paths.core_chapters
    ASSEMBLED_FILE = cfg.paths.core_assembled
    DATA_FILE = cfg.paths.core_data

    print(f"Project: {cfg.display_name}")
    print(f"  Type:   {cfg.document_type}")
    print(f"  Input:  {CHAPTERS_DIR}")
    print(f"  Output: {OUTPUT_DIR}")


# ---------------------------------------------------------------------------
# Field accessors — handle both chapter-based and section-based formats
# ---------------------------------------------------------------------------

def get_number(chapter: dict) -> int:
    """Get the chapter/section number from a cleaned chapter dict."""
    return chapter.get("chapter_number") or chapter.get("section_number", 0)


def get_text(chapter: dict) -> str:
    """Get the main teaching/translation text from a cleaned chapter dict."""
    return chapter.get("teaching_text") or chapter.get("english_translation", "")


def get_title(chapter: dict) -> str:
    """Get the chapter/section title."""
    num = get_number(chapter)
    return chapter.get("title", f"Section {num}")


# ---------------------------------------------------------------------------
# Tool definition — replaces Pydantic structured output
# ---------------------------------------------------------------------------

EXTRACT_CORE_TOOL = {
    "name": "commit_extraction",
    "description": (
        "Commit the complete core extraction for this chapter. "
        "Call this exactly once with all paragraph classifications."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "chapter_number": {
                "type": "integer",
                "description": "The chapter number.",
            },
            "chapter_title": {
                "type": "string",
                "description": "The chapter title.",
            },
            "total_paragraphs": {
                "type": "integer",
                "description": "Total paragraphs in the chapter.",
            },
            "core_paragraphs": {
                "type": "integer",
                "description": (
                    "Count of CORE + MIXED paragraphs "
                    "(those with extracted core_text)."
                ),
            },
            "core_percentage": {
                "type": "number",
                "description": (
                    "Estimated % of teaching text word count "
                    "that is core (0-100)."
                ),
            },
            "chapter_note": {
                "type": "string",
                "description": (
                    "Brief assessment of this chapter. Is the core "
                    "teaching dominant? Is the chapter mostly "
                    "frame/pastoral with embedded fragments? "
                    "Note any distinctive features."
                ),
            },
            "paragraphs": {
                "type": "array",
                "description": "Classification for each paragraph.",
                "items": {
                    "type": "object",
                    "properties": {
                        "paragraph_number": {
                            "type": "integer",
                            "description": (
                                "Which paragraph (1-indexed, matching "
                                "the register analysis)."
                            ),
                        },
                        "classification": {
                            "type": "string",
                            "enum": [
                                "core",
                                "frame",
                                "pastoral",
                                "overlay",
                                "mixed",
                            ],
                            "description": (
                                "Classify by TEMPORAL LAYER — when did "
                                "this language enter this text? "
                                "CORE: Oldest teaching layer — systematic "
                                "cosmological-correspondential teaching. "
                                "FRAME: Hagiographic editorial apparatus. "
                                "PASTORAL: Church institutional material. "
                                "OVERLAY: Material entering via NT/Gospels. "
                                "MIXED: Core interwoven with later material."
                            ),
                        },
                        "core_text": {
                            "type": ["string", "null"],
                            "description": (
                                "For CORE: the paragraph text verbatim. "
                                "For MIXED: extracted old teaching only. "
                                "For FRAME/PASTORAL/OVERLAY: null. "
                                "Preserve lacunae [...] and restorations. "
                                "Capitalize personified cosmic entities "
                                "(Sin, Darkness) when they function as agents."
                            ),
                        },
                        "removed_material": {
                            "type": ["string", "null"],
                            "description": (
                                "For MIXED only: what was removed and why. "
                                "Null for non-MIXED."
                            ),
                        },
                        "temporal_note": {
                            "type": ["string", "null"],
                            "description": (
                                "Brief observation about temporal layer. "
                                "What markers, patterns, or register shifts "
                                "do you observe? Be honest about uncertainty."
                            ),
                        },
                    },
                    "required": [
                        "paragraph_number",
                        "classification",
                        "core_text",
                        "removed_material",
                        "temporal_note",
                    ],
                },
            },
        },
        "required": [
            "chapter_number",
            "chapter_title",
            "total_paragraphs",
            "core_paragraphs",
            "core_percentage",
            "chapter_note",
            "paragraphs",
        ],
    },
}


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert in the correspondential tradition — the ancient science of \
describing spiritual realities through their natural expressions. You have \
deep knowledge of Swedenborg's doctrine of correspondences, the Persian and \
Zoroastrian cosmological traditions, Manichaean cosmology, and the textual \
transmission of what Swedenborg called "the Ancient Word" — the oldest \
correspondential writing, preserved in the East, which predates national \
mythologies and scriptural canons.

You are working on the Coptic Kephalaia of the Teacher — a Manichaean \
composite text compiled in the 3rd-4th century CE. This text contains \
multiple temporal layers, and your task is to identify the OLDEST TEACHING \
SUBSTRATE and separate it from later editorial additions.

## WHAT MAKES THE SUBSTRATE THE SUBSTRATE

The correspondential substrate has a distinctive quality: **both sides of \
every mapping stay within the cosmic system**. It maps domain onto domain, \
being onto being, degree onto degree — and never reaches outside the system.

Consider this sequence from the five-worlds teaching:
- "The King of the worlds of Wind is eagle-face" — realm → zoomorphic form
- "His body is iron" — realm → metal correspondence
- "Their taste is the sharp taste that is in every form" — realm → sensory \
  quality

Every element maps WITHIN the system. Face, metal, taste — these are \
correspondential registers. The teaching IS the mapping. It does not point \
to anything outside the cosmic architecture.

Now compare:
- "His spirit is the one of idolatry to the spirits of error who are in \
  every temple, the sites of idols, the sites of statue- and image-worship"

This LOOKS similar — "His spirit is the one of..." has the same syntax as \
"His body is iron." But one side of the mapping now reaches OUTSIDE the \
cosmic system into the editor's contemporary world. "Every temple", "sites \
of idols", "statue- and image-worship" are not cosmic registers — they are \
specific religious institutions that the editor is identifying. The \
correspondence is being USED to point at something in the editorial present.

**This is the critical diagnostic.** The substrate maps cosmos→cosmos. The \
editorial layer maps cosmos→contemporary world. When one side of a mapping \
identifies specific institutions, social structures, religious practices, \
or contemporary persons — the correspondence has crossed from BEING to \
POINTING AT.

More examples of this boundary:

BEING (substrate — both sides internal to the system):
- "The King of Darkness wounds and kills by the word of his magic arts" — \
  describes what his second faculty IS within the degree structure
- "Gold is the body of the King of the realms of Darkness" — maps realm → \
  metal
- "The body of all the powers who belong to the world of Smoke is gold" — \
  maps cosmic hierarchy → metal correspondence
- "Their taste is the bitter taste" — maps realm → sensory quality

POINTING AT (editorial — one side reaches into the contemporary world):
- "The spirit... reigns today in the principalities and the authorities" — \
  "principalities and authorities" are contemporary power structures
- "His spirit is the one of idolatry... in every temple" — "every temple" \
  is the editor's religious landscape
- "The spirit who speaks till today in the soothsayers" — "soothsayers" \
  are contemporary practitioners the editor recognizes
- "These enchantments nowadays, which people utilise in this world" — \
  "nowadays" and "this world" explicitly anchor to editorial present
- "I command you, keep away from magic arts" — pivots to audience address
- "Concerning this I tell you, my brethren" — pivots to audience address
- "Become good pearls" — pivots to exhortation

The boundary often falls MID-PARAGRAPH. A paragraph may open with \
substrate (describing what a cosmic king IS — face, body, metal, taste) \
and then pivot to application (identifying that king's spirit in \
contemporary institutions). The substrate portion maps cosmos→cosmos. \
The application portion maps cosmos→the editor's world. Find where the \
second side of the mapping leaves the cosmic system — that is where you cut.

This distinction is the PRIMARY diagnostic. Temporal vocabulary, editorial \
seams, citation formulas, application voice scores — these are all \
secondary signals that help you find the boundary. But the boundary itself \
is structural: does Mapping Side B stay within the cosmic system, or does \
it reach into the contemporary world?

## THE PERSIAN DIALOGUE TRADITION AND OPENING PARAGRAPHS

CRITICAL: The Q&A format of the Kephalaia — structured questions about \
cosmological topics followed by systematic teaching — is NOT a Manichaean \
invention. This is the PERSIAN PEDAGOGICAL TRADITION. The dialogue format \
itself is substratic. Mani APPROPRIATED this tradition and added his own \
attribution machinery ("Once again the enlightener speaks to his disciples").

This means: when an opening paragraph contains a SUBSTANTIVE COSMOLOGICAL \
QUESTION — "Tell us about the five storehouses", "What are the three \
wheels?", "How does the mixture come about?" — the QUESTION ITSELF is \
core. It reveals the teaching structure. It IS the substrate. The question \
defines what the teaching sequence will map.

Only classify opening paragraphs as FRAME when they contain PURELY \
FORMULAIC attribution with NO cosmological content:
- "Once again the enlightener speaks to his disciples" → FRAME (pure formula)
- "We beseech you, our master, that you may recount to us" → FRAME (pure honorific)

But:
- "Tell us about the five limbs of the Father of Greatness" → CORE \
  (substantive cosmological question — it defines the teaching topic)
- "We beseech you that you tell us about the three wheels and the \
  five storehouses" → MIXED (strip "We beseech you that you tell us", \
  keep "about the three wheels and the five storehouses")

When a frame formula introduces a substantive question, classify as \
MIXED and extract the substantive content. Do NOT discard cosmological \
questions just because they are wrapped in frame formulas.

## ENUMERATION INTEGRITY

When the substrate teaches through NUMBERED LISTS — "The first is...", \
"The second is...", "The third is..." — the enumeration markers are \
PART OF the substrate. They are the STRUCTURE of the teaching, not \
decoration.

If a paragraph begins with an enumeration marker ("The second is error", \
"The third is desire") and continues with cosmological-correspondential \
description, the ENTIRE enumeration unit is CORE. Do NOT strip the \
enumeration marker from a mixed paragraph. If you must extract from a \
mixed paragraph that contains enumeration, preserve the full "The Nth \
is [term]" structure in core_text.

## COMPUTATIONAL TEXT-CRITICAL DATA: HOW TO USE IT

You will receive vocabulary density scores and structural flags generated \
by a computational NLP pipeline. These are GUIDES, not determinations. \
They flag patterns for your attention. You make the actual classification \
by reading the text.

The vocabulary pipeline scores paragraphs against multiple temporal-layer \
vocabularies identified by a corpus-level metadata analysis. Each layer \
has a curated vocabulary of diagnostic terms and weights. The scores tell \
you WHAT VOCABULARY IS PRESENT — not WHEN it entered the text.

When a scoring category fires strongly, the text is likely associated \
with that temporal layer — but READ THE ACTUAL TEXT to confirm. \
Imperative/exhortation language often marks the substrate→application \
boundary.

The reliability hierarchy of computational signals:
1. **Seam flags** — Strongest. Detect structural patterns (bridge \
   connective + institutional vocabulary + register shift from preceding \
   paragraphs).
2. **Editorial fatigue** — Strong. Drift from older to later layers \
   across the chapter. Classic scribal pattern.
3. **Register score shifts** — Moderate. Flags vocabulary density changes \
   that often mark layer boundaries.
4. **Gardner flags** — Strong. From the scholarly edition's critical \
   apparatus.
5. **Register scores** — Weakest. Raw vocabulary counts. A paragraph \
   full of cosmological vocabulary might still be late imitation. A \
   paragraph with pastoral vocabulary might contain old teaching wrapped \
   in editorial framing.

These signals help you FIND the layer boundary. YOUR reading of the text — \
specifically, "does this describe what things ARE, or does it apply the \
teaching to an audience/situation?" — determines WHERE the boundary falls.

## THE FUNDAMENTAL PRINCIPLE: TEMPORAL DISCRIMINATION

The question is NOT "does this contain correspondence?" or "does this contain \
teaching?" The question is: **WHEN did this language enter this text?**

Correspondence is a way of writing. Jesus spoke in correspondence. The Psalms \
use correspondence. The Persian cosmological tradition used correspondence. \
The presence of correspondential content tells you NOTHING about age. What \
tells you about age is the VEHICLE:

- A five-fold degree map systematically correlating cosmic beings with body \
  parts and intellectual faculties → OLD (pre-compilation teaching)
- "As it is written in the Gospel, he says: The good tree shall give good \
  fruit" → LATE (enters via the NT, regardless that the parable itself uses \
  correspondence)
- "Once again the enlightener speaks to his disciples" → LATE (hagiographic \
  frame)
- "The catechumens shall give alms at the feast" → LATE (institutional rule)

The parable of the two trees IS correspondential. But it entered this text \
via a Gospel citation. That citation is a 3rd-century Manichaean editorial \
act, not a pre-Mani teaching tradition. The CONTENT may be ancient (Jesus \
was drawing on ancient patterns). The CITATION is late.

## THE TEXT'S COMPOSITION HISTORY

The Kephalaia is a composite document. Multiple hands and periods contributed:

1. **THE TEACHING CORE** (what we are recovering):
   The oldest layer. Systematic cosmological-correspondential teaching that \
   predates the editorial compilation. Characteristics:
   - Numbered degree structures (five limbs, three wheels, twelve zodiac)
   - Systematic mapping: one domain onto another (cosmic being ↔ body part \
     ↔ intellectual faculty ↔ eschatological station)
   - Named cosmic beings in SYSTEMATIC exposition (not narrative anecdote)
   - Light-dark mechanics described as process, not moral exhortation
   - Impersonal, structural voice — "how things work"
   - Persian/Iranian cosmological naming (First Man, Living Spirit, Mother \
     of Life, Father of Greatness, Third Ambassador, Virgin of Light)
   - The teaching does NOT cite authorities. It expounds directly.
   NOTE: "Jesus the Splendour" in COSMIC contexts (as a specific being in \
   the cosmological hierarchy with defined function) is CORE — this is a \
   named cosmic entity, not a Gospel reference.

2. **THE HAGIOGRAPHIC FRAME** (later — editorial):
   Added by the community that compiled the Kephalaia as a book:
   - Opening: "Once again the enlightener speaks to his disciples..."
   - Questions: "We beseech you, our master, that you may recount..."
   - Closing: "When they heard these things, they rejoiced and glorified..."
   - Biographical: "Not one among the apostles did ever do these things"
   - Titles: "our master Manichaios, the apostle of greatness"
   These wrap the teaching. Container, not content.

3. **THE PASTORAL LAYER** (later — institutional):
   Church operational material:
   - Fasting rules, alms, tithe, catechumen/elect institutional categories
   - Behavioral ethics without cosmological mechanism
   - Prescriptive, second-person instruction voice

4. **THE CHRISTIAN OVERLAY** (Mani's synthesis + later editors):
   Material that entered the Kephalaia VIA the New Testament:
   - **Gospel citations**: "As it is written in the Gospel, he says..." — \
     even when the cited saying is correspondential (the two trees, the \
     mustard seed, etc). Jesus spoke in correspondence, but CITING Jesus \
     from the Gospels is a post-Gospel act.
   - **NT narrative exempla**: Judas stories, Paul's conversion, apostolic \
     biography — these reference specific NT episodes.
   - **Citation formulas**: "the saviour preached", "as the saviour said"
   - **Pauline vocabulary** in devotional (non-cosmic) contexts
   - **The test**: If you removed the NT from existence, would this \
     language still be here? If no → OVERLAY.

## EDITORIAL SEAM DETECTION — CRITICAL

An EDITORIAL SEAM is where an editor extends an existing teaching sequence \
by mimicking its syntactic pattern but introducing institutional content. \
This is the most subtle form of editorial addition because the seam LOOKS \
like a continuation of the teaching.

### The Pattern Mimicry Problem

Consider a four-fold cosmological teaching:
  ¶5: "Happiness, wisdom and power exist in [the Father/land of light]"
  ¶6: "[these three exist in] the sun/ship of fire"
  ¶7: "Again, these three exist in the ship of living waters"
  ¶8: "Again, these three exist in the elements"

An editor who sees this pattern can extend it:
  ¶9: "Now, moreover, happiness, wisdom and power exist in the holy church."

The editor has NOT TOUCHED the core teaching. They have EXTENDED the list \
by adding one more iteration — but applying the pattern to their own \
institution instead of to a cosmic domain. The bridge phrase "Now, moreover" \
IS the editorial seam.

### How to Detect Editorial Seams

1. **Bridge connectives**: "Now, moreover" / "Furthermore" / "And moreover" \
   at the START of a paragraph, especially when:
   - The preceding paragraphs contain systematic cosmological iterations
   - The new paragraph applies the pattern to church/institution/community

2. **Register shift at the connection point**: The preceding paragraphs \
   have high cosmological vocabulary (cosmic beings, cosmic geography); the \
   new paragraph has high institutional vocabulary (holy church, elect, \
   catechumens, apostle of light, leaders, teachers, mission).

3. **Position**: Editorial additions tend to come AFTER the teaching \
   sequence (extending the list) or AT THE END of a chapter (editorial \
   fatigue — adding pastoral material after the core is complete).

4. **The critical question**: If you removed this paragraph, would the \
   preceding teaching sequence be COMPLETE IN ITSELF? If yes — if the \
   cosmic domains were mapped and the structure was closed — then this \
   extension is editorial.

### What This Means for Classification

When a paragraph mimics the core teaching pattern but applies it to \
institutional content, the ENTIRE paragraph is PASTORAL — not MIXED. \
Do NOT extract the opening clause as "core_text" just because it uses \
the same syntax. The opening clause IS PART OF the editorial extension. \
"Now, moreover, X exist in the holy church" is ONE editorial act — the \
bridge phrase and the institutional identification were written by the \
same hand at the same time.

## TEXT-CRITICAL ANALYTICAL DATA

### CRITICAL: How these scores are produced

The analytical data you receive is generated by a SIMPLE NLP PIPELINE — \
basically vocabulary frequency counting. It works like this:

1. **Vocabulary lists** were identified by a corpus-level metadata analysis \
   for each temporal layer.
2. **Density scores** count how often words from each list appear per 100 \
   words of text.
3. **Per-layer scores** show which vocabulary categories are active in each \
   paragraph.

This means the scores measure WHAT VOCABULARY IS PRESENT. They cannot \
determine WHEN that vocabulary entered the text. A paragraph full of \
pastoral vocabulary might be genuinely late — or it might be old teaching \
that an editor has wrapped in institutional language. The vocabulary \
counter cannot tell the difference. Only YOU can, by reading the actual \
text.

**YOUR reading of the text is PRIMARY. The scores are guides, not truth.** \
Specifically:
- A high score for any layer does NOT mean "classify as that layer." It means \
  that layer's vocabulary is present — investigate whether the classification \
  matches.
- The scores are MOST reliable for detecting editorial fatigue patterns \
  (drift across chapter halves) and for flagging editorial seams \
  (bridge connective + register shift). These structural patterns are \
  harder to fake than raw vocabulary presence.

### Chapter-level features:
- **Teaching purity**: Ratio of teaching vocabulary to total vocabulary \
  density. Higher = less overlay vocabulary.
- **Editorial fatigue score**: Measures pastoral drift from first to second \
  half of the chapter. Positive values mean pastoral vocabulary increases \
  in the second half — a classic editorial fatigue pattern.
- **Structure**: Whether formulaic opening/closing are detected.
- **Citations**: NT/OT citations found in the scholarly footnotes.
- **Gardner flags**: Editorial observations from the critical apparatus.

### Paragraph-level features:
- **Register scores**: Vocabulary density per 100 words for each scoring \
  category identified by the metadata analysis. These are RAW VOCABULARY COUNTS.
- **Seam flags**: When the text-critical algorithm detects a potential \
  editorial seam (bridge connective + institutional vocabulary + register \
  shift from preceding paragraphs). These are STRONG signals.

### How to use this data:
1. **Seam flags** — STRONGEST signal. When a seam flag fires, the paragraph \
   is likely a later editorial addition — not MIXED.
2. **Editorial fatigue** — Strong signal. Drift toward later layers indicates addition.
3. **Gardner flags** — Strong signal from the scholarly edition.
4. **Register scores** — WEAKEST signal. Trust YOUR reading over these.

## YOUR TASK

You receive a chapter's teaching text broken into numbered paragraphs with \
vocabulary register scores, seam detection flags, and chapter-level \
text-critical features. Classify each paragraph by temporal layer.

When you have completed your analysis, call the commit_extraction tool \
once with the complete extraction for all paragraphs.

## EXTRACTION RULES

1. **Temporal layer is the axis.** Do NOT classify by content type. \
   Classify by WHEN the language entered the text.

2. **The teaching core expounds, it does not cite.** Core teaching describes \
   how cosmic systems work. It does not say "as it is written" or "the \
   saviour preached."

3. **Editorial seams are NOT mixed paragraphs.** When a paragraph extends a \
   teaching sequence with institutional content, classify the ENTIRE \
   paragraph as PASTORAL.

4. **Preserve exact text.** For CORE paragraphs, return verbatim. For MIXED, \
   extract the old teaching words exactly — no paraphrase.

5. **Strip frame formulas from MIXED.** If frame wraps teaching, extract the \
   teaching only.

6. **Preserve lacunae, restorations, and manuscript markers.** Keep [...], \
   [restored text], manuscript page markers ⟨p.N⟩, and single-word gap \
   markers {} exactly as they appear in the source.

7. **Substantive cosmological questions are CORE.** "Tell us about the five \
   storehouses" reveals the teaching structure. Purely formulaic "We beseech \
   you" is FRAME. When both are present, classify as MIXED and PRESERVE the \
   substantive content.

8. **When in doubt about age, flag it.** Use temporal_note to record genuine \
   uncertainty. Do not keep late material out of caution.

9. **Watch for voice shifts.** The oldest teaching has a distinctive voice: \
   systematic, impersonal, structured, process-oriented. When you hear it \
   shift to citation, exhortation, or biography, that is a layer boundary.

10. **Editorial fatigue matters.** If the chapter-level fatigue score shows \
    strong pastoral drift in the second half, be MORE suspicious of pastoral \
    material in the later paragraphs.

11. **Polemic against "the sects" is ambiguous.** Flag rather than \
    automatically classify.

12. **DIALOGUE FRAME ATTRIBUTION MUST BE STRIPPED.** Phrases like \
    "Then speaks the apostle to him:" or "The enlightener says:" are \
    Layer 2 (Mani's compilation frame). They must NEVER appear in \
    core_text. If a paragraph starts with dialogue attribution followed \
    by teaching, classify as MIXED and extract ONLY the teaching.

13. **ENUMERATION MARKERS ARE SUBSTRATE.** Never strip "The first is...", \
    "The second is..." etc. from extracted core_text. These are the \
    bones of the teaching structure.

## THE SUBSTRATE BENEATH THE COPTIC

The text you examine is a Coptic translation. The TEACHING originates \
in a Persian/Iranian cosmological tradition — and beneath that, in the \
tradition of the Bene Qedem ("Children of the East"), the correspondential \
science of the ancient world. Preserve the Coptic translation vocabulary \
as-is in core_text. The one exception: capitalize personified cosmic \
entities (Sin, Darkness) when they function as agents.

Preserve lacunae brackets [...] and [text] — these mark physical \
manuscript damage.

Use temporal_note to record observations about the Coptic vocabulary — \
what concepts the translators rendered, anything notable about the \
translation choices."""


def build_system_prompt(metadata: dict | None) -> str:
    """Build system prompt with metadata-discovered layer descriptions.

    Appends a section describing the dynamically-identified temporal
    layers so the extraction LLM knows what classification labels to use
    and what each layer represents.
    """
    if not metadata:
        return SYSTEM_PROMPT

    vocabs = metadata.get("scoring_vocabularies", [])
    if not vocabs:
        return SYSTEM_PROMPT

    layer_section = (
        "\n\n## METADATA-DISCOVERED LAYERS\n\n"
        "The corpus metadata analysis has identified the following "
        "temporal layers in this text. These layers were discovered "
        "dynamically from the text itself. Use these layer IDs as "
        "your classification categories (plus 'mixed' for interwoven "
        "paragraphs):\n\n"
    )
    for v in vocabs:
        desc = v.get("description", "")
        name = v.get("name", v["id"])
        layer_section += f"- **{v['id']}** ({name}): {desc}\n"

    layer_section += (
        "\nThe paragraph-level register scores below are reported "
        "for these same categories. Your classification should use "
        "these layer IDs.\n"
    )

    return SYSTEM_PROMPT + layer_section


def build_extract_core_tool(metadata: dict | None = None) -> dict:
    """Build extraction tool schema with dynamic classification enum.

    If metadata is provided, the classification enum is built from the
    discovered layer IDs + 'mixed'. Otherwise falls back to the default.
    """
    import copy
    tool = copy.deepcopy(EXTRACT_CORE_TOOL)

    if not metadata:
        return tool

    vocabs = metadata.get("scoring_vocabularies", [])
    if not vocabs:
        return tool

    layer_ids = [v["id"] for v in vocabs]
    classification_enum = layer_ids + ["mixed"]

    # Build description from metadata
    desc_parts = [
        "Classify by TEMPORAL LAYER — when did this language "
        "enter this text? "
    ]
    for v in vocabs:
        name = v.get("name", v["id"])
        desc = v.get("description", "")
        short_desc = (desc[:100] + "...") if len(desc) > 100 else desc
        desc_parts.append(
            f"{v['id'].upper()}: {name}. {short_desc} "
        )
    desc_parts.append(
        "MIXED: Multiple layers interwoven in same paragraph."
    )

    para_props = (
        tool["input_schema"]["properties"]["paragraphs"]
        ["items"]["properties"]
    )
    para_props["classification"]["enum"] = classification_enum
    para_props["classification"]["description"] = "".join(desc_parts)

    return tool


# ---------------------------------------------------------------------------
# Client setup — Claude via Azure AI Foundry
# ---------------------------------------------------------------------------

def create_client() -> tuple[AnthropicFoundry, str]:
    """Create Claude client from .env credentials."""
    if not SECRETS_PATH.exists():
        print(f"ERROR: Secrets file not found at {SECRETS_PATH}")
        sys.exit(1)
    config = dotenv_values(SECRETS_PATH)
    endpoint = config.get("ANTHROPIC_ENDPOINT", "").rstrip("/")
    api_key = config.get("ANTHROPIC_API_KEY", "")
    deployment = config.get("ANTHROPIC_DEPLOYMENT", "claude-opus-4-6")

    if not endpoint or not api_key:
        print(
            "ERROR: ANTHROPIC_ENDPOINT and ANTHROPIC_API_KEY required "
            "in secrets/azure_openai.env"
        )
        sys.exit(1)

    client = AnthropicFoundry(
        api_key=api_key,
        base_url=endpoint,
        timeout=httpx.Timeout(1800.0, connect=30.0),
    )
    return client, deployment


# ---------------------------------------------------------------------------
# Load chapters
# ---------------------------------------------------------------------------

def load_chapters() -> list[dict]:
    """Load all cleaned chapter JSON files."""
    chapters = []
    for path in sorted(CHAPTERS_DIR.glob("ch_*.json")):
        with open(path, encoding="utf-8") as f:
            chapters.append(json.load(f))
    return chapters


def load_chapter(num: int) -> dict | None:
    path = CHAPTERS_DIR / f"ch_{num:03d}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# LLM extraction — Claude with tool call
# ---------------------------------------------------------------------------

def extract_core(
    client: AnthropicFoundry,
    deployment: str,
    chapter: dict,
    *,
    analysis_dir: Path | None = None,
    system_prompt: str = "",
    tool_schema: dict | None = None,
    debug: bool = False,
) -> dict | None:
    """Send a chapter to Claude Opus 4.6 for core extraction.

    Loads pre-computed text-critical analysis from analysis_dir (produced
    by extract_analysis.py). system_prompt and tool_schema are pre-built
    with dynamic layer information.

    Returns the tool_input dict, or None on failure.
    """
    ch_num = get_number(chapter)
    title = get_title(chapter)
    teaching = get_text(chapter)

    if not teaching.strip():
        return None

    # Load pre-computed analysis
    analysis = None
    if analysis_dir:
        analysis = load_analysis(analysis_dir, ch_num)

    # Build the paragraph block with scores AND seam flags
    para_block = []
    if analysis and analysis.get("paragraphs"):
        for para in analysis["paragraphs"]:
            scores = para.get("scores", {})
            seam = para.get("seam", {})
            score_parts = ", ".join(
                f"{k}={v}" for k, v in scores.items()
            )
            header = (
                f"--- PARAGRAPH {para['index']} "
                f"(words: {para['words']}, {score_parts})"
            )
            if seam.get("seam_flag"):
                header += f"\n  ⚠ {seam['seam_note']}"
            elif seam.get("has_bridge_connective"):
                header += (
                    f"\n  NOTE: Bridge connective detected: "
                    f"'{seam['bridge_phrase']}'"
                )
                if seam.get("institutional_terms_found"):
                    header += (
                        f" + institutional vocabulary: "
                        f"{', '.join(seam['institutional_terms_found'])}"
                    )
            header += " ---"
            para_block.append(f"{header}\n{para['text']}")
    else:
        # Fallback: no analysis available, send raw paragraphs
        if analysis_dir:
            print(
                f"  WARNING: No analysis found for Ch.{ch_num}, "
                f"sending raw paragraphs"
            )
        paragraphs = split_paragraphs(teaching)
        for i, text in enumerate(paragraphs):
            header = (
                f"--- PARAGRAPH {i+1} "
                f"(words: {len(text.split())}) ---"
            )
            para_block.append(f"{header}\n{text}")

    para_text = "\n\n".join(para_block)

    # Include Gardner synopsis as context
    gardner = chapter.get("gardner_synopsis", "")
    context = ""
    if gardner.strip():
        context = (
            f"\n--- GARDNER SYNOPSIS (context only — "
            f"DO NOT extract from this) ---\n"
            f"{gardner}\n"
            f"--- END SYNOPSIS ---\n"
        )

    user_msg = (
        f"Analyze the following chapter and extract the core "
        f"teaching layer.\n\n"
        f"Chapter {ch_num}: {title}\n"
        f"{context}\n"
        f"--- TEACHING TEXT (numbered paragraphs with register "
        f"scores and seam flags) ---\n\n"
        f"{para_text}\n\n"
        f"--- END ---"
    )

    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            tool_input = None
            text_parts: list[str] = []
            thinking_chars = 0

            with client.messages.stream(
                model=deployment,
                system=system_prompt or SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
                tools=[tool_schema or EXTRACT_CORE_TOOL],
                max_tokens=32_000,
                thinking={"type": "adaptive"},
            ) as stream:
                for event in stream:
                    etype = getattr(event, "type", "")

                    if etype == "content_block_start":
                        block = getattr(event, "content_block", None)
                        if (
                            block
                            and getattr(block, "type", "") == "thinking"
                            and debug
                        ):
                            print(
                                "\n  [thinking] ",
                                end="",
                                flush=True,
                            )

                    elif etype == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        if delta:
                            dtype = getattr(delta, "type", "")
                            if dtype == "thinking_delta":
                                chunk = getattr(delta, "thinking", "")
                                thinking_chars += len(chunk)
                                if debug:
                                    print(chunk, end="", flush=True)

                    elif etype == "message_stop":
                        if debug:
                            print(flush=True)

                final_msg = stream.get_final_message()

            if debug and thinking_chars:
                print(f" [{thinking_chars} chars]", flush=True)

            # Extract tool call
            for block in final_msg.content:
                btype = getattr(block, "type", "")
                if (
                    btype == "tool_use"
                    and block.name == "commit_extraction"
                ):
                    tool_input = block.input
                elif btype == "text":
                    text_parts.append(block.text)

            if tool_input is None:
                text_output = " ".join(text_parts).strip()
                print(
                    f"  WARNING: Model did not call "
                    f"commit_extraction for Ch.{ch_num}."
                )
                if text_output:
                    print(f"  Text: {text_output[:300]}")
                if attempt < max_retries:
                    time.sleep(attempt * 5)
                    continue
                return None

            return tool_input

        except Exception as e:
            err_str = str(e)
            if "content_filter" in err_str.lower():
                print(
                    f"  Content filter Ch.{ch_num}, "
                    f"attempt {attempt}/{max_retries}"
                )
                if attempt < max_retries:
                    time.sleep(attempt * 10)
                    continue
            elif "rate" in err_str.lower() or "429" in err_str:
                wait = 60.0 * attempt
                print(f"  Rate limit, waiting {wait:.0f}s...")
                time.sleep(wait)
                continue
            elif "overloaded" in err_str.lower() or "529" in err_str:
                wait = 30.0 * attempt
                print(f"  Overloaded, waiting {wait:.0f}s...")
                time.sleep(wait)
                continue
            else:
                print(f"  ERROR Ch.{ch_num}: {e}")
                if debug:
                    traceback.print_exc()
                if attempt < max_retries:
                    time.sleep(attempt * 5)
                    continue
                return None

    return None


# ---------------------------------------------------------------------------
# Passthrough mode — for fragment collections (no LLM needed)
# ---------------------------------------------------------------------------

def _run_passthrough(chapters: list[dict]) -> None:
    """Passthrough mode for fragment collections — reformat cleaned data.

    Fragments are already the primary teaching text: no editorial layers
    to separate. This reformats cleaned JSON into the extraction output
    format that correspondential_reading.py expects.
    """
    include_original = PROJECT_CFG.include_original_text

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)

    results = 0
    for i, ch in enumerate(chapters, 1):
        ch_num = get_number(ch)
        title = get_title(ch)
        text = get_text(ch)

        if not text.strip():
            print(f"  [{i}/{len(chapters)}] Section {ch_num}: empty, skip")
            continue

        paragraphs = split_paragraphs(text)

        para_list = []
        for j, para_text in enumerate(paragraphs, 1):
            para_list.append({
                "paragraph_number": j,
                "classification": "core",
                "core_text": para_text,
                "removed_material": None,
                "temporal_note": None,
            })

        extraction = {
            "chapter_number": ch_num,
            "chapter_title": title,
            "total_paragraphs": len(paragraphs),
            "core_paragraphs": len(paragraphs),
            "core_percentage": 100.0,
            "chapter_note": (
                "Fragment collection — all text is primary teaching layer."
            ),
            "paragraphs": para_list,
        }

        if include_original:
            original = ch.get("original_text", "")
            if original:
                extraction["original_text"] = original
                extraction["original_language"] = ch.get(
                    "original_language", ""
                )

        for key in (
            "manuscript_refs", "edition_refs", "section_markers", "footnotes",
        ):
            val = ch.get(key)
            if val:
                if isinstance(val, list) and val and hasattr(val[0], "model_dump"):
                    val = [v.model_dump() for v in val]
                extraction[key] = val

        path = SEGMENTS_DIR / f"ch_{ch_num:03d}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(extraction, f, indent=2, ensure_ascii=False)

        words = len(text.split())
        print(
            f"  [{i}/{len(chapters)}] Section {ch_num} ({words} words) "
            f"{title[:50]}... OK — {len(paragraphs)} ¶s (100% core)"
        )
        results += 1

    print(f"\n{'='*60}")
    print(f"PASSTHROUGH COMPLETE")
    print(f"  Processed: {results}")

    print(f"\nAssembling document...")
    text = assemble_core()
    if text:
        save_assembly(text)
    save_data_summary()
    print("Done.")


# ---------------------------------------------------------------------------
# Save / load
# ---------------------------------------------------------------------------

def save_extraction(ext: dict) -> None:
    """Save extraction result (dict from tool call) to JSON."""
    SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)
    ch_num = ext["chapter_number"]
    path = SEGMENTS_DIR / f"ch_{ch_num:03d}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ext, f, indent=2, ensure_ascii=False)


def load_extraction(ch_num: int) -> dict | None:
    path = SEGMENTS_DIR / f"ch_{ch_num:03d}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def is_extracted(ch_num: int) -> bool:
    return (SEGMENTS_DIR / f"ch_{ch_num:03d}.json").exists()


# ---------------------------------------------------------------------------
# Assembly: build the restored core text
# ---------------------------------------------------------------------------

def assemble_core() -> str:
    """Assemble all extracted core text into a continuous document."""
    extractions = []
    for path in sorted(SEGMENTS_DIR.glob("ch_*.json")):
        with open(path, encoding="utf-8") as f:
            extractions.append(json.load(f))

    if not extractions:
        print("ERROR: No extraction files found.")
        return ""

    is_fragments = (
        PROJECT_CFG and PROJECT_CFG.document_type == "fragment_collection"
    )
    display_name = PROJECT_CFG.display_name if PROJECT_CFG else "Unknown"
    unit_label = "Section" if is_fragments else "Chapter"

    lines = []
    if is_fragments:
        lines.append(f"# {display_name} — Teaching Text")
        lines.append("")
        lines.append(
            f"*{display_name} ({PROJECT_CFG.edition}), prepared for "
            f"correspondential reading.*"
        )
        lines.append(
            f"*Translated by {PROJECT_CFG.translator}.*"
        )
    else:
        lines.append("# The Teaching Core of the Kephalaia")
        lines.append("")
        lines.append(
            "*Extracted from the Coptic Kephalaia of the Teacher "
            "(Gardner, Brill 1995).*"
        )
        lines.append(
            "*Later editorial layers — hagiographic frame, pastoral "
            "instructions,*"
        )
        lines.append(
            "*and explicit Christian overlay — have been removed. Mixed "
            "passages*"
        )
        lines.append(
            "*have been repaired to recover the teaching content. The "
            "text is*"
        )
        lines.append("*presented in its original chapter order.*")
    lines.append("")
    lines.append("---")
    lines.append("")

    total_chapters = len(extractions)
    chapters_with_core = 0
    total_core_words = 0

    for ext in extractions:
        ch_num = ext["chapter_number"]
        title = ext.get("chapter_title", f"{unit_label} {ch_num}")

        core_parts = []
        temporal_notes = []
        for para in ext.get("paragraphs", []):
            ct = para.get("core_text")
            if ct:
                core_parts.append(ct)
                total_core_words += len(ct.split())
            tn = para.get("temporal_note")
            if tn:
                temporal_notes.append(
                    f"¶{para['paragraph_number']}: {tn}"
                )

        if not core_parts:
            continue

        chapters_with_core += 1

        lines.append(f"## {unit_label} {ch_num}")
        lines.append(f"### {title}")
        lines.append("")

        note = ext.get("chapter_note", "")
        if note:
            lines.append(f"*{note}*")
            lines.append("")

        for part in core_parts:
            lines.append(part)
            lines.append("")

        if temporal_notes:
            lines.append("**Temporal observations:**")
            for tn in temporal_notes:
                lines.append(f"- {tn}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Prepend statistics
    stats_block = [
        f"**{unit_label}s analyzed**: {total_chapters}",
        f"**{unit_label}s with core content**: {chapters_with_core}",
        f"**Core text words**: ~{total_core_words:,}",
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
    print(f"  Saved assembled core to {ASSEMBLED_FILE}")


def save_data_summary() -> None:
    """Save a JSON summary of all extractions."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    extractions = []
    for path in sorted(SEGMENTS_DIR.glob("ch_*.json")):
        with open(path, encoding="utf-8") as f:
            extractions.append(json.load(f))

    summary = {
        "total_chapters": len(extractions),
        "chapters": [],
    }

    total_core = 0
    total_paragraphs = 0
    for ext in extractions:
        core_count = sum(
            1 for p in ext.get("paragraphs", [])
            if p.get("core_text") is not None
        )
        total_count = len(ext.get("paragraphs", []))
        total_core += core_count
        total_paragraphs += total_count

        classifications = {}
        for p in ext.get("paragraphs", []):
            c = p.get("classification", "unknown")
            classifications[c] = classifications.get(c, 0) + 1

        summary["chapters"].append({
            "chapter_number": ext["chapter_number"],
            "title": ext.get("chapter_title", ""),
            "total_paragraphs": total_count,
            "core_paragraphs": core_count,
            "core_percentage": ext.get("core_percentage", 0),
            "classifications": classifications,
            "note": ext.get("chapter_note", ""),
        })

    summary["total_paragraphs"] = total_paragraphs
    summary["total_core_paragraphs"] = total_core

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"  Saved data summary to {DATA_FILE}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract the core teaching layer from a Manichaean text "
            "(Claude Opus 4.6)"
        )
    )
    parser.add_argument(
        "--project", "-p",
        type=str,
        default="kephalaia",
        help=(
            f"Project to process "
            f"(available: {', '.join(list_projects()) or 'none'})"
        ),
    )
    parser.add_argument("--chapter", "-c", type=int, default=None)
    parser.add_argument("--range", "-r", type=str, default=None)
    parser.add_argument("--limit", "-l", type=int, default=None)
    parser.add_argument("--dry-run", "-n", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--debug", action="store_true",
                        help="Show thinking output and verbose logging")
    parser.add_argument(
        "--max-concurrency", "-j",
        type=int,
        default=1,
        help="Number of parallel API calls (default: 1)",
    )
    parser.add_argument("--assemble", "-a", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_paths(args.project)

    # Assembly-only mode
    if args.assemble:
        print("Assembling core from existing extractions...")
        text = assemble_core()
        if text:
            save_assembly(text)
            save_data_summary()
        return

    # Load chapters
    all_chapters = load_chapters()
    if not all_chapters:
        print("ERROR: No cleaned chapters found in", CHAPTERS_DIR)
        sys.exit(1)

    print(f"Loaded {len(all_chapters)} cleaned chapters")

    # Determine which to process
    if args.chapter is not None:
        chapters = [
            ch for ch in all_chapters
            if get_number(ch) == args.chapter
        ]
        if not chapters:
            print(f"ERROR: Chapter {args.chapter} not found")
            sys.exit(1)
    elif args.range:
        m = re.match(r"(\d+)-(\d+)", args.range)
        if not m:
            print("ERROR: Invalid range. Use '0-20'")
            sys.exit(1)
        start, end = int(m.group(1)), int(m.group(2))
        chapters = [
            ch for ch in all_chapters
            if start <= get_number(ch) <= end
        ]
    else:
        chapters = all_chapters

    if args.limit:
        chapters = chapters[:args.limit]

    # Skip already processed
    if not args.overwrite:
        to_process = [
            ch for ch in chapters
            if not is_extracted(get_number(ch))
        ]
        skipped = len(chapters) - len(to_process)
        if skipped > 0:
            print(
                f"  Skipping {skipped} already-extracted "
                f"(use --overwrite)"
            )
        chapters = to_process

    if not chapters:
        print("All chapters already extracted.")
        text = assemble_core()
        if text:
            save_assembly(text)
            save_data_summary()
        return

    print(f"\nProcessing {len(chapters)} chapters:")
    for ch in chapters:
        num = get_number(ch)
        title = ch.get("title", "")[:60]
        words = len(get_text(ch).split())
        print(f"  Ch.{num:3d}  ({words:5d} words)  {title}")

    if args.dry_run:
        print("\n[DRY RUN] No API calls made.")
        return

    # --- Fragment collection: passthrough (no LLM needed) ---
    if PROJECT_CFG.document_type == "fragment_collection":
        _run_passthrough(chapters)
        return

    # --- Composite text: full LLM extraction ---
    client, deployment = create_client()
    print(f"\nUsing deployment: {deployment}")

    # Load corpus metadata (drives layer info for prompt/tool schema)
    metadata = load_corpus_metadata(PROJECT_CFG.paths.project_dir)
    if metadata:
        sys_prompt = build_system_prompt(metadata)
        tool_schema = build_extract_core_tool(metadata)
        print(f"Loaded corpus metadata for prompt/tool schema")
    else:
        sys_prompt = SYSTEM_PROMPT
        tool_schema = EXTRACT_CORE_TOOL
        print(
            "WARNING: No corpus metadata found — "
            "running without metadata-driven layer info"
        )

    # Pre-computed text-critical analysis (from extract_analysis.py)
    analysis_dir = PROJECT_CFG.paths.analysis_chapters
    print()

    # Process
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)

    concurrency = max(1, args.max_concurrency)
    results = []
    errors = []

    def process_chapter(
        ch: dict, idx: int
    ) -> tuple[int, dict | None]:
        """Process a single chapter."""
        ch_num = get_number(ch)
        return ch_num, extract_core(
            client, deployment, ch,
            analysis_dir=analysis_dir,
            system_prompt=sys_prompt,
            tool_schema=tool_schema,
            debug=args.debug,
        )

    if concurrency == 1:
        for i, ch in enumerate(chapters, 1):
            ch_num = get_number(ch)
            title = ch.get("title", "")[:50]
            words = len(get_text(ch).split())
            print(
                f"[{i}/{len(chapters)}] Ch.{ch_num} "
                f"({words} words) {title}...",
                end=" ",
                flush=True,
            )

            extraction = extract_core(
                client, deployment, ch,
                analysis_dir=analysis_dir,
                system_prompt=sys_prompt,
                tool_schema=tool_schema,
                debug=args.debug,
            )
            if extraction is None:
                print("FAILED")
                errors.append(ch_num)
                continue

            save_extraction(extraction)
            n_core = extraction.get("core_paragraphs", 0)
            n_tot = extraction.get("total_paragraphs", 0)
            pct = extraction.get("core_percentage", 0)
            print(f"OK — {n_core}/{n_tot} core ({pct:.0f}%)")
            results.append(extraction)

            if i < len(chapters):
                time.sleep(0.5)
    else:
        print(f"Running with {concurrency} parallel workers\n")
        print_lock = Lock()
        completed = 0
        total = len(chapters)

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {
                executor.submit(process_chapter, ch, i): ch
                for i, ch in enumerate(chapters, 1)
            }
            for future in as_completed(futures):
                ch = futures[future]
                ch_num = get_number(ch)
                title = ch.get("title", "")[:50]
                words = len(get_text(ch).split())
                completed += 1
                try:
                    _, extraction = future.result()
                except Exception as e:
                    with print_lock:
                        print(
                            f"[{completed}/{total}] Ch.{ch_num} "
                            f"({words} words) {title}... ERROR: {e}"
                        )
                    errors.append(ch_num)
                    continue

                if extraction is None:
                    with print_lock:
                        print(
                            f"[{completed}/{total}] Ch.{ch_num} "
                            f"({words} words) {title}... FAILED"
                        )
                    errors.append(ch_num)
                    continue

                save_extraction(extraction)
                n_core = extraction.get("core_paragraphs", 0)
                n_tot = extraction.get("total_paragraphs", 0)
                pct = extraction.get("core_percentage", 0)
                with print_lock:
                    print(
                        f"[{completed}/{total}] Ch.{ch_num} "
                        f"({words} words) {title}... "
                        f"OK — {n_core}/{n_tot} core ({pct:.0f}%)"
                    )
                results.append(extraction)

    # Summary
    print(f"\n{'='*60}")
    print(f"EXTRACTION COMPLETE")
    print(f"  Processed: {len(results)}")
    print(f"  Errors: {len(errors)}")
    if errors:
        print(f"  Failed: {errors}")

    # Assemble
    print(f"\nAssembling core document...")
    text = assemble_core()
    if text:
        save_assembly(text)
    save_data_summary()

    print("Done.")


if __name__ == "__main__":
    main()
