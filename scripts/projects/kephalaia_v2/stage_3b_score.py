"""
Stage 3b: Score assembled chapters using corpus metadata vocabularies.

Reads chapter-level files produced by stage_3a and scores them using the
vocabulary markers from corpus_metadata.json. No LLM calls — pure NLP.

Input:
  - output/projects/kephalaia_v2/chapters/ch_NNN.json
  - output/projects/kephalaia_v2/corpus_metadata.json

Output:
  - output/projects/kephalaia_v2/scores/ch_NNN.json

Usage:
    python scripts/projects/kephalaia_v2/stage_3b_score_chapters.py
    python scripts/projects/kephalaia_v2/stage_3b_score_chapters.py --chapter 4
    python scripts/projects/kephalaia_v2/stage_3b_score_chapters.py --overwrite
"""
import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PROJECT_DIR = REPO_ROOT / "output" / "projects" / "kephalaia_v2"
CHAPTERS_DIR = PROJECT_DIR / "chapters"
SCORES_DIR = PROJECT_DIR / "scores"
METADATA_PATH = PROJECT_DIR / "corpus_metadata.json"


# ---------------------------------------------------------------------------
# Metadata loading (from old stage_3_score.py)
# ---------------------------------------------------------------------------

def load_corpus_metadata() -> dict | None:
    if not METADATA_PATH.exists():
        return None
    with open(METADATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def build_scoring_dicts(metadata: dict) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for vocab in metadata.get("scoring_vocabularies", []):
        result[vocab["id"]] = vocab.get("markers", {})
    return result


def build_bridge_patterns(metadata: dict) -> list[re.Pattern]:
    seam = metadata.get("seam_detection", {})
    patterns: list[re.Pattern] = []
    for bp in seam.get("bridge_phrases", []):
        phrase = bp["phrase"]
        words = phrase.split()
        parts = [re.escape(w).rstrip(",") + ",?" for w in words]
        regex_str = r"(?i)^" + r"\s+".join(parts)
        try:
            patterns.append(re.compile(regex_str))
        except re.error:
            patterns.append(re.compile(r"(?i)^" + re.escape(phrase)))
    return patterns


def build_institutional_terms(metadata: dict) -> set[str]:
    seam = metadata.get("seam_detection", {})
    return set(seam.get("institutional_terms", []))


# ---------------------------------------------------------------------------
# Core scoring
# ---------------------------------------------------------------------------

def score_text(text: str, markers: dict[str, int]) -> float:
    """Score text against a marker set. Return normalized score per 100 words."""
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


def score_line(line: dict, scoring_dicts: dict[str, dict[str, int]]) -> dict:
    """Score a single line across all vocabulary layers."""
    coptic = line.get("coptic") or ""
    scores = {}
    for layer_id, markers in scoring_dicts.items():
        scores[layer_id] = score_text(coptic, markers)
    return {
        "i": line.get("i", 0),
        "n": line.get("n", 0),
        "scores": scores,
        "is_null": line.get("coptic") is None,
    }


# ---------------------------------------------------------------------------
# Seam detection
# ---------------------------------------------------------------------------

def detect_seams(
    lines: list[dict],
    line_scores: list[dict],
    bridge_patterns: list[re.Pattern],
    institutional_terms: set[str],
) -> int:
    """Count editorial seam flags in the chapter."""
    n_seams = 0
    for idx, line in enumerate(lines):
        coptic = (line.get("coptic") or "").lower()

        has_bridge = False
        has_institutional = 0

        for pat in bridge_patterns:
            if pat.search(line.get("coptic") or ""):
                has_bridge = True
                break

        for term in institutional_terms:
            if term in coptic:
                has_institutional += 1

        # Register shift check
        register_shift = False
        if idx >= 1:
            s = line_scores[idx]["scores"]
            lookback = min(idx, 3)
            for cat in s:
                prev_avg = sum(
                    line_scores[idx - j - 1]["scores"].get(cat, 0)
                    for j in range(lookback)
                ) / lookback
                if s.get(cat, 0) - prev_avg > 1.0:
                    register_shift = True
                    break

        if has_bridge and (register_shift or has_institutional >= 2):
            n_seams += 1
        elif has_institutional >= 3 and register_shift:
            n_seams += 1

    return n_seams


# ---------------------------------------------------------------------------
# Chapter-level features
# ---------------------------------------------------------------------------

def compute_chapter_features(
    line_scores: list[dict],
    scoring_dicts: dict[str, dict[str, int]],
) -> dict:
    """Compute chapter-level analytical features."""
    non_null = [s for s in line_scores if not s["is_null"]]
    n = len(non_null)
    layer_ids = list(scoring_dicts.keys())

    # Teaching purity
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

    # Editorial fatigue: first-half vs second-half per layer
    mid = n // 2 if n > 1 else n
    fatigue: dict[str, dict[str, float]] = {}
    for lid in layer_ids:
        fh = [non_null[i]["scores"].get(lid, 0.0) for i in range(mid)]
        sh = [non_null[i]["scores"].get(lid, 0.0) for i in range(mid, n)]
        fh_d = round(sum(fh) / len(fh), 2) if fh else 0.0
        sh_d = round(sum(sh) / len(sh), 2) if sh else 0.0
        fatigue[lid] = {"first_half": fh_d, "second_half": sh_d, "shift": round(sh_d - fh_d, 2)}

    non_substrate_shifts = [v["shift"] for k, v in fatigue.items() if k != substrate_id]
    fatigue_score = round(
        sum(non_substrate_shifts) / len(non_substrate_shifts), 2
    ) if non_substrate_shifts else 0.0

    return {
        "teaching_purity": teaching_purity,
        "editorial_fatigue_score": fatigue_score,
        "editorial_fatigue_detail": fatigue,
    }


# ---------------------------------------------------------------------------
# Damage assessment
# ---------------------------------------------------------------------------

def assess_damage(lines: list[dict]) -> dict:
    """Compute damage statistics from line data."""
    total = len(lines)
    null_lines = sum(1 for l in lines if l.get("coptic") is None)
    # Count lines with lacunae markers in their text
    segments_with_gaps = 0
    lacunae = 0
    restorations = 0
    for l in lines:
        coptic = l.get("coptic") or ""
        english = l.get("english") or ""
        if "{" in coptic or "[" in english:
            segments_with_gaps += 1
        lacunae += coptic.count("{")
        restorations += english.count("[")

    damage_ratio = round(segments_with_gaps / total, 3) if total > 0 else 0.0
    return {
        "total_lines": total,
        "null_lines": null_lines,
        "segments_with_gaps": segments_with_gaps,
        "lacunae": lacunae,
        "restorations": restorations,
        "damage_ratio": damage_ratio,
    }


# ---------------------------------------------------------------------------
# Score a chapter
# ---------------------------------------------------------------------------

def score_chapter(chapter_data: dict, scoring_dicts, bridge_pats, inst_terms) -> dict:
    """Run full scoring on a chapter file."""
    lines = chapter_data.get("lines", [])
    header = chapter_data.get("header", {})
    title = chapter_data.get("title") or header.get("title_english", "")

    # Score each line
    line_scores = [score_line(l, scoring_dicts) for l in lines]

    # Chapter-level aggregate scores (mean per line)
    non_null = [s for s in line_scores if not s["is_null"]]
    chapter_scores = {}
    if non_null:
        for layer_id in scoring_dicts:
            vals = [s["scores"].get(layer_id, 0) for s in non_null]
            chapter_scores[layer_id] = round(sum(vals) / len(vals), 2)
    else:
        chapter_scores = {lid: 0.0 for lid in scoring_dicts}

    # Score totals (sum, not mean)
    score_totals = {}
    for layer_id in scoring_dicts:
        score_totals[layer_id] = round(
            sum(s["scores"].get(layer_id, 0) for s in non_null), 2
        )

    # Features
    features = compute_chapter_features(line_scores, scoring_dicts)

    # Damage
    damage = assess_damage(lines)

    # Seams
    n_seams = detect_seams(lines, line_scores, bridge_pats, inst_terms)

    return {
        "chapter": chapter_data["chapter"],
        "title": title,
        "total_lines": len(lines),
        "non_null_lines": len(non_null),
        "scores_mean": chapter_scores,
        "scores_total": score_totals,
        "features": features,
        "damage": damage,
        "seam_flags": n_seams,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score assembled chapters")
    parser.add_argument("--chapter", "-c", type=int, nargs="+", default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", "-n", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("Stage 3b: Score Chapters")
    print(f"  Input:  {CHAPTERS_DIR}")
    print(f"  Output: {SCORES_DIR}")

    # Load metadata
    metadata = load_corpus_metadata()
    if metadata:
        scoring_dicts = build_scoring_dicts(metadata)
        bridge_pats = build_bridge_patterns(metadata)
        inst_terms = build_institutional_terms(metadata)
        total_terms = sum(len(v) for v in scoring_dicts.values())
        print(f"  Metadata: {len(scoring_dicts)} layers, {total_terms} terms")
    else:
        print(f"  WARNING: No corpus_metadata.json at {METADATA_PATH}")
        scoring_dicts = {}
        bridge_pats = []
        inst_terms = set()

    # Find chapter files
    all_chapters = sorted(CHAPTERS_DIR.glob("ch_*.json"))
    if not all_chapters:
        print(f"ERROR: No chapter files in {CHAPTERS_DIR}")
        sys.exit(1)

    # Filter if specific chapters requested
    if args.chapter:
        requested = set(args.chapter)
        all_chapters = [f for f in all_chapters if int(f.stem.split("_")[1]) in requested]

    # Check existing
    if not args.overwrite:
        to_process = []
        for f in all_chapters:
            score_path = SCORES_DIR / f.name
            if not score_path.exists():
                to_process.append(f)
        skipped = len(all_chapters) - len(to_process)
        if skipped:
            print(f"  Skipping {skipped} already scored (use --overwrite to redo)")
        all_chapters = to_process

    print(f"\n  Scoring {len(all_chapters)} chapters...")

    if args.dry_run:
        for f in all_chapters:
            print(f"    [dry-run] {f.name}")
        return

    SCORES_DIR.mkdir(parents=True, exist_ok=True)

    for f in all_chapters:
        with open(f, "r", encoding="utf-8") as fh:
            ch_data = json.load(fh)

        result = score_chapter(ch_data, scoring_dicts, bridge_pats, inst_terms)

        outpath = SCORES_DIR / f.name
        with open(outpath, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, ensure_ascii=False)

    print(f"  Done. Scores written to {SCORES_DIR}")


if __name__ == "__main__":
    main()
