#!/usr/bin/env python3
"""
Text-critical scoring of v2 translated pages — Coptic-primary analysis.

Pipeline stage: runs AFTER translate_kephalaia_v2.py, BEFORE extract.py.

This script performs automated vocabulary scoring and editorial pattern
detection on each page using the Coptic text directly. No LLM calls —
all analysis is computational NLP on Coptic morphemes.

What it produces (per page):
  - Per-segment layer scores (substrate, editorial, pastoral, overlay)
  - Formulaic pattern detection (frame openings/closings, questions)
  - Greek loanword density as register indicator
  - Structural unit boundaries from break_after data
  - Damage assessment (lacuna density per segment)

Output: output/projects/kephalaia_v2/scores/p_NNN.json

The output is consumed by extract.py, which formats the score data
into the Claude prompt for LLM-driven temporal layer classification.

Usage:
    python scripts/projects/kephalaia_v2/score.py
    python scripts/projects/kephalaia_v2/score.py --page 35
    python scripts/projects/kephalaia_v2/score.py --page 35 96 15 185
    python scripts/projects/kephalaia_v2/score.py --range 10-50
    python scripts/projects/kephalaia_v2/score.py --dry-run
    python scripts/projects/kephalaia_v2/score.py --overwrite
"""
import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PROJECT_DIR = REPO_ROOT / "output" / "projects" / "kephalaia_v2"
PAGES_DIR = PROJECT_DIR / "pages"
SCORES_DIR = PROJECT_DIR / "scores"


# ---------------------------------------------------------------------------
# Coptic scoring vocabularies
#
# These are the v2 equivalent of the v1 corpus_metadata.json scoring dicts.
# In v1 they were English terms discovered by an LLM from the Gardner
# translation. In v2 they are Coptic morphemes observed directly in the
# manuscript, compiled from the v1 findings and manuscript knowledge.
#
# Each dict maps Coptic string → weight (1-5).
# Matching is case-insensitive and uses substring containment.
# ---------------------------------------------------------------------------

# Layer 1: Cosmological-Correspondential Substrate
# The oldest teaching layer — systematic cosmic mappings, five-element
# nomenclature, emanation hierarchies, body-cosmos correspondences.
SUBSTRATE_MARKERS: dict[str, int] = {
    # Five elements / worlds of Darkness
    "ⲕⲁⲡⲛⲟⲥ": 4,          # smoke (Gk loan: kapnos)
    "ⲕⲱⲍⲧ": 4,             # fire
    "ⲧⲏⲩ": 3,              # wind
    "ⲙⲟⲟⲩ": 3,             # water (generic, needs context)
    "ⲕⲉⲕⲉ": 4,             # darkness
    # Cosmic furniture
    "ⲧⲣⲟⲭⲟⲥ": 5,           # wheel (Gk: trochos)
    "ⲥⲧⲉⲣⲉⲱⲙⲁ": 5,        # firmament (Gk: stereōma)
    "ⲍⲱⲇⲓⲟⲛ": 5,           # zodiac sign
    "ⲡⲗⲓⲗⲟⲩ": 5,           # Pillar (of Glory)
    "ⲱⲙⲟⲫⲟⲣⲟⲥ": 5,        # Omophoros (Atlas-figure)
    "ⲥⲫⲁⲓⲣⲁ": 4,           # sphere
    # Emanation / cosmogonic titles
    "ⲡⲣⲱⲧⲟⲙⲏ": 4,         # protomē (first-image)
    "ⲡⲣⲉⲥⲃⲉⲓⲁ": 4,        # ambassador/embassy (Gk: presbeia)
    "ⲟⲙⲟⲫⲟⲣⲓⲟⲛ": 5,       # omophorion (burden-bearers)
    # Body-cosmos correspondences
    "ⲕⲉⲥ": 4,              # bone
    "ⲙⲁⲥⲧ": 3,             # sinew
    "ⲥⲁⲣⲝ": 3,             # flesh (Gk: sarx)
    "ⲥⲛⲁϥ": 3,             # blood
    # Five faculties / members of soul
    "ⲡⲛⲟⲩⲥ": 4,            # mind (Gk: nous)
    "ⲉⲛⲛⲟⲓⲁ": 4,           # thought (Gk: ennoia)
    "ⲫⲣⲟⲛⲏⲥⲓⲥ": 4,        # reflection/insight (Gk: phronēsis)
    "ⲉⲛⲑⲩⲙⲏⲥⲓⲥ": 4,       # consideration (Gk: enthymēsis)
    # Light cosmology
    "ⲟⲩⲁⲓⲛⲉ": 4,           # light (Lycopolitan)
    "ⲡⲁⲣⲁⲕⲗⲏⲧⲟⲥ": 4,      # Paraclete
    "ⲁⲓⲱⲛ": 3,             # aeon
    # Cosmic process vocabulary
    "ⲥⲱⲧϥ": 4,             # refine/purify
    "ⲃⲱⲗ": 3,              # release/dissolve
    "ⲙⲟⲩⲛⲕ": 3,            # mold/form
    "ⲕⲱⲧ": 3,              # build
    # Five Sons nomenclature
    "ⲡⲉⲛⲧⲁⲥ": 4,           # pentad/five
}

# Layer 2: Editorial Frame (Manichaean compilation)
# The editorial apparatus added by the Kephalaia compiler:
# question-answer frames, chapter markers, doxologies, attributions.
FRAME_MARKERS: dict[str, int] = {
    # Formulaic frames
    "ⲡⲉϫⲉ ⲡⲥⲁⲍ": 5,       # "the Teacher said"
    "ⲡⲉϫⲁⲩ": 4,            # "they said" (disciples asking)
    "ⲕⲉⲫⲁⲗⲁⲓⲟⲛ": 5,       # kephalaion (chapter marker)
    "ⲉⲧⲃⲉ": 3,             # "concerning" (topic marker)
    # Doxological
    "ϫⲉⲕⲁⲥ": 3,            # "in order that" (purposive — common in frames)
    "ⲉⲩⲣⲁϣⲉ": 4,           # "they rejoiced" (closing formula)
    "ⲁⲩϯⲉⲟⲟⲩ": 4,          # "they glorified" (closing formula)
    # Discourse markers
    "ⲟⲛ ⲟⲩⲥⲁⲡ": 4,         # "once again / another time"
    "ⲛ̄ⲕⲉⲥⲁⲡ": 4,           # "another time"
}

# Layer 3: Pastoral/Institutional
# Later additions addressing church practice, ranks, commandments.
PASTORAL_MARKERS: dict[str, int] = {
    # Institutional vocabulary
    "ⲉⲕⲕⲗⲏⲥⲓⲁ": 5,         # church (Gk: ekklēsia)
    "ⲕⲁⲧⲏⲭⲟⲩⲙⲉⲛⲟⲥ": 5,    # catechumen
    "ⲉⲕⲗⲉⲕⲧⲟⲥ": 4,         # elect (Gk: eklektos)
    "ⲉⲛⲧⲟⲗⲏ": 4,           # commandment (Gk: entolē)
    "ⲇⲓⲕⲁⲓⲟⲥⲩⲛⲏ": 4,      # righteousness (Gk: dikaiosynē)
    "ⲛⲏⲥⲧⲉⲓⲁ": 4,          # fasting (Gk: nēsteia)
    "ⲡⲣⲟⲥⲉⲩⲭⲏ": 4,        # prayer (Gk: proseuchē)
    "ⲉⲗⲉⲏⲙⲟⲥⲩⲛⲏ": 4,      # alms (Gk: eleēmosynē)
    # Church hierarchy
    "ⲁⲡⲟⲥⲧⲟⲗⲟⲥ": 3,       # apostle (also substrate in some contexts)
    "ⲉⲡⲓⲥⲕⲟⲡⲟⲥ": 5,       # bishop
    "ⲡⲣⲉⲥⲃⲩⲧⲉⲣⲟⲥ": 5,     # elder/presbyter
    "ⲇⲓⲁⲕⲟⲛⲟⲥ": 5,        # deacon
}

# Layer 4: Christian Overlay
# Later Christianizing additions referencing NT, Jesus as savior, etc.
OVERLAY_MARKERS: dict[str, int] = {
    "ⲓⲏⲥⲟⲩⲥ": 3,           # Jesus (lower weight — genuinely Manichaean too)
    "ⲥⲧⲁⲩⲣⲟⲥ": 5,          # cross (Gk: stauros — Christian specific)
    "ⲃⲁⲡⲧⲓⲥⲙⲁ": 5,         # baptism
    "ⲉⲩⲁⲅⲅⲉⲗⲓⲟⲛ": 3,       # gospel (also Manichaean)
}

SCORING_DICTS: dict[str, dict[str, int]] = {
    "substrate": SUBSTRATE_MARKERS,
    "frame": FRAME_MARKERS,
    "pastoral": PASTORAL_MARKERS,
    "overlay": OVERLAY_MARKERS,
}


# ---------------------------------------------------------------------------
# Greek loanword detection
#
# High Greek density = likely editorial/pastoral layer (institutional vocab).
# Low Greek density in cosmological context = likely substrate.
# This is a heuristic — the substrate ALSO uses Greek loans (nous, ennoia)
# but they're technical cosmological terms, not institutional terms.
# ---------------------------------------------------------------------------

# Common Greek suffixes/patterns visible in Coptic script
_GREEK_SUFFIX_RE = re.compile(
    r"(?:"
    r"ⲟⲥ|ⲟⲛ|ⲓⲟⲛ|ⲓⲁ|ⲉⲓⲁ|ⲥⲓⲥ|ⲙⲁ|ⲧⲏⲥ|ⲧⲏⲣ|"
    r"ⲉⲩⲉ|ⲉⲩⲥⲓⲥ"
    r")$"
)

# Greek-origin words we know about (broader detection)
_KNOWN_GREEK_LOANS = {
    "ⲙⲩⲥⲧⲏⲣⲓⲟⲛ", "ⲕⲟⲥⲙⲟⲥ", "ⲅⲉⲛⲉⲁ", "ⲯⲩⲭⲏ", "ⲥⲱⲙⲁ",
    "ⲡⲛⲉⲩⲙⲁ", "ⲗⲟⲅⲟⲥ", "ⲥⲟⲫⲓⲁ", "ⲉⲝⲟⲩⲥⲓⲁ", "ⲁⲣⲭⲱⲛ",
    "ⲡⲁⲣⲁⲕⲗⲏⲧⲟⲥ", "ⲡⲁⲣⲁⲇⲉⲓⲥⲟⲥ", "ⲑⲁⲗⲁⲥⲥⲁ", "ⲡⲟⲗⲓⲥ",
    "ⲭⲱⲣⲁ", "ⲉⲕⲕⲗⲏⲥⲓⲁ", "ⲁⲡⲟⲥⲧⲟⲗⲟⲥ", "ⲕⲉⲫⲁⲗⲁⲓⲟⲛ",
    "ⲇⲓⲕⲁⲓⲟⲥⲩⲛⲏ", "ⲡⲁⲣⲍⲏⲥⲓⲁ", "ⲡⲟⲗⲉⲙⲟⲥ", "ⲥⲧⲟⲓⲭⲉⲓⲟⲛ",
    "ⲟⲩⲥⲓⲁ", "ⲫⲩⲥⲓⲥ", "ⲙⲉⲗⲟⲥ", "ⲡⲣⲟⲥⲱⲡⲟⲛ",
}


def count_greek_loans(coptic_text: str) -> int:
    """Count Greek loanwords in a Coptic text segment."""
    if not coptic_text:
        return 0
    text_lower = coptic_text.lower()
    count = 0
    for loan in _KNOWN_GREEK_LOANS:
        if loan in text_lower:
            count += text_lower.count(loan)
    return count


# ---------------------------------------------------------------------------
# Formulaic pattern detection (Coptic-level)
# ---------------------------------------------------------------------------

# Frame opening patterns
_OPENING_PATTERNS = [
    re.compile(r"ⲡⲉϫⲉ\s*ⲡⲥⲁⲍ", re.IGNORECASE),           # "the Teacher said"
    re.compile(r"ⲟⲛ\s*ⲟⲩⲥⲁⲡ", re.IGNORECASE),              # "once again"
    re.compile(r"ⲛ̄ⲕⲉⲥⲁⲡ", re.IGNORECASE),                   # "another time"
    re.compile(r"ⲡⲉϫⲁⲩ\s*ϫⲉ", re.IGNORECASE),              # "they said:" (question)
]

# Frame closing patterns
_CLOSING_PATTERNS = [
    re.compile(r"ⲉⲩⲣⲁϣⲉ", re.IGNORECASE),                   # "they rejoiced"
    re.compile(r"ⲁⲩϯⲉⲟⲟⲩ", re.IGNORECASE),                  # "they glorified"
    re.compile(r"ⲛⲧⲉⲣⲟⲩⲥⲱⲧⲙ", re.IGNORECASE),              # "when they heard"
]

# Question/petition patterns
_QUESTION_PATTERNS = [
    re.compile(r"ⲧⲛ̄ⲥⲟⲡⲥ", re.IGNORECASE),                   # "we beseech"
    re.compile(r"ⲧⲛ̄ⲡⲁⲣⲁⲕⲁⲗⲉⲓ", re.IGNORECASE),             # "we entreat"
    re.compile(r"ⲧⲁⲙⲁⲛ\s*ⲉⲧⲃⲉ", re.IGNORECASE),            # "tell us concerning"
]


# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------

def score_coptic_text(text: str, markers: dict[str, int]) -> float:
    """Score Coptic text against a marker set.

    Returns normalized score per 100 Coptic words (whitespace-split tokens).
    """
    if not text:
        return 0.0
    text_lower = text.lower()
    total = 0
    for marker, weight in markers.items():
        marker_lower = marker.lower()
        count = text_lower.count(marker_lower)
        if count > 0:
            total += weight * count
    # Normalize by approximate word count
    words = max(len(text.split()), 1)
    return round((total / words) * 100, 2)


def score_segment(segment: dict) -> dict:
    """Score a single line segment across all layers.

    Args:
        segment: A line entry from the page JSON {i, n, coptic, english, ...}

    Returns:
        Dict with layer scores, greek loan count, and pattern flags.
    """
    coptic = segment.get("coptic") or ""
    english = segment.get("english") or ""

    scores = {}
    for layer_id, markers in SCORING_DICTS.items():
        scores[layer_id] = score_coptic_text(coptic, markers)

    greek_loans = count_greek_loans(coptic)

    # Pattern detection
    has_opening = any(p.search(coptic) for p in _OPENING_PATTERNS)
    has_closing = any(p.search(coptic) for p in _CLOSING_PATTERNS)
    has_question = any(p.search(coptic) for p in _QUESTION_PATTERNS)

    return {
        "i": segment["i"],
        "n": segment["n"],
        "scores": scores,
        "greek_loans": greek_loans,
        "patterns": {
            "frame_opening": has_opening,
            "frame_closing": has_closing,
            "question_formula": has_question,
        },
        "break_after": segment.get("break_after", False),
        "is_null": segment.get("coptic") is None,
    }


# ---------------------------------------------------------------------------
# Damage / lacuna assessment
# ---------------------------------------------------------------------------

def assess_damage(page_data: dict) -> dict:
    """Compute page-level damage statistics from apparatus.

    Returns:
        Dict with total_lacunae, total_restorations, total_est_chars_lost,
        null_lines count, and damage_ratio (fraction of segments with gaps).
    """
    apparatus = page_data.get("apparatus", [])
    lines = page_data.get("lines", [])

    n_lacunae = sum(1 for a in apparatus if a["type"] == "lacuna")
    n_restorations = sum(1 for a in apparatus if a["type"] == "restoration")
    est_chars_lost = sum(
        a.get("est_chars", 0) for a in apparatus if a["type"] == "lacuna"
    )
    null_lines = sum(1 for l in lines if l.get("coptic") is None)

    # Which segments have gaps?
    segments_with_gaps = set()
    for a in apparatus:
        seg = a.get("segment")
        if isinstance(seg, int):
            segments_with_gaps.add(seg)

    damage_ratio = (
        round(len(segments_with_gaps) / len(lines), 3)
        if lines else 0.0
    )

    return {
        "lacunae": n_lacunae,
        "restorations": n_restorations,
        "est_chars_lost": est_chars_lost,
        "null_lines": null_lines,
        "segments_with_gaps": len(segments_with_gaps),
        "total_segments": len(lines),
        "damage_ratio": damage_ratio,
    }


# ---------------------------------------------------------------------------
# Structural unit detection
# ---------------------------------------------------------------------------

def detect_structural_units(segments: list[dict]) -> list[dict]:
    """Group segments into structural units based on break_after markers.

    Returns a list of units, each with start_i, end_i, and segment count.
    """
    units = []
    current_start = 0

    for seg in segments:
        if seg.get("break_after", False):
            units.append({
                "start_i": current_start,
                "end_i": seg["i"],
                "segments": seg["i"] - current_start + 1,
            })
            current_start = seg["i"] + 1

    # Final unit (from last break_after to end)
    if segments and current_start <= segments[-1]["i"]:
        units.append({
            "start_i": current_start,
            "end_i": segments[-1]["i"],
            "segments": segments[-1]["i"] - current_start + 1,
        })

    return units


# ---------------------------------------------------------------------------
# Per-page analysis — combines all scoring
# ---------------------------------------------------------------------------

def analyze_page(page_data: dict) -> dict:
    """Run text-critical scoring on a single page.

    Returns a dict with page number, per-segment scores, structural units,
    damage assessment, and page-level features.
    """
    page_num = page_data.get("page", 0)
    lines = page_data.get("lines", [])

    # Score each segment
    segment_scores = [score_segment(seg) for seg in lines]

    # Structural units from break_after
    structural_units = detect_structural_units(lines)

    # Page-level damage assessment
    damage = assess_damage(page_data)

    # Page-level aggregate scores (weighted by non-null segments)
    non_null = [s for s in segment_scores if not s["is_null"]]
    page_scores = {}
    if non_null:
        for layer_id in SCORING_DICTS:
            layer_values = [s["scores"].get(layer_id, 0) for s in non_null]
            page_scores[layer_id] = round(
                sum(layer_values) / len(layer_values), 2
            )
    else:
        page_scores = {lid: 0.0 for lid in SCORING_DICTS}

    # Page-level pattern summary
    has_frame_opening = any(
        s["patterns"]["frame_opening"] for s in segment_scores
    )
    has_frame_closing = any(
        s["patterns"]["frame_closing"] for s in segment_scores
    )
    total_greek = sum(s["greek_loans"] for s in segment_scores)

    return {
        "page": page_num,
        "total_segments": len(lines),
        "structural_units": structural_units,
        "damage": damage,
        "page_scores": page_scores,
        "page_features": {
            "has_frame_opening": has_frame_opening,
            "has_frame_closing": has_frame_closing,
            "total_greek_loans": total_greek,
            "greek_density": round(
                total_greek / max(len(non_null), 1), 2
            ),
        },
        "segments": segment_scores,
    }


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def load_page(page_num: int) -> dict | None:
    """Load a translated page JSON."""
    path = PAGES_DIR / f"p_{page_num:03d}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_score(analysis: dict) -> None:
    """Save per-page score result to JSON."""
    SCORES_DIR.mkdir(parents=True, exist_ok=True)
    page_num = analysis["page"]
    path = SCORES_DIR / f"p_{page_num:03d}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)


def is_scored(page_num: int) -> bool:
    """Check whether score output exists for a page."""
    return (SCORES_DIR / f"p_{page_num:03d}.json").exists()


def list_available_pages() -> list[int]:
    """List all page numbers with translation output."""
    pages = []
    for path in sorted(PAGES_DIR.glob("p_*.json")):
        m = re.match(r"p_(\d+)\.json", path.name)
        if m:
            pages.append(int(m.group(1)))
    return pages


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Text-critical scoring: Coptic vocabulary analysis and "
            "editorial pattern detection (no LLM)"
        )
    )
    parser.add_argument(
        "--page", "-p", type=int, nargs="+", default=None,
        help="Page number(s) to score",
    )
    parser.add_argument("--range", "-r", type=str, default=None)
    parser.add_argument("--limit", "-l", type=int, default=None)
    parser.add_argument("--dry-run", "-n", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("Project: Kephalaia v2 — Text-Critical Scoring")
    print(f"  Input:  {PAGES_DIR}")
    print(f"  Output: {SCORES_DIR}")
    print(
        f"  Scoring layers: "
        f"{', '.join(SCORING_DICTS.keys())} "
        f"({sum(len(v) for v in SCORING_DICTS.values())} total markers)"
    )

    all_pages = list_available_pages()
    if not all_pages:
        print(f"\nERROR: No translated pages in {PAGES_DIR}")
        sys.exit(1)
    print(f"\nFound {len(all_pages)} translated pages (p.{all_pages[0]}-p.{all_pages[-1]})")

    # Determine which to process
    if args.page is not None:
        requested = set(args.page)
        pages = [p for p in all_pages if p in requested]
        missing = requested - set(pages)
        if missing:
            print(f"ERROR: Pages not found: {sorted(missing)}")
            sys.exit(1)
    elif args.range:
        m = re.match(r"(\d+)-(\d+)", args.range)
        if not m:
            print("ERROR: Invalid range. Use '10-50'")
            sys.exit(1)
        start, end = int(m.group(1)), int(m.group(2))
        pages = [p for p in all_pages if start <= p <= end]
    else:
        pages = all_pages

    if args.limit:
        pages = pages[:args.limit]

    # Skip already processed
    if not args.overwrite:
        to_process = [p for p in pages if not is_scored(p)]
        skipped = len(pages) - len(to_process)
        if skipped > 0:
            print(f"  Skipping {skipped} already-scored (use --overwrite)")
        pages = to_process

    if not pages:
        print("All requested pages already scored.")
        return

    print(f"\nScoring {len(pages)} pages:")
    for p in pages:
        data = load_page(p)
        n_lines = len(data["lines"]) if data else 0
        print(f"  p.{p:3d}  ({n_lines:2d} segments)")

    if args.dry_run:
        print("\n[DRY RUN] No scoring performed.")
        return

    # Process
    SCORES_DIR.mkdir(parents=True, exist_ok=True)
    total_seams = 0
    total_segments = 0

    for i, page_num in enumerate(pages, 1):
        data = load_page(page_num)
        if data is None:
            print(f"  p.{page_num}: SKIPPED (file not found)")
            continue

        n_lines = len(data.get("lines", []))
        print(
            f"[{i}/{len(pages)}] p.{page_num} ({n_lines} segments)...",
            end=" ", flush=True,
        )

        analysis = analyze_page(data)
        save_score(analysis)

        n_units = len(analysis["structural_units"])
        damage_pct = round(analysis["damage"]["damage_ratio"] * 100, 1)
        frame_flag = (
            "F" if analysis["page_features"]["has_frame_opening"] else ""
        )
        total_segments += n_lines

        print(
            f"OK — {n_units} units, {damage_pct}% damaged"
            f"{', FRAME' if frame_flag else ''}"
        )

    # Summary
    print(f"\n{'='*50}")
    print("SCORING COMPLETE")
    print(f"  Pages scored:     {len(pages)}")
    print(f"  Total segments:   {total_segments}")
    print(f"  Output: {SCORES_DIR}")


if __name__ == "__main__":
    main()
