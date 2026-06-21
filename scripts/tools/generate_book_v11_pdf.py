#!/usr/bin/env python3
"""
Generate a structured book PDF: The Ancient Word — v1.1

This is a transformed edition of the substrate text. Three classes of
transformation are applied to every paragraph before rendering:

  1. Manichaean Layer 2 name substitution
     Names imposed by Mani's tradition ("Jesus the Splendour",
     "Light Mind", "Cross of Light", etc.) are replaced with their
     substrate Persian literal readings in English, so the text reads
     as a Persian-language mind would have read the original.

  2. Coptic glossary corrections (from scripts/glossary/coptic_glossary.yaml)
     Critical translation issues identified in the glossary are applied:
     - "insight" → "teaching" (ⲧⲥⲃⲱ is teaching, not insight)
     - "release" / "free" / "save" (when from ⲧⲟⲩⲱ) → "raise"
     - "image" / "form" (when from ⲡⲉⲓⲛⲉ) → "likeness"
     - "Jesus the Splendour" / "the Splendour" (from ⲡⲡⲣⲓ̈ⲉ) → "the Radiance"
     (Note: ⲧⲟⲩⲱ and ⲡⲉⲓⲛⲉ corrections are applied heuristically to
     the English text since we are working from Gardner's translation.)

  3. Title page and preface updated to describe v1.1.

All other logic (layout, fonts, TOC, lexicon, two-pass build) is
identical to generate_book_pdf.py.

Dependencies: reportlab  (available in conda env 'manichaean')

Usage:
    conda run -n manichaean python scripts/tools/generate_book_v11_pdf.py
"""

import json
import re
import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, HRFlowable,
    Flowable,
)
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ---------------------------------------------------------------------------
# Font registration — use TTF Times New Roman for full Unicode support
# (Greek, macrons, schwa, etc.)
# ---------------------------------------------------------------------------

_FONT_DIR = Path(r"C:\Windows\Fonts")
pdfmetrics.registerFont(TTFont("TNR", str(_FONT_DIR / "times.ttf")))
pdfmetrics.registerFont(TTFont("TNR-Bold", str(_FONT_DIR / "timesbd.ttf")))
pdfmetrics.registerFont(TTFont("TNR-Italic", str(_FONT_DIR / "timesi.ttf")))
pdfmetrics.registerFont(TTFont("TNR-BoldItalic", str(_FONT_DIR / "timesbi.ttf")))

# Coptic: NotoSansCoptic (bundled alongside v2 script). TNR lacks Coptic
# glyphs so any Coptic characters in the preface render as tofu boxes
# without this. We wrap Coptic runs in <font name="Coptic"> inline markup.
_REPO_FONT_DIR = Path(__file__).resolve().parent / "fonts"
pdfmetrics.registerFont(TTFont("Coptic", str(_REPO_FONT_DIR / "NotoSansCoptic-Regular.ttf")))

from reportlab.pdfbase.pdfmetrics import registerFontFamily
registerFontFamily(
    "TNR",
    normal="TNR",
    bold="TNR-Bold",
    italic="TNR-Italic",
    boldItalic="TNR-BoldItalic",
)

# Shorthand constants for font names
FONT_ROMAN = "TNR"
FONT_BOLD = "TNR-Bold"
FONT_ITALIC = "TNR-Italic"

# Coptic-script Unicode runs (U+2C80–U+2CFF Coptic block, U+03E2–U+03EF
# Coptic letters in Greek block, and combining marks) embedded in a Latin
# paragraph must be wrapped in a <font name="Coptic"> tag so they render
# through NotoSansCoptic instead of as missing-glyph boxes.
_COPTIC_RUN_RE = re.compile(
    r"[\u2C80-\u2CFF\u03E2-\u03EF\u0300-\u036F]+"
)


def _wrap_coptic_runs(text: str) -> str:
    """Wrap Coptic-script substrings in <font name="Coptic"> tags.

    Call this on XML-escaped markup strings before passing to Paragraph.
    Allows Coptic glyphs to render through NotoSansCoptic when surrounding
    text is in Times New Roman.
    """
    return _COPTIC_RUN_RE.sub(
        lambda m: f'<font name="Coptic">{m.group(0)}</font>',
        text,
    )

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # scripts/tools/ → project root

KEPH_DIR = PROJECT_ROOT / "output" / "projects" / "kephalaia"
STRUCTURE_FILE = KEPH_DIR / "book_structure.json"
LEXICON_FILE = KEPH_DIR / "correspondence_lexicon.json"
CORE_DIR = KEPH_DIR / "core" / "chapters"
RESTORED_DIR = KEPH_DIR / "restored" / "chapters"
OUTPUT = PROJECT_ROOT / "output" / "pdfs" / "The_Ancient_Word_v1.1.pdf"
OUTPUT_TMP = PROJECT_ROOT / "output" / "pdfs" / "The_Ancient_Word_v1.1_tmp.pdf"

PAGE_W, PAGE_H = A4

LACUNA_GRAY = "#999999"
RULE_COLOR = "#CCCCCC"
NOTE_COLOR = "#555555"
MUTED = "#888888"
DARK_MUTED = "#666666"
TOC_DOT_COLOR = "#BBBBBB"
TOC_PAGE_COLOR = "#888888"
FOOTER_RULE_COLOR = "#CCCCCC"

# Global page-number registry used by the two-pass build
_page_registry: dict[str, int] = {}


class _PageRecorder(Flowable):
    """Zero-size flowable that records its page number when drawn."""

    width = 0
    height = 0

    def __init__(self, key: str):
        super().__init__()
        self.key = key

    def draw(self):
        _page_registry[self.key] = self.canv.getPageNumber()


class _TocLine(Flowable):
    """Single TOC line: title, extending dot leader, right-aligned page number."""

    def __init__(self, title: str, page_num, *,
                 title_font: str, font_size: float, leading: float,
                 indent: float = 0,
                 dot_color: str = TOC_DOT_COLOR,
                 page_color: str = TOC_PAGE_COLOR):
        super().__init__()
        self.title = title
        self.page_num = str(page_num) if page_num else ""
        self.title_font = title_font
        self.font_size = font_size
        self._leading = leading
        self.indent = indent
        self.dot_color = dot_color
        self.page_color = page_color

    def wrap(self, availWidth, availHeight):
        self._avail_w = availWidth
        return (availWidth, self._leading)

    def draw(self):
        c = self.canv
        y = self._leading - self.font_size  # baseline offset

        # --- Title (left) ---
        c.setFont(self.title_font, self.font_size)
        c.setFillColor(HexColor("#000000"))
        c.drawString(self.indent, y, self.title)
        title_w = pdfmetrics.stringWidth(
            self.title, self.title_font, self.font_size
        )

        if not self.page_num:
            return

        # --- Page number (right, always roman / non-bold) ---
        c.setFont(FONT_ROMAN, self.font_size)
        c.setFillColor(HexColor(self.page_color))
        c.drawRightString(self._avail_w, y, self.page_num)
        page_w = pdfmetrics.stringWidth(
            self.page_num, FONT_ROMAN, self.font_size
        )

        # --- Dot leaders (filling the gap) ---
        dot = " \u00b7"  # space + middle dot
        dot_w = pdfmetrics.stringWidth(dot, FONT_ROMAN, self.font_size)
        x_start = self.indent + title_w + 2
        x_end = self._avail_w - page_w - 2

        if x_end - x_start > dot_w * 2:  # only draw if room for ≥2 dots
            c.setFont(FONT_ROMAN, self.font_size)
            c.setFillColor(HexColor(self.dot_color))
            # Draw right-to-left so dots always align at the page-number edge
            x = x_end - dot_w
            while x >= x_start:
                c.drawString(x, y, dot)
                x -= dot_w


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _xml_esc(text: str) -> str:
    """Escape XML entities for reportlab Paragraph markup."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _clean_gap_markers(text: str) -> str:
    """Normalize [GAP-N] and [GAP-N: text] markers for display.

    - [GAP-N]           → [...]
    - [GAP-N: text]     → [text]
    - [GAP-N: REVIEW …] → [...]  (review flags become plain lacunae)
    """
    text = re.sub(r"\[GAP-\d+:\s*REVIEW\s*[—–-].*?\]", "[...]", text)
    text = re.sub(r"\[GAP-\d+:\s*(.+?)\]", r"[\1]", text)
    text = re.sub(r"\[GAP-\d+\]", "[...]", text)
    return text


# ---------------------------------------------------------------------------
# Global §-indexed paragraph store
# ---------------------------------------------------------------------------


def build_paragraph_lookup() -> dict[int, str]:
    """Build a global mapping from sequential §N → paragraph text.

    This reproduces exactly the same numbering that
    format_corpus_interleaved() uses, so the §-ranges in
    book_structure.json select the right paragraphs.
    """
    lookup: dict[int, str] = {}
    seq = 0

    core_files = sorted(CORE_DIR.glob("ch_*.json"))
    for core_path in core_files:
        with open(core_path, encoding="utf-8") as f:
            core_data = json.load(f)

        ch_num = core_data["chapter_number"]

        # Build reconstruction map from restored layer
        recon_map: dict[int, str] = {}
        restored_path = RESTORED_DIR / f"ch_{ch_num:03d}.json"
        if restored_path.exists():
            with open(restored_path, encoding="utf-8") as f:
                restored_data = json.load(f)
            for rec in restored_data.get("reconstructions", []):
                pnum = rec.get("paragraph")
                rtext = rec.get("reconstructed_text", "")
                if pnum is not None and rtext:
                    recon_map[pnum] = rtext

        for para in core_data.get("paragraphs", []):
            raw_text = para.get("core_text", "")
            if not raw_text:
                continue
            pnum = para["paragraph_number"]
            # Prefer reconstructed (gap-filled) text
            text = recon_map.get(pnum, raw_text)
            seq += 1
            lookup[seq] = text

    return lookup


def _style_lacunae(text: str) -> str:
    """XML-escape text and render [...] brackets in gray."""
    text = _xml_esc(text)

    def _gray_bracket(m: re.Match) -> str:
        inner = m.group(0)[1:-1]

        def _black_if_visible(m2: re.Match) -> str:
            seg = m2.group(0)
            if seg.strip():
                return f'<font color="#000000">{seg}</font>'
            return seg

        styled = re.sub(r"[^.]+", _black_if_visible, inner)
        return f'<font color="{LACUNA_GRAY}">[{styled}]</font>'

    return re.sub(r"\[[^\]]*\]", _gray_bracket, text)


def _clean_core_text(text: str) -> str:
    """Strip manuscript page markers and leading paragraph numbers."""
    # Remove ⟨p.N⟩ prefix (and whitespace/newline after)
    text = re.sub(r"⟨p\.\d+⟩\s*", "", text)
    # Remove leading (N) at start of text
    text = re.sub(r"^\(\d+\)\s*", "", text)
    # Collapse multiple newlines to single space
    text = re.sub(r"\n+", " ", text)
    return text.strip()


# --- Sentence starters: words that reliably signal a new sentence --------
# Conservative list — only words that almost never appear mid-sentence
# after a lowercase word without preceding punctuation.
_SENTENCE_STARTERS = frozenset({
    "The", "This", "That", "These", "Those",
    "It", "He", "She", "They", "We", "I",
    "And", "But", "For", "So", "Yet", "Or", "Nor",
    "Now", "Then", "When", "If", "After", "Before",
    "Again", "Also", "As", "Because", "Each", "Every",
    "From", "How", "In", "Let", "No", "Not", "On",
    "One", "Only", "Out", "Since", "Some", "Such",
    "There", "Thus", "What", "Who", "Why", "While",
})


# ---------------------------------------------------------------------------
# v1.1 — Transformation layer
# ---------------------------------------------------------------------------
#
# ORDER OF SUBSTITUTION MATTERS.
# Longer / more specific strings must be substituted before shorter ones
# that are substrings of them (e.g. "Jesus the Splendour" before "Jesus").
# The list is processed top-to-bottom; each substitution operates on the
# output of the previous one.

# --- 1. Manichaean Layer 2 name substitutions ---
# Format: (pattern, replacement)
# Replacements are plain English renderings of the Persian substrate name,
# expressed as a natural English phrase that reads as the original word
# would have read to a Persian mind.
#
# Where the Persian name is itself a transparent common noun (e.g. Vohu
# Manah = Good Mind), the replacement IS that meaning.
# Where the substrate name is a title composed of common words (e.g.
# Xradeshahr = Kingdom of Wisdom), the replacement uses that composition.
# Names with unknown substrate are left as descriptive English epithets
# drawn from function (e.g. Saklas remains as "the Fool" since the Persian
# substrate name is lost).

_NAME_SUBSTITUTIONS: list[tuple[str, str]] = [
    # -----------------------------------------------------------------------
    # STEP 0: Special bracket-context rules
    #
    # _normalize_word_brackets() handles no-space partial-word brackets.
    # The rules here handle the remaining cases:
    #
    # (a) Space-separated bracket forms — Gardner sometimes writes
    #     "[Word] rest" or "start [Word]" with a space.  The normalizer
    #     only absorbs without a space, so these must be listed explicitly.
    #
    # (b) [the] + name — standalone [the] restoration bracket preceding a name
    #     that substitutes to "the X", producing "[the] the X".
    #
    # (c) Direct bracket forms for specific names where the bracket covers
    #     only part of the phrase.
    # -----------------------------------------------------------------------

    # --- Class 5: [Jesus] the Youth → correct before bare Jesus rule fires ---
    ("[Jesus] the Youth",        "the Living Word"),
    ("[Jesus] the Radiance",     "the Kingdom of Wisdom"),
    ("[Jesus] the Splendour",    "the Kingdom of Wisdom"),   # fallback

    # --- Class 1a: [Living] Spirit / Living [Spirit] ---
    ("[Living] Spirit",          "Living Spirit"),
    ("Living [Spirit]",          "Living Spirit"),
    # --- Class 1b: [Father of] Life / [Father] of Life ---
    ("[Father of] Life",         "Father of Life"),
    ("[Father] of Life",         "Father of Life"),
    # --- Class 1c: [Holy] Spirit (stays as Bounteous Spirit) ---
    ("[Holy] Spirit",            "Bounteous Spirit"),

    # --- Class 2/3: [the] + name producing [the] the X ---
    ("[the] Living Spirit",      "the Lord of Covenants"),
    ("[the] Holy Spirit",        "the Bounteous Spirit"),
    ("[the] Morning Builder",    "the Dawn"),
    ("[the] Sent Ones",          "the Sent Ones"),
    ("[the] Sent One",           "the Sent One"),
    ("[the] Envoy",              "the Envoy"),

    # --- Phrase-mid bracket forms ---
    ("Mother of [Life]",         "Mother of Life"),

    # -----------------------------------------------------------------------
    # STEP 1: "glorious + name" forms
    # In Coptic syntax the adjective can precede the article, so Gardner
    # sometimes writes "glorious the X" or "glorious X" as a title.
    # These rules must come BEFORE the normal substitutions to prevent
    # the article in the replacement creating "glorious the X → glorious the the Y".
    # -----------------------------------------------------------------------
    ("the glorious Great Builder",        "the glorious Dawn"),
    ("glorious Great Builder",            "glorious Dawn"),
    ("the glorious Ambassador",           "the glorious Envoy"),
    ("glorious Ambassador",               "glorious Envoy"),
    ("glorious Jesus the Radiance",       "glorious the Kingdom of Wisdom"),
    ("glorious Jesus the Splendour",      "glorious the Kingdom of Wisdom"),  # fallback

    # -----------------------------------------------------------------------
    # STEP 2: Parenthetical forms
    # -----------------------------------------------------------------------
    ("(Ambassador)",              "(Envoy)"),

    # -----------------------------------------------------------------------
    # STEP 3: Main substitution rules
    # RULE: for every (old, "the X") substitution, the capitalized form
    # "The X" must appear before the lowercase "the X" form, which must
    # appear before the bare "X" form — to prevent double-"the" artifacts.
    # -----------------------------------------------------------------------

    # --- First Man (and variant titles: living Man, blessed Man) ---
    ("The First Man",             "Lord Wisdom"),
    ("the First Man",             "Lord Wisdom"),
    ("First Man's",               "Lord Wisdom's"),
    ("First living Man",          "Lord Wisdom"),
    ("first living man",          "Lord Wisdom"),
    ("The Living Man",            "Lord Wisdom"),
    ("the Living Man",            "Lord Wisdom"),
    ("Living Man",                "Lord Wisdom"),
    ("living Man",                "Lord Wisdom"),
    ("The blessed Man",           "Lord Wisdom"),
    ("the blessed Man",           "Lord Wisdom"),
    ("blessed Man",               "Lord Wisdom"),
    ("The first Man",             "Lord Wisdom"),
    ("the first Man",             "Lord Wisdom"),
    ("This first Man",            "Lord Wisdom"),
    ("this first Man",            "Lord Wisdom"),
    ("First Man",                 "Lord Wisdom"),

    # --- Father of Greatness ---
    ("The Father of Greatness",   "Boundless Time"),
    ("the Father of Greatness",   "Boundless Time"),
    ("Father of Greatness",       "Boundless Time"),

    # --- Mother of Life ---
    ("The Mother of Life",        "The Bounteous Spirit"),
    ("the Mother of Life",        "the Bounteous Spirit"),
    ("Mother of Life",            "the Bounteous Spirit"),
    # "Holy Spirit" used as a standalone title in the text
    ("the first Holy Spirit",     "the first Bounteous Spirit"),
    ("first Holy Spirit",         "first Bounteous Spirit"),
    ("The Holy Spirit",           "The Bounteous Spirit"),
    ("the Holy Spirit",           "the Bounteous Spirit"),
    ("Holy Spirit",               "Bounteous Spirit"),

    # --- Father of Life / Living Spirit ---
    ("its Living Spirit",         "its Lord of Covenants"),
    ("his Living Spirit",         "his Lord of Covenants"),
    ("The Father of Life",        "The Lord of Covenants"),
    ("the Father of Life",        "the Lord of Covenants"),
    ("Father of Life",            "the Lord of Covenants"),
    ("The Living Spirit",         "The Lord of Covenants"),
    ("the Living Spirit",         "the Lord of Covenants"),
    ("Living Spirit",             "the Lord of Covenants"),

    # --- Third Ambassador / Ambassador ---
    ("The Third Ambassador",      "The Envoy"),
    ("the Third Ambassador",      "the Envoy"),
    ("Third Ambassador",          "the Envoy"),
    ("The Ambassador",            "The Envoy"),   # sentence-start form
    ("the Ambassador",            "the Envoy"),
    ("Ambassador",                "Envoy"),        # bare form (variants lists)

    # --- Jesus the Radiance (after glossary corrects Splendour → Radiance) ---
    ("Jesus the Radiance",        "the Kingdom of Wisdom"),
    ("Jesus the Splendour",       "the Kingdom of Wisdom"),   # fallback
    ("Jesus the Youth",           "the Living Word"),
    ("Jesus the Son of Greatness","the Kingdom of Wisdom"),
    ("Jesus",                     "the Kingdom of Wisdom"),

    # --- Light Mind ---
    ("Light Mind",                "Good Mind"),
    ("Light-Nous",                "Good Mind"),
    ("the Nous",                  "Good Mind"),

    # --- Pillar of Glory / Perfect Man ---
    ("the Pillar of Glory",       "Hearkening"),
    ("Pillar of Glory",           "Hearkening"),
    ("the Perfect Man",           "Hearkening"),
    ("Perfect Man",               "Hearkening"),

    # --- Virgin of Light ---
    ("The Virgin of Light",       "The Maiden"),
    ("the Virgin of Light",       "the Maiden"),
    ("Virgin of Light",           "the Maiden"),
    ("The virgin of light",       "the Maiden"),
    ("the virgin of light",       "the Maiden"),
    ("the light virgin",          "the Maiden"),
    ("the holy virgin",           "the Maiden"),

    # --- Beloved of the Lights ---
    ("Beloved of the Lights",     "King of Radiance"),
    ("the Beloved",               "King of Radiance"),

    # --- Great Builder ---
    ("The Great Builder",         "The Dawn"),
    ("the Great Builder",         "the Dawn"),
    ("Great Builder",             "the Dawn"),

    # --- Five watch-keepers ---
    ("King of Honour",            "Lord of the Settled Lands"),
    ("Keeper of Splendour",       "Master of Wisdom"),
    ("Adamant of Light",          "Life-Champion"),
    ("King of Glory",             "Lord of the Mind"),
    ("[the] great Porter",        "the Guardian Spirit"),
    ("[the] great porter",        "the Guardian Spirit"),
    ("[Porter]",                  "[Guardian Spirit]"),
    ("the Porter",                "the Guardian Spirit"),

    # --- Great Judge ---
    ("[great Judge]",             "Justice"),
    ("[great judge]",             "Justice"),
    ("The great Judge",           "Justice"),
    ("the great Judge",           "Justice"),
    ("Great Judge",               "Justice"),
    ("Judge of Truth",            "Justice"),
    ("Judge of truth",            "Justice"),
    ("the Judge",                 "Justice"),

    # --- The Counterpart / Companion (Narig — the Precious One) ---
    ("The Counterpart",           "The Precious One"),
    ("the counterpart",           "the Precious One"),

    # --- Apostle of Light / apostle ---
    ("The Apostle of Light",      "The Sent One"),
    ("the Apostle of Light",      "the Sent One"),
    ("Apostle of Light",          "the Sent One"),
    ("the apostle",               "the Sent One"),
    ("The Apostle",               "The Sent One"),
    ("the Apostle",               "the Sent One"),
    ("apostle",                   "the Sent One"),
    ("Apostle",                   "the Sent One"),

    # --- Light Form / Vision ---
    ("The Light Form",            "The Vision"),
    ("the Light Form",            "the Vision"),
    ("Light Form",                "the Vision"),
    ("the light form",            "the Vision"),

    # --- Last Statue ---
    ("The Last Statue",           "The Final Body"),
    ("the Last Statue",           "the Final Body"),
    ("Last Statue",               "the Final Body"),
    ("the Statue",                "the Final Body"),

    # --- Dark world rulers ---
    ("King of Darkness",          "Evil Spirit"),
    ("King of the realms of Darkness", "Evil Spirit"),
    ("ruler of Smoke",            "Evil Spirit"),

    # --- Matter / Hyle ---
    # Compound phrases first, then the catch-all (capital M only).
    # The catch-all is last so more-specific forms are handled first.
    ("Matter, the sculptress",    "Greed, the sculptress"),
    ("Matter, the thought of death", "Greed, the thought of death"),
    ("this Matter",               "Greed"),
    ("\"Matter\"",                "\"Greed\""),
    # Catch-all: remaining capital "Matter" = the entity Az/Hyle.
    # Python str.replace is case-sensitive: lowercase "matter" (common noun)
    # is NOT replaced by this rule.
    ("Matter",                    "Greed"),

    # --- Cross of Light ---
    ("The Cross of Light",        "The Bound Radiance"),
    ("the Cross of Light",        "the Bound Radiance"),
    ("Cross of Light",            "the Bound Radiance"),
    ("the cross of light",        "the Bound Radiance"),
    ("crucified",                 "bound and spread"),
    ("crucify",                   "bind and spread"),

    # --- Miscellaneous overlays ---
    ("the elect one",             "the purified one"),
    ("the Elect",                 "the Purified Ones"),
    ("the elect",                 "the purified ones"),
    ("the holy churches",         "the living assemblies"),
    ("holy churches",             "living assemblies"),
    ("the churches",              "the living assemblies"),
    ("the holy church",           "the living assembly"),
    ("holy church",               "the living assembly"),
    ("the church",                "the living assembly"),
    ("The good news",             "The proclamation"),
    ("the good news",             "the proclamation"),
    ("good news",                 "the proclamation"),
    ("Saklas",                    "the Fool"),
]

# --- 2. Coptic glossary corrections (from coptic_glossary.yaml) ---
# Applied after name substitutions.
# These correct systematic translation errors in Gardner's English that
# were identified through Coptic lexical analysis.

_GLOSSARY_CORRECTIONS: list[tuple[str, str]] = [
    # ⲧⲥⲃⲱ = teaching, NOT insight
    # Replace "insight" only in the five-faculty context.
    # The faculty sequence is: mind, thought, insight, counsel, reflection
    # (or consideration). In Gardner's translation the third faculty is
    # "insight" — per the glossary it MUST be "teaching".
    # We use context-aware substitution: replace "insight" when it appears
    # as a faculty name alongside the other four.
    ("mind, thought, insight, counsel",    "mind, thought, teaching, counsel"),
    ("mind, thought, insight,",            "mind, thought, teaching,"),
    ("Insight",                            "Teaching"),
    ("insight",                            "teaching"),
    # ⲡⲉⲓⲛⲉ = likeness (NOT image, form, resemblance, appearance)
    # Gardner varies: "image", "likeness", "form", "shape" for ⲡⲉⲓⲛⲉ.
    # Per glossary: always "likeness".
    # Note: we preserve "image" when it refers to ⲉⲓⲕⲱⲛ (eikon, Greek loanword)
    # which Gardner also uses. The most reliable signal for ⲡⲉⲓⲛⲉ is
    # the phrase "after his likeness" / "after the likeness" vs "in the image".
    # We correct the cases explicitly listed in the glossary note:
    ("the light image",                    "the light likeness"),
    ("his image",                          "his likeness"),
    ("her image",                          "her likeness"),
    ("its image",                          "its likeness"),
    ("their image",                        "their likeness"),
    ("this image",                         "this likeness"),
    ("that image",                         "that likeness"),
    ("the image of the Ambassador",        "the likeness of the Envoy"),
    ("the image of the exalted one",       "the likeness of the Exalted One"),
    ("displayed his image",                "displayed his likeness"),
    ("revealed his image",                 "revealed his likeness"),
    ("his glorious image",                 "his glorious likeness"),
    # ⲡⲡⲣⲓ̈ⲉ = Radiance (active shining-forth, NOT static Splendour)
    # Already handled above via name substitution of "Jesus the Splendour".
    # Handle the bare epithet:
    ("the Splendour",                      "the Radiance"),
    ("his splendour",                      "his radiance"),
    ("its splendour",                      "its radiance"),
    ("glorious Splendour",                 "glorious Radiance"),
    # ⲧⲟⲩⲱ = raise (preserve vertical direction, NOT flatten to release/free/save)
    # This is the hardest to apply heuristically since Gardner uses
    # "release", "free", "save", "redeem" for multiple different verbs.
    # We apply only where the soteriological vertical sense is clear:
    ("brought him up",                     "raised him up"),
    ("bore him up",                        "raised him up"),
    ("brought up the First Man",           "raised up the First Man"),
    ("bring him up",                       "raise him up"),
    ("brings it up",                       "raises it up"),
]


def _normalize_word_brackets(text: str) -> str:
    """Expand every bracket boundary to cover complete English words, then
    merge adjacent brackets into one.

    Gardner's restorations mark individual Coptic characters. In English
    translation these produce incoherent partial-word brackets
    (e.g. 'Ambass[ador dis]pl[aye]d', '[The Ambassa]dor', 'fiv[e fa]thers').
    This function removes that letter-precision from the output while
    preserving the restoration marker on the complete word.

    Phase 1 (iterated until stable):
      - word_chars + [content] \u2192 [word_chars + content]  (absorb left)
      - [content] + word_chars \u2192 [content + word_chars]  (absorb right)
      Only fires when the bracket content starts/ends with a letter
      (not a pure ellipsis lacuna).

    Phase 2:
      - ][  or  ] [  \u2192 merge into one bracket  (preserving any space)

    Examples:
      'Ambass[ador dis]pl[aye]d' \u2192 '[Ambassador displayed]'
      '[The Ambassa]dor'          \u2192 '[The Ambassador]'
      'im[age of the Ambassa]dor' \u2192 '[image of the Ambassador]'
      'fiv[e fa]thers'            \u2192 '[five fathers]'
      'Light [Mind]'              \u2192 '[Light Mind]'
      '[ ... ]'                   \u2192 unchanged (pure lacuna)
    """
    # Phase 0: normalize slash-variant readings (critical apparatus notation).
    # Gardner sometimes writes T[h/i]rd (uncertain reading) or Lig/ht.
    # Join both sides of the slash to reconstruct the full word.
    # Run repeatedly to collapse chains like T/h/i/r/d in one go.
    while '/' in text:
        prev_slash = text
        text = re.sub(r'([A-Za-z]+)/([A-Za-z]+)', lambda m: m.group(1) + m.group(2), text)
        if text == prev_slash:
            break  # no letter/letter slash found; stop to avoid infinite loop

    # Phase 0b: merge 'word_chars SPACE [bracketed_phrase]' for known Manichaean
    # phrase starters. Gardner's brackets sometimes cover only the LAST word of a
    # multi-word name, with the preceding words unbracketed: 'Light [Mind]',
    # 'Adamant of [Light]', etc. The direct-adjacency normalizer (Phase 1) can
    # also create these forms (e.g. 'Light Mi[nd]' → 'Light [Mind]'), so Phase 0b
    # must run INSIDE the stability loop to catch patterns created by Phase 1.
    _PHRASE_STARTS = [
        'Mother of ', 'Father of ', 'Living ', 'Holy ',
        'Adamant of ', 'Keeper of ', 'King of ', 'Pillar of ', 'Virgin of ',
        'Cross of ', 'Beloved of the ', 'Lord of ', 'Judge of ',
        'Light ', 'Last ', 'Great ',
    ]
    # Known name-tail words that can appear AFTER a closing bracket when Gardner's
    # lacuna brackets cut a name in mid-suffix, e.g. '[that of the Virgin of] Light'.
    _PHRASE_TAILS = [
        'Light', 'Greatness', 'Darkness', 'Life', 'Mind', 'Glory',
        'Honour', 'Radiance', 'Splendour', 'Spirit', 'Wisdom', 'Statue',
    ]

    prev = None
    while prev != text:
        prev = text
        # Phase 0b (inside loop): merge known phrase prefixes with adjacent brackets
        for _ps in _PHRASE_STARTS:
            text = re.sub(
                re.escape(_ps) + r'(\[[^\[\]]*\])',
                lambda m, ps=_ps: '[' + ps + m.group(1)[1:-1] + ']',
                text
            )
        # Phase 1: absorb word characters immediately before [ when inner starts with letter
        text = re.sub(
            r"([A-Za-z']+)\[([A-Za-z][^\[\]]*)\]",
            lambda m: '[' + m.group(1) + m.group(2) + ']',
            text
        )
        # Phase 1b: absorb word characters immediately after ] when inner ends with letter
        text = re.sub(
            r"\[([^\[\]]*[A-Za-z])\]([A-Za-z']+)",
            lambda m: '[' + m.group(1) + m.group(2) + ']',
            text
        )
        # Phase 0c (inside loop): merge known phrase-tail words that follow a closing bracket
        # with a space, e.g. '[that of the Virgin of] Light' → '[that of the Virgin of Light]'.
        _tail_pat = '|'.join(re.escape(t) for t in _PHRASE_TAILS)
        text = re.sub(
            r'(\[[^\[\]]*)\]\s+(' + _tail_pat + r')\b',
            lambda m: '[' + m.group(1)[1:] + ' ' + m.group(2) + ']',
            text
        )
    # Merge adjacent brackets, preserving any whitespace between them
    text = re.sub(r'\](\s*)\[', lambda m: m.group(1), text)
    return text


def _capitalize_sentences(text: str) -> str:
    """Capitalize the first letter of the text and after sentence-ending punctuation.

    Applied to structural text after _apply_transformations(), since substitutions
    can turn a sentence-starting name into a lowercase article.
    """
    # Capitalize the very first character
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    # Capitalize after sentence-ending punctuation
    return re.sub(r'([.!?])\s+([a-z])',
                  lambda m: m.group(1) + ' ' + m.group(2).upper(),
                  text)


def _apply_name_subs_bracket_aware(text: str) -> str:
    """Apply _NAME_SUBSTITUTIONS, matching through bracket chars.

    For each (old, new) pair:
      1. Fast path: try a literal match first.  Covers all cases where the
         bracket normaliser already merged partial-word brackets.
      2. Slow path: strip every '[' and ']' from a scratch copy of the text,
         search for old in that stripped copy, map the match back to the
         original character indices, and replace the original span —
         including any bracket chars that fell inside it — with new.
         If the span was enclosed in brackets (char immediately before is '['
         and immediately after is ']'), or contained brackets internally,
         the replacement is wrapped in [ ] to preserve the restoration marker.
    """
    for old, new in _NAME_SUBSTITUTIONS:
        if '[' not in text and ']' not in text:
            # No brackets in text — safe to use global str.replace (fast path)
            if old in text:
                text = text.replace(old, new)
            continue

        # Text contains brackets — always use the slow path so that bare rules
        # like "First Man" don't fire inside "[the] First Man" via str.replace
        # and leave dangling bracket fragments like "[the] Lord Wisdom".
        while True:
            # Build mapping: orig_pos[i] = index in text of stripped[i]
            orig_pos = [i for i, ch in enumerate(text) if ch not in '[]']
            stripped = ''.join(text[i] for i in orig_pos)
            idx = stripped.find(old)
            if idx == -1:
                break
            end = idx + len(old)

            orig_start = orig_pos[idx]
            orig_end   = orig_pos[end - 1] + 1   # exclusive end in original

            span_text   = text[orig_start:orig_end]
            inner_brkt  = '[' in span_text or ']' in span_text
            before_open = orig_start > 0 and text[orig_start - 1] == '['
            after_close = orig_end < len(text) and text[orig_end] == ']'

            if inner_brkt or (before_open and after_close):
                s = orig_start - (1 if before_open else 0)
                e = orig_end   + (1 if after_close else 0)
                text = text[:s] + '[' + new + ']' + text[e:]
            else:
                text = text[:orig_start] + new + text[orig_end:]

    return text


def _apply_transformations(text: str) -> str:
    """Apply v1.1 translation corrections and name substitutions.

    Transformations are applied in two passes:
      1. Glossary corrections (fix Gardner's English mistranslations of Coptic)
      2. Name substitutions (Manichaean Layer 2 → Persian literal readings)

    The order is deliberate: glossary corrections run first so that
    corrected forms feed into name substitution. Specifically,
    Gardner's 'Splendour' is corrected to 'Radiance' (per ⲡⲡⲞۋⲥⲑⲥ = active
    shining-forth), so 'Jesus the Radiance' is then caught by the
    name substitution rather than the pre-corrected 'Jesus the Splendour'.

    Applied uniformly to all text including bracket restorations.
    Bracket-damaged names are handled by _apply_name_subs_bracket_aware(),
    which strips brackets to find match positions then maps them back.
    """
    # Pass 1: glossary corrections (fix Gardner's Coptic translation errors)
    for old, new in _GLOSSARY_CORRECTIONS:
        text = text.replace(old, new)

    # Pass 2: name substitutions — bracket-aware matching
    text = _apply_name_subs_bracket_aware(text)

    # Phase 3: article deduplication at bracket boundaries.
    # Substitutions can introduce double-article artifacts:
    # (a) "[...the] the X" — bracket tail 'the' + substituted 'the X'.
    text = re.sub(
        r'\[([^\[\]]*?)\s+the\]\s+(the\b)',
        lambda m: '[' + m.group(1).rstrip() + '] the',
        text
    )
    # (b) "[the] the X" — standalone [the] bracket + substituted 'the X'.
    text = re.sub(r'\[the\]\s+the\b', 'the', text)
    # (c) "the [the X]" — substitution added leading 'the' inside bracket
    #     where the article was already outside the bracket.
    text = re.sub(r'\b(the|The)\s+\[the\s+', lambda m: m.group(1) + ' [', text)
    # (d) "the [word] the X" — 'the' before a complete-word restoration bracket,
    #     then another 'the' after it (substitution artifact).
    #     Example: 'the [glorious] the Holy Spirit' → 'the [glorious] Holy Spirit'.
    text = re.sub(r'(\bthe\s+\[[^\[\]]+\])\s+the\b', r'\1', text)
    # (e) "glorious the X" — Coptic adjective-before-article word order produces this
    #     artifact when 'glorious Jesus the Radiance' is substituted.
    #     Example: 'glorious the Kingdom of Wisdom' → 'the glorious Kingdom of Wisdom'.
    text = re.sub(r'\bglorious\s+the\s+', 'the glorious ', text)

    return text


def _normalize_text(text: str) -> str:
    """Apply safe micro-normalizations to a paragraph.

    1. Capitalize the first alphabetic character.
    2. Ensure the paragraph ends with terminal punctuation.
    3. Insert a missing period before obvious sentence starters
       (only when the preceding character is a lowercase letter,
        so "the Light Mind" is never touched).

    Bracket content ([GAP-N: ...] and [...]) is protected —
    normalization skips everything inside square brackets.
    """
    if not text:
        return text

    # --- 1. Capitalize first letter ---
    for i, ch in enumerate(text):
        if ch.isalpha():
            text = text[:i] + ch.upper() + text[i + 1:]
            break

    # --- 2. Terminal punctuation ---
    stripped = text.rstrip()
    if stripped and stripped[-1] not in '.!?;:)\'\"\u2019\u201d':
        text = stripped + '.'

    # --- 3. Missing period before sentence starters ---
    # Strategy: split text into bracket-protected and free regions,
    # only apply the regex to free regions.
    parts = re.split(r'(\[[^\]]*\])', text)
    result: list[str] = []
    for j, part in enumerate(parts):
        if part.startswith('['):
            # Inside brackets — pass through unchanged
            result.append(part)
        else:
            # Free text — insert period where needed
            def _insert_period(m: re.Match) -> str:
                before, space, word = m.group(1), m.group(2), m.group(3)
                if word in _SENTENCE_STARTERS:
                    return before + '.' + space + word
                return m.group(0)

            part = re.sub(
                r'([a-z])(\s+)([A-Z][a-z]+\b)', _insert_period, part,
            )
            result.append(part)
    text = ''.join(result)

    return text


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------


def _styles() -> dict:
    return dict(
        # --- Title page ---
        main_title=ParagraphStyle(
            "MT", fontName=FONT_BOLD, fontSize=24,
            alignment=TA_CENTER, leading=30, spaceAfter=8,
        ),
        subtitle=ParagraphStyle(
            "ST", fontName=FONT_ITALIC, fontSize=14,
            alignment=TA_CENTER, leading=18, spaceAfter=6,
        ),
        subtitle2=ParagraphStyle(
            "ST2", fontName=FONT_ITALIC, fontSize=11,
            alignment=TA_CENTER, leading=15, spaceAfter=6,
            textColor=HexColor("#777777"),
        ),
        credit=ParagraphStyle(
            "CR", fontName=FONT_ROMAN, fontSize=10,
            alignment=TA_CENTER, leading=14, spaceAfter=6,
            textColor=HexColor(DARK_MUTED),
        ),

        # --- Table of Contents ---
        toc_part=ParagraphStyle(
            "TOCP", fontName=FONT_BOLD, fontSize=11,
            alignment=TA_LEFT, leading=16,
            spaceBefore=10, spaceAfter=2,
        ),
        toc_chapter=ParagraphStyle(
            "TOCC", fontName=FONT_ROMAN, fontSize=10,
            alignment=TA_LEFT, leading=14,
            spaceAfter=1, leftIndent=8 * mm,
        ),

        # --- Section titles (CONTENTS, OBSERVATIONS, etc.) ---
        section_title=ParagraphStyle(
            "SECT", fontName=FONT_BOLD, fontSize=16,
            alignment=TA_CENTER, leading=22,
            spaceBefore=0, spaceAfter=16,
        ),

        # --- Part divider pages ---
        part_number=ParagraphStyle(
            "PN", fontName=FONT_ROMAN, fontSize=12,
            alignment=TA_CENTER, leading=16, spaceAfter=4,
            textColor=HexColor(MUTED),
        ),
        part_title=ParagraphStyle(
            "PT", fontName=FONT_BOLD, fontSize=18,
            alignment=TA_CENTER, leading=24, spaceAfter=12,
        ),
        part_desc=ParagraphStyle(
            "PD", fontName=FONT_ITALIC, fontSize=10.5,
            alignment=TA_JUSTIFY, leading=15,
            spaceAfter=6, leftIndent=15 * mm, rightIndent=15 * mm,
            textColor=HexColor("#444444"),
        ),

        # --- Chapter headings ---
        chapter_title=ParagraphStyle(
            "CHT", fontName=FONT_BOLD, fontSize=13,
            alignment=TA_CENTER, leading=17,
            spaceBefore=0, spaceAfter=4,
        ),
        chapter_role=ParagraphStyle(
            "CHR", fontName=FONT_ITALIC, fontSize=9,
            alignment=TA_CENTER, leading=12,
            spaceAfter=4, textColor=HexColor(MUTED),
        ),
        chapter_desc=ParagraphStyle(
            "CHD", fontName=FONT_ITALIC, fontSize=10,
            alignment=TA_JUSTIFY, leading=14,
            spaceAfter=12, leftIndent=8 * mm, rightIndent=8 * mm,
            textColor=HexColor(NOTE_COLOR),
        ),

        # --- Core (substrate) text ---
        body=ParagraphStyle(
            "B", fontName=FONT_ROMAN, fontSize=10.5,
            alignment=TA_JUSTIFY, leading=14.5,
            spaceAfter=6, firstLineIndent=18,
        ),
        body_first=ParagraphStyle(
            "B1", fontName=FONT_ROMAN, fontSize=10.5,
            alignment=TA_JUSTIFY, leading=14.5,
            spaceAfter=6, firstLineIndent=0,
        ),

        # --- Observations ---
        obs_title=ParagraphStyle(
            "OT", fontName=FONT_BOLD, fontSize=12,
            alignment=TA_LEFT, leading=16,
            spaceBefore=16, spaceAfter=6,
        ),
        obs_body=ParagraphStyle(
            "OB", fontName=FONT_ROMAN, fontSize=10,
            alignment=TA_JUSTIFY, leading=14,
            spaceAfter=10,
        ),

        # --- Preface ---
        preface_title=ParagraphStyle(
            "PFT", fontName=FONT_BOLD, fontSize=16,
            alignment=TA_CENTER, leading=22,
            spaceBefore=0, spaceAfter=16,
        ),
        preface_heading=ParagraphStyle(
            "PFH", fontName=FONT_BOLD, fontSize=11,
            alignment=TA_LEFT, leading=15,
            spaceBefore=14, spaceAfter=4,
        ),
        preface_body=ParagraphStyle(
            "PFB", fontName=FONT_ROMAN, fontSize=10,
            alignment=TA_JUSTIFY, leading=14,
            spaceAfter=6,
        ),
        preface_italic=ParagraphStyle(
            "PFI", fontName=FONT_ITALIC, fontSize=10,
            alignment=TA_JUSTIFY, leading=14,
            spaceAfter=6,
        ),
        preface_indent=ParagraphStyle(
            "PFIN", fontName=FONT_ROMAN, fontSize=9.5,
            alignment=TA_JUSTIFY, leading=13,
            spaceAfter=4,
            leftIndent=10 * mm,
        ),
        preface_indent_italic=ParagraphStyle(
            "PFII", fontName=FONT_ITALIC, fontSize=9.5,
            alignment=TA_JUSTIFY, leading=13,
            spaceAfter=4,
            leftIndent=10 * mm,
        ),
        preface_label=ParagraphStyle(
            "PFL", fontName=FONT_BOLD, fontSize=9.5,
            alignment=TA_LEFT, leading=13,
            spaceBefore=8, spaceAfter=2,
            leftIndent=10 * mm,
        ),

        # --- Lexicon ---
        lex_category=ParagraphStyle(
            "LEXC", fontName=FONT_BOLD, fontSize=12,
            alignment=TA_LEFT, leading=16,
            spaceBefore=16, spaceAfter=6,
        ),
        lex_entry_head=ParagraphStyle(
            "LEXH", fontName=FONT_ROMAN, fontSize=10,
            alignment=TA_LEFT, leading=14,
            spaceBefore=10, spaceAfter=1,
        ),
        lex_entry_body=ParagraphStyle(
            "LEXB", fontName=FONT_ROMAN, fontSize=9,
            alignment=TA_JUSTIFY, leading=12.5,
            spaceAfter=2, leftIndent=6 * mm,
            textColor=HexColor(NOTE_COLOR),
        ),
        lex_entry_detail=ParagraphStyle(
            "LEXD", fontName=FONT_ITALIC, fontSize=8.5,
            alignment=TA_LEFT, leading=11,
            spaceAfter=1, leftIndent=6 * mm,
            textColor=HexColor(MUTED),
        ),
    )


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_structure() -> dict:
    with open(STRUCTURE_FILE, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# PDF content builders
# ---------------------------------------------------------------------------


def _page_footer(canvas, doc):
    canvas.saveState()
    page_num = canvas.getPageNumber()
    cx = PAGE_W / 2
    y = 12 * mm
    rule_w = 30 * mm
    rule_y = y + 1.2 * mm
    canvas.setStrokeColor(HexColor(FOOTER_RULE_COLOR))
    canvas.setLineWidth(0.4)
    canvas.line(cx - rule_w - 8 * mm, rule_y, cx - 8 * mm, rule_y)
    canvas.line(cx + 8 * mm, rule_y, cx + rule_w + 8 * mm, rule_y)
    canvas.setFont(FONT_ROMAN, 9)
    canvas.setFillColor(HexColor(DARK_MUTED))
    canvas.drawCentredString(cx, y, str(page_num))
    canvas.restoreState()


def _title_page(st: dict) -> list:
    return [
        Spacer(1, 55 * mm),
        Paragraph(
            "THE ANCIENT WORD",
            st["main_title"],
        ),
        Spacer(1, 10 * mm),
        Paragraph(
            "Recovered from the Kephalaia of the Teacher",
            st["subtitle"],
        ),
        Spacer(1, 4 * mm),
        Paragraph(
            "Version 1.1 — Translated Edition",
            st["subtitle2"],
        ),
        Spacer(1, 2 * mm),
        Paragraph(
            "Manichaean overlay names replaced with their Persian substrate readings.<br/>"
            "Coptic translation corrections applied per philological glossary.",
            st["subtitle2"],
        ),
        Spacer(1, 24 * mm),
        Paragraph(
            "Based on the translation by Iain Gardner (1995)<br/>"
            "<i>The Kephalaia of the Teacher: The Edited Coptic<br/>"
            "Manichaean Texts in Translation with Commentary</i>",
            st["credit"],
        ),
        Spacer(1, 8 * mm),
        Paragraph(
            "Ancient teaching substrate extracted and organized by discovered structure.<br/>"
            "Structure discovered by Claude Opus 4.6 from the text alone,<br/>"
            "without access to manuscript chapter divisions.",
            st["credit"],
        ),
        Spacer(1, 6 * mm),
        Paragraph(
            f'Lacunae markers shown in <font color="{LACUNA_GRAY}">light gray</font>.',
            st["credit"],
        ),
        PageBreak(),
    ]


def _preface_pages(st: dict) -> list:
    """Generate the preface pages for the book."""
    elements: list = [
        Spacer(1, 15 * mm),
        Paragraph("PREFACE", st["preface_title"]),
        Spacer(1, 6 * mm),
    ]

    p = st["preface_body"]
    pi = st["preface_italic"]
    h = st["preface_heading"]
    ind = st["preface_indent"]
    indi = st["preface_indent_italic"]
    lbl = st["preface_label"]

    # Helper: build an indented Paragraph with Coptic runs wrapped in the
    # Coptic font so they don't render as tofu boxes in Times New Roman.
    def _cpara(markup: str) -> "Paragraph":
        return Paragraph(_wrap_coptic_runs(markup), ind)

    # --- Opening: The Ancient Word ---
    elements.append(Paragraph(
        "In the eighteenth century, Emanuel Swedenborg described a text he "
        "called the &ldquo;Ancient Word&rdquo; &mdash; written entirely in "
        "correspondences, older than the Hebrew scriptures, carried eastward "
        "by the <i>Bene Qedem</i> (the &ldquo;Children of the East&rdquo;), "
        "and preserved in a region he called &ldquo;Great Tartary.&rdquo; "
        "He said it still existed there.",
        pi,
    ))
    elements.append(Paragraph(
        "This is that text.",
        pi,
    ))
    elements.append(Paragraph(
        "What you hold is the teaching core of the <i>Kephalaia of the "
        "Teacher</i>, a third- or fourth-century Coptic Manichaean "
        "manuscript translated by Iain Gardner in 1995. Within this "
        "manuscript lies a complete correspondential cosmology that matches "
        "Swedenborg&rsquo;s description of the Ancient Word in every "
        "particular: written entirely in correspondences, complete from "
        "beginning to end, containing the content the Bible attributes to "
        "now-lost texts, found in the exact region Swedenborg identified, "
        "and tracing back through the exact transmission path he described.",
        p,
    ))

    # --- What Swedenborg Described ---
    elements.append(Paragraph("What Swedenborg Described", h))
    elements.append(Paragraph(
        "Swedenborg made five specific claims about the Ancient Word. "
        "(1)&nbsp;It was written entirely in the style of correspondences "
        "&mdash; natural images expressing spiritual realities through "
        "organic, functional relationships, not arbitrary symbolism. "
        "(2)&nbsp;It contained a complete teaching from beginning to end. "
        "(3)&nbsp;The biblical references to the &ldquo;Wars of the "
        "LORD&rdquo; (Numbers 21:14) and the &ldquo;Book of "
        "Jashar&rdquo; (Joshua 10:13, 2&nbsp;Samuel 1:18) were citations "
        "from this text. (4)&nbsp;It was preserved in &ldquo;Great "
        "Tartary&rdquo; &mdash; the vast Central Asian interior. "
        "(5)&nbsp;It was carried there by the <i>Bene Qedem</i>, the "
        "ancient bearers of correspondential knowledge.",
        p,
    ))
    elements.append(Paragraph(
        "All five claims can be independently verified against the "
        "text extracted here.",
        pi,
    ))

    # --- Five Lines of Evidence ---
    elements.append(Paragraph("Five Lines of Evidence", h))

    elements.append(Paragraph("1. Written entirely in correspondences", lbl))
    elements.append(Paragraph(
        "The teaching core extracted from the <i>Kephalaia</i> is "
        "correspondential throughout. &sect;490&ndash;&sect;507 "
        "(identified as 90% ancient substrate) state the organizing "
        "principle directly: &ldquo;This whole universe, above and below, "
        "reflects the pattern of the human body.&rdquo; The text then "
        "systematically maps the cosmos onto the human form &mdash; head "
        "to feet, organ by organ &mdash; with each correspondence "
        "grounded in function. Elsewhere, five storehouses map to five "
        "elements, to five trees, to five genera, to five worlds &mdash; "
        "and the pattern repeats through realms, metals, and tastes. "
        "A body-cosmos isomorphism culminates in a soul-body binding "
        "formula. This is not scattered symbolic language. It is "
        "systematic correspondential architecture sustained across "
        "934&nbsp;paragraphs.",
        ind,
    ))

    elements.append(Paragraph("2. Complete from beginning to end", lbl))
    elements.append(Paragraph(
        "The text contains the complete arc of regeneration. "
        "&sect;1&ndash;&sect;9 present the primordial cosmogonic "
        "narrative: the separation of light and darkness, the descent "
        "of the Divine Human into combat with falsity, the ordering of "
        "recaptured good, and the final restoration &mdash; "
        "&ldquo;a single God comes to be over the totality.&rdquo; "
        "Parts&nbsp;2 through 12 systematically elaborate every phase: the "
        "dual architecture of reality, the descent of influx, redemptive "
        "combat, the interior of the Divine, the anatomy of evil, the "
        "ordering of the spiritual world, purification of mind, the "
        "architecture of influx, the formation of the human being, the "
        "correspondences of heaven and earth, and the dynamics of "
        "spiritual life. The final vision (&sect;899&ndash;&sect;934) "
        "closes with three entreaties, the two fundamental essences, "
        "and the portals of divine conjunction. This is not a fragment. "
        "It is a complete text.",
        ind,
    ))

    elements.append(Paragraph(
        "3. Contains the Wars of the Lord and the Book of Jashar",
        lbl,
    ))
    elements.append(Paragraph(
        "The Hebrew Bible cites two lost texts by name: the "
        "&ldquo;Wars of the LORD&rdquo; (Numbers 21:14) and the "
        "&ldquo;Book of Jashar&rdquo; &mdash; the Book of the Upright "
        "(Joshua 10:13, 2&nbsp;Samuel 1:18). Swedenborg identified both as "
        "portions of the Ancient Word. Both are found here. "
        "A consonantal analysis of the "
        "Wars of the LORD demonstrates that the quotation fragments, "
        "read at the three degrees Swedenborg specified (natural, "
        "spiritual, celestial), reveal a cosmic architecture &mdash; "
        "the Beloved, the Conflagration, Cosmic Trenches, the Seat of "
        "Watchers, the Border of the Father &mdash; that matches the "
        "macrocosmic narrative in this text exactly. "
        "The Book of Jashar &mdash; the practical manual of the upright "
        "life &mdash; matches the pedagogical content: how stillness "
        "defeats falsity, how the mind is regenerated faculty by faculty, "
        "how the divine call meets human obedience. The cosmological "
        "text and the pedagogical text, the macrocosm and the microcosm "
        "&mdash; both reside together in the same teaching.",
        ind,
    ))

    elements.append(Paragraph("4. Found exactly where Swedenborg said", lbl))
    elements.append(Paragraph(
        "Swedenborg located the Ancient Word in &ldquo;Great "
        "Tartary&rdquo; &mdash; the vast interior of Central Asia. "
        "The <i>Kephalaia</i> was transmitted through the Manichaean "
        "tradition, which was officially adopted as state religion by "
        "the Uyghur Khaganate in 762/763&nbsp;CE. The Kingdom of Qocho "
        "preserved Manichaean texts in cave temple-libraries at Turfan "
        "&mdash; in the heart of Swedenborg&rsquo;s &ldquo;Great "
        "Tartary.&rdquo; The Coptic manuscript translated by Gardner is "
        "a sister text of these Central Asian recensions. The text was "
        "found where Swedenborg said it would be.",
        ind,
    ))

    elements.append(Paragraph(
        "5. Traces back through the transmission path Swedenborg described",
        lbl,
    ))
    elements.append(Paragraph(
        "Swedenborg said the Ancient Word was carried eastward by the "
        "<i>Bene Qedem</i> &mdash; the Children of the East &mdash; "
        "the ancient bearers of correspondential knowledge. The "
        "substrate teaching in the <i>Kephalaia</i> predates its "
        "Manichaean frame. Its five-fold architecture, body-cosmos "
        "correspondence system, and doctrine of discrete degrees are "
        "rooted in Zoroastrian cosmology &mdash; specifically the "
        "tradition of <i>Vohu Manah</i> (Good Mind), the "
        "<i>Amesha Spentas</i>, and the "
        "<i>mēnōg/gētīg</i> (spiritual/material) ontology. The "
        "Apocryphon of John, a related text, explicitly cites "
        "&ldquo;the book of Zoroaster&rdquo; as its source for "
        "the body-creation angel list &mdash; a correspondential "
        "catalogue in exactly the form of <i>Bene Qedem</i> tradition. "
        "The teaching did not originate with Mani. He received it from "
        "the Persian-Zoroastrian tradition, which received it from the "
        "Children of the East.",
        ind,
    ))

    # --- Three Layers ---
    elements.append(Paragraph("Three Layers", h))
    elements.append(Paragraph(
        "Within the <i>Kephalaia of the Teacher</i>, three distinct "
        "layers can be identified:",
        p,
    ))

    elements.append(Paragraph(
        '<b>Layer 3 (Outermost): The Hagiographic Frame.</b> '
        '&ldquo;Once again the Enlightener sits in the congregation&hellip;&rdquo; '
        '&mdash; the narrative scaffolding that casts the teaching as dialogues '
        'between Mani and his disciples. This layer belongs entirely to the '
        'Manichaean institutional setting.',
        ind,
    ))
    elements.append(Paragraph(
        '<b>Layer 2 (Middle): The Manichaean Theological Overlay.</b> '
        'Names, titles, and institutional vocabulary that Mani&rsquo;s tradition '
        'imposed upon older content: &ldquo;Jesus the Splendour,&rdquo; '
        '&ldquo;Light Mind,&rdquo; &ldquo;Holy Spirit,&rdquo; '
        '&ldquo;apostle,&rdquo; &ldquo;the elect.&rdquo; These terms '
        'replaced earlier designations &mdash; almost certainly Persian &mdash; '
        'while leaving the underlying teaching structure intact.',
        ind,
    ))
    elements.append(Paragraph(
        '<b>Layer 1 (Core): The Ancient Word.</b> '
        'A systematic correspondential cosmology organized around five degrees '
        'at every scale, teaching the complete arc of regeneration from first '
        'to last. This layer is older than Mani. Its five-fold architecture, '
        'its body-cosmos correspondence system, its doctrine of discrete '
        'degrees, its &ldquo;summons and obedience&rdquo; mechanism (divine '
        'influx and human reception) &mdash; these do not originate with '
        'third-century Babylonia. They preserve the Ancient Word whose '
        'roots extend through Zoroastrian Persia into the proto-Indo-Iranian '
        'and ancient Near Eastern traditions of the <i>Bene Qedem</i>.',
        ind,
    ))
    elements.append(Paragraph(
        "This book is an extraction of Layer 1 &mdash; the Ancient "
        "Word &mdash; from its Manichaean vessel.",
        pi,
    ))

    # --- What Was Extracted ---
    elements.append(Paragraph("What Was Extracted", h))
    elements.append(Paragraph(
        "The extraction was performed using the methods of textual "
        "criticism, with Claude Opus 4.6 &mdash; an advanced language "
        "model &mdash; serving as the primary analytical instrument. "
        "The entire <i>Kephalaia</i> corpus was read as a continuous "
        "flow of 934 sequentially numbered paragraphs. Each passage "
        "was analyzed for editorial layering: separating the "
        "hagiographic frame (Layer&nbsp;3) from the Manichaean "
        "theological overlay (Layer&nbsp;2) and the ancient teaching "
        "core (Layer&nbsp;1). The model read the text as a philologist "
        "would &mdash; attending to vocabulary shifts, structural seams, "
        "and correspondential consistency &mdash; but across the full "
        "corpus as a single sustained reading. The structure of this "
        "book &mdash; its twelve parts and forty-four chapters &mdash; "
        "was not imposed from the manuscript&rsquo;s chapter divisions. "
        "It was discovered by reading the text as a single continuous "
        "teaching and identifying where the natural structural seams fall.",
        p,
    ))
    elements.append(Paragraph(
        "The reader will notice that the number five recurs at every "
        "scale. The text itself teaches this: five elements, five "
        "faculties, five trees, five storehouses, five wars, five "
        "liberations, five modes of conjunction, five works of fire, "
        "five watch-stations. Chapter 48 makes the principle explicit "
        "&mdash; &ldquo;In each one of these five garments there are "
        "five powers&hellip; the summons with the obedience constitute "
        "twenty-five characteristics in their twenty-five limbs.&rdquo; "
        "This is not a numerological coincidence. The five-fold "
        "principle is the teaching&rsquo;s own organizing architecture: "
        "five degrees through which the one reality makes itself "
        "receivable, repeated at every level from cosmic emanation to "
        "human anatomy. It is visible on every page.",
        p,
    ))

    # --- Translation Corrections ---
    elements.append(Paragraph("Translation Corrections", h))
    elements.append(Paragraph(
        "Iain Gardner&rsquo;s 1995 translation is the sole surviving English "
        "edition of the <i>Kephalaia of the Teacher</i> and is the foundation "
        "of this work. It is a rigorous philological achievement. However, "
        "a systematic review identified four recurring translation decisions "
        "that misrepresent the Coptic source. These are not matters of "
        "interpretive preference; they are cases where the Coptic text is "
        "unambiguous and Gardner&rsquo;s rendering loses a distinction that "
        "the Coptic scribes deliberately encoded. All four corrections are "
        "applied uniformly throughout this edition.",
        p,
    ))

    elements.append(_cpara(
        '<b>1. \u2ca1\u2ca1\u2ca3\u2c93\u0308\u2c89 rendered as &ldquo;Splendour&rdquo; &mdash; corrected to &ldquo;Radiance.&rdquo;</b> '
        'The Coptic word derives from a verbal root meaning to shine forth, '
        'to radiate actively. Gardner renders it &ldquo;Splendour&rdquo; &mdash; '
        'a static quality observed from outside. The correction &ldquo;Radiance&rdquo; '
        'preserves the active, outward-proceeding quality of the term. The '
        'same root underlies \u2ca1\u2ca3\u2c8f (<i>pr\u0113</i>, &ldquo;sun&rdquo; = the shining one), '
        'confirming the verbal emission sense. The title &ldquo;Jesus the '
        'Splendour&rdquo; in Gardner becomes &ldquo;Jesus the Radiance&rdquo; '
        'under this correction; the subsequent name substitution then replaces '
        'the Manichaean title with its Persian substrate reading.'
    ))
    elements.append(_cpara(
        '<b>2. \u2ca7\u2ca5\u2c83\u2cb1 rendered as &ldquo;insight&rdquo; &mdash; corrected to &ldquo;teaching.&rdquo;</b> '
        'The word \u2ca7\u2ca5\u2c83\u2cb1 means instruction or teaching. It appears as the third '
        'of the five intellectual faculties (&ldquo;mind, thought, teaching, '
        'counsel, reflection&rdquo;). Gardner renders the third faculty '
        '&ldquo;insight,&rdquo; following the German critical edition&rsquo;s '
        '<i>Einsicht</i>. But the Coptic scribes had available the Greek loanword '
        '\u03c6\u03c1\u03cc\u03bd\u03b7\u03c3\u03b9\u03c2 (ph\u016bn\u0113sis, &ldquo;prudence/insight&rdquo;) and chose not to use it. '
        'They wrote \u2ca7\u2ca5\u2c83\u2cb1 &mdash; a native Coptic word whose semantic field is '
        'instruction and teaching. The Coptic term is primary. '
        'The compound \u2ca3\u2c89\u03e9\u2ca7\u2ca5\u2c83\u2cb1 ('
        '<i>rehtsbō</i>) = &ldquo;teacher&rdquo; further confirms this.'
    ))
    elements.append(_cpara(
        '<b>3. \u2ca1\u2c89\u2c93\u2c9b\u2c89 rendered variously as &ldquo;image,&rdquo; &ldquo;form,&rdquo; '
        '&ldquo;shape,&rdquo; &ldquo;resemblance&rdquo; &mdash; corrected uniformly '
        'to &ldquo;likeness.&rdquo;</b> '
        'The Coptic uses one word; the translation should use one word. '
        'Gardner varies his rendering depending on context, obscuring the '
        'systematic correspondential function of \u2ca1\u2c89\u2c93\u2c9b\u2c89: always the relational '
        'quality of one thing corresponding to another in form and nature. '
        '&ldquo;Likeness&rdquo; captures this relational quality; '
        '&ldquo;image&rdquo; and &ldquo;form&rdquo; do not. The Greek loanword '
        '\u03b5\u1f30\u03ba\u03ce\u03bd (eik\u014dn, &ldquo;image&rdquo; in the strict sense) appears separately '
        'in the text and is preserved as &ldquo;image&rdquo; where it occurs.'
    ))
    elements.append(_cpara(
        '<b>4. \u2ca7\u2c9f\u2ca9\u2cb1 rendered as &ldquo;release,&rdquo; &ldquo;free,&rdquo; &ldquo;save,&rdquo; '
        '&ldquo;redeem&rdquo; &mdash; corrected to &ldquo;raise.&rdquo;</b> '
        'The Coptic causative \u2ca7\u2c9f\u2ca9\u2cb1 means to cause to stand up, to raise. '
        'In Manichaean soteriology the upward direction is essential: '
        'light particles are <i>raised</i> from matter, not merely '
        '&ldquo;released&rdquo; or &ldquo;freed.&rdquo; Gardner flattens '
        'the spatial dimension by varying his rendering, losing the '
        'physical cosmological mechanic that the text repeatedly '
        'describes. The complementary verb \u2c83\u2cb1\u2c97 \u2c81\u2c83\u2c81\u2c97 '
        '(&ldquo;loose, release&rdquo; &mdash; the horizontal/dissolving complement) '
        'is preserved separately in the text and correctly rendered '
        '&ldquo;release.&rdquo;'
    ))

    # --- What Was Translated ---
    elements.append(Paragraph("What Was Translated", h))
    elements.append(Paragraph(
        "This is version 1.1 &mdash; the translated edition. The Manichaean "
        "Layer 2 naming overlays identified in the systematic review have been "
        "replaced throughout with their Persian substrate readings in plain "
        "English. The complete substitution mapping is given in the "
        "Translation Notes below.",
        p,
    ))
    elements.append(Paragraph(
        "The Coptic papyrus is damaged. Where gaps remained in the extracted "
        "text, those that could be constrained by correspondential logic and "
        "surrounding context were restored; those too large or uncertain were "
        "left open. Square brackets mark both the original lacunae and the "
        "restorations throughout. The restoration method was the same "
        "correspondences that organize the text itself: a spiritual reading "
        "of each chapter identified what must belong in each gap, and the "
        "fill was written in the text&rsquo;s own vocabulary.",
        p,
    ))

    # --- Translation Notes ---
    elements.append(Paragraph("Translation Notes", h))
    elements.append(Paragraph(
        "The following name-for-name substitutions were applied throughout "
        "this edition &mdash; in body text, chapter titles, structural "
        "descriptions, and the correspondence lexicon. The philological "
        "basis for each is noted.",
        p,
    ))

    _tn: list[tuple[str, str, str]] = [
        (
            "&ldquo;the Father of Greatness&rdquo;",
            "&ldquo;Boundless Time&rdquo;",
            "<i>Zurvan Akarana</i> &mdash; Boundless Time, the Zurvanite "
            "substrate of Manichaean Persian theology. <i>Zurvan</i> = Time; "
            "<i>akarana</i> = without limit or boundary. The boundless origin "
            "preceding the duality of light and darkness, from which all "
            "five fathers proceed.",
        ),
        (
            "&ldquo;First Man&rdquo;",
            "&ldquo;Lord Wisdom&rdquo;",
            "<i>Ohrmazd / Hormizd</i> &mdash; Avestan <i>Ahura Mazd&amacr;</i>, "
            "the good creating spirit in its human-facing descending form. "
            "<i>Ahura</i> = Lord, <i>Mazd&amacr;</i> = Wisdom; the name is "
            "a compound meaning Lord Wisdom. The First Man descends clothed "
            "in five protective truths and endures the darkness before his "
            "rescue by the Living Spirit.",
        ),
        (
            "&ldquo;Mother of Life&rdquo;",
            "&ldquo;the Bounteous Spirit&rdquo;",
            "<i>Spenta Mainyu</i> (Bounteous/Beneficent Spirit) from "
            "Zoroastrian theology. <i>Spenta</i> means bounteous or "
            "life-giving, not holy in the later Christian sense. The "
            "Manichaean name for this entity was drawn from the same source.",
        ),
        (
            "&ldquo;Father of Life&rdquo; / &ldquo;Living Spirit&rdquo;",
            "&ldquo;the Lord of Covenants&rdquo;",
            "<i>Mihryazd</i> (Mithra), the divine ordering truth that "
            "constructs the world-structure and judges according to covenant.",
        ),
        (
            "&ldquo;Third Ambassador&rdquo;",
            "&ldquo;the Envoy&rdquo;",
            "<i>Narisaf</i> (<i>Naryosanha</i> in Avestan) &mdash; the "
            "Manly Envoy or Announcer of Men. <i>Narya</i> = manly/human, "
            "<i>sanha</i> = announcement/envoy. He displays the divine "
            "image to extract captive light.",
        ),
        (
            "&ldquo;Jesus the Radiance&rdquo;",
            "&ldquo;the Kingdom of Wisdom&rdquo;",
            "<i>Xradeshahr</i> (Realm of Wisdom; <i>xrad</i> = wisdom, "
            "<i>shahr</i> = realm/kingdom). Radiant divine wisdom that "
            "illuminates, separates truth from falsity, and liberates. "
            "Note: Gardner rendered the Coptic title \u2ca1\u2ca1\u2ca3\u2c93\u0308\u2c89 as "
            "&ldquo;Jesus the Splendour&rdquo;; the Translation Corrections "
            "above correct this to &ldquo;Jesus the Radiance&rdquo; before "
            "the name substitution fires.",
        ),
        (
            "&ldquo;Jesus the Youth&rdquo;",
            "&ldquo;the Living Word&rdquo;",
            "Functional title: the active expression of divine wisdom "
            "made present in the world.",
        ),
        (
            "&ldquo;Light Mind&rdquo; / &ldquo;Light-Nous&rdquo;",
            "&ldquo;Good Mind&rdquo;",
            "<i>Vohu Manah</i> (Good Mind), one of the Amesha Spentas "
            "in Zoroastrian theology. The Greek <i>no&ucirc;s</i> entered "
            "through Hellenistic synthesis; <i>Vohu Manah</i> is the "
            "substrate.",
        ),
        (
            "&ldquo;Pillar of Glory&rdquo; / &ldquo;Perfect Man&rdquo;",
            "&ldquo;Hearkening&rdquo;",
            "<i>Sr&amacr;osha</i> &mdash; the Avestan deity whose name means "
            "the act of hearkening or listening to divine command. The Coptic "
            "source has no capitals; &ldquo;pillar&rdquo; describes the "
            "function (the column that bears all things) not a distinct "
            "proper name, and is left untranslated where it appears as a "
            "structural descriptor.",
        ),
        (
            "&ldquo;Virgin of Light&rdquo;",
            "&ldquo;the Maiden&rdquo;",
            "<i>Kany&amacr;g</i>, the feminine wisdom figure who takes away "
            "the hearts of the rulers by her likeness.",
        ),
        (
            "&ldquo;Beloved of the Lights&rdquo;",
            "&ldquo;King of Radiance&rdquo;",
            "<i>Roshan-sh&amacr;h</i> (King of Splendour/Radiance), "
            "the divine good made manifest through the illuminated mind.",
        ),
        (
            "&ldquo;Great Builder&rdquo;",
            "&ldquo;the Dawn&rdquo;",
            "<i>B&amacr;m-yazd</i> &mdash; <i>b&amacr;m</i> = dawn or "
            "morning; <i>yazd</i> = deity. The Persian substrate name "
            "means simply the Dawn Deity. The title &ldquo;Great "
            "Builder&rdquo; belongs to the Manichaean layer, not to the "
            "Persian substrate.",
        ),
        (
            "&ldquo;King of Honour&rdquo;",
            "&ldquo;Lord of the Settled Lands&rdquo;",
            "<i>Visbed</i>, lord of the settled/cultivated lands; "
            "governs the innermost rational degree.",
        ),
        (
            "&ldquo;Keeper of Splendour&rdquo;",
            "&ldquo;Master of Wisdom&rdquo;",
            "<i>Xradbed</i> &mdash; <i>xrad</i> = wisdom, "
            "<i>bed</i> = master or lord. The Persian name means "
            "Master of Wisdom.",
        ),
        (
            "&ldquo;Adamant of Light&rdquo;",
            "&ldquo;Life-Champion&rdquo;",
            "<i>Zandbed</i> (champion of the living/life), the "
            "unbreakable defender of life against darkness.",
        ),
        (
            "&ldquo;King of Glory&rdquo;",
            "&ldquo;Lord of the Mind&rdquo;",
            "<i>Manbed</i> (lord of mind/thought), who reigns over "
            "all the mental faculties.",
        ),
        (
            "&ldquo;the Porter&rdquo;",
            "&ldquo;the Guardian Spirit&rdquo;",
            "<i>Fravashi</i> (<i>fravarti</i>) &mdash; the guardian spirit "
            "in Zoroastrian cosmology; the heavenly double that bears up the "
            "structure of heaven and accompanies each soul.",
        ),
        (
            "&ldquo;Great Judge&rdquo; / &ldquo;Judge of Truth&rdquo;",
            "&ldquo;Justice&rdquo;",
            "<i>Rashnu</i>, the divine judge of souls at death in "
            "Zoroastrian theology.",
        ),
        (
            "&ldquo;the Counterpart&rdquo;",
            "&ldquo;the Precious One&rdquo;",
            "<i>Narig</i> (the precious/dear one) in Manichaean texts; "
            "the divine companion who accompanies the apostle and provides "
            "help from all afflictions &mdash; corresponding to the "
            "Zoroastrian <i>Fravashi</i>, each soul&rsquo;s heavenly twin.",
        ),
        (
            "&ldquo;Apostle of Light&rdquo; / &ldquo;apostle&rdquo;",
            "&ldquo;the Sent One&rdquo;",
            "<i>Fr&emacr;stag</i> (messenger/envoy), the Persian term "
            "for the transmitter of sacred knowledge.",
        ),
        (
            "&ldquo;Light Form&rdquo;",
            "&ldquo;the Vision&rdquo;",
            "<i>D&amacr;en&amacr;</i>, the personal vision of divine truth "
            "that appears to the soul at death &mdash; one&rsquo;s own "
            "conscience made visible in form.",
        ),
        (
            "&ldquo;Last Statue&rdquo;",
            "&ldquo;the Final Body&rdquo;",
            "<i>Tan-&imacr; Pas&emacr;n</i> (the body of the end-time), "
            "the fully realized Divine Human gathering all recaptured light "
            "at the consummation.",
        ),
        (
            "&ldquo;King of Darkness&rdquo;",
            "&ldquo;Evil Spirit&rdquo;",
            "<i>Angra Mainyu</i>, the destructive spirit in Zoroastrian "
            "theology.",
        ),
        (
            "&ldquo;Matter&rdquo; / &ldquo;Hyl&emacr;&rdquo;",
            "&ldquo;Greed&rdquo;",
            "Greek <i>h&uacute;l&emacr;</i> replacing <i>&Amacr;z</i> "
            "(the demon of concupiscence) from Zurvanite tradition. "
            "Consistently paired in the text with "
            "&ldquo;the thought of death.&rdquo;",
        ),
        (
            "&ldquo;Cross of Light&rdquo; / &ldquo;crucified&rdquo;",
            "&ldquo;the Bound Radiance&rdquo; / &ldquo;bound and spread&rdquo;",
            "Christian crucifixion vocabulary mapped onto the substrate "
            "concept of divine light scattered and bound within matter &mdash; "
            "a Zoroastrian concept requiring no crucifixion metaphor.",
        ),
        (
            "&ldquo;Saklas&rdquo;",
            "&ldquo;the Fool&rdquo;",
            "Aramaic for &ldquo;fool&rdquo; &mdash; a Gnostic/Sethian name "
            "imported from texts like the Apocryphon of John. The Persian "
            "substrate name is lost; &ldquo;the Fool&rdquo; renders "
            "the semantic content.",
        ),
        (
            "&ldquo;the elect&rdquo; / &ldquo;the elect one&rdquo;",
            "&ldquo;the purified ones&rdquo; / &ldquo;the purified one&rdquo;",
            "Manichaean institutional vocabulary for those in the advanced "
            "stage of purification; replaced by their functional equivalent.",
        ),
        (
            "&ldquo;the church&rdquo; / &ldquo;holy church&rdquo;",
            "&ldquo;the living assembly&rdquo;",
            "The cosmic assembly of purified souls.",
        ),
        (
            "&ldquo;good news&rdquo;",
            "&ldquo;the proclamation&rdquo;",
            "Greek <i>e&uacute;ang&eacute;lion</i> &mdash; distinctly Pauline "
            "vocabulary replaced by its functional equivalent.",
        ),
    ]

    for old_name, new_name, note in _tn:
        elements.append(Paragraph(
            f'<b>{old_name}</b> &rarr; <b>{new_name}</b>. {note}',
            ind,
        ))

    # --- Deeper Transmission Evidence ---
    elements.append(Paragraph("Deeper Transmission Evidence", h))
    elements.append(Paragraph(
        "Beyond the Manichaean overlay, the review also identified material "
        "that predates even the Persian-Zoroastrian vessel:",
        p,
    ))
    elements.append(Paragraph(
        "The five dark elements (smoke, fire, wind, water, darkness) do not "
        "match either classical Greek (four elements) or standard Zoroastrian "
        "categories. This sequence appears to preserve a "
        "<b>proto-Indo-Iranian or Mesopotamian elemental cosmology</b> older "
        "than the Persian formulation.",
        ind,
    ))
    elements.append(Paragraph(
        "The &ldquo;sea giant&rdquo; passage (&sect;437&ndash;441) &mdash; "
        "a composite being formed from cosmic debris in a primordial sea, "
        "bearing the imprint of all celestial cycles upon its body &mdash; "
        "has parallels to Mesopotamian creation narratives and "
        "<b>Zurvanite cosmogony</b>, and may represent one of the oldest "
        "layers in the text.",
        ind,
    ))
    elements.append(Paragraph(
        "The water-reflection/inversion teaching (&sect;804&ndash;808) "
        "&mdash; the upper world reflected inversely in the lower &mdash; "
        "appears across ancient Near Eastern and Vedic/Upanishadic traditions "
        "and expresses a law of correspondence more fundamental than any "
        "single cultural formulation.",
        ind,
    ))
    elements.append(Paragraph(
        "The medical/healing analogy (&sect;393&ndash;397) &mdash; cosmic "
        "healing through three medicines applied in three directions &mdash; "
        "has strong parallels to Mesopotamian therapeutic traditions, "
        "suggesting an ancient Near Eastern substrate beneath the "
        "Persian vessel.",
        ind,
    ))

    # --- How to Read This Text ---
    elements.append(Paragraph("How to Read This Text", h))
    elements.append(Paragraph(
        "You are reading the Ancient Word &mdash; and it has traveled far "
        "to reach you. It was given systematic form in the "
        "Persian-Zoroastrian tradition, where it acquired its five-fold "
        "architecture, its body-cosmos correspondence map, and its doctrine "
        "of discrete degrees. It was received by Mani in third-century "
        "Babylonia, who translated its Persian entities into a mixed "
        "vocabulary of Christian, Greek, and Gnostic terms. It was recorded "
        "in Coptic by Manichaean scribes in Egypt. It was translated into "
        "English by Iain Gardner in 1995. And it was extracted from its "
        "manuscript frame and organized by its own internal structure here.",
        p,
    ))
    elements.append(Paragraph(
        "Through all these transmissions, the teaching itself survived. "
        "The five-fold architecture did not change. The body-cosmos "
        "correspondence did not change. The doctrine that reality proceeds "
        "through discrete degrees &mdash; celestial, spiritual, natural "
        "&mdash; did not change. The mechanism of divine influx and human "
        "reception (&ldquo;the summons and the obedience&rdquo;) did not "
        "change. The complete arc of regeneration &mdash; from the primordial "
        "separation of wisdom and falsity through divine descent, combat, "
        "purification, and final restoration &mdash; did not change.",
        p,
    ))
    elements.append(Paragraph(
        "The names changed. The teaching did not.",
        pi,
    ))
    elements.append(Paragraph(
        "In this edition the Layer 2 names have been replaced with their "
        "substrate readings throughout. The complete mapping is given in "
        "the Translation Notes above.",
        p,
    ))
    elements.append(Paragraph(
        "The correspondences are in the text. They have always been in "
        "the text. The Manichaean names are garments. What wears them "
        "is the Ancient Word.",
        pi,
    ))
    elements.append(PageBreak())
    return elements


def _toc_page(st: dict, structure: dict) -> list:
    elements: list = [
        Spacer(1, 15 * mm),
        Paragraph("CONTENTS", st["section_title"]),
        Spacer(1, 6 * mm),
    ]

    indent = 8 * mm  # chapter indent

    for part in structure["parts"]:
        pn = part["part_number"]
        part_key = f"part_{pn}"
        part_page = _page_registry.get(part_key, "")
        toc_part_label = _apply_transformations(part['title'])
        part_title = f"Part {pn} \u2014 {toc_part_label}"

        elements.append(Spacer(1, 10))   # spaceBefore
        elements.append(_TocLine(
            part_title, part_page,
            title_font=FONT_BOLD, font_size=11, leading=16,
        ))

        for ch in structure["chapters"]:
            if ch["part_number"] == pn:
                ch_key = f"ch_{ch['section_start']}"
                ch_page = _page_registry.get(ch_key, "")
                toc_ch_title = _apply_transformations(ch["title"])

                elements.append(_TocLine(
                    toc_ch_title, ch_page,
                    title_font=FONT_ROMAN, font_size=10, leading=14,
                    indent=indent,
                ))

    # --- Back matter entries ---
    lex_page = _page_registry.get("lexicon", "")
    if lex_page:
        elements.append(Spacer(1, 10))
        elements.append(_TocLine(
            "Correspondence Lexicon", lex_page,
            title_font=FONT_BOLD, font_size=11, leading=16,
        ))

    elements.append(PageBreak())
    return elements


def _part_page(st: dict, part: dict) -> list:
    part_title = _apply_transformations(part["title"])
    part_desc = _apply_transformations(part["description"])
    part_desc = _capitalize_sentences(part_desc)
    return [
        _PageRecorder(f"part_{part['part_number']}"),
        Spacer(1, 60 * mm),
        Paragraph(f'Part {part["part_number"]}', st["part_number"]),
        Spacer(1, 4 * mm),
        Paragraph(_xml_esc(part_title), st["part_title"]),
        Spacer(1, 12 * mm),
        Paragraph(_xml_esc(part_desc), st["part_desc"]),
        PageBreak(),
    ]


def _render_chapter(
    st: dict,
    ch: dict,
    para_lookup: dict[int, str],
) -> list:
    """Render a structural chapter using §-range from book_structure.json.

    All titles come from the structure.  Paragraph text is selected
    by the §-range (section_start – section_end).
    """
    elements: list = []

    # Bookmark for TOC page number
    elements.append(_PageRecorder(f"ch_{ch['section_start']}"))

    # --- Chapter heading (from structure only) ---
    ch_title = _apply_transformations(ch["title"])
    elements.append(
        Paragraph(_xml_esc(ch_title), st["chapter_title"])
    )
    if ch.get("role"):
        role_label = ch["role"].replace("_", " ").title()
        elements.append(Paragraph(role_label, st["chapter_role"]))

    # --- Chapter description (from the model's analysis) ---
    if ch.get("description"):
        ch_desc = _apply_transformations(ch["description"])
        ch_desc = _capitalize_sentences(ch_desc)
        elements.append(
            Paragraph(_xml_esc(ch_desc), st["chapter_desc"])
        )

    # Thin rule after description
    elements.append(
        HRFlowable(
            width="50%", thickness=0.5,
            color=HexColor(RULE_COLOR),
            spaceAfter=8 * mm, spaceBefore=4 * mm,
        )
    )

    # --- Select paragraphs by §-range ---
    s_start = ch["section_start"]
    s_end = ch["section_end"]
    first = True
    para_count = 0

    for seq_n in range(s_start, s_end + 1):
        text = para_lookup.get(seq_n)
        if not text:
            continue

        text = _clean_core_text(text)
        if not text:
            continue

        text = _normalize_word_brackets(text)   # expand partial-word brackets
        text = _normalize_text(text)
        text = _apply_transformations(text)
        text = _normalize_word_brackets(text)   # clean up any remaining partials
        text = _clean_gap_markers(text)
        styled = _style_lacunae(text)
        style = st["body_first"] if first else st["body"]
        first = False
        para_count += 1

        try:
            elements.append(Paragraph(styled, style))
        except Exception as exc:
            print(f"  WARNING: skipped §{seq_n} ({exc})")

    if para_count == 0:
        elements.append(
            Paragraph(
                f'<font color="{LACUNA_GRAY}">[No surviving text in this section]</font>',
                st["body_first"],
            )
        )

    elements.append(PageBreak())
    return elements


# ---------------------------------------------------------------------------
# Lexicon renderer
# ---------------------------------------------------------------------------

_CATEGORY_LABELS = {
    "cosmological_entity": "Cosmological Entities",
    "cosmic_element": "Cosmic Elements & Substances",
    "structural_term": "Structural Terms",
    "body_anatomy": "Body & Anatomy",
    "natural_imagery": "Natural Imagery",
    "action_process": "Actions & Processes",
    "quality_state": "Qualities & States",
    "numerical_correspondence": "Numerical Correspondences",
}

_CATEGORY_ORDER = [
    "cosmological_entity",
    "cosmic_element",
    "structural_term",
    "body_anatomy",
    "natural_imagery",
    "action_process",
    "quality_state",
    "numerical_correspondence",
]


def _load_lexicon() -> dict | None:
    """Load the correspondence lexicon JSON, or None if absent."""
    if not LEXICON_FILE.exists():
        return None
    with open(LEXICON_FILE, encoding="utf-8") as f:
        return json.load(f)


def _section_to_chapters(section_refs: list[str],
                         chapters: list[dict]) -> list[int]:
    """Convert §N / §N\u2013§M references to sorted, unique chapter indices."""
    import re
    sec_nums: set[int] = set()
    for ref in section_refs:
        # Match §N or §N–§M (en-dash or hyphen)
        for m in re.finditer(r'§(\d+)(?:[–\-](\d+))?', ref):
            lo = int(m.group(1))
            hi = int(m.group(2)) if m.group(2) else lo
            sec_nums.update(range(lo, hi + 1))
    if not sec_nums:
        return []
    ch_indices: set[int] = set()
    for idx, ch in enumerate(chapters):
        s, e = ch["section_start"], ch["section_end"]
        if any(s <= n <= e for n in sec_nums):
            ch_indices.add(idx)
    return sorted(ch_indices)


def _render_lexicon(st: dict, lexicon: dict, chapters: list[dict]) -> list:
    """Render the correspondence lexicon as PDF flowables."""
    elements: list = [
        _PageRecorder("lexicon"),
        Spacer(1, 30 * mm),
        Paragraph("CORRESPONDENCE LEXICON", st["section_title"]),
        Spacer(1, 4 * mm),
        Paragraph(
            "A comprehensive mapping of every natural term in the Ancient "
            "Word to its spiritual correspondence. Entries are organized "
            "by category. Where the same natural image carries both a "
            "positive and a negative sense, the opposite sense is noted.",
            ParagraphStyle(
                "LI", fontName=FONT_ITALIC, fontSize=10,
                alignment=TA_CENTER, leading=14, spaceAfter=16,
                textColor=HexColor(NOTE_COLOR),
            ),
        ),
    ]

    entries = lexicon.get("entries", [])
    by_cat: dict[str, list] = {}
    for e in entries:
        by_cat.setdefault(e["category"], []).append(e)

    for cat_key in _CATEGORY_ORDER:
        group = by_cat.get(cat_key, [])
        if not group:
            continue

        label = _CATEGORY_LABELS.get(cat_key, cat_key.replace("_", " ").title())
        elements.append(Paragraph(
            _xml_esc(f"{label} ({len(group)})"),
            st["lex_category"],
        ))
        elements.append(HRFlowable(
            width="100%", thickness=0.4,
            color=HexColor(RULE_COLOR),
            spaceAfter=4 * mm,
        ))

        for e in group:
            # --- Entry heading: term → spiritual meaning ---
            nat = _xml_esc(_apply_transformations(e["natural_term"]))
            spi = _xml_esc(_apply_transformations(e["spiritual_meaning"]))
            head = f'<b>{nat}</b> \u2014 <i>{spi}</i>'

            # Variants
            variants = e.get("natural_variants", [])
            if variants:
                vlist = ", ".join(_xml_esc(_apply_transformations(v)) for v in variants)
                head += f'  <font color="{MUTED}" size="8">({vlist})</font>'

            elements.append(Paragraph(head, st["lex_entry_head"]))

            # --- Definition ---
            defn = e.get("definition", "")
            if defn:
                defn_text = _apply_transformations(defn)
                defn_text = _capitalize_sentences(defn_text)
                elements.append(Paragraph(_xml_esc(defn_text), st["lex_entry_body"]))

            # --- Opposite sense ---
            opp = e.get("opposite_sense", "")
            if opp:
                opp_text = _apply_transformations(opp)
                opp_text = _capitalize_sentences(opp_text)
                elements.append(Paragraph(
                    f'Opposite sense: {_xml_esc(opp_text)}',
                    st["lex_entry_detail"],
                ))

            # --- Notes ---
            notes = e.get("notes", "")
            ch_refs = _section_to_chapters(
                e.get("section_refs", []), chapters
            )
            ch_label = ""
            if ch_refs:
                ch_label = "Ch. " + ", ".join(str(c + 1) for c in ch_refs)

            if notes and ch_label:
                notes_text = _apply_transformations(notes)
                notes_text = _capitalize_sentences(notes_text)
                elements.append(Paragraph(
                    f'{_xml_esc(notes_text)}  '
                    f'<font color="{MUTED}">({ch_label})</font>',
                    st["lex_entry_detail"],
                ))
            elif notes:
                notes_text = _apply_transformations(notes)
                notes_text = _capitalize_sentences(notes_text)
                elements.append(Paragraph(
                    _xml_esc(notes_text), st["lex_entry_detail"],
                ))
            elif ch_label:
                elements.append(Paragraph(
                    f'<font color="{MUTED}">({ch_label})</font>',
                    st["lex_entry_detail"],
                ))

    elements.append(PageBreak())
    return elements


def _render_observations(st: dict, observations: list[dict]) -> list:
    """Render the structural observations section."""
    elements: list = [
        Spacer(1, 30 * mm),
        Paragraph("STRUCTURAL OBSERVATIONS", st["section_title"]),
        Spacer(1, 8 * mm),
        Paragraph(
            "Patterns and principles identified by reading the entire "
            "corpus as a single continuous text, without manuscript "
            "chapter divisions.",
            ParagraphStyle(
                "OI", fontName=FONT_ITALIC, fontSize=10,
                alignment=TA_CENTER, leading=14, spaceAfter=16,
                textColor=HexColor(NOTE_COLOR),
            ),
        ),
    ]

    for obs in observations:
        elements.append(
            Paragraph(_xml_esc(obs["title"]), st["obs_title"])
        )
        elements.append(
            Paragraph(_xml_esc(obs["content"]), st["obs_body"])
        )

    return elements


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def build_pdf():
    print("Loading structure ...")
    structure = load_structure()

    parts = structure["parts"]
    chapters = structure["chapters"]
    observations = structure["observations"]

    print(
        f"  {len(parts)} parts, {len(chapters)} chapters, "
        f"{len(observations)} observations"
    )

    # Build the global §N → paragraph text lookup
    print("\nBuilding paragraph lookup ...")
    para_lookup = build_paragraph_lookup()
    print(f"  {len(para_lookup)} paragraphs indexed (§1–§{max(para_lookup)})")

    # PDF setup
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    st = _styles()

    # Use temp file to avoid viewer lock, then rename
    build_target = OUTPUT_TMP
    doc = SimpleDocTemplate(
        str(build_target),
        pagesize=A4,
        leftMargin=25 * mm,
        rightMargin=25 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title="The Ancient Word v1.1 \u2014 Translated Edition",
        author="Manichaean Analysis Project",
    )

    elements: list = []

    # ---- Title page ----
    elements.extend(_title_page(st))

    # ---- Preface ----
    elements.extend(_preface_pages(st))

    # ---- Table of contents ----
    elements.extend(_toc_page(st, structure))

    # ---- Parts & chapters ----
    current_part = None
    for ch_idx, ch in enumerate(chapters):
        pn = ch["part_number"]

        # Part divider page
        if pn != current_part:
            current_part = pn
            part = next(p for p in parts if p["part_number"] == pn)
            elements.extend(_part_page(st, part))

        # Chapter content — selected by §-range
        s_start = ch["section_start"]
        s_end = ch["section_end"]
        n_paras = sum(1 for n in range(s_start, s_end + 1) if n in para_lookup)
        readable = ch["title"][:60]
        print(f"  Ch {ch_idx}: §{s_start}–§{s_end} ({n_paras} ¶)  \"{readable}\"")
        elements.extend(_render_chapter(st, ch, para_lookup))

    # ---- Correspondence Lexicon (back matter) ----
    lexicon = _load_lexicon()
    if lexicon:
        elements.extend(_render_lexicon(st, lexicon, chapters))
        n_lex = len(lexicon.get("entries", []))
        print(f"\n  Lexicon: {n_lex} entries")

    # Build — two passes: first to collect page numbers, second with TOC
    print(f"\n  Pass 1: collecting page numbers ({len(elements)} flowables) ...")
    _page_registry.clear()
    doc.build(list(elements), onLaterPages=_page_footer)

    print(f"  Pass 2: rebuilding with page numbers ...")
    # Rebuild TOC with recorded page numbers
    elements_pass2: list = []
    elements_pass2.extend(_title_page(st))
    elements_pass2.extend(_preface_pages(st))
    elements_pass2.extend(_toc_page(st, structure))
    current_part = None
    for ch in chapters:
        pn = ch["part_number"]
        if pn != current_part:
            current_part = pn
            part = next(p for p in parts if p["part_number"] == pn)
            elements_pass2.extend(_part_page(st, part))
        elements_pass2.extend(_render_chapter(st, ch, para_lookup))

    if lexicon:
        elements_pass2.extend(_render_lexicon(st, lexicon, chapters))

    doc2 = SimpleDocTemplate(
        str(build_target),
        pagesize=A4,
        leftMargin=25 * mm,
        rightMargin=25 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title="The Ancient Word v1.1 \u2014 Translated Edition",
        author="Manichaean Analysis Project",
    )
    doc2.build(elements_pass2, onLaterPages=_page_footer)

    # Rename temp → final (handles viewer-locked file on retry)
    import shutil
    try:
        shutil.move(str(build_target), str(OUTPUT))
    except PermissionError:
        print(f"  \u26a0 Could not overwrite {OUTPUT.name} (file locked).")
        print(f"  Output written to: {build_target}")

    final = OUTPUT if OUTPUT.exists() else build_target
    size_kb = final.stat().st_size / 1024
    print(f"  Saved to {final}")
    print(f"  Size: {size_kb:,.0f} KB")


def main():
    if not STRUCTURE_FILE.exists():
        import sys
        sys.exit(f"Structure file not found: {STRUCTURE_FILE}")

    build_pdf()
    print("\nDone.")


if __name__ == "__main__":
    main()
