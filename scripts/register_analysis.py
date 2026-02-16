#!/usr/bin/env python3
"""
Textual Criticism: Register Analysis of the Kephalaia

Identifies distinct textual registers (voices) in each chapter by scoring
paragraphs against vocabulary and syntactic markers. This is proper bottom-up
textual criticism that precedes and guides the LLM-based extraction.

REGISTERS:

  1. CORRESPONDENTIAL (likely Book of Jashar)
     Written in the Science of Correspondences: natural images (body parts,
     food, water, fire, wind, light, animals, plants) mapped to spiritual
     realities or interior states. Describes HOW things work through functional
     relationships. No or minimal proper names of mythological beings.
     Distinctive voice: teaching about the inner person through natural images.

  2. MANICHAEAN COSMOLOGICAL (Mani's narrative framework)
     Named beings (Father of Greatness, Mother of Life, Living Spirit, Third
     Ambassador, First Man, Pillar of Glory, etc.) in a specific mythological
     story. Cosmic events narrated as history: evocations, emanations, battles,
     constructions. This may WRAP correspondential content in Mani's vocabulary.

  3. CHRISTIAN / NT OVERLAY
     Jesus the Splendour, Christ, holy church, apostolate, catechumens,
     brothers/sisters as church members, Gospel language.

  4. HAGIOGRAPHIC FRAME
     Editorial Q&A: "Once again the enlightener speaks...", disciple questions,
     closing praise formulas.

  5. PASTORAL
     Church rules, fasting, prayer, alms, catechumen instruction, behavioral
     ethics without cosmological grounding.

Usage:
    python scripts/register_analysis.py                     # Analyze all chapters
    python scripts/register_analysis.py --chapter 86        # Single chapter detail
    python scripts/register_analysis.py --report            # Summary report
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHAPTERS_DIR = PROJECT_ROOT / "output" / "cleaned" / "chapters"
OUTPUT_DIR = PROJECT_ROOT / "output" / "analysis" / "registers"


# ---------------------------------------------------------------------------
# Vocabulary marker sets for each register
# ---------------------------------------------------------------------------

# Register 1: CORRESPONDENTIAL (Book of Jashar)
# Natural images, interior states, body-as-cosmos, functional descriptions
CORRESPONDENTIAL_MARKERS = {
    # Body-cosmos correspondence
    "corresponds": 5, "accords": 5, "pattern of": 4, "reflects": 3,
    "likeness": 3, "after the pattern": 5, "image": 2,
    # Body parts as correspondence subjects
    "head": 2, "neck": 2, "heart": 3, "stomach": 2, "ribs": 2,
    "navel": 2, "loins": 2, "liver": 3, "lung": 3, "spleen": 3,
    "kidneys": 3, "intestines": 2, "veins": 2, "skin": 2,
    "shinbones": 3, "footsoles": 3, "gall": 3, "blood": 2,
    "flesh": 2, "bone": 2, "marrow": 2, "eyes": 1, "ears": 1,
    "limbs": 2, "body": 1, "senses": 2,
    # Interior states (the microcosmic warfare)
    "peaceful": 4, "troubled": 4, "confusion": 4, "disturbance": 4,
    "ordered": 3, "tranquil": 4, "carefree": 4, "sweet": 2,
    "gladness": 3, "grief": 3, "anger": 3, "lust": 3, "envy": 3,
    "depression": 3, "gloom": 3, "constructive": 3, "wicked": 2,
    "rebellions": 3, "subdue": 3, "uprightness": 5,
    # Natural images as correspondence vehicles
    "food": 3, "nourishment": 4, "bread": 2, "water": 2,
    "eaten": 3, "drunk": 3, "digestion": 4,
    "tree": 2, "trees": 2, "fruit": 2, "fruits": 2,
    "seed": 3, "root": 2, "branch": 2, "plant": 3,
    "animal": 2, "animals": 2, "bird": 2, "birds": 2,
    "fish": 2, "reptile": 2, "creature": 2,
    "fire": 2, "wind": 2, "air": 2, "atmosphere": 3,
    "spring": 2, "well": 2, "flood": 3, "rain": 3,
    "mountain": 2, "earth": 1, "dust": 2,
    # Functional descriptions (not proper names)
    "the mind": 2, "old man": 4, "new man": 4,
    "counsels": 3, "doctrines": 3, "considerations": 3,
    "the soul": 2, "wisdom": 2, "knowledge": 2,
    "conduits": 4, "roots": 2, "channels": 3,
    # Correspondential methodology
    "corresponds to": 5, "macro-cosmos": 5, "micro": 4,
    "small body": 5, "reflects the pattern": 5,
    "worn and torn": 4, "garments": 2, "rags": 3, "tattered": 4,
    "cross of light": 3,
    # Teaching about HOW things work
    "gathered in": 3, "purified": 2, "refined": 2,
    "separated": 2, "mixed": 2, "mixture": 2,
    "enters": 1, "comes into": 2, "goes out": 2,
    "birth-signs": 4, "stars": 2,
}

# Register 2: MANICHAEAN COSMOLOGICAL (Mani's named framework)
COSMOLOGICAL_MARKERS = {
    # Named beings — the mythology proper
    "father of greatness": 5, "mother of life": 5,
    "living spirit": 4, "third ambassador": 5, "ambassador": 3,
    "first man": 3, "pillar of glory": 5, "column of glory": 5,
    "perfect man": 4, "keeper of splendour": 5, "king of honour": 5,
    "adamant of light": 5, "king of glory": 5, "porter": 3,
    "five sons": 4, "five shekhinas": 5,
    "twelve virgins": 5, "beloved of the lights": 5,
    "great builder": 4, "land of light": 3, "land of darkness": 3,
    "king of darkness": 4,
    # Cosmogonic events
    "evoked": 4, "evocation": 5, "summoned": 3,
    "emanation": 4, "emanations": 4, "manifested": 3,
    "poured forth": 3, "revealed": 2,
    "constructed": 2, "fashioned": 2, "sculpted": 3,
    # Cosmic structures
    "firmament": 3, "firmaments": 3, "aeons": 3, "aeon": 3,
    "storehouses": 4, "storehouse": 4,
    "principalities": 4, "rulers": 3, "archons": 4,
    "zodiac": 3, "sphere": 3,
    "light ship": 4, "ship of the day": 4, "ship of the night": 4,
    "great wheel": 4, "cosmic wheel": 4,
    # Numbered hierarchies with names
    "five greatnesses": 5, "five fathers": 4,
    "five elements": 3, "five worlds": 4,
    "three earths": 4, "ten firmaments": 4,
    "twelve hours": 4, "twelve judges": 4,
    # Battle narrative
    "swallowed": 3, "devoured": 3, "defeated": 2,
    "victory": 2, "armour": 3, "weapons": 2,
}

# Register 3: CHRISTIAN / NT OVERLAY
CHRISTIAN_MARKERS = {
    "jesus the splendour": 5, "jesus the son of greatness": 5,
    "jesus the youth": 5, "beloved christ": 5,
    "christ": 3, "son of god": 4,
    "holy church": 5, "his church": 4, "the church": 3,
    "apostolate": 5, "apostle": 2,
    "catechumen": 5, "catechumens": 5,
    "brothers": 2, "sisters": 3,
    "sons of the faith": 5, "daughters of the light": 5,
    "holy spirit": 3, "grace": 3,
    "gospel": 4, "scripture": 2, "scriptures": 2,
    "parable": 3, "elect": 3,
    "preaching": 2, "congregation": 2,
    "baptism": 4, "resurrection": 3,
    "psalms": 2, "prayers": 2, "fast": 1, "fasting": 2,
}

# Register 4: HAGIOGRAPHIC FRAME
FRAME_MARKERS = {
    "once again the enlightener speaks": 5,
    "once again he speaks": 4,
    "once more the enlightener": 5,
    "once more the apostle": 4,
    "once more his disciples": 4,
    "once again a disciple speaks": 5,
    "once again, at one of the times": 5,
    "his disciples questioned": 5,
    "the disciple questioned": 5,
    "disciples say to him": 5,
    "i beseech you": 4, "i entreat you": 4,
    "then speaks the apostle": 5,
    "then the apostle says": 5,
    "then the apostle speaks": 5,
    "then speaks the glorious one": 5,
    "the enlightener speaks to him": 4,
    "he speaks to that disciple": 4,
    "when they heard these things": 5,
    "when that disciple had heard": 5,
    "they rejoiced": 4, "they glorified": 4,
    "blessed is he who": 4,
    "you are glorious and blessed": 5,
    "sitting down among the church": 4,
    "sitting in the congregation": 4,
    "my master": 3, "our master": 3,
    "our enlightener": 4, "our father": 3,
    "the glorious one": 3,
    "i will explain it to you": 3,
    "behold, i have explained": 4,
    "on one of the occasions": 4,
}

# Register 5: PASTORAL
PASTORAL_MARKERS = {
    "fasting": 2, "prayer": 2, "alms": 4, "alms-giving": 5,
    "catechumen": 4, "catechumens": 4,
    "church rules": 5, "sin": 2, "righteousness": 2,
    "sinners": 3, "repentance": 4,
    "the elect": 3, "the hearer": 4, "hearers": 4,
    "tithe": 5, "offering": 2, "charity": 4,
    "commandment": 3, "commandments": 3,
    "forbidden": 3, "lawful": 3,
    "holiness": 2, "purity": 2,
    "works of righteousness": 4,
}


# ---------------------------------------------------------------------------
# Scoring engine
# ---------------------------------------------------------------------------

def split_into_paragraphs(text: str) -> list[str]:
    """Split teaching text into paragraphs by double newline or page markers."""
    # Split on double newlines or page markers
    parts = re.split(r'\n\s*\n|\n(?=⟨p\.\d+⟩)', text)
    paragraphs = []
    for part in parts:
        part = part.strip()
        if part and len(part.split()) >= 3:  # At least 3 words
            paragraphs.append(part)
    return paragraphs


def score_text(text: str, markers: dict[str, int]) -> tuple[float, list[tuple[str, int]]]:
    """Score a text against a marker set.

    Returns (total_score, list of (marker, weight) hits).
    Scoring: each marker hit adds its weight. Score is normalized by text length.
    """
    text_lower = text.lower()
    hits = []
    total = 0
    for marker, weight in markers.items():
        # Count occurrences
        count = text_lower.count(marker.lower())
        if count > 0:
            hits.append((marker, weight * count))
            total += weight * count
    # Normalize by word count (per 100 words)
    words = max(len(text.split()), 1)
    normalized = (total / words) * 100
    return normalized, hits


def analyze_paragraph(text: str) -> dict:
    """Score a paragraph against all registers."""
    scores = {}
    details = {}
    for name, markers in [
        ("correspondential", CORRESPONDENTIAL_MARKERS),
        ("cosmological", COSMOLOGICAL_MARKERS),
        ("christian", CHRISTIAN_MARKERS),
        ("frame", FRAME_MARKERS),
        ("pastoral", PASTORAL_MARKERS),
    ]:
        score, hits = score_text(text, markers)
        scores[name] = round(score, 2)
        details[name] = hits
    return scores, details


def classify_paragraph(scores: dict) -> str:
    """Classify a paragraph based on its highest-scoring register."""
    if not scores:
        return "unclassified"
    # Frame detection: if frame score is high, it's frame regardless
    if scores.get("frame", 0) > 5.0:
        return "frame"
    # Find dominant register among content types
    content_scores = {
        k: v for k, v in scores.items() if k != "frame"
    }
    if not content_scores or max(content_scores.values()) == 0:
        return "unclassified"
    dominant = max(content_scores, key=content_scores.get)
    # Check for mixed correspondential + cosmological
    corr = scores.get("correspondential", 0)
    cosm = scores.get("cosmological", 0)
    if corr > 2.0 and cosm > 2.0:
        if corr > cosm:
            return "correspondential_with_names"
        else:
            return "cosmological_with_correspondences"
    return dominant


# ---------------------------------------------------------------------------
# Chapter analysis
# ---------------------------------------------------------------------------

def analyze_chapter(chapter: dict) -> dict:
    """Analyze an entire chapter, paragraph by paragraph."""
    ch_num = chapter["chapter_number"]
    title = chapter.get("title", "")
    text = chapter.get("teaching_text", "")

    if not text.strip():
        return {
            "chapter_number": ch_num,
            "title": title,
            "word_count": 0,
            "paragraphs": [],
            "register_distribution": {},
            "dominant_register": "empty",
        }

    paragraphs = split_into_paragraphs(text)
    results = []
    register_word_counts = defaultdict(int)

    for i, para_text in enumerate(paragraphs):
        scores, details = analyze_paragraph(para_text)
        classification = classify_paragraph(scores)
        word_count = len(para_text.split())
        register_word_counts[classification] += word_count

        results.append({
            "paragraph_number": i + 1,
            "word_count": word_count,
            "text_preview": para_text[:200],
            "scores": scores,
            "classification": classification,
            "top_hits": {
                reg: sorted(hits, key=lambda x: -x[1])[:5]
                for reg, hits in details.items() if hits
            },
        })

    total_words = sum(p["word_count"] for p in results)
    distribution = {}
    for reg, wc in sorted(register_word_counts.items()):
        distribution[reg] = {
            "words": wc,
            "percent": round(wc / max(total_words, 1) * 100, 1),
        }

    # Dominant register (excluding frame)
    content_dist = {
        k: v for k, v in register_word_counts.items()
        if k not in ("frame", "unclassified")
    }
    dominant = max(content_dist, key=content_dist.get) if content_dist else "unclassified"

    return {
        "chapter_number": ch_num,
        "title": title,
        "word_count": total_words,
        "paragraph_count": len(results),
        "dominant_register": dominant,
        "register_distribution": distribution,
        "paragraphs": results,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_chapter_detail(analysis: dict) -> None:
    """Print detailed analysis of a single chapter."""
    ch = analysis["chapter_number"]
    title = analysis["title"]
    print(f"\n{'='*80}")
    print(f"Chapter {ch}: {title}")
    print(f"{'='*80}")
    print(f"Words: {analysis['word_count']}, Paragraphs: {analysis['paragraph_count']}")
    print(f"Dominant register: {analysis['dominant_register']}")
    print()

    # Distribution
    print("Register Distribution:")
    for reg, info in sorted(analysis["register_distribution"].items(),
                            key=lambda x: -x[1]["percent"]):
        bar = "█" * int(info["percent"] / 2)
        print(f"  {reg:40s} {info['percent']:5.1f}% ({info['words']:4d} words) {bar}")
    print()

    # Paragraph details
    for para in analysis["paragraphs"]:
        pn = para["paragraph_number"]
        wc = para["word_count"]
        cls = para["classification"]
        scores = para["scores"]
        preview = para["text_preview"][:100].replace("\n", " ")

        # Color-code by classification
        tag = {
            "correspondential": "[CORR]",
            "cosmological": "[COSM]",
            "christian": "[CHRI]",
            "frame": "[FRAM]",
            "pastoral": "[PAST]",
            "correspondential_with_names": "[C+N ]",
            "cosmological_with_correspondences": "[N+C ]",
            "unclassified": "[----]",
        }.get(cls, "[????]")

        print(f"  ¶{pn:2d} {tag} ({wc:3d}w) corr={scores.get('correspondential',0):5.1f} "
              f"cosm={scores.get('cosmological',0):5.1f} "
              f"chri={scores.get('christian',0):5.1f} "
              f"fram={scores.get('frame',0):5.1f}")
        print(f"       {preview}...")

        # Top hits for dominant register
        if cls in para["top_hits"]:
            top = para["top_hits"][cls][:3]
            hit_str = ", ".join(f"'{h[0]}'({h[1]})" for h in top)
            print(f"       Hits: {hit_str}")
        print()


def print_summary_report(all_analyses: list[dict]) -> None:
    """Print a summary report across all chapters."""
    print(f"\n{'='*80}")
    print("REGISTER ANALYSIS SUMMARY — Kephalaia of the Teacher")
    print(f"{'='*80}\n")

    # Aggregate stats
    total_words = sum(a["word_count"] for a in all_analyses)
    register_totals = defaultdict(int)
    chapter_by_dominant = defaultdict(list)

    for a in all_analyses:
        chapter_by_dominant[a["dominant_register"]].append(a["chapter_number"])
        for reg, info in a["register_distribution"].items():
            register_totals[reg] += info["words"]

    print(f"Total chapters: {len(all_analyses)}")
    print(f"Total words: {total_words:,}")
    print()

    # Overall register distribution
    print("OVERALL REGISTER DISTRIBUTION (by word count):")
    print("-" * 60)
    for reg, wc in sorted(register_totals.items(), key=lambda x: -x[1]):
        pct = wc / max(total_words, 1) * 100
        bar = "█" * int(pct / 2)
        print(f"  {reg:40s} {pct:5.1f}% ({wc:6,d} words) {bar}")
    print()

    # Chapters by dominant register
    print("CHAPTERS BY DOMINANT REGISTER:")
    print("-" * 60)
    for reg, chapters in sorted(chapter_by_dominant.items(),
                                key=lambda x: -len(x[1])):
        ch_str = ", ".join(str(c) for c in sorted(chapters))
        print(f"  {reg} ({len(chapters)} chapters):")
        print(f"    {ch_str}")
    print()

    # Pure correspondential chapters (highest ratio of correspondential to cosmological)
    print("TOP 20 CHAPTERS BY CORRESPONDENTIAL PURITY:")
    print("(highest correspondential:cosmological ratio)")
    print("-" * 60)
    ratios = []
    for a in all_analyses:
        dist = a["register_distribution"]
        corr_words = dist.get("correspondential", {}).get("words", 0)
        corr_wn = dist.get("correspondential_with_names", {}).get("words", 0)
        cosm_words = dist.get("cosmological", {}).get("words", 0)
        cosm_wc = dist.get("cosmological_with_correspondences", {}).get("words", 0)
        total_corr = corr_words + corr_wn
        total_cosm = cosm_words + cosm_wc
        if total_corr + total_cosm > 0:
            ratio = total_corr / max(total_corr + total_cosm, 1)
        else:
            ratio = 0
        ratios.append((a["chapter_number"], a["title"][:50], ratio,
                        total_corr, total_cosm, a["word_count"]))
    ratios.sort(key=lambda x: -x[2])
    for ch, title, ratio, corr, cosm, wc in ratios[:20]:
        print(f"  Ch.{ch:3d} ratio={ratio:.2f} (corr={corr:4d} cosm={cosm:4d} "
              f"total={wc:4d}) {title}")
    print()

    # Pure cosmological chapters (for contrast)
    print("TOP 15 CHAPTERS BY COSMOLOGICAL DOMINANCE:")
    print("-" * 60)
    cosm_ratios = [(ch, title, 1 - ratio, corr, cosm, wc)
                    for ch, title, ratio, corr, cosm, wc in ratios]
    cosm_ratios.sort(key=lambda x: -x[2])
    for ch, title, ratio, corr, cosm, wc in cosm_ratios[:15]:
        print(f"  Ch.{ch:3d} cosm_ratio={ratio:.2f} (corr={corr:4d} cosm={cosm:4d} "
              f"total={wc:4d}) {title}")
    print()

    # Christian overlay detection
    print("CHAPTERS WITH SIGNIFICANT CHRISTIAN MARKERS:")
    print("-" * 60)
    for a in all_analyses:
        dist = a["register_distribution"]
        chri = dist.get("christian", {}).get("words", 0)
        chri_pct = dist.get("christian", {}).get("percent", 0)
        if chri_pct > 10:
            print(f"  Ch.{a['chapter_number']:3d} christian={chri_pct:.1f}% "
                  f"({chri} words) {a['title'][:50]}")
    print()


# ---------------------------------------------------------------------------
# Load and run
# ---------------------------------------------------------------------------

def load_all_chapters() -> list[dict]:
    """Load all cleaned chapters."""
    chapters = []
    for path in sorted(CHAPTERS_DIR.glob("ch_*.json")):
        with open(path, encoding="utf-8") as f:
            chapters.append(json.load(f))
    return chapters


def main():
    parser = argparse.ArgumentParser(
        description="Register analysis of Kephalaia chapters"
    )
    parser.add_argument(
        "--chapter", "-c", type=int, default=None,
        help="Analyze a single chapter in detail"
    )
    parser.add_argument(
        "--report", "-r", action="store_true",
        help="Print summary report across all chapters"
    )
    parser.add_argument(
        "--save", "-s", action="store_true",
        help="Save analysis data to JSON"
    )
    args = parser.parse_args()

    chapters = load_all_chapters()
    if not chapters:
        print("ERROR: No cleaned chapters found")
        sys.exit(1)

    print(f"Loaded {len(chapters)} chapters")

    if args.chapter is not None:
        # Single chapter detail
        ch = next((c for c in chapters if c["chapter_number"] == args.chapter), None)
        if not ch:
            print(f"ERROR: Chapter {args.chapter} not found")
            sys.exit(1)
        analysis = analyze_chapter(ch)
        print_chapter_detail(analysis)
        return

    # Analyze all chapters
    all_analyses = []
    for ch in chapters:
        analysis = analyze_chapter(ch)
        all_analyses.append(analysis)

    if args.save:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUTPUT_DIR / "register_analysis.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(all_analyses, f, indent=2, ensure_ascii=False)
        print(f"Saved to {out_path}")

    if args.report or not args.save:
        print_summary_report(all_analyses)


if __name__ == "__main__":
    main()
