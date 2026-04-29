#!/usr/bin/env python3
"""
Extract the core teaching layer from translated Kephalaia pages.

Pipeline stage 4: runs AFTER stage_3_score.py, BEFORE stage_5_read.py.

This script sends each page to Claude WITH its pre-computed score data
as guidance. The LLM classifies each line segment by temporal layer.
Layer categories are loaded dynamically from corpus_metadata.json (produced
by stage_2_discover.py).

For substrate segments: preserved verbatim (Coptic + English).
For mixed segments: oldest teaching extracted, removed material noted.
For all others: core_text is null.

Input:
  - output/projects/kephalaia_v2/pages/p_NNN.json     (translation)
  - output/projects/kephalaia_v2/scores/p_NNN.json    (scoring)
  - output/projects/kephalaia_v2/corpus_metadata.json  (layer definitions)

Output:
  - output/projects/kephalaia_v2/core/p_NNN.json

Usage:
    python scripts/projects/kephalaia_v2/stage_4_extract.py
    python scripts/projects/kephalaia_v2/stage_4_extract.py --page 35
    python scripts/projects/kephalaia_v2/stage_4_extract.py --range 10-50
    python scripts/projects/kephalaia_v2/stage_4_extract.py --dry-run
    python scripts/projects/kephalaia_v2/stage_4_extract.py --max-concurrency 4
"""
import copy
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
# Load corpus metadata
# ---------------------------------------------------------------------------

METADATA_PATH = PROJECT_DIR / "corpus_metadata.json"


def load_metadata() -> dict:
    """Load corpus_metadata.json produced by stage_2_discover."""
    if not METADATA_PATH.exists():
        print(f"ERROR: corpus_metadata.json not found at {METADATA_PATH}")
        print("       Run stage_2_discover.py first.")
        sys.exit(1)
    with open(METADATA_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Build tool schema dynamically from metadata
# ---------------------------------------------------------------------------

def build_extract_tool(metadata: dict) -> dict:
    """Build the commit_extraction tool with dynamic classification enum.

    The enum uses the metadata layer IDs + 'mixed' + 'null_line'.
    This ensures classification labels match the score data keys exactly.
    """
    vocabs = metadata.get("scoring_vocabularies", [])
    layer_ids = [v["id"] for v in vocabs]

    # Build description parts for the enum
    desc_parts = [
        "Temporal layer classification. "
        "Classify by WHEN this language entered the text. "
    ]
    for v in vocabs:
        lid = v["id"]
        name = v.get("name", lid)
        desc_parts.append(f"'{lid}' = {name}. ")
    desc_parts.append(
        "'mixed' = multiple layers interwoven in one segment. "
    )
    desc_parts.append(
        "'null_line' = line is physically lost (coptic and english null)."
    )

    classification_enum = layer_ids + ["mixed", "null_line"]

    return {
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
                        "Count of segments classified as oldest layer "
                        "or mixed (i.e. segments with core_text)."
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
                                "enum": classification_enum,
                                "description": "".join(desc_parts),
                            },
                            "core_coptic": {
                                "type": ["string", "null"],
                                "description": (
                                    "For oldest layer: the coptic field "
                                    "verbatim. "
                                    "For mixed: extracted oldest-layer "
                                    "Coptic. "
                                    "For all others: null."
                                ),
                            },
                            "core_english": {
                                "type": ["string", "null"],
                                "description": (
                                    "For oldest layer: the english field "
                                    "verbatim. "
                                    "For mixed: extracted oldest-layer "
                                    "English. "
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
# Build system prompt dynamically from metadata
# ---------------------------------------------------------------------------

def build_system_prompt(metadata: dict) -> str:
    """Build the system prompt with metadata-discovered layer descriptions.

    Uses v1's proven prompt as base, adjusting only for v2 structural
    differences (segments not paragraphs, pages not chapters, Coptic+English,
    null_line category, dynamic layer IDs from metadata).
    """
    vocabs = metadata.get("scoring_vocabularies", [])

    # Build dynamic layer descriptions section
    layer_lines = []
    for v in vocabs:
        lid = v["id"]
        name = v.get("name", lid)
        desc = v.get("description", "")
        markers = v.get("markers", {})
        top_markers = sorted(markers, key=markers.get, reverse=True)[:8]

        layer_lines.append(f"### {lid} ({name})")
        if desc:
            layer_lines.append(desc)
        if top_markers:
            layer_lines.append(
                f"Key Coptic markers: {', '.join(top_markers)}"
            )
        layer_lines.append("")

    layers_section = "\n".join(layer_lines)

    # Identify the substrate layer ID (first in metadata = oldest)
    substrate_id = vocabs[0]["id"] if vocabs else "cosmological_substrate"

    return f"""\
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

The boundary often falls MID-SEGMENT. A segment may open with \
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

## THE PERSIAN DIALOGUE TRADITION AND OPENING LINES

CRITICAL: The Q&A format of the Kephalaia — structured questions about \
cosmological topics followed by systematic teaching — is NOT a Manichaean \
invention. This is the PERSIAN PEDAGOGICAL TRADITION. The dialogue format \
itself is substratic. Mani APPROPRIATED this tradition and added his own \
attribution machinery ("Once again the enlightener speaks to his disciples").

This means: when a segment contains a SUBSTANTIVE COSMOLOGICAL \
QUESTION — "Tell us about the five storehouses", "What are the three \
wheels?", "How does the mixture come about?" — the QUESTION ITSELF is \
core. It reveals the teaching structure. It IS the substrate. The question \
defines what the teaching sequence will map.

Only classify segments as dialogue frame when they contain PURELY \
FORMULAIC attribution with NO cosmological content:
- "ⲡⲉϫⲉ ⲡⲥⲁⲍ" / "The Teacher said" → apostolic_dialogue (pure formula)
- "Once again the enlightener speaks to his disciples" → apostolic_dialogue \
  (pure hagiographic frame)

But:
- "Tell us about the five limbs of the Father of Greatness" → {substrate_id} \
  (substantive cosmological question — it defines the teaching topic)
- "We beseech you that you tell us about the three wheels and the \
  five storehouses" → mixed (strip "We beseech you that you tell us", \
  keep "about the three wheels and the five storehouses")

When a frame formula introduces a substantive question, classify as \
mixed and extract the substantive content. Do NOT discard cosmological \
questions just because they are wrapped in frame formulas.

## ENUMERATION INTEGRITY

When the substrate teaches through NUMBERED LISTS — "The first is...", \
"The second is...", "The third is..." — the enumeration markers are \
PART OF the substrate. They are the STRUCTURE of the teaching, not \
decoration.

If a segment begins with an enumeration marker ("The second is error", \
"The third is desire") and continues with cosmological-correspondential \
description, the ENTIRE enumeration unit belongs in the oldest teaching \
layer. Do NOT strip the enumeration marker from a mixed segment. If you \
must extract from a mixed segment that contains enumeration, preserve the \
full "The Nth is [term]" structure in core_coptic / core_english.

## COMPUTATIONAL TEXT-CRITICAL DATA: HOW TO USE IT

You will receive vocabulary density scores and structural flags generated \
by a computational NLP pipeline. These are GUIDES, not determinations. \
They flag patterns for your attention. You make the actual classification \
by reading the text.

### CRITICAL: How these scores are produced

The analytical data you receive is generated by a SIMPLE NLP PIPELINE — \
basically vocabulary frequency counting. It works like this:

1. **Vocabulary lists** were identified by a corpus-level metadata analysis \
   for each temporal layer.
2. **Density scores** count how often words from each list appear per 100 \
   words of text in each segment.
3. **Per-layer scores** show which vocabulary categories are active in each \
   segment.

This means the scores measure WHAT VOCABULARY IS PRESENT. They cannot \
determine WHEN that vocabulary entered the text. A segment full of \
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
  (drift across page halves) and for flagging editorial seams \
  (bridge connective + register shift). These structural patterns are \
  harder to fake than raw vocabulary presence.

### Page-level features:
- **Teaching purity**: Ratio of oldest-layer ({substrate_id}) vocabulary to \
  total vocabulary density. Higher = more teaching, less overlay.
- **Editorial fatigue score**: Measures later-layer drift from first to second \
  half of the page. Positive values mean editorial vocabulary increases \
  in the second half — a classic editorial fatigue pattern. Per-layer \
  first-half / second-half breakdowns are included.

### Segment-level features:
- **Register scores**: Vocabulary density per 100 words for each scoring \
  category identified by the metadata analysis. These are RAW VOCABULARY COUNTS.
- **Seam flags**: When the text-critical algorithm detects a potential \
  editorial seam (bridge connective + institutional vocabulary + register \
  shift from preceding segments). These are STRONG signals.

### How to use this data:
1. **Seam flags** — STRONGEST signal. When a seam flag fires, the segment \
   is likely a later editorial addition — not MIXED.
2. **Editorial fatigue** — Strong signal. Drift toward later layers indicates \
   addition.
3. **Register scores** — WEAKEST signal. Trust YOUR reading over these.

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

{layers_section}\
### mixed
Multiple layers interwoven in one segment. Extract the oldest teaching \
and note what was removed.

### null_line
The line is physically lost (coptic and english are both null).

## EDITORIAL SEAM DETECTION — CRITICAL

An EDITORIAL SEAM is where an editor extends an existing teaching sequence \
by mimicking its syntactic pattern but introducing institutional content. \
This is the most subtle form of editorial addition because the seam LOOKS \
like a continuation of the teaching.

### The Pattern Mimicry Problem

Consider a four-fold cosmological teaching:
  Seg 5: "Happiness, wisdom and power exist in [the Father/land of light]"
  Seg 6: "[these three exist in] the sun/ship of fire"
  Seg 7: "Again, these three exist in the ship of living waters"
  Seg 8: "Again, these three exist in the elements"

An editor who sees this pattern can extend it:
  Seg 9: "Now, moreover, happiness, wisdom and power exist in the holy church."

The editor has NOT TOUCHED the core teaching. They have EXTENDED the list \
by adding one more iteration — but applying the pattern to their own \
institution instead of to a cosmic domain. The bridge phrase "Now, moreover" \
IS the editorial seam.

### How to Detect Editorial Seams

1. **Bridge connectives**: "Now, moreover" / "Furthermore" / "And moreover" \
   at the START of a segment, especially when:
   - The preceding segments contain systematic cosmological iterations
   - The new segment applies the pattern to church/institution/community

2. **Register shift at the connection point**: The preceding segments \
   have high cosmological vocabulary (cosmic beings, cosmic geography); the \
   new segment has high institutional vocabulary (holy church, elect, \
   catechumens, apostle of light, leaders, teachers, mission).

3. **Position**: Editorial additions tend to come AFTER the teaching \
   sequence (extending the list) or AT THE END of a structural unit \
   (editorial fatigue — adding pastoral material after the core is complete).

4. **The critical question**: If you removed this segment, would the \
   preceding teaching sequence be COMPLETE IN ITSELF? If yes — if the \
   cosmic domains were mapped and the structure was closed — then this \
   extension is editorial.

### What This Means for Classification

When a segment mimics the core teaching pattern but applies it to \
institutional content, the ENTIRE segment is a later editorial \
layer — not mixed. \
Do NOT extract the opening clause as "core" just because it uses \
the same syntax. The opening clause IS PART OF the editorial extension. \
"Now, moreover, X exist in the holy church" is ONE editorial act — the \
bridge phrase and the institutional identification were written by the \
same hand at the same time.

## YOUR TASK

You receive a page with:
1. The translated line segments (Coptic + English + apparatus notes)
2. The per-segment vocabulary scores
3. Page-level features (teaching purity, editorial fatigue, damage)

Classify each segment by temporal layer. For {substrate_id} and mixed, \
preserve the core teaching Coptic and English verbatim (both fields). \
For mixed, note what was removed and why.

When complete, call commit_extraction exactly once.

## EXTRACTION RULES

1. **Temporal layer is the axis.** Do NOT classify by content type. \
   Classify by WHEN the language entered the text.

2. **The oldest teaching layer expounds, it does not cite.** It describes \
   how cosmic systems work. It does not say "as it is written" or "the \
   saviour preached."

3. **Editorial seams are NOT mixed segments.** When a segment extends a \
   teaching sequence with institutional content, classify the ENTIRE \
   segment as the appropriate editorial layer — not mixed.

4. **Preserve exact text.** For the oldest teaching layer, return both \
   core_coptic and core_english verbatim from the page JSON. \
   For mixed, extract the oldest teaching words exactly — no paraphrase. \
   For all other layers: core_coptic and core_english are null.

5. **Strip frame formulas from MIXED.** If frame wraps teaching, extract the \
   teaching only (in both Coptic and English).

6. **Preserve lacunae and manuscript markers.** Keep {{N}} placeholders \
   exactly as they appear — they mark physical gaps in the manuscript.

7. **Null lines.** When both coptic and english are null for a segment, \
   classify as null_line. These are physically lost lines.

8. **Substantive cosmological questions belong to the oldest layer.** \
   "Tell us about the five storehouses" reveals the teaching structure. \
   Purely formulaic "We beseech you" / "ⲡⲉϫⲉ ⲡⲥⲁⲍ" is dialogue frame. \
   When both are present, classify as mixed and PRESERVE the substantive \
   content in core_coptic / core_english.

9. **When in doubt about age, flag it.** Use temporal_note to record genuine \
   uncertainty. Do not keep late material out of caution.

10. **Watch for voice shifts.** The oldest teaching has a distinctive voice: \
    systematic, impersonal, structured, process-oriented. When you hear it \
    shift to citation, exhortation, or biography, that is a layer boundary.

11. **Editorial fatigue matters.** If the page-level fatigue score shows \
    strong later-layer drift in the second half, be MORE suspicious of \
    editorial material in the later segments.

12. **Polemic against "the sects" is ambiguous.** Flag rather than \
    automatically classify.

13. **DIALOGUE FRAME ATTRIBUTION MUST BE STRIPPED.** Phrases like \
    "ⲡⲉϫⲉ ⲡⲥⲁⲍ" / "The Teacher said" or "Then speaks the apostle to \
    him:" are dialogue frame. They must NEVER appear in core_coptic / \
    core_english. If a segment starts with dialogue attribution followed \
    by teaching, classify as mixed and extract ONLY the teaching.

14. **ENUMERATION MARKERS ARE SUBSTRATE.** Never strip "The first is...", \
    "The second is..." etc. from extracted core text. These are the \
    bones of the teaching structure.

## THE SUBSTRATE BENEATH THE COPTIC

The text you examine is a Coptic translation. The TEACHING originates \
in a Persian/Iranian cosmological tradition — and beneath that, in the \
tradition of the Bene Qedem ("Children of the East"), the correspondential \
science of the ancient world. Preserve the Coptic translation vocabulary \
as-is in core_coptic. The one exception: capitalize personified cosmic \
entities (Sin, Darkness) when they function as agents in core_english.

Preserve {{N}} lacuna placeholders — these mark physical manuscript damage.

Use temporal_note to record observations about the Coptic vocabulary — \
what concepts the translators rendered, anything notable about the \
translation choices."""


# ---------------------------------------------------------------------------
# Stage implementation
# ---------------------------------------------------------------------------

class ExtractStage(PipelineStage):
    stage_name = "Extract Core"
    stage_number = 4
    description = "Temporal layer classification per line segment"
    tool_name = "commit_extraction"
    tool_schema = {}  # Built dynamically in run()

    def __init__(self) -> None:
        super().__init__()
        self.metadata: dict = {}
        self._system_prompt: str = ""
        self._substrate_id: str = "cosmological_substrate"

    def run(self) -> None:
        """Override to load metadata before base run."""
        # Load metadata first — needed for tool schema and system prompt
        self.metadata = load_metadata()
        vocabs = self.metadata.get("scoring_vocabularies", [])
        if vocabs:
            self._substrate_id = vocabs[0]["id"]
        self.tool_schema = build_extract_tool(self.metadata)
        self._system_prompt = build_system_prompt(self.metadata)

        print(f"  Metadata: {len(vocabs)} scoring layers, "
              f"substrate = '{self._substrate_id}'")

        super().run()

    def get_system_prompt(self) -> str:
        return self._system_prompt

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
                    parts.append(
                        f"  {{{aid}}} seg={seg} lacuna ~{est}ch"
                    )
                else:
                    cop = a.get("coptic", "")
                    eng = a.get("english", "")
                    parts.append(
                        f"  {{{aid}}} seg={seg} restoration: "
                        f"{cop} = {eng}"
                    )

        return "\n".join(parts)

    def _format_scores(self, score_data: dict) -> str:
        """Format score data for the prompt.

        Uses the actual keys from stage_3 output:
        - page_scores: {layer_id: density} for each metadata layer
        - page_features: {teaching_purity, editorial_fatigue_score, ...}
        - segments: [{i, n, scores: {layer_id: density}, is_null, ...}]
        - structural_units, damage, seam_flags, seams
        """
        parts = []

        # Page-level summary
        ps = score_data.get("page_scores", {})
        pf = score_data.get("page_features", {})
        damage = score_data.get("damage", {})

        parts.append("### Page-level features")

        # Report all layer scores by their actual keys
        for layer_id, density in ps.items():
            if density > 0:
                parts.append(f"- {layer_id}: {density}")

        # Teaching purity and editorial fatigue
        tp = pf.get("teaching_purity")
        if tp is not None:
            parts.append(f"- Teaching purity: {tp:.3f}")

        fatigue = pf.get("editorial_fatigue_score", 0.0)
        parts.append(f"- Editorial fatigue score: {fatigue:.2f}")
        if fatigue > 0.5:
            parts.append(
                "  ⚠ SIGNIFICANT later-layer drift in second half — "
                "editor likely added material after core teaching"
            )
        elif fatigue > 0.2:
            parts.append(
                "  ⚠ Moderate later-layer drift in second half"
            )

        # Fatigue detail per layer
        detail = pf.get("editorial_fatigue_detail", {})
        for lid, vals in detail.items():
            shift = vals.get("shift", 0.0)
            if abs(shift) > 1.0:
                fh = vals.get("first_half", 0.0)
                sh = vals.get("second_half", 0.0)
                parts.append(
                    f"    {lid}: {fh:.1f}→{sh:.1f} (shift {shift:+.1f})"
                )

        # Damage
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

        # Build seam lookup for inline display
        # seams array is parallel to segments — seams[i] = seam data for segment i
        seams = score_data.get("seams", [])
        seam_by_i = {}
        for i, s in enumerate(seams):
            if s.get("seam_flag"):
                note = s.get("seam_note", "")
                if not note:
                    # Build note from available fields
                    parts_s = []
                    bp = s.get("bridge_phrase")
                    if bp:
                        parts_s.append(f"bridge: '{bp}'")
                    inst = s.get("institutional_terms_found", [])
                    if inst:
                        parts_s.append(
                            f"institutional: {', '.join(inst)}"
                        )
                    if s.get("register_shift"):
                        parts_s.append("register shift")
                    note = " + ".join(parts_s) if parts_s else (
                        "editorial seam detected"
                    )
                seam_by_i[i] = note

        # Per-segment scores (with seam flags inline)
        segments = score_data.get("segments", [])
        parts.append("### Per-segment scores")
        for seg in segments:
            i = seg["i"]
            scores = seg.get("scores", {})
            is_null = seg.get("is_null", False)

            if is_null:
                parts.append(f"  [i={i}] NULL (line lost)")
                continue

            score_str = " | ".join(
                f"{k}={v}" for k, v in scores.items() if v > 0
            )
            if not score_str:
                score_str = "no hits"

            line = f"  [i={i}] {score_str}"
            if i in seam_by_i:
                line += f"\n    ⚠ SEAM: {seam_by_i[i]}"
            parts.append(line)

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
