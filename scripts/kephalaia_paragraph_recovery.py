#!/usr/bin/env python3
"""
Kephalaia Paragraph-Level Core Recovery (v3)
=============================================
Treats chapter boundaries as editorial artifacts.
Works at passage level to recover original teaching.

Stage 1: Line Classification
Stage 2: Teaching Text Extraction & Paragraph Segmentation
Stage 3: Vocabulary Scoring (per paragraph)
Stage 4: TF-IDF Sub-Clustering
Stage 5: Tier Classification
Stage 6: Core Reconstruction
Stage 7: Reporting & Visualization
"""

import re
import json
import sys
import numpy as np
from pathlib import Path
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Tuple, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.colors import LinearSegmentedColormap

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, silhouette_samples
from sklearn.decomposition import PCA
from scipy.cluster.hierarchy import linkage, dendrogram, fcluster

# ─── PATHS ──────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
SOURCE_PATH = PROJECT_ROOT / "output" / "texts" / "Kephalaia_of_the_Teacher.md"
OUTPUT_DIR = PROJECT_ROOT / "output" / "analysis" / "v3"

# ─── VOCABULARY CATEGORIES ──────────────────────────────────────────────
# Phrases searched first (multi-word); words searched second (single-word)

VOCAB = {
    "cosmological": {
        "phrases": [
            "first man", "living spirit", "mother of life", "father of greatness",
            "third ambassador", "jesus splendour", "jesus the splendour",
            "light mind", "maiden of light", "great builder",
            "beloved of the lights", "king of honour", "adamas of light",
            "king of the gardens", "keeper of splendour",
            "five shekhinas", "five sons", "twelve maidens",
            "living soul", "cross of light", "living fire",
            "ships of light", "land of darkness", "realm of light",
            "land of light", "land of rest", "land of the living",
            "garment of light", "garment of fire", "garment of wind",
            "garment of water", "living water", "living ones",
            "new earth", "great fire", "final lump",
            "new man", "old man", "light form",
            "column of glory", "perfect man",
            "five elements", "five garments", "five worlds",
            "two principles", "three wheels", "three vessels",
            "wheel of the stars", "ten firmaments",
        ],
        "words": [
            "storehouses", "firmaments", "aeons", "emanation", "emanations",
            "rulers", "archons", "elements", "mixture", "vessels",
            "principalities", "zodiac",
            "fashioned", "constructed", "discharged", "crucified",
            "snared", "hunted", "mingled", "entangled",
        ],
    },
    "persian_substrate": {
        "phrases": [
            "realm of darkness", "father of greatness",
            "two principles", "five elements",
            "call and response",
        ],
        "words": [
            "ohrmizd", "ahriman",
        ],
    },
    "pastoral": {
        "phrases": [
            "holy church", "alms-giving", "alms-offering",
            "place of rest", "land of light",
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
        "phrases": [],
        "words": [
            "christ", "gospel", "paraclete",
        ],
    },
    "hagiographic": {
        "phrases": [
            "apostle of light", "lord manichaios",
            "apostle of greatness",
        ],
        "words": [
            "manichaios",
        ],
    },
}

# Composite score weights
WEIGHTS = {
    "cosmological": 2.0,
    "persian_substrate": 3.0,
    "pastoral": -2.0,
    "nt_christian": -1.5,
    "hagiographic": -1.0,
}

# ─── LINE CLASSIFICATION ───────────────────────────────────────────────

# Patterns for chapter markers (two OCR formats)
RE_CHAPTER_MIDDOT = re.compile(r"^[·]{2,}\s*(?:\(?\w+\)?\s*)?[·]*", re.UNICODE)
RE_CHAPTER_DOTS = re.compile(r"^\.{2,}\s*\d+\s*\.+", re.UNICODE)
RE_CHAPTER_NUM = re.compile(r"(\d+)")

# Page reference: (208,11 - 213,20)
RE_PAGE_REF = re.compile(r"^\(\d+[,.:]\s*\d+\s*[-–]\s*\d+[,.:]\s*\d+")

# Page header: CHAPTER EIGHTY-FOUR or THE KEPHALAIA OF THE TEACHER
RE_PAGE_HEADER = re.compile(
    r"^(?:CHAPTER\s|THE KEPHALAIA|THE EDITED COPTIC|INTRODUCTION$|"
    r"NAG HAMMADI|PREFACE|CONTENTS)",
    re.IGNORECASE,
)

# Standalone page number
RE_PAGE_NUMBER = re.compile(r"^\d{1,3}$")

# Footnote: *120 or *66
RE_FOOTNOTE = re.compile(r"^\*\d+")

# Divider
RE_DIVIDER = re.compile(r"^-{3,}$")

# Title line: starts and/or ends with /
RE_TITLE = re.compile(r"^/\s*\w")

# Gardner section reference: 270.31 - 271.12
RE_GARDNER_SECTION = re.compile(r"^\d{1,3}\.\d+\s*[-–]\s*\d{1,3}\.\d+")

# Gardner commentary signals (patterns that appear in scholarly commentary)
GARDNER_SIGNALS = [
    r"(?i)\bthis (?:chapter|kephalaion|section)\b",
    r"(?i)\bmani (?:compares|develops|explains|remarks|uses|begins|asserts|acknowledges|is|was|then|here)\b",
    r"(?i)\bsee (?:further|also)\b",
    r"(?i)\bthe (?:ed\.|editio|ed\.?\s*pr)\b",
    r"(?i)\b(?:albeit|whilst|implicit|evidencing|problematic|redaction)\b",
    r"(?i)\b(?:universalisation|christological|soteriological|eschatological)\b",
    r"(?i)\bin (?:this|the) (?:preceding|following|readable)\b",
    r"(?i)\bthe (?:question|doctrine|chapter|text) (?:concerns|discusses|is|provides|begins)\b",
    r"(?i)\bmanichaean (?:practices|doctrine|ethics|teaching|church)\b",
    r"(?i)\b(?:cf\.|restoring|reading)\s",
    r"(?i)\bkarmic\b",
    r"(?i)\ba good example of\b",
]
GARDNER_SIGNAL_RES = [re.compile(p) for p in GARDNER_SIGNALS]

# Teaching start formulas (transition from Gardner to teaching text)
TEACHING_START_PATTERNS = [
    re.compile(r"(?i)onc\w*\s+again"),
    re.compile(r"(?i)then\s+(?:the\s+)?(?:apostle|enlightener)\s+speak"),
    re.compile(r"(?i)(?:a|one|another|that)\s+(?:disciple|catechumen|nazorean)"),
    re.compile(r"(?i)again,?\s+it\s+happened"),
    re.compile(r"(?i)speaks?\s+(?:the\s+)?(?:apostle|enlightener|our)"),
    re.compile(r"(?i)^(?:the|this)\s+(?:first|second|third)\s+(?:parable|thing|blow)"),
    re.compile(r"(?i)at\s+the\s+time\s+when\s+the"),
    re.compile(r"(?i)understand\s+this"),
    re.compile(r"(?i)happen\s+you\s+know"),
    re.compile(r"(?i)^\d+\s+the\s+first\s+(?:parable|chapt)"),
    re.compile(r"(?i)the\s+(?:apostle|enlightener)\s+(?:says?|speaks?)"),
    re.compile(r"(?i)^he\s+says?\s+to\s+(?:his|the|them)"),
    re.compile(r"(?i)^\d+\s+(?:the\s+)?(?:apostle|enlightener)\s+(?:says?|speaks?)"),
    re.compile(r"(?i)his\s+disciples\s+(?:question|ask)"),
    re.compile(r"(?i)^\d+\s+his\s+disciples"),
    re.compile(r"(?i)^\d+\s+once\s+again"),
    re.compile(r"(?i)i\s+will\s+(?:teach|reveal|tell|recount)\s+"),
    re.compile(r"(?i)^the\s+first\s+chapt"),  # "The first chapt[e]r..."
]

# Paragraph split markers within teaching text
PARA_SPLIT_PATTERNS = [
    re.compile(r"(?i)^\s*(?:\[\s*\w\s*\])?\s*onc\w*\s+again"),
    re.compile(r"(?i)^\s*(?:\[\s*\w\s*\])?\s*then\s+(?:the\s+)?(?:apostle|enlightener)\s+speak"),
    re.compile(r"(?i)^\s*(?:\[\s*\w\s*\])?\s*(?:a|one|another|that)\s+(?:disciple|catechumen|nazorean)"),
    re.compile(r"(?i)^\s*(?:\[\s*\w\s*\])?\s*when\s+(?:that|this)\s+(?:disciple|catechumen).*heard"),
    re.compile(r"(?i)^\s*(?:\[\s*\w\s*\])?\s*behold,?\s+(?:i|you)\s+have"),
    re.compile(r"(?i)^\s*(?:\[\s*\w\s*\])?\s*again,?\s+it\s+happened"),
    re.compile(r"(?i)^\s*(?:\[\s*\w\s*\])?\s*(?:also|again),?\s+this\s+(?:too\s+)?is\s+(?:the\s+)?(?:case|what)"),
]


def is_chapter_marker(line: str) -> Optional[int]:
    """Check if line is a chapter marker. Returns chapter number or None."""
    s = line.strip()
    if not s:
        return None

    # Unified detection: line starts with 2+ dots/middots of any kind
    # Dots can be · (U+00B7 middot) or . (period)
    if not re.match(r"^[·.]{2,}", s, re.UNICODE):
        return None

    # Reject if it looks like real text (has many words after the dots+number)
    # Real chapter markers are short; OCR text with "..." at start is longer
    words_after = re.sub(r"^[·.\s\d()]+", "", s).split()
    if len(words_after) > 6:
        return None

    # Special case: ··· (Introduction) ···
    if "introduction" in s.lower():
        return 0

    # Special case: ··· . ··· (chapter 1 — uses dot instead of number)
    if re.match(r"^[·]+\s*\.\s*[·]+$", s, re.UNICODE):
        return 1

    # Extract chapter number
    m = RE_CHAPTER_NUM.search(s)
    if m:
        return int(m.group(1))

    return None


def has_gardner_signal(line: str) -> bool:
    """Check if line contains Gardner commentary signals."""
    for pat in GARDNER_SIGNAL_RES:
        if pat.search(line):
            return True
    return False


def _strip_ocr_brackets(text: str) -> str:
    """Remove OCR bracket restorations for pattern matching."""
    return re.sub(r"\[([^\]]*)\]", r"\1", text)


def is_teaching_start(line: str) -> bool:
    """Check if line matches a teaching text opening formula."""
    # Strip OCR brackets before matching
    s = _strip_ocr_brackets(line.strip())
    for pat in TEACHING_START_PATTERNS:
        if pat.search(s):
            return True
    return False


def classify_lines(text: str) -> List[Dict]:
    """Classify every line of the source text."""
    lines = text.split("\n")
    classified = []

    # State machine
    state = "FRONT_MATTER"  # FRONT_MATTER -> HEADER -> GARDNER -> TEACHING
    current_chapter = -1
    gardner_line_count = 0
    header_line_count = 0  # Lines since entering HEADER state
    seen_title = False  # Whether we've seen a TITLE in current HEADER

    for i, raw_line in enumerate(lines):
        line = raw_line.rstrip()
        stripped = line.strip()
        line_num = i + 1  # 1-based

        entry = {
            "line_num": line_num,
            "text": line,
            "type": None,
            "chapter": current_chapter,
        }

        # --- Always-match patterns ---
        if not stripped:
            entry["type"] = "BLANK"
        elif RE_DIVIDER.match(stripped):
            entry["type"] = "DIVIDER"
        elif RE_FOOTNOTE.match(stripped):
            entry["type"] = "FOOTNOTE"
        elif RE_PAGE_HEADER.match(stripped):
            entry["type"] = "PAGE_HEADER"
        elif RE_PAGE_NUMBER.match(stripped) and len(stripped) <= 3:
            entry["type"] = "PAGE_NUMBER"

        # --- Chapter marker detection ---
        if entry["type"] is None:
            ch_num = is_chapter_marker(stripped)
            if ch_num is not None:
                entry["type"] = "CHAPTER_MARKER"
                current_chapter = ch_num
                entry["chapter"] = current_chapter
                state = "HEADER"
                gardner_line_count = 0
                header_line_count = 0
                seen_title = False
            else:
                # Front matter before first chapter
                if state == "FRONT_MATTER":
                    if entry["type"] is None:
                        entry["type"] = "FRONT_MATTER"
                elif state == "HEADER":
                    header_line_count += 1
                    if entry["type"] is None:
                        if RE_PAGE_REF.match(stripped):
                            entry["type"] = "PAGE_REF"
                        elif RE_TITLE.match(stripped) or (
                            stripped.startswith("/") and len(stripped) > 2
                        ):
                            entry["type"] = "TITLE"
                            seen_title = True
                        elif RE_GARDNER_SECTION.match(stripped):
                            entry["type"] = "GARDNER"
                            gardner_line_count += 1
                        elif is_teaching_start(stripped):
                            entry["type"] = "TEACHING"
                            state = "TEACHING"
                        elif has_gardner_signal(stripped):
                            entry["type"] = "GARDNER"
                            gardner_line_count += 1
                        else:
                            # Fallback: after seeing title, if we've been in HEADER
                            # too long without finding a teaching formula, check if
                            # this looks more like teaching than Gardner
                            if seen_title and header_line_count > 8 and len(stripped) > 20:
                                # Likely teaching text that lacks a formal opening
                                entry["type"] = "TEACHING"
                                state = "TEACHING"
                            elif len(stripped) > 20 and not stripped[0].isdigit():
                                entry["type"] = "GARDNER"
                                gardner_line_count += 1
                            elif gardner_line_count > 0 and len(stripped) > 10:
                                entry["type"] = "GARDNER"
                                gardner_line_count += 1
                            else:
                                entry["type"] = "TITLE"
                elif state == "TEACHING":
                    if entry["type"] is None:
                        entry["type"] = "TEACHING"

        # Default: if still None, use state
        if entry["type"] is None:
            if state == "TEACHING":
                entry["type"] = "TEACHING"
            elif state in ("HEADER",):
                entry["type"] = "GARDNER"
            else:
                entry["type"] = "FRONT_MATTER"

        entry["chapter"] = current_chapter
        classified.append(entry)

    return classified


# ─── PARAGRAPH EXTRACTION ──────────────────────────────────────────────

def clean_for_scoring(text: str) -> str:
    """Clean text for vocabulary scoring."""
    # Remove OCR bracket restorations but keep content
    text = re.sub(r"\[([^\]]*)\]", r"\1", text)
    # Remove footnote markers
    text = re.sub(r"\*\d+", "", text)
    # Remove page line numbers embedded in text (e.g., " 15 " between words)
    text = re.sub(r"\s+\d{1,2}\s+", " ", text)
    # Remove curly braces
    text = re.sub(r"[{}]", "", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def extract_paragraphs(classified_lines: List[Dict]) -> List[Dict]:
    """Extract teaching paragraphs from classified lines."""
    # Group lines by editorial chapter
    chapters = defaultdict(list)
    for entry in classified_lines:
        if entry["chapter"] >= 0:
            chapters[entry["chapter"]].append(entry)

    paragraphs = []
    para_id = 0

    for ch_num in sorted(chapters.keys()):
        ch_lines = chapters[ch_num]

        # Collect teaching lines with their positions
        teaching_runs = []  # list of lists of consecutive teaching lines
        current_run = []
        gap_types = []  # non-teaching types between runs

        for entry in ch_lines:
            if entry["type"] == "TEACHING":
                if gap_types and current_run:
                    # Check if gap is just page transitions
                    real_gap = any(
                        t not in ("BLANK", "DIVIDER", "PAGE_HEADER", "PAGE_NUMBER", "FOOTNOTE")
                        for t in gap_types
                    )
                    if real_gap:
                        teaching_runs.append(current_run)
                        current_run = []
                gap_types = []
                current_run.append(entry)
            elif entry["type"] not in ("BLANK", "DIVIDER", "PAGE_HEADER", "PAGE_NUMBER", "FOOTNOTE"):
                if entry["type"] != "TEACHING":
                    gap_types.append(entry["type"])
            else:
                gap_types.append(entry["type"])

        if current_run:
            teaching_runs.append(current_run)

        # Each teaching_run is a block of consecutive teaching lines
        # (page transitions already joined). Now split into paragraphs.
        for run in teaching_runs:
            # Join lines into flowing text, then split at paragraph markers
            sub_paras = _split_run_into_paragraphs(run)
            for sp in sub_paras:
                if not sp:
                    continue
                raw_text = "\n".join(e["text"] for e in sp)
                joined = " ".join(e["text"].strip() for e in sp if e["text"].strip())
                cleaned = clean_for_scoring(joined)
                word_count = len(cleaned.split())

                if word_count < 5:
                    continue  # skip tiny fragments

                para_id += 1
                paragraphs.append({
                    "id": f"P{para_id:04d}",
                    "editorial_chapter": ch_num,
                    "start_line": sp[0]["line_num"],
                    "end_line": sp[-1]["line_num"],
                    "word_count": word_count,
                    "text": cleaned,
                    "raw_text": raw_text,
                    "joined_text": joined,
                })

    # Post-process: merge very short paragraphs with next
    paragraphs = _merge_short_paragraphs(paragraphs, min_words=20)
    # Re-number
    for i, p in enumerate(paragraphs):
        p["id"] = f"P{i+1:04d}"

    return paragraphs


def _split_run_into_paragraphs(run: List[Dict]) -> List[List[Dict]]:
    """Split a teaching run into paragraphs at semantic boundaries."""
    if not run:
        return []

    paragraphs = []
    current = []

    for entry in run:
        stripped = entry["text"].strip()
        # Check if this line starts a new paragraph
        if current and _is_para_boundary(stripped):
            paragraphs.append(current)
            current = []
        current.append(entry)

    if current:
        paragraphs.append(current)

    # Split any very long paragraphs (>350 words)
    result = []
    for para in paragraphs:
        joined = " ".join(e["text"].strip() for e in para)
        wc = len(joined.split())
        if wc > 350:
            split = _force_split_long(para)
            result.extend(split)
        else:
            result.append(para)

    return result


def _is_para_boundary(line: str) -> bool:
    """Check if a line marks the start of a new semantic paragraph."""
    for pat in PARA_SPLIT_PATTERNS:
        if pat.search(line):
            return True
    return False


def _force_split_long(para: List[Dict], target: int = 200) -> List[List[Dict]]:
    """Force split a very long paragraph near the target word count."""
    result = []
    current = []
    wc = 0
    for entry in para:
        words_in_line = len(entry["text"].split())
        if wc >= target and current:
            # Try to split at a sentence boundary
            result.append(current)
            current = []
            wc = 0
        current.append(entry)
        wc += words_in_line
    if current:
        result.append(current)
    return result


def _merge_short_paragraphs(paragraphs: List[Dict], min_words: int = 20) -> List[Dict]:
    """Merge paragraphs shorter than min_words with the next paragraph."""
    if not paragraphs:
        return paragraphs

    merged = []
    i = 0
    while i < len(paragraphs):
        p = paragraphs[i]
        # If short and not the last paragraph, merge with next
        if p["word_count"] < min_words and i + 1 < len(paragraphs):
            nxt = paragraphs[i + 1]
            # Only merge if same chapter
            if p["editorial_chapter"] == nxt["editorial_chapter"]:
                combined = {
                    "id": p["id"],
                    "editorial_chapter": p["editorial_chapter"],
                    "start_line": p["start_line"],
                    "end_line": nxt["end_line"],
                    "word_count": p["word_count"] + nxt["word_count"],
                    "text": p["text"] + " " + nxt["text"],
                    "raw_text": p["raw_text"] + "\n" + nxt["raw_text"],
                    "joined_text": p["joined_text"] + " " + nxt["joined_text"],
                }
                paragraphs[i + 1] = combined
                i += 1
                continue
        merged.append(p)
        i += 1

    return merged


# ─── VOCABULARY SCORING ────────────────────────────────────────────────

def score_vocabulary(text: str, word_count: int) -> Tuple[Dict, Dict]:
    """Score a text against all vocabulary categories.

    Returns:
        densities: {category: occurrences_per_100_words}
        terms: {category: [terms_found_with_counts]}
    """
    densities = {}
    terms = {}

    for cat, vocab in VOCAB.items():
        count = 0
        found = []

        # Count phrase matches
        for phrase in vocab.get("phrases", []):
            n = text.lower().count(phrase)
            if n > 0:
                count += n
                found.append(f"{phrase} x{n}")

        # Count single word matches
        words = text.lower().split()
        word_freq = Counter(words)
        for word in vocab.get("words", []):
            n = word_freq.get(word, 0)
            if n > 0:
                count += n
                found.append(f"{word} x{n}")

        density = (count / word_count * 100) if word_count > 0 else 0
        densities[cat] = round(density, 3)
        terms[cat] = found

    return densities, terms


def compute_composite(densities: Dict) -> float:
    """Compute composite originality score from vocabulary densities."""
    score = 0.0
    for cat, weight in WEIGHTS.items():
        score += densities.get(cat, 0) * weight
    return round(score, 3)


# ─── NT CITATION DETECTION ────────────────────────────────────────────

RE_NT_CITATION = re.compile(
    r"(?:Mt\.|Mk\.|Lk\.|Jn\.?|Cor\.|Phil\.|Col\.|Thess\.|Tim\.|Heb\.|"
    r"Rev\.|Rom\.|Gal\.|Eph\.|Pet\.|Jas\.|Acts)\s*\d",
    re.IGNORECASE,
)


def detect_nt_citations(raw_text: str) -> List[str]:
    """Detect New Testament citations in raw text (usually from footnotes nearby)."""
    return RE_NT_CITATION.findall(raw_text)


# ─── STRUCTURAL FEATURES ──────────────────────────────────────────────

OPENING_FORMULAS = [
    re.compile(r"(?i)onc\w*\s+again"),
    re.compile(r"(?i)again,?\s+it\s+happened"),
    re.compile(r"(?i)then\s+(?:the\s+)?(?:apostle|enlightener)\s+speak"),
]

CLOSING_FORMULAS = [
    re.compile(r"(?i)when\s+(?:that|this)\s+(?:disciple|catechumen)\s+heard"),
    re.compile(r"(?i)he\s+(?:was\s+)?persuaded"),
    re.compile(r"(?i)(?:he|she)\s+(?:rejoiced|glorified|made\s+obeisance)"),
    re.compile(r"(?i)i\s+(?:give\s+)?thanks?\s+to\s+you\s+my\s+mas"),
]

SPEAKER_PATTERNS = {
    "apostle": re.compile(r"(?i)(?:apostle|enlightener|master)\s+speak|(?:apostle|enlightener)\s+says?"),
    "disciple": re.compile(r"(?i)(?:disciple|catechumen|nazorean)\s+(?:speak|says?|stood|came|question)"),
}


def detect_structural(text: str) -> Dict:
    """Detect structural features of a paragraph."""
    is_opening = any(p.search(text) for p in OPENING_FORMULAS)
    is_closing = any(p.search(text) for p in CLOSING_FORMULAS)
    speaker = None
    for spk, pat in SPEAKER_PATTERNS.items():
        if pat.search(text):
            speaker = spk
            break
    # Fragmentation: proportion of [...] gaps
    gaps = len(re.findall(r"\[[\s.]*\]", text))
    total_words = len(text.split())
    fragmentation = round(gaps / max(total_words, 1), 4)

    return {
        "is_opening": is_opening,
        "is_closing": is_closing,
        "speaker": speaker,
        "fragmentation": fragmentation,
    }


# ─── TF-IDF & CLUSTERING ──────────────────────────────────────────────

def cluster_paragraphs(paragraphs: List[Dict]) -> Dict:
    """Perform TF-IDF vectorization and clustering on paragraphs."""
    texts = [p["text"] for p in paragraphs]

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

    # K-means: test k=2..10
    silhouette_scores = {}
    for k in range(2, min(11, len(paragraphs))):
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(tfidf_matrix)
        sil = silhouette_score(tfidf_matrix, labels)
        silhouette_scores[k] = round(sil, 4)

    optimal_k = max(silhouette_scores, key=silhouette_scores.get)
    print(f"  Silhouette scores: {silhouette_scores}")
    print(f"  Optimal k: {optimal_k} (silhouette={silhouette_scores[optimal_k]})")

    # Final clustering with optimal k
    km_final = KMeans(n_clusters=optimal_k, random_state=42, n_init=10)
    labels = km_final.fit_predict(tfidf_matrix)

    # Characterize clusters
    cluster_profiles = {}
    for k in range(optimal_k):
        members = [paragraphs[i] for i in range(len(paragraphs)) if labels[i] == k]
        if not members:
            continue

        avg_densities = {}
        for cat in VOCAB:
            vals = [m["vocab_densities"][cat] for m in members]
            avg_densities[cat] = round(sum(vals) / len(vals), 3)

        avg_score = round(sum(m["composite_score"] for m in members) / len(members), 3)

        # Top terms from TF-IDF
        center = km_final.cluster_centers_[k]
        feature_names = vectorizer.get_feature_names_out()
        top_idx = center.argsort()[-15:][::-1]
        top_terms = [feature_names[j] for j in top_idx]

        cluster_profiles[k] = {
            "size": len(members),
            "avg_densities": avg_densities,
            "avg_composite": avg_score,
            "top_terms": top_terms,
        }

    # Hierarchical clustering
    if tfidf_matrix.shape[0] > 3:
        distances = tfidf_matrix.toarray()
        linkage_matrix = linkage(distances, method="ward")
    else:
        linkage_matrix = None

    # Assign labels
    for i, p in enumerate(paragraphs):
        p["cluster"] = int(labels[i])
        p["pca_x"] = float(coords[i, 0])
        p["pca_y"] = float(coords[i, 1])

    # Name clusters by dominant vocabulary
    cluster_names = {}
    for k, profile in cluster_profiles.items():
        d = profile["avg_densities"]
        if d.get("cosmological", 0) > d.get("pastoral", 0) * 1.5:
            name = "Cosmological"
        elif d.get("pastoral", 0) > d.get("cosmological", 0) * 1.5:
            name = "Pastoral"
        else:
            name = "Mixed"
        # Check if avg composite is high
        if profile["avg_composite"] > 3:
            name = "Core " + name
        elif profile["avg_composite"] < -1:
            name = "Heavy " + name
        cluster_names[k] = name

    for p in paragraphs:
        p["cluster_name"] = cluster_names.get(p["cluster"], "Unknown")

    return {
        "silhouette_scores": silhouette_scores,
        "optimal_k": optimal_k,
        "cluster_profiles": cluster_profiles,
        "cluster_names": cluster_names,
        "tfidf_matrix": tfidf_matrix,
        "vectorizer": vectorizer,
        "pca": pca,
        "coords": coords,
        "linkage_matrix": linkage_matrix,
    }


# ─── TIER CLASSIFICATION ──────────────────────────────────────────────

def classify_tiers(paragraphs: List[Dict]) -> None:
    """Assign tiers based on composite score."""
    for p in paragraphs:
        score = p["composite_score"]
        if score >= 4.0:
            p["tier"] = 1
            p["tier_label"] = "DEFINITE CORE"
        elif score >= 2.0:
            p["tier"] = 2
            p["tier_label"] = "STRONG CORE"
        elif score >= 0.5:
            p["tier"] = 3
            p["tier_label"] = "PROBABLE CORE"
        elif score >= -0.5:
            p["tier"] = 4
            p["tier_label"] = "BORDERLINE"
        else:
            p["tier"] = 5
            p["tier_label"] = "EDITORIAL"


# ─── CORE RECONSTRUCTION ──────────────────────────────────────────────

def generate_reconstruction(paragraphs: List[Dict]) -> str:
    """Generate the reconstructed core teaching text."""
    lines = []
    lines.append("# The Kephalaia of the Teacher — Recovered Core Teaching")
    lines.append("")
    lines.append("> **Method**: Paragraph-level vocabulary analysis with editorial stripping")
    lines.append("> **Source**: Gardner (1995), Brill — OCR'd and analyzed computationally")
    lines.append("> **Date**: Generated by v3 paragraph-level core recovery pipeline")
    lines.append("")

    # Statistics
    core = [p for p in paragraphs if p["tier"] <= 3]
    total_words = sum(p["word_count"] for p in paragraphs)
    core_words = sum(p["word_count"] for p in core)

    lines.append(f"**Recovery summary**: {len(core)} of {len(paragraphs)} passages retained "
                 f"({core_words:,} of {total_words:,} words = {core_words/total_words*100:.1f}%)")
    lines.append("")
    lines.append("**Tier legend**:")
    lines.append("- **T1** = Definite Core (score >= 4.0) — Pure Manichaean cosmogonic teaching")
    lines.append("- **T2** = Strong Core (score 2.0–4.0) — Predominantly cosmological")
    lines.append("- **T3** = Probable Core (score 0.5–2.0) — Cosmological content with some editorial framing")
    lines.append("- *Excluded*: T4 Borderline (score -0.5–0.5) and T5 Editorial (score < -0.5)")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Reconstruct in document order
    current_tier = None
    for p in sorted(core, key=lambda x: x["start_line"]):
        tier = p["tier"]
        if tier != current_tier:
            if current_tier is not None:
                lines.append("")
            tier_headers = {
                1: "## Tier 1 — Definite Core",
                2: "## Tier 2 — Strong Core",
                3: "## Tier 3 — Probable Core",
            }
            # Don't add tier headers — just flow continuously
            current_tier = tier

        # Passage header
        ch = p["editorial_chapter"]
        score = p["composite_score"]
        tier_tag = f"T{tier}"
        lines.append(f"### [{p['id']}] — Score {score:+.2f} [{tier_tag}] "
                     f"(Ch.{ch}, lines {p['start_line']}–{p['end_line']})")
        lines.append("")

        # Clean up raw text for presentation
        raw = p["raw_text"]
        # Remove inline line numbers but keep the text readable
        cleaned_raw = re.sub(r"(?<=\S)\s*\d{1,2}\s+(?=[A-Z])", " ", raw)
        lines.append(cleaned_raw)
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# ─── VISUALIZATIONS ───────────────────────────────────────────────────

def generate_visualizations(paragraphs: List[Dict], cluster_info: Dict) -> None:
    """Generate all analysis visualizations."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Color schemes
    tier_colors = {1: "#1a5276", 2: "#2874a6", 3: "#5dade2", 4: "#f0b27a", 5: "#e74c3c"}

    # --- Figure 1: Score along document ---
    fig, ax = plt.subplots(figsize=(16, 5))
    scores = [p["composite_score"] for p in paragraphs]
    colors = [tier_colors[p["tier"]] for p in paragraphs]
    x = range(len(paragraphs))
    ax.bar(x, scores, color=colors, width=1.0, edgecolor="none")
    ax.axhline(y=4.0, color="#1a5276", linestyle="--", alpha=0.5, label="T1 threshold")
    ax.axhline(y=2.0, color="#2874a6", linestyle="--", alpha=0.5, label="T2 threshold")
    ax.axhline(y=0.5, color="#5dade2", linestyle="--", alpha=0.5, label="T3 threshold")
    ax.axhline(y=-0.5, color="#f0b27a", linestyle="--", alpha=0.5, label="T4 threshold")
    ax.axhline(y=0, color="black", linewidth=0.5)
    ax.set_xlabel("Paragraph (document order)")
    ax.set_ylabel("Composite Score")
    ax.set_title("Paragraph Originality Scores — Document Flow")
    ax.legend(loc="upper right", fontsize=8)
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "v3_01_score_flow.png", dpi=150)
    plt.close(fig)
    print("  Saved v3_01_score_flow.png")

    # --- Figure 2: Score distribution ---
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(scores, bins=40, color="#2874a6", edgecolor="white", alpha=0.8)
    for thresh, label, col in [(4.0, "T1", "#1a5276"), (2.0, "T2", "#2874a6"),
                                (0.5, "T3", "#5dade2"), (-0.5, "T4", "#f0b27a")]:
        ax.axvline(x=thresh, color=col, linestyle="--", label=label)
    ax.set_xlabel("Composite Score")
    ax.set_ylabel("Count")
    ax.set_title("Distribution of Paragraph Scores")
    ax.legend()
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "v3_02_score_distribution.png", dpi=150)
    plt.close(fig)
    print("  Saved v3_02_score_distribution.png")

    # --- Figure 3: Vocabulary flow ---
    fig, ax = plt.subplots(figsize=(16, 5))
    cats = ["cosmological", "persian_substrate", "pastoral", "nt_christian", "hagiographic"]
    cat_colors = ["#1a5276", "#7d3c98", "#e74c3c", "#f39c12", "#95a5a6"]
    window = 5  # rolling average
    for cat, col in zip(cats, cat_colors):
        vals = [p["vocab_densities"].get(cat, 0) for p in paragraphs]
        if len(vals) >= window:
            smoothed = np.convolve(vals, np.ones(window)/window, mode="valid")
            ax.plot(range(len(smoothed)), smoothed, label=cat, color=col, linewidth=1.5)
    ax.set_xlabel("Paragraph (document order)")
    ax.set_ylabel("Vocabulary Density (per 100 words, smoothed)")
    ax.set_title("Vocabulary Category Flow Through Document")
    ax.legend(fontsize=8)
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "v3_03_vocab_flow.png", dpi=150)
    plt.close(fig)
    print("  Saved v3_03_vocab_flow.png")

    # --- Figure 4: Sub-cluster PCA ---
    fig, ax = plt.subplots(figsize=(10, 8))
    cluster_colors = plt.cm.Set2(np.linspace(0, 1, cluster_info["optimal_k"]))
    for k in range(cluster_info["optimal_k"]):
        members = [p for p in paragraphs if p["cluster"] == k]
        if members:
            xs = [p["pca_x"] for p in members]
            ys = [p["pca_y"] for p in members]
            name = cluster_info["cluster_names"].get(k, f"C{k}")
            ax.scatter(xs, ys, c=[cluster_colors[k]], label=f"{name} ({len(members)})",
                      alpha=0.6, s=20)
    ax.set_xlabel(f"PC1 ({cluster_info['pca'].explained_variance_ratio_[0]*100:.1f}%)")
    ax.set_ylabel(f"PC2 ({cluster_info['pca'].explained_variance_ratio_[1]*100:.1f}%)")
    ax.set_title(f"Paragraph Sub-Clusters (k={cluster_info['optimal_k']})")
    ax.legend(fontsize=8, loc="best")
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "v3_04_subclusters.png", dpi=150)
    plt.close(fig)
    print("  Saved v3_04_subclusters.png")

    # --- Figure 5: Dendrogram ---
    if cluster_info["linkage_matrix"] is not None:
        fig, ax = plt.subplots(figsize=(16, 6))
        dendrogram(
            cluster_info["linkage_matrix"],
            truncate_mode="lastp",
            p=30,
            leaf_rotation=90,
            leaf_font_size=8,
            ax=ax,
        )
        ax.set_title("Hierarchical Clustering of Paragraphs")
        ax.set_ylabel("Distance")
        plt.tight_layout()
        fig.savefig(OUTPUT_DIR / "v3_05_dendrogram.png", dpi=150)
        plt.close(fig)
        print("  Saved v3_05_dendrogram.png")

    # --- Figure 6: Tier composition ---
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # By paragraph count
    tier_counts = Counter(p["tier"] for p in paragraphs)
    tier_labels = ["T1: Definite", "T2: Strong", "T3: Probable", "T4: Borderline", "T5: Editorial"]
    counts = [tier_counts.get(i+1, 0) for i in range(5)]
    cols = [tier_colors[i+1] for i in range(5)]
    axes[0].pie(counts, labels=tier_labels, colors=cols, autopct="%1.1f%%", startangle=90)
    axes[0].set_title("By Paragraph Count")

    # By word count
    tier_words = defaultdict(int)
    for p in paragraphs:
        tier_words[p["tier"]] += p["word_count"]
    words = [tier_words.get(i+1, 0) for i in range(5)]
    axes[1].pie(words, labels=tier_labels, colors=cols, autopct="%1.1f%%", startangle=90)
    axes[1].set_title("By Word Count")

    fig.suptitle("Tier Composition of the Kephalaia", fontsize=14)
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "v3_06_tier_composition.png", dpi=150)
    plt.close(fig)
    print("  Saved v3_06_tier_composition.png")

    # --- Figure 7: Cluster vocabulary profiles ---
    fig, ax = plt.subplots(figsize=(12, 6))
    profiles = cluster_info["cluster_profiles"]
    n_clusters = len(profiles)
    cats = list(VOCAB.keys())
    x_pos = np.arange(len(cats))
    width = 0.8 / n_clusters

    for i, (k, prof) in enumerate(sorted(profiles.items())):
        vals = [prof["avg_densities"].get(c, 0) for c in cats]
        name = cluster_info["cluster_names"].get(k, f"C{k}")
        ax.bar(x_pos + i * width, vals, width, label=f"{name} (n={prof['size']})",
               color=cluster_colors[i] if i < len(cluster_colors) else "gray")

    ax.set_xticks(x_pos + width * (n_clusters - 1) / 2)
    ax.set_xticklabels(cats, rotation=30, ha="right")
    ax.set_ylabel("Avg Density (per 100 words)")
    ax.set_title("Vocabulary Profiles by Sub-Cluster")
    ax.legend(fontsize=8)
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "v3_07_cluster_profiles.png", dpi=150)
    plt.close(fig)
    print("  Saved v3_07_cluster_profiles.png")

    # --- Figure 8: Reconstruction map ---
    fig, ax = plt.subplots(figsize=(16, 3))
    for i, p in enumerate(paragraphs):
        color = "#2ecc71" if p["tier"] <= 3 else "#e74c3c"
        alpha = max(0.3, min(1.0, 0.3 + p["composite_score"] / 10))
        ax.barh(0, 1, left=i, height=0.8, color=color, alpha=alpha, edgecolor="none")
    ax.set_xlim(0, len(paragraphs))
    ax.set_yticks([])
    ax.set_xlabel("Paragraph (document order)")
    ax.set_title("Reconstruction Map — Green=Retained, Red=Excluded")
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "v3_08_reconstruction_map.png", dpi=150)
    plt.close(fig)
    print("  Saved v3_08_reconstruction_map.png")


# ─── REPORT GENERATION ────────────────────────────────────────────────

def generate_report(paragraphs: List[Dict], cluster_info: Dict,
                    line_stats: Dict) -> str:
    """Generate comprehensive analysis report."""
    lines = []
    lines.append("# Kephalaia Core Recovery — v3 Paragraph-Level Analysis Report")
    lines.append("")
    lines.append("## 1. Methodology")
    lines.append("")
    lines.append("This analysis treats **chapter boundaries as editorial artifacts** and works at the "
                "paragraph level to recover the original Manichaean teaching underneath the editorial "
                "infrastructure imposed by later redactors.")
    lines.append("")
    lines.append("### Pipeline")
    lines.append("1. **Line Classification**: Every line tagged as FRONT_MATTER, CHAPTER_MARKER, "
                "PAGE_REF, TITLE, GARDNER, PAGE_HEADER, PAGE_NUMBER, FOOTNOTE, DIVIDER, TEACHING, or BLANK")
    lines.append("2. **Paragraph Extraction**: Teaching text extracted, joined across page breaks, "
                "split at semantic boundaries (speaker changes, teaching formulas, closing formulas)")
    lines.append("3. **Vocabulary Scoring**: 5 vocabulary categories (cosmological, persian_substrate, "
                "pastoral, nt_christian, hagiographic) scored per 100 words")
    lines.append("4. **Composite Scoring**: Weighted combination of vocabulary densities")
    lines.append("5. **Sub-Clustering**: TF-IDF + K-means on paragraph texts")
    lines.append("6. **Tier Classification**: Paragraphs assigned to 5 tiers based on composite score")
    lines.append("7. **Core Reconstruction**: Tier 1–3 paragraphs extracted in document order")
    lines.append("")

    # Line classification stats
    lines.append("## 2. Source Text Decomposition")
    lines.append("")
    lines.append("| Line Type | Count | % |")
    lines.append("|-----------|-------|---|")
    total_lines = sum(line_stats.values())
    for lt in ["TEACHING", "GARDNER", "FRONT_MATTER", "BLANK", "DIVIDER",
               "PAGE_HEADER", "FOOTNOTE", "CHAPTER_MARKER", "PAGE_REF",
               "TITLE", "PAGE_NUMBER"]:
        c = line_stats.get(lt, 0)
        pct = c / total_lines * 100 if total_lines > 0 else 0
        lines.append(f"| {lt} | {c} | {pct:.1f}% |")
    lines.append(f"| **TOTAL** | **{total_lines}** | **100%** |")
    lines.append("")

    # Paragraph stats
    lines.append("## 3. Paragraph Statistics")
    lines.append("")
    total_paras = len(paragraphs)
    total_words = sum(p["word_count"] for p in paragraphs)
    word_counts = [p["word_count"] for p in paragraphs]
    lines.append(f"- **Total teaching paragraphs**: {total_paras}")
    lines.append(f"- **Total teaching words**: {total_words:,}")
    lines.append(f"- **Mean paragraph length**: {np.mean(word_counts):.0f} words")
    lines.append(f"- **Median paragraph length**: {np.median(word_counts):.0f} words")
    lines.append(f"- **Range**: {min(word_counts)} – {max(word_counts)} words")
    lines.append("")

    # Score distribution
    scores = [p["composite_score"] for p in paragraphs]
    lines.append("## 4. Score Distribution")
    lines.append("")
    lines.append(f"- **Mean**: {np.mean(scores):.2f}")
    lines.append(f"- **Median**: {np.median(scores):.2f}")
    lines.append(f"- **Std Dev**: {np.std(scores):.2f}")
    lines.append(f"- **Range**: {min(scores):.2f} to {max(scores):.2f}")
    lines.append("")

    # Tier breakdown
    lines.append("## 5. Tier Breakdown")
    lines.append("")
    lines.append("| Tier | Label | Threshold | Paragraphs | Words | % Words |")
    lines.append("|------|-------|-----------|------------|-------|---------|")
    for tier in range(1, 6):
        members = [p for p in paragraphs if p["tier"] == tier]
        tier_words = sum(p["word_count"] for p in members)
        pct = tier_words / total_words * 100 if total_words > 0 else 0
        labels = {1: "Definite Core", 2: "Strong Core", 3: "Probable Core",
                  4: "Borderline", 5: "Editorial"}
        thresholds = {1: ">= 4.0", 2: "2.0–4.0", 3: "0.5–2.0", 4: "-0.5–0.5", 5: "< -0.5"}
        lines.append(f"| T{tier} | {labels[tier]} | {thresholds[tier]} | "
                    f"{len(members)} | {tier_words:,} | {pct:.1f}% |")
    core = [p for p in paragraphs if p["tier"] <= 3]
    core_words = sum(p["word_count"] for p in core)
    lines.append(f"| **T1–T3** | **Core Total** | **>= 0.5** | "
                f"**{len(core)}** | **{core_words:,}** | **{core_words/total_words*100:.1f}%** |")
    lines.append("")

    # Sub-clustering
    lines.append("## 6. Sub-Clustering")
    lines.append("")
    lines.append(f"**Optimal k**: {cluster_info['optimal_k']}")
    lines.append("")
    lines.append("**Silhouette scores**:")
    for k, s in sorted(cluster_info["silhouette_scores"].items()):
        marker = " ← optimal" if k == cluster_info["optimal_k"] else ""
        lines.append(f"- k={k}: {s}{marker}")
    lines.append("")

    lines.append("### Cluster Profiles")
    lines.append("")
    for k, prof in sorted(cluster_info["cluster_profiles"].items()):
        name = cluster_info["cluster_names"].get(k, f"Cluster {k}")
        lines.append(f"**{name}** (n={prof['size']}, avg_score={prof['avg_composite']:.2f})")
        lines.append(f"- Top terms: {', '.join(prof['top_terms'][:10])}")
        lines.append(f"- Avg densities: {prof['avg_densities']}")
        lines.append("")

    # Top passages
    lines.append("## 7. Top 30 Passages by Score")
    lines.append("")
    lines.append("| Rank | ID | Ch. | Score | Words | Cosmo | Pastoral | Key Terms |")
    lines.append("|------|-----|-----|-------|-------|-------|----------|-----------|")
    ranked = sorted(paragraphs, key=lambda p: -p["composite_score"])
    for rank, p in enumerate(ranked[:30], 1):
        cosmo = p["vocab_densities"].get("cosmological", 0)
        pastoral = p["vocab_densities"].get("pastoral", 0)
        key_terms = "; ".join(p["vocab_terms"].get("cosmological", [])[:3])
        lines.append(f"| {rank} | {p['id']} | {p['editorial_chapter']} | "
                    f"{p['composite_score']:+.2f} | {p['word_count']} | "
                    f"{cosmo:.1f} | {pastoral:.1f} | {key_terms} |")
    lines.append("")

    # Bottom passages
    lines.append("## 8. Bottom 15 Passages (Most Editorial)")
    lines.append("")
    lines.append("| Rank | ID | Ch. | Score | Words | Cosmo | Pastoral | Key Terms |")
    lines.append("|------|-----|-----|-------|-------|-------|----------|-----------|")
    for rank, p in enumerate(ranked[-15:], len(ranked) - 14):
        cosmo = p["vocab_densities"].get("cosmological", 0)
        pastoral = p["vocab_densities"].get("pastoral", 0)
        key_terms = "; ".join(p["vocab_terms"].get("pastoral", [])[:3])
        lines.append(f"| {rank} | {p['id']} | {p['editorial_chapter']} | "
                    f"{p['composite_score']:+.2f} | {p['word_count']} | "
                    f"{cosmo:.1f} | {pastoral:.1f} | {key_terms} |")
    lines.append("")

    # Editorial chapter coverage
    lines.append("## 9. Editorial Chapter Coverage")
    lines.append("")
    lines.append("How each editorial chapter's paragraphs distribute across tiers:")
    lines.append("")
    lines.append("| Ch. | Paras | T1 | T2 | T3 | T4 | T5 | Avg Score | Verdict |")
    lines.append("|-----|-------|----|----|----|----|----|-----------| --------|")

    ch_groups = defaultdict(list)
    for p in paragraphs:
        ch_groups[p["editorial_chapter"]].append(p)

    for ch in sorted(ch_groups.keys()):
        group = ch_groups[ch]
        tier_counts = Counter(p["tier"] for p in group)
        avg = np.mean([p["composite_score"] for p in group])
        verdict = "CORE" if avg >= 2.0 else "MIXED" if avg >= 0.0 else "EDITORIAL"
        lines.append(
            f"| {ch} | {len(group)} | {tier_counts.get(1,0)} | {tier_counts.get(2,0)} | "
            f"{tier_counts.get(3,0)} | {tier_counts.get(4,0)} | {tier_counts.get(5,0)} | "
            f"{avg:+.2f} | {verdict} |"
        )
    lines.append("")

    # Full paragraph inventory (appendix)
    lines.append("## Appendix: Full Paragraph Inventory")
    lines.append("")
    lines.append("| ID | Ch. | Lines | Words | Score | Tier | Cluster | Cosmo | Pastoral |")
    lines.append("|----|-----|-------|-------|-------|------|---------|-------|----------|")
    for p in paragraphs:
        lines.append(
            f"| {p['id']} | {p['editorial_chapter']} | "
            f"{p['start_line']}–{p['end_line']} | {p['word_count']} | "
            f"{p['composite_score']:+.2f} | T{p['tier']} | {p.get('cluster_name', '?')} | "
            f"{p['vocab_densities'].get('cosmological', 0):.1f} | "
            f"{p['vocab_densities'].get('pastoral', 0):.1f} |"
        )
    lines.append("")

    return "\n".join(lines)


# ─── MAIN ─────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("KEPHALAIA v3 — PARAGRAPH-LEVEL CORE RECOVERY")
    print("=" * 70)

    # Load source text
    print("\n[1/7] Loading source text...")
    text = SOURCE_PATH.read_text(encoding="utf-8")
    total_lines = len(text.split("\n"))
    print(f"  Loaded {total_lines:,} lines from {SOURCE_PATH.name}")

    # Classify lines
    print("\n[2/7] Classifying lines...")
    classified = classify_lines(text)
    line_stats = Counter(e["type"] for e in classified)
    teaching_count = line_stats.get("TEACHING", 0)
    gardner_count = line_stats.get("GARDNER", 0)
    print(f"  TEACHING: {teaching_count} lines ({teaching_count/total_lines*100:.1f}%)")
    print(f"  GARDNER:  {gardner_count} lines ({gardner_count/total_lines*100:.1f}%)")
    print(f"  OTHER:    {total_lines - teaching_count - gardner_count} lines")

    # Extract paragraphs
    print("\n[3/7] Extracting paragraphs...")
    paragraphs = extract_paragraphs(classified)
    print(f"  Extracted {len(paragraphs)} teaching paragraphs")
    word_counts = [p["word_count"] for p in paragraphs]
    print(f"  Word count: mean={np.mean(word_counts):.0f}, "
          f"median={np.median(word_counts):.0f}, "
          f"range={min(word_counts)}-{max(word_counts)}")

    # Score vocabularies
    print("\n[4/7] Scoring vocabulary...")
    for p in paragraphs:
        densities, terms = score_vocabulary(p["text"], p["word_count"])
        p["vocab_densities"] = densities
        p["vocab_terms"] = terms
        p["composite_score"] = compute_composite(densities)

        # Structural features
        p["structural"] = detect_structural(p["joined_text"])

        # NT citations from raw text
        p["nt_citations"] = detect_nt_citations(p["raw_text"])

    scores = [p["composite_score"] for p in paragraphs]
    print(f"  Score range: {min(scores):.2f} to {max(scores):.2f}")
    print(f"  Mean: {np.mean(scores):.2f}, Median: {np.median(scores):.2f}")

    # Sub-clustering
    print("\n[5/7] Sub-clustering paragraphs...")
    cluster_info = cluster_paragraphs(paragraphs)

    # Tier classification
    print("\n[6/7] Classifying tiers...")
    classify_tiers(paragraphs)
    tier_counts = Counter(p["tier"] for p in paragraphs)
    for tier in range(1, 6):
        c = tier_counts.get(tier, 0)
        labels = {1: "DEFINITE CORE", 2: "STRONG CORE", 3: "PROBABLE CORE",
                  4: "BORDERLINE", 5: "EDITORIAL"}
        print(f"  T{tier} ({labels[tier]}): {c} paragraphs")

    core_paras = [p for p in paragraphs if p["tier"] <= 3]
    core_words = sum(p["word_count"] for p in core_paras)
    total_words = sum(p["word_count"] for p in paragraphs)
    print(f"  CORE (T1-T3): {len(core_paras)} passages, {core_words:,} words "
          f"({core_words/total_words*100:.1f}% of teaching text)")

    # Generate outputs
    print("\n[7/7] Generating outputs...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Visualizations
    print("  Generating visualizations...")
    generate_visualizations(paragraphs, cluster_info)

    # Report
    print("  Generating report...")
    report = generate_report(paragraphs, cluster_info, line_stats)
    (OUTPUT_DIR / "v3_report.md").write_text(report, encoding="utf-8")
    print(f"  Saved v3_report.md ({len(report):,} chars)")

    # Reconstruction
    print("  Generating core reconstruction...")
    recon = generate_reconstruction(paragraphs)
    (OUTPUT_DIR / "v3_reconstruction.md").write_text(recon, encoding="utf-8")
    print(f"  Saved v3_reconstruction.md ({len(recon):,} chars)")

    # JSON data
    print("  Saving paragraph data...")
    json_data = []
    for p in paragraphs:
        entry = {k: v for k, v in p.items()
                 if k not in ("text", "raw_text", "joined_text", "pca_x", "pca_y")}
        entry["text_preview"] = p["text"][:200]
        entry["pca"] = {"x": p.get("pca_x", 0), "y": p.get("pca_y", 0)}
        json_data.append(entry)
    (OUTPUT_DIR / "v3_paragraphs.json").write_text(
        json.dumps(json_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  Saved v3_paragraphs.json ({len(json_data)} entries)")

    # Summary
    print("\n" + "=" * 70)
    print("COMPLETE")
    print(f"  Total paragraphs: {len(paragraphs)}")
    print(f"  Core recovered:   {len(core_paras)} passages ({core_words:,} words)")
    print(f"  Output directory:  {OUTPUT_DIR}")
    print("=" * 70)


if __name__ == "__main__":
    main()
