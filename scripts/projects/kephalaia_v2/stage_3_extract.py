#!/usr/bin/env python3
"""
Extract the core teaching layer from translated Kephalaia pages.

Pipeline stage 3: runs AFTER score.py, BEFORE read.py.

This script sends each page to Claude WITH its pre-computed score data
as guidance. The LLM classifies each line segment by temporal layer:
- substrate: oldest correspondential teaching (cosmos→cosmos mapping)
- dialogue_frame: pure formulaic attribution (ⲡⲉϫⲉ ⲡⲥⲁⲍ etc.)
- pastoral: institutional rules, commandments, church hierarchy
- overlay: later Christian/editorial additions
- mixed: multiple layers interwoven in one segment

For substrate segments: preserved verbatim.
For mixed segments: oldest teaching extracted, removed material noted.
For all others: core_text is null.

Input:
  - output/projects/kephalaia_v2/pages/p_NNN.json  (translation)
  - output/projects/kephalaia_v2/scores/p_NNN.json (scoring)

Output:
  - output/projects/kephalaia_v2/core/p_NNN.json

Usage:
    python scripts/projects/kephalaia_v2/extract.py
    python scripts/projects/kephalaia_v2/extract.py --page 35
    python scripts/projects/kephalaia_v2/extract.py --range 10-50
    python scripts/projects/kephalaia_v2/extract.py --dry-run
    python scripts/projects/kephalaia_v2/extract.py --max-concurrency 4
"""
import json
import sys
from pathlib import Path

# Ensure package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_base import (
    PipelineStage,
    PAGES_DIR,
    SCORES_DIR,
    PROJECT_DIR,
)


# ---------------------------------------------------------------------------
# Tool schema
# ---------------------------------------------------------------------------

EXTRACT_TOOL = {
    "name": "commit_extraction",
    "description": (
        "Commit the temporal layer classification for all segments "
        "on this page. Call exactly once."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "page": {
                "type": "integer",
                "description": "The manuscript page number.",
            },
            "total_segments": {
                "type": "integer",
                "description": "Total line segments on this page.",
            },
            "core_segments": {
                "type": "integer",
                "description": (
                    "Count of segments classified as substrate or "
                    "mixed (i.e. segments with core_text)."
                ),
            },
            "core_percentage": {
                "type": "number",
                "description": (
                    "Estimated percentage of page content that is "
                    "core substrate teaching (0-100)."
                ),
            },
            "page_note": {
                "type": "string",
                "description": (
                    "Brief assessment: is the oldest teaching "
                    "dominant on this page? Any distinctive features, "
                    "editorial seams, or structural observations?"
                ),
            },
            "segments": {
                "type": "array",
                "description": (
                    "Classification for each line segment on the page."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "i": {
                            "type": "integer",
                            "description": (
                                "Segment index (matching the page JSON)."
                            ),
                        },
                        "classification": {
                            "type": "string",
                            "enum": [
                                "substrate",
                                "dialogue_frame",
                                "pastoral",
                                "overlay",
                                "mixed",
                                "null_line",
                            ],
                            "description": (
                                "Temporal layer classification. "
                                "'substrate' = oldest correspondential "
                                "teaching (cosmos→cosmos). "
                                "'dialogue_frame' = pure formulaic "
                                "attribution. "
                                "'pastoral' = institutional rules. "
                                "'overlay' = later additions. "
                                "'mixed' = multiple layers interwoven. "
                                "'null_line' = line is physically lost."
                            ),
                        },
                        "core_coptic": {
                            "type": ["string", "null"],
                            "description": (
                                "For substrate: the coptic field verbatim. "
                                "For mixed: extracted oldest-layer Coptic. "
                                "For all others: null."
                            ),
                        },
                        "core_english": {
                            "type": ["string", "null"],
                            "description": (
                                "For substrate: the english field verbatim. "
                                "For mixed: extracted oldest-layer English. "
                                "For all others: null."
                            ),
                        },
                        "removed_material": {
                            "type": ["string", "null"],
                            "description": (
                                "For mixed only: what was removed and "
                                "why. Null for non-mixed."
                            ),
                        },
                        "temporal_note": {
                            "type": ["string", "null"],
                            "description": (
                                "Brief observation: what markers, "
                                "patterns, or register shifts indicate "
                                "the classification? Be honest about "
                                "uncertainty."
                            ),
                        },
                    },
                    "required": [
                        "i", "classification",
                        "core_coptic", "core_english",
                        "removed_material", "temporal_note",
                    ],
                },
            },
        },
        "required": [
            "page", "total_segments", "core_segments",
            "core_percentage", "page_note", "segments",
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
Zoroastrian cosmological traditions, Manichaean cosmology, and textual \
criticism of composite religious texts.

You are working on the Coptic Kephalaia of the Teacher — a Manichaean \
composite text compiled in the 3rd-4th century CE. This text contains \
multiple temporal layers, and your task is to identify the OLDEST TEACHING \
SUBSTRATE and separate it from later editorial additions.

## WHAT MAKES THE SUBSTRATE THE SUBSTRATE

The correspondential substrate has a distinctive quality: **both sides of \
every mapping stay within the cosmic system**. It maps domain onto domain, \
being onto being, degree onto degree — and never reaches outside the system.

Examples of SUBSTRATE (cosmos→cosmos):
- "The King of the worlds of Wind is eagle-face" — realm → zoomorphic form
- "His body is iron" — realm → metal correspondence
- "Their taste is the bitter taste" — realm → sensory quality

Examples of EDITORIAL (cosmos→contemporary world):
- "His spirit is the one of idolatry... in every temple" — reaches into \
  the editor's religious landscape
- "I command you, keep away from magic arts" — pivots to audience address
- "Concerning this I tell you, my brethren" — pivots to audience address

**The critical diagnostic:** Does Mapping Side B stay within the cosmic \
system, or does it reach into the contemporary world?

## TEMPORAL LAYERS

### substrate (Oldest Teaching)
The correspondential cosmological teaching. Maps cosmos→cosmos. Systematic, \
impersonal, structured. Five-element nomenclature, emanation hierarchies, \
body-cosmos correspondences, degree structures. The teaching IS the mapping.

### dialogue_frame (Editorial Frame)
Pure formulaic attribution: "ⲡⲉϫⲉ ⲡⲥⲁⲍ" (the Teacher said), "ⲡⲉϫⲁⲩ" \
(they said), "ⲟⲛ ⲟⲩⲥⲁⲡ" (once again), doxological closings. HOWEVER: \
substantive cosmological questions within frame formulas are SUBSTRATE — \
"Tell us about the five storehouses" is teaching structure, not frame.

### pastoral (Institutional)
Church hierarchy (ⲉⲕⲕⲗⲏⲥⲓⲁ, ⲕⲁⲧⲏⲭⲟⲩⲙⲉⲛⲟⲥ, ⲉⲕⲗⲉⲕⲧⲟⲥ), commandments \
(ⲉⲛⲧⲟⲗⲏ), institutional rules, ecclesiastical vocabulary. Later additions \
addressing community practice and organization.

### overlay (Christian/Later)
Specifically Christian terminology (ⲥⲧⲁⲩⲣⲟⲥ = cross, ⲃⲁⲡⲧⲓⲥⲙⲁ = baptism), \
NT citations, Christianizing editorial additions.

### mixed
Multiple layers interwoven in one segment. Extract the oldest teaching \
and note what was removed.

### null_line
The line is physically lost (coptic and english are both null).

## EDITORIAL SEAM DETECTION

An editorial seam is where an editor extends an existing teaching sequence \
by mimicking its syntactic pattern but introducing institutional content.

Signs of editorial seams:
1. Bridge connectives at paragraph/unit start after systematic cosmological \
   iterations
2. Register shift: cosmological → institutional vocabulary
3. Position: additions tend to come AFTER teaching sequences or at chapter end
4. The preceding teaching is COMPLETE IN ITSELF without this extension

When a segment mimics the core teaching pattern but applies it to \
institutional content, classify the ENTIRE segment as the appropriate \
editorial layer — not mixed.

## HOW TO USE THE SCORE DATA

You receive pre-computed vocabulary scores for each segment:
- **substrate score**: density of cosmological vocabulary
- **frame score**: density of formulaic/editorial vocabulary
- **pastoral score**: density of institutional vocabulary
- **overlay score**: density of Christian overlay vocabulary
- **greek_loans**: count of Greek loanwords
- **patterns**: whether formulaic openings/closings/questions were detected

These scores are GUIDES. They measure what vocabulary is present, not when \
it entered the text. YOUR reading is primary. Use the scores to flag \
patterns for investigation:
- High frame score → check if purely formulaic or contains teaching
- High pastoral → likely editorial extension
- High substrate → likely core, but verify it maps cosmos→cosmos
- Seam detected → high suspicion of editorial addition

## YOUR TASK

You receive a page with:
1. The translated line segments (Coptic + English + apparatus)
2. The per-segment vocabulary scores and pattern flags
3. Page-level damage assessment

Classify each segment by temporal layer. For substrate and mixed, \
preserve the core teaching Coptic and English. For mixed, note what \
was removed and why.

When complete, call commit_extraction exactly once.

## RULES

1. Temporal layer is the axis — WHEN did this enter the text?
2. The substrate expounds, it does not cite or exhort
3. Editorial seams are NOT mixed — they're later editorial acts
4. Preserve exact text for substrate (verbatim from page JSON)
5. For mixed: extract oldest teaching only, note removed material
6. Preserve {N} placeholders — they mark physical gaps
7. Null lines (coptic=null) → classify as null_line
8. Substantive cosmological questions within frame formulas → substrate
9. Enumeration markers ("The first is...", "The second is...") are substrate
10. When uncertain, use temporal_note honestly — do not keep late material \
    out of caution"""


# ---------------------------------------------------------------------------
# Stage implementation
# ---------------------------------------------------------------------------

class ExtractStage(PipelineStage):
    stage_name = "Extract Core"
    stage_number = 3
    description = "Temporal layer classification per line segment"
    tool_name = "commit_extraction"
    tool_schema = EXTRACT_TOOL

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def get_input_dir(self) -> Path:
        return PAGES_DIR

    def get_output_dir(self) -> Path:
        return PROJECT_DIR / "core"

    def list_available(self) -> list[int]:
        """Only pages that have BOTH translation and score output."""
        import re as _re
        pages_available = set()
        for path in sorted(PAGES_DIR.glob("p_*.json")):
            m = _re.match(r"p_(\d+)\.json", path.name)
            if m:
                pages_available.add(int(m.group(1)))

        scores_available = set()
        for path in sorted(SCORES_DIR.glob("p_*.json")):
            m = _re.match(r"p_(\d+)\.json", path.name)
            if m:
                scores_available.add(int(m.group(1)))

        return sorted(pages_available & scores_available)

    def build_user_message(self, page_num: int) -> str:
        """Load page + score data and format into user message."""
        page_data = self.load_page_json(page_num, PAGES_DIR)
        score_data = self.load_page_json(page_num, SCORES_DIR)

        if page_data is None:
            print(f"  ERROR: No page data for p.{page_num}")
            return None
        if score_data is None:
            print(f"  ERROR: No score data for p.{page_num}")
            return None

        # Format page translation
        lines_section = self._format_translation(page_data)

        # Format score data
        scores_section = self._format_scores(score_data)

        return (
            f"## Page {page_num} — Translation\n\n"
            f"{lines_section}\n\n"
            f"## Page {page_num} — Text-Critical Score Data\n\n"
            f"{scores_section}\n\n"
            f"Classify each segment by temporal layer. "
            f"Call commit_extraction with the complete classification."
        )

    def _format_translation(self, page_data: dict) -> str:
        """Format translated lines for the prompt."""
        lines = page_data.get("lines", [])
        apparatus = page_data.get("apparatus", [])

        parts = []

        # Header
        header = page_data.get("header", {})
        if header:
            parts.append(
                f"Header: {header.get('title_coptic', '—')} "
                f"= {header.get('title_english', '—')}"
            )
            parts.append("")

        # Lines
        for seg in lines:
            i = seg["i"]
            n = seg["n"]
            coptic = seg.get("coptic") or "[NULL — line lost]"
            english = seg.get("english") or "[NULL — line lost]"
            ba = " [BREAK]" if seg.get("break_after") else ""
            parts.append(f"[i={i}, n={n}]{ba}")
            parts.append(f"  Coptic:  {coptic}")
            parts.append(f"  English: {english}")

        # Apparatus summary
        if apparatus:
            parts.append("")
            parts.append(f"Apparatus: {len(apparatus)} entries")
            for a in apparatus[:20]:  # Limit to avoid token overflow
                aid = a["id"]
                atype = a["type"]
                seg = a.get("segment", "?")
                if atype == "lacuna":
                    est = a.get("est_chars", "?")
                    parts.append(f"  {{{{id={aid}}}}} seg={seg} lacuna ~{est}ch")
                else:
                    cop = a.get("coptic", "")
                    eng = a.get("english", "")
                    parts.append(
                        f"  {{{{id={aid}}}}} seg={seg} restoration: "
                        f"{cop} = {eng}"
                    )

        return "\n".join(parts)

    def _format_scores(self, score_data: dict) -> str:
        """Format score data for the prompt."""
        parts = []

        # Page-level summary
        ps = score_data.get("page_scores", {})
        pf = score_data.get("page_features", {})
        damage = score_data.get("damage", {})

        parts.append("### Page-level features")
        parts.append(
            f"- Substrate density: {ps.get('substrate', 0)}"
        )
        parts.append(f"- Frame density: {ps.get('frame', 0)}")
        parts.append(f"- Pastoral density: {ps.get('pastoral', 0)}")
        parts.append(f"- Overlay density: {ps.get('overlay', 0)}")
        parts.append(
            f"- Greek loan density: "
            f"{pf.get('greek_density', 0)} per segment"
        )
        parts.append(
            f"- Frame opening detected: "
            f"{pf.get('has_frame_opening', False)}"
        )
        parts.append(
            f"- Frame closing detected: "
            f"{pf.get('has_frame_closing', False)}"
        )
        parts.append(
            f"- Damage ratio: "
            f"{damage.get('damage_ratio', 0)*100:.1f}%"
        )
        parts.append("")

        # Structural units
        units = score_data.get("structural_units", [])
        if units:
            parts.append(f"### Structural units ({len(units)})")
            for u in units:
                parts.append(
                    f"  Unit: segments {u['start_i']}-{u['end_i']} "
                    f"({u['segments']} segments)"
                )
            parts.append("")

        # Per-segment scores
        segments = score_data.get("segments", [])
        parts.append("### Per-segment scores")
        for seg in segments:
            i = seg["i"]
            scores = seg.get("scores", {})
            gl = seg.get("greek_loans", 0)
            pats = seg.get("patterns", {})
            is_null = seg.get("is_null", False)

            if is_null:
                parts.append(f"  [i={i}] NULL (line lost)")
                continue

            score_str = " | ".join(
                f"{k}={v}" for k, v in scores.items() if v > 0
            )
            if not score_str:
                score_str = "no hits"

            flags = []
            if pats.get("frame_opening"):
                flags.append("FRAME_OPEN")
            if pats.get("frame_closing"):
                flags.append("FRAME_CLOSE")
            if pats.get("question_formula"):
                flags.append("QUESTION")
            if gl > 0:
                flags.append(f"greek={gl}")

            flag_str = f" [{', '.join(flags)}]" if flags else ""
            parts.append(f"  [i={i}] {score_str}{flag_str}")

        return "\n".join(parts)

    def process_result(self, page_num: int, result: dict) -> dict:
        """Pass through the raw result (already structured)."""
        return result

    def format_summary(self, page_num: int, result: dict) -> str:
        """Format a one-line summary."""
        total = result.get("total_segments", 0)
        core = result.get("core_segments", 0)
        pct = result.get("core_percentage", 0)
        return f"OK — {core}/{total} core ({pct:.0f}%)"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    stage = ExtractStage()
    stage.run()
