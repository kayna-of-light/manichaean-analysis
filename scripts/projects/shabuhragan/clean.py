#!/usr/bin/env python3
"""
Clean the Šābuhragān using GPT-5.2 to separate Middle Persian transliteration
from English translation and strip OCR/PDF artifacts.

The Šābuhragān is a fragment-based text, not a chapter-based one. This script:
  1. Parses the raw OCR'd markdown into named sections (the "chapter" equivalent)
  2. Strips running headers, page numbers, and page-break artifacts
  3. Sends each section to GPT-5.2 to separate MP text from English translation,
     clean OCR artifacts, and structure the scholarly apparatus
  4. Outputs structured JSON files (one per section) compatible with the pipeline

Structure of the source text:
  - Three major divisions: (I) AUTOBIOGRAPHY, (II) COSMOGONY, (III) ESCHATOLOGY
  - Within each: named sub-sections (e.g. "The Kingdom of Light")
  - Each sub-section references specific manuscript fragments (M49, M178, M519...)
  - Middle Persian transliteration is interleaved with English translation
  - Section markers like {a.1}, {y.1}, {z.1} mark internal divisions
  - Lacunae: [ ... ], {ll. NNN-NNN missing}, {N lines left blank}

Usage:
    python scripts/projects/shabuhragan/clean.py                    # Process all sections
    python scripts/projects/shabuhragan/clean.py --chapter 1        # Process single section
    python scripts/projects/shabuhragan/clean.py --range 0-5        # Process section range
    python scripts/projects/shabuhragan/clean.py --dry-run           # Show sections without processing
    python scripts/projects/shabuhragan/clean.py --overwrite         # Reprocess existing sections
    python scripts/projects/shabuhragan/clean.py --list              # List all sections
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

from openai import OpenAI, RateLimitError, APIStatusError
from dotenv import dotenv_values
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SECRETS_PATH = REPO_ROOT / "secrets" / "azure_openai.env"
SOURCE_FILE = REPO_ROOT / "output" / "texts" / "DB_Anthology_3_Shabuhragan.md"
OUTPUT_DIR = REPO_ROOT / "output" / "projects" / "shabuhragan" / "cleaned"
CHAPTERS_DIR = OUTPUT_DIR / "chapters"
TRANSLATION_FILE = OUTPUT_DIR / "shabuhragan_translation.md"
APPARATUS_FILE = OUTPUT_DIR / "shabuhragan_apparatus.md"

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a scholarly text editor specializing in Manichaean religious texts. You are \
given a raw section from the Šābuhragān — Mani's Middle Persian cosmogonic and \
eschatological work composed for King Šābuhr I (Shapur I). The text comes from the \
Database of Manichaean Texts (DbMT 2022), compiled by Samuel N.C. Lieu, based on \
editions by Henning, Mackenzie, Skjærvø, and Sims-Williams.

The source text was OCR'd from PDF and contains significant artifacts. The most \
critical feature is that MIDDLE PERSIAN TRANSLITERATION and ENGLISH TRANSLATION are \
INTERLEAVED on the same lines. Your primary task is to separate these cleanly.

## SOURCE TEXT STRUCTURE

Each section you receive will contain:

1. **Section header**: A named title (e.g. "The Kingdom of Light") and/or a major \
   division marker (e.g. "(II) COSMOGONY").

2. **Manuscript references**: Lines like "M178 (= MIK III 4990) I" followed by \
   edition/translation citations.

3. **Column/page markers**: [R], [V], [R/Hd], [V/Hd] (Recto, Verso, Headings), \
   plus manuscript designations like [M98 I/R], [M99 I/V].

4. **Interleaved text**: Middle Persian transliteration (using a modified Latin \
   alphabet with special characters: ', ʿ, ẅ, º, |, ₩, etc.) appears on the SAME \
   LINES as the English translation. The MP text uses sequences like: \
   'wd, 'c, yzd, m'h, zmyg, dyw'n, xwr, etc.

5. **Section markers**: {a.1}, {b.1}, {y.1}, {z.1}, {ac.1}, {ad.1}, {ae.1} etc. \
   These mark internal divisions and appear in BOTH the MP and English text. \
   PRESERVE these in both outputs.

6. **Lacunae markers**: [ ... ], [ ...... ], {ll. NNN-NNN missing}, \
   {N lines left blank}, {N lines illegible}. PRESERVE all of these.

7. **Manuscript line numbers**: Numbers in parentheses like (5), (10), (15), (25), \
   (30) etc. embedded in the running text. These mark original manuscript positions.

8. **Page breaks and running headers**: Lines containing "III. Šābuhragān and \
   Šābuhragān-related texts" or "Anthologia Manichaica Orientalia" or bare page \
   numbers (single integers at end of lines). These are PDF pagination artifacts.

9. **Footnotes**: Numbered footnotes (1, 2, 3...) appear at section boundaries, \
   typically starting with a number followed by scholarly commentary about readings.

10. **Sogdian text**: Some sections (especially M178) contain Sogdian rather than \
    Middle Persian. The language is identified in the manuscript reference line \
    ("Sogd.:" prefix).

## YOUR TASK

Produce a structured output with these fields:

### english_translation
The clean English translation ONLY. Remove all Middle Persian/Sogdian transliteration. \
Preserve:
- Section markers {a.1}, {z.1} etc. — keep them inline
- Lacunae [ ... ] and editorial notes {ll. NNN-NNN missing}
- Paragraph breaks at natural boundaries (section markers, new topics)
- Column/manuscript markers [R], [V] etc. as paragraph-level indicators if helpful
- Manuscript line numbers in parentheses — keep them for scholarly reference

Remove:
- ALL Middle Persian/Sogdian transliteration sequences
- Page break markers (---) and running headers
- OCR artifacts (broken lines, orphan characters)
- Page numbers

### original_text
The Middle Persian or Sogdian transliteration ONLY. Remove all English. Preserve:
- Section markers {a.1}, {z.1} etc.
- Lacunae markers
- Column/page markers [R], [V], [M98 I/R] etc.
- Manuscript line numbers
- The special characters: ', º, |, ₩, ẅ, etc.
- Paragraph at natural boundaries

If the section contains NO original text (pure English summary), set to empty string.

### manuscript_refs
List of manuscript fragment references (e.g. "M178 (= MIK III 4990) I"). \
One entry per distinct fragment.

### edition_refs
List of edition/translation citations from the header (e.g. \
"Ed. W.B. Henning, 'A Sogdian Fragment of the Manichaean Cosmogony', BSOAS 12 (1948)").

### footnotes
Collected footnotes with number and text. Only scholarly footnotes — not OCR noise.

### editorial_notes
Notes about the condition of this section — major lacunae, illegible passages, \
OCR issues you corrected, anything a downstream reader should know.

## CRITICAL RULES

1. **DO NOT translate, interpret, or rewrite.** You are separating and cleaning only.
2. **Middle Persian identification**: MP text uses a distinctive script with characters \
   like ', ʿ, ẅ, ₩, º, |. It reads as transliterated consonant clusters: 'wd, xwr, \
   dyw'n, yzd'n, etc. When you see these on the same line as readable English, the \
   MP portion goes to original_text and the English to english_translation.
3. **Section markers are sacred**: {a.1}, {y.3}, {z.11} etc. must appear in BOTH \
   original_text and english_translation at their correct positions.
4. **Lacunae preservation**: Every [ ... ], {ll. NNN-NNN missing}, and \
   {N lines blank} must be preserved exactly.
5. **Sogdian sections**: Some text (M178) is Sogdian, not Middle Persian. The \
   original_language field should reflect this. The separation task is the same.
"""


# ---------------------------------------------------------------------------
# Pydantic schema
# ---------------------------------------------------------------------------

class Footnote(BaseModel):
    """A scholarly footnote from the text."""
    number: int = Field(description="Footnote number")
    text: str = Field(description="Footnote text content")


class CleanedSection(BaseModel):
    """Structured output for a cleaned Šābuhragān section."""
    section_number: int = Field(
        description="Sequential section number (0-based) as assigned in the input"
    )
    title: str = Field(
        description="Section title (e.g. 'The Kingdom of Light'). "
        "Include the major division prefix if present (e.g. '(II) COSMOGONY: The Kingdom of Light')."
    )
    english_translation: str = Field(
        description="The clean English translation only. All Middle Persian/Sogdian "
        "transliteration removed. Section markers, lacunae, and manuscript line "
        "numbers preserved."
    )
    original_text: str = Field(
        description="The Middle Persian or Sogdian transliteration only. All English "
        "removed. Section markers, lacunae, and column markers preserved. "
        "Empty string if no original text in this section."
    )
    original_language: str = Field(
        description="Language of the original text: 'middle_persian', 'sogdian', "
        "'mixed', or 'none' if the section has no original text."
    )
    manuscript_refs: list[str] = Field(
        default_factory=list,
        description="List of manuscript fragment references (e.g. 'M178 (= MIK III 4990) I')"
    )
    edition_refs: list[str] = Field(
        default_factory=list,
        description="List of edition/translation citations"
    )
    footnotes: list[Footnote] = Field(
        default_factory=list,
        description="Collected scholarly footnotes. Empty list if none."
    )
    editorial_notes: str = Field(
        default="",
        description="Notes about manuscript condition, OCR corrections, "
        "significant lacunae, or editorial observations."
    )
    section_markers: list[str] = Field(
        default_factory=list,
        description="List of all internal section markers found (e.g. ['{a.1}', '{a.2}', '{b.1}'])"
    )


# ---------------------------------------------------------------------------
# Client setup
# ---------------------------------------------------------------------------

def create_client() -> OpenAI:
    """Create OpenAI client configured for Azure Foundry."""
    if not SECRETS_PATH.exists():
        print(f"ERROR: Secrets file not found at {SECRETS_PATH}")
        sys.exit(1)

    config = dotenv_values(SECRETS_PATH)
    return OpenAI(
        base_url=config["OPENAI_ENDPOINT"],
        api_key=config["OPENAI_API_KEY"],
    )


def get_deployment() -> str:
    """Get the model deployment name."""
    config = dotenv_values(SECRETS_PATH)
    return config["OPENAI_DEPLOYMENT"]


# ---------------------------------------------------------------------------
# Section parsing
# ---------------------------------------------------------------------------

# Major division markers
DIVISION_RE = re.compile(r"^\((?:I{1,3})\)\s+(.+)$")

# Named sub-section titles — lines that start a new thematic unit.
# These are English title lines that precede manuscript references.
SUBSECTION_TITLE_RE = re.compile(
    r"^(The |On |What |Mani )"   # Titles typically start with these
)

# Manuscript reference lines
MS_REF_RE = re.compile(r"^M\d+")

# Page break / running header patterns to strip
PAGE_HEADER_RE = re.compile(
    r"^(III\.\s+Šābuhragān|Anthologia Manichaica Orientalia|DATABASE OF MANICHAEAN)",
    re.IGNORECASE,
)
BARE_PAGE_NUM_RE = re.compile(r"^\d{1,2}\s*$")

# Section markers inside text
SECTION_MARKER_RE = re.compile(r"\{[a-z]{1,3}\.\d+\}")


class RawSection:
    """A parsed section from the source text."""
    def __init__(self, number: int, title: str, division: str,
                 lines: list[str], start_line: int):
        self.number = number
        self.title = title
        self.division = division      # "AUTOBIOGRAPHY", "COSMOGONY", "ESCHATOLOGY"
        self.lines = lines
        self.start_line = start_line

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    @property
    def line_count(self) -> int:
        return len(self.lines)

    def __repr__(self) -> str:
        return (f"Section {self.number}: [{self.division}] {self.title} "
                f"(line {self.start_line}, {self.line_count} lines)")


def parse_sections(source_path: Path) -> list[RawSection]:
    """Parse the Šābuhragān markdown into named sections.

    Strategy: We identify section boundaries by looking for:
    1. Major division markers: (I) AUTOBIOGRAPHY, (II) COSMOGONY, (III) ESCHATOLOGY
    2. Named sub-section titles: "The Kingdom of Light", "The Third Evocation", etc.
    3. Manuscript reference lines that follow titles (M49, M178, M519, etc.)

    A new section starts when we see either a division marker or a named title
    followed by a manuscript reference.
    """
    with open(source_path, "r", encoding="utf-8") as f:
        all_lines = f.readlines()

    # Strip trailing newlines
    all_lines = [line.rstrip("\n") for line in all_lines]

    sections: list[RawSection] = []
    current_division = ""
    current_title = ""
    current_lines: list[str] = []
    current_start = 0
    section_num = 0

    # Skip the document header (title, metadata block, front matter)
    # Find the first major division marker
    start_idx = 0
    for i, line in enumerate(all_lines):
        if DIVISION_RE.match(line.strip()):
            start_idx = i
            break

    # State: scanning for section boundaries
    i = start_idx
    while i < len(all_lines):
        line = all_lines[i].strip()

        # Check for major division marker
        div_match = DIVISION_RE.match(line)
        if div_match:
            # Save previous section if any
            if current_lines and current_title:
                sections.append(RawSection(
                    number=section_num,
                    title=f"({_roman(current_division)}) {current_division}: {current_title}",
                    division=current_division,
                    lines=current_lines,
                    start_line=current_start,
                ))
                section_num += 1
                current_lines = []

            current_division = div_match.group(1).strip()

            # Look ahead: is the next non-empty line a named title or MS ref?
            j = i + 1
            while j < len(all_lines) and not all_lines[j].strip():
                j += 1

            if j < len(all_lines):
                next_line = all_lines[j].strip()
                # If next line is a named title, consume it too (skip j)
                if SUBSECTION_TITLE_RE.match(next_line):
                    current_title = _clean_title(next_line)
                    current_start = i
                    current_lines = [all_lines[i]]
                    # Add blank lines between i and j
                    for k in range(i + 1, j):
                        current_lines.append(all_lines[k])
                    current_lines.append(all_lines[j])
                    i = j + 1  # Skip past the consumed title line
                    continue
                # If next line is directly a MS ref, the division IS the title
                elif MS_REF_RE.match(next_line):
                    current_title = current_division
                    current_start = i
                    current_lines = [all_lines[i]]
                    i += 1
                    continue

            # Division line with something following — use division as title
            current_title = current_division
            current_start = i
            current_lines = [all_lines[i]]
            i += 1
            continue

        # Check for named sub-section title
        # A sub-section title is a descriptive English line followed within
        # a few lines by a manuscript reference
        if (SUBSECTION_TITLE_RE.match(line)
                and not PAGE_HEADER_RE.match(line)
                and _has_ms_ref_nearby(all_lines, i)):
            # Save previous section
            if current_lines and current_title:
                sections.append(RawSection(
                    number=section_num,
                    title=f"({_roman(current_division)}) {current_division}: {current_title}"
                          if current_division else current_title,
                    division=current_division,
                    lines=current_lines,
                    start_line=current_start,
                ))
                section_num += 1

            current_title = _clean_title(line)
            current_start = i
            current_lines = [all_lines[i]]
            i += 1
            continue

        # Accumulate line into current section
        if current_title:
            current_lines.append(all_lines[i])

        i += 1

    # Save final section
    if current_lines and current_title:
        sections.append(RawSection(
            number=section_num,
            title=f"({_roman(current_division)}) {current_division}: {current_title}"
                  if current_division else current_title,
            division=current_division,
            lines=current_lines,
            start_line=current_start,
        ))

    return sections


def _roman(division: str) -> str:
    """Map division name to roman numeral prefix."""
    mapping = {
        "AUTOBIOGRAPHY": "I",
        "COSMOGONY": "II",
        "ESCHATOLOGY": "III",
    }
    return mapping.get(division, "?")


def _clean_title(title: str) -> str:
    """Strip trailing manuscript references from a section title.

    E.g. "The Superiority of Mani's religion M5794 + M5761 + M6062"
      -> "The Superiority of Mani's religion"
    """
    # Remove trailing M-number sequences
    cleaned = re.sub(r"\s+M\d+[a-z]?(?:\s*\+\s*M\d+[a-z]?)*\s*$", "", title)
    return cleaned.strip()


def _has_ms_ref_nearby(lines: list[str], title_idx: int, lookahead: int = 4) -> bool:
    """Check if a manuscript reference line appears within `lookahead` lines."""
    for j in range(title_idx + 1, min(title_idx + lookahead + 1, len(lines))):
        stripped = lines[j].strip()
        if MS_REF_RE.match(stripped):
            return True
        if stripped.startswith("MP:") or stripped.startswith("Sogd"):
            return True
    return False


def pre_clean(text: str) -> str:
    """Light pre-cleaning: strip obvious PDF artifacts before sending to LLM.

    Removes:
    - Running page headers
    - Bare page numbers on their own line
    - Horizontal rule page breaks (--- surrounded by blanks)
    - "INDEX OF SOURCES" and anything after it
    """
    lines = text.split("\n")
    cleaned: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Skip running headers
        if PAGE_HEADER_RE.match(stripped):
            continue

        # Skip bare page numbers
        if BARE_PAGE_NUM_RE.match(stripped):
            continue

        # Skip bare horizontal rules (page breaks)
        if stripped == "---":
            continue

        # Stop at index of sources (end of actual text)
        if stripped.upper().startswith("INDEX OF SOURCES"):
            break

        cleaned.append(line)

    return "\n".join(cleaned)


# ---------------------------------------------------------------------------
# LLM cleaning
# ---------------------------------------------------------------------------

def clean_section(client: OpenAI, deployment: str, section: RawSection,
                  retries: int = 3) -> CleanedSection | None:
    """Send a section to GPT-5.2 for cleaning and separation."""
    pre_cleaned = pre_clean(section.text)

    user_message = (
        f"## Section {section.number}: {section.title}\n"
        f"## Division: {section.division}\n\n"
        f"```\n{pre_cleaned}\n```"
    )

    for attempt in range(retries):
        try:
            response = client.beta.chat.completions.parse(
                model=deployment,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                response_format=CleanedSection,
            )
            result = response.choices[0].message.parsed
            if result is None:
                print(f"    WARNING: LLM returned None for section {section.number}")
                continue
            # Ensure section number matches
            result.section_number = section.number
            return result

        except (RateLimitError, APIStatusError) as e:
            wait = 2 ** (attempt + 1)
            print(f"    API error ({e}), retrying in {wait}s...")
            time.sleep(wait)
        except Exception as e:
            print(f"    ERROR cleaning section {section.number}: {e}")
            if attempt < retries - 1:
                time.sleep(2)

    return None


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def save_section(section_data: CleanedSection, output_dir: Path) -> Path:
    """Save a cleaned section as JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"ch_{section_data.section_number:03d}.json"
    path = output_dir / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(section_data.model_dump(), f, indent=2, ensure_ascii=False)
    return path


def is_cleaned(section_num: int, output_dir: Path) -> bool:
    """Check if a section has already been cleaned."""
    return (output_dir / f"ch_{section_num:03d}.json").exists()


def load_cleaned(section_num: int, output_dir: Path) -> CleanedSection | None:
    """Load a previously cleaned section."""
    path = output_dir / f"ch_{section_num:03d}.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return CleanedSection.model_validate(json.load(f))


def assemble_translation(output_dir: Path, translation_path: Path,
                         apparatus_path: Path) -> None:
    """Assemble all cleaned sections into unified translation and apparatus files."""
    translation_parts: list[str] = []
    apparatus_parts: list[str] = []

    for path in sorted(output_dir.glob("ch_*.json")):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        section = CleanedSection.model_validate(data)

        # Translation file
        translation_parts.append(f"## {section.title}\n")
        if section.manuscript_refs:
            translation_parts.append(
                f"*Manuscripts: {', '.join(section.manuscript_refs)}*\n"
            )
        translation_parts.append(section.english_translation)
        translation_parts.append("\n\n---\n\n")

        # Apparatus file
        apparatus_parts.append(f"## {section.title}\n")
        if section.original_text:
            apparatus_parts.append("### Original Text\n")
            apparatus_parts.append(section.original_text)
            apparatus_parts.append("\n\n")
        if section.footnotes:
            apparatus_parts.append("### Footnotes\n")
            for fn in section.footnotes:
                num = fn.number if isinstance(fn, Footnote) else fn['number']
                text = fn.text if isinstance(fn, Footnote) else fn['text']
                apparatus_parts.append(f"{num}. {text}\n")
            apparatus_parts.append("\n")
        if section.editorial_notes:
            apparatus_parts.append("### Editorial Notes\n")
            apparatus_parts.append(section.editorial_notes)
            apparatus_parts.append("\n\n")
        apparatus_parts.append("---\n\n")

    # Write files
    translation_path.parent.mkdir(parents=True, exist_ok=True)
    with open(translation_path, "w", encoding="utf-8") as f:
        f.write("# Šābuhragān — English Translation\n\n")
        f.write("> Compiled from: Database of Manichaean Texts (DbMT 2022)\n")
        f.write("> Editor: Samuel N.C. Lieu FBA\n\n---\n\n")
        f.write("".join(translation_parts))

    with open(apparatus_path, "w", encoding="utf-8") as f:
        f.write("# Šābuhragān — Original Text & Apparatus\n\n")
        f.write("> Middle Persian / Sogdian transliteration and scholarly footnotes\n\n---\n\n")
        f.write("".join(apparatus_parts))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clean the Šābuhragān: separate Middle Persian from English "
        "translation and remove OCR artifacts"
    )
    parser.add_argument("--chapter", "-c", type=int, default=None,
                        help="Process a single section (by number)")
    parser.add_argument("--range", "-r", type=str, default=None,
                        help="Process a range of sections (e.g. '0-5')")
    parser.add_argument("--limit", "-l", type=int, default=None,
                        help="Process only first N sections")
    parser.add_argument("--dry-run", "-n", action="store_true",
                        help="Show sections without processing")
    parser.add_argument("--overwrite", action="store_true",
                        help="Reprocess already-cleaned sections")
    parser.add_argument("--list", action="store_true",
                        help="List all parsed sections with details")
    parser.add_argument("--assemble", "-a", action="store_true",
                        help="Skip cleaning, assemble existing outputs only")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    # Parse source file into sections
    if not SOURCE_FILE.exists():
        print(f"ERROR: Source file not found at {SOURCE_FILE}")
        print("  Run process_ocr_json.py first to extract text from the PDF.")
        sys.exit(1)

    sections = parse_sections(SOURCE_FILE)
    print(f"Parsed {len(sections)} sections from {SOURCE_FILE.name}\n")

    if not sections:
        print("ERROR: No sections found. Check the source file format.")
        sys.exit(1)

    # --list mode: show all sections
    if args.list:
        for sec in sections:
            markers = SECTION_MARKER_RE.findall(sec.text)
            print(f"  {sec.number:2d}  {sec.title}")
            print(f"       Lines {sec.start_line}-{sec.start_line + sec.line_count} "
                  f"({sec.line_count} lines), "
                  f"{len(markers)} section markers: {', '.join(markers[:5])}"
                  f"{'...' if len(markers) > 5 else ''}")
        return

    # --assemble mode: just rebuild the assembled files
    if args.assemble:
        print("Assembling from existing cleaned sections...")
        assemble_translation(CHAPTERS_DIR, TRANSLATION_FILE, APPARATUS_FILE)
        print(f"  Translation: {TRANSLATION_FILE}")
        print(f"  Apparatus:   {APPARATUS_FILE}")
        return

    # Determine which sections to process
    to_process: list[RawSection] = []

    if args.chapter is not None:
        matches = [s for s in sections if s.number == args.chapter]
        if not matches:
            print(f"ERROR: Section {args.chapter} not found (available: 0-{len(sections)-1})")
            sys.exit(1)
        to_process = matches
    elif args.range:
        try:
            start, end = map(int, args.range.split("-"))
        except ValueError:
            print("ERROR: --range must be in format 'N-M' (e.g. '0-5')")
            sys.exit(1)
        to_process = [s for s in sections if start <= s.number <= end]
    else:
        to_process = list(sections)

    if args.limit:
        to_process = to_process[:args.limit]

    # Filter already-cleaned unless overwriting
    if not args.overwrite:
        already = [s for s in to_process if is_cleaned(s.number, CHAPTERS_DIR)]
        to_process = [s for s in to_process if not is_cleaned(s.number, CHAPTERS_DIR)]
        if already:
            print(f"Skipping {len(already)} already-cleaned sections "
                  f"(use --overwrite to reprocess)")

    if not to_process:
        print("No sections to process.")
        # Still assemble if there are existing outputs
        if list(CHAPTERS_DIR.glob("ch_*.json")):
            assemble_translation(CHAPTERS_DIR, TRANSLATION_FILE, APPARATUS_FILE)
            print(f"  Assembled existing outputs -> {TRANSLATION_FILE.name}")
        return

    # Show what will be processed
    print(f"Processing {len(to_process)} sections:\n")
    for sec in to_process:
        ms_refs = re.findall(r"M\d+[a-z]?(?:\s*\+\s*M\d+[a-z]?)*", sec.text[:500])
        ref_str = f" [{', '.join(ms_refs[:3])}]" if ms_refs else ""
        print(f"  {sec.number:2d}  {sec.title}{ref_str}")
        print(f"       {sec.line_count} lines")
    print()

    if args.dry_run:
        print("[DRY RUN] No API calls made.")
        return

    # Process sections
    client = create_client()
    deployment = get_deployment()
    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)

    success = 0
    failed = 0

    for sec in to_process:
        print(f"\nCleaning section {sec.number}: {sec.title}")
        print(f"  {sec.line_count} lines, starting at line {sec.start_line}")

        result = clean_section(client, deployment, sec)

        if result:
            path = save_section(result, CHAPTERS_DIR)
            lang = result.original_language
            mp_len = len(result.original_text) if result.original_text else 0
            en_len = len(result.english_translation)
            markers = len(result.section_markers)
            fn_count = len(result.footnotes)
            print(f"  ✓ Saved: {path.name}")
            print(f"    Language: {lang}, MP: {mp_len} chars, EN: {en_len} chars, "
                  f"{markers} markers, {fn_count} footnotes")
            success += 1
        else:
            print(f"  ✗ FAILED")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Done: {success} cleaned, {failed} failed")

    # Assemble all outputs
    if success > 0:
        assemble_translation(CHAPTERS_DIR, TRANSLATION_FILE, APPARATUS_FILE)
        print(f"  Translation: {TRANSLATION_FILE}")
        print(f"  Apparatus:   {APPARATUS_FILE}")


if __name__ == "__main__":
    main()
