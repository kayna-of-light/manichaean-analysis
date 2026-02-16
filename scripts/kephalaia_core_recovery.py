#!/usr/bin/env python3
"""
Kephalaia Core Recovery Analysis v2
====================================
Data-driven identification of editorial layers in the Kephalaia of the Teacher.

Rather than imposing predetermined layers, this analysis:
  1. Parses ALL chapters with robust OCR-aware regex
  2. Uses TF-IDF + unsupervised clustering to discover natural groupings
  3. Applies expanded vocabulary profiling as secondary validation
  4. Detects editor fatigue, formulaic patterns, and structural anomalies
  5. Produces a composite "originality" score ranking chapters by proximity
     to the original cosmological teaching core

Output:
  - output/analysis/v2_report.md          — Comprehensive analysis report
  - output/analysis/v2_data.json          — Per-chapter analysis data
  - output/analysis/v2_01_pca_clusters.png — PCA scatter colored by cluster
  - output/analysis/v2_02_dendrogram.png   — Hierarchical clustering dendrogram
  - output/analysis/v2_03_category_heatmap.png — Vocabulary category profiles
  - output/analysis/v2_04_cluster_profile.png  — Cluster characterization
  - output/analysis/v2_05_originality.png      — Originality score ranking
  - output/analysis/v2_06_editor_fatigue.png   — Intra-chapter shift detection
"""

import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.metrics import silhouette_score, silhouette_samples
from sklearn.preprocessing import StandardScaler
from scipy.cluster.hierarchy import dendrogram, linkage
from scipy.spatial.distance import pdist

# ============================================================
# CONFIGURATION
# ============================================================

KEPHALAIA_PATH = Path("output/texts/Kephalaia_of_the_Teacher.md")
OUTPUT_DIR = Path("output/analysis")
MIN_WORDS_FOR_CLUSTERING = 50  # chapters shorter than this are "fragmentary"
MAX_K = 7  # max clusters to test
RANDOM_STATE = 42

# Chapters in the previous manual Layer 1 extract (for comparison only)
MANUAL_LAYER1 = {2, 3, 6, 38, 39, 40, 41, 55, 56, 62, 70, 71, 72, 74, 75,
                 85, 86, 109, 114, 115, 122}

# ============================================================
# 1. ROBUST CHAPTER PARSER
# ============================================================

def find_chapter_markers(lines: list[str]) -> list[tuple[int, int]]:
    """
    Find ALL chapter markers in the OCR'd text.
    Handles both ··· (middots) and ... (regular dots) formats,
    with or without trailing dots, and with optional page references.
    """
    markers = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        # Must start with 2+ dots or middots
        if not re.match(r'^[·.]{2,}', stripped):
            continue

        # Special: ··· (Introduction) ···
        if re.search(r'\(Introduction\)', stripped, re.IGNORECASE):
            markers.append((i, 0))
            continue

        # Special: ··· . ··· (Chapter 1 — OCR misread of "1" as ".")
        if re.match(r'^[·]{2,}\s*\.\s*[·]{2,}\s*$', stripped):
            markers.append((i, 1))
            continue

        # General: extract a number from the line
        # Remove leading dots/middots
        rest = re.sub(r'^[·.\s]+', '', stripped)
        # Try to match a number at the start of what remains
        m = re.match(r'^(\d+)', rest)
        if not m:
            continue

        num = int(m.group(1))
        if num < 1 or num > 150:
            continue

        # Validate: after removing dots, number, page refs, nothing meaningful remains
        after_num = rest[m.end():]
        # Remove trailing dots/middots/spaces
        after_num = re.sub(r'^[·.\s]+', '', after_num)
        # Remove optional page reference like (197,1 - 200, 8)
        after_num = re.sub(r'\([\d,\s\-\.]+\)', '', after_num)
        after_num = after_num.strip()

        if after_num == '' or len(after_num) < 3:
            markers.append((i, num))

    # Sort by line number and deduplicate by chapter number
    markers.sort(key=lambda x: x[0])
    seen = set()
    unique = []
    for line_num, ch_num in markers:
        if ch_num not in seen:
            seen.add(ch_num)
            unique.append((line_num, ch_num))
    return unique


def separate_commentary_and_teaching(block_lines: list[str]) -> tuple[str, str]:
    """
    Separate Gardner's editorial commentary from Mani's teaching text.
    Gardner's commentary appears first (modern scholarly English),
    then the teaching text begins (translated Coptic).
    """
    commentary_lines = []
    teaching_lines = []
    text_started = False

    for line in block_lines:
        stripped = line.strip()

        # Skip structural markers
        if re.match(r'^[·.]{2,}', stripped):
            continue
        if re.match(r'^\([\d,\s\-\.]+\)', stripped):
            continue
        if stripped.startswith("---"):
            continue
        if re.match(r'^THE KEPHALAIA', stripped):
            continue
        if re.match(r'^CHAPTER\s+', stripped):
            continue
        if not stripped:
            if text_started:
                teaching_lines.append(line)
            continue

        # Detect transition to teaching text
        if not text_started:
            # Teaching text indicators
            teaching_starts = [
                r'once again',
                r'the first chapt',
                r'the apostle\s+(sa|speak)',
                r'our (master|father|enlightener)',
                r'the enlightener',
                r'again.*(he|the apostle|our)',
                r'^\d+\s+the first',
                r'^[A-Z][a-z]*\s+again',
                r'^\[\s*on',
                r'^on\[?c',
                r'^also\s+concerning',
                r'^\[?\s*once',
                r'a disciple',
                r'a catechumen',
                r'blessed is',
                r'^\[',  # Lacunae at start often = teaching text
            ]

            is_teaching = False
            lower = stripped.lower()

            # Gardner commentary characteristics:
            # - References to other chapters: "see chapter X", "compare Y"
            # - Scholarly language: "evidences", "schematic", "docetic"
            # - Parenthetical references: "(H. 41.11-20)", "(Puech 1949: 144)"
            # - Sentences without lacunae brackets

            for pattern in teaching_starts:
                if re.search(pattern, lower):
                    is_teaching = True
                    break

            # Also check: if line has lacunae brackets or page numbers
            # typical of the Coptic text
            if not is_teaching and re.search(r'\[\s*\.{3,}\s*\]', stripped):
                is_teaching = True
            if not is_teaching and re.search(r'\(\d+\)', stripped):
                # Page marker like (17)
                is_teaching = True

            # Check for scholarly refs (Gardner)
            has_scholarly = bool(re.search(
                r'(see\s+(also\s+)?chapter|compare|evidences|'
                r'schematic|docetic|redact|interpolat|'
                r'Puech|Bohlig|Polotsky|H\.\s*\d|PsBk|'
                r'see\s+further|has been discussed|'
                r'the text\s+(does not|cannot|is)|'
                r'this (kephalaion|chapter)\s+(is|provides|discusses))',
                stripped, re.IGNORECASE))

            if is_teaching and not has_scholarly:
                text_started = True
                teaching_lines.append(line)
            else:
                commentary_lines.append(line)
        else:
            teaching_lines.append(line)

    return "\n".join(commentary_lines), "\n".join(teaching_lines)


def parse_chapters(text: str) -> list[dict]:
    """Parse all chapters from the Kephalaia with robust OCR handling."""
    lines = text.split("\n")
    markers = find_chapter_markers(lines)

    print(f"  Found {len(markers)} chapter markers")
    print(f"  Chapter numbers: {sorted(m[1] for m in markers)}")

    chapters = []
    for idx, (start_line, ch_num) in enumerate(markers):
        # End is line before next marker (or end of file)
        if idx + 1 < len(markers):
            end_line = markers[idx + 1][0] - 1
        else:
            end_line = len(lines) - 1

        block = lines[start_line:end_line + 1]

        # Extract title from first ~15 lines
        title = extract_title(block)

        # Separate Gardner commentary from teaching
        gardner_text, teaching_text = separate_commentary_and_teaching(block)

        # Word count of teaching text
        words = teaching_text.split()
        word_count = len(words)

        chapters.append({
            "number": ch_num,
            "title": title,
            "teaching_text": teaching_text,
            "gardner_text": gardner_text,
            "full_text": "\n".join(block),
            "word_count": word_count,
            "line_start": start_line,
            "line_end": end_line,
        })

    return chapters


def extract_title(block: list[str]) -> str:
    """Extract chapter title from the first few lines of a chapter block."""
    for line in block[:15]:
        stripped = line.strip()
        # Skip markers, page refs, empty lines
        if not stripped or re.match(r'^[·.]{2,}', stripped):
            continue
        if re.match(r'^\([\d,\s\-\.]+\)', stripped):
            continue
        if stripped.startswith("---") or re.match(r'^(THE KEPHALAIA|CHAPTER\s)', stripped):
            continue

        # Look for "Concerning..." pattern
        m = re.search(r'(Concerning\s+.+?)(?:\.|$)', stripped)
        if m:
            return m.group(1).strip().rstrip(".")

        # Look for "The Chapter of/on..." pattern
        m = re.search(r'(The Chapter\s+(?:of|on)\s+.+?)(?:\.|$)', stripped)
        if m:
            return m.group(1).strip().rstrip(".")

        # Look for "The Interpretation..." pattern
        m = re.search(r'(The Interpretation\s+.+?)(?:\.|$)', stripped)
        if m:
            return m.group(1).strip().rstrip(".")

        # Look for other descriptive lines
        cleaned = stripped.strip("/").strip()
        if cleaned and len(cleaned) > 10 and not re.match(r'^[\d\s\(\),\-\.]+$', cleaned):
            if not re.match(r'^(THE KEPHALAIA|CHAPTER|---|\*)', cleaned):
                return cleaned[:100]

    return f"(Untitled)"


# ============================================================
# 2. TEXT PREPROCESSING
# ============================================================

STOPWORDS = {
    "the", "and", "of", "to", "in", "that", "is", "it", "for", "he",
    "his", "him", "they", "them", "their", "this", "which", "who",
    "was", "were", "are", "be", "been", "has", "have", "had", "but",
    "not", "with", "from", "all", "its", "will", "shall", "may",
    "also", "one", "out", "upon", "them", "there", "or", "an", "as",
    "if", "so", "do", "did", "can", "would", "could", "she", "her",
    "you", "your", "we", "our", "my", "me", "no", "nor", "yet",
    "than", "then", "when", "where", "how", "what", "these", "those",
    "each", "every", "some", "any", "own", "too", "about", "after",
    "before", "again", "other", "because", "even", "while", "thus",
    "into", "over", "under", "between", "through", "being", "like",
    "more", "another", "though", "still", "however", "rather", "only",
    "very", "same", "first", "second", "third", "fourth", "fifth",
    "great", "said", "says", "say", "spoke", "speak", "speaks",
    "time", "way", "come", "came", "comes", "gave", "gives", "give",
    "made", "make", "makes", "find", "found", "knows", "know",
    "shall", "its", "let", "now", "see", "here",
}


def clean_for_analysis(text: str) -> str:
    """Clean teaching text for vocabulary analysis."""
    # Remove page markers like (17), (K.xxx,yy)
    text = re.sub(r'\(\d+\)', '', text)
    text = re.sub(r'\(K\.[\d,\s]+\)', '', text)
    # Remove footnote markers *N
    text = re.sub(r'\*\d+', '', text)
    # Remove verse/line numbers at start of lines
    text = re.sub(r'^\d+\s', '', text, flags=re.MULTILINE)
    # Remove lacunae brackets content but keep surrounding text
    text = re.sub(r'\[\s*\.{2,}\s*\]', ' ', text)
    # Remove remaining bracket artifacts
    text = re.sub(r'[\[\]]', '', text)
    # Remove scripture refs like Mt. 6:21, Jn. 15:13 etc.
    text = re.sub(r'(?:Mt|Mk|Lk|Jn|Cor|Phil|Gal|Rom|Col|Eph)\.\s*\d+[:\d]*', '', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def tokenize(text: str) -> list[str]:
    """Tokenize text to lowercase words, removing stopwords."""
    text = clean_for_analysis(text)
    tokens = re.findall(r'[a-z]+(?:[\'-][a-z]+)*', text.lower())
    return [t for t in tokens if t not in STOPWORDS and len(t) > 2]


# ============================================================
# 3. VOCABULARY CATEGORIES (Supervised Signal)
# ============================================================
# These are NOT used for clustering — only for post-hoc characterization.
# The clustering is purely data-driven via TF-IDF.

VOCAB_CATEGORIES = {
    "cosmological": {
        # Deities and cosmic figures
        "father of greatness", "mother of life", "first man", "living spirit",
        "third ambassador", "ambassador", "beloved of the lights",
        "virgin of light", "pillar of glory", "king of honour",
        "keeper of splendour", "great builder", "adam of light",
        "jesus the splendour",  # cosmic figure, not NT Jesus
        "column of glory", "perfect man", "light mind",
        "great nous", "call and answer", "summons and obedience",
        "last statue", "living soul",
        # Cosmic mechanisms
        "five elements", "five sons", "five storehouses", "five trees",
        "five worlds", "five rulers", "five spirits", "five bodies",
        "five tastes", "five fathers", "five limbs",
        "light elements", "living fire", "living water", "living wind",
        "living air", "cross of light",
        "ship of living", "light ship",
        "new aeon", "great fire", "dissolution",
        # Cosmic structures
        "land of darkness", "land of light", "aeons of light",
        "realms of darkness", "firmament", "zodiac",
        # Processes
        "light gathered", "ascent", "descent", "contest",
        "mixture", "mingling", "purification", "separation",
        "realm of light", "kingdom of light",
        "storehouses", "lump",
    },

    "persian_substrate": {
        # Iranian/Zoroastrian terms
        "zarathustra", "zoroaster", "persia", "persian", "hystaspes",
        "magi", "magian",
        # Cosmic warfare (Iranian signature)
        "king of the realms", "king of darkness",
        "land of darkness", "five wars",
    },

    "nt_christian": {
        # NT figure names (as names, not cosmic titles)
        "jesus christ", "apostle of jesus", "son of god",
        "holy spirit",
        # NT apostle names
        "paul", "matthew", "john", "mark", "luke", "peter",
        "judas", "iscariot",
        # NT sacramental
        "baptism", "eucharist", "communion",
        # Pauline vocabulary
        "grace", "redemption",
        # NT citations (detected separately too)
        "gospel of john", "gospel of matthew",
        "written in the gospel", "the saviour has said",
        "as it is written",
    },

    "hagiographic": {
        # Mani titles & biographical
        "the enlightener", "paraclete", "apostle of light",
        "lord manichaios", "our father", "our master",
        "twin spirit", "spirit of truth",
        # Canonical scriptures mentioned
        "great gospel", "treasury of life", "treatise",
        "book of mysteries", "psalms and prayers",
        "epistle", "epistles",
        # Miracle/biographical language
        "his journeying", "missionary", "his revelation",
    },

    "pastoral": {
        # Church practice
        "fasting", "fast", "alms", "alms-giving", "prayer", "prayers",
        "confession", "commandments", "sabbath",
        "lord's day",
        # Church hierarchy
        "elect", "catechumen", "catechumens",
        "teacher", "teachers", "leaders", "bishop",
        "hearer", "hearers",
        # Ethics and conduct
        "sin", "sinners", "wicked", "righteous",
        "commandment", "obey", "obedience",
        "fornication", "lust", "gluttony",
        "self-control", "chastity",
    },
}

# Single-word markers that are strong signals when found
SINGLE_WORD_MARKERS = {
    "nt_christian": {"paul", "matthew", "john", "mark", "luke", "peter",
                     "judas", "baptism", "eucharist", "grace"},
    "cosmological": {"firmament", "zodiac", "conduits", "storehouses",
                     "dissolution", "purification", "lump", "mingling",
                     "mixture", "ascent"},
    "hagiographic": {"paraclete", "enlightener", "manichaios"},
    "pastoral": {"fasting", "catechumen", "catechumens", "alms",
                 "commandments", "sabbath", "confession"},
}


def compute_category_densities(text: str, word_count: int) -> dict:
    """Compute vocabulary category densities per 100 words."""
    if word_count == 0:
        return {cat: 0.0 for cat in VOCAB_CATEGORIES}

    lower = text.lower()
    densities = {}
    details = {}

    for cat, phrases in VOCAB_CATEGORIES.items():
        total_hits = 0
        found_terms = []
        for phrase in phrases:
            count = len(re.findall(re.escape(phrase), lower))
            if count > 0:
                total_hits += count
                found_terms.append((phrase, count))

        # Also count single-word markers
        if cat in SINGLE_WORD_MARKERS:
            words_in_text = set(re.findall(r'[a-z]+', lower))
            for marker in SINGLE_WORD_MARKERS[cat]:
                # Count occurrences (not just presence)
                count = len(re.findall(r'\b' + re.escape(marker) + r'\b', lower))
                if count > 0:
                    total_hits += count
                    found_terms.append((marker, count))

        densities[cat] = (total_hits / word_count) * 100
        details[cat] = found_terms

    return densities, details


# ============================================================
# 4. STRUCTURAL FEATURES
# ============================================================

def compute_structural_features(text: str) -> dict:
    """Compute structural features of a chapter's teaching text."""
    if not text.strip():
        return {
            "word_count": 0, "sentence_count": 0, "avg_sentence_length": 0,
            "ttr": 0, "lacunae_density": 0, "lacunae_count": 0,
        }

    words = text.split()
    word_count = len(words)

    # Sentence segmentation (approximate)
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]
    sentence_count = max(len(sentences), 1)
    avg_sentence_length = word_count / sentence_count

    # Type-token ratio (vocabulary richness)
    tokens = [w.lower() for w in re.findall(r'[a-z]+', text.lower()) if len(w) > 2]
    ttr = len(set(tokens)) / max(len(tokens), 1)

    # Lacunae density (manuscript damage indicator)
    lacunae = re.findall(r'\[[\s.]*\]|\[\s*\.\.\.\s*\]|\.\.\.\s*\]|\[\s*\.\.\.', text)
    lacunae_density = (len(lacunae) / max(word_count, 1)) * 100

    return {
        "word_count": word_count,
        "sentence_count": sentence_count,
        "avg_sentence_length": round(avg_sentence_length, 1),
        "ttr": round(ttr, 3),
        "lacunae_density": round(lacunae_density, 2),
        "lacunae_count": len(lacunae),
    }


# ============================================================
# 5. FORMULAIC PATTERN DETECTION
# ============================================================

FORMULAIC_OPENINGS = [
    (r'once again\s+(the\s+)?(enlightener|apostle|our\s+father)', "standard_teaching"),
    (r'once again\s+(he|the apostle|our)\s+speak', "standard_teaching"),
    (r'once again\s+a\s+disciple', "disciple_question"),
    (r'a catechumen\s+ask', "catechumen_question"),
    (r'the catechumen\s+ask', "catechumen_question"),
    (r'then speaks?\s+our\s+master', "master_speaks"),
    (r'a disciple\s+(speak|question|ask)', "disciple_question"),
    (r'another disciple\s+question', "disciple_question"),
    (r'the first chapt', "chapter_reference"),
]

FORMULAIC_CLOSINGS = [
    (r'blessed is\s+(every\s+one|whoever|he)', "blessing_close"),
    (r'he (was persuaded|rejoiced).*he (says|made)', "disciple_response"),
    (r'when.*disciple.*heard.*he\s+(rejoiced|was persuaded)', "disciple_response"),
    (r'for ever and ever', "eternal_close"),
]


def detect_formulaic_patterns(text: str) -> dict:
    """Detect formulaic opening and closing patterns."""
    lower = text.lower()

    # Check first ~200 chars for opening
    opening_text = lower[:500]
    openings = []
    for pattern, label in FORMULAIC_OPENINGS:
        if re.search(pattern, opening_text):
            openings.append(label)

    # Check last ~300 chars for closing
    closing_text = lower[-800:]
    closings = []
    for pattern, label in FORMULAIC_CLOSINGS:
        if re.search(pattern, closing_text):
            closings.append(label)

    return {
        "openings": openings,
        "closings": closings,
        "has_standard_opening": bool(openings),
        "has_standard_closing": bool(closings),
    }


# ============================================================
# 6. NT CITATION DETECTION
# ============================================================

def detect_nt_citations(text: str) -> list[str]:
    """Detect NT scripture citations and references."""
    citations = []

    # Footnote-style: *N followed by book reference
    for m in re.finditer(r'\*(\d+)\s+.*?((?:Mt|Mk|Lk|Jn|Cor|Phil|Gal|Rom|Col|Eph)\.?\s*\d+)', text):
        citations.append(m.group(2))

    # Inline: "as the saviour has said" + nearby NT ref
    for m in re.finditer(r'(?:Mt|Mk|Lk|Jn|1?\s*Cor|Phil|Gal|Rom|Col|Eph)\.?\s*\d+(?::\d+)?', text):
        ref = m.group(0)
        if ref not in citations:
            citations.append(ref)

    # "Gospel of Thomas" reference
    if re.search(r'gospel of thomas', text, re.IGNORECASE):
        citations.append("Gospel of Thomas")

    return citations


# ============================================================
# 7. GARDNER EDITORIAL FLAGS
# ============================================================

GARDNER_FLAGS = {
    "redaction": r'(?:redact|later\s+addition|secondary\s+(?:addition|material)|editorial|'
                 r'inserted|interpolat|emend|rework|revision)',
    "corruption": r'(?:corrupt|garbled|unintelligible|error in|mistranslat|confused\s+text)',
    "uncertain": r'(?:uncertain|unclear|difficult to|obscure|problematic|'
                 r'debated|much discussed)',
    "textual_development": r'(?:textual development|evolved|developed|expanded|'
                           r'secondary to|later than)',
    "parallel_text": r'(?:parallel|compare\s+(?:also\s+)?chapter|cf\.\s*chapter|see\s+also\s+chapter)',
    "christian_connection": r'(?:christian|christolog|docetic|canonical|gospel\s+of\s+john|'
                            r'pauline|johannine|new testament)',
    "gnostic_connection": r'(?:gnostic|mandae|nag hammadi|valentinian|sethian)',
    "mani_attribution": r'(?:mani\'s own|attribut(?:ed|ion)\s+to\s+mani|unmistakably\s+mani)',
    "buddhist_connection": r'(?:buddhis|indian|karmic|transmi(?:grat|ssion)|reincarnation)',
    "zoroastrian_connection": r'(?:zoroastr|zarathustr|iranian|persian\s+(?:root|origin|influence))',
}


def detect_gardner_flags(gardner_text: str) -> list[str]:
    """Detect editorial flags in Gardner's commentary."""
    lower = gardner_text.lower()
    flags = []
    for flag_name, pattern in GARDNER_FLAGS.items():
        if re.search(pattern, lower):
            flags.append(flag_name)
    return flags


# ============================================================
# 8. EDITOR FATIGUE DETECTION
# ============================================================

def compute_editor_fatigue(text: str) -> dict:
    """
    Detect intra-chapter vocabulary shift.
    Compares vocabulary profile of first half vs second half.
    A high shift suggests composite authorship.
    """
    words = text.split()
    if len(words) < 60:
        return {"shift_score": 0.0, "first_half": {}, "second_half": {}}

    mid = len(words) // 2
    first_half = " ".join(words[:mid])
    second_half = " ".join(words[mid:])

    # Compute category densities for each half
    fh_count = len(first_half.split())
    sh_count = len(second_half.split())

    fh_densities, _ = compute_category_densities(first_half, fh_count)
    sh_densities, _ = compute_category_densities(second_half, sh_count)

    # Shift = change in cosmological density (decrease = dilution)
    # Plus change in NT/hagiographic density (increase = interpolation)
    cosmo_shift = fh_densities.get("cosmological", 0) - sh_densities.get("cosmological", 0)
    nt_shift = sh_densities.get("nt_christian", 0) - fh_densities.get("nt_christian", 0)
    hagio_shift = sh_densities.get("hagiographic", 0) - fh_densities.get("hagiographic", 0)

    # Combined shift: positive = first half more cosmological, second half more interpolated
    shift_score = cosmo_shift + nt_shift + hagio_shift

    return {
        "shift_score": round(shift_score, 3),
        "first_half_cosmological": round(fh_densities.get("cosmological", 0), 3),
        "second_half_cosmological": round(sh_densities.get("cosmological", 0), 3),
        "first_half_nt": round(fh_densities.get("nt_christian", 0), 3),
        "second_half_nt": round(sh_densities.get("nt_christian", 0), 3),
    }


# ============================================================
# 9. TF-IDF + CLUSTERING (Unsupervised Core)
# ============================================================

def build_tfidf_matrix(chapters: list[dict]) -> tuple:
    """
    Build TF-IDF matrix from teaching texts.
    Uses unigrams + bigrams, with document frequency filtering.
    Returns: tfidf_matrix, feature_names, vectorizer, valid_indices
    """
    # Only include chapters with enough text
    valid_indices = [i for i, ch in enumerate(chapters)
                     if ch["word_count"] >= MIN_WORDS_FOR_CLUSTERING]

    texts = [clean_for_analysis(chapters[i]["teaching_text"]) for i in valid_indices]

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.90,
        stop_words=list(STOPWORDS),
        token_pattern=r'[a-z]+(?:[\'-][a-z]+)*',
        lowercase=True,
        max_features=2000,
    )

    tfidf_matrix = vectorizer.fit_transform(texts)
    feature_names = vectorizer.get_feature_names_out()

    return tfidf_matrix, feature_names, vectorizer, valid_indices


def find_optimal_clusters(tfidf_matrix, max_k=MAX_K):
    """
    Test k=2..max_k and find optimal number of clusters
    using silhouette coefficient.
    """
    if tfidf_matrix.shape[0] < 4:
        return 2, {2: 0.0}

    scores = {}
    for k in range(2, min(max_k + 1, tfidf_matrix.shape[0])):
        km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
        labels = km.fit_predict(tfidf_matrix)
        score = silhouette_score(tfidf_matrix, labels)
        scores[k] = round(score, 4)

    optimal_k = max(scores, key=scores.get)
    return optimal_k, scores


def cluster_chapters(tfidf_matrix, k):
    """Run K-means clustering with k clusters."""
    km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=20)
    labels = km.fit_predict(tfidf_matrix)
    return labels, km


def characterize_clusters(tfidf_matrix, feature_names, labels, chapters,
                          valid_indices):
    """
    Characterize each cluster by its most distinctive vocabulary
    and average category densities.
    """
    n_clusters = len(set(labels))
    dense = tfidf_matrix.toarray() if hasattr(tfidf_matrix, 'toarray') else tfidf_matrix

    cluster_info = {}
    for c in range(n_clusters):
        mask = (labels == c)
        if not mask.any():
            continue

        # Mean TF-IDF within cluster
        cluster_mean = dense[mask].mean(axis=0)
        # Mean TF-IDF outside cluster
        other_mask = ~mask
        other_mean = dense[other_mask].mean(axis=0) if other_mask.any() else np.zeros_like(cluster_mean)

        # Distinctiveness = cluster_mean - other_mean
        distinctiveness = cluster_mean - other_mean
        top_indices = distinctiveness.argsort()[-20:][::-1]
        top_terms = [(feature_names[j], round(float(distinctiveness[j]), 4))
                     for j in top_indices if distinctiveness[j] > 0]

        # Average category densities for chapters in this cluster
        ch_indices = [valid_indices[i] for i in range(len(labels)) if labels[i] == c]
        avg_densities = defaultdict(float)
        for ci in ch_indices:
            ch = chapters[ci]
            densities, _ = compute_category_densities(ch["teaching_text"], ch["word_count"])
            for cat, val in densities.items():
                avg_densities[cat] += val
        for cat in avg_densities:
            avg_densities[cat] /= len(ch_indices)

        # Average structural features
        avg_words = np.mean([chapters[ci]["word_count"] for ci in ch_indices])
        chapter_numbers = [chapters[ci]["number"] for ci in ch_indices]

        cluster_info[c] = {
            "size": int(mask.sum()),
            "distinctive_terms": top_terms,
            "avg_densities": dict(avg_densities),
            "avg_word_count": round(avg_words, 0),
            "chapter_numbers": sorted(chapter_numbers),
        }

    return cluster_info


def label_clusters(cluster_info):
    """
    Assign interpretive labels to clusters based on their characteristics.
    The cluster with highest cosmological density is the "original core" candidate.
    """
    labels = {}
    # Sort clusters by cosmological density (descending)
    ranked = sorted(cluster_info.items(),
                    key=lambda x: x[1]["avg_densities"].get("cosmological", 0),
                    reverse=True)

    for rank, (c, info) in enumerate(ranked):
        cosmo = info["avg_densities"].get("cosmological", 0)
        nt = info["avg_densities"].get("nt_christian", 0)
        hagio = info["avg_densities"].get("hagiographic", 0)
        pastoral = info["avg_densities"].get("pastoral", 0)

        if rank == 0:
            labels[c] = "Core Cosmological"
        elif nt > 0.1:
            labels[c] = "NT-Influenced"
        elif pastoral > cosmo:
            labels[c] = "Pastoral/Catechetical"
        elif hagio > cosmo:
            labels[c] = "Hagiographic/Biographical"
        else:
            labels[c] = f"Mixed/Transitional"

    return labels


# ============================================================
# 10. COMPOSITE ORIGINALITY SCORING
# ============================================================

def compute_originality_scores(chapters, cluster_labels_map, cluster_label_names,
                               valid_indices):
    """
    Compute a composite originality score for each chapter.
    Higher = more likely original core material.

    Components:
      - Cosmological vocabulary density (+)
      - Persian substrate density (+)
      - NT/Christian density (-)
      - Hagiographic density (-)
      - Pastoral density (-/neutral)
      - Cluster assignment (core cluster = bonus)
      - Standard formulaic opening (+)
      - Low editor fatigue (+)
    """
    scores = []

    # Find which cluster label is "Core Cosmological"
    core_cluster = None
    for c, name in cluster_label_names.items():
        if "Core" in name:
            core_cluster = c
            break

    for i, ch in enumerate(chapters):
        if ch["number"] == 0:  # Skip Introduction
            scores.append({"originality": -999, "components": {}})
            continue

        wc = ch["word_count"]
        if wc < 10:
            scores.append({"originality": -999, "components": {}})
            continue

        densities, _ = compute_category_densities(ch["teaching_text"], wc)
        fatigue = compute_editor_fatigue(ch["teaching_text"])
        formulaic = detect_formulaic_patterns(ch["teaching_text"])

        # Component scores (each normalized roughly 0-5 range)
        cosmo_score = min(densities.get("cosmological", 0) * 1.5, 5.0)
        persian_score = min(densities.get("persian_substrate", 0) * 3.0, 3.0)
        nt_penalty = min(densities.get("nt_christian", 0) * 5.0, 5.0)
        hagio_penalty = min(densities.get("hagiographic", 0) * 2.0, 3.0)
        pastoral_penalty = min(densities.get("pastoral", 0) * 0.5, 2.0)

        # Cluster bonus
        cluster_bonus = 0.0
        if i in valid_indices:
            vi_pos = valid_indices.index(i)
            if vi_pos < len(cluster_labels_map):
                assigned_cluster = cluster_labels_map[vi_pos]
                if assigned_cluster == core_cluster:
                    cluster_bonus = 2.0

        # Formulaic bonus (standard teaching structure)
        formulaic_bonus = 1.0 if formulaic["has_standard_opening"] else 0.0

        # Fatigue penalty (high positive shift = contaminated second half)
        fatigue_penalty = max(0, fatigue["shift_score"] * 0.3)

        # Composite
        originality = (cosmo_score + persian_score + cluster_bonus + formulaic_bonus
                       - nt_penalty - hagio_penalty - pastoral_penalty - fatigue_penalty)

        scores.append({
            "originality": round(originality, 3),
            "components": {
                "cosmological": round(cosmo_score, 3),
                "persian": round(persian_score, 3),
                "nt_penalty": round(-nt_penalty, 3),
                "hagio_penalty": round(-hagio_penalty, 3),
                "pastoral_penalty": round(-pastoral_penalty, 3),
                "cluster_bonus": round(cluster_bonus, 3),
                "formulaic_bonus": round(formulaic_bonus, 3),
                "fatigue_penalty": round(-fatigue_penalty, 3),
            }
        })

    return scores


# ============================================================
# 11. VISUALIZATIONS
# ============================================================

def generate_visualizations(chapters, tfidf_matrix, valid_indices, labels,
                            cluster_info, cluster_label_names, originality_scores,
                            silhouette_scores_dict):
    """Generate all analysis visualizations."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- 1. PCA Scatter ---
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    pca = PCA(n_components=2, random_state=RANDOM_STATE)
    coords = pca.fit_transform(tfidf_matrix.toarray())

    colors = plt.cm.Set1(np.linspace(0, 1, len(set(labels))))
    for c in sorted(set(labels)):
        mask = (labels == c)
        name = cluster_label_names.get(c, f"Cluster {c}")
        axes[0].scatter(coords[mask, 0], coords[mask, 1], c=[colors[c]],
                        label=name, alpha=0.7, s=60, edgecolors='k', linewidth=0.5)
        for j in np.where(mask)[0]:
            ch_num = chapters[valid_indices[j]]["number"]
            axes[0].annotate(str(ch_num), (coords[j, 0], coords[j, 1]),
                             fontsize=6, ha='center', va='bottom')

    axes[0].set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]:.1%} var)")
    axes[0].set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]:.1%} var)")
    axes[0].set_title("PCA of Chapter TF-IDF (colored by cluster)")
    axes[0].legend(fontsize=8)

    # Silhouette score by k
    ks = sorted(silhouette_scores_dict.keys())
    axes[1].bar(ks, [silhouette_scores_dict[k] for k in ks], color='steelblue')
    axes[1].set_xlabel("Number of clusters (k)")
    axes[1].set_ylabel("Silhouette Score")
    axes[1].set_title("Optimal Cluster Count")
    axes[1].set_xticks(ks)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "v2_01_pca_clusters.png", dpi=150)
    plt.close()

    # --- 2. Dendrogram ---
    fig, ax = plt.subplots(figsize=(20, 8))
    ch_labels = [f"Ch.{chapters[valid_indices[i]]['number']}"
                 for i in range(len(valid_indices))]

    linked = linkage(tfidf_matrix.toarray(), method='ward')
    dendrogram(linked, ax=ax, labels=ch_labels, leaf_rotation=90,
               leaf_font_size=7, color_threshold=0.7 * max(linked[:, 2]))
    ax.set_title("Hierarchical Clustering of Kephalaia Chapters")
    ax.set_ylabel("Ward Distance")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "v2_02_dendrogram.png", dpi=150)
    plt.close()

    # --- 3. Vocabulary Category Heatmap ---
    fig, ax = plt.subplots(figsize=(18, max(8, len(chapters) * 0.12)))

    categories = list(VOCAB_CATEGORIES.keys())
    ch_nums = []
    data = []
    for ch in chapters:
        if ch["number"] == 0:
            continue
        ch_nums.append(ch["number"])
        densities, _ = compute_category_densities(ch["teaching_text"], ch["word_count"])
        data.append([densities.get(cat, 0) for cat in categories])

    data = np.array(data)
    if data.size > 0:
        im = ax.imshow(data, aspect='auto', cmap='YlOrRd', interpolation='nearest')
        ax.set_xticks(range(len(categories)))
        ax.set_xticklabels([c.replace("_", "\n") for c in categories], fontsize=9)
        ax.set_yticks(range(len(ch_nums)))
        ax.set_yticklabels([str(n) for n in ch_nums], fontsize=6)
        ax.set_ylabel("Chapter")
        ax.set_title("Vocabulary Category Density (per 100 words)")
        plt.colorbar(im, ax=ax, shrink=0.5)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "v2_03_category_heatmap.png", dpi=150)
    plt.close()

    # --- 4. Cluster Profile Comparison ---
    n_clusters = len(cluster_info)
    fig, ax = plt.subplots(figsize=(10, 6))

    x = np.arange(len(categories))
    width = 0.8 / n_clusters
    for c in sorted(cluster_info.keys()):
        info = cluster_info[c]
        vals = [info["avg_densities"].get(cat, 0) for cat in categories]
        name = cluster_label_names.get(c, f"Cluster {c}")
        offset = (c - n_clusters / 2 + 0.5) * width
        ax.bar(x + offset, vals, width, label=f"{name} (n={info['size']})")

    ax.set_xticks(x)
    ax.set_xticklabels([c.replace("_", "\n") for c in categories], fontsize=9)
    ax.set_ylabel("Avg Density per 100 words")
    ax.set_title("Cluster Vocabulary Profiles")
    ax.legend()
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "v2_04_cluster_profile.png", dpi=150)
    plt.close()

    # --- 5. Originality Score Ranking ---
    scored = [(ch["number"], originality_scores[i]["originality"])
              for i, ch in enumerate(chapters)
              if originality_scores[i]["originality"] > -900 and ch["number"] > 0]
    scored.sort(key=lambda x: x[1], reverse=True)

    if scored:
        fig, ax = plt.subplots(figsize=(16, max(8, len(scored) * 0.18)))
        nums = [str(s[0]) for s in scored]
        vals = [s[1] for s in scored]

        colors_bar = []
        for n, v in scored:
            if n in MANUAL_LAYER1:
                colors_bar.append('darkgreen')
            elif v > 2.0:
                colors_bar.append('forestgreen')
            elif v > 0.5:
                colors_bar.append('goldenrod')
            elif v > -1.0:
                colors_bar.append('orange')
            else:
                colors_bar.append('firebrick')

        ax.barh(range(len(scored)), vals, color=colors_bar, edgecolor='grey',
                linewidth=0.5)
        ax.set_yticks(range(len(scored)))
        ax.set_yticklabels(nums, fontsize=6)
        ax.set_xlabel("Originality Score")
        ax.set_title("Chapter Originality Ranking\n(dark green = in manual Layer 1 extract)")
        ax.axvline(x=0, color='black', linewidth=0.5)
        ax.invert_yaxis()
        plt.tight_layout()
        plt.savefig(OUTPUT_DIR / "v2_05_originality.png", dpi=150)
        plt.close()

    # --- 6. Editor Fatigue ---
    fatigue_data = []
    for ch in chapters:
        if ch["number"] == 0 or ch["word_count"] < 60:
            continue
        f = compute_editor_fatigue(ch["teaching_text"])
        fatigue_data.append((ch["number"], f["shift_score"]))

    fatigue_data.sort(key=lambda x: x[1], reverse=True)

    if fatigue_data:
        fig, ax = plt.subplots(figsize=(16, max(6, len(fatigue_data) * 0.15)))
        nums_f = [str(d[0]) for d in fatigue_data]
        shifts = [d[1] for d in fatigue_data]
        colors_f = ['firebrick' if s > 1.5 else 'goldenrod' if s > 0.5 else 'steelblue'
                    for s in shifts]

        ax.barh(range(len(fatigue_data)), shifts, color=colors_f)
        ax.set_yticks(range(len(fatigue_data)))
        ax.set_yticklabels(nums_f, fontsize=6)
        ax.set_xlabel("Vocabulary Shift Score (positive = cosmological front-loaded)")
        ax.set_title("Editor Fatigue Detection")
        ax.axvline(x=0, color='black', linewidth=0.5)
        ax.invert_yaxis()
        plt.tight_layout()
        plt.savefig(OUTPUT_DIR / "v2_06_editor_fatigue.png", dpi=150)
        plt.close()

    print(f"  6 visualizations saved to {OUTPUT_DIR}/v2_*.png")


# ============================================================
# 12. REPORT GENERATION
# ============================================================

def generate_report(chapters, valid_indices, labels, cluster_info,
                    cluster_label_names, originality_scores,
                    silhouette_scores_dict, optimal_k):
    """Generate comprehensive markdown analysis report."""
    lines = []
    lines.append("# Kephalaia Core Recovery Analysis")
    lines.append("")
    lines.append("**Method**: Data-driven layer detection using TF-IDF clustering,")
    lines.append("vocabulary profiling, structural analysis, and editor fatigue detection.")
    lines.append("")
    lines.append(f"**Date**: 2026-02-16")
    lines.append(f"**Chapters parsed**: {len(chapters)} "
                 f"(range {min(ch['number'] for ch in chapters)}"
                 f"-{max(ch['number'] for ch in chapters)})")
    lines.append(f"**Chapters with sufficient text for clustering**: {len(valid_indices)}")
    lines.append(f"**Min words threshold**: {MIN_WORDS_FOR_CLUSTERING}")
    lines.append("")

    # ----- Section 1: Cluster Discovery -----
    lines.append("---")
    lines.append("")
    lines.append("## 1. Cluster Discovery (Unsupervised)")
    lines.append("")
    lines.append("### Silhouette Analysis")
    lines.append("")
    lines.append("| k | Silhouette Score |")
    lines.append("|---|-----------------|")
    for k in sorted(silhouette_scores_dict.keys()):
        marker = " **← optimal**" if k == optimal_k else ""
        lines.append(f"| {k} | {silhouette_scores_dict[k]:.4f}{marker} |")
    lines.append("")
    lines.append(f"**Optimal k = {optimal_k}** (highest average silhouette coefficient)")
    lines.append("")

    # ----- Section 2: Cluster Characterization -----
    lines.append("### Cluster Profiles")
    lines.append("")

    for c in sorted(cluster_info.keys()):
        info = cluster_info[c]
        name = cluster_label_names.get(c, f"Cluster {c}")
        lines.append(f"#### Cluster {c}: {name} ({info['size']} chapters)")
        lines.append("")
        lines.append(f"**Avg word count**: {info['avg_word_count']:.0f}")
        lines.append("")

        lines.append("**Vocabulary category densities** (per 100 words):")
        lines.append("")
        for cat in VOCAB_CATEGORIES:
            val = info["avg_densities"].get(cat, 0)
            bar = "█" * int(val * 10)
            lines.append(f"- {cat}: {val:.3f} {bar}")
        lines.append("")

        lines.append("**Most distinctive terms**:")
        lines.append("")
        for term, score in info["distinctive_terms"][:15]:
            lines.append(f"- `{term}` ({score:.4f})")
        lines.append("")

        lines.append("**Chapters**: " +
                     ", ".join(str(n) for n in info["chapter_numbers"]))
        lines.append("")

    # ----- Section 3: Originality Ranking -----
    lines.append("---")
    lines.append("")
    lines.append("## 2. Originality Ranking")
    lines.append("")
    lines.append("Chapters ranked by composite originality score. "
                 "Higher = more likely part of the original cosmological core.")
    lines.append("")
    lines.append("| Rank | Ch. | Title | Score | Cosmo | NT | Cluster | Manual L1 |")
    lines.append("|------|-----|-------|-------|-------|----|---------|:---------:|")

    scored = [(i, ch["number"], ch["title"],
               originality_scores[i]["originality"],
               originality_scores[i]["components"])
              for i, ch in enumerate(chapters)
              if originality_scores[i]["originality"] > -900 and ch["number"] > 0]
    scored.sort(key=lambda x: x[3], reverse=True)

    for rank, (idx, num, title, score, comp) in enumerate(scored, 1):
        # Find cluster assignment
        cluster_str = ""
        if idx in valid_indices:
            vi_pos = valid_indices.index(idx)
            if vi_pos < len(labels):
                c = labels[vi_pos]
                cluster_str = cluster_label_names.get(c, f"C{c}")

        manual = "✅" if num in MANUAL_LAYER1 else ""
        lines.append(f"| {rank} | {num} | {title[:50]} | "
                     f"{score:.2f} | {comp.get('cosmological', 0):.2f} | "
                     f"{comp.get('nt_penalty', 0):.2f} | {cluster_str} | {manual} |")

    lines.append("")

    # ----- Section 4: Proposed Core -----
    lines.append("---")
    lines.append("")
    lines.append("## 3. Proposed Original Core")
    lines.append("")
    lines.append("Chapters with originality score > 1.0 and assigned to the "
                 "Core Cosmological cluster:")
    lines.append("")

    core_candidates = [(num, score) for idx, num, title, score, comp in scored
                       if score > 1.0]
    core_in_manual = [n for n, s in core_candidates if n in MANUAL_LAYER1]
    core_not_in_manual = [n for n, s in core_candidates if n not in MANUAL_LAYER1]

    lines.append(f"**Total core candidates**: {len(core_candidates)}")
    lines.append(f"**Also in manual Layer 1**: {len(core_in_manual)} — "
                 + ", ".join(str(n) for n in sorted(core_in_manual)))
    lines.append(f"**NEW (not in manual Layer 1)**: {len(core_not_in_manual)} — "
                 + ", ".join(str(n) for n in sorted(core_not_in_manual)))
    lines.append("")

    manual_not_in_core = [n for n in sorted(MANUAL_LAYER1)
                          if n not in [x[0] for x in core_candidates]]
    lines.append(f"**In manual Layer 1 but NOT in computed core**: "
                 f"{len(manual_not_in_core)} — "
                 + ", ".join(str(n) for n in manual_not_in_core))
    lines.append("")

    # ----- Section 5: Editor Fatigue -----
    lines.append("---")
    lines.append("")
    lines.append("## 4. Editor Fatigue Detection")
    lines.append("")
    lines.append("Chapters where cosmological vocabulary is concentrated in the "
                 "first half, suggesting an original core was diluted by later additions:")
    lines.append("")
    lines.append("| Ch. | Title | Shift | 1st Cosmo | 2nd Cosmo | 1st NT | 2nd NT |")
    lines.append("|-----|-------|-------|-----------|-----------|--------|--------|")

    fatigue_data = []
    for ch in chapters:
        if ch["number"] == 0 or ch["word_count"] < 60:
            continue
        f = compute_editor_fatigue(ch["teaching_text"])
        fatigue_data.append((ch["number"], ch["title"], f))
    fatigue_data.sort(key=lambda x: x[2]["shift_score"], reverse=True)

    for num, title, f in fatigue_data[:25]:
        lines.append(f"| {num} | {title[:45]} | {f['shift_score']:.2f} | "
                     f"{f['first_half_cosmological']:.2f} | "
                     f"{f['second_half_cosmological']:.2f} | "
                     f"{f['first_half_nt']:.2f} | {f['second_half_nt']:.2f} |")
    lines.append("")

    # ----- Section 6: Gardner Flags -----
    lines.append("---")
    lines.append("")
    lines.append("## 5. Gardner Editorial Flags")
    lines.append("")
    lines.append("| Ch. | Title | Flags |")
    lines.append("|-----|-------|-------|")

    for ch in chapters:
        if ch["number"] == 0:
            continue
        flags = detect_gardner_flags(ch["gardner_text"])
        if flags:
            lines.append(f"| {ch['number']} | {ch['title'][:50]} | "
                         f"{', '.join(flags)} |")
    lines.append("")

    # ----- Section 7: NT Citations -----
    lines.append("---")
    lines.append("")
    lines.append("## 6. NT Citation Distribution")
    lines.append("")
    lines.append("| Ch. | Title | Citations | Count |")
    lines.append("|-----|-------|-----------|-------|")

    for ch in chapters:
        if ch["number"] == 0:
            continue
        cites = detect_nt_citations(ch["full_text"])
        if cites:
            lines.append(f"| {ch['number']} | {ch['title'][:50]} | "
                         f"{', '.join(cites)} | {len(cites)} |")
    lines.append("")

    # ----- Section 8: Fragmentary Chapters -----
    lines.append("---")
    lines.append("")
    lines.append("## 7. Fragmentary Chapters (excluded from clustering)")
    lines.append("")
    lines.append(f"Chapters with fewer than {MIN_WORDS_FOR_CLUSTERING} words:")
    lines.append("")

    for i, ch in enumerate(chapters):
        if ch["number"] == 0:
            continue
        if ch["word_count"] < MIN_WORDS_FOR_CLUSTERING:
            lines.append(f"- **Ch. {ch['number']}** ({ch['word_count']} words): {ch['title']}")
    lines.append("")

    # ----- Appendix: Full Table -----
    lines.append("---")
    lines.append("")
    lines.append("## Appendix: Full Chapter Data")
    lines.append("")
    lines.append("| Ch. | Words | Originality | Cosmo | NT | Hagio | Pastoral | "
                 "Persian | Cluster | Fatigue | L1? |")
    lines.append("|-----|------:|------------:|------:|---:|------:|---------:|"
                 "--------:|---------|--------:|:---:|")

    for i, ch in enumerate(chapters):
        if ch["number"] == 0:
            continue
        o = originality_scores[i]
        if o["originality"] <= -900:
            continue

        densities, _ = compute_category_densities(ch["teaching_text"], ch["word_count"])
        fatigue = compute_editor_fatigue(ch["teaching_text"])

        cluster_str = ""
        if i in valid_indices:
            vi_pos = valid_indices.index(i)
            if vi_pos < len(labels):
                c = labels[vi_pos]
                cluster_str = cluster_label_names.get(c, f"C{c}")[:12]

        l1 = "✅" if ch["number"] in MANUAL_LAYER1 else ""

        lines.append(
            f"| {ch['number']} | {ch['word_count']} | "
            f"{o['originality']:.2f} | "
            f"{densities.get('cosmological', 0):.2f} | "
            f"{densities.get('nt_christian', 0):.2f} | "
            f"{densities.get('hagiographic', 0):.2f} | "
            f"{densities.get('pastoral', 0):.2f} | "
            f"{densities.get('persian_substrate', 0):.2f} | "
            f"{cluster_str} | "
            f"{fatigue['shift_score']:.2f} | {l1} |"
        )

    lines.append("")
    return "\n".join(lines)


# ============================================================
# 13. MAIN
# ============================================================

def main():
    print("=" * 60)
    print("KEPHALAIA CORE RECOVERY ANALYSIS v2")
    print("=" * 60)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load and parse
    print("\n1. Loading and parsing chapters...")
    text = KEPHALAIA_PATH.read_text(encoding="utf-8")
    chapters = parse_chapters(text)
    print(f"  {len(chapters)} chapters parsed")

    # Count teaching-text words
    total_words = sum(ch["word_count"] for ch in chapters)
    print(f"  Total teaching text words: {total_words:,}")
    viable = sum(1 for ch in chapters if ch["word_count"] >= MIN_WORDS_FOR_CLUSTERING)
    print(f"  Chapters with >= {MIN_WORDS_FOR_CLUSTERING} words: {viable}")

    # 2. Build TF-IDF matrix
    print("\n2. Building TF-IDF matrix (unigrams + bigrams)...")
    tfidf_matrix, feature_names, vectorizer, valid_indices = build_tfidf_matrix(chapters)
    print(f"  Matrix shape: {tfidf_matrix.shape} "
          f"({tfidf_matrix.shape[0]} chapters × {tfidf_matrix.shape[1]} features)")

    # 3. Find optimal clusters
    print("\n3. Finding optimal cluster count...")
    optimal_k, silhouette_scores_dict = find_optimal_clusters(tfidf_matrix)
    print(f"  Silhouette scores: {silhouette_scores_dict}")
    print(f"  Optimal k = {optimal_k}")

    # 4. Run clustering
    print(f"\n4. Clustering with k={optimal_k}...")
    labels, km = cluster_chapters(tfidf_matrix, optimal_k)
    cluster_info = characterize_clusters(tfidf_matrix, feature_names, labels,
                                         chapters, valid_indices)
    cluster_label_names = label_clusters(cluster_info)
    for c, name in cluster_label_names.items():
        print(f"  Cluster {c}: {name} ({cluster_info[c]['size']} chapters)")

    # 5. Compute originality scores
    print("\n5. Computing originality scores...")
    originality_scores = compute_originality_scores(
        chapters, labels, cluster_label_names, valid_indices
    )

    scored = [(ch["number"], originality_scores[i]["originality"])
              for i, ch in enumerate(chapters)
              if originality_scores[i]["originality"] > -900 and ch["number"] > 0]
    scored.sort(key=lambda x: x[1], reverse=True)
    print(f"  Top 10 by originality:")
    for num, score in scored[:10]:
        l1 = " [L1]" if num in MANUAL_LAYER1 else ""
        print(f"    Ch. {num}: {score:.2f}{l1}")

    # 6. Generate visualizations
    print("\n6. Generating visualizations...")
    generate_visualizations(chapters, tfidf_matrix, valid_indices, labels,
                            cluster_info, cluster_label_names, originality_scores,
                            silhouette_scores_dict)

    # 7. Generate report
    print("\n7. Generating report...")
    report = generate_report(chapters, valid_indices, labels, cluster_info,
                             cluster_label_names, originality_scores,
                             silhouette_scores_dict, optimal_k)
    report_path = OUTPUT_DIR / "v2_report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"  Report saved to {report_path}")

    # 8. Save raw data
    print("\n8. Saving raw data...")
    data_out = []
    for i, ch in enumerate(chapters):
        if ch["number"] == 0:
            continue
        o = originality_scores[i]
        densities, details = compute_category_densities(
            ch["teaching_text"], ch["word_count"])
        structural = compute_structural_features(ch["teaching_text"])
        fatigue = compute_editor_fatigue(ch["teaching_text"])
        formulaic = detect_formulaic_patterns(ch["teaching_text"])
        nt_cites = detect_nt_citations(ch["full_text"])
        g_flags = detect_gardner_flags(ch["gardner_text"])

        cluster_str = ""
        if i in valid_indices:
            vi_pos = valid_indices.index(i)
            if vi_pos < len(labels):
                cluster_str = cluster_label_names.get(labels[vi_pos], "")

        data_out.append({
            "chapter": ch["number"],
            "title": ch["title"],
            "word_count": ch["word_count"],
            "originality_score": o["originality"],
            "originality_components": o.get("components", {}),
            "cluster": cluster_str,
            "category_densities": {k: round(v, 4) for k, v in densities.items()},
            "category_details": {k: v for k, v in details.items() if v},
            "structural": structural,
            "fatigue": fatigue,
            "formulaic": formulaic,
            "nt_citations": nt_cites,
            "gardner_flags": g_flags,
            "in_manual_layer1": ch["number"] in MANUAL_LAYER1,
        })

    data_path = OUTPUT_DIR / "v2_data.json"
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(data_out, f, indent=2, ensure_ascii=False)
    print(f"  Data saved to {data_path}")

    # Summary
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)
    core = [d for d in data_out if d["originality_score"] > 1.0]
    print(f"Proposed core chapters (score > 1.0): {len(core)}")
    print(f"Chapters: {', '.join(str(d['chapter']) for d in sorted(core, key=lambda x: x['chapter']))}")
    manual_match = sum(1 for d in core if d["in_manual_layer1"])
    print(f"Overlap with manual Layer 1: {manual_match}/{len(MANUAL_LAYER1)}")


if __name__ == "__main__":
    main()
