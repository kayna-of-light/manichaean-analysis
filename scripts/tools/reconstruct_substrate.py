#!/usr/bin/env python3
"""
Reconstruct the pre-Mani cosmological substrate from the Kephalaia of the Teacher.

This script uses GPT-5.2 to:
  1. Read each cleaned chapter's teaching text
  2. Identify distinct teaching segments
  3. Classify each segment (substrate / frame / pastoral / nt_overlay / transition)
  4. For substrate segments, assign a narrative episode in the cosmological sequence
  5. Extract the core teaching stripped of editorial framing
  6. Assemble the substrate as a continuous text organized by its own internal logic

The output is the restored substrate — the original cosmological/correspondential
teaching that underlies the Kephalaia, organized by the narrative sequence rather
than the imposed chapter structure.

Validation criterion: the substrate should parallel the Book of Jashar / Book of
the Upright and the Šābuhragān cosmological architecture (as established in
docs/WARS_OF_YHWH_CONSONANTAL_ANALYSIS.md).

Usage:
    python scripts/reconstruct_substrate.py                    # Process all chapters
    python scripts/reconstruct_substrate.py --chapter 10       # Process single chapter
    python scripts/reconstruct_substrate.py --range 0-20       # Process range
    python scripts/reconstruct_substrate.py --dry-run           # Show chapters, no API calls
    python scripts/reconstruct_substrate.py --overwrite         # Reprocess already-done chapters
    python scripts/reconstruct_substrate.py --assemble          # Skip extraction, just assemble
    python scripts/reconstruct_substrate.py --limit 5           # Process first N chapters only
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
OUTPUT_DIR = PROJECT_ROOT / "output" / "substrate"
SEGMENTS_DIR = OUTPUT_DIR / "segments"
ASSEMBLED_FILE = OUTPUT_DIR / "restored_substrate.md"
DATA_FILE = OUTPUT_DIR / "substrate_data.json"


# ---------------------------------------------------------------------------
# Enums: Narrative episodes in the cosmological sequence
# ---------------------------------------------------------------------------

class NarrativeEpisode(str, Enum):
    """The cosmological narrative section this substrate segment belongs to.

    The episodes follow the established Manichaean cosmogonic sequence,
    which the Wars of YHWH analysis confirmed parallels the Šābuhragān
    architecture: Beloved → Conflagration → Trenches → Seat of Watchers
    → Border of the Father.
    """

    # I. THE TWO PRINCIPLES — The primordial dualism
    LAND_OF_LIGHT = "land_of_light"
    FATHER_OF_GREATNESS = "father_of_greatness"
    FIVE_SHEKHINAS = "five_shekhinas"
    LAND_OF_DARKNESS = "land_of_darkness"
    KING_OF_DARKNESS = "king_of_darkness"

    # II. THE FIRST EVOCATION — Mother of Life, First Man, the Battle
    MOTHER_OF_LIFE = "mother_of_life"
    FIRST_MAN = "first_man"
    FIVE_SONS_OF_FIRST_MAN = "five_sons_of_first_man"
    BATTLE_AND_DEFEAT = "battle_and_defeat"
    SWALLOWING_OF_LIGHT = "swallowing_of_light"

    # III. THE SECOND EVOCATION — Living Spirit, Rescue, Cosmic Construction
    CALL_AND_ANSWER = "call_and_answer"
    LIVING_SPIRIT = "living_spirit"
    RESCUE_OF_FIRST_MAN = "rescue_of_first_man"
    COSMIC_CONSTRUCTION = "cosmic_construction"
    FIRMAMENTS_AND_EARTHS = "firmaments_and_earths"
    SUN_AND_MOON = "sun_and_moon"
    STARS_AND_ZODIAC = "stars_and_zodiac"
    COSMIC_WHEEL = "cosmic_wheel"

    # IV. THE THIRD CREATION — Ambassador, Column of Glory, Three Vessels
    THIRD_AMBASSADOR = "third_ambassador"
    COLUMN_OF_GLORY = "column_of_glory"
    THREE_VESSELS = "three_vessels"
    LIGHT_REFINEMENT = "light_refinement"
    JESUS_THE_SPLENDOUR = "jesus_the_splendour"

    # V. CREATION AND AWAKENING OF HUMANITY
    CREATION_OF_ADAM = "creation_of_adam"
    AWAKENING_OF_ADAM = "awakening_of_adam"
    EVE_AND_REPRODUCTION = "eve_and_reproduction"
    SETH_AND_SUCCESSION = "seth_and_succession"

    # VI. THE ANTHROPOLOGY — The human being, Light Mind, Old Man / New Man
    FIVE_FOLD_HUMAN = "five_fold_human"
    LIGHT_MIND_NOUS = "light_mind_nous"
    OLD_MAN_NEW_MAN = "old_man_new_man"
    SOUL_IN_BODY = "soul_in_body"
    THREE_IMAGES = "three_images"
    DEATH_AND_JUDGMENT = "death_and_judgment"

    # VII. THE CORRESPONDENTIAL SYSTEM — Light in nature, body correspondences
    LIGHT_IN_NATURE = "light_in_nature"
    TREES_AND_PLANTS = "trees_and_plants"
    FOOD_AND_DIGESTION = "food_and_digestion"
    ANIMALS_AND_CREATURES = "animals_and_creatures"
    BODY_CORRESPONDENCES = "body_correspondences"
    ELEMENTS_IN_NATURE = "elements_in_nature"
    COSMIC_WEATHER = "cosmic_weather"

    # VIII. THE ESCHATOLOGY — Last Statue, Great Fire, New Earth
    LAST_STATUE = "last_statue"
    GREAT_FIRE = "great_fire"
    FINAL_SEPARATION = "final_separation"
    NEW_EARTH = "new_earth"

    # IX. THE PROPHETIC CHAIN — Succession of messengers
    PROPHETIC_SUCCESSION = "prophetic_succession"
    ZOROASTER = "zoroaster"
    BUDDHA = "buddha"

    # X. THE COSMOLOGICAL MECHANISM — General cosmic operations
    COSMIC_MECHANISM = "cosmic_mechanism"
    TWELVE_ZODIAC = "twelve_zodiac"
    FIVE_ELEMENTS_SYSTEM = "five_elements_system"
    CONDUITS_AND_CHANNELS = "conduits_and_channels"

    # Catch-all for substrate that doesn't fit the above
    OTHER_COSMOLOGICAL = "other_cosmological"


class SegmentType(str, Enum):
    """Classification of each text segment."""
    SUBSTRATE = "substrate"
    FRAME = "frame"
    PASTORAL = "pastoral"
    NT_OVERLAY = "nt_overlay"
    MIXED = "mixed"
    TRANSITION = "transition"


class ConfidenceLevel(str, Enum):
    """Confidence in the classification."""
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


# ---------------------------------------------------------------------------
# Pydantic models for structured output
# ---------------------------------------------------------------------------

class SubstrateSegment(BaseModel):
    """A single identified segment from the teaching text."""
    segment_number: int = Field(
        description="Sequential order of this segment within the chapter (1, 2, 3...)"
    )
    original_text: str = Field(
        description="The original text of this segment, exactly as it appears in the chapter"
    )
    segment_type: SegmentType = Field(
        description=(
            "Classification of the segment. "
            "SUBSTRATE: Pre-Mani cosmological/correspondential teaching — descriptions "
            "of cosmic events, divine beings, light-dark dynamics, five-fold systems, "
            "body correspondences, discrete degrees, call-and-response. "
            "FRAME: Hagiographic wrapper — 'Once again the enlightener speaks to his "
            "disciples:', 'Then the disciples questioned...', closing praise formulas. "
            "PASTORAL: Church rules, ethics, fasting, prayer, alms, catechumen instruction. "
            "NT_OVERLAY: Citations of Jesus/Paul, Christian theological additions. "
            "MIXED: Contains both substrate and non-substrate content interleaved. "
            "TRANSITION: A question or setup that introduces substrate content."
        )
    )
    narrative_episode: Optional[NarrativeEpisode] = Field(
        default=None,
        description=(
            "For SUBSTRATE or MIXED segments only: which episode of the cosmological "
            "sequence does this teaching belong to? Must be one of the defined episodes. "
            "NULL for FRAME, PASTORAL, NT_OVERLAY segments."
        )
    )
    extracted_teaching: Optional[str] = Field(
        default=None,
        description=(
            "For SUBSTRATE or MIXED segments: the core cosmological/correspondential "
            "teaching extracted from this segment, STRIPPED of any editorial framing. "
            "Remove 'the enlightener speaks:', 'once again he says:', etc. "
            "Preserve the actual teaching content, lacunae [...], and editorial "
            "restorations [text]. Keep manuscript page markers ⟨p.N⟩. "
            "Make it read as a continuous teaching passage. "
            "NULL for FRAME, PASTORAL segments that contain no substrate."
        )
    )
    narrative_summary: Optional[str] = Field(
        default=None,
        description=(
            "For SUBSTRATE segments: a brief (1-2 sentence) summary of what this "
            "segment teaches about the cosmological narrative. What cosmic event, "
            "structure, or principle is being described? NULL for non-substrate."
        )
    )
    confidence: ConfidenceLevel = Field(
        description="Confidence in the classification"
    )


class ChapterExtraction(BaseModel):
    """Complete extraction result for one chapter."""
    chapter_number: int = Field(
        description="Chapter number (0 for Introduction)"
    )
    chapter_title: str = Field(
        description="Title of the chapter"
    )
    total_segments: int = Field(
        description="Total number of segments identified"
    )
    substrate_segments: int = Field(
        description="Number of segments classified as SUBSTRATE or MIXED with extracted content"
    )
    substrate_percentage: float = Field(
        description="Estimated percentage of the chapter's teaching text that is substrate (0-100)"
    )
    chapter_assessment: str = Field(
        description=(
            "Brief assessment of this chapter's relationship to the substrate. "
            "Is it mostly substrate with light framing? Mostly pastoral with "
            "embedded substrate fragments? Pure frame with no substrate? etc."
        )
    )
    segments: list[SubstrateSegment] = Field(
        description="All identified segments, in text order"
    )


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a scholar specializing in Manichaean textual criticism and the reconstruction \
of source documents from composite texts. You are working on recovering the original \
pre-Mani cosmological substrate from the Coptic Kephalaia of the Teacher.

## BACKGROUND

The Kephalaia of the Teacher is a composite text containing multiple layers:

1. **THE SUBSTRATE** (Layer 1 — what we are recovering):
   A pre-Mani cosmological and correspondential teaching system. This is the \
   original body of knowledge that Mani inherited from the Elcesaite/Jewish-Christian \
   and Iranian religious traditions. It describes:
   - The Two Principles: the Land of Light (Father of Greatness, Five Shekhinas) \
     and the Land of Darkness (King of Darkness, five dark elements)
   - The First Evocation: Mother of Life, First Man (Ohrmizd), his five sons (the \
     five light elements as armor), the battle, defeat, swallowing of light
   - The Living Spirit's rescue: Call and Answer, cosmic construction from archon \
     bodies (firmaments, earths, sun, moon, stars, zodiac, wheel)
   - The Third Creation: Third Ambassador, Column of Glory, Three Vessels (Sun, \
     Moon, Column) as the light-refinement mechanism
   - Human creation and awakening: Adam created by archons to trap light, Jesus \
     the Splendour awakens Adam
   - The five-fold anthropology: five aspects of the human being, Light Mind (Nous), \
     Old Man vs New Man
   - The correspondential system: light trapped in nature, body-correspondence \
     maps, five elements in natural forms
   - The eschatology: Last Statue, Great Fire, final separation, New Earth

   This substrate uses characteristic vocabulary: storehouses, firmaments, aeons, \
   emanations, rulers, archons, elements, mixture, vessels, principalities, zodiac, \
   constructed, fashioned, discharged, crucified (= light crucified in matter), \
   separation, evocation, call and answer, column of glory.

2. **THE HAGIOGRAPHIC FRAME** (Layer 3):
   The Q&A format imposed by the editors: "Once again the enlightener speaks to his \
   disciples...", "The disciples questioned the apostle...", "When his disciples heard \
   these things, they rejoiced and glorified him..." These are editorial formulas \
   wrapping the teaching content.

3. **THE NT/CHRISTIAN OVERLAY** (Layer 2):
   References to Jesus Christ, Gospel citations, Pauline language, Christian theological \
   additions that were overlaid onto the original teaching.

4. **THE PASTORAL LAYER** (Layer 4):
   Church rules, ethics instruction, fasting regulations, prayer formulas, catechumen \
   instruction, alms-giving regulations — ecclesiastical administration.

## YOUR TASK

For each chapter's teaching text, identify distinct segments and classify each one. \
The key distinction is between SUBSTRATE (the original cosmological teaching) and \
everything else (frame, pastoral, NT overlay).

**How to recognize substrate:**
- Describes cosmic events, structures, or beings in the cosmogonic narrative
- Uses cosmological vocabulary (five elements, storehouses, firmaments, vessels, etc.)
- Teaches about the nature of light, darkness, mixture, separation
- Describes the five-fold structure of anything (five shekhinas, five sons, five elements)
- Explains body-correspondence systems or natural-spiritual mappings
- Describes the mechanism of light refinement (three vessels, column of glory)
- Teaches about the Light Mind, the Old Man / New Man, soul-in-body dynamics
- Has the quality of a TEACHING about reality, not a rule for behavior

**How to recognize frame:**
- Opening formulas: "Once again the enlightener speaks...", "His disciples say to him..."
- Closing formulas: "When they heard this, they rejoiced...", "He sat down"
- Transitions: "then he says to them:", "he speaks thus:"
- Question formulas: "We beseech you, our master, that you may instruct us about..."

**How to recognize pastoral:**
- Fasting rules, prayer regulations, alms-giving instructions
- Church organization, catechumen vs elect distinctions
- Ethical instruction about personal behavior (not cosmic)
- Sin, righteousness, judgment in a behavioral (not cosmological) sense

**How to recognize NT overlay:**
- Citation of Jesus's words from the Gospels
- Pauline theological language (grace, justification)
- Christian titles used non-cosmologically (Christ, Son of God as piety, not as cosmic role)

## EXTRACTION RULES

1. **Strip the frame, keep the content.** When a segment begins "the enlightener speaks \
   to his disciples:" followed by cosmological teaching, the extracted_teaching should \
   contain ONLY the cosmological teaching, not the framing formula.

2. **Preserve the exact teaching words.** Do not paraphrase, summarize, or modernize. \
   Extract the teaching text verbatim (minus the frame).

3. **Preserve lacunae and restorations.** Keep [...], [restored text], and ⟨p.N⟩ markers.

4. **Handle mixed segments carefully.** Some paragraphs contain substrate teaching \
   with pastoral additions woven in. Mark these as MIXED and extract only the \
   substrate portion.

5. **Questions can be substrate.** "Tell us about the five storehouses" is a \
   TRANSITION that reveals the topic. If the question contains cosmological \
   content, it may be SUBSTRATE or TRANSITION.

6. **Assign narrative episodes accurately.** Each substrate segment should be \
   assigned to the specific episode it describes. If a segment covers multiple \
   episodes, assign the primary one.

7. **When in doubt between substrate and pastoral:** If the teaching describes how \
   a cosmic mechanism works (even if applied ethically), it is SUBSTRATE. If it \
   prescribes behavior without cosmic grounding, it is PASTORAL.
"""


# ---------------------------------------------------------------------------
# Client setup
# ---------------------------------------------------------------------------

def create_client() -> OpenAI:
    """Create OpenAI client configured for Azure Foundry."""
    if not SECRETS_PATH.exists():
        print(f"ERROR: Secrets file not found at {SECRETS_PATH}")
        sys.exit(1)

    config = dotenv_values(SECRETS_PATH)
    return OpenAI(
        base_url=config["OPENAI_ENDPOINT"],
        api_key=config["OPENAI_API_KEY"],
    )


def get_deployment() -> str:
    """Get the model deployment name."""
    config = dotenv_values(SECRETS_PATH)
    return config["OPENAI_DEPLOYMENT"]


# ---------------------------------------------------------------------------
# Load cleaned chapters
# ---------------------------------------------------------------------------

def load_chapters() -> list[dict]:
    """Load all cleaned chapter JSON files, sorted by chapter number."""
    chapters = []
    for path in sorted(CHAPTERS_DIR.glob("ch_*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        chapters.append(data)
    return chapters


def load_chapter(chapter_num: int) -> dict | None:
    """Load a single chapter by number."""
    path = CHAPTERS_DIR / f"ch_{chapter_num:03d}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# LLM extraction
# ---------------------------------------------------------------------------

def extract_substrate(
    client: OpenAI, deployment: str, chapter: dict
) -> ChapterExtraction | None:
    """Send a chapter to GPT-5.2 for substrate extraction.

    Returns a validated ChapterExtraction model, or None on failure.
    """
    ch_num = chapter["chapter_number"]
    title = chapter.get("title", f"Chapter {ch_num}")
    teaching = chapter.get("teaching_text", "")

    if not teaching.strip():
        print(f"  [skip] Ch.{ch_num} — empty teaching text")
        return None

    # Include Gardner synopsis as context (helps model understand the chapter)
    gardner = chapter.get("gardner_synopsis", "")
    context_block = ""
    if gardner.strip():
        context_block = (
            f"\n\n--- GARDNER SCHOLARLY SYNOPSIS (for context only — do NOT extract from this) ---\n"
            f"{gardner}\n"
            f"--- END SYNOPSIS ---\n"
        )

    user_msg = (
        f"Analyze the following chapter from the Kephalaia of the Teacher and extract "
        f"the substrate segments according to your instructions.\n\n"
        f"Chapter {ch_num}: {title}\n"
        f"{context_block}\n"
        f"--- TEACHING TEXT ---\n\n"
        f"{teaching}\n\n"
        f"--- END TEACHING TEXT ---"
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
                raise ValueError("No structured output returned (parsed is None)")
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
                print(f"  (filter hit, retry {attempt}/{max_retries} in {wait}s)...",
                      end=" ", flush=True)
                time.sleep(wait)
                continue
            print(f"  API error: {e}")
            if attempt < max_retries:
                wait = backoff
                time.sleep(wait)
                backoff *= 2
                continue
            return None

        except Exception as e:
            err_str = str(e)
            if "content_filter" in err_str.lower() and attempt < max_retries:
                wait = attempt * 10
                print(f"  (filter exception, retry {attempt}/{max_retries} in {wait}s)...",
                      end=" ", flush=True)
                time.sleep(wait)
                continue
            print(f"  ERROR Ch.{ch_num}: {e}")
            if attempt < max_retries:
                wait = backoff
                time.sleep(wait)
                backoff *= 2
                continue
            return None

    return None


# ---------------------------------------------------------------------------
# Save / load segment data
# ---------------------------------------------------------------------------

def save_extraction(extraction: ChapterExtraction) -> None:
    """Save extraction result to JSON."""
    SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)
    path = SEGMENTS_DIR / f"ch_{extraction.chapter_number:03d}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(extraction.model_dump(), f, indent=2, ensure_ascii=False)


def load_extraction(chapter_num: int) -> dict | None:
    """Load an existing extraction result."""
    path = SEGMENTS_DIR / f"ch_{chapter_num:03d}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def is_extracted(chapter_num: int) -> bool:
    """Check if a chapter has already been extracted."""
    return (SEGMENTS_DIR / f"ch_{chapter_num:03d}.json").exists()


# ---------------------------------------------------------------------------
# Assembly: reconstruct the substrate from all extractions
# ---------------------------------------------------------------------------

# Narrative episode ordering for the cosmological sequence
EPISODE_ORDER = [
    # I. The Two Principles
    NarrativeEpisode.LAND_OF_LIGHT,
    NarrativeEpisode.FATHER_OF_GREATNESS,
    NarrativeEpisode.FIVE_SHEKHINAS,
    NarrativeEpisode.LAND_OF_DARKNESS,
    NarrativeEpisode.KING_OF_DARKNESS,
    # II. The First Evocation
    NarrativeEpisode.MOTHER_OF_LIFE,
    NarrativeEpisode.FIRST_MAN,
    NarrativeEpisode.FIVE_SONS_OF_FIRST_MAN,
    NarrativeEpisode.BATTLE_AND_DEFEAT,
    NarrativeEpisode.SWALLOWING_OF_LIGHT,
    # III. The Second Evocation
    NarrativeEpisode.CALL_AND_ANSWER,
    NarrativeEpisode.LIVING_SPIRIT,
    NarrativeEpisode.RESCUE_OF_FIRST_MAN,
    NarrativeEpisode.COSMIC_CONSTRUCTION,
    NarrativeEpisode.FIRMAMENTS_AND_EARTHS,
    NarrativeEpisode.SUN_AND_MOON,
    NarrativeEpisode.STARS_AND_ZODIAC,
    NarrativeEpisode.COSMIC_WHEEL,
    # IV. The Third Creation
    NarrativeEpisode.THIRD_AMBASSADOR,
    NarrativeEpisode.COLUMN_OF_GLORY,
    NarrativeEpisode.THREE_VESSELS,
    NarrativeEpisode.LIGHT_REFINEMENT,
    NarrativeEpisode.JESUS_THE_SPLENDOUR,
    # V. Creation and Awakening
    NarrativeEpisode.CREATION_OF_ADAM,
    NarrativeEpisode.AWAKENING_OF_ADAM,
    NarrativeEpisode.EVE_AND_REPRODUCTION,
    NarrativeEpisode.SETH_AND_SUCCESSION,
    # VI. The Anthropology
    NarrativeEpisode.FIVE_FOLD_HUMAN,
    NarrativeEpisode.LIGHT_MIND_NOUS,
    NarrativeEpisode.OLD_MAN_NEW_MAN,
    NarrativeEpisode.SOUL_IN_BODY,
    NarrativeEpisode.THREE_IMAGES,
    NarrativeEpisode.DEATH_AND_JUDGMENT,
    # VII. The Correspondential System
    NarrativeEpisode.LIGHT_IN_NATURE,
    NarrativeEpisode.TREES_AND_PLANTS,
    NarrativeEpisode.FOOD_AND_DIGESTION,
    NarrativeEpisode.ANIMALS_AND_CREATURES,
    NarrativeEpisode.BODY_CORRESPONDENCES,
    NarrativeEpisode.ELEMENTS_IN_NATURE,
    NarrativeEpisode.COSMIC_WEATHER,
    # VIII. The Eschatology
    NarrativeEpisode.LAST_STATUE,
    NarrativeEpisode.GREAT_FIRE,
    NarrativeEpisode.FINAL_SEPARATION,
    NarrativeEpisode.NEW_EARTH,
    # IX. The Prophetic Chain
    NarrativeEpisode.PROPHETIC_SUCCESSION,
    NarrativeEpisode.ZOROASTER,
    NarrativeEpisode.BUDDHA,
    # X. The Cosmological Mechanism
    NarrativeEpisode.COSMIC_MECHANISM,
    NarrativeEpisode.TWELVE_ZODIAC,
    NarrativeEpisode.FIVE_ELEMENTS_SYSTEM,
    NarrativeEpisode.CONDUITS_AND_CHANNELS,
    # Catch-all
    NarrativeEpisode.OTHER_COSMOLOGICAL,
]

# Human-readable section titles for the narrative
SECTION_STRUCTURE = {
    "I. THE TWO PRINCIPLES": [
        NarrativeEpisode.LAND_OF_LIGHT,
        NarrativeEpisode.FATHER_OF_GREATNESS,
        NarrativeEpisode.FIVE_SHEKHINAS,
        NarrativeEpisode.LAND_OF_DARKNESS,
        NarrativeEpisode.KING_OF_DARKNESS,
    ],
    "II. THE FIRST EVOCATION": [
        NarrativeEpisode.MOTHER_OF_LIFE,
        NarrativeEpisode.FIRST_MAN,
        NarrativeEpisode.FIVE_SONS_OF_FIRST_MAN,
        NarrativeEpisode.BATTLE_AND_DEFEAT,
        NarrativeEpisode.SWALLOWING_OF_LIGHT,
    ],
    "III. THE SECOND EVOCATION — THE LIVING SPIRIT": [
        NarrativeEpisode.CALL_AND_ANSWER,
        NarrativeEpisode.LIVING_SPIRIT,
        NarrativeEpisode.RESCUE_OF_FIRST_MAN,
        NarrativeEpisode.COSMIC_CONSTRUCTION,
        NarrativeEpisode.FIRMAMENTS_AND_EARTHS,
        NarrativeEpisode.SUN_AND_MOON,
        NarrativeEpisode.STARS_AND_ZODIAC,
        NarrativeEpisode.COSMIC_WHEEL,
    ],
    "IV. THE THIRD CREATION — LIGHT REFINEMENT": [
        NarrativeEpisode.THIRD_AMBASSADOR,
        NarrativeEpisode.COLUMN_OF_GLORY,
        NarrativeEpisode.THREE_VESSELS,
        NarrativeEpisode.LIGHT_REFINEMENT,
        NarrativeEpisode.JESUS_THE_SPLENDOUR,
    ],
    "V. CREATION AND AWAKENING OF HUMANITY": [
        NarrativeEpisode.CREATION_OF_ADAM,
        NarrativeEpisode.AWAKENING_OF_ADAM,
        NarrativeEpisode.EVE_AND_REPRODUCTION,
        NarrativeEpisode.SETH_AND_SUCCESSION,
    ],
    "VI. THE ANTHROPOLOGY": [
        NarrativeEpisode.FIVE_FOLD_HUMAN,
        NarrativeEpisode.LIGHT_MIND_NOUS,
        NarrativeEpisode.OLD_MAN_NEW_MAN,
        NarrativeEpisode.SOUL_IN_BODY,
        NarrativeEpisode.THREE_IMAGES,
        NarrativeEpisode.DEATH_AND_JUDGMENT,
    ],
    "VII. THE CORRESPONDENTIAL SYSTEM": [
        NarrativeEpisode.LIGHT_IN_NATURE,
        NarrativeEpisode.TREES_AND_PLANTS,
        NarrativeEpisode.FOOD_AND_DIGESTION,
        NarrativeEpisode.ANIMALS_AND_CREATURES,
        NarrativeEpisode.BODY_CORRESPONDENCES,
        NarrativeEpisode.ELEMENTS_IN_NATURE,
        NarrativeEpisode.COSMIC_WEATHER,
    ],
    "VIII. THE ESCHATOLOGY": [
        NarrativeEpisode.LAST_STATUE,
        NarrativeEpisode.GREAT_FIRE,
        NarrativeEpisode.FINAL_SEPARATION,
        NarrativeEpisode.NEW_EARTH,
    ],
    "IX. THE PROPHETIC CHAIN": [
        NarrativeEpisode.PROPHETIC_SUCCESSION,
        NarrativeEpisode.ZOROASTER,
        NarrativeEpisode.BUDDHA,
    ],
    "X. THE COSMOLOGICAL MECHANISM": [
        NarrativeEpisode.COSMIC_MECHANISM,
        NarrativeEpisode.TWELVE_ZODIAC,
        NarrativeEpisode.FIVE_ELEMENTS_SYSTEM,
        NarrativeEpisode.CONDUITS_AND_CHANNELS,
    ],
    "XI. OTHER COSMOLOGICAL TEACHING": [
        NarrativeEpisode.OTHER_COSMOLOGICAL,
    ],
}

# Episode display names
EPISODE_NAMES = {
    NarrativeEpisode.LAND_OF_LIGHT: "The Land of Light",
    NarrativeEpisode.FATHER_OF_GREATNESS: "The Father of Greatness",
    NarrativeEpisode.FIVE_SHEKHINAS: "The Five Shekhinas",
    NarrativeEpisode.LAND_OF_DARKNESS: "The Land of Darkness",
    NarrativeEpisode.KING_OF_DARKNESS: "The King of Darkness",
    NarrativeEpisode.MOTHER_OF_LIFE: "The Mother of Life",
    NarrativeEpisode.FIRST_MAN: "The First Man (Ohrmizd)",
    NarrativeEpisode.FIVE_SONS_OF_FIRST_MAN: "The Five Sons — The Armour of Light",
    NarrativeEpisode.BATTLE_AND_DEFEAT: "The Battle and Defeat",
    NarrativeEpisode.SWALLOWING_OF_LIGHT: "The Swallowing of Light",
    NarrativeEpisode.CALL_AND_ANSWER: "The Call and the Answer",
    NarrativeEpisode.LIVING_SPIRIT: "The Living Spirit",
    NarrativeEpisode.RESCUE_OF_FIRST_MAN: "The Rescue of the First Man",
    NarrativeEpisode.COSMIC_CONSTRUCTION: "The Cosmic Construction",
    NarrativeEpisode.FIRMAMENTS_AND_EARTHS: "The Firmaments and the Earths",
    NarrativeEpisode.SUN_AND_MOON: "The Sun and the Moon",
    NarrativeEpisode.STARS_AND_ZODIAC: "The Stars and the Zodiac",
    NarrativeEpisode.COSMIC_WHEEL: "The Cosmic Wheel",
    NarrativeEpisode.THIRD_AMBASSADOR: "The Third Ambassador",
    NarrativeEpisode.COLUMN_OF_GLORY: "The Column of Glory (Perfect Man)",
    NarrativeEpisode.THREE_VESSELS: "The Three Vessels",
    NarrativeEpisode.LIGHT_REFINEMENT: "The Mechanism of Light Refinement",
    NarrativeEpisode.JESUS_THE_SPLENDOUR: "Jesus the Splendour",
    NarrativeEpisode.CREATION_OF_ADAM: "The Creation of Adam",
    NarrativeEpisode.AWAKENING_OF_ADAM: "The Awakening of Adam",
    NarrativeEpisode.EVE_AND_REPRODUCTION: "Eve and the Trap of Reproduction",
    NarrativeEpisode.SETH_AND_SUCCESSION: "Seth and the Succession",
    NarrativeEpisode.FIVE_FOLD_HUMAN: "The Five-Fold Human Being",
    NarrativeEpisode.LIGHT_MIND_NOUS: "The Light Mind (Nous)",
    NarrativeEpisode.OLD_MAN_NEW_MAN: "The Old Man and the New Man",
    NarrativeEpisode.SOUL_IN_BODY: "The Soul in the Body",
    NarrativeEpisode.THREE_IMAGES: "The Three Images in the Person",
    NarrativeEpisode.DEATH_AND_JUDGMENT: "Death and Judgment",
    NarrativeEpisode.LIGHT_IN_NATURE: "Light Trapped in Nature",
    NarrativeEpisode.TREES_AND_PLANTS: "Trees and Plants",
    NarrativeEpisode.FOOD_AND_DIGESTION: "Food and Digestion",
    NarrativeEpisode.ANIMALS_AND_CREATURES: "Animals and Creatures",
    NarrativeEpisode.BODY_CORRESPONDENCES: "Body Correspondences",
    NarrativeEpisode.ELEMENTS_IN_NATURE: "The Elements in Nature",
    NarrativeEpisode.COSMIC_WEATHER: "Cosmic Weather",
    NarrativeEpisode.LAST_STATUE: "The Last Statue",
    NarrativeEpisode.GREAT_FIRE: "The Great Fire",
    NarrativeEpisode.FINAL_SEPARATION: "The Final Separation",
    NarrativeEpisode.NEW_EARTH: "The New Earth",
    NarrativeEpisode.PROPHETIC_SUCCESSION: "The Prophetic Succession",
    NarrativeEpisode.ZOROASTER: "Zoroaster",
    NarrativeEpisode.BUDDHA: "The Buddha",
    NarrativeEpisode.COSMIC_MECHANISM: "Cosmic Mechanism",
    NarrativeEpisode.TWELVE_ZODIAC: "The Twelve Signs of the Zodiac",
    NarrativeEpisode.FIVE_ELEMENTS_SYSTEM: "The Five Elements System",
    NarrativeEpisode.CONDUITS_AND_CHANNELS: "The Conduits and Channels",
    NarrativeEpisode.OTHER_COSMOLOGICAL: "Other Cosmological Teaching",
}


def assemble_substrate() -> str:
    """Assemble all extracted substrate segments into a continuous document.

    Returns the markdown text of the restored substrate.
    """
    # Load all extraction files
    extractions = []
    for path in sorted(SEGMENTS_DIR.glob("ch_*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        extractions.append(data)

    if not extractions:
        print("ERROR: No extraction files found. Run extraction first.")
        return ""

    # Collect all substrate segments, grouped by narrative episode
    episode_segments: dict[str, list[dict]] = {}
    total_substrate = 0
    total_segments = 0
    total_chapters = len(extractions)

    for ext in extractions:
        ch_num = ext["chapter_number"]
        for seg in ext["segments"]:
            total_segments += 1
            seg_type = seg["segment_type"]

            if seg_type in ("substrate", "mixed") and seg.get("extracted_teaching"):
                episode = seg.get("narrative_episode", "other_cosmological")
                if episode is None:
                    episode = "other_cosmological"
                if episode not in episode_segments:
                    episode_segments[episode] = []
                episode_segments[episode].append({
                    "chapter": ch_num,
                    "text": seg["extracted_teaching"],
                    "summary": seg.get("narrative_summary", ""),
                    "confidence": seg.get("confidence", "moderate"),
                    "original": seg.get("original_text", ""),
                })
                total_substrate += 1

    # Build the document
    lines = []
    lines.append("# The Restored Substrate")
    lines.append("")
    lines.append("## A Reconstruction of the Pre-Mani Cosmological Teaching")
    lines.append("## from the Coptic Kephalaia of the Teacher")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("### Methodology")
    lines.append("")
    lines.append(
        "This document reconstructs the original cosmological and correspondential "
        "teaching substrate that underlies the Kephalaia of the Teacher. The Kephalaia's "
        "123 chapters represent an editorial arrangement imposed on top of a pre-existing "
        "body of teaching. Using GPT-5.2 structured extraction, each chapter's teaching "
        "text was analyzed to identify and extract substrate segments — the original "
        "cosmological content — stripped of the hagiographic Q&A frame, pastoral additions, "
        "and NT/Christian overlay."
    )
    lines.append("")
    lines.append(
        "The substrate is reorganized here by its own internal cosmological logic — the "
        "narrative sequence of the Manichaean cosmogony — rather than by the imposed "
        "chapter structure. The sequence parallels the Šābuhragān architecture confirmed "
        "in the Wars of YHWH consonantal analysis: Beloved → Conflagration → Trenches → "
        "Seat of Watchers → Border of the Father."
    )
    lines.append("")
    lines.append(f"**Source**: {total_chapters} chapters analyzed")
    lines.append(f"**Extracted**: {total_substrate} substrate segments from {total_segments} total segments")
    lines.append(f"**Episodes populated**: {len(episode_segments)} of {len(EPISODE_ORDER)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Emit sections in narrative order
    for section_title, episodes in SECTION_STRUCTURE.items():
        # Check if any episodes in this section have content
        section_has_content = any(
            ep.value in episode_segments for ep in episodes
        )
        if not section_has_content:
            continue

        lines.append(f"## {section_title}")
        lines.append("")

        for episode in episodes:
            if episode.value not in episode_segments:
                continue

            segments = episode_segments[episode.value]
            ep_name = EPISODE_NAMES.get(episode, episode.value)

            lines.append(f"### {ep_name}")
            lines.append("")

            # Sort segments by chapter number for consistent ordering
            segments.sort(key=lambda s: s["chapter"])

            for seg in segments:
                # Add source reference as a small annotation
                lines.append(f"*[Keph. {seg['chapter']}]*")
                lines.append("")
                lines.append(seg["text"])
                lines.append("")

            lines.append("---")
            lines.append("")

    # Add statistics appendix
    lines.append("## APPENDIX: Extraction Statistics")
    lines.append("")
    lines.append("### Segments by Narrative Episode")
    lines.append("")
    lines.append("| Episode | Segments | Chapters |")
    lines.append("|---------|----------|----------|")

    for episode in EPISODE_ORDER:
        if episode.value in episode_segments:
            segs = episode_segments[episode.value]
            ep_name = EPISODE_NAMES.get(episode, episode.value)
            chapters = sorted(set(s["chapter"] for s in segs))
            ch_str = ", ".join(str(c) for c in chapters)
            lines.append(f"| {ep_name} | {len(segs)} | {ch_str} |")

    lines.append("")

    # Episode coverage summary
    populated = sum(1 for ep in EPISODE_ORDER if ep.value in episode_segments)
    lines.append(f"**Total episodes populated**: {populated}/{len(EPISODE_ORDER)}")
    lines.append(f"**Total substrate segments**: {total_substrate}")
    lines.append("")

    return "\n".join(lines)


def save_assembly(text: str) -> None:
    """Save the assembled substrate document."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(ASSEMBLED_FILE, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  Saved assembled substrate to {ASSEMBLED_FILE}")


def save_data_summary(extractions: list[dict]) -> None:
    """Save a JSON summary of all extraction data."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    summary = {
        "total_chapters": len(extractions),
        "total_segments": sum(e.get("total_segments", 0) for e in extractions),
        "total_substrate": sum(e.get("substrate_segments", 0) for e in extractions),
        "chapters": [],
    }

    for ext in extractions:
        ch_summary = {
            "chapter_number": ext["chapter_number"],
            "title": ext.get("chapter_title", ""),
            "total_segments": ext.get("total_segments", 0),
            "substrate_segments": ext.get("substrate_segments", 0),
            "substrate_percentage": ext.get("substrate_percentage", 0),
            "assessment": ext.get("chapter_assessment", ""),
            "episodes": [],
        }
        for seg in ext.get("segments", []):
            if seg["segment_type"] in ("substrate", "mixed") and seg.get("narrative_episode"):
                ch_summary["episodes"].append(seg["narrative_episode"])
        ch_summary["episodes"] = sorted(set(ch_summary["episodes"]))
        summary["chapters"].append(ch_summary)

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"  Saved data summary to {DATA_FILE}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reconstruct the pre-Mani substrate from the Kephalaia"
    )
    parser.add_argument(
        "--chapter", "-c", type=int, default=None,
        help="Process a single chapter (by number)"
    )
    parser.add_argument(
        "--range", "-r", type=str, default=None,
        help="Process a range of chapters (e.g. '0-20')"
    )
    parser.add_argument(
        "--limit", "-l", type=int, default=None,
        help="Process only the first N chapters"
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true",
        help="Show what would be processed without making API calls"
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Reprocess chapters that already have extraction results"
    )
    parser.add_argument(
        "--assemble", "-a", action="store_true",
        help="Skip extraction, just assemble existing results into the substrate document"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Assembly-only mode
    if args.assemble:
        print("Assembling substrate from existing extractions...")
        text = assemble_substrate()
        if text:
            save_assembly(text)

            # Also save data summary
            extractions = []
            for path in sorted(SEGMENTS_DIR.glob("ch_*.json")):
                with open(path, encoding="utf-8") as f:
                    extractions.append(json.load(f))
            save_data_summary(extractions)

        return

    # Load chapters
    all_chapters = load_chapters()
    if not all_chapters:
        print("ERROR: No cleaned chapters found in", CHAPTERS_DIR)
        sys.exit(1)

    print(f"Loaded {len(all_chapters)} cleaned chapters")

    # Determine which chapters to process
    if args.chapter is not None:
        chapters = [ch for ch in all_chapters if ch["chapter_number"] == args.chapter]
        if not chapters:
            print(f"ERROR: Chapter {args.chapter} not found")
            sys.exit(1)
    elif args.range:
        match = re.match(r"(\d+)-(\d+)", args.range)
        if not match:
            print("ERROR: Invalid range format. Use '0-20'")
            sys.exit(1)
        start, end = int(match.group(1)), int(match.group(2))
        chapters = [ch for ch in all_chapters if start <= ch["chapter_number"] <= end]
    else:
        chapters = all_chapters

    if args.limit:
        chapters = chapters[:args.limit]

    # Filter already-processed (unless --overwrite)
    if not args.overwrite:
        to_process = [ch for ch in chapters if not is_extracted(ch["chapter_number"])]
        skipped = len(chapters) - len(to_process)
        if skipped > 0:
            print(f"  Skipping {skipped} already-extracted chapters (use --overwrite to reprocess)")
        chapters = to_process

    if not chapters:
        print("Nothing to process. All chapters already extracted.")
        # Still assemble if we have data
        text = assemble_substrate()
        if text:
            save_assembly(text)
            extractions = []
            for path in sorted(SEGMENTS_DIR.glob("ch_*.json")):
                with open(path, encoding="utf-8") as f:
                    extractions.append(json.load(f))
            save_data_summary(extractions)
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
    print()

    # Process chapters
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

        extraction = extract_substrate(client, deployment, ch)
        if extraction is None:
            print("FAILED")
            errors.append(ch_num)
            continue

        save_extraction(extraction)
        n_sub = extraction.substrate_segments
        n_tot = extraction.total_segments
        pct = extraction.substrate_percentage
        print(f"OK — {n_sub}/{n_tot} substrate segments ({pct:.0f}%)")
        results.append(extraction.model_dump())

        # Brief pause between requests
        if i < len(chapters):
            time.sleep(0.5)

    # Summary
    print(f"\n{'='*60}")
    print(f"EXTRACTION COMPLETE")
    print(f"  Processed: {len(results)}")
    print(f"  Errors: {len(errors)}")
    if errors:
        print(f"  Failed chapters: {errors}")

    # Assemble the substrate
    print(f"\nAssembling substrate document...")
    text = assemble_substrate()
    if text:
        save_assembly(text)

    # Save data summary
    all_extractions = []
    for path in sorted(SEGMENTS_DIR.glob("ch_*.json")):
        with open(path, encoding="utf-8") as f:
            all_extractions.append(json.load(f))
    save_data_summary(all_extractions)

    print(f"\nDone.")


if __name__ == "__main__":
    main()
