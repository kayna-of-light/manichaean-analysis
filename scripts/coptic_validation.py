#!/usr/bin/env python3
"""
Coptic-based validation of English-derived temporal layer classifications.

Pipeline stage: runs AFTER all English-side analysis, using Coptic transcriptions.

This script performs computational linguistic analysis on the raw Coptic text
to validate and extend the temporal-layer classifications that were produced
by stages 2-4 using English translation alone.

What it extracts (per chapter):
  - Greek loanword density, split by register (cosmological vs. ecclesiastical)
  - Sub-Achmimic dialect consistency (ⲍ/ϩ ratio)
  - Coptic formulaic patterns (dialogue frame, blessing closures, etc.)
  - Lacunae density (proportion of damaged/illegible text)
  - Chapter-level concordance with English-based classification

What it does NOT do:
  - Map Coptic lines to individual English paragraphs (that's unreliable)
  - All analysis is at the CHAPTER level, where boundaries are certain

Output: output/projects/<project>/analysis/coptic/ch_NNN.json
        output/projects/<project>/analysis/coptic_summary.json

Usage:
    python scripts/stage_11_coptic_analysis.py --project kephalaia
    python scripts/stage_11_coptic_analysis.py --project kephalaia --chapter 38
    python scripts/stage_11_coptic_analysis.py --project kephalaia --range 0-50
    python scripts/stage_11_coptic_analysis.py --project kephalaia --dry-run
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

from project_config import load_project

# ---------------------------------------------------------------------------
# Paths — set by configure_paths() at startup
# ---------------------------------------------------------------------------

PROJECT_CFG = None
CLEANED_DIR: Path | None = None    # cleaned chapter JSONs (for manuscript_pages)
CORE_DIR: Path | None = None       # core chapter JSONs (for classifications)
COPTIC_DIR: Path | None = None     # Coptic transcriptions
OUTPUT_DIR: Path | None = None     # analysis output


def configure_paths(project_name: str) -> None:
    global PROJECT_CFG, CLEANED_DIR, CORE_DIR, COPTIC_DIR, OUTPUT_DIR

    cfg = load_project(project_name)
    cfg.paths.ensure_dirs()
    PROJECT_CFG = cfg

    CLEANED_DIR = cfg.paths.cleaned_chapters
    CORE_DIR = cfg.paths.core_chapters
    COPTIC_DIR = cfg.paths.project_dir / "coptic" / "transcriptions"
    OUTPUT_DIR = cfg.paths.project_dir / "analysis" / "coptic"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Project: {cfg.display_name}")
    print(f"  Cleaned: {CLEANED_DIR}")
    print(f"  Core:    {CORE_DIR}")
    print(f"  Coptic:  {COPTIC_DIR}")
    print(f"  Output:  {OUTPUT_DIR}")


# ---------------------------------------------------------------------------
# Greek loanword lexicons — classified by register
#
# These lists are based on the actual vocabulary observed in the Kephalaia
# Coptic transcriptions. Words are in their common Coptic-script forms.
# ---------------------------------------------------------------------------

# Cosmological/philosophical Greek — used in the oldest teaching substrate
GREEK_COSMOLOGICAL = {
    # Cosmological terms
    "ⲥⲧⲟⲓⲭⲉⲓⲟⲛ", "ⲥⲧⲟⲭⲉⲓⲟⲛ", "ⲥⲧⲟⲓⲭⲓⲟⲛ", "ⲥⲧⲟⲭⲉⲱⲛ",
    "ⲕⲟⲥⲙⲟⲥ",
    "ⲁⲓⲱⲛ", "ⲁⲱⲛ",  # aeon (both spellings)
    "ⲍⲩⲗⲏ", "ϩⲩⲗⲏ",  # hyle/matter
    "ⲫⲩⲥⲓⲥ",  # physis/nature
    "ⲡⲛⲉⲩⲙⲁ", "ⲡⲛ̅ⲁ̅",  # pneuma (full + abbreviation)
    "ⲯⲩⲭⲏ",  # psyche
    "ⲛⲟⲩⲥ",  # nous/mind
    "ⲥⲱⲙⲁ",  # soma/body
    "ⲍⲱⲇⲓⲟⲛ", "ⲍⲱⲇⲓⲁ",  # zodion
    "ⲥⲫⲁⲓⲣⲁ",  # sphaira
    # Philosophical terms
    "ⲁⲣⲭⲏ",  # arche
    "ⲟⲩⲥⲓⲁ",  # ousia
    "ⲉⲓⲕⲱⲛ",  # eikon/image
    "ⲧⲩⲡⲟⲥ",  # typos/type
    "ⲑⲉⲗⲏⲙⲁ",  # thelema/will
    "ⲉⲛⲉⲣⲅⲓⲁ", "ⲉⲛⲉⲣⲅⲉⲓⲁ",  # energeia
    "ⲇⲩⲛⲁⲙⲓⲥ",  # dynamis
    "ⲡⲗⲏⲣⲱⲙⲁ",  # pleroma
    "ⲙⲟⲣⲫⲏ",  # morphe
    "ⲡⲁⲣⲁⲇⲉⲓⲥⲟⲥ", "ⲡⲁⲣⲁⲇⲓⲥⲟⲥ",  # paradeisos
    "ⲅⲉⲛⲟⲥ",  # genos/genus
    "ⲅⲉⲛⲉⲁ",  # genea/generation
    "ⲡⲣⲟⲃⲟⲗⲏ",  # probole/emanation
}

# Ecclesiastical/institutional Greek — church organization, hierarchy, ritual
GREEK_ECCLESIASTICAL = {
    # Church offices
    "ⲡⲣⲉⲥⲃⲩⲧⲉⲣⲟⲥ",  # presbyteros
    "ⲉⲡⲓⲥⲕⲟⲡⲟⲥ",  # episkopos
    "ⲇⲓⲁⲕⲟⲛⲟⲥ",  # diakonos
    "ⲁⲡⲟⲥⲧⲟⲗⲟⲥ",  # apostolos
    "ⲉⲕⲗⲉⲕⲧⲟⲥ",  # eklektos/elect
    "ⲕⲁⲧⲏⲭⲟⲩⲙⲉⲛⲟⲥ",  # katechoumenos
    # Ritual/institutional terms
    "ⲭⲉⲓⲣⲟⲧⲟⲛⲓⲁ",  # cheirotonia/laying on of hands
    "ⲉⲩⲭⲁⲣⲓⲥⲧⲓⲁ",  # eucharistia
    "ⲃⲁⲡⲧⲓⲥⲙⲁ",  # baptisma
    "ⲡⲁⲣⲁⲕⲗⲏⲧⲟⲥ",  # parakletos
    "ⲉⲕⲕⲗⲏⲥⲓⲁ",  # ekklesia
    "ⲡⲣⲟⲥⲉⲩⲭⲏ",  # proseuche/prayer
    "ⲉⲗⲉⲏⲙⲟⲥⲩⲛⲏ",  # eleemosyne/alms
    "ⲁⲅⲁⲡⲏ",  # agape
    "ⲡⲓⲥⲧⲓⲥ",  # pistis/faith
    "ⲁⲥⲡⲁⲥⲙⲟⲥ",  # aspasmos/greeting
    "ⲙⲩⲥⲧⲏⲣⲓⲟⲛ",  # mysterion
    # Moral/ethical terms (pastoral application)
    "ⲇⲓⲕⲁⲓⲟⲥⲩⲛⲏ", "ⲁⲓⲕⲁⲓⲟⲥⲩⲛⲏ",  # dikaiosyne
    "ⲡⲁⲣⲁⲃⲁⲥⲓⲥ",  # parabasis/transgression
    "ⲡⲁⲣⲁⲙⲡⲧⲟⲗⲏ", "ⲡⲁⲣⲁⲡⲧⲱⲙⲁ",  # paraptoma
    "ⲡⲟⲣⲛⲉⲓⲁ",  # porneia
    "ⲙⲉⲧⲁⲛⲟⲓⲁ",  # metanoia
    "ⲡⲁⲣⲑⲉⲛⲟⲥ",  # parthenos
    # Titles
    "ⲫⲱⲥⲧⲏⲣ",  # phoster/enlightener
    "ⲁⲣⲭⲏⲅⲟⲥ",  # archegos/leader
    "ⲙⲁⲑⲏⲧⲏⲥ",  # mathetes/disciple
    "ⲇⲓⲇⲁⲥⲕⲁⲗⲟⲥ",  # didaskalos/teacher
    "ⲡⲣⲉⲥⲃⲉⲩⲧⲏⲥ",  # presbeutes/ambassador
}

# General Greek loanwords that appear everywhere (not diagnostic by register)
GREEK_GENERAL = {
    "ⲉⲡⲉⲓⲇⲏ", "ⲉⲡⲉⲓⲁⲏ",  # epeide/since (conjunction)
    "ⲁⲗⲗⲁ",  # alla/but
    "ⲅⲁⲣ",  # gar/for
    "ⲇⲉ", "ⲁⲉ",  # de/and, but
    "ⲟⲩⲇⲉ",  # oude/nor
    "ⲕⲁⲓ",  # kai/and (used less in Coptic)
    "ϩⲱⲥⲧⲉ",  # hoste/so that
    "ⲕⲁⲧⲁ",  # kata/according to
    "ⲡⲣⲟⲥ",  # pros/toward
    "ⲡⲁⲣⲁ",  # para/from
    "ⲭⲱⲣⲓⲥ",  # choris/without
}

# ---------------------------------------------------------------------------
# Coptic formulaic patterns — dialogue frame signatures
# ---------------------------------------------------------------------------

# Dialogue openings in Coptic
DIALOGUE_OPENING_PATTERNS = [
    re.compile(r"ⲧⲧⲁⲗⲓⲛ\s+ⲁ\s+ⲛⲙⲁⲑⲏⲧⲏⲥ", re.IGNORECASE),  # "once again the disciples"
    re.compile(r"ⲡⲁⲡⲟⲥⲧⲟⲗⲟⲥ\s+ⲡⲁ[ⲭⲭ]ⲉ", re.IGNORECASE),  # "the apostle says"
    re.compile(r"ⲧⲟⲧⲉ\s+ⲡⲁⲭⲉ", re.IGNORECASE),  # "then he said"
    re.compile(r"ⲡⲓⲫⲱⲥⲧ[ⲏⲏ]ⲣ", re.IGNORECASE),  # "the enlightener"
    re.compile(r"ⲡⲁⲭⲉ[ϩⲩ]\s+ⲁⲣⲁ[ⲩⲉ]", re.IGNORECASE),  # "he/they said to them"
]

# Disciple question patterns
QUESTION_PATTERNS = [
    re.compile(r"ⲧⲛⲧⲱⲃϩ\s+ⲙⲙⲁⲕ", re.IGNORECASE),  # "we beseech you"
    re.compile(r"ⲡⲛ̄ⲭⲁⲓ̈?ⲥ", re.IGNORECASE),  # "our master"
    re.compile(r"ⲁⲭⲓⲥ\s+ⲁⲣⲁⲛ", re.IGNORECASE),  # "tell us"
]

# Response/teaching formulas
RESPONSE_PATTERNS = [
    re.compile(r"ⲁⲛⲁⲕ\s+ⲡⲉⲧⲛⲁ", re.IGNORECASE),  # "I am the one who will..."
    re.compile(r"ⲉⲧⲉⲧⲛⲥⲁⲩⲛⲉ", re.IGNORECASE),  # "happen you know"
    re.compile(r"ⲱⲱⲧⲉ\s+ⲉⲧⲉⲧⲛⲥⲁⲩⲛⲉ", re.IGNORECASE),  # "so that you know"
]

# Blessing/closure formulas
BLESSING_PATTERNS = [
    re.compile(r"ⲉⲩⲙⲁⲕⲁⲣⲓⲟⲥ", re.IGNORECASE),  # "blessed is"
    re.compile(r"ⲛⲁⲙⲉⲣⲉⲧⲉ", re.IGNORECASE),  # "my beloved"
    re.compile(r"ⲛⲁⲙⲉⲗⲟⲥ", re.IGNORECASE),  # "my limbs"
]

# Exhortation markers
EXHORTATION_PATTERNS = [
    re.compile(r"ⲁⲣⲓ[ⲡⲧ]ⲙⲉⲉⲩⲉ", re.IGNORECASE),  # "remember" (hortatory)
    re.compile(r"ⲙⲁⲣⲉ[ⲛⲛ]", re.IGNORECASE),  # "let us" (hortatory subjunctive)
]

# ---------------------------------------------------------------------------
# Sub-Achmimic dialect markers
# ---------------------------------------------------------------------------

# Sub-Achmimic forms (older dialect of the Kephalaia manuscript)
# The key marker is ⲍ where Sahidic has ϩ
SUBACHMIMIC_MARKERS = {
    "ⲍⲙ̄": "ϩⲙ̄",    # "in"
    "ⲍⲛ": "ϩⲛ",      # "in"
    "ⲍⲛ̄": "ϩⲛ̄",    # "in" (with supralinear stroke)
    "ⲁⲍ": "ⲁϩ",      # prefix form
    "ⲍⲓ": "ϩⲓ",      # "upon"
    "ⲍⲁ": "ϩⲁ",      # "under"
    "ⲍⲏⲧ": "ϩⲏⲧ",   # "heart/belly"
    "ⲍⲱⲃ": "ϩⲱⲃ",   # "thing"
    "ⲍⲣⲏ": "ϩⲣⲏ",   # part of compound words
    "ⲍⲁⲗ": "ϩⲁⲗ",   # old woman / wife
    "ⲍⲱⲡ": "ϩⲱⲡ",   # "to hide"
    "ⲍⲉ": "ϩⲉ",      # "manner"
    "ⲍⲁⲉ": "ϩⲁⲉ",   # "end"
    "ⲍⲁⲏ": "ϩⲁⲏ",   # "end" (variant)
}

# The reverse: Sahidic forms where Sub-Achmimic would use ⲍ
# Finding these in the text suggests Sahidic influence/later editing
SAHIDIC_INTRUSIONS = {v: k for k, v in SUBACHMIMIC_MARKERS.items()}


# ---------------------------------------------------------------------------
# Manuscript page parsing
# ---------------------------------------------------------------------------

def parse_manuscript_pages(ms_pages: str) -> list[int]:
    """Parse 'manuscript_pages' field into list of page numbers.

    Formats:
      "42,24 - 43,21"  → [42, 43]
      "(9,11 - 16,31)" → [9, 10, 11, 12, 13, 14, 15, 16]
      "28,1 - 30,11"   → [28, 29, 30]
    """
    if not ms_pages:
        return []

    # Strip parentheses
    clean = ms_pages.strip("() ")

    # Split on " - "
    parts = clean.split(" - ")
    if len(parts) != 2:
        return []

    try:
        start_page = int(parts[0].split(",")[0].strip())
        end_page = int(parts[1].split(",")[0].strip())
    except (ValueError, IndexError):
        return []

    return list(range(start_page, end_page + 1))


def load_coptic_page(page_num: int) -> str | None:
    """Load pass2 Coptic transcription for a page number."""
    path = COPTIC_DIR / f"keph_p{page_num:03d}_pass2.txt"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def get_chapter_coptic(cleaned_chapter: dict) -> str:
    """Assemble full Coptic text for a chapter from its manuscript pages."""
    ms_pages = cleaned_chapter.get("manuscript_pages", "")
    pages = parse_manuscript_pages(ms_pages)
    if not pages:
        return ""

    parts = []
    for p in pages:
        text = load_coptic_page(p)
        if text:
            parts.append(text)

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Coptic feature extraction
# ---------------------------------------------------------------------------

def tokenize_coptic(text: str) -> list[str]:
    """Simple whitespace tokenizer for Coptic text.

    Strips line numbers, lacunae markers, page numerals, and headers.
    Returns lowercased word-like tokens.
    """
    # Remove line numbers at start of lines
    text = re.sub(r"^\d+\s+", "", text, flags=re.MULTILINE)
    # Remove lacunae markers
    text = re.sub(r"\[[\.\s]*\]", "", text)
    # Remove standalone dots (illegible text)
    text = re.sub(r"\.\s+\.\s+\.\s*", " ", text)
    # Remove page headers/numerals (standalone short Coptic numerals)
    text = re.sub(r"^[ⲁ-ⳣ]{1,4}̄?\s*$", "", text, flags=re.MULTILINE)
    # Remove "leer" markers
    text = re.sub(r"\bleer\b", "", text, flags=re.IGNORECASE)
    # Remove ⲛ̄ⲕⲉⲫⲁⲗⲁⲓⲟⲛ headers
    text = re.sub(r"ⲛ̄?ⲕⲉⲫⲁⲗⲁⲓⲟⲛ", "", text, flags=re.IGNORECASE)
    # Remove various brackets
    text = re.sub(r"[⟨⟩\[\]()>·<—]", "", text)
    # Remove PAGE BREAK markers
    text = re.sub(r"---\s*PAGE BREAK\s*---", "", text)

    # Tokenize on whitespace
    tokens = text.split()
    # Filter: keep only tokens with Coptic characters
    coptic_re = re.compile(r"[ⲁ-ⳣ]")
    return [t for t in tokens if coptic_re.search(t)]


def count_loanwords(tokens: list[str]) -> dict:
    """Count Greek loanwords by register.

    Returns dict with counts for cosmological, ecclesiastical, and general.
    Also returns the specific words found in each category.
    """
    cosmo_hits: list[str] = []
    eccl_hits: list[str] = []
    general_hits: list[str] = []

    for token in tokens:
        # Normalize: strip common Coptic prefixes/suffixes for matching
        # Check raw token and also stripped versions
        forms = {token}
        # Strip common prefixes
        for prefix in ("ⲡ", "ⲧ", "ⲛ", "ⲛ̄", "ⲡⲉ", "ⲧⲉ", "ⲛⲉ",
                       "ⲟⲩ", "ϩⲉⲛ", "ⲙ̄ⲡ", "ⲛ̄ⲧ", "ⲛ̄ⲛ"):
            if token.startswith(prefix) and len(token) > len(prefix) + 2:
                forms.add(token[len(prefix):])

        for form in forms:
            if form in GREEK_COSMOLOGICAL:
                cosmo_hits.append(form)
                break
            elif form in GREEK_ECCLESIASTICAL:
                eccl_hits.append(form)
                break
            elif form in GREEK_GENERAL:
                general_hits.append(form)
                break

    return {
        "cosmological_count": len(cosmo_hits),
        "ecclesiastical_count": len(eccl_hits),
        "general_count": len(general_hits),
        "total_greek": len(cosmo_hits) + len(eccl_hits) + len(general_hits),
        "cosmological_words": dict(Counter(cosmo_hits)),
        "ecclesiastical_words": dict(Counter(eccl_hits)),
    }


def count_formulaic_patterns(text: str) -> dict:
    """Count occurrences of formulaic Coptic patterns."""
    result = {
        "dialogue_openings": 0,
        "disciple_questions": 0,
        "response_formulas": 0,
        "blessing_closures": 0,
        "exhortation_markers": 0,
        "total_formulaic": 0,
        "details": [],
    }

    for pat in DIALOGUE_OPENING_PATTERNS:
        for m in pat.finditer(text):
            result["dialogue_openings"] += 1
            result["details"].append({"type": "dialogue_opening", "match": m.group()})

    for pat in QUESTION_PATTERNS:
        for m in pat.finditer(text):
            result["disciple_questions"] += 1
            result["details"].append({"type": "disciple_question", "match": m.group()})

    for pat in RESPONSE_PATTERNS:
        for m in pat.finditer(text):
            result["response_formulas"] += 1
            result["details"].append({"type": "response_formula", "match": m.group()})

    for pat in BLESSING_PATTERNS:
        for m in pat.finditer(text):
            result["blessing_closures"] += 1
            result["details"].append({"type": "blessing_closure", "match": m.group()})

    for pat in EXHORTATION_PATTERNS:
        for m in pat.finditer(text):
            result["exhortation_markers"] += 1
            result["details"].append({"type": "exhortation", "match": m.group()})

    result["total_formulaic"] = (
        result["dialogue_openings"]
        + result["disciple_questions"]
        + result["response_formulas"]
        + result["blessing_closures"]
        + result["exhortation_markers"]
    )
    return result


def measure_dialect(text: str) -> dict:
    """Measure Sub-Achmimic vs. Sahidic dialect markers.

    The Kephalaia manuscript is Sub-Achmimic. Consistency of dialect
    markers across chapters can indicate interpolation or later editing.
    """
    subachmimic_count = 0
    sahidic_count = 0
    sa_forms: list[str] = []
    s_forms: list[str] = []

    for sa_form, s_form in SUBACHMIMIC_MARKERS.items():
        sa_matches = len(re.findall(re.escape(sa_form), text))
        s_matches = len(re.findall(re.escape(s_form), text))
        if sa_matches:
            subachmimic_count += sa_matches
            sa_forms.append(f"{sa_form}×{sa_matches}")
        if s_matches:
            sahidic_count += s_matches
            s_forms.append(f"{s_form}×{s_matches}")

    total = subachmimic_count + sahidic_count
    ratio = round(subachmimic_count / total, 3) if total > 0 else None

    return {
        "subachmimic_count": subachmimic_count,
        "sahidic_count": sahidic_count,
        "total_dialect_markers": total,
        "subachmimic_ratio": ratio,  # 1.0 = pure Sub-Achmimic, 0.0 = pure Sahidic
        "subachmimic_forms": sa_forms,
        "sahidic_intrusions": s_forms,
    }


def measure_lacunae(text: str) -> dict:
    """Measure density of lacunae and illegible text.

    Counts:
      - Bracketed restorations: [text]
      - Dot sequences: . . . . .
      - Empty brackets: [ ]
      - 'leer' markers (blank space in manuscript)
    """
    # Count lines total
    lines = [ln for ln in text.split("\n") if ln.strip()]
    total_lines = len(lines)

    # Dot sequences (illegible text)
    dot_sequences = len(re.findall(r"\.(?:\s+\.){2,}", text))

    # Bracketed restorations
    brackets = len(re.findall(r"\[[^\]]+\]", text))

    # Empty/near-empty brackets
    empty_brackets = len(re.findall(r"\[\s*\.\s*(?:\.\s*)*\]", text))

    # Leer markers
    leer_count = len(re.findall(r"\bleer\b", text, re.IGNORECASE))

    # Lines that are predominantly damaged (more dots than text)
    damaged_lines = 0
    for ln in lines:
        stripped = ln.strip()
        if not stripped:
            continue
        dot_chars = stripped.count(".")
        total_chars = len(stripped)
        if total_chars > 0 and dot_chars / total_chars > 0.4:
            damaged_lines += 1

    lacunae_density = round(damaged_lines / total_lines, 3) if total_lines > 0 else 0.0

    return {
        "total_lines": total_lines,
        "damaged_lines": damaged_lines,
        "lacunae_density": lacunae_density,
        "dot_sequences": dot_sequences,
        "bracketed_restorations": brackets,
        "empty_brackets": empty_brackets,
        "leer_markers": leer_count,
    }


# ---------------------------------------------------------------------------
# English-side classification loading
# ---------------------------------------------------------------------------

def load_english_classifications(ch_num: int) -> dict | None:
    """Load classification data from core chapter JSON."""
    path = CORE_DIR / f"ch_{ch_num:03d}.json"
    if not path.exists():
        return None

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # Extract classification distribution
    paras = data.get("paragraphs", [])
    class_counts: Counter = Counter()
    for p in paras:
        cls = p.get("classification", "unknown")
        class_counts[cls] += 1

    return {
        "chapter_number": data.get("chapter_number", ch_num),
        "chapter_title": data.get("chapter_title", ""),
        "total_paragraphs": data.get("total_paragraphs", len(paras)),
        "core_paragraphs": data.get("core_paragraphs", 0),
        "core_percentage": data.get("core_percentage", 0),
        "chapter_note": data.get("chapter_note", ""),
        "classification_distribution": dict(class_counts),
    }


# ---------------------------------------------------------------------------
# Chapter analysis — combines all features
# ---------------------------------------------------------------------------

def analyze_chapter(ch_num: int) -> dict | None:
    """Run full Coptic analysis for a single chapter.

    Returns None if the chapter doesn't exist or has no Coptic coverage.
    """
    # Load cleaned chapter for manuscript pages
    cleaned_path = CLEANED_DIR / f"ch_{ch_num:03d}.json"
    if not cleaned_path.exists():
        return None

    with open(cleaned_path, encoding="utf-8") as f:
        cleaned = json.load(f)

    # Get Coptic text
    coptic_text = get_chapter_coptic(cleaned)
    if not coptic_text.strip():
        return None

    # Get English classifications
    english = load_english_classifications(ch_num)

    # Tokenize
    tokens = tokenize_coptic(coptic_text)
    total_tokens = len(tokens)

    if total_tokens == 0:
        return None

    # Run analyses
    loanwords = count_loanwords(tokens)
    formulaic = count_formulaic_patterns(coptic_text)
    dialect = measure_dialect(coptic_text)
    lacunae = measure_lacunae(coptic_text)

    # Compute derived metrics
    greek_density = round(loanwords["total_greek"] / total_tokens * 100, 2) if total_tokens else 0.0
    cosmo_density = round(loanwords["cosmological_count"] / total_tokens * 100, 2) if total_tokens else 0.0
    eccl_density = round(loanwords["ecclesiastical_count"] / total_tokens * 100, 2) if total_tokens else 0.0

    # Register ratio: cosmological vs. ecclesiastical Greek
    cosmo_total = loanwords["cosmological_count"]
    eccl_total = loanwords["ecclesiastical_count"]
    register_total = cosmo_total + eccl_total
    cosmo_ratio = round(cosmo_total / register_total, 3) if register_total > 0 else None

    # Formulaic density (per 100 tokens)
    formulaic_density = round(formulaic["total_formulaic"] / total_tokens * 100, 2) if total_tokens else 0.0

    # Concordance assessment
    concordance = assess_concordance(
        english=english,
        greek_density=greek_density,
        cosmo_ratio=cosmo_ratio,
        eccl_density=eccl_density,
        formulaic=formulaic,
        dialect=dialect,
        lacunae=lacunae,
    )

    return {
        "chapter_number": ch_num,
        "manuscript_pages": cleaned.get("manuscript_pages", ""),
        "coptic_tokens": total_tokens,

        # Greek loanword analysis
        "greek_loanwords": {
            "total_density_pct": greek_density,
            "cosmological_density_pct": cosmo_density,
            "ecclesiastical_density_pct": eccl_density,
            "cosmological_ratio": cosmo_ratio,  # cosmo / (cosmo + eccl)
            **loanwords,
        },

        # Formulaic patterns
        "formulaic_patterns": {
            "density_per_100_tokens": formulaic_density,
            **formulaic,
        },

        # Dialect analysis
        "dialect": dialect,

        # Lacunae density
        "lacunae": lacunae,

        # English-side classification (for comparison)
        "english_classification": english,

        # Concordance assessment
        "concordance": concordance,
    }


def assess_concordance(
    english: dict | None,
    greek_density: float,
    cosmo_ratio: float | None,
    eccl_density: float,
    formulaic: dict,
    dialect: dict,
    lacunae: dict,
) -> dict:
    """Assess concordance between Coptic features and English classification.

    Returns indicators of agreement, disagreement, and new findings.
    """
    if not english:
        return {"status": "no_english_data"}

    core_pct = english.get("core_percentage", 0)
    class_dist = english.get("classification_distribution", {})
    signals: list[str] = []
    flags: list[str] = []

    # 1. Cosmological ratio vs. substrate percentage
    if cosmo_ratio is not None:
        if core_pct >= 70 and cosmo_ratio >= 0.5:
            signals.append(
                f"CONCORDANT: High substrate ({core_pct}%) with high cosmological "
                f"Greek ratio ({cosmo_ratio:.2f})"
            )
        elif core_pct <= 30 and cosmo_ratio <= 0.3:
            signals.append(
                f"CONCORDANT: Low substrate ({core_pct}%) with low cosmological "
                f"Greek ratio ({cosmo_ratio:.2f})"
            )
        elif core_pct >= 70 and cosmo_ratio < 0.3:
            flags.append(
                f"DISCORDANT: High substrate ({core_pct}%) but low cosmological "
                f"Greek ({cosmo_ratio:.2f}) — Coptic suggests more institutional "
                f"register than English classification indicates"
            )
        elif core_pct <= 30 and cosmo_ratio > 0.7:
            flags.append(
                f"DISCORDANT: Low substrate ({core_pct}%) but high cosmological "
                f"Greek ({cosmo_ratio:.2f}) — Coptic suggests more substrate "
                f"content than English classification captured"
            )

    # 2. Ecclesiastical density in chapters classified as pure substrate
    if core_pct >= 90 and eccl_density > 2.0:
        flags.append(
            f"NOTABLE: Chapter classified as {core_pct}% substrate but "
            f"ecclesiastical Greek density is {eccl_density:.1f}% — "
            f"possible institutional vocabulary not visible in translation"
        )

    # 3. Dialogue frame detection: Coptic formulas vs. English classification
    dialogue_count = class_dist.get("dialogue_frame", 0)
    coptic_dialogue = formulaic.get("dialogue_openings", 0)
    if coptic_dialogue > 0 and dialogue_count == 0:
        flags.append(
            f"DISCORDANT: Coptic has {coptic_dialogue} dialogue opening(s) "
            f"but English classified 0 paragraphs as dialogue_frame"
        )
    elif dialogue_count > 0 and coptic_dialogue > 0:
        signals.append(
            f"CONCORDANT: English detected {dialogue_count} dialogue_frame "
            f"paragraph(s), Coptic confirms {coptic_dialogue} dialogue opening(s)"
        )

    # 4. Dialect consistency
    sa_ratio = dialect.get("subachmimic_ratio")
    if sa_ratio is not None and sa_ratio < 0.5:
        flags.append(
            f"DIALECT FLAG: Sub-Achmimic ratio is only {sa_ratio:.2f} — "
            f"substantial Sahidic intrusion suggests later editorial hand"
        )
    elif sa_ratio is not None and sa_ratio >= 0.8:
        signals.append(
            f"DIALECT CONSISTENT: Sub-Achmimic ratio {sa_ratio:.2f} — "
            f"consistent with the original manuscript dialect"
        )

    # 5. Lacunae as age indicator
    lac_density = lacunae.get("lacunae_density", 0)
    if lac_density > 0.3:
        signals.append(
            f"LACUNAE: High damage density ({lac_density:.2f}) — "
            f"may indicate older or more-handled portion of manuscript"
        )

    # 6. Blessing/exhortation in Coptic vs. English classification
    exhort_count = class_dist.get("exhortation", 0)
    coptic_blessings = formulaic.get("blessing_closures", 0)
    coptic_exhort = formulaic.get("exhortation_markers", 0)
    if (coptic_blessings + coptic_exhort) > 0 and exhort_count == 0:
        flags.append(
            f"NOTABLE: Coptic has {coptic_blessings} blessing formula(s) and "
            f"{coptic_exhort} exhortation marker(s), but English classified "
            f"0 paragraphs as exhortation"
        )

    return {
        "concordance_signals": signals,
        "discordance_flags": flags,
        "signal_count": len(signals),
        "flag_count": len(flags),
    }


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------

def build_summary(all_results: list[dict]) -> dict:
    """Build corpus-wide summary from all chapter analyses."""
    n = len(all_results)
    if n == 0:
        return {"error": "No chapters analyzed"}

    # Aggregate metrics
    total_tokens = sum(r["coptic_tokens"] for r in all_results)
    total_cosmo = sum(r["greek_loanwords"]["cosmological_count"] for r in all_results)
    total_eccl = sum(r["greek_loanwords"]["ecclesiastical_count"] for r in all_results)
    total_formulaic = sum(r["formulaic_patterns"]["total_formulaic"] for r in all_results)

    # Concordance tallies
    total_signals = sum(r["concordance"]["signal_count"] for r in all_results
                        if "signal_count" in r.get("concordance", {}))
    total_flags = sum(r["concordance"]["flag_count"] for r in all_results
                      if "flag_count" in r.get("concordance", {}))

    # Greek density by chapter zone
    first_half = [r for r in all_results if r["chapter_number"] <= 74]
    second_half = [r for r in all_results if r["chapter_number"] > 74]

    def avg_density(chapters: list[dict], key: str) -> float:
        if not chapters:
            return 0.0
        vals = [r["greek_loanwords"][key] for r in chapters]
        return round(sum(vals) / len(vals), 3)

    # Dialect consistency across corpus
    dialect_ratios = [
        r["dialect"]["subachmimic_ratio"]
        for r in all_results
        if r["dialect"]["subachmimic_ratio"] is not None
    ]
    avg_dialect = round(sum(dialect_ratios) / len(dialect_ratios), 3) if dialect_ratios else None

    # Collect all discordance flags
    all_flags = []
    for r in all_results:
        conc = r.get("concordance", {})
        for flag in conc.get("discordance_flags", []):
            all_flags.append({
                "chapter": r["chapter_number"],
                "flag": flag,
            })

    # Chapters with highest ecclesiastical Greek
    eccl_ranked = sorted(all_results,
                         key=lambda r: r["greek_loanwords"]["ecclesiastical_density_pct"],
                         reverse=True)[:15]

    # Chapters with highest cosmological Greek
    cosmo_ranked = sorted(all_results,
                          key=lambda r: r["greek_loanwords"]["cosmological_density_pct"],
                          reverse=True)[:15]

    return {
        "corpus_overview": {
            "chapters_analyzed": n,
            "total_coptic_tokens": total_tokens,
            "total_greek_cosmological": total_cosmo,
            "total_greek_ecclesiastical": total_eccl,
            "total_formulaic_patterns": total_formulaic,
            "concordance_signals": total_signals,
            "discordance_flags": total_flags,
            "average_dialect_ratio": avg_dialect,
        },
        "zone_comparison": {
            "chapters_1_74": {
                "count": len(first_half),
                "avg_cosmo_density": avg_density(first_half, "cosmological_density_pct"),
                "avg_eccl_density": avg_density(first_half, "ecclesiastical_density_pct"),
            },
            "chapters_75_122": {
                "count": len(second_half),
                "avg_cosmo_density": avg_density(second_half, "cosmological_density_pct"),
                "avg_eccl_density": avg_density(second_half, "ecclesiastical_density_pct"),
            },
        },
        "highest_ecclesiastical_greek": [
            {
                "chapter": r["chapter_number"],
                "eccl_density": r["greek_loanwords"]["ecclesiastical_density_pct"],
                "core_percentage": (r.get("english_classification") or {}).get("core_percentage", "?"),
            }
            for r in eccl_ranked
        ],
        "highest_cosmological_greek": [
            {
                "chapter": r["chapter_number"],
                "cosmo_density": r["greek_loanwords"]["cosmological_density_pct"],
                "core_percentage": (r.get("english_classification") or {}).get("core_percentage", "?"),
            }
            for r in cosmo_ranked
        ],
        "all_discordance_flags": all_flags,
    }


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def save_chapter_analysis(analysis: dict) -> None:
    ch_num = analysis["chapter_number"]
    path = OUTPUT_DIR / f"ch_{ch_num:03d}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)


def save_summary(summary: dict) -> None:
    path = OUTPUT_DIR.parent / "coptic_summary.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Coptic-based validation of English-derived classifications"
    )
    parser.add_argument("--project", default="kephalaia",
                        help="Project name (default: kephalaia)")
    parser.add_argument("--chapter", type=int,
                        help="Analyze a single chapter")
    parser.add_argument("--range",
                        help="Analyze a range, e.g. '0-50'")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be analyzed without running")
    parser.add_argument("--overwrite", action="store_true",
                        help="Overwrite existing analysis files")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_paths(args.project)

    # Determine chapters to analyze
    if args.chapter is not None:
        chapters = [args.chapter]
    elif args.range:
        lo, hi = args.range.split("-")
        chapters = list(range(int(lo), int(hi) + 1))
    else:
        # All chapters
        chapter_files = sorted(CLEANED_DIR.glob("ch_*.json"))
        chapters = []
        for f in chapter_files:
            m = re.search(r"ch_(\d+)\.json", f.name)
            if m:
                chapters.append(int(m.group(1)))

    if args.dry_run:
        print(f"\nDry run — would analyze {len(chapters)} chapter(s):")
        for ch in chapters:
            cleaned_path = CLEANED_DIR / f"ch_{ch:03d}.json"
            if cleaned_path.exists():
                with open(cleaned_path, encoding="utf-8") as f:
                    data = json.load(f)
                ms = data.get("manuscript_pages", "?")
                pages = parse_manuscript_pages(ms)
                available = sum(1 for p in pages if (COPTIC_DIR / f"keph_p{p:03d}_pass2.txt").exists())
                print(f"  ch_{ch:03d}: ms pages {ms} → {len(pages)} pages, {available} with Coptic")
        return

    # Skip existing unless --overwrite
    if not args.overwrite:
        to_analyze = []
        for ch in chapters:
            if not (OUTPUT_DIR / f"ch_{ch:03d}.json").exists():
                to_analyze.append(ch)
            else:
                pass  # silently skip
        skipped = len(chapters) - len(to_analyze)
        if skipped:
            print(f"\nSkipping {skipped} already-analyzed chapter(s)")
        chapters = to_analyze

    print(f"\nAnalyzing {len(chapters)} chapter(s)...")

    results = []
    for ch in chapters:
        result = analyze_chapter(ch)
        if result is None:
            print(f"  ch_{ch:03d}: SKIPPED (no data)")
            continue

        save_chapter_analysis(result)

        # Brief summary
        gl = result["greek_loanwords"]
        conc = result["concordance"]
        flags = conc.get("flag_count", 0)
        flag_str = f" ⚠ {flags} flag(s)" if flags else ""
        print(
            f"  ch_{ch:03d}: {result['coptic_tokens']} tokens, "
            f"Greek {gl['total_density_pct']:.1f}% "
            f"(cosmo {gl['cosmological_density_pct']:.1f}% / "
            f"eccl {gl['ecclesiastical_density_pct']:.1f}%)"
            f"{flag_str}"
        )
        results.append(result)

    # Build and save corpus summary
    if len(results) > 1:
        summary = build_summary(results)
        save_summary(summary)
        print(f"\nSummary: {summary['corpus_overview']['chapters_analyzed']} chapters analyzed")
        print(f"  Concordance signals: {summary['corpus_overview']['concordance_signals']}")
        print(f"  Discordance flags:   {summary['corpus_overview']['discordance_flags']}")
        print(f"  Avg dialect ratio:   {summary['corpus_overview']['average_dialect_ratio']}")
        if summary["all_discordance_flags"]:
            print(f"\nDiscordance flags:")
            for df in summary["all_discordance_flags"]:
                print(f"  Ch {df['chapter']:3d}: {df['flag']}")


if __name__ == "__main__":
    main()
