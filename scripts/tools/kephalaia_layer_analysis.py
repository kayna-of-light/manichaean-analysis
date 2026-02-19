#!/usr/bin/env python3
"""
Kephalaia Layer Analysis — Multi-Signal Composite Textual Analysis
==================================================================

Applies computational textual-critical techniques to the Kephalaia of the Teacher
(Gardner 1995 translation) to identify editorial layers:

  Layer 1 (Original Correspondential): Manichaean cosmological teaching using
      Light Mind, Ambassador, First Man, five elements, etc.
  Layer 2 (NT/Pauline Interpolation): Christian overlay — Jesus Christ, apostle
      (in Christian sense), Pauline theology, NT citations
  Layer 3 (Hagiographic): Biographical Mani material, miracle stories, "the
      enlightener/apostle" as title for Mani

Techniques applied per chapter:
  1. Theological vocabulary profiling (three-layer dictionaries)
  2. Formulaic opening analysis
  3. Chapter length distribution
  4. Scripture citation mapping
  5. Sentence length / complexity distribution
  6. Type-Token Ratio (vocabulary richness)
  7. Lacunae density (manuscript condition)
  8. Gardner commentary extraction (editorial flags)
  9. Intra-chapter vocabulary shift (editor fatigue detection)

Output: JSON data + matplotlib visualizations + summary report.
"""

import re
import json
import statistics
from pathlib import Path
from dataclasses import dataclass, field, asdict
from collections import Counter
from typing import Optional

# ---------------------------------------------------------------------------
# Vocabulary Dictionaries
# ---------------------------------------------------------------------------

# Layer 1: Original Manichaean correspondential cosmology
LAYER1_VOCAB = {
    # Cosmological beings (Manichaean proper)
    "father of greatness", "mother of life", "first man", "living spirit",
    "ambassador", "third messenger", "virgin of light", "great builder",
    "beloved of the lights", "keeper of splendour", "king of glory",
    "king of honour", "porter", "adamant of light", "column of glory",
    "pillar of glory", "perfect man", "great spirit",
    # Cosmological structures
    "five elements", "five storehouses", "five worlds", "five trees",
    "ten firmaments", "eight earths", "new earth", "land of light",
    "land of darkness", "realm of light", "realm of darkness",
    "king of darkness", "five sons", "matter",
    # Correspondential/structural terms
    "light mind", "cross of light", "living soul", "thought of death",
    "light elements", "dark elements", "vessels", "firmaments",
    "storehouses", "five garments", "three wheels",
    # Process terms
    "call and answer", "summons", "obedience", "mixture",
    "purification", "separation", "ascent", "descent",
    "emanation", "evocation",
    # Manichaean technical terms
    "elect", "catechumen", "hearer", "righteousness",
    "five limbs", "five intellectuals",
    # Zoroastrian / Manichaean deities
    "saclas", "nebroel", "ashaqlun", "namrael",
    # Cosmological events
    "first time", "second time", "third time", "last day",
    "great fire", "new aeon",
}

# Layer 2: NT/Pauline/Christian interpolation
LAYER2_VOCAB = {
    # Christological titles (NT sense, not Manichaean Jesus the Splendour)
    "jesus christ", "christ jesus", "lord jesus",
    "son of god",  # in Christian theological sense
    # Pauline vocabulary
    "apostle of jesus", "grace", "faith and works",
    "body of christ", "justified", "justification",
    "salvation through faith", "redemption through",
    # NT citations and references
    "it is written", "scripture says", "the gospel says",
    "the apostle says",  # when citing Paul
    # Christian ecclesiastical
    "bishop", "deacon", "presbyter", "baptism",
    "eucharist", "communion",
    # Specific Christian phrases
    "father, son", "holy trinity", "original sin",
    "crucifixion", "resurrection of the dead",
    "kingdom of heaven", "eternal life",
}

# Layer 2 single-word markers (need different matching)
LAYER2_SINGLE = {
    "paul", "matthew", "john", "luke", "mark",
}

# Layer 3: Hagiographic / Mani biographical
LAYER3_VOCAB = {
    # Mani as subject
    "the enlightener", "the apostle of light",
    "mani the living", "manichaios",
    "the apostle speaks", "the apostle is sitting",
    "the apostle said",
    # Biographical narrative
    "in the land of babel", "in babylon",
    "the twin", "twin spirit", "paraclete",
    # Hagiographic markers
    "miracle", "miraculous", "wonder",
    # Institutional
    "the holy church", "the church of",
    "his disciples",
}

# Formulaic openings
FORMULAIC_OPENINGS = [
    r"once again (?:he|the (?:enlightener|apostle)) speaks?(?: to his disciples)?",
    r"once more he speaks",
    r"again he speaks",
    r"he says? to (?:his|them|the)",
    r"the enlightener speaks",
    r"the apostle is sitting",
]

# NT citation patterns
NT_CITATION_PATTERNS = [
    r"\*\d+\s*(?:Jn|Mt|Mk|Lk|Rom|1?\s*Cor|Gal|Eph|Phil|Col|1?\s*Thess|1?\s*Tim|Tit|Heb|Jas|1?\s*Pet|Rev)\.",
    r"(?:Jn|Mt|Mk|Lk|Rom|1?\s*Cor|Gal|Eph|Phil|Col)\.\s*\d+",
    r"gospel of thomas",
]

# OT / Manichaean scripture citation patterns
MANI_CITATION_PATTERNS = [
    r"the (?:living )?gospel",
    r"the treasure",
    r"the pragmateia",
    r"the book of giants",
    r"the image",
    r"the epistles?",
    r"the (?:great |holy )?psalm",
    r"shabuhragan",
]


# ---------------------------------------------------------------------------
# Chapter Parser
# ---------------------------------------------------------------------------

@dataclass
class Chapter:
    """Parsed chapter from the Kephalaia."""
    number: int
    title: str
    page_ref: str
    gardner_commentary: str  # editorial intro by Gardner
    teaching_text: str       # Mani's actual teaching
    full_text: str           # everything including commentary
    start_line: int
    end_line: int


def parse_chapters(text: str) -> list[Chapter]:
    """Parse the Kephalaia text into individual chapters."""
    lines = text.split("\n")
    chapters = []

    # Find chapter boundaries using ··· N ··· pattern
    chapter_starts = []
    for i, line in enumerate(lines):
        m = re.match(r"^···\s*(\d+)\s*[·.]+", line.strip())
        if m:
            chapter_starts.append((i, int(m.group(1))))

    for idx, (start_line, chapter_num) in enumerate(chapter_starts):
        # End is the line before next chapter (or end of file)
        if idx + 1 < len(chapter_starts):
            end_line = chapter_starts[idx + 1][0] - 1
        else:
            end_line = len(lines) - 1

        # Extract full text block
        block = lines[start_line:end_line + 1]
        full_text = "\n".join(block)

        # Extract title — usually on the line with "/" markers after the chapter number
        title = ""
        page_ref = ""

        # Look for page reference pattern like (155,6-29) or (155,6 - 29)
        for line in block[:5]:
            m = re.search(r"\([\d,\s\-\.]+\)", line)
            if m:
                page_ref = m.group(0)

        # Look for title — line starting with / Concerning or similar
        for line in block[:10]:
            m = re.search(r"/\s*(Concerning[^/]+)", line)
            if m:
                title = m.group(1).strip().rstrip("/").strip()
                break
            # Also try without the leading /
            m = re.search(r"(Concerning\s+.+?)(?:\.|$)", line)
            if m and not title:
                title = m.group(1).strip().rstrip(".").strip()
                break

        if not title:
            # Try to find any descriptive line in first 5 lines
            for line in block[1:6]:
                cleaned = line.strip().strip("/").strip()
                if cleaned and not re.match(r"^[\d\s\(\),\-\.]+$", cleaned) and len(cleaned) > 10:
                    if not re.match(r"^(THE KEPHALAIA|CHAPTER|---|\*)", cleaned):
                        title = cleaned[:80]
                        break

        # Separate Gardner's commentary from teaching text
        # Gardner's commentary is typically the first paragraph(s) before
        # "Once again..." or the actual teaching begins
        gardner_commentary = ""
        teaching_text = ""

        text_started = False
        commentary_lines = []
        teaching_lines = []

        for line in block:
            stripped = line.strip()
            # Skip chapter markers, page refs, title lines
            if re.match(r"^···", stripped) or re.match(r"^\(\d+", stripped):
                continue
            if stripped.startswith("---") or stripped.startswith("THE KEPHALAIA"):
                continue
            if re.match(r"^CHAPTER\s+", stripped):
                continue
            if not stripped:
                if text_started:
                    teaching_lines.append(line)
                else:
                    commentary_lines.append(line)
                continue

            # Detect where Mani's teaching begins
            if not text_started:
                lower = stripped.lower()
                if any(re.search(pat, lower) for pat in FORMULAIC_OPENINGS):
                    text_started = True
                    teaching_lines.append(line)
                elif lower.startswith("once again") or lower.startswith("he says") or lower.startswith("he speaks"):
                    text_started = True
                    teaching_lines.append(line)
                # Some chapters start with direct speech without formula
                elif any(marker in lower for marker in [
                    "five ", "three ", "the first", "there are", "know that",
                    "blessed is", "this is the manner", "now, ",
                    "the father of greatness", "the living spirit",
                ]):
                    # Could be teaching or commentary — heuristic: if it's after
                    # some commentary lines, it's likely teaching
                    if len(commentary_lines) > 3:
                        text_started = True
                        teaching_lines.append(line)
                    else:
                        commentary_lines.append(line)
                else:
                    commentary_lines.append(line)
            else:
                teaching_lines.append(line)

        gardner_commentary = "\n".join(commentary_lines).strip()
        teaching_text = "\n".join(teaching_lines).strip()

        # If we never detected a teaching start, everything is teaching
        if not teaching_text and gardner_commentary:
            teaching_text = gardner_commentary
            gardner_commentary = ""

        chapters.append(Chapter(
            number=chapter_num,
            title=title or f"Chapter {chapter_num}",
            page_ref=page_ref,
            gardner_commentary=gardner_commentary,
            teaching_text=teaching_text,
            full_text=full_text,
            start_line=start_line,
            end_line=end_line,
        ))

    return chapters


# ---------------------------------------------------------------------------
# Analysis Functions
# ---------------------------------------------------------------------------

@dataclass
class ChapterAnalysis:
    """Complete analysis results for a single chapter."""
    chapter_number: int
    title: str
    page_ref: str

    # Basic metrics
    total_words: int = 0
    teaching_words: int = 0
    commentary_words: int = 0
    sentence_count: int = 0

    # Vocabulary profiling
    layer1_hits: int = 0
    layer2_hits: int = 0
    layer3_hits: int = 0
    layer1_terms: list = field(default_factory=list)
    layer2_terms: list = field(default_factory=list)
    layer3_terms: list = field(default_factory=list)
    layer1_density: float = 0.0  # hits per 100 words
    layer2_density: float = 0.0
    layer3_density: float = 0.0

    # Formulaic analysis
    has_formulaic_opening: bool = False
    opening_formula: str = ""

    # Complexity
    avg_sentence_length: float = 0.0
    sentence_length_std: float = 0.0
    type_token_ratio: float = 0.0

    # Lacunae
    lacunae_count: int = 0
    lacunae_density: float = 0.0  # per 100 words

    # Citations
    nt_citations: list = field(default_factory=list)
    mani_citations: list = field(default_factory=list)

    # Gardner flags
    gardner_flags: list = field(default_factory=list)

    # Editor fatigue — vocabulary shift within chapter
    first_half_layer1: float = 0.0
    second_half_layer1: float = 0.0
    first_half_layer2: float = 0.0
    second_half_layer2: float = 0.0
    layer_shift_score: float = 0.0  # positive = more L2 in second half

    # Composite scores
    layer1_score: float = 0.0
    layer2_score: float = 0.0
    layer3_score: float = 0.0
    purity_score: float = 0.0  # layer1 - (layer2 + layer3)

    # Manual comparison
    in_layer1_extract: bool = False


def count_vocab_hits(text: str, vocab_set: set[str]) -> tuple[int, list[str]]:
    """Count multi-word vocabulary hits in text."""
    lower = text.lower()
    hits = 0
    found_terms = []
    for term in vocab_set:
        count = len(re.findall(re.escape(term), lower))
        if count > 0:
            hits += count
            found_terms.append(f"{term} ({count})")
    return hits, found_terms


def count_single_word_hits(text: str, vocab_set: set[str]) -> tuple[int, list[str]]:
    """Count single-word vocabulary hits (word-boundary aware)."""
    lower = text.lower()
    hits = 0
    found_terms = []
    for term in vocab_set:
        count = len(re.findall(r"\b" + re.escape(term) + r"\b", lower))
        if count > 0:
            hits += count
            found_terms.append(f"{term} ({count})")
    return hits, found_terms


def count_lacunae(text: str) -> int:
    """Count manuscript lacunae markers: [...], [  ], brackets with gaps."""
    return len(re.findall(r"\[\s*\.{2,}\s*\]|\[\s{2,}\]|\[\s*\.\.\.\s*\]", text))


def get_sentences(text: str) -> list[str]:
    """Split text into sentences (approximate)."""
    # Clean up manuscript markers
    cleaned = re.sub(r"\[\s*\.{2,}\s*\]", "", text)
    cleaned = re.sub(r"\*\d+[^\n]*", "", cleaned)  # Remove footnotes
    cleaned = re.sub(r"\d{2,}", "", cleaned)  # Remove page numbers
    # Split on sentence-ending punctuation
    sentences = re.split(r"[.!?]+", cleaned)
    return [s.strip() for s in sentences if len(s.strip().split()) > 2]


def get_words(text: str) -> list[str]:
    """Extract words from text."""
    cleaned = re.sub(r"\[\s*\.{2,}\s*\]", "", text)
    cleaned = re.sub(r"\*\d+[^\n]*", "", cleaned)
    cleaned = re.sub(r"[^\w\s'-]", " ", cleaned)
    words = cleaned.lower().split()
    return [w for w in words if len(w) > 1 and not w.isdigit()]


def type_token_ratio(words: list[str]) -> float:
    """Calculate vocabulary richness (unique words / total words)."""
    if not words:
        return 0.0
    return len(set(words)) / len(words)


def find_citations(text: str) -> tuple[list[str], list[str]]:
    """Find NT and Manichaean scripture citations."""
    nt_cites = []
    for pat in NT_CITATION_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            nt_cites.append(m.group(0).strip())

    mani_cites = []
    for pat in MANI_CITATION_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            mani_cites.append(m.group(0).strip())

    return nt_cites, mani_cites


def extract_gardner_flags(commentary: str) -> list[str]:
    """Extract editorial flags from Gardner's commentary."""
    flags = []
    lower = commentary.lower()

    flag_patterns = [
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
    ]

    for pat, label in flag_patterns:
        if re.search(pat, lower):
            flags.append(label)

    return flags


def analyze_chapter(chapter: Chapter, layer1_chapters: set[int]) -> ChapterAnalysis:
    """Run all analyses on a single chapter."""
    text = chapter.teaching_text or chapter.full_text
    words = get_words(text)
    sentences = get_sentences(text)

    analysis = ChapterAnalysis(
        chapter_number=chapter.number,
        title=chapter.title,
        page_ref=chapter.page_ref,
    )

    # Basic metrics
    analysis.total_words = len(get_words(chapter.full_text))
    analysis.teaching_words = len(words)
    analysis.commentary_words = len(get_words(chapter.gardner_commentary))
    analysis.sentence_count = len(sentences)

    # Vocabulary profiling — on teaching text only
    l1_hits, l1_terms = count_vocab_hits(text, LAYER1_VOCAB)
    l2_hits, l2_terms = count_vocab_hits(text, LAYER2_VOCAB)
    l2s_hits, l2s_terms = count_single_word_hits(text, LAYER2_SINGLE)
    l3_hits, l3_terms = count_vocab_hits(text, LAYER3_VOCAB)

    analysis.layer1_hits = l1_hits
    analysis.layer2_hits = l2_hits + l2s_hits
    analysis.layer3_hits = l3_hits
    analysis.layer1_terms = l1_terms
    analysis.layer2_terms = l2_terms + l2s_terms
    analysis.layer3_terms = l3_terms

    if analysis.teaching_words > 0:
        analysis.layer1_density = (l1_hits / analysis.teaching_words) * 100
        analysis.layer2_density = ((l2_hits + l2s_hits) / analysis.teaching_words) * 100
        analysis.layer3_density = (l3_hits / analysis.teaching_words) * 100

    # Formulaic opening
    lower_text = text.lower()
    for pat in FORMULAIC_OPENINGS:
        m = re.search(pat, lower_text)
        if m:
            analysis.has_formulaic_opening = True
            analysis.opening_formula = m.group(0)
            break

    # Sentence complexity
    if sentences:
        lengths = [len(s.split()) for s in sentences]
        analysis.avg_sentence_length = statistics.mean(lengths)
        analysis.sentence_length_std = statistics.stdev(lengths) if len(lengths) > 1 else 0.0

    # Type-Token Ratio
    analysis.type_token_ratio = type_token_ratio(words)

    # Lacunae
    analysis.lacunae_count = count_lacunae(text)
    if analysis.teaching_words > 0:
        analysis.lacunae_density = (analysis.lacunae_count / analysis.teaching_words) * 100

    # Citations
    analysis.nt_citations, analysis.mani_citations = find_citations(text)

    # Gardner flags
    analysis.gardner_flags = extract_gardner_flags(chapter.gardner_commentary)

    # Editor fatigue — split chapter in half, compare layer densities
    if analysis.teaching_words > 40:
        mid = len(words) // 2
        first_half_text = " ".join(words[:mid])
        second_half_text = " ".join(words[mid:])
        fh_l1, _ = count_vocab_hits(first_half_text, LAYER1_VOCAB)
        sh_l1, _ = count_vocab_hits(second_half_text, LAYER1_VOCAB)
        fh_l2, _ = count_vocab_hits(first_half_text, LAYER2_VOCAB)
        sh_l2, _ = count_vocab_hits(second_half_text, LAYER2_VOCAB)
        fh_l2s, _ = count_single_word_hits(first_half_text, LAYER2_SINGLE)
        sh_l2s, _ = count_single_word_hits(second_half_text, LAYER2_SINGLE)

        analysis.first_half_layer1 = (fh_l1 / mid) * 100 if mid > 0 else 0
        analysis.second_half_layer1 = (sh_l1 / (len(words) - mid)) * 100 if (len(words) - mid) > 0 else 0
        analysis.first_half_layer2 = ((fh_l2 + fh_l2s) / mid) * 100 if mid > 0 else 0
        analysis.second_half_layer2 = ((sh_l2 + sh_l2s) / (len(words) - mid)) * 100 if (len(words) - mid) > 0 else 0

        # Shift score: positive means L2 increases relative to L1 in second half
        l1_shift = analysis.second_half_layer1 - analysis.first_half_layer1
        l2_shift = analysis.second_half_layer2 - analysis.first_half_layer2
        analysis.layer_shift_score = l2_shift - l1_shift

    # Composite scores
    analysis.layer1_score = analysis.layer1_density
    analysis.layer2_score = analysis.layer2_density + len(analysis.nt_citations) * 0.5
    analysis.layer3_score = analysis.layer3_density

    # Purity: how "clean" is this chapter for Layer 1
    analysis.purity_score = analysis.layer1_score - (analysis.layer2_score + analysis.layer3_score)

    # Manual comparison
    analysis.in_layer1_extract = chapter.number in layer1_chapters

    return analysis


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------

def generate_visualizations(analyses: list[ChapterAnalysis], output_dir: Path):
    """Generate matplotlib visualizations."""
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np

    # Sort by chapter number
    analyses = sorted(analyses, key=lambda a: a.chapter_number)
    ch_nums = [a.chapter_number for a in analyses]
    n = len(analyses)

    # Color coding
    colors_layer1 = []
    for a in analyses:
        if a.in_layer1_extract:
            colors_layer1.append("#2ecc71")  # green = in our Layer 1
        else:
            colors_layer1.append("#e74c3c")  # red = excluded

    # ===== Figure 1: Layer Density Heatmap =====
    fig, axes = plt.subplots(4, 1, figsize=(20, 14), sharex=True,
                              gridspec_kw={"height_ratios": [1, 1, 1, 0.3]})
    fig.suptitle("Kephalaia Layer Analysis — Vocabulary Density per Chapter",
                 fontsize=16, fontweight="bold")

    # Layer 1 density
    l1_vals = [a.layer1_density for a in analyses]
    axes[0].bar(range(n), l1_vals, color="#3498db", alpha=0.8, edgecolor="white")
    axes[0].set_ylabel("L1 Density\n(per 100 words)")
    axes[0].set_title("Layer 1 — Original Manichaean Cosmological Vocabulary", fontsize=11)

    # Layer 2 density
    l2_vals = [a.layer2_density for a in analyses]
    axes[1].bar(range(n), l2_vals, color="#e74c3c", alpha=0.8, edgecolor="white")
    axes[1].set_ylabel("L2 Density\n(per 100 words)")
    axes[1].set_title("Layer 2 — NT/Pauline/Christian Vocabulary", fontsize=11)

    # Layer 3 density
    l3_vals = [a.layer3_density for a in analyses]
    axes[2].bar(range(n), l3_vals, color="#f39c12", alpha=0.8, edgecolor="white")
    axes[2].set_ylabel("L3 Density\n(per 100 words)")
    axes[2].set_title("Layer 3 — Hagiographic / Biographical Vocabulary", fontsize=11)

    # Layer 1 extract indicator
    for i, a in enumerate(analyses):
        axes[3].bar(i, 1, color=colors_layer1[i], edgecolor="white")
    axes[3].set_ylabel("In L1\nExtract")
    axes[3].set_yticks([])
    axes[3].set_title("Manual Layer 1 Classification (green = included, red = excluded)", fontsize=11)

    # X-axis labels
    axes[3].set_xticks(range(n))
    axes[3].set_xticklabels([str(c) for c in ch_nums], rotation=90, fontsize=7)
    axes[3].set_xlabel("Chapter Number")

    plt.tight_layout()
    fig.savefig(output_dir / "01_layer_density_heatmap.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: 01_layer_density_heatmap.png")

    # ===== Figure 2: Composite Purity Score =====
    fig, ax = plt.subplots(figsize=(20, 6))
    purity = [a.purity_score for a in analyses]
    bar_colors = ["#2ecc71" if p > 0 else "#e74c3c" for p in purity]
    # Overlay with manual classification markers
    ax.bar(range(n), purity, color=bar_colors, alpha=0.7, edgecolor="white")
    for i, a in enumerate(analyses):
        if a.in_layer1_extract:
            ax.plot(i, purity[i], "^", color="blue", markersize=8, zorder=5)
        else:
            ax.plot(i, purity[i], "v", color="gray", markersize=5, zorder=5)

    ax.axhline(y=0, color="black", linewidth=0.5)
    ax.set_xticks(range(n))
    ax.set_xticklabels([str(c) for c in ch_nums], rotation=90, fontsize=7)
    ax.set_xlabel("Chapter Number")
    ax.set_ylabel("Purity Score (L1 - L2 - L3)")
    ax.set_title("Composite Purity Score per Chapter  (▲ = in Layer 1 extract, ▼ = excluded)",
                 fontsize=14, fontweight="bold")
    # Legend
    blue_tri = mpatches.Patch(color="blue", label="In Layer 1 Extract")
    gray_tri = mpatches.Patch(color="gray", label="Excluded")
    green_bar = mpatches.Patch(color="#2ecc71", label="Positive purity (L1 dominant)")
    red_bar = mpatches.Patch(color="#e74c3c", label="Negative purity (L2/L3 dominant)")
    ax.legend(handles=[blue_tri, gray_tri, green_bar, red_bar], loc="upper right", fontsize=9)

    plt.tight_layout()
    fig.savefig(output_dir / "02_purity_score.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: 02_purity_score.png")

    # ===== Figure 3: Chapter Length + Lacunae =====
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(20, 8), sharex=True)

    word_counts = [a.teaching_words for a in analyses]
    ax1.bar(range(n), word_counts, color=colors_layer1, alpha=0.7, edgecolor="white")
    ax1.set_ylabel("Teaching Text (words)")
    ax1.set_title("Chapter Length and Manuscript Condition", fontsize=14, fontweight="bold")
    avg_len = statistics.mean(word_counts) if word_counts else 0
    ax1.axhline(y=avg_len, color="blue", linestyle="--", linewidth=0.8, label=f"Mean: {avg_len:.0f}")
    ax1.legend()

    lacunae = [a.lacunae_density for a in analyses]
    ax2.bar(range(n), lacunae, color="#9b59b6", alpha=0.7, edgecolor="white")
    ax2.set_ylabel("Lacunae per 100 words")
    ax2.set_xticks(range(n))
    ax2.set_xticklabels([str(c) for c in ch_nums], rotation=90, fontsize=7)
    ax2.set_xlabel("Chapter Number")

    plt.tight_layout()
    fig.savefig(output_dir / "03_length_lacunae.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: 03_length_lacunae.png")

    # ===== Figure 4: Text Complexity (TTR + Sentence Length) =====
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(20, 8), sharex=True)

    ttr = [a.type_token_ratio for a in analyses]
    ax1.bar(range(n), ttr, color=colors_layer1, alpha=0.7, edgecolor="white")
    ax1.set_ylabel("Type-Token Ratio")
    ax1.set_title("Vocabulary Richness and Sentence Complexity", fontsize=14, fontweight="bold")

    sent_len = [a.avg_sentence_length for a in analyses]
    ax2.bar(range(n), sent_len, color=colors_layer1, alpha=0.7, edgecolor="white")
    ax2.set_ylabel("Avg Sentence Length (words)")
    ax2.set_xticks(range(n))
    ax2.set_xticklabels([str(c) for c in ch_nums], rotation=90, fontsize=7)
    ax2.set_xlabel("Chapter Number")

    plt.tight_layout()
    fig.savefig(output_dir / "04_complexity.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: 04_complexity.png")

    # ===== Figure 5: Editor Fatigue — Intra-chapter Vocabulary Shift =====
    fig, ax = plt.subplots(figsize=(20, 6))
    shifts = [a.layer_shift_score for a in analyses]
    shift_colors = ["#e74c3c" if s > 0.5 else ("#2ecc71" if s < -0.5 else "#95a5a6") for s in shifts]
    ax.bar(range(n), shifts, color=shift_colors, alpha=0.7, edgecolor="white")
    ax.axhline(y=0, color="black", linewidth=0.5)
    ax.set_xticks(range(n))
    ax.set_xticklabels([str(c) for c in ch_nums], rotation=90, fontsize=7)
    ax.set_xlabel("Chapter Number")
    ax.set_ylabel("Layer Shift Score")
    ax.set_title("Editor Fatigue Detection: Intra-Chapter Vocabulary Shift\n"
                 "(positive = L2 vocabulary increases in second half relative to L1)",
                 fontsize=14, fontweight="bold")
    plt.tight_layout()
    fig.savefig(output_dir / "05_editor_fatigue.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: 05_editor_fatigue.png")

    # ===== Figure 6: Agreement Matrix =====
    # Compare computational classification vs manual
    fig, ax = plt.subplots(figsize=(8, 6))
    # 2x2: computational says L1 vs not, manual says L1 vs not
    comp_l1 = [a.purity_score > 0 for a in analyses]
    man_l1 = [a.in_layer1_extract for a in analyses]

    tp = sum(1 for c, m in zip(comp_l1, man_l1) if c and m)
    fp = sum(1 for c, m in zip(comp_l1, man_l1) if c and not m)
    fn = sum(1 for c, m in zip(comp_l1, man_l1) if not c and m)
    tn = sum(1 for c, m in zip(comp_l1, man_l1) if not c and not m)

    matrix = [[tp, fp], [fn, tn]]
    im = ax.imshow(matrix, cmap="YlGnBu", aspect="auto")
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Manual: Yes", "Manual: No"])
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["Computed: L1", "Computed: Not L1"])
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(matrix[i][j]), ha="center", va="center", fontsize=20, fontweight="bold")
    ax.set_title(f"Classification Agreement Matrix\n"
                 f"Agreement: {(tp + tn) / n * 100:.1f}%  |  Cohen's κ: {_cohens_kappa(tp, fp, fn, tn):.3f}",
                 fontsize=14, fontweight="bold")
    plt.colorbar(im)
    plt.tight_layout()
    fig.savefig(output_dir / "06_agreement_matrix.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: 06_agreement_matrix.png")


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


# ---------------------------------------------------------------------------
# Report Generator
# ---------------------------------------------------------------------------

def generate_report(analyses: list[ChapterAnalysis], chapters: list[Chapter], output_dir: Path):
    """Generate markdown summary report."""
    analyses = sorted(analyses, key=lambda a: a.chapter_number)

    # Compute statistics
    n = len(analyses)
    l1_included = [a for a in analyses if a.in_layer1_extract]
    l1_excluded = [a for a in analyses if not a.in_layer1_extract]

    comp_l1 = [a for a in analyses if a.purity_score > 0]
    comp_not_l1 = [a for a in analyses if a.purity_score <= 0]

    # Agreement
    tp = sum(1 for a in analyses if a.purity_score > 0 and a.in_layer1_extract)
    fp = sum(1 for a in analyses if a.purity_score > 0 and not a.in_layer1_extract)
    fn = sum(1 for a in analyses if a.purity_score <= 0 and a.in_layer1_extract)
    tn = sum(1 for a in analyses if a.purity_score <= 0 and not a.in_layer1_extract)
    agreement = (tp + tn) / n * 100 if n > 0 else 0
    kappa = _cohens_kappa(tp, fp, fn, tn)

    report = []
    report.append("# Kephalaia Layer Analysis — Computational Results")
    report.append("")
    report.append(f"**Date**: 2026-02-16")
    report.append(f"**Source**: Kephalaia of the Teacher (Gardner 1995, OCR'd)")
    report.append(f"**Chapters analyzed**: {n}")
    report.append(f"**Manual Layer 1 chapters**: {len(l1_included)}")
    report.append("")
    report.append("---")
    report.append("")

    # ===== Agreement Summary =====
    report.append("## 1. Computational vs. Manual Classification Agreement")
    report.append("")
    report.append(f"| Metric | Value |")
    report.append(f"|--------|-------|")
    report.append(f"| Total chapters | {n} |")
    report.append(f"| True Positive (both say L1) | {tp} |")
    report.append(f"| True Negative (both say not L1) | {tn} |")
    report.append(f"| False Positive (computed L1, manual excluded) | {fp} |")
    report.append(f"| False Negative (computed not L1, manual included) | {fn} |")
    report.append(f"| **Agreement** | **{agreement:.1f}%** |")
    report.append(f"| **Cohen's κ** | **{kappa:.3f}** |")
    report.append("")

    if fn > 0:
        report.append("### Chapters in Layer 1 Extract but Computationally Flagged (False Negatives)")
        report.append("")
        report.append("These chapters are in our manual Layer 1 extract but have negative purity scores:")
        report.append("")
        for a in analyses:
            if a.purity_score <= 0 and a.in_layer1_extract:
                report.append(f"- **Ch. {a.chapter_number}** ({a.title}): purity={a.purity_score:.2f}, "
                             f"L1={a.layer1_density:.2f}, L2={a.layer2_density:.2f}, L3={a.layer3_density:.2f}")
                if a.layer2_terms:
                    report.append(f"  - L2 terms: {', '.join(a.layer2_terms)}")
                if a.layer3_terms:
                    report.append(f"  - L3 terms: {', '.join(a.layer3_terms)}")
        report.append("")

    if fp > 0:
        report.append("### Chapters Excluded but Computationally Pure (False Positives)")
        report.append("")
        report.append("These chapters were excluded from Layer 1 but have positive purity — potential candidates for restoration:")
        report.append("")
        for a in sorted([a for a in analyses if a.purity_score > 0 and not a.in_layer1_extract],
                       key=lambda x: -x.purity_score):
            report.append(f"- **Ch. {a.chapter_number}** ({a.title}): purity={a.purity_score:.2f}, "
                         f"L1={a.layer1_density:.2f}, L2={a.layer2_density:.2f}, L3={a.layer3_density:.2f}")
            if a.layer1_terms:
                report.append(f"  - L1 terms: {', '.join(a.layer1_terms[:8])}")
        report.append("")

    # ===== Top Layer 1 Chapters =====
    report.append("---")
    report.append("")
    report.append("## 2. Purest Layer 1 Chapters (by Purity Score)")
    report.append("")
    report.append("| Rank | Ch. | Title | Purity | L1 | L2 | L3 | In Extract |")
    report.append("|------|-----|-------|--------|----|----|----|-----------:|")
    for rank, a in enumerate(sorted(analyses, key=lambda x: -x.purity_score)[:20], 1):
        marker = "✅" if a.in_layer1_extract else "❌"
        report.append(f"| {rank} | {a.chapter_number} | {a.title[:40]} | {a.purity_score:.2f} | "
                     f"{a.layer1_density:.2f} | {a.layer2_density:.2f} | {a.layer3_density:.2f} | {marker} |")
    report.append("")

    # ===== Most Contaminated =====
    report.append("## 3. Most Contaminated Chapters (by L2+L3 Density)")
    report.append("")
    report.append("| Rank | Ch. | Title | Purity | L1 | L2 | L3 | In Extract |")
    report.append("|------|-----|-------|--------|----|----|----|-----------:|")
    for rank, a in enumerate(sorted(analyses, key=lambda x: x.purity_score)[:20], 1):
        marker = "✅" if a.in_layer1_extract else "❌"
        report.append(f"| {rank} | {a.chapter_number} | {a.title[:40]} | {a.purity_score:.2f} | "
                     f"{a.layer1_density:.2f} | {a.layer2_density:.2f} | {a.layer3_density:.2f} | {marker} |")
    report.append("")

    # ===== Editor Fatigue =====
    report.append("## 4. Editor Fatigue — Highest Intra-Chapter Shifts")
    report.append("")
    report.append("Chapters where Layer 2 vocabulary increases significantly in the second half")
    report.append("relative to Layer 1 (suggesting interpolated material was added to an original core):")
    report.append("")
    shifted = sorted([a for a in analyses if a.layer_shift_score > 0.3],
                    key=lambda x: -x.layer_shift_score)
    if shifted:
        report.append("| Ch. | Title | Shift Score | 1st Half L1 | 2nd Half L1 | 1st Half L2 | 2nd Half L2 |")
        report.append("|-----|-------|-------------|-------------|-------------|-------------|-------------|")
        for a in shifted[:15]:
            report.append(f"| {a.chapter_number} | {a.title[:35]} | {a.layer_shift_score:.3f} | "
                         f"{a.first_half_layer1:.2f} | {a.second_half_layer1:.2f} | "
                         f"{a.first_half_layer2:.2f} | {a.second_half_layer2:.2f} |")
    else:
        report.append("*No significant intra-chapter shifts detected.*")
    report.append("")

    # ===== Gardner Flags =====
    report.append("## 5. Gardner's Editorial Flags")
    report.append("")
    flagged = [a for a in analyses if a.gardner_flags]
    if flagged:
        report.append("| Ch. | Title | Flags |")
        report.append("|-----|-------|-------|")
        for a in sorted(flagged, key=lambda x: x.chapter_number):
            report.append(f"| {a.chapter_number} | {a.title[:40]} | {', '.join(a.gardner_flags)} |")
    else:
        report.append("*No editorial flags detected in Gardner's commentary.*")
    report.append("")

    # ===== NT Citations =====
    report.append("## 6. NT Citation Distribution")
    report.append("")
    cited = [a for a in analyses if a.nt_citations]
    if cited:
        report.append("| Ch. | Title | NT Citations | In Extract |")
        report.append("|-----|-------|-------------|:----------:|")
        for a in sorted(cited, key=lambda x: x.chapter_number):
            marker = "✅" if a.in_layer1_extract else "❌"
            report.append(f"| {a.chapter_number} | {a.title[:40]} | {', '.join(a.nt_citations)} | {marker} |")
    else:
        report.append("*No NT citations detected (footnote markers may not have been captured).*")
    report.append("")

    # ===== Formulaic Openings =====
    report.append("## 7. Formulaic Opening Analysis")
    report.append("")
    with_formula = sum(1 for a in analyses if a.has_formulaic_opening)
    without_formula = n - with_formula
    report.append(f"- Chapters with formulaic opening: **{with_formula}** ({with_formula/n*100:.1f}%)")
    report.append(f"- Chapters without formulaic opening: **{without_formula}** ({without_formula/n*100:.1f}%)")
    report.append("")
    if without_formula > 0:
        report.append("Chapters without standard opening (possible different source):")
        report.append("")
        for a in analyses:
            if not a.has_formulaic_opening:
                report.append(f"- Ch. {a.chapter_number} ({a.title[:50]})")
    report.append("")

    # ===== Full Chapter Data =====
    report.append("---")
    report.append("")
    report.append("## Appendix: Full Chapter Scores")
    report.append("")
    report.append("| Ch. | Title | Words | Purity | L1 | L2 | L3 | TTR | AvgSent | Lacunae | Shift | Extract |")
    report.append("|-----|-------|------:|-------:|---:|---:|---:|----:|--------:|--------:|------:|:-------:|")
    for a in analyses:
        marker = "✅" if a.in_layer1_extract else "❌"
        report.append(f"| {a.chapter_number} | {a.title[:30]} | {a.teaching_words} | {a.purity_score:.2f} | "
                     f"{a.layer1_density:.2f} | {a.layer2_density:.2f} | {a.layer3_density:.2f} | "
                     f"{a.type_token_ratio:.3f} | {a.avg_sentence_length:.1f} | {a.lacunae_density:.2f} | "
                     f"{a.layer_shift_score:.3f} | {marker} |")
    report.append("")

    report_text = "\n".join(report)
    report_path = output_dir / "kephalaia_layer_analysis_report.md"
    report_path.write_text(report_text, encoding="utf-8")
    print(f"  Saved: {report_path.name}")
    return report_text


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    project_root = Path(__file__).parent.parent
    text_path = project_root / "output" / "texts" / "Kephalaia_of_the_Teacher.md"
    output_dir = project_root / "output" / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("KEPHALAIA LAYER ANALYSIS — Multi-Signal Composite Textual Analysis")
    print("=" * 70)
    print()

    # Load text
    print("[1/5] Loading Kephalaia text...")
    text = text_path.read_text(encoding="utf-8")
    print(f"  Loaded: {len(text):,} characters, {len(text.split(chr(10))):,} lines")

    # Parse chapters
    print("[2/5] Parsing chapters...")
    chapters = parse_chapters(text)
    print(f"  Parsed: {len(chapters)} chapters")
    print(f"  Chapter range: {min(c.number for c in chapters)} – {max(c.number for c in chapters)}")

    # Our manual Layer 1 extract chapters (from Kephalaia_Layer_1_Extract.md)
    layer1_chapters = {2, 3, 6, 38, 39, 40, 41, 55, 56, 62, 70, 71, 72, 74, 75, 85, 86, 109, 114, 115, 122}

    # Analyze
    print("[3/5] Running multi-signal analysis...")
    analyses = []
    for chapter in chapters:
        a = analyze_chapter(chapter, layer1_chapters)
        analyses.append(a)
    print(f"  Analyzed: {len(analyses)} chapters")

    # Quick stats
    l1_densities = [a.layer1_density for a in analyses]
    l2_densities = [a.layer2_density for a in analyses]
    print(f"  Avg L1 density: {statistics.mean(l1_densities):.3f} per 100 words")
    print(f"  Avg L2 density: {statistics.mean(l2_densities):.3f} per 100 words")

    # Save raw data
    print("[4/5] Saving raw data...")
    raw_data = []
    for a in analyses:
        d = asdict(a)
        raw_data.append(d)
    raw_path = output_dir / "kephalaia_layer_analysis.json"
    raw_path.write_text(json.dumps(raw_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Saved: {raw_path.name}")

    # Generate report
    print("[5/5] Generating report and visualizations...")
    generate_report(analyses, chapters, output_dir)

    try:
        generate_visualizations(analyses, output_dir)
    except ImportError:
        print("  WARNING: matplotlib not available — skipping visualizations")
        print("  Install with: conda install -c conda-forge matplotlib numpy")

    print()
    print("=" * 70)
    print("ANALYSIS COMPLETE")
    print(f"Output directory: {output_dir}")
    print("=" * 70)


if __name__ == "__main__":
    main()
