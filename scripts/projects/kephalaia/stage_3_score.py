#!/usr/bin/env python3
"""
Text-critical analysis of corpus chapters.

Pipeline stage: runs AFTER stage_2_discover.py, BEFORE stage_4_extract.py.

This script performs automated vocabulary scoring and editorial seam detection
on each chapter using the corpus metadata produced by stage_2_discover.py.
It does NOT involve any LLM calls — all analysis is computational NLP.

What it produces (per chapter):
  - Paragraph-level vocabulary density scores for each temporal layer
  - Editorial seam detection flags (bridge connectives + institutional vocab)
  - Register shift detection across paragraph boundaries

Output: output/projects/<project>/analysis/chapters/ch_NNN.json

The output is consumed by stage_4_extract.py, which formats the analysis data
into the Claude prompt for LLM-driven temporal layer classification.

Usage:
    python scripts/stage_3_score.py --project kephalaia
    python scripts/stage_3_score.py --project kephalaia --chapter 38
    python scripts/stage_3_score.py --project kephalaia --range 0-50
    python scripts/stage_3_score.py --project kephalaia --dry-run
    python scripts/stage_3_score.py --project kephalaia --overwrite
"""
import argparse
import json
import re
import sys
from pathlib import Path

from project_config import load_project, list_projects

# ---------------------------------------------------------------------------
# Paths — set by configure_paths() at startup
# ---------------------------------------------------------------------------

PROJECT_CFG = None
CHAPTERS_DIR: Path | None = None   # input: cleaned chapters
ANALYSIS_DIR: Path | None = None   # output: analysis/chapters/


def configure_paths(project_name: str) -> None:
    """Set module-level path variables from project config."""
    global PROJECT_CFG, CHAPTERS_DIR, ANALYSIS_DIR

    cfg = load_project(project_name)
    cfg.paths.ensure_dirs()
    PROJECT_CFG = cfg

    CHAPTERS_DIR = cfg.paths.cleaned_chapters
    ANALYSIS_DIR = cfg.paths.analysis_chapters

    print(f"Project: {cfg.display_name}")
    print(f"  Type:   {cfg.document_type}")
    print(f"  Input:  {CHAPTERS_DIR}")
    print(f"  Output: {ANALYSIS_DIR}")


# ---------------------------------------------------------------------------
# Field accessors — handle both chapter-based and section-based formats
# ---------------------------------------------------------------------------

def get_number(chapter: dict) -> int:
    """Get the chapter/section number from a cleaned chapter dict."""
    return chapter.get("chapter_number") or chapter.get("section_number", 0)


def get_text(chapter: dict) -> str:
    """Get the main teaching/translation text from a cleaned chapter dict."""
    return chapter.get("teaching_text") or chapter.get("english_translation", "")


def get_title(chapter: dict) -> str:
    """Get the chapter/section title."""
    num = get_number(chapter)
    return chapter.get("title", f"Section {num}")


# ---------------------------------------------------------------------------
# Metadata loading
# ---------------------------------------------------------------------------

def load_corpus_metadata(project_dir: Path) -> dict | None:
    """Load corpus metadata produced by stage_2_discover.py.

    Returns the parsed JSON, or None if the file doesn't exist.
    """
    path = project_dir / "corpus_metadata.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_scoring_dicts(metadata: dict) -> dict[str, dict[str, int]]:
    """Build scoring dictionaries from metadata scoring_vocabularies.

    Returns a dict of category_id → {term: weight}.
    Directly consumable by score_text() and score_chapter_paragraphs().
    """
    result: dict[str, dict[str, int]] = {}
    for vocab in metadata.get("scoring_vocabularies", []):
        cat_id = vocab["id"]
        result[cat_id] = vocab.get("markers", {})
    return result


def build_bridge_patterns(metadata: dict) -> list[re.Pattern]:
    """Build compiled regex patterns from metadata bridge phrases.

    Each phrase is anchored to paragraph start with flexible whitespace
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
            patterns.append(re.compile(
                r"(?i)^" + re.escape(phrase)
            ))
    return patterns


def build_institutional_terms(metadata: dict) -> set[str]:
    """Build institutional terms set from metadata seam_detection."""
    seam = metadata.get("seam_detection", {})
    return set(seam.get("institutional_terms", []))


# ---------------------------------------------------------------------------
# Register analysis — scoring functions
# ---------------------------------------------------------------------------

def score_text(text: str, markers: dict[str, int]) -> float:
    """Score text against a marker set. Return normalized score per 100 words."""
    text_lower = text.lower()
    total = 0
    for marker, weight in markers.items():
        count = text_lower.count(marker.lower())
        if count > 0:
            total += weight * count
    words = max(len(text.split()), 1)
    return round((total / words) * 100, 2)


def split_paragraphs(text: str) -> list[str]:
    """Split teaching text into paragraphs."""
    parts = re.split(r'\n\s*\n|\n(?=⟨p\.\d+⟩)', text)
    return [p.strip() for p in parts if p.strip() and len(p.split()) >= 3]


def score_chapter_paragraphs(
    teaching_text: str,
    scoring_dicts: dict[str, dict[str, int]],
) -> list[dict]:
    """Score each paragraph in a chapter's teaching text.

    Args:
        teaching_text: The raw teaching text to score.
        scoring_dicts: Category → {term: weight} dicts loaded from metadata.

    Returns a list of dicts with paragraph text, word count, and register scores.
    """
    paragraphs = split_paragraphs(teaching_text)
    results = []
    for i, text in enumerate(paragraphs):
        scores = {
            name: score_text(text, markers)
            for name, markers in scoring_dicts.items()
        }
        results.append({
            "index": i + 1,
            "words": len(text.split()),
            "text_preview": text[:150].replace("\n", " "),
            "scores": scores,
        })
    return results


# ---------------------------------------------------------------------------
# Editorial seam detection — paragraph-level (metadata-driven)
# ---------------------------------------------------------------------------

def detect_editorial_seams(
    paragraphs: list[str],
    para_scores: list[dict],
    bridge_patterns: list[re.Pattern],
    institutional_terms: set[str],
) -> list[dict]:
    """Detect potential editorial seams at paragraph level.

    Uses metadata-loaded bridge patterns and institutional terms instead
    of hardcoded values.

    An editorial seam is where an editor extends an existing teaching sequence
    by mimicking the syntactic pattern but introducing institutional content.
    """
    results = []
    for i, (text, scores) in enumerate(zip(paragraphs, para_scores)):
        text_lower = text.lower()
        seam = {
            "has_bridge_connective": False,
            "bridge_phrase": None,
            "institutional_terms_found": [],
            "register_shift": False,
            "seam_flag": False,
            "seam_note": None,
        }

        # Check for bridge connective at paragraph start
        first_line = text.strip().split("\n")[0] if text.strip() else ""
        for pat in bridge_patterns:
            m = pat.search(first_line)
            if m:
                seam["has_bridge_connective"] = True
                seam["bridge_phrase"] = m.group(0)
                break

        # Check for institutional vocabulary
        for term in institutional_terms:
            if term in text_lower:
                seam["institutional_terms_found"].append(term)

        # Register shift detection — dynamic across all categories
        if i >= 1:
            s = scores["scores"]
            if s:
                lookback = min(i, 3)
                prev_avgs = {}
                for cat in s:
                    prev_avgs[cat] = sum(
                        para_scores[i - j - 1]["scores"].get(cat, 0)
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
            seam["seam_note"] = (
                f"EDITORIAL SEAM DETECTED: Bridge connective "
                f"'{seam['bridge_phrase']}' with institutional "
                f"vocabulary ({', '.join(seam['institutional_terms_found'])}). "
                f"This paragraph likely extends an existing teaching "
                f"sequence with institutional application — the editor "
                f"mimics the preceding pattern but shifts to "
                f"church-specific content."
            )
        elif (
            len(seam["institutional_terms_found"]) >= 3
            and seam.get("register_shift")
        ):
            seam["seam_flag"] = True
            seam["seam_note"] = (
                f"PROBABLE EDITORIAL EXTENSION: High institutional "
                f"vocabulary ({', '.join(seam['institutional_terms_found'])}) "
                f"with register shift from preceding cosmological paragraphs."
            )

        results.append(seam)
    return results


# ---------------------------------------------------------------------------
# Per-chapter analysis — combines scoring + seam detection
# ---------------------------------------------------------------------------

# Formulaic patterns for structure detection
_OPENING_PATTERNS = [
    re.compile(r"(?i)^once again (?:the )?(?:enlightener|apostle) speaks?"),
    re.compile(r"(?i)^once more (?:the )?(?:enlightener|apostle)"),
    re.compile(r"(?i)^once again,? at one of the times"),
    re.compile(r"(?i)^once again a disciple speaks?"),
    re.compile(r"(?i)^his disciples questioned"),
    re.compile(r"(?i)^the disciple(?:s)? questioned"),
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
_NT_CITATION_RE = re.compile(
    r"\b(?:Matt|Mark|Luke|John|Acts|Rom|[12] ?Cor|Gal|Eph|Phil|Col|"
    r"[12] ?Thess|[12] ?Tim|Tit|Heb|Jas|[12] ?Pet|[123] ?Jn|Jude|Rev)"
    r"\.?\s*\d",
    re.IGNORECASE,
)
_OT_CITATION_RE = re.compile(
    r"\b(?:Gen|Exod|Lev|Num|Deut|Josh|Judg|Ruth|[12] ?Sam|[12] ?Kgs|"
    r"[12] ?Chr|Ezra|Neh|Esth|Job|Ps|Prov|Eccl|Song|Isa|Jer|Lam|Ezek|"
    r"Dan|Hos|Joel|Amos|Obad|Jonah|Mic|Nah|Hab|Zeph|Hag|Zech|Mal)"
    r"\.?\s*\d",
    re.IGNORECASE,
)


def _compute_chapter_features(
    chapter: dict,
    paragraphs: list[str],
    para_scores: list[dict],
    scoring_dicts: dict[str, dict[str, int]],
) -> dict:
    """Compute chapter-level analytical features from paragraph data.

    Returns a dict with:
      - teaching_purity: ratio of oldest-layer vocab to total vocab density
      - editorial_fatigue: per-layer drift from first to second half
      - structure: formulaic opening/closing/question detection
      - citations: NT/OT citations found in footnotes
    """
    n = len(para_scores)
    layer_ids = list(scoring_dicts.keys())

    # --- Teaching purity ---
    # Ratio of the first (substrate) layer to total vocabulary density
    substrate_id = layer_ids[0] if layer_ids else None
    total_density = 0.0
    substrate_density = 0.0
    total_words = 0
    for ps in para_scores:
        w = ps["words"]
        total_words += w
        for cat, score in ps["scores"].items():
            total_density += score * w / 100.0
            if cat == substrate_id:
                substrate_density += score * w / 100.0
    teaching_purity = (
        round(substrate_density / total_density, 3)
        if total_density > 0 else 0.0
    )

    # --- Editorial fatigue: per-layer first-half vs second-half density ---
    mid = n // 2 if n > 1 else 1
    fatigue: dict[str, dict[str, float]] = {}
    for lid in layer_ids:
        fh_total = sh_total = 0.0
        fh_words = sh_words = 0
        for i, ps in enumerate(para_scores):
            w = ps["words"]
            s = ps["scores"].get(lid, 0.0)
            if i < mid:
                fh_total += s * w / 100.0
                fh_words += w
            else:
                sh_total += s * w / 100.0
                sh_words += w
        fh_density = round(fh_total / fh_words * 100, 2) if fh_words else 0.0
        sh_density = round(sh_total / sh_words * 100, 2) if sh_words else 0.0
        shift = round(sh_density - fh_density, 2)
        fatigue[lid] = {
            "first_half": fh_density,
            "second_half": sh_density,
            "shift": shift,
        }

    # Overall fatigue score: sum of non-substrate shifts (positive = later
    # layers growing in second half)
    non_substrate_shifts = [
        v["shift"] for k, v in fatigue.items() if k != substrate_id
    ]
    fatigue_score = round(
        sum(non_substrate_shifts) / len(non_substrate_shifts), 2
    ) if non_substrate_shifts else 0.0

    # --- Structure detection ---
    first_para = paragraphs[0] if paragraphs else ""
    last_para = paragraphs[-1] if paragraphs else ""
    has_formulaic_opening = any(
        p.search(first_para) for p in _OPENING_PATTERNS
    )
    has_formulaic_closing = any(
        p.search(last_para) for p in _CLOSING_PATTERNS
    )
    has_question_formula = any(
        p.search(first_para) for p in _QUESTION_PATTERNS
    ) or (len(paragraphs) > 1 and any(
        p.search(paragraphs[1]) for p in _QUESTION_PATTERNS
    ))

    # --- Citations from footnotes ---
    footnotes = chapter.get("footnotes", [])
    footnote_text = " ".join(f.get("text", "") for f in footnotes)
    nt_citations = sorted(set(_NT_CITATION_RE.findall(footnote_text)))
    ot_citations = sorted(set(_OT_CITATION_RE.findall(footnote_text)))

    return {
        "teaching_purity": teaching_purity,
        "editorial_fatigue_score": fatigue_score,
        "editorial_fatigue_detail": fatigue,
        "structure": {
            "has_formulaic_opening": has_formulaic_opening,
            "has_formulaic_closing": has_formulaic_closing,
            "has_question_formula": has_question_formula,
        },
        "nt_citations": nt_citations,
        "ot_citations": ot_citations,
    }


def analyze_chapter(
    chapter: dict,
    scoring_dicts: dict[str, dict[str, int]],
    bridge_patterns: list[re.Pattern],
    institutional_terms: set[str],
) -> dict:
    """Run text-critical analysis on a single chapter.

    Returns a dict with chapter_number, title, total_paragraphs,
    chapter-level features (fatigue, purity, structure, citations),
    and per-paragraph scoring and seam detection results.
    """
    ch_num = get_number(chapter)
    title = get_title(chapter)
    teaching = get_text(chapter)

    paragraphs = split_paragraphs(teaching)
    para_scores = score_chapter_paragraphs(teaching, scoring_dicts)
    seam_results = detect_editorial_seams(
        paragraphs, para_scores,
        bridge_patterns, institutional_terms,
    )

    # Chapter-level features computed from paragraph data
    chapter_features = _compute_chapter_features(
        chapter, paragraphs, para_scores, scoring_dicts,
    )

    result_paragraphs = []
    for i, (text, scores, seam) in enumerate(
        zip(paragraphs, para_scores, seam_results)
    ):
        result_paragraphs.append({
            "index": i + 1,
            "words": scores["words"],
            "text": text,
            "scores": scores["scores"],
            "seam": seam,
        })

    return {
        "chapter_number": ch_num,
        "title": title,
        "total_paragraphs": len(paragraphs),
        "chapter_features": chapter_features,
        "paragraphs": result_paragraphs,
    }


# ---------------------------------------------------------------------------
# Save / load
# ---------------------------------------------------------------------------

def save_analysis(analysis: dict, output_dir: Path) -> None:
    """Save per-chapter analysis result to JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    ch_num = analysis["chapter_number"]
    path = output_dir / f"ch_{ch_num:03d}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)


def load_analysis(output_dir: Path, ch_num: int) -> dict | None:
    """Load pre-computed analysis for a chapter."""
    path = output_dir / f"ch_{ch_num:03d}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def is_analyzed(output_dir: Path, ch_num: int) -> bool:
    """Check whether analysis output exists for a chapter."""
    return (output_dir / f"ch_{ch_num:03d}.json").exists()


# ---------------------------------------------------------------------------
# Load chapters
# ---------------------------------------------------------------------------

def load_chapters() -> list[dict]:
    """Load all cleaned chapter JSON files."""
    chapters = []
    for path in sorted(CHAPTERS_DIR.glob("ch_*.json")):
        with open(path, encoding="utf-8") as f:
            chapters.append(json.load(f))
    return chapters


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Text-critical analysis: vocabulary scoring and "
            "editorial seam detection (no LLM)"
        )
    )
    parser.add_argument(
        "--project", "-p",
        type=str,
        default="kephalaia",
        help=(
            f"Project to process "
            f"(available: {', '.join(list_projects()) or 'none'})"
        ),
    )
    parser.add_argument("--chapter", "-c", type=int, default=None)
    parser.add_argument("--range", "-r", type=str, default=None)
    parser.add_argument("--limit", "-l", type=int, default=None)
    parser.add_argument("--dry-run", "-n", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_paths(args.project)

    # Load chapters
    all_chapters = load_chapters()
    if not all_chapters:
        print("ERROR: No cleaned chapters found in", CHAPTERS_DIR)
        sys.exit(1)

    print(f"Loaded {len(all_chapters)} cleaned chapters")

    # Determine which to process
    if args.chapter is not None:
        chapters = [
            ch for ch in all_chapters
            if get_number(ch) == args.chapter
        ]
        if not chapters:
            print(f"ERROR: Chapter {args.chapter} not found")
            sys.exit(1)
    elif args.range:
        m = re.match(r"(\d+)-(\d+)", args.range)
        if not m:
            print("ERROR: Invalid range. Use '0-20'")
            sys.exit(1)
        start, end = int(m.group(1)), int(m.group(2))
        chapters = [
            ch for ch in all_chapters
            if start <= get_number(ch) <= end
        ]
    else:
        chapters = all_chapters

    if args.limit:
        chapters = chapters[:args.limit]

    # Skip already processed
    if not args.overwrite:
        to_process = [
            ch for ch in chapters
            if not is_analyzed(ANALYSIS_DIR, get_number(ch))
        ]
        skipped = len(chapters) - len(to_process)
        if skipped > 0:
            print(
                f"  Skipping {skipped} already-analyzed "
                f"(use --overwrite)"
            )
        chapters = to_process

    if not chapters:
        print("All chapters already analyzed.")
        return

    print(f"\nProcessing {len(chapters)} chapters:")
    for ch in chapters:
        num = get_number(ch)
        title = ch.get("title", "")[:60]
        words = len(get_text(ch).split())
        print(f"  Ch.{num:3d}  ({words:5d} words)  {title}")

    if args.dry_run:
        print("\n[DRY RUN] No analysis performed.")
        return

    # Load corpus metadata
    metadata = load_corpus_metadata(PROJECT_CFG.paths.project_dir)
    if metadata:
        scoring_dicts = build_scoring_dicts(metadata)
        bridge_pats = build_bridge_patterns(metadata)
        inst_terms = build_institutional_terms(metadata)
        print(
            f"\nLoaded corpus metadata: "
            f"{len(scoring_dicts)} scoring layers, "
            f"{sum(len(v) for v in scoring_dicts.values())} terms"
        )
    else:
        print(
            "\nWARNING: No corpus metadata found — "
            "running without metadata-driven scoring"
        )
        scoring_dicts = {}
        bridge_pats = []
        inst_terms = set()

    print()

    # Process
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    total_seams = 0
    total_paragraphs = 0

    for i, ch in enumerate(chapters, 1):
        ch_num = get_number(ch)
        title = ch.get("title", "")[:50]
        words = len(get_text(ch).split())
        print(
            f"[{i}/{len(chapters)}] Ch.{ch_num} "
            f"({words} words) {title}...",
            end=" ",
            flush=True,
        )

        analysis = analyze_chapter(
            ch, scoring_dicts, bridge_pats, inst_terms,
        )
        save_analysis(analysis, ANALYSIS_DIR)

        n_para = analysis["total_paragraphs"]
        n_seams = sum(
            1 for p in analysis["paragraphs"]
            if p["seam"].get("seam_flag")
        )
        total_paragraphs += n_para
        total_seams += n_seams

        print(f"OK — {n_para} ¶s, {n_seams} seam flags")

    # Summary
    print(f"\n{'='*60}")
    print(f"ANALYSIS COMPLETE")
    print(f"  Chapters analyzed: {len(chapters)}")
    print(f"  Total paragraphs:  {total_paragraphs}")
    print(f"  Total seam flags:  {total_seams}")
    print(f"  Output: {ANALYSIS_DIR}")
    print("Done.")


if __name__ == "__main__":
    main()
