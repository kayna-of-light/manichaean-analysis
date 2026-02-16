#!/usr/bin/env python3
"""
Kephalaia Layer Analysis v4 — Temporal-Axis Textual Critical Analysis
====================================================================

Reads from LLM-cleaned structured JSON (output/cleaned/chapters/ch_*.json)
where teaching text, Gardner synopsis, and footnotes are already separated.

Previous versions (v1–v3) fought raw OCR to separate these layers with regex.
Now the LLM pipeline has done that work — this script applies the analysis
to CLEAN data, eliminating noise from parsing heuristics.

CRITICAL METHODOLOGICAL PRINCIPLE:
  The primary axis of discrimination is TEMPORAL — "when did this language
  enter this text?" — not THEMATIC ("does it contain cosmology vs. ethics?").
  Cosmological content IS correspondential. They are the same thing at
  different levels of description. The five sons, the ships, the body-universe
  maps ARE correspondences. The vocabulary categories detect different MARKERS
  but the composite score groups them on a temporal axis:
    - TEACHING SUBSTRATE (positive): cosmological + correspondential +
      persian_substrate — all indicators of older material
    - INSTITUTIONAL OVERLAY (negative): pastoral + nt_christian +
      hagiographic — all indicators of later editorial layers

Analytical pipeline:
  1. Load cleaned chapters (teaching_text, gardner_synopsis, footnotes)
  2. Vocabulary profiling across 6 marker categories (on teaching text only)
  3. TF-IDF vectorization + unsupervised clustering
  4. Paragraph-level segmentation within teaching text
  5. Editor fatigue detection (intra-chapter vocabulary shift)
  6. Gardner editorial flag extraction (from isolated synopsis)
  7. Footnote-based citation analysis (from structured footnote objects)
  8. Formulaic/structural pattern detection
  9. Temporal composite scoring and tier classification
  10. Core substrate reconstruction

Temporal layers (from oldest to latest):
  Layer 1 (Teaching Substrate): Systematic correspondential-cosmological
      teaching — five-fold systems, body-universe maps, discrete degree
      chains, call-and-answer, numbered enumerations. Some predates Mani;
      some is Mani's own systematization of ancient material.
  Layer 2 (Christian Overlay): Mani's Marcionite Christianity framing —
      NT citations, Pauline vocabulary, Jesus Splendour Christology,
      Gospel allusions. 3rd century CE.
  Layer 3 (Hagiographic Frame): Community-added biographical material —
      formulaic Q&A, titles of reverence, miracle claims. 3rd-5th century.
  Layer 4 (Institutional Layer): Church instruction — catechumen/elect
      distinctions, pastoral rules, fasting, alms, mission. Post-Mani.

Output: output/analysis/v4/
"""

import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.metrics import silhouette_score
from scipy.cluster.hierarchy import dendrogram, linkage

# ============================================================
# PATHS
# ============================================================

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
CHAPTERS_DIR = PROJECT_ROOT / "output" / "cleaned" / "chapters"
OUTPUT_DIR = PROJECT_ROOT / "output" / "analysis" / "v4"

# Chapters in the previous manual Layer 1 extract (for comparison only)
MANUAL_LAYER1 = {2, 3, 6, 38, 39, 40, 41, 55, 56, 62, 70, 71, 72, 74, 75,
                 85, 86, 109, 114, 115, 122}

# ============================================================
# VOCABULARY DICTIONARIES
# ============================================================

VOCAB = {
    "cosmological": {
        "phrases": [
            "first man", "living spirit", "mother of life", "father of greatness",
            "third ambassador",
            "light mind", "virgin of light", "maiden of light", "great builder",
            "beloved of the lights", "king of honour", "king of honor",
            "adamas of light", "adamant of light",
            "king of the gardens", "keeper of splendour", "keeper of splendor",
            "king of glory", "king of darkness",
            "five shekhinas", "five sons", "twelve maidens",
            "living soul", "cross of light", "living fire",
            "ships of light", "ship of living waters", "ship of living fire",
            "land of darkness", "realm of light", "realm of darkness",
            "land of light", "land of rest", "land of the living",
            "place of rest",
            "garment of light", "garment of fire", "garment of wind",
            "garment of water", "living water", "living ones",
            "new earth", "great fire", "final lump",
            "new man", "old man", "light form",
            "column of glory", "pillar of glory", "perfect man",
            "five elements", "five garments", "five worlds",
            "five storehouses", "five trees", "five intellectuals",
            "five limbs", "five dark",
            "two principles", "three wheels", "three vessels",
            "wheel of the stars", "ten firmaments", "eight earths",
            "thought of death",
            "call and answer", "summons and obedience",
            "great spirit", "porter",
        ],
        "words": [
            "storehouses", "firmaments", "aeons", "emanation", "emanations",
            "rulers", "archons", "elements", "mixture", "vessels",
            "principalities", "zodiac",
            "fashioned", "constructed", "discharged", "crucified",
            "snared", "hunted", "mingled", "entangled",
            "purification", "separation", "evocation",
        ],
    },
    "persian_substrate": {
        "phrases": [
            "realm of darkness", "father of greatness",
            "two principles", "five elements",
            "call and response", "call and answer",
            "land of light", "land of darkness",
        ],
        "words": [
            "ohrmizd", "ahriman", "saclas", "nebroel", "ashaqlun", "namrael",
        ],
    },
    "pastoral": {
        "phrases": [
            "holy church", "alms-giving", "alms-offering",
        ],
        "words": [
            "catechumen", "catechumens", "elect",
            "alms", "fasting", "prayer", "prayers",
            "commandments", "church", "congregation",
            "saints", "brothers", "sisters",
            "sin", "sins", "sinner", "sinners",
            "righteous", "deeds", "retribution",
            "remembrance", "mission",
            "salvation", "saved",
        ],
    },
    "nt_christian": {
        "phrases": [
            "jesus christ", "christ jesus", "lord jesus",
            "jesus the splendour", "jesus splendour",
            "son of god", "body of christ",
            "father, son", "holy trinity",
            "resurrection of the dead", "kingdom of heaven",
            "eternal life", "it is written", "scripture says",
            "the gospel says", "the apostle says",
        ],
        "words": [
            "christ", "gospel", "paraclete",
            "paul", "matthew", "john", "luke", "mark",
            "grace", "justified", "justification",
            "baptism", "eucharist", "communion",
            "bishop", "deacon", "presbyter",
        ],
    },
    "hagiographic": {
        "phrases": [
            "apostle of light", "lord manichaios", "mani the living",
            "apostle of greatness", "the apostle speaks",
            "the apostle is sitting", "the apostle said",
            "the enlightener speaks", "the enlightener said",
            "once again the enlightener",
            "not one among the apostles",
        ],
        "words": [
            "manichaios", "miracle", "miraculous", "wonder",
        ],
    },
    "correspondential": {
        "phrases": [
            "after the likeness", "in the likeness",
            "resembles", "signifies",
            "in the manner of", "like unto",
            "is the manner",
            "these are the five", "these are the three",
            "these are the seven", "these are the twelve",
            "these are the ten",
            "this is the manner", "this is the interpretation",
            "this is the explanation",
            "corresponds", "correspondence",
        ],
        "words": [
            "likeness", "image", "similitude", "parable",
            "interpretation", "explanation", "meaning",
        ],
    },
}

# Temporal axis weights:
# POSITIVE = teaching substrate indicators (older material)
# NEGATIVE = institutional overlay indicators (later material)
# Cosmological + correspondential + persian_substrate are ALL teaching substrate.
# They are the same thing at different levels of description.
WEIGHTS = {
    "cosmological": 1.5,         # Teaching content (slightly reduced: includes Mani's own)
    "persian_substrate": 2.0,    # Ancient substrate markers (Zoroastrian roots)
    "correspondential": 1.5,     # Teaching method markers
    "pastoral": -2.0,            # Institutional/community layer
    "nt_christian": -2.5,        # Christian overlay (Mani-era or later)
    "hagiographic": -1.5,        # Community veneration frame
}

# ============================================================
# CHAPTER LOADING
# ============================================================

@dataclass
class CleanChapter:
    """A chapter loaded from the cleaned JSON output."""
    number: int
    title: str
    teaching_text: str
    gardner_synopsis: str
    footnotes: list  # list of {number: int, text: str}
    editorial_notes: str
    manuscript_pages: str

    @property
    def teaching_words(self) -> int:
        return len(self.teaching_text.split())

    @property
    def synopsis_words(self) -> int:
        return len(self.gardner_synopsis.split()) if self.gardner_synopsis else 0


def load_chapters() -> list[CleanChapter]:
    """Load all cleaned chapter JSONs."""
    chapters = []
    for path in sorted(CHAPTERS_DIR.glob("ch_*.json")):
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        chapters.append(CleanChapter(
            number=d["chapter_number"],
            title=d.get("title", f"Chapter {d['chapter_number']}"),
            teaching_text=d.get("teaching_text", ""),
            gardner_synopsis=d.get("gardner_synopsis", ""),
            footnotes=d.get("footnotes", []),
            editorial_notes=d.get("editorial_notes", ""),
            manuscript_pages=d.get("manuscript_pages", ""),
        ))
    return chapters


# ============================================================
# TEXT UTILITIES
# ============================================================

def clean_for_scoring(text: str) -> str:
    """Normalize text for vocabulary scoring."""
    # Remove page markers ⟨p.N⟩
    text = re.sub(r"⟨p\.\d+⟩", "", text)
    # Remove editorial brackets but keep content
    text = re.sub(r"\[([^\]]*)\]", r"\1", text)
    # Remove curly braces
    text = re.sub(r"[{}]", "", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def get_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    cleaned = re.sub(r"⟨p\.\d+⟩", "", text)
    cleaned = re.sub(r"\[([^\]]*)\]", r"\1", cleaned)
    sentences = re.split(r"[.!?]+", cleaned)
    return [s.strip() for s in sentences if len(s.strip().split()) > 2]


def get_words(text: str) -> list[str]:
    """Extract words from text."""
    cleaned = clean_for_scoring(text)
    words = cleaned.split()
    return [w for w in words if len(w) > 1 and not w.isdigit()]


def type_token_ratio(words: list[str]) -> float:
    """Vocabulary richness (unique words / total words)."""
    if not words:
        return 0.0
    return len(set(words)) / len(words)


def count_lacunae(text: str) -> int:
    """Count manuscript lacunae markers: [...], [ ... ], bracketed gaps."""
    return len(re.findall(r"\[\s*\.{2,}\s*\]|\[\s{2,}\]|\[\s*…\s*\]", text))


# ============================================================
# VOCABULARY PROFILING
# ============================================================

def score_vocabulary(text: str, word_count: int) -> tuple[dict, dict]:
    """Score text against all vocabulary categories.

    Returns:
        densities: {category: occurrences per 100 words}
        terms: {category: [terms found with counts]}
    """
    lower = text.lower()
    densities = {}
    terms = {}

    for cat, vocab in VOCAB.items():
        count = 0
        found = []

        # Phrase matches first (multi-word)
        for phrase in vocab.get("phrases", []):
            n = lower.count(phrase)
            if n > 0:
                count += n
                found.append(f"{phrase} x{n}")

        # Single word matches (word-boundary aware)
        word_freq = Counter(lower.split())
        for word in vocab.get("words", []):
            n = word_freq.get(word, 0)
            if n > 0:
                count += n
                found.append(f"{word} x{n}")

        density = (count / word_count * 100) if word_count > 0 else 0
        densities[cat] = round(density, 4)
        terms[cat] = found

    return densities, terms


def compute_composite(densities: dict) -> float:
    """Compute temporal composite: teaching substrate vs. institutional overlay.

    Positive = teaching substrate dominates (older material).
    Negative = institutional overlay dominates (later material).
    """
    score = 0.0
    for cat, weight in WEIGHTS.items():
        score += densities.get(cat, 0) * weight
    return round(score, 3)


# ============================================================
# GARDNER SYNOPSIS ANALYSIS
# ============================================================

GARDNER_FLAG_PATTERNS = [
    (r"redact(?:ed|or|ion)", "redaction"),
    (r"later\s+(?:addition|interpolat|layer|edit)", "later_addition"),
    (r"corrupt(?:ion|ed)", "corruption"),
    (r"secondary", "secondary_material"),
    (r"textual\s+develop", "textual_development"),
    (r"uncertain|unclear|obscure", "uncertain"),
    (r"parallel\s+(?:passage|text|version)", "parallel_text"),
    (r"christian|christianis", "christian_connection"),
    (r"gnostic", "gnostic_connection"),
    (r"zoroast|iranian|persian", "iranian_connection"),
    (r"buddhis", "buddhist_connection"),
    (r"mani\s+(?:himself|directly|personally)", "mani_attribution"),
    (r"canonical", "canonical_source"),
    (r"earlier\s+(?:form|version|tradition)", "earlier_tradition"),
    (r"diverging\s+tradition", "diverging_tradition"),
    (r"mandaean|right\s+ginza", "mandaean_parallel"),
    (r"prior\s+source|must\s+rely\s+on", "prior_source"),
    (r"pentad", "pentadic_structure"),
    (r"psalm|hymn", "liturgical_connection"),
    (r"cosmolog", "cosmological_content"),
    (r"myth(?:olog|ic)", "mythological_content"),
    (r"correspond", "correspondential_signal"),
]


def extract_gardner_flags(synopsis: str) -> list[str]:
    """Extract editorial flags from Gardner's synopsis."""
    if not synopsis:
        return []
    flags = []
    lower = synopsis.lower()
    for pattern, label in GARDNER_FLAG_PATTERNS:
        if re.search(pattern, lower):
            flags.append(label)
    return flags


# ============================================================
# FOOTNOTE ANALYSIS
# ============================================================

RE_NT_IN_FOOTNOTE = re.compile(
    r"\b(?:Mt\.?|Mk\.?|Lk\.?|Jn\.?|(?:1|2)\s*Cor\.?|Gal\.?|Eph\.?|Phil\.?|"
    r"Col\.?|(?:1|2)\s*Thess\.?|(?:1|2)\s*Tim\.?|Tit\.?|Heb\.?|Jas\.?|"
    r"(?:1|2)\s*Pet\.?|Rev\.?|Rom\.?|Acts)\s*\d",
    re.IGNORECASE,
)

RE_OT_IN_FOOTNOTE = re.compile(
    r"\b(?:Gen\.?|Ex\.?|Exod\.?|Lev\.?|Num\.?|Deut\.?|Ps\.?|Pss\.?|Isa\.?|"
    r"Jer\.?|Ezek\.?|Dan\.?|Prov\.?)\s*\d",
    re.IGNORECASE,
)

RE_MANI_IN_FOOTNOTE = re.compile(
    r"(?i)\b(?:gospel\s+of\s+thomas|book\s+of\s+giants|shabuhragan|"
    r"pragmateia|living\s+gospel|psalm-?book|image|treasure|kephalai)",
)


def analyze_footnotes(footnotes: list) -> dict:
    """Analyze structured footnotes for citation references."""
    nt_cites = []
    ot_cites = []
    mani_cites = []
    coptic_notes = 0
    total = len(footnotes)

    for fn in footnotes:
        text = fn.get("text", "")
        nt_matches = RE_NT_IN_FOOTNOTE.findall(text)
        ot_matches = RE_OT_IN_FOOTNOTE.findall(text)
        mani_matches = RE_MANI_IN_FOOTNOTE.findall(text)

        nt_cites.extend(nt_matches)
        ot_cites.extend(ot_matches)
        mani_cites.extend(mani_matches)

        # Coptic language notes (indicate textual-critical apparatus)
        if re.search(r"[ⲁ-ⲱ]|coptic|copt\.|reading|restoring", text, re.IGNORECASE):
            coptic_notes += 1

    return {
        "total_footnotes": total,
        "nt_citations": nt_cites,
        "ot_citations": ot_cites,
        "mani_citations": mani_cites,
        "coptic_notes": coptic_notes,
    }


# ============================================================
# STRUCTURAL PATTERN DETECTION
# ============================================================

OPENING_FORMULAS = [
    re.compile(r"(?i)once\s+again\s+(?:the\s+)?(?:enlightener|apostle)\s+speak"),
    re.compile(r"(?i)once\s+more\s+he\s+speak"),
    re.compile(r"(?i)again\s+he\s+speak"),
    re.compile(r"(?i)he\s+says?\s+to\s+(?:his|them|the)"),
    re.compile(r"(?i)the\s+enlightener\s+speaks?\s+to"),
    re.compile(r"(?i)the\s+apostle\s+is\s+sitting"),
    re.compile(r"(?i)the\s+apostle\s+speaks?\s+to"),
]

CLOSING_FORMULAS = [
    re.compile(r"(?i)when\s+(?:that|this)\s+(?:disciple|catechumen)\s+heard"),
    re.compile(r"(?i)he\s+(?:was\s+)?persuaded"),
    re.compile(r"(?i)(?:he|she|they)\s+(?:rejoiced|glorified|made\s+obeisance)"),
    re.compile(r"(?i)thanks?\s+to\s+you\s+my\s+master"),
]

QUESTION_FORMULAS = [
    re.compile(r"(?i)(?:a|one|another|that)\s+(?:disciple|catechumen|nazorean)\s+(?:ask|question|stood|came)"),
    re.compile(r"(?i)the\s+apostle\s+(?:is\s+)?ask"),
    re.compile(r"(?i)the\s+catechumen\s+ask"),
]

# Correspondential structure markers
CORRESPONDENCE_MARKERS = [
    re.compile(r"(?i)(?:he|it|this)\s+(?:construct|fashion)ed\s+(?:after|in)\s+the\s+likeness"),
    re.compile(r"(?i)the\s+likeness\s+of"),
    re.compile(r"(?i)this\s+is\s+(?:the\s+)?(?:manner|explanation|interpretation)"),
    re.compile(r"(?i)these\s+are\s+the\s+(?:five|three|seven|twelve|ten)"),
    re.compile(r"(?i)(?:five|three|seven|twelve|ten)\s+\w+\s+(?:are|exist|have)"),
]

ENUMERATION_MARKERS = [
    re.compile(r"(?i)the\s+first\b.*?\bthe\s+second\b"),
    re.compile(r"(?i)the\s+(?:first|second|third|fourth|fifth)\s+(?:is|was|who)"),
]


def detect_structure(text: str) -> dict:
    """Detect structural features of the teaching text."""
    has_opening = any(p.search(text[:500]) for p in OPENING_FORMULAS)
    has_closing = any(p.search(text[-500:]) for p in CLOSING_FORMULAS)
    has_question = any(p.search(text) for p in QUESTION_FORMULAS)
    correspondences = sum(1 for p in CORRESPONDENCE_MARKERS if p.search(text))
    enumerations = sum(1 for p in ENUMERATION_MARKERS if p.search(text))
    lacunae = count_lacunae(text)

    return {
        "has_formulaic_opening": has_opening,
        "has_formulaic_closing": has_closing,
        "has_question_formula": has_question,
        "correspondence_markers": correspondences,
        "enumeration_markers": enumerations,
        "lacunae_count": lacunae,
    }


# ============================================================
# PARAGRAPH SEGMENTATION
# ============================================================

PARA_SPLIT_PATTERNS = [
    re.compile(r"(?i)^\s*once\s+again"),
    re.compile(r"(?i)^\s*then\s+(?:the\s+)?(?:apostle|enlightener)\s+speak"),
    re.compile(r"(?i)^\s*(?:a|one|another|that)\s+(?:disciple|catechumen|nazorean)"),
    re.compile(r"(?i)^\s*when\s+(?:that|this)\s+(?:disciple|catechumen).*heard"),
    re.compile(r"(?i)^\s*(?:also|again),?\s+(?:this|it|these)"),
    re.compile(r"(?i)^\s*furthermore"),
    re.compile(r"(?i)^\s*⟨p\.\d+⟩"),  # Page markers as natural break points
]


def segment_into_paragraphs(text: str, chapter_number: int) -> list[dict]:
    """Segment teaching text into meaningful paragraphs."""
    # Split on double newlines first (natural paragraph breaks)
    raw_paras = re.split(r"\n\s*\n", text)

    paragraphs = []
    for raw in raw_paras:
        stripped = raw.strip()
        if not stripped:
            continue

        # Further split at formulaic boundaries within a paragraph
        lines = stripped.split("\n")
        sub_paras = []
        current_lines = []

        for line in lines:
            if current_lines and any(p.search(line) for p in PARA_SPLIT_PATTERNS):
                sub_paras.append("\n".join(current_lines))
                current_lines = []
            current_lines.append(line)

        if current_lines:
            sub_paras.append("\n".join(current_lines))

        for sp in sub_paras:
            cleaned = clean_for_scoring(sp)
            words = cleaned.split()
            if len(words) < 3:
                continue
            paragraphs.append({
                "chapter": chapter_number,
                "text": cleaned,
                "raw_text": sp.strip(),
                "word_count": len(words),
            })

    # Merge very short paragraphs with the next
    merged = []
    i = 0
    while i < len(paragraphs):
        p = paragraphs[i]
        if p["word_count"] < 15 and i + 1 < len(paragraphs):
            nxt = paragraphs[i + 1]
            paragraphs[i + 1] = {
                "chapter": p["chapter"],
                "text": p["text"] + " " + nxt["text"],
                "raw_text": p["raw_text"] + "\n\n" + nxt["raw_text"],
                "word_count": p["word_count"] + nxt["word_count"],
            }
            i += 1
            continue
        merged.append(p)
        i += 1

    return merged


# ============================================================
# CHAPTER ANALYSIS
# ============================================================

@dataclass
class ChapterAnalysis:
    """Complete analysis results for a single chapter."""
    chapter_number: int
    title: str
    manuscript_pages: str

    # Word counts
    teaching_words: int = 0
    synopsis_words: int = 0
    paragraph_count: int = 0
    sentence_count: int = 0

    # Vocabulary densities (per 100 words)
    vocab_densities: dict = field(default_factory=dict)
    vocab_terms: dict = field(default_factory=dict)

    # Composite score
    composite_score: float = 0.0

    # Structure
    has_formulaic_opening: bool = False
    has_formulaic_closing: bool = False
    has_question_formula: bool = False
    correspondence_markers: int = 0
    enumeration_markers: int = 0

    # Complexity
    avg_sentence_length: float = 0.0
    type_token_ratio: float = 0.0
    lacunae_count: int = 0
    lacunae_density: float = 0.0

    # Footnotes
    total_footnotes: int = 0
    nt_citations: list = field(default_factory=list)
    ot_citations: list = field(default_factory=list)
    mani_citations: list = field(default_factory=list)

    # Gardner flags
    gardner_flags: list = field(default_factory=list)

    # Grouped temporal densities
    teaching_density: float = 0.0   # cosmological + correspondential + persian_substrate
    overlay_density: float = 0.0    # pastoral + nt_christian + hagiographic
    teaching_purity: float = 0.0    # teaching / (teaching + overlay + epsilon)

    # Editor fatigue — vocabulary shift within chapter
    first_half_cosmo: float = 0.0
    second_half_cosmo: float = 0.0
    first_half_pastoral: float = 0.0
    second_half_pastoral: float = 0.0
    layer_shift_score: float = 0.0

    # Classification
    tier: str = ""  # core / secondary / mixed / pastoral / hagiographic / peripheral / fragmentary
    in_manual_extract: bool = False

    # Cluster assignment (from TF-IDF)
    cluster: int = -1
    pca_x: float = 0.0
    pca_y: float = 0.0


def analyze_chapter(chapter: CleanChapter) -> ChapterAnalysis:
    """Run all analyses on a single cleaned chapter."""
    text = chapter.teaching_text
    cleaned = clean_for_scoring(text)
    words = get_words(text)
    sentences = get_sentences(text)

    analysis = ChapterAnalysis(
        chapter_number=chapter.number,
        title=chapter.title,
        manuscript_pages=chapter.manuscript_pages,
    )

    # Word counts
    analysis.teaching_words = len(words)
    analysis.synopsis_words = chapter.synopsis_words
    analysis.sentence_count = len(sentences)

    # Vocabulary profiling on clean teaching text
    densities, terms = score_vocabulary(cleaned, len(words))
    analysis.vocab_densities = densities
    analysis.vocab_terms = terms
    analysis.composite_score = compute_composite(densities)

    # Grouped temporal densities
    analysis.teaching_density = round(
        densities.get("cosmological", 0) +
        densities.get("correspondential", 0) +
        densities.get("persian_substrate", 0), 4)
    analysis.overlay_density = round(
        densities.get("pastoral", 0) +
        densities.get("nt_christian", 0) +
        densities.get("hagiographic", 0), 4)
    total_density = analysis.teaching_density + analysis.overlay_density
    analysis.teaching_purity = round(
        analysis.teaching_density / (total_density + 0.01), 4)

    # Structure detection
    structure = detect_structure(text)
    analysis.has_formulaic_opening = structure["has_formulaic_opening"]
    analysis.has_formulaic_closing = structure["has_formulaic_closing"]
    analysis.has_question_formula = structure["has_question_formula"]
    analysis.correspondence_markers = structure["correspondence_markers"]
    analysis.enumeration_markers = structure["enumeration_markers"]
    analysis.lacunae_count = structure["lacunae_count"]

    # Complexity metrics
    if sentences:
        lengths = [len(s.split()) for s in sentences]
        analysis.avg_sentence_length = statistics.mean(lengths)
    analysis.type_token_ratio = type_token_ratio(words)
    if len(words) > 0:
        analysis.lacunae_density = (analysis.lacunae_count / len(words)) * 100

    # Footnote analysis
    fn_result = analyze_footnotes(chapter.footnotes)
    analysis.total_footnotes = fn_result["total_footnotes"]
    analysis.nt_citations = fn_result["nt_citations"]
    analysis.ot_citations = fn_result["ot_citations"]
    analysis.mani_citations = fn_result["mani_citations"]

    # Gardner flags
    analysis.gardner_flags = extract_gardner_flags(chapter.gardner_synopsis)

    # Editor fatigue — split teaching text in half
    if len(words) > 40:
        mid = len(words) // 2
        first_half = " ".join(words[:mid])
        second_half = " ".join(words[mid:])
        fh_d, _ = score_vocabulary(first_half, mid)
        sh_d, _ = score_vocabulary(second_half, len(words) - mid)
        analysis.first_half_cosmo = fh_d.get("cosmological", 0)
        analysis.second_half_cosmo = sh_d.get("cosmological", 0)
        analysis.first_half_pastoral = fh_d.get("pastoral", 0)
        analysis.second_half_pastoral = sh_d.get("pastoral", 0)
        # Shift: positive means pastoral increases / cosmological decreases
        cosmo_shift = analysis.second_half_cosmo - analysis.first_half_cosmo
        pastoral_shift = analysis.second_half_pastoral - analysis.first_half_pastoral
        analysis.layer_shift_score = round(pastoral_shift - cosmo_shift, 4)

    # Paragraph count
    paras = segment_into_paragraphs(text, chapter.number)
    analysis.paragraph_count = len(paras)

    # Manual extract comparison
    analysis.in_manual_extract = chapter.number in MANUAL_LAYER1

    return analysis


def classify_tier(analysis: ChapterAnalysis) -> str:
    """Classify chapter by temporal layer dominance.

    Uses both composite score (weighted teaching vs overlay) and
    teaching purity (ratio of teaching to total vocabulary signal).

    NOTE: Vocabulary analysis has LIMITED ability to distinguish "old
    teaching with editorial overlays grafted on" from "genuinely mixed
    or late material." Many chapters in the manual Layer 1 extract have
    significant pastoral vocabulary from overlays — the LLM extraction
    (not this tier) is what achieves fine-grained temporal discrimination.
    These tiers indicate vocabulary-level signal strength, not final
    temporal classification.
    """
    if analysis.teaching_words < 30:
        return "fragmentary"

    # Core: high composite AND high purity AND structural markers
    if (analysis.composite_score > 4.0
            and analysis.teaching_purity > 0.70
            and (analysis.correspondence_markers > 0
                 or analysis.enumeration_markers > 0)):
        return "core"

    # Secondary: teaching signal dominant with reasonable purity
    if analysis.composite_score > 1.0 and analysis.teaching_purity > 0.55:
        return "secondary"

    # Secondary via structure: positive composite + strong structural markers
    # (catches chapters with editorial overlays that dilute purity but still
    # contain systematic correspondential teaching)
    if (analysis.composite_score > 0.0
            and (analysis.correspondence_markers >= 2
                 or analysis.enumeration_markers >= 1)):
        return "secondary"

    d = analysis.vocab_densities
    overlay = (d.get("pastoral", 0) + d.get("nt_christian", 0)
               + d.get("hagiographic", 0))
    teaching = (d.get("cosmological", 0) + d.get("correspondential", 0)
                + d.get("persian_substrate", 0))

    if d.get("hagiographic", 0) > 0.5 and d.get("hagiographic", 0) > teaching:
        return "hagiographic"

    if overlay > teaching * 1.3:
        return "pastoral"

    if analysis.composite_score > -0.5:
        return "mixed"

    return "peripheral"


# ============================================================
# TF-IDF CLUSTERING
# ============================================================

def cluster_chapters(chapters: list[CleanChapter], analyses: list[ChapterAnalysis]):
    """Perform TF-IDF vectorization and clustering on teaching texts."""
    # Filter chapters with enough text
    valid_idx = [i for i, ch in enumerate(chapters) if ch.teaching_words > 50]
    texts = [clean_for_scoring(chapters[i].teaching_text) for i in valid_idx]

    if len(texts) < 5:
        print("  Too few chapters for clustering")
        return

    # TF-IDF
    vectorizer = TfidfVectorizer(
        max_features=1500,
        min_df=2,
        max_df=0.85,
        ngram_range=(1, 2),
        stop_words="english",
    )
    tfidf_matrix = vectorizer.fit_transform(texts)

    # PCA for visualization
    pca = PCA(n_components=2)
    coords = pca.fit_transform(tfidf_matrix.toarray())

    # Test k=2..8 for optimal clustering
    silhouette_scores = {}
    max_k = min(9, len(texts))
    for k in range(2, max_k):
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(tfidf_matrix)
        sil = silhouette_score(tfidf_matrix, labels)
        silhouette_scores[k] = round(sil, 4)

    optimal_k = max(silhouette_scores, key=silhouette_scores.get)
    print(f"  Silhouette scores: {silhouette_scores}")
    print(f"  Optimal k={optimal_k} (silhouette={silhouette_scores[optimal_k]})")

    # Final clustering
    km_final = KMeans(n_clusters=optimal_k, random_state=42, n_init=10)
    labels = km_final.fit_predict(tfidf_matrix)

    # Assign to analyses
    for j, idx in enumerate(valid_idx):
        analyses[idx].cluster = int(labels[j])
        analyses[idx].pca_x = float(coords[j, 0])
        analyses[idx].pca_y = float(coords[j, 1])

    # Characterize clusters
    cluster_profiles = {}
    for k in range(optimal_k):
        members = [analyses[valid_idx[j]] for j in range(len(valid_idx)) if labels[j] == k]
        if not members:
            continue

        avg_densities = {}
        for cat in VOCAB:
            vals = [m.vocab_densities.get(cat, 0) for m in members]
            avg_densities[cat] = round(sum(vals) / len(vals), 3) if vals else 0

        avg_score = round(sum(m.composite_score for m in members) / len(members), 3)

        # Top TF-IDF terms
        center = km_final.cluster_centers_[k]
        feature_names = vectorizer.get_feature_names_out()
        top_idx = center.argsort()[-15:][::-1]
        top_terms = [feature_names[j] for j in top_idx]

        # Name cluster by temporal dominance
        teaching_total = (avg_densities.get("cosmological", 0)
                         + avg_densities.get("correspondential", 0)
                         + avg_densities.get("persian_substrate", 0))
        overlay_total = (avg_densities.get("pastoral", 0)
                        + avg_densities.get("nt_christian", 0)
                        + avg_densities.get("hagiographic", 0))
        if teaching_total > overlay_total * 1.5:
            name = "Teaching Substrate"
        elif overlay_total > teaching_total * 1.5:
            name = "Institutional Overlay"
        elif avg_densities.get("hagiographic", 0) > 0.3:
            name = "Hagiographic"
        else:
            name = "Mixed"

        cluster_profiles[k] = {
            "name": name,
            "size": len(members),
            "avg_densities": avg_densities,
            "avg_composite": avg_score,
            "top_terms": top_terms,
            "chapters": sorted(m.chapter_number for m in members),
        }

    # Hierarchical clustering linkage
    linkage_matrix = None
    if tfidf_matrix.shape[0] > 3:
        linkage_matrix = linkage(tfidf_matrix.toarray(), method="ward")

    return {
        "optimal_k": optimal_k,
        "silhouette_scores": silhouette_scores,
        "cluster_profiles": cluster_profiles,
        "linkage_matrix": linkage_matrix,
        "valid_idx": valid_idx,
        "coords": coords,
        "labels": labels,
    }


# ============================================================
# PARAGRAPH-LEVEL ANALYSIS
# ============================================================

def analyze_paragraphs(chapters: list[CleanChapter]) -> list[dict]:
    """Run vocabulary scoring on individual paragraphs across all chapters."""
    all_paras = []
    pid = 0

    for ch in chapters:
        paras = segment_into_paragraphs(ch.teaching_text, ch.number)
        for p in paras:
            pid += 1
            densities, terms = score_vocabulary(p["text"], p["word_count"])
            composite = compute_composite(densities)
            all_paras.append({
                "id": f"P{pid:04d}",
                "chapter": ch.number,
                "word_count": p["word_count"],
                "text_preview": p["text"][:200],
                "vocab_densities": densities,
                "composite_score": composite,
            })

    return all_paras


# ============================================================
# VISUALIZATION
# ============================================================

TIER_COLORS = {
    "core": "#2ecc71",
    "secondary": "#3498db",
    "mixed": "#f39c12",
    "pastoral": "#e67e22",
    "hagiographic": "#9b59b6",
    "peripheral": "#e74c3c",
    "fragmentary": "#95a5a6",
}


def generate_visualizations(analyses: list[ChapterAnalysis], cluster_result: dict,
                            output_dir: Path):
    """Generate all visualizations."""
    analyses = sorted(analyses, key=lambda a: a.chapter_number)
    n = len(analyses)
    ch_nums = [a.chapter_number for a in analyses]
    tier_colors = [TIER_COLORS.get(a.tier, "#95a5a6") for a in analyses]

    # ===== Figure 1: Composite Score Flow =====
    fig, ax = plt.subplots(figsize=(22, 6))
    scores = [a.composite_score for a in analyses]
    ax.bar(range(n), scores, color=tier_colors, alpha=0.8, edgecolor="white", linewidth=0.3)

    for i, a in enumerate(analyses):
        if a.in_manual_extract:
            ax.plot(i, scores[i], "^", color="blue", markersize=7, zorder=5)

    ax.axhline(y=0, color="black", linewidth=0.5)
    ax.axhline(y=3.0, color="#2ecc71", linewidth=0.5, linestyle="--", alpha=0.5)
    ax.axhline(y=0.5, color="#3498db", linewidth=0.5, linestyle="--", alpha=0.5)
    ax.set_xticks(range(n))
    ax.set_xticklabels([str(c) for c in ch_nums], rotation=90, fontsize=6)
    ax.set_xlabel("Chapter Number")
    ax.set_ylabel("Temporal Composite")
    ax.set_title("Kephalaia v4 — Temporal Composite Score per Chapter\n"
                 "(teaching substrate vs institutional overlay; ▲ = in manual Layer 1 extract)",
                 fontsize=14, fontweight="bold")

    # Legend
    patches = [mpatches.Patch(color=c, label=t.capitalize()) for t, c in TIER_COLORS.items()]
    patches.append(mpatches.Patch(color="blue", label="Manual L1"))
    ax.legend(handles=patches, loc="upper right", fontsize=8, ncol=2)

    plt.tight_layout()
    fig.savefig(output_dir / "v4_01_composite_scores.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: v4_01_composite_scores.png")

    # ===== Figure 2: Vocabulary Category Heatmap =====
    fig, axes = plt.subplots(len(VOCAB), 1, figsize=(22, 3 * len(VOCAB)), sharex=True)
    fig.suptitle("Vocabulary Category Densities per Chapter", fontsize=16, fontweight="bold")

    category_colors = {
        "cosmological": "#3498db",
        "persian_substrate": "#1abc9c",
        "correspondential": "#2ecc71",
        "pastoral": "#e67e22",
        "nt_christian": "#e74c3c",
        "hagiographic": "#9b59b6",
    }

    for idx, cat in enumerate(VOCAB.keys()):
        vals = [a.vocab_densities.get(cat, 0) for a in analyses]
        color = category_colors.get(cat, "#95a5a6")
        axes[idx].bar(range(n), vals, color=color, alpha=0.8, edgecolor="white", linewidth=0.3)
        axes[idx].set_ylabel(f"{cat}\n(per 100w)", fontsize=8)
        axes[idx].set_title(cat.replace("_", " ").title(), fontsize=10)

    axes[-1].set_xticks(range(n))
    axes[-1].set_xticklabels([str(c) for c in ch_nums], rotation=90, fontsize=6)
    axes[-1].set_xlabel("Chapter Number")

    plt.tight_layout()
    fig.savefig(output_dir / "v4_02_vocab_heatmap.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: v4_02_vocab_heatmap.png")

    # ===== Figure 3: PCA Cluster Scatter =====
    if cluster_result and cluster_result.get("coords") is not None:
        fig, ax = plt.subplots(figsize=(12, 10))

        valid_idx = cluster_result["valid_idx"]
        coords = cluster_result["coords"]
        labels = cluster_result["labels"]
        profiles = cluster_result["cluster_profiles"]

        cmap = matplotlib.colormaps["tab10"]
        for j, idx in enumerate(valid_idx):
            a = analyses[idx]
            color = cmap(labels[j])
            marker = "^" if a.in_manual_extract else "o"
            size = 80 if a.in_manual_extract else 40
            ax.scatter(coords[j, 0], coords[j, 1], c=[color], marker=marker, s=size,
                      edgecolors="black", linewidth=0.5, zorder=3)
            ax.annotate(str(a.chapter_number), (coords[j, 0], coords[j, 1]),
                       fontsize=6, ha="center", va="bottom")

        # Legend for clusters
        for k, profile in profiles.items():
            ax.scatter([], [], c=[cmap(k)], label=f"Cluster {k}: {profile['name']} (n={profile['size']})")
        ax.legend(loc="upper right", fontsize=9)
        ax.set_title(f"TF-IDF PCA Clusters (k={cluster_result['optimal_k']})\n"
                     f"▲ = Manual Layer 1", fontsize=14, fontweight="bold")
        ax.set_xlabel("PC1")
        ax.set_ylabel("PC2")

        plt.tight_layout()
        fig.savefig(output_dir / "v4_03_pca_clusters.png", dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Saved: v4_03_pca_clusters.png")

    # ===== Figure 4: Dendrogram =====
    if cluster_result and cluster_result.get("linkage_matrix") is not None:
        fig, ax = plt.subplots(figsize=(22, 8))
        valid_idx = cluster_result["valid_idx"]
        ch_labels = [str(analyses[i].chapter_number) for i in valid_idx]

        dendrogram(cluster_result["linkage_matrix"], labels=ch_labels,
                  leaf_rotation=90, leaf_font_size=7, ax=ax)
        ax.set_title("Hierarchical Clustering Dendrogram (Ward's method)",
                    fontsize=14, fontweight="bold")
        ax.set_ylabel("Distance")

        plt.tight_layout()
        fig.savefig(output_dir / "v4_04_dendrogram.png", dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Saved: v4_04_dendrogram.png")

    # ===== Figure 5: Editor Fatigue =====
    fig, ax = plt.subplots(figsize=(22, 6))
    shifts = [a.layer_shift_score for a in analyses]
    shift_colors = ["#e74c3c" if s > 0.5 else ("#2ecc71" if s < -0.5 else "#95a5a6") for s in shifts]
    ax.bar(range(n), shifts, color=shift_colors, alpha=0.7, edgecolor="white", linewidth=0.3)
    ax.axhline(y=0, color="black", linewidth=0.5)
    ax.set_xticks(range(n))
    ax.set_xticklabels([str(c) for c in ch_nums], rotation=90, fontsize=6)
    ax.set_xlabel("Chapter Number")
    ax.set_ylabel("Layer Shift Score")
    ax.set_title("Editor Fatigue: Intra-Chapter Vocabulary Shift\n"
                 "(positive = pastoral vocabulary increases in second half vs cosmological)",
                 fontsize=14, fontweight="bold")
    plt.tight_layout()
    fig.savefig(output_dir / "v4_05_editor_fatigue.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: v4_05_editor_fatigue.png")

    # ===== Figure 6: Tier Composition =====
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    tier_counts = Counter(a.tier for a in analyses)
    tier_order = ["core", "secondary", "mixed", "pastoral", "hagiographic", "peripheral", "fragmentary"]
    tier_vals = [tier_counts.get(t, 0) for t in tier_order]
    colors = [TIER_COLORS[t] for t in tier_order]

    ax1.bar(range(len(tier_order)), tier_vals, color=colors, edgecolor="white")
    ax1.set_xticks(range(len(tier_order)))
    ax1.set_xticklabels([t.capitalize() for t in tier_order], rotation=45)
    ax1.set_ylabel("Number of Chapters")
    ax1.set_title("Tier Distribution", fontsize=12, fontweight="bold")

    # Agreement matrix: computational tier vs manual
    comp_core = [a.tier in ("core", "secondary") for a in analyses]
    man_l1 = [a.in_manual_extract for a in analyses]
    tp = sum(1 for c, m in zip(comp_core, man_l1) if c and m)
    fp = sum(1 for c, m in zip(comp_core, man_l1) if c and not m)
    fn = sum(1 for c, m in zip(comp_core, man_l1) if not c and m)
    tn = sum(1 for c, m in zip(comp_core, man_l1) if not c and not m)

    matrix = np.array([[tp, fp], [fn, tn]])
    im = ax2.imshow(matrix, cmap="YlGnBu", aspect="auto")
    ax2.set_xticks([0, 1])
    ax2.set_xticklabels(["Manual: Yes", "Manual: No"])
    ax2.set_yticks([0, 1])
    ax2.set_yticklabels(["Computed:\nCore/Secondary", "Computed:\nOther"])
    for i in range(2):
        for j in range(2):
            ax2.text(j, i, str(matrix[i][j]), ha="center", va="center",
                    fontsize=20, fontweight="bold")

    agreement = (tp + tn) / n * 100
    kappa = _cohens_kappa(tp, fp, fn, tn)
    ax2.set_title(f"Agreement: {agreement:.1f}% | κ={kappa:.3f}",
                 fontsize=12, fontweight="bold")
    plt.colorbar(im, ax=ax2)

    plt.tight_layout()
    fig.savefig(output_dir / "v4_06_tier_composition.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: v4_06_tier_composition.png")

    # ===== Figure 7: Length + Lacunae =====
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(22, 8), sharex=True)

    word_counts = [a.teaching_words for a in analyses]
    ax1.bar(range(n), word_counts, color=tier_colors, alpha=0.7, edgecolor="white", linewidth=0.3)
    ax1.set_ylabel("Teaching Text (words)")
    ax1.set_title("Chapter Length and Manuscript Condition", fontsize=14, fontweight="bold")
    if word_counts:
        avg_len = statistics.mean(word_counts)
        ax1.axhline(y=avg_len, color="blue", linestyle="--", linewidth=0.8,
                    label=f"Mean: {avg_len:.0f}")
        ax1.legend()

    lacunae = [a.lacunae_density for a in analyses]
    ax2.bar(range(n), lacunae, color="#9b59b6", alpha=0.7, edgecolor="white", linewidth=0.3)
    ax2.set_ylabel("Lacunae per 100 words")
    ax2.set_xticks(range(n))
    ax2.set_xticklabels([str(c) for c in ch_nums], rotation=90, fontsize=6)
    ax2.set_xlabel("Chapter Number")

    plt.tight_layout()
    fig.savefig(output_dir / "v4_07_length_lacunae.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: v4_07_length_lacunae.png")


def _cohens_kappa(tp, fp, fn, tn):
    """Calculate Cohen's kappa for inter-rater agreement."""
    n = tp + fp + fn + tn
    if n == 0:
        return 0.0
    po = (tp + tn) / n
    pe = ((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)) / (n * n)
    if pe == 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


# ============================================================
# REPORT GENERATION
# ============================================================

def generate_report(analyses: list[ChapterAnalysis], cluster_result: dict,
                    paragraphs: list[dict], output_dir: Path):
    """Generate comprehensive markdown report."""
    analyses = sorted(analyses, key=lambda a: a.chapter_number)
    n = len(analyses)

    # Statistics
    tier_counts = Counter(a.tier for a in analyses)
    core_chapters = [a for a in analyses if a.tier == "core"]
    secondary_chapters = [a for a in analyses if a.tier == "secondary"]

    # Agreement with manual extract
    comp_core = [a.tier in ("core", "secondary") for a in analyses]
    man_l1 = [a.in_manual_extract for a in analyses]
    tp = sum(1 for c, m in zip(comp_core, man_l1) if c and m)
    fp = sum(1 for c, m in zip(comp_core, man_l1) if c and not m)
    fn = sum(1 for c, m in zip(comp_core, man_l1) if not c and m)
    tn = sum(1 for c, m in zip(comp_core, man_l1) if not c and not m)
    agreement = (tp + tn) / n * 100 if n > 0 else 0
    kappa = _cohens_kappa(tp, fp, fn, tn)

    r = []
    r.append("# Kephalaia Layer Analysis v4 — Temporal-Axis Results")
    r.append("")
    r.append(f"**Date**: 2026-02-16")
    r.append(f"**Data Source**: LLM-cleaned structured JSON (output/cleaned/chapters/)")
    r.append(f"**Chapters analyzed**: {n}")
    r.append(f"**Total teaching words**: {sum(a.teaching_words for a in analyses):,}")
    r.append(f"**Total paragraphs**: {len(paragraphs)}")
    r.append("")
    r.append("---")
    r.append("")

    # Tier summary
    r.append("## 1. Tier Classification Summary")
    r.append("")
    r.append("| Tier | Count | % | Description |")
    r.append("|------|------:|--:|-------------|")
    tier_desc = {
        "core": "Strong teaching substrate + structural markers, minimal overlay",
        "secondary": "Teaching dominant with some overlay present",
        "mixed": "Both teaching and overlay vocabulary present",
        "pastoral": "Institutional/overlay vocabulary dominant — later layer",
        "hagiographic": "Biographical/veneration material dominant",
        "peripheral": "Low vocabulary signal — inconclusive",
        "fragmentary": "Too short for reliable analysis (<30 words)",
    }
    for tier in ["core", "secondary", "mixed", "pastoral", "hagiographic", "peripheral", "fragmentary"]:
        count = tier_counts.get(tier, 0)
        pct = count / n * 100 if n > 0 else 0
        desc = tier_desc.get(tier, "")
        r.append(f"| {tier.capitalize()} | {count} | {pct:.1f}% | {desc} |")
    r.append("")

    # Agreement with manual
    r.append("## 2. Agreement with Manual Layer 1 Extract")
    r.append("")
    r.append(f"| Metric | Value |")
    r.append(f"|--------|-------|")
    r.append(f"| Manual Layer 1 chapters | {sum(man_l1)} |")
    r.append(f"| Computed Core+Secondary | {sum(comp_core)} |")
    r.append(f"| True Positive | {tp} |")
    r.append(f"| True Negative | {tn} |")
    r.append(f"| False Positive (computed core, manual excluded) | {fp} |")
    r.append(f"| False Negative (computed other, manual included) | {fn} |")
    r.append(f"| **Agreement** | **{agreement:.1f}%** |")
    r.append(f"| **Cohen's κ** | **{kappa:.3f}** |")
    r.append("")

    # False negatives — chapters in manual L1 but not computed core
    fn_chapters = [a for a in analyses if a.in_manual_extract and a.tier not in ("core", "secondary")]
    if fn_chapters:
        r.append("### False Negatives (in manual extract but not computed core/secondary)")
        r.append("")
        for a in fn_chapters:
            r.append(f"- **Ch. {a.chapter_number}** ({a.title[:50]}): tier={a.tier}, "
                     f"score={a.composite_score:.2f}, cosmo={a.vocab_densities.get('cosmological', 0):.2f}, "
                     f"pastoral={a.vocab_densities.get('pastoral', 0):.2f}")
        r.append("")

    # False positives — chapters not in manual L1 but computed core
    fp_chapters = sorted([a for a in analyses if not a.in_manual_extract and a.tier in ("core", "secondary")],
                        key=lambda x: -x.composite_score)
    if fp_chapters:
        r.append("### Candidates for Restoration (computed core/secondary, not in manual extract)")
        r.append("")
        for a in fp_chapters:
            r.append(f"- **Ch. {a.chapter_number}** ({a.title[:50]}): tier={a.tier}, "
                     f"score={a.composite_score:.2f}")
            if a.vocab_terms.get("cosmological"):
                r.append(f"  - Cosmological: {', '.join(a.vocab_terms['cosmological'][:8])}")
        r.append("")

    # Top core chapters
    r.append("---")
    r.append("")
    r.append("## 3. Strongest Teaching Substrate Chapters (by Temporal Composite)")
    r.append("")
    r.append("| Rank | Ch. | Title | Score | Teaching | Overlay | Purity | Corr | Struct | Tier | Manual |")
    r.append("|------|-----|-------|------:|---------:|--------:|-------:|-----:|-------:|------|:------:|")
    for rank, a in enumerate(sorted(analyses, key=lambda x: -x.composite_score)[:25], 1):
        marker = "✅" if a.in_manual_extract else ""
        r.append(f"| {rank} | {a.chapter_number} | {a.title[:35]} | {a.composite_score:.2f} | "
                f"{a.teaching_density:.2f} | {a.overlay_density:.2f} | "
                f"{a.teaching_purity:.2f} | {a.correspondence_markers} | "
                f"{a.enumeration_markers} | "
                f"{a.tier} | {marker} |")
    r.append("")

    # Most contaminated
    r.append("## 4. Strongest Overlay Chapters (by Temporal Composite)")
    r.append("")
    r.append("| Rank | Ch. | Title | Score | Pastoral | NT | Hagio | Teaching | Tier |")
    r.append("|------|-----|-------|------:|---------:|---:|------:|---------:|------|")
    for rank, a in enumerate(sorted(analyses, key=lambda x: x.composite_score)[:20], 1):
        d = a.vocab_densities
        r.append(f"| {rank} | {a.chapter_number} | {a.title[:40]} | {a.composite_score:.2f} | "
                f"{d.get('pastoral', 0):.2f} | {d.get('nt_christian', 0):.2f} | "
                f"{d.get('hagiographic', 0):.2f} | {a.teaching_density:.2f} | {a.tier} |")
    r.append("")

    # Editor fatigue
    r.append("## 5. Editor Fatigue — Highest Intra-Chapter Shifts")
    r.append("")
    shifted = sorted([a for a in analyses if a.layer_shift_score > 0.3],
                    key=lambda x: -x.layer_shift_score)
    if shifted:
        r.append("| Ch. | Title | Shift | 1st Cosmo | 2nd Cosmo | 1st Pastoral | 2nd Pastoral |")
        r.append("|-----|-------|------:|----------:|----------:|-------------:|-------------:|")
        for a in shifted[:15]:
            r.append(f"| {a.chapter_number} | {a.title[:35]} | {a.layer_shift_score:.3f} | "
                    f"{a.first_half_cosmo:.2f} | {a.second_half_cosmo:.2f} | "
                    f"{a.first_half_pastoral:.2f} | {a.second_half_pastoral:.2f} |")
    else:
        r.append("*No significant intra-chapter shifts detected.*")
    r.append("")

    # Gardner flags
    r.append("## 6. Gardner Editorial Observations")
    r.append("")
    flagged = [a for a in analyses if a.gardner_flags]
    if flagged:
        r.append("| Ch. | Title | Flags |")
        r.append("|-----|-------|-------|")
        for a in sorted(flagged, key=lambda x: x.chapter_number):
            r.append(f"| {a.chapter_number} | {a.title[:40]} | {', '.join(a.gardner_flags)} |")
    else:
        r.append("*No editorial flags detected.*")
    r.append("")

    # NT citations from footnotes
    r.append("## 7. NT Citation Distribution (from Footnotes)")
    r.append("")
    cited = [a for a in analyses if a.nt_citations]
    if cited:
        r.append("| Ch. | Title | NT Citations | Tier |")
        r.append("|-----|-------|-------------|------|")
        for a in sorted(cited, key=lambda x: x.chapter_number):
            r.append(f"| {a.chapter_number} | {a.title[:40]} | {', '.join(a.nt_citations)} | {a.tier} |")
    else:
        r.append("*No NT citations found in structured footnotes.*")
    r.append("")

    # Structural patterns
    r.append("## 8. Structural Patterns (Temporal Markers)")
    r.append("")
    r.append(f"- Chapters with formulaic opening: "
            f"**{sum(1 for a in analyses if a.has_formulaic_opening)}** "
            f"({sum(1 for a in analyses if a.has_formulaic_opening)/n*100:.0f}%)")
    r.append(f"- Chapters with formulaic closing: "
            f"**{sum(1 for a in analyses if a.has_formulaic_closing)}** "
            f"({sum(1 for a in analyses if a.has_formulaic_closing)/n*100:.0f}%)")
    r.append(f"- Chapters with Q&A formula: "
            f"**{sum(1 for a in analyses if a.has_question_formula)}** "
            f"({sum(1 for a in analyses if a.has_question_formula)/n*100:.0f}%)")
    r.append(f"- Chapters with correspondence markers: "
            f"**{sum(1 for a in analyses if a.correspondence_markers > 0)}** "
            f"({sum(1 for a in analyses if a.correspondence_markers > 0)/n*100:.0f}%)")
    r.append("")

    # Correspondence-rich chapters
    corr_rich = sorted([a for a in analyses if a.correspondence_markers > 0],
                      key=lambda x: -x.correspondence_markers)
    if corr_rich:
        r.append("### Chapters with Highest Correspondence Marker Density")
        r.append("")
        r.append("| Ch. | Title | Corr Markers | Enum Markers | Tier | Score |")
        r.append("|-----|-------|:------------:|:------------:|------|------:|")
        for a in corr_rich[:15]:
            r.append(f"| {a.chapter_number} | {a.title[:40]} | {a.correspondence_markers} | "
                    f"{a.enumeration_markers} | {a.tier} | {a.composite_score:.2f} |")
    r.append("")

    # Cluster profiles
    if cluster_result:
        r.append("## 9. TF-IDF Cluster Profiles")
        r.append("")
        r.append(f"Optimal k={cluster_result['optimal_k']} "
                f"(silhouette={cluster_result['silhouette_scores'].get(cluster_result['optimal_k'], 'N/A')})")
        r.append("")
        for k, profile in sorted(cluster_result["cluster_profiles"].items()):
            r.append(f"### Cluster {k}: {profile['name']} (n={profile['size']})")
            r.append(f"- Avg composite: {profile['avg_composite']:.2f}")
            r.append(f"- Top TF-IDF terms: {', '.join(profile['top_terms'][:10])}")
            r.append(f"- Chapters: {', '.join(str(c) for c in profile['chapters'])}")
            r.append(f"- Avg densities: {profile['avg_densities']}")
            r.append("")

    # Full appendix
    r.append("---")
    r.append("")
    r.append("## Appendix: Full Chapter Data")
    r.append("")
    r.append("| Ch. | Title | Words | Score | Teach | Overlay | Purity | Shift | Tier | Manual |")
    r.append("|-----|-------|------:|------:|------:|--------:|-------:|------:|------|:------:|")
    for a in analyses:
        marker = "✅" if a.in_manual_extract else ""
        r.append(f"| {a.chapter_number} | {a.title[:25]} | {a.teaching_words} | "
                f"{a.composite_score:.2f} | {a.teaching_density:.2f} | "
                f"{a.overlay_density:.2f} | {a.teaching_purity:.2f} | "
                f"{a.layer_shift_score:.3f} | "
                f"{a.tier} | {marker} |")
    r.append("")

    report_text = "\n".join(r)
    report_path = output_dir / "v4_report.md"
    report_path.write_text(report_text, encoding="utf-8")
    print(f"  Saved: v4_report.md")
    return report_text


# ============================================================
# MAIN
# ============================================================

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("KEPHALAIA LAYER ANALYSIS v4 — Temporal-Axis Textual Critical Analysis")
    print("=" * 70)
    print()

    # 1. Load cleaned chapters
    print("[1/7] Loading cleaned chapters...")
    chapters = load_chapters()
    print(f"  Loaded: {len(chapters)} chapters from {CHAPTERS_DIR}")
    total_words = sum(ch.teaching_words for ch in chapters)
    print(f"  Total teaching words: {total_words:,}")
    print(f"  Total synopsis words: {sum(ch.synopsis_words for ch in chapters):,}")
    print(f"  Total footnotes: {sum(len(ch.footnotes) for ch in chapters)}")

    # 2. Analyze each chapter
    print("[2/7] Analyzing chapters...")
    analyses = []
    for ch in chapters:
        a = analyze_chapter(ch)
        a.tier = classify_tier(a)
        analyses.append(a)

    tier_counts = Counter(a.tier for a in analyses)
    print(f"  Tier distribution: {dict(tier_counts)}")

    avg_teaching = statistics.mean([a.teaching_density for a in analyses])
    avg_overlay = statistics.mean([a.overlay_density for a in analyses])
    avg_purity = statistics.mean([a.teaching_purity for a in analyses])
    print(f"  Avg teaching substrate density: {avg_teaching:.3f} per 100 words")
    print(f"  Avg overlay density: {avg_overlay:.3f} per 100 words")
    print(f"  Avg teaching purity: {avg_purity:.3f}")

    # 3. TF-IDF clustering
    print("[3/7] Running TF-IDF clustering...")
    cluster_result = cluster_chapters(chapters, analyses)

    # 4. Paragraph-level analysis
    print("[4/7] Paragraph-level analysis...")
    paragraphs = analyze_paragraphs(chapters)
    print(f"  Total paragraphs: {len(paragraphs)}")

    # 5. Save raw data
    print("[5/7] Saving data...")
    data_path = OUTPUT_DIR / "v4_data.json"
    raw_data = []
    for a in analyses:
        d = asdict(a)
        raw_data.append(d)
    data_path.write_text(json.dumps(raw_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Saved: v4_data.json")

    para_path = OUTPUT_DIR / "v4_paragraphs.json"
    para_path.write_text(json.dumps(paragraphs, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Saved: v4_paragraphs.json")

    # 6. Report
    print("[6/7] Generating report...")
    generate_report(analyses, cluster_result, paragraphs, OUTPUT_DIR)

    # 7. Visualizations
    print("[7/7] Generating visualizations...")
    try:
        generate_visualizations(analyses, cluster_result, OUTPUT_DIR)
    except Exception as e:
        print(f"  WARNING: Visualization error: {e}")

    print()
    print("=" * 70)
    print("ANALYSIS COMPLETE")
    print(f"Output: {OUTPUT_DIR}")
    print("=" * 70)


if __name__ == "__main__":
    main()
