#!/usr/bin/env python3
"""
Text-critical scoring of translated pages using LLM-derived metadata.

Pipeline stage 3: runs AFTER stage_2_discover.py, BEFORE stage_4_extract.py.

This script performs automated vocabulary scoring and editorial seam detection
on each page using the corpus metadata produced by stage_2_discover.py.
It does NOT involve any LLM calls — all analysis is computational NLP.

What it produces (per page):
  - Per-segment vocabulary density scores for each temporal layer
  - Editorial seam detection flags (bridge connectives + institutional vocab)
  - Register shift detection across segment boundaries
  - Structural unit boundaries from break_after data
  - Damage assessment (lacuna density per segment)
  - Page-level features: teaching purity, editorial fatigue, Greek loans

Output: output/projects/kephalaia_v2/scores/p_NNN.json

The output is consumed by stage_4_extract.py, which formats the score data
into the Claude prompt for LLM-driven temporal layer classification.

Usage:
    python scripts/projects/kephalaia_v2/stage_3_score.py
    python scripts/projects/kephalaia_v2/stage_3_score.py --page 35
    python scripts/projects/kephalaia_v2/stage_3_score.py --page 35 96 15 185
    python scripts/projects/kephalaia_v2/stage_3_score.py --range 10-50
    python scripts/projects/kephalaia_v2/stage_3_score.py --dry-run
    python scripts/projects/kephalaia_v2/stage_3_score.py --overwrite
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
METADATA_PATH = PROJECT_DIR / "corpus_metadata.json"


# ---------------------------------------------------------------------------
# Metadata loading — ported from v1 stage_3_score.py
# ---------------------------------------------------------------------------

def load_corpus_metadata() -> dict | None:
    """Load corpus metadata produced by stage_2_discover.py."""
    if not METADATA_PATH.exists():
        return None
    with open(METADATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def build_scoring_dicts(metadata: dict) -> dict[str, dict[str, int]]:
    """Build scoring dictionaries from metadata scoring_vocabularies.

    Returns a dict of category_id → {term: weight}.
    Directly consumable by score_text().
    """
    result: dict[str, dict[str, int]] = {}
    for vocab in metadata.get("scoring_vocabularies", []):
        cat_id = vocab["id"]
        result[cat_id] = vocab.get("markers", {})
    return result


def build_bridge_patterns(metadata: dict) -> list[re.Pattern]:
    """Build compiled regex patterns from metadata bridge phrases.

    Each phrase is anchored to segment start with flexible whitespace
    and optional commas, matching case-insensitively.
    """
    seam = metadata.get("seam_detection", {})
    patterns: list[re.Pattern] = []
    for bp in seam.get("bridge_phrases", []):
        phrase = bp["phrase"]
        words = phrase.split()
        parts = []
        for w in words:
            escaped = re.escape(w)
            if escaped.endswith(","):
                escaped = escaped[:-1] + ",?"
            parts.append(escaped)
        regex_str = r"(?i)^" + r"\s+".join(parts)
        try:
            patterns.append(re.compile(regex_str))
        except re.error:
            patterns.append(re.compile(r"(?i)^" + re.escape(phrase)))
    return patterns


def build_institutional_terms(metadata: dict) -> set[str]:
    """Build institutional terms set from metadata seam_detection."""
    seam = metadata.get("seam_detection", {})
    return set(seam.get("institutional_terms", []))


# ---------------------------------------------------------------------------
# Greek loanword detection (kept from original — this is language-level,
# not dependent on LLM discovery)
# ---------------------------------------------------------------------------

_KNOWN_GREEK_LOANS = {
    "mystery", "cosmos", "soul", "body", "spirit", "logos",
    "sophia", "wisdom", "authority", "archon", "paraclete",
    "paradise", "sea", "city", "church", "apostle", "chapter",
    "righteousness", "element", "substance", "nature", "member",
    "person", "sphere", "firmament", "zodiac", "aeon",
}


def count_greek_loans(english_text: str) -> int:
    """Count known Greek-origin theological terms in English text."""
    if not english_text:
        return 0
    text_lower = english_text.lower()
    count = 0
    for loan in _KNOWN_GREEK_LOANS:
        count += text_lower.count(loan)
    return count


# ---------------------------------------------------------------------------
# Formulaic pattern detection (English-level, from v1)
# ---------------------------------------------------------------------------

_OPENING_PATTERNS = [
    re.compile(r"(?i)^once again (?:the )?(?:teacher|enlightener|apostle)"),
    re.compile(r"(?i)^once more (?:the )?(?:teacher|enlightener|apostle)"),
    re.compile(r"(?i)^once again,? at one of the times"),
    re.compile(r"(?i)^once again a disciple"),
    re.compile(r"(?i)^his disciples questioned"),
    re.compile(r"(?i)^the disciple(?:s)? questioned"),
    re.compile(r"(?i)^the teacher (?:said|spoke|speaks)"),
]

_CLOSING_PATTERNS = [
    re.compile(r"(?i)when they heard these things"),
    re.compile(r"(?i)when that disciple had heard"),
    re.compile(r"(?i)they rejoiced"),
    re.compile(r"(?i)they glorified"),
]

_QUESTION_PATTERNS = [
    re.compile(r"(?i)we beseech you"),
    re.compile(r"(?i)we entreat you"),
    re.compile(r"(?i)tell us.*(?:about|concerning)"),
    re.compile(r"(?i)that you may recount"),
]


# ---------------------------------------------------------------------------
# Core scoring function — identical to v1
# ---------------------------------------------------------------------------

def score_text(text: str, markers: dict[str, int]) -> float:
    """Score text against a marker set. Return normalized score per 100 words.

    This is the exact function consumed by the metadata:
    - Lowercases both text and marker keys
    - Counts substring occurrences
    - Multiplies by weight
    - Normalizes per 100 words
    """
    if not text:
        return 0.0
    text_lower = text.lower()
    total = 0
    for marker, weight in markers.items():
        count = text_lower.count(marker.lower())
        if count > 0:
            total += weight * count
    words = max(len(text.split()), 1)
    return round((total / words) * 100, 2)


# ---------------------------------------------------------------------------
# Per-segment scoring
# ---------------------------------------------------------------------------

def score_segment(
    segment: dict,
    scoring_dicts: dict[str, dict[str, int]],
) -> dict:
    """Score a single line segment across all discovered layers.

    Uses the ENGLISH translation for vocabulary scoring (matching the
    language the LLM derived its vocabularies from).
    """
    english = segment.get("english") or ""

    # Score against each layer vocabulary
    scores = {}
    for layer_id, markers in scoring_dicts.items():
        scores[layer_id] = score_text(english, markers)

    # Greek loanword count
    greek_loans = count_greek_loans(english)

    # Pattern detection on English
    has_opening = any(p.search(english) for p in _OPENING_PATTERNS)
    has_closing = any(p.search(english) for p in _CLOSING_PATTERNS)
    has_question = any(p.search(english) for p in _QUESTION_PATTERNS)

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
        "is_null": segment.get("english") is None,
    }


# ---------------------------------------------------------------------------
# Editorial seam detection — ported from v1
# ---------------------------------------------------------------------------

def detect_editorial_seams(
    segments: list[dict],
    segment_scores: list[dict],
    bridge_patterns: list[re.Pattern],
    institutional_terms: set[str],
    scoring_dicts: dict[str, dict[str, int]],
) -> list[dict]:
    """Detect potential editorial seams at segment boundaries.

    Uses metadata-loaded bridge patterns and institutional terms.
    An editorial seam is where an editor extends an existing teaching
    sequence by mimicking the syntactic pattern but introducing
    institutional content.
    """
    results = []
    for idx, (seg, scores) in enumerate(zip(segments, segment_scores)):
        english = seg.get("english") or ""
        english_lower = english.lower()

        seam = {
            "has_bridge_connective": False,
            "bridge_phrase": None,
            "institutional_terms_found": [],
            "register_shift": False,
            "seam_flag": False,
        }

        # Check for bridge connective at segment start
        for pat in bridge_patterns:
            m = pat.search(english)
            if m:
                seam["has_bridge_connective"] = True
                seam["bridge_phrase"] = m.group(0)
                break

        # Check for institutional vocabulary
        for term in institutional_terms:
            if term in english_lower:
                seam["institutional_terms_found"].append(term)

        # Register shift detection — dynamic across all categories
        if idx >= 1:
            s = scores["scores"]
            if s:
                lookback = min(idx, 3)
                prev_avgs = {}
                for cat in s:
                    prev_avgs[cat] = sum(
                        segment_scores[idx - j - 1]["scores"].get(cat, 0)
                        for j in range(lookback)
                    ) / lookback

                any_significant_rise = any(
                    s.get(cat, 0) - prev_avgs.get(cat, 0) > 1.0
                    for cat in s
                )
                if any_significant_rise or (
                    seam["has_bridge_connective"]
                    and len(seam["institutional_terms_found"]) >= 1
                ):
                    seam["register_shift"] = True

        # Combined seam flag
        if seam["has_bridge_connective"] and (
            seam["register_shift"]
            or len(seam["institutional_terms_found"]) >= 2
        ):
            seam["seam_flag"] = True
        elif (
            len(seam["institutional_terms_found"]) >= 3
            and seam.get("register_shift")
        ):
            seam["seam_flag"] = True

        results.append(seam)
    return results


# ---------------------------------------------------------------------------
# Damage / lacuna assessment
# ---------------------------------------------------------------------------

def assess_damage(page_data: dict) -> dict:
    """Compute page-level damage statistics from apparatus."""
    apparatus = page_data.get("apparatus", [])
    lines = page_data.get("lines", [])

    n_lacunae = sum(1 for a in apparatus if a["type"] == "lacuna")
    n_restorations = sum(1 for a in apparatus if a["type"] == "restoration")
    est_chars_lost = sum(
        a.get("est_chars", 0) for a in apparatus if a["type"] == "lacuna"
    )
    null_lines = sum(1 for l in lines if l.get("english") is None)

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
    """Group segments into structural units based on break_after markers."""
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

    # Final unit
    if segments and current_start <= segments[-1]["i"]:
        units.append({
            "start_i": current_start,
            "end_i": segments[-1]["i"],
            "segments": segments[-1]["i"] - current_start + 1,
        })

    return units


# ---------------------------------------------------------------------------
# Page-level features — ported from v1 _compute_chapter_features
# ---------------------------------------------------------------------------

def compute_page_features(
    segment_scores: list[dict],
    scoring_dicts: dict[str, dict[str, int]],
) -> dict:
    """Compute page-level analytical features from segment data.

    Ported from v1's _compute_chapter_features. Returns:
      - teaching_purity: ratio of substrate vocab to total vocab density
      - editorial_fatigue: per-layer drift from first to second half
    """
    non_null = [s for s in segment_scores if not s["is_null"]]
    n = len(non_null)
    layer_ids = list(scoring_dicts.keys())

    # --- Teaching purity ---
    substrate_id = layer_ids[0] if layer_ids else None
    total_density = 0.0
    substrate_density = 0.0

    for s in non_null:
        for cat, score in s["scores"].items():
            total_density += score
            if cat == substrate_id:
                substrate_density += score

    teaching_purity = (
        round(substrate_density / total_density, 3)
        if total_density > 0 else 0.0
    )

    # --- Editorial fatigue: first-half vs second-half per layer ---
    mid = n // 2 if n > 1 else 1
    fatigue: dict[str, dict[str, float]] = {}
    for lid in layer_ids:
        fh_scores = [
            non_null[i]["scores"].get(lid, 0.0) for i in range(mid)
        ]
        sh_scores = [
            non_null[i]["scores"].get(lid, 0.0) for i in range(mid, n)
        ]
        fh_density = (
            round(sum(fh_scores) / len(fh_scores), 2)
            if fh_scores else 0.0
        )
        sh_density = (
            round(sum(sh_scores) / len(sh_scores), 2)
            if sh_scores else 0.0
        )
        fatigue[lid] = {
            "first_half": fh_density,
            "second_half": sh_density,
            "shift": round(sh_density - fh_density, 2),
        }

    # Overall fatigue: average non-substrate shift
    non_substrate_shifts = [
        v["shift"] for k, v in fatigue.items() if k != substrate_id
    ]
    fatigue_score = round(
        sum(non_substrate_shifts) / len(non_substrate_shifts), 2
    ) if non_substrate_shifts else 0.0

    return {
        "teaching_purity": teaching_purity,
        "editorial_fatigue_score": fatigue_score,
        "editorial_fatigue_detail": fatigue,
    }


# ---------------------------------------------------------------------------
# Per-page analysis — combines all scoring
# ---------------------------------------------------------------------------

def analyze_page(
    page_data: dict,
    scoring_dicts: dict[str, dict[str, int]],
    bridge_patterns: list[re.Pattern],
    institutional_terms: set[str],
) -> dict:
    """Run text-critical scoring on a single page.

    Returns a dict with page number, per-segment scores, structural units,
    damage assessment, page-level features, and seam detection.
    """
    page_num = page_data.get("page", 0)
    lines = page_data.get("lines", [])

    # Score each segment
    segment_scores = [score_segment(seg, scoring_dicts) for seg in lines]

    # Structural units from break_after
    structural_units = detect_structural_units(lines)

    # Damage assessment
    damage = assess_damage(page_data)

    # Seam detection
    seam_results = detect_editorial_seams(
        lines, segment_scores,
        bridge_patterns, institutional_terms, scoring_dicts,
    )

    # Page-level aggregate scores
    non_null = [s for s in segment_scores if not s["is_null"]]
    page_scores = {}
    if non_null:
        for layer_id in scoring_dicts:
            layer_values = [s["scores"].get(layer_id, 0) for s in non_null]
            page_scores[layer_id] = round(
                sum(layer_values) / len(layer_values), 2
            )
    else:
        page_scores = {lid: 0.0 for lid in scoring_dicts}

    # Page-level pattern summary
    has_frame_opening = any(
        s["patterns"]["frame_opening"] for s in segment_scores
    )
    has_frame_closing = any(
        s["patterns"]["frame_closing"] for s in segment_scores
    )
    total_greek = sum(s["greek_loans"] for s in segment_scores)

    # Page-level features (teaching purity, editorial fatigue)
    page_features_extra = compute_page_features(
        segment_scores, scoring_dicts,
    )

    # Seam flag count
    n_seams = sum(1 for s in seam_results if s["seam_flag"])

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
            **page_features_extra,
        },
        "seam_flags": n_seams,
        "segments": segment_scores,
        "seams": seam_results,
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
            "Text-critical scoring: vocabulary analysis and "
            "editorial seam detection using LLM-derived metadata (no LLM)"
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

    print("Stage 3: Score")
    print("  Text-critical scoring (metadata-driven, no LLM)")
    print(f"  Input:  {PAGES_DIR}")
    print(f"  Output: {SCORES_DIR}")

    # Load corpus metadata
    metadata = load_corpus_metadata()
    if metadata:
        scoring_dicts = build_scoring_dicts(metadata)
        bridge_pats = build_bridge_patterns(metadata)
        inst_terms = build_institutional_terms(metadata)
        total_terms = sum(len(v) for v in scoring_dicts.values())
        print(
            f"  Metadata: {len(scoring_dicts)} scoring layers, "
            f"{total_terms} terms, "
            f"{len(bridge_pats)} bridge patterns, "
            f"{len(inst_terms)} institutional terms"
        )
    else:
        print(
            f"\n  WARNING: No corpus_metadata.json found at {METADATA_PATH}"
        )
        print(
            "  Run stage_2_discover.py first to generate metadata."
        )
        print("  Proceeding with EMPTY scoring dictionaries.")
        scoring_dicts = {}
        bridge_pats = []
        inst_terms = set()

    # List available pages
    all_pages = list_available_pages()
    if not all_pages:
        print(f"\nERROR: No translated pages in {PAGES_DIR}")
        sys.exit(1)
    print(
        f"\nFound {len(all_pages)} translated pages "
        f"(p.{all_pages[0]}-p.{all_pages[-1]})"
    )

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

        analysis = analyze_page(
            data, scoring_dicts, bridge_pats, inst_terms,
        )
        save_score(analysis)

        n_units = len(analysis["structural_units"])
        n_seams = analysis["seam_flags"]
        damage_pct = round(analysis["damage"]["damage_ratio"] * 100, 1)
        frame_flag = (
            "F" if analysis["page_features"]["has_frame_opening"] else ""
        )
        total_segments += n_lines
        total_seams += n_seams

        print(
            f"OK — {n_units} units, {damage_pct}% damaged, "
            f"{n_seams} seams"
            f"{', FRAME' if frame_flag else ''}"
        )

    # Summary
    print(f"\n{'='*50}")
    print("SCORING COMPLETE")
    print(f"  Pages scored:     {len(pages)}")
    print(f"  Total segments:   {total_segments}")
    print(f"  Total seam flags: {total_seams}")
    print(f"  Output: {SCORES_DIR}")


if __name__ == "__main__":
    main()
