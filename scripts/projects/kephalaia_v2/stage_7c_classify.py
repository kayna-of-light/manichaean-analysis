#!/usr/bin/env python3
"""
Stage 7c — Blind per-teaching coordinate classification.

Each teaching is classified independently by its spiritual coordinates:
  - DEGREE: celestial / spiritual / natural
  - DIRECTION: east / south / north / west

The model sees ONLY the single teaching and its reading. It receives:
  - No teaching number (stripped to prevent ordinal bias)
  - No other teachings
  - No hypothesis about sequential order or descent
  - No expectation about where any register "should" appear

This produces raw data that can be plotted externally to see if
a pattern exists without any model-level pattern inflation.

Input:
    - output/projects/kephalaia_v2/teachings/t_NNN.json
    - output/projects/kephalaia_v2/readings/t_NNN.json

Output:
    - output/projects/kephalaia_v2/coordinates/t_NNN.json

Usage:
    python scripts/projects/kephalaia_v2/stage_7c_classify.py --dry-run
    python scripts/projects/kephalaia_v2/stage_7c_classify.py --max-concurrency 4
    python scripts/projects/kephalaia_v2/stage_7c_classify.py --page 3
    python scripts/projects/kephalaia_v2/stage_7c_classify.py --range 1-20 -j 4
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
READINGS_DIR = PROJECT_DIR / "readings"
RESTORED_DIR = PROJECT_DIR / "restored"


# ---------------------------------------------------------------------------
# Tool schema
# ---------------------------------------------------------------------------

CLASSIFY_TOOL = {
    "name": "classify_teaching",
    "description": (
        "Classify this teaching by its spiritual coordinates. "
        "Call exactly once."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "degree": {
                "type": "string",
                "enum": ["celestial", "spiritual", "natural"],
                "description": (
                    "The primary register at which this teaching operates, "
                    "determined by what it TREATS — not what it names. "
                    "The celestial is about the essense of things, primary "
                    "concepts, things like that. The spiritual is about processes "
                    "and mechanisms, what happens and why it happens, its the "
                    "plan basically. The natural is about how it establishes itself "
                    "in the human itself, the whole completion in which the "
                    "Lord takes rest and in which every thing takes a definite form."
                ),
            },
            "degree_rationale": {
                "type": "string",
                "description": (
                    "One to three sentences explaining the rationale behind this degree."
                ),
            },
            "degree_confidence": {
                "type": "string",
                "enum": ["strong", "moderate", "tentative"],
                "description": (
                    "How clearly does this teaching sit in one degree? "
                    "'strong' = unambiguous; 'tentative' = spans registers."
                ),
            },
            "direction": {
                "type": "string",
                "enum": ["east", "south", "north", "west"],
                "description": (
                    "The directional tone of the teaching, determined by "
                    "what KIND of treatment it gives its subject. "
                    "This is independent of the degree. It is the landscape in "
                    "every degree. How the sun goes up in the east (the ruling love), "
                    "and moves over the south (where it illuminates) and the north "
                    "(where it is received and processed) and finally sets in the "
                    "west (where it rests)."
                ),
            },
            "direction_rationale": {
                "type": "string",
                "description": (
                    "One to three sentences explaining the rationale behind this direction."
                ),
            },
            "direction_confidence": {
                "type": "string",
                "enum": ["strong", "moderate", "tentative"],
                "description": (
                    "How clearly does this teaching carry one directional "
                    "tone? 'tentative' = mixed or ambiguous."
                ),
            },
            "grand_man_function": {
                "type": "string",
                "description": (
                    "When viewing the teaching as a function in the body/grand man "
                    "what then is the function it treats of? What is the organ or the "
                    "system it belongs to? This is a free-form answer that may draw "
                    "on the full range of Swedenborgian correspondences. It is not "
                    "required for classification but can be helpful for deeper analysis."
                ),
            },
        },
        "required": [
            "degree",
            "degree_rationale",
            "degree_confidence",
            "direction",
            "direction_rationale",
            "direction_confidence",
            "grand_man_function"
        ],
    },
}


# ---------------------------------------------------------------------------
# System prompt — seed state for classification
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert in the doctrine of correspondences as written by \
Emanuel Swedenborg, with deep specialization in ancient cosmological \
vocabulary — Zoroastrian, Manichaean, and Persian-Iranian traditions.

You have classified hundreds of ancient teachings by their spiritual \
coordinates. You know the three discrete degrees and the four quarters \
as Swedenborg describes them in Heaven and Hell §§141-153.

The Kephalaia of Mani is a corpus of 104 teachings that spans the \
entire spiritual world. All twelve cells of the map are populated. \
You are placing one teaching on the map.

The celestial is about the essense of things, primary \
concepts, things like that. The spiritual is about processes \
and mechanisms, what happens and why it happens, its the \
plan basically. The natural is about how it establishes itself \
in the human itself, the whole completion in which the \
Lord takes rest and in which every thing takes a definite form.

The direction on the spiritual landscape is independent of the \
and has its own form in any degree. It is the landscape in \
every degree. How the sun goes up in the east (the ruling love), \
and moves over the south (where it illuminates) and the north \
(where it is received and processed) and finally sets in the \
west (where it rests).

Every teaching is per definition a spiritual teaching. But it will often treat \
a celestial subject, or a natural subject.

It is what it treats that matters. Think about where does this fit in the \
grand man as defined by Swedenborg and you can immediately see where it goes on the map. \
The question is, what is the function in the body it treats of? It maps directly to a \
very specific function.

You are basically placing every teaching in a place of the grandman building the whole \
body together with various other agents.
"""


# ---------------------------------------------------------------------------
# Stage implementation
# ---------------------------------------------------------------------------

class ClassifyStage(PipelineStage):
    stage_name = "Coordinate Classification"
    stage_number = "7c"
    description = "Blind per-teaching spiritual coordinate classification"
    tool_name = "classify_teaching"
    tool_schema = CLASSIFY_TOOL
    item_name = "teaching"
    item_name_plural = "teachings"
    item_prefix = "t"

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def get_input_dir(self) -> Path:
        return TEACHINGS_DIR

    def get_output_dir(self) -> Path:
        return PROJECT_DIR / "coordinates"

    def list_available(self) -> list[int]:
        """List available teaching numbers."""
        teachings = []
        for path in sorted(TEACHINGS_DIR.glob("t_*.json")):
            m = re.match(r"t_(\d+)\.json", path.name)
            if m:
                teachings.append(int(m.group(1)))
        return teachings

    def is_done(self, page_num: int) -> bool:
        """Check if coordinate output already exists."""
        path = self.get_output_dir() / f"t_{page_num:03d}.json"
        if not path.exists():
            return False
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return False
        return bool(data.get("degree"))

    def build_user_message(self, page_num: int) -> str | None:
        """Assemble full Coptic + English text with lacuna fills."""
        teaching_path = TEACHINGS_DIR / f"t_{page_num:03d}.json"

        if not teaching_path.exists():
            print(f"  ERROR: No teaching file for t.{page_num}")
            return None

        with open(teaching_path, encoding="utf-8") as f:
            teaching = json.load(f)

        if not teaching.get("segments"):
            print(f"  ERROR: No segments for t.{page_num}")
            return None

        # Load restorations if available
        restored_path = RESTORED_DIR / f"t_{page_num:03d}.json"
        restorations_by_id: dict = {}
        if restored_path.exists():
            with open(restored_path, encoding="utf-8") as f:
                restored = json.load(f)
            restorations_by_id = {
                r["gap_id"]: r for r in restored.get("restorations", [])
            }

        # Assemble texts
        coptic_lines = []
        english_lines = []

        for seg in teaching["segments"]:
            cop = seg["core_coptic"]
            eng = seg["core_english"]

            for ap in seg["apparatus"]:
                placeholder = "{" + str(ap["id"]) + "}"
                if ap["type"] == "restoration":
                    cop = cop.replace(placeholder, ap.get("coptic", ""))
                    eng = eng.replace(placeholder, ap.get("english", ""))
                elif ap["type"] == "lacuna":
                    rest = restorations_by_id.get(ap["id"])
                    if rest and rest.get("proposed_coptic"):
                        cop = cop.replace(placeholder, f"[{rest['proposed_coptic']}]")
                    else:
                        cop = cop.replace(placeholder, "[...]")
                    if rest and rest.get("proposed_english"):
                        eng = eng.replace(placeholder, f"[{rest['proposed_english']}]")
                    else:
                        eng = eng.replace(placeholder, "[...]")

            coptic_lines.append(cop)
            english_lines.append(eng)

        parts = [
            "## Coptic",
            "",
            "\n".join(coptic_lines),
            "",
            "## English",
            "",
            "\n".join(english_lines),
        ]

        return "\n".join(parts)

    def process_result(self, page_num: int, result: dict) -> dict:
        """Add teaching number back to the output."""
        result["teaching"] = page_num
        return result

    def format_summary(self, page_num: int, result: dict) -> str:
        """One-line summary."""
        deg = result.get("degree", "?")
        dir_ = result.get("direction", "?")
        dc = result.get("degree_confidence", "?")
        drc = result.get("direction_confidence", "?")
        return f"{deg}/{dir_} ({dc}/{drc})"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    stage = ClassifyStage()
    stage.run()
