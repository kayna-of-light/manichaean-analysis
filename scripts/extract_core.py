#!/usr/bin/env python3
"""
Extract the core teaching layer from the Kephalaia of the Teacher.

This script performs textual criticism to recover the oldest teaching layer
from the composite Kephalaia text. It does NOT impose any narrative scheme
or reorganize content. It works chapter by chapter in textual order:

  1. Runs the register analysis (vocabulary scoring) on each paragraph
  2. Sends the chapter to GPT-5.2 WITH the register scores as guidance
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
"""
import argparse
import json
import re
import sys
import time
from enum import Enum
from pathlib import Path
from typing import Optional

from openai import OpenAI, RateLimitError, APIStatusError
from dotenv import dotenv_values
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SECRETS_PATH = PROJECT_ROOT / "secrets" / "azure_openai.env"
CHAPTERS_DIR = PROJECT_ROOT / "output" / "cleaned" / "chapters"
REGISTER_JSON = PROJECT_ROOT / "output" / "analysis" / "registers" / "register_analysis.json"
V4_DATA_JSON = PROJECT_ROOT / "output" / "analysis" / "v4" / "v4_data.json"
V4_PARA_JSON = PROJECT_ROOT / "output" / "analysis" / "v4" / "v4_paragraphs.json"
OUTPUT_DIR = PROJECT_ROOT / "output" / "core"
SEGMENTS_DIR = OUTPUT_DIR / "chapters"
ASSEMBLED_FILE = OUTPUT_DIR / "restored_core.md"
DATA_FILE = OUTPUT_DIR / "core_data.json"


# ---------------------------------------------------------------------------
# Register analysis — inline scoring (no import needed)
# ---------------------------------------------------------------------------

# Marker dictionaries copied from register_analysis.py for self-containment.
# We only need the scoring, not the full reporting.

FRAME_MARKERS = {
    "once again the enlightener speaks": 5,
    "once again he speaks": 4,
    "once more the enlightener": 5,
    "once more the apostle": 4,
    "once more his disciples": 4,
    "once again a disciple speaks": 5,
    "once again, at one of the times": 5,
    "his disciples questioned": 5,
    "the disciple questioned": 5,
    "disciples say to him": 5,
    "i beseech you": 4, "i entreat you": 4,
    "then speaks the apostle": 5,
    "then the apostle says": 5,
    "then the apostle speaks": 5,
    "then speaks the glorious one": 5,
    "the enlightener speaks to him": 4,
    "he speaks to that disciple": 4,
    "when they heard these things": 5,
    "when that disciple had heard": 5,
    "they rejoiced": 4, "they glorified": 4,
    "blessed is he who": 3,
    "you are glorious and blessed": 5,
    "sitting down among the church": 4,
    "sitting in the congregation": 4,
    "my master": 3, "our master": 3,
    "our enlightener": 4, "our father": 3,
    "the glorious one": 2,
    "i will explain it to you": 3,
    "behold, i have explained": 4,
    "on one of the occasions": 4,
    "we beseech you": 4, "we entreat you": 4,
    "that you may recount": 4,
    "he says to him": 3, "he says to them": 3,
}

PASTORAL_MARKERS = {
    "fasting": 2, "prayer": 2, "alms": 4, "alms-giving": 5,
    "catechumen": 4, "catechumens": 4,
    "church rules": 5, "sin": 1, "righteousness": 1,
    "sinners": 2, "repentance": 3,
    "the elect": 3, "the hearer": 4, "hearers": 4,
    "tithe": 5, "offering": 2, "charity": 4,
    "commandment": 3, "commandments": 3,
    "forbidden": 3, "lawful": 3,
    "holiness": 2, "purity": 2,
    "works of righteousness": 4,
}

CHRISTIAN_MARKERS = {
    "jesus the splendour": 2, "jesus the son of greatness": 3,
    "jesus the youth": 3, "beloved christ": 5,
    "christ": 2, "son of god": 3,
    "holy church": 3, "his church": 3,
    "apostolate": 4,
    "catechumen": 3, "catechumens": 3,
    "sons of the faith": 5, "daughters of the light": 5,
    "holy spirit": 2,
    "gospel": 3, "scripture": 1, "scriptures": 1,
    "parable": 2,
    "baptism": 4, "resurrection": 2,
}

TEACHING_MARKERS = {
    # Body-cosmos correspondence
    "corresponds": 5, "accords": 5, "pattern of": 4, "reflects": 3,
    "likeness": 3, "after the pattern": 5, "after the likeness": 5,
    "image": 2, "in the manner of": 3,
    # Body parts
    "head": 1, "neck": 1, "heart": 2, "stomach": 2, "ribs": 2,
    "navel": 2, "loins": 2, "liver": 3, "lung": 3, "spleen": 3,
    "kidneys": 3, "intestines": 2, "veins": 2, "skin": 1,
    "bone": 2, "marrow": 2, "sinew": 3, "flesh": 1, "blood": 1,
    # Interior states
    "peaceful": 3, "troubled": 3, "confusion": 3, "disturbance": 3,
    "ordered": 2, "tranquil": 3, "sweet": 1,
    "gladness": 2, "grief": 2, "anger": 2, "lust": 2, "envy": 2,
    # Natural images
    "food": 2, "nourishment": 3, "water": 1, "fire": 1, "wind": 1,
    "tree": 1, "trees": 1, "fruit": 1, "fruits": 1,
    "seed": 2, "root": 1, "branch": 1,
    "animal": 1, "animals": 1, "bird": 1, "birds": 1,
    "fish": 1, "reptile": 2, "creature": 1,
    "mountain": 2, "dust": 2, "spring": 2, "well": 1,
    # Cosmological teaching (NOT separated from correspondential)
    "first man": 3, "living spirit": 3, "mother of life": 3,
    "father of greatness": 3, "third ambassador": 3,
    "light mind": 3, "virgin of light": 3,
    "five shekhinas": 4, "five sons": 3, "five elements": 3,
    "five worlds": 3, "five limbs": 3, "five trees": 3,
    "two principles": 4, "three wheels": 3, "three vessels": 3,
    "living soul": 2, "cross of light": 3, "living fire": 3,
    "land of darkness": 3, "land of light": 2,
    "garment of light": 3, "garment of fire": 3,
    "new man": 3, "old man": 3,
    "column of glory": 4, "pillar of glory": 4, "perfect man": 3,
    "storehouses": 3, "firmaments": 3, "aeons": 2,
    "rulers": 2, "archons": 3, "elements": 1, "mixture": 2,
    "vessels": 2, "principalities": 3, "zodiac": 3,
    "call and answer": 5, "summons and obedience": 5,
    "consideration": 2, "counsel": 2, "insight": 2,
    "thought": 1, "mind": 1,
    # Five-fold / degree indicators
    "five": 1, "three": 1, "twelve": 1,
    "degree": 3, "degrees": 3,
}


def score_text(text: str, markers: dict[str, int]) -> float:
    """Score text against a marker set. Return normalized score per 100 words."""
    text_lower = text.lower()
    total = 0
    for marker, weight in markers.items():
        count = text_lower.count(marker.lower())
        if count > 0:
            total += weight * count
    words = max(len(text.split()), 1)
    return round((total / words) * 100, 2)


def split_paragraphs(text: str) -> list[str]:
    """Split teaching text into paragraphs."""
    parts = re.split(r'\n\s*\n|\n(?=⟨p\.\d+⟩)', text)
    return [p.strip() for p in parts if p.strip() and len(p.split()) >= 3]


def score_chapter_paragraphs(teaching_text: str) -> list[dict]:
    """Score each paragraph in a chapter's teaching text.

    Returns a list of dicts with paragraph text, word count, and register scores.
    """
    paragraphs = split_paragraphs(teaching_text)
    results = []
    for i, text in enumerate(paragraphs):
        results.append({
            "index": i + 1,
            "words": len(text.split()),
            "text_preview": text[:150].replace("\n", " "),
            "scores": {
                "teaching": score_text(text, TEACHING_MARKERS),
                "frame": score_text(text, FRAME_MARKERS),
                "pastoral": score_text(text, PASTORAL_MARKERS),
                "christian": score_text(text, CHRISTIAN_MARKERS),
            },
        })
    return results


# ---------------------------------------------------------------------------
# V4 data loader — chapter-level text-critical features
# ---------------------------------------------------------------------------

def load_v4_chapter_data() -> dict[int, dict]:
    """Load v4 analysis data keyed by chapter number.

    Returns dict of chapter_number → {
        layer_shift_score, first_half_cosmo, second_half_cosmo,
        first_half_pastoral, second_half_pastoral,
        has_formulaic_opening, has_formulaic_closing, has_question_formula,
        nt_citations, ot_citations, mani_citations,
        gardner_flags, composite_score, vocab_densities
    }
    """
    if not V4_DATA_JSON.exists():
        print(f"  WARNING: v4 data not found at {V4_DATA_JSON}")
        return {}
    with open(V4_DATA_JSON, encoding="utf-8") as f:
        data = json.load(f)
    result = {}
    for ch in data:
        result[ch["chapter_number"]] = {
            "layer_shift_score": ch.get("layer_shift_score", 0.0),
            "first_half_cosmo": ch.get("first_half_cosmo", 0.0),
            "second_half_cosmo": ch.get("second_half_cosmo", 0.0),
            "first_half_pastoral": ch.get("first_half_pastoral", 0.0),
            "second_half_pastoral": ch.get("second_half_pastoral", 0.0),
            "has_formulaic_opening": ch.get("has_formulaic_opening", False),
            "has_formulaic_closing": ch.get("has_formulaic_closing", False),
            "has_question_formula": ch.get("has_question_formula", False),
            "nt_citations": ch.get("nt_citations", []),
            "ot_citations": ch.get("ot_citations", []),
            "mani_citations": ch.get("mani_citations", []),
            "gardner_flags": ch.get("gardner_flags", []),
            "composite_score": ch.get("composite_score", 0.0),
            "vocab_densities": ch.get("vocab_densities", {}),
        }
    return result


# ---------------------------------------------------------------------------
# Editorial seam detection — paragraph-level
# ---------------------------------------------------------------------------

# Bridge connectives that editors use to graft new material onto existing
# teaching sequences. These are NOT the same as "Again," which is used
# within the core teaching to continue a series.
EDITORIAL_BRIDGE_PHRASES = [
    r"(?i)^now,?\s+moreover",
    r"(?i)^furthermore,?\s+(?:also|moreover)",
    r"(?i)^now,?\s+also",
    r"(?i)^moreover,?\s+also",
    r"(?i)^and\s+moreover",
    r"(?i)^but\s+moreover",
    r"(?i)^now,?\s+(?:these|this|the)\s+(?:same|very)",
]

EDITORIAL_BRIDGE_RES = [re.compile(p) for p in EDITORIAL_BRIDGE_PHRASES]

# Institutional vocabulary that signals the content is church-application
INSTITUTIONAL_TERMS = {
    "holy church", "the church", "apostle of light", "elect",
    "catechumen", "catechumens", "hearers", "leaders", "teachers",
    "congregation", "bishops", "presbyter", "deacons",
    "mission", "apostolate",
}


def detect_editorial_seams(paragraphs: list[str], para_scores: list[dict]) -> list[dict]:
    """Detect potential editorial seams at paragraph level.

    An editorial seam is where an editor extends an existing teaching sequence
    by mimicking the syntactic pattern but introducing institutional content.
    The archetype is Ch.3 ¶9: "Now, moreover, happiness, wisdom and power
    exist in the holy church" — the editor saw the four-fold cosmological
    iteration and added a fifth applying it to their own institution.

    Returns one dict per paragraph with seam analysis.
    """
    results = []
    for i, (text, scores) in enumerate(zip(paragraphs, para_scores)):
        text_lower = text.lower()
        seam = {
            "has_bridge_connective": False,
            "bridge_phrase": None,
            "institutional_terms_found": [],
            "register_shift": False,
            "seam_flag": False,
            "seam_note": None,
        }

        # Check for bridge connective at paragraph start
        first_line = text.strip().split("\n")[0] if text.strip() else ""
        for pat in EDITORIAL_BRIDGE_RES:
            m = pat.search(first_line)
            if m:
                seam["has_bridge_connective"] = True
                seam["bridge_phrase"] = m.group(0)
                break

        # Check for institutional vocabulary
        for term in INSTITUTIONAL_TERMS:
            if term in text_lower:
                seam["institutional_terms_found"].append(term)

        # Register shift detection: compare to preceding paragraphs
        if i >= 1:
            s = scores["scores"]
            # Average teaching and pastoral scores of preceding 1-3 paragraphs
            lookback = min(i, 3)
            prev_teaching = sum(
                para_scores[i - j - 1]["scores"]["teaching"]
                for j in range(lookback)
            ) / lookback
            prev_pastoral = sum(
                para_scores[i - j - 1]["scores"]["pastoral"]
                for j in range(lookback)
            ) / lookback

            # If pastoral rises AND teaching drops relative to predecessors
            pastoral_rise = s["pastoral"] - prev_pastoral
            teaching_drop = prev_teaching - s["teaching"]
            if pastoral_rise > 1.0 or (
                seam["has_bridge_connective"] and len(seam["institutional_terms_found"]) >= 1
            ):
                seam["register_shift"] = True

        # Combined seam flag
        if seam["has_bridge_connective"] and (
            seam["register_shift"] or len(seam["institutional_terms_found"]) >= 2
        ):
            seam["seam_flag"] = True
            seam["seam_note"] = (
                f"EDITORIAL SEAM DETECTED: Bridge connective '{seam['bridge_phrase']}' "
                f"with institutional vocabulary ({', '.join(seam['institutional_terms_found'])}). "
                f"This paragraph likely extends an existing teaching sequence with "
                f"institutional application — the editor mimics the preceding pattern "
                f"but shifts to church-specific content."
            )
        elif len(seam["institutional_terms_found"]) >= 3 and seam.get("register_shift"):
            seam["seam_flag"] = True
            seam["seam_note"] = (
                f"PROBABLE EDITORIAL EXTENSION: High institutional vocabulary "
                f"({', '.join(seam['institutional_terms_found'])}) with register shift "
                f"from preceding cosmological paragraphs."
            )

        results.append(seam)
    return results


def format_editorial_fatigue(v4_data: dict) -> str:
    """Format chapter-level editorial fatigue assessment for LLM context."""
    shift = v4_data.get("layer_shift_score", 0.0)
    fh_c = v4_data.get("first_half_cosmo", 0.0)
    sh_c = v4_data.get("second_half_cosmo", 0.0)
    fh_p = v4_data.get("first_half_pastoral", 0.0)
    sh_p = v4_data.get("second_half_pastoral", 0.0)

    lines = []
    lines.append(f"  Editorial fatigue score: {shift:.2f}")
    lines.append(f"    First half — cosmological: {fh_c:.2f}, pastoral: {fh_p:.2f}")
    lines.append(f"    Second half — cosmological: {sh_c:.2f}, pastoral: {sh_p:.2f}")

    if shift > 0.5:
        lines.append("    ⚠ SIGNIFICANT pastoral drift in second half — "
                      "editor likely added institutional material after core teaching")
    elif shift > 0.2:
        lines.append("    ⚠ Moderate pastoral drift in second half")
    elif shift < -0.5:
        lines.append("    Cosmological density increases in second half — unusual pattern")

    return "\n".join(lines)


def format_chapter_context(v4_data: dict) -> str:
    """Format chapter-level v4 analytical context for the LLM."""
    lines = []

    # Structure
    features = []
    if v4_data.get("has_formulaic_opening"):
        features.append("formulaic opening")
    if v4_data.get("has_formulaic_closing"):
        features.append("formulaic closing")
    if v4_data.get("has_question_formula"):
        features.append("question formula")
    if features:
        lines.append(f"  Structure: {', '.join(features)}")

    # Citations
    nt = v4_data.get("nt_citations", [])
    ot = v4_data.get("ot_citations", [])
    if nt:
        lines.append(f"  NT citations in footnotes: {', '.join(nt)}")
    if ot:
        lines.append(f"  OT citations in footnotes: {', '.join(ot)}")

    # Gardner flags
    flags = v4_data.get("gardner_flags", [])
    if flags:
        lines.append(f"  Gardner editorial flags: {', '.join(flags)}")

    # Teaching purity (new v4 field)
    purity = v4_data.get("teaching_purity", None)
    teach_d = v4_data.get("teaching_density", None)
    overlay_d = v4_data.get("overlay_density", None)
    if purity is not None:
        lines.append(f"  Teaching purity: {purity:.2f} "
                      f"(teaching_density={teach_d:.2f}, overlay_density={overlay_d:.2f})")

    # Vocab densities (raw details)
    vd = v4_data.get("vocab_densities", {})
    if vd:
        top = sorted(vd.items(), key=lambda x: x[1], reverse=True)[:3]
        density_str = ", ".join(f"{k}={v:.2f}" for k, v in top if v > 0)
        if density_str:
            lines.append(f"  Top vocabulary densities (raw): {density_str}")

    # Editorial fatigue
    lines.append(format_editorial_fatigue(v4_data))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pydantic models for structured LLM output
# ---------------------------------------------------------------------------

class ParagraphType(str, Enum):
    """Classification of a paragraph by temporal layer."""
    CORE = "core"
    FRAME = "frame"
    PASTORAL = "pastoral"
    OVERLAY = "overlay"
    MIXED = "mixed"


class ParagraphExtraction(BaseModel):
    """Extraction result for a single paragraph."""
    paragraph_number: int = Field(
        description="Which paragraph in the chapter (1-indexed, matching the register analysis)"
    )
    classification: ParagraphType = Field(
        description=(
            "Classify by TEMPORAL LAYER — when did this language enter this text? "
            "CORE: The oldest teaching layer. Systematic cosmological-correspondential "
            "teaching that predates the editorial compilation. Identified by: "
            "numbered degree structures, body-universe maps, named cosmic beings in "
            "SYSTEMATIC exposition, light-dark mechanics, five-fold/three-fold sets. "
            "Characteristic voice: impersonal, structural, 'how things work'. "
            "FRAME: Hagiographic editorial apparatus added by the compiling community. "
            "Q&A formulas, closing praise, biographical Mani-claims, titles of reverence. "
            "PASTORAL: Institutional church material — fasting, alms, catechumen rules, "
            "behavioral ethics without cosmological mechanism. "
            "CRITICAL: When a paragraph extends a teaching sequence by mimicking its "
            "syntax but applying it to church/institutional content, the ENTIRE "
            "paragraph is PASTORAL. Example: after a series mapping 'these three exist "
            "in [cosmic domain]', a paragraph saying 'Now, moreover, these three exist "
            "in the holy church' followed by ecclesial identifications is PASTORAL — "
            "the editor added the whole paragraph, including the opening clause. "
            "Do NOT split such paragraphs as MIXED. "
            "OVERLAY: Material that entered via the Gospels, NT, or Mani's Christian "
            "synthesis. This includes: Gospel citations and their paraphrases (even if "
            "the cited teaching uses correspondence — Jesus spoke in correspondence "
            "but citing his Gospel sayings is a LATER act), 'As it is written in the "
            "Gospel', Pauline vocabulary in devotional contexts, 'the saviour preached', "
            "NT narrative exempla (Judas, Paul's conversion, etc). The test: did this "
            "language ENTER the Kephalaia via the NT? If yes, it is overlay regardless "
            "of its internal content quality. "
            "MIXED: A paragraph where genuinely old teaching is interwoven with later "
            "material such that cutting cleanly is possible. Use ONLY when old teaching "
            "language (not just borrowed syntax) is genuinely present alongside later "
            "additions. A paragraph flagged as EDITORIAL SEAM is NOT mixed — it is "
            "pastoral or overlay, because the entire paragraph was written by the editor."
        )
    )
    core_text: Optional[str] = Field(
        default=None,
        description=(
            "For CORE paragraphs: the paragraph text with vocabulary RESTORED "
            "to the register of the oldest substrate (see SUBSTRATE section in "
            "system prompt). The Coptic text is a translation of Persian/Iranian "
            "cosmological teaching that may reach back to the Bene Qedem. Where "
            "the Coptic translators used Christian vocabulary to render concepts "
            "that belong to an older cosmological tradition, restore the "
            "vocabulary to what that tradition would have used. "
            "For MIXED paragraphs: the extracted old teaching with later "
            "additions removed, also in substrate register. "
            "Preserve lacunae [...], editorial restorations [text], and "
            "manuscript page markers ⟨p.N⟩. Text inside brackets may also be "
            "transformed to substrate register where appropriate. "
            "For FRAME/PASTORAL/OVERLAY: null. "
            "CRITICAL: A paragraph classified as OVERLAY or PASTORAL gets null "
            "here even if its content is profound or correspondential. The "
            "classification is about WHEN it entered the text, not content quality. "
            "SPECIFICALLY: when a paragraph with an EDITORIAL SEAM flag mimics "
            "the preceding teaching syntax but applies it to institutional content, "
            "core_text must be null — the opening clause that echoes the pattern "
            "is PART OF the editorial graft, not a remnant of old teaching."
        )
    )
    removed_material: Optional[str] = Field(
        default=None,
        description=(
            "For MIXED paragraphs only: describe what was removed and why. "
            "Be specific: 'Removed opening frame formula: Once again the "
            "enlightener speaks to his disciples.' Null for non-MIXED."
        )
    )
    temporal_note: Optional[str] = Field(
        default=None,
        description=(
            "Brief observation about temporal layer. What makes you date this "
            "paragraph to its assigned layer? What voice markers, citation "
            "formulas, structural patterns, or register shifts do you observe? "
            "For overlay: note the entry vector (e.g. 'Gospel citation formula'). "
            "For core: note what marks it as old (e.g. 'systematic five-fold "
            "mapping, impersonal expository voice'). "
            "Be honest about uncertainty."
        )
    )


class ChapterExtraction(BaseModel):
    """Complete extraction result for one chapter."""
    chapter_number: int
    chapter_title: str
    total_paragraphs: int
    core_paragraphs: int = Field(
        description="Count of CORE + MIXED paragraphs (those with extracted core_text)"
    )
    core_percentage: float = Field(
        description="Estimated % of teaching text word count that is core (0-100)"
    )
    chapter_note: str = Field(
        description=(
            "Brief assessment of this chapter. Is the core teaching dominant? "
            "Is the chapter mostly frame/pastoral with embedded fragments? "
            "Note any distinctive features of the language or content."
        )
    )
    paragraphs: list[ParagraphExtraction]


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a textual critic working on the Coptic Kephalaia of the Teacher — a \
Manichaean composite text compiled in the 3rd-4th century CE. Your task is to \
identify the OLDEST TEACHING LAYER and separate it from later editorial additions.

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

1. **Vocabulary lists** were manually curated for six categories: \
   cosmological, persian_substrate, correspondential, pastoral, \
   nt_christian, hagiographic.
2. **Density scores** count how often words from each list appear per 100 \
   words of text.
3. **Composite scores** weight those densities (teaching categories \
   positive, overlay categories negative) into a single number.

This means the scores measure WHAT VOCABULARY IS PRESENT. They cannot \
determine WHEN that vocabulary entered the text. A paragraph full of \
pastoral vocabulary might be genuinely late — or it might be old teaching \
that an editor has wrapped in institutional language. The vocabulary \
counter cannot tell the difference. Only YOU can, by reading the actual \
text.

**YOUR reading of the text is PRIMARY. The scores are guides, not truth.** \
Specifically:
- A high pastoral score does NOT mean "classify as pastoral." It means \
  "pastoral vocabulary is present — investigate whether the underlying \
  teaching is old."
- A high teaching score does NOT mean "classify as core." It means \
  "teaching vocabulary is present — verify this is genuinely old and not \
  a later imitation."
- The scores are MOST reliable for detecting editorial fatigue patterns \
  (pastoral drift across chapter halves) and for flagging editorial seams \
  (bridge connective + register shift). These structural patterns are \
  harder to fake than raw vocabulary presence.

### Chapter-level features:
- **Teaching purity**: Ratio of teaching vocabulary to total vocabulary \
  density. Higher = less overlay vocabulary. But this is still just \
  vocabulary counting — a chapter with high purity can still have late \
  material if the editor wrote in teaching style.
- **Editorial fatigue score**: Measures pastoral drift from first to second \
  half of the chapter. Positive values mean pastoral vocabulary increases \
  in the second half — a classic editorial fatigue pattern where scribes \
  add institutional material after the core teaching. This is one of the \
  MORE reliable signals because it detects a structural pattern, not just \
  vocabulary presence.
- **Structure**: Whether formulaic opening/closing are detected.
- **Citations**: NT/OT citations found in the scholarly footnotes.
- **Gardner flags**: Editorial observations from the critical apparatus \
  (these come directly from the scholarly edition — high reliability).

### Paragraph-level features:
- **Register scores**: teaching, frame, pastoral, christian vocabulary \
  density per 100 words. These are RAW VOCABULARY COUNTS — they tell you \
  what words are present, not what temporal layer the paragraph belongs to. \
  Use them to direct your attention, not to determine your classification.
- **Seam flags**: When the text-critical algorithm detects a potential \
  editorial seam (bridge connective + institutional vocabulary + register \
  shift from preceding paragraphs). These flags are STRONG signals because \
  they detect a STRUCTURAL pattern (an editor extending an existing sequence), \
  not just vocabulary presence.

### How to use this data:
Use these features alongside your own temporal judgment. The reliability \
hierarchy is:
1. **Seam flags** — STRONGEST signal. These detect a STRUCTURAL pattern \
   (bridge connective + institutional terms + register shift from preceding \
   paragraphs). A seam flag means an editor extended an existing sequence. \
   When a seam flag fires, the paragraph is PASTORAL or OVERLAY — not MIXED. \
   Do NOT override a seam flag by extracting the opening clause as core_text. \
   The opening clause that mimics the pattern IS PART OF the editorial graft.
2. **Editorial fatigue** — Strong signal. Pastoral drift across chapter \
   halves indicates scribal addition of institutional material.
3. **Gardner flags** — Strong signal. These come from the scholarly edition.
4. **Register scores** — WEAKEST signal. These are raw vocabulary counts. \
   They tell you what words are present, not what layer a paragraph belongs \
   to. A paragraph with high pastoral score might contain old teaching \
   wrapped in editorial language. Trust YOUR reading of the actual text \
   over register scores — but NOT over seam flags.

## YOUR TASK

You receive a chapter's teaching text broken into numbered paragraphs with \
vocabulary register scores, seam detection flags, and chapter-level \
text-critical features. Classify each paragraph by temporal layer.

## EXTRACTION RULES

1. **Temporal layer is the axis.** Do NOT classify by content type ("this has \
   correspondence so it must be core"). Classify by WHEN the language entered \
   the text. A Gospel citation containing correspondential content is OVERLAY.

2. **The teaching core expounds, it does not cite.** Core teaching describes \
   how cosmic systems work. It does not say "as it is written" or "the \
   saviour preached." When you see citation formulas, you are looking at a \
   later hand — even if what is cited is profound.

3. **Editorial seams are NOT mixed paragraphs.** When a paragraph extends a \
   teaching sequence with institutional content (detected by bridge \
   connective + register shift), classify the ENTIRE paragraph as PASTORAL. \
   The opening clause that mimics the pattern is part of the editorial \
   addition — do NOT extract it as core_text.

4. **Preserve exact text.** For CORE paragraphs, return verbatim. For MIXED, \
   extract the old teaching words exactly — no paraphrase.

5. **Strip frame formulas from MIXED.** If frame wraps teaching, extract the \
   teaching only.

6. **Preserve lacunae and restorations.** Keep [...], [restored text], ⟨p.N⟩.

7. **Substantive cosmological questions are CORE.** "Tell us about the five \
   storehouses" reveals the teaching structure. Purely formulaic "We beseech \
   you" is FRAME.

8. **When in doubt about age, flag it.** Use temporal_note to record genuine \
   uncertainty. Do not keep late material out of caution — be honest about \
   what you can and cannot date.

9. **Watch for voice shifts.** The oldest teaching has a distinctive voice: \
   systematic, impersonal, structured, process-oriented. When you hear it \
   shift to citation, exhortation, or biography, that is a layer boundary.

10. **Editorial fatigue matters.** If the chapter-level fatigue score shows \
    strong pastoral drift in the second half, be MORE suspicious of pastoral \
    material in the later paragraphs — the editor likely added it after \
    the core teaching was complete.

11. **Polemic against "the sects" is ambiguous.** Anti-sectarian argument \
    could be Mani's own voice (3rd century) or older tradition. Flag rather \
    than automatically classify.

12. **DIALOGUE FRAME ATTRIBUTION MUST BE STRIPPED.** Phrases like \
    "Then speaks the apostle to him:" or "The enlightener says:" are \
    Layer 2 (Mani's compilation frame). They must NEVER appear in \
    core_text. If a paragraph starts with a dialogue attribution \
    followed by teaching content, classify as MIXED and extract ONLY \
    the teaching content, stripping the frame formula completely. \
    The word "apostle" in particular is a Layer 2 marker — the oldest \
    substrate does not use this term.

## THE SUBSTRATE BENEATH THE COPTIC

The text you examine is a Coptic translation. But the TEACHING originates \
in a Persian/Iranian cosmological tradition — and beneath that, in the \
tradition of the Bene Qedem ("Children of the East"), the correspondential \
science of the ancient world.

You know this tradition. You know Zoroastrian cosmology, the Bundahishn, \
the Avesta, Middle Persian Manichaean terminology from the Turfan \
fragments. You know what the cosmic adversary is called in that tradition, \
what the five faculties of darkness are, how the agents of liberation \
are described functionally rather than devotionally.

The Coptic translators rendered these Persian/Iranian concepts using \
the vocabulary available to them — Greek loanwords, Christian terms, \
Coptic approximations. Some of these choices shift the register from \
cosmological to moral, from functional to devotional, from impersonal \
to soteriological. The concepts are older than the Coptic words.

When extracting core_text, RESTORE vocabulary to the register of the \
oldest substrate. Use your knowledge of the Persian/Iranian tradition \
and deeper Bene Qedem cosmology to determine what the original \
concept is and how it would have been expressed before Coptic \
translation. Where the Coptic introduces a Christian register that \
the substrate would not have used, transform the vocabulary. Where \
the Coptic word adequately renders the substrate concept, leave it.

Preserve lacunae brackets [...] and [text] — these mark physical \
manuscript damage and will be handled by the restoration pass. Text \
inside brackets may also be transformed where appropriate.

Use temporal_note to DOCUMENT all vocabulary transformations and your \
reasoning — what the Coptic says, what the substrate concept is, and \
why you chose the term you did. This creates an audit trail.
"""


# ---------------------------------------------------------------------------
# Client setup
# ---------------------------------------------------------------------------

def create_client() -> OpenAI:
    """Create OpenAI client."""
    if not SECRETS_PATH.exists():
        print(f"ERROR: Secrets file not found at {SECRETS_PATH}")
        sys.exit(1)
    config = dotenv_values(SECRETS_PATH)
    return OpenAI(
        base_url=config["OPENAI_ENDPOINT"],
        api_key=config["OPENAI_API_KEY"],
    )


def get_deployment() -> str:
    config = dotenv_values(SECRETS_PATH)
    return config["OPENAI_DEPLOYMENT"]


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
# LLM extraction
# ---------------------------------------------------------------------------

def extract_core(client: OpenAI, deployment: str, chapter: dict,
                  v4_data: dict | None = None) -> ChapterExtraction | None:
    """Send a chapter to GPT-5.2 for core extraction."""
    ch_num = chapter["chapter_number"]
    title = chapter.get("title", f"Chapter {ch_num}")
    teaching = chapter.get("teaching_text", "")

    if not teaching.strip():
        return None

    # Score paragraphs
    para_scores = score_chapter_paragraphs(teaching)
    paragraphs = split_paragraphs(teaching)

    # Run editorial seam detection
    seam_results = detect_editorial_seams(paragraphs, para_scores)

    # Build the paragraph block with scores AND seam flags
    para_block = []
    for i, (text, scores, seam) in enumerate(zip(paragraphs, para_scores, seam_results)):
        s = scores["scores"]
        header = (
            f"--- PARAGRAPH {i+1} (words: {scores['words']}, "
            f"teaching={s['teaching']}, frame={s['frame']}, "
            f"pastoral={s['pastoral']}, christian={s['christian']})"
        )
        # Add seam flag if detected
        if seam["seam_flag"]:
            header += f"\n  ⚠ {seam['seam_note']}"
        elif seam["has_bridge_connective"]:
            header += (
                f"\n  NOTE: Bridge connective detected: '{seam['bridge_phrase']}'"
            )
            if seam["institutional_terms_found"]:
                header += (
                    f" + institutional vocabulary: "
                    f"{', '.join(seam['institutional_terms_found'])}"
                )
        header += " ---"
        para_block.append(f"{header}\n{text}")

    para_text = "\n\n".join(para_block)

    # Include Gardner synopsis as context
    gardner = chapter.get("gardner_synopsis", "")
    context = ""
    if gardner.strip():
        context = (
            f"\n--- GARDNER SYNOPSIS (context only — DO NOT extract from this) ---\n"
            f"{gardner}\n"
            f"--- END SYNOPSIS ---\n"
        )

    # Build chapter-level text-critical context
    tc_context = ""
    if v4_data:
        tc_context = (
            f"\n--- TEXT-CRITICAL ANALYSIS (chapter-level features) ---\n"
            f"{format_chapter_context(v4_data)}\n"
            f"--- END TEXT-CRITICAL ANALYSIS ---\n"
        )

    user_msg = (
        f"Analyze the following chapter and extract the core teaching layer.\n\n"
        f"Chapter {ch_num}: {title}\n"
        f"{context}"
        f"{tc_context}\n"
        f"--- TEACHING TEXT (numbered paragraphs with register scores and seam flags) ---\n\n"
        f"{para_text}\n\n"
        f"--- END ---"
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
                text_format=ChapterExtraction,
                max_output_tokens=16384,
            )
            result = response.output_parsed
            if result is None:
                raise ValueError("No structured output (parsed is None)")
            return result

        except RateLimitError:
            wait = 60.0
            print(f"  (rate limit, retry {attempt}/{max_retries} in {wait:.0f}s)...",
                  end=" ", flush=True)
            time.sleep(wait)

        except APIStatusError as e:
            err_str = str(e)
            if "content_filter" in err_str.lower() and attempt < max_retries:
                wait = attempt * 10
                print(f"  (filter, retry {attempt}/{max_retries} in {wait}s)...",
                      end=" ", flush=True)
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
# Save / load
# ---------------------------------------------------------------------------

def save_extraction(ext: ChapterExtraction) -> None:
    SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)
    path = SEGMENTS_DIR / f"ch_{ext.chapter_number:03d}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ext.model_dump(), f, indent=2, ensure_ascii=False)


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
    """Assemble all extracted core text into a continuous document in chapter order."""
    extractions = []
    for path in sorted(SEGMENTS_DIR.glob("ch_*.json")):
        with open(path, encoding="utf-8") as f:
            extractions.append(json.load(f))

    if not extractions:
        print("ERROR: No extraction files found.")
        return ""

    lines = []
    lines.append("# The Teaching Core of the Kephalaia")
    lines.append("")
    lines.append("*Extracted from the Coptic Kephalaia of the Teacher (Gardner, Brill 1995).*")
    lines.append("*Later editorial layers — hagiographic frame, pastoral instructions,*")
    lines.append("*and explicit Christian overlay — have been removed. Mixed passages*")
    lines.append("*have been repaired to recover the teaching content. The text is*")
    lines.append("*presented in its original chapter order.*")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Statistics
    total_chapters = len(extractions)
    chapters_with_core = 0
    total_core_words = 0
    total_teaching_words = 0

    for ext in extractions:
        ch_num = ext["chapter_number"]
        title = ext.get("chapter_title", f"Chapter {ch_num}")

        # Collect core text from this chapter
        core_parts = []
        temporal_notes = []
        for para in ext.get("paragraphs", []):
            ct = para.get("core_text")
            if ct:
                core_parts.append(ct)
                total_core_words += len(ct.split())
            tn = para.get("temporal_note")
            if tn:
                temporal_notes.append(f"¶{para['paragraph_number']}: {tn}")

        # Estimate total teaching words from paragraph count × average
        # (we don't have the original text here, just the extraction)
        total_teaching_words += sum(
            len(p.get("core_text", "").split()) if p.get("core_text") else 0
            for p in ext.get("paragraphs", [])
        )

        if not core_parts:
            continue

        chapters_with_core += 1

        lines.append(f"## Chapter {ch_num}")
        lines.append(f"### {title}")
        lines.append("")

        # Chapter note
        note = ext.get("chapter_note", "")
        if note:
            lines.append(f"*{note}*")
            lines.append("")

        # Core text
        for part in core_parts:
            lines.append(part)
            lines.append("")

        # Temporal observations (if any)
        if temporal_notes:
            lines.append("**Temporal observations:**")
            for tn in temporal_notes:
                lines.append(f"- {tn}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Prepend statistics
    stats_block = [
        f"**Chapters analyzed**: {total_chapters}",
        f"**Chapters with core content**: {chapters_with_core}",
        f"**Core text words**: ~{total_core_words:,}",
        "",
    ]
    # Insert after the header
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
        description="Extract the core teaching layer from the Kephalaia"
    )
    parser.add_argument("--chapter", "-c", type=int, default=None)
    parser.add_argument("--range", "-r", type=str, default=None)
    parser.add_argument("--limit", "-l", type=int, default=None)
    parser.add_argument("--dry-run", "-n", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--assemble", "-a", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

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
        chapters = [ch for ch in all_chapters if ch["chapter_number"] == args.chapter]
        if not chapters:
            print(f"ERROR: Chapter {args.chapter} not found")
            sys.exit(1)
    elif args.range:
        m = re.match(r"(\d+)-(\d+)", args.range)
        if not m:
            print("ERROR: Invalid range. Use '0-20'")
            sys.exit(1)
        start, end = int(m.group(1)), int(m.group(2))
        chapters = [ch for ch in all_chapters if start <= ch["chapter_number"] <= end]
    else:
        chapters = all_chapters

    if args.limit:
        chapters = chapters[:args.limit]

    # Skip already processed
    if not args.overwrite:
        to_process = [ch for ch in chapters if not is_extracted(ch["chapter_number"])]
        skipped = len(chapters) - len(to_process)
        if skipped > 0:
            print(f"  Skipping {skipped} already-extracted chapters (use --overwrite)")
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
        num = ch["chapter_number"]
        title = ch.get("title", "")[:60]
        words = len(ch.get("teaching_text", "").split())
        print(f"  Ch.{num:3d}  ({words:5d} words)  {title}")

    if args.dry_run:
        print("\n[DRY RUN] No API calls made.")
        return

    # Create client
    client = create_client()
    deployment = get_deployment()
    print(f"\nUsing deployment: {deployment}")

    # Load v4 text-critical data
    v4_all = load_v4_chapter_data()
    if v4_all:
        print(f"Loaded v4 text-critical data for {len(v4_all)} chapters")
    else:
        print("WARNING: No v4 data loaded — running without text-critical context")
    print()

    # Process
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    errors = []
    for i, ch in enumerate(chapters, 1):
        ch_num = ch["chapter_number"]
        title = ch.get("title", "")[:50]
        words = len(ch.get("teaching_text", "").split())
        print(f"[{i}/{len(chapters)}] Ch.{ch_num} ({words} words) {title}...",
              end=" ", flush=True)

        extraction = extract_core(client, deployment, ch,
                                   v4_data=v4_all.get(ch_num))
        if extraction is None:
            print("FAILED")
            errors.append(ch_num)
            continue

        save_extraction(extraction)
        n_core = extraction.core_paragraphs
        n_tot = extraction.total_paragraphs
        pct = extraction.core_percentage
        print(f"OK — {n_core}/{n_tot} core ({pct:.0f}%)")
        results.append(extraction.model_dump())

        # Brief pause
        if i < len(chapters):
            time.sleep(0.5)

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
