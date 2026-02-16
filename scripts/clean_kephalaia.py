#!/usr/bin/env python3
"""
Clean Kephalaia chapters using GPT-5.2 to separate teaching text from editorial apparatus.

Reads the raw OCR'd Kephalaia of the Teacher markdown, splits it into chapters,
sends each chapter to GPT-5.2 for cleaning, and produces two output files:
  - kephalaia_teaching.md   (clean teaching text only)
  - kephalaia_apparatus.md  (Gardner commentary, footnotes, editorial observations)

The LLM handles what regex cannot: understanding which text is Mani's teaching
vs. Gardner's scholarly commentary, fixing OCR line-break artifacts, removing
embedded manuscript line numbers, and producing clean readable prose.

Usage:
    python scripts/clean_kephalaia.py                    # Process all chapters
    python scripts/clean_kephalaia.py --chapter 1        # Process single chapter
    python scripts/clean_kephalaia.py --range 0-10       # Process chapter range
    python scripts/clean_kephalaia.py --dry-run           # Show chapters without processing
    python scripts/clean_kephalaia.py --overwrite         # Reprocess already-cleaned chapters
    python scripts/clean_kephalaia.py --list              # List all chapters with line ranges
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

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SECRETS_PATH = PROJECT_ROOT / "secrets" / "azure_openai.env"
SOURCE_FILE = PROJECT_ROOT / "output" / "texts" / "Kephalaia_of_the_Teacher.md"
OUTPUT_DIR = PROJECT_ROOT / "output" / "cleaned"
CHAPTERS_DIR = OUTPUT_DIR / "chapters"
TEACHING_FILE = OUTPUT_DIR / "kephalaia_teaching.md"
APPARATUS_FILE = OUTPUT_DIR / "kephalaia_apparatus.md"

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a scholarly text editor specializing in Manichaean religious texts. You are \
given a raw chapter from Iain Gardner's English translation of the Coptic Kephalaia \
of the Teacher (Medinet Madi codex, Brill 1995). The text was OCR'd from PDF and \
contains many artifacts that need cleaning.

Your task: separate the TEACHING TEXT (Mani's actual words and the narrative frame) \
from the EDITORIAL APPARATUS (Gardner's scholarly commentary, footnotes), and clean \
both. You are NOT rewriting or interpreting. You are restoring and separating.

## SOURCE TEXT STRUCTURE (what you will receive)

Each chapter in the raw source follows this pattern:
1. **Chapter marker**: `··· N ···` (chapter number in middots)
2. **Page range**: `(X,Y - A,B)` — manuscript page.line references
3. **Title**: Usually starts with `/` and contains the chapter heading
4. **Gardner commentary**: One or more paragraphs of scholarly English analysis. \
   Gardner writes in the third person about Mani, references other scholars, uses \
   section references like `(30.33 - 33.1)`, and provides interpretive context. \
   This is ALWAYS before the teaching text begins.
5. **Teaching text**: The actual translated Coptic text. Teaching text contains:
   - Teaching formulas: "Once again the enlightener speaks...", "Then speaks the apostle..."
   - Direct speech by Mani to his disciples
   - Disciple questions and Mani's responses
   - Cosmological, ethical, and doctrinal content
   - Lacunae: `[...]` or `[ ... ]` (text lost to manuscript damage)
   - Editorial restorations: `[restored text]` in square brackets
   - Manuscript line-break markers: `/` between clauses
   - Embedded manuscript line numbers: bare numbers (5, 10, 15, 20, 25, 30, 35) \
     that interrupt the English text at regular intervals
   - Page transitions: `---` dividers followed by page numbers and running headers
   - Footnotes: `*N text` format at various points
   - Closing formulas: disciples rejoicing, thanking Mani
6. **Page artifacts interspersed**: standalone page numbers (e.g. `36`, `37`), \
   running headers (`THE KEPHALAIA OF THE TEACHER`, `CHAPTER SIX`), and `---` dividers

## WHAT TO PRODUCE

Return a structured response with the chapter number, title, cleaned teaching text, \
Gardner's scholarly synopsis, collected footnotes, editorial notes about corrections made, \
and the manuscript page range.

## CLEANING RULES FOR TEACHING TEXT

1. **Remove embedded manuscript line numbers**: Bare numbers (5, 10, 15, 20, 25, 30, 35) \
   that appear in the running text marking Coptic manuscript line positions. \
   Example: "five s[to]/rehouses have arisen since the beginning 20 in the land" → \
   remove the "20". KEEP numbers that are actual content ("five storehouses", "twelve aeons").

2. **Remove `/` line-break markers**: These mark Coptic manuscript line breaks. \
   Replace with space or nothing as appropriate for English flow. \
   Example: "five s[to]/rehouses" → "five storehouses" (rejoin broken word). \
   Example: "his disciples / and his" → "his disciples and his" (space).

3. **Remove page transitions**: Delete `---` dividers, standalone page numbers \
   (e.g. `36`, `37`), and running headers (`THE KEPHALAIA OF THE TEACHER`, \
   `CHAPTER SIX`, `CHAPTER EIGHTY-FOUR`, etc.).

4. **Remove footnote markers from text**: Remove `*N` markers from the teaching text \
   body. Collect footnotes separately.

5. **Fix broken words**: Words split across line breaks: "s[to]/rehouses" → \
   "storehouses", "dan[ger]s" → "dangers", "ap[os] tolate" → "apostolate".

6. **Preserve lacunae**: Keep `[...]` markers exactly — these represent lost text.

7. **Preserve editorial restorations**: Keep `[restored text]` brackets — these \
   show where Gardner restored damaged text.

8. **Add manuscript page markers**: Insert `⟨p.N⟩` at manuscript page transitions \
   (you can determine these from the page numbers that appear in the raw text).

9. **Paragraph the text**: Break the teaching text into readable paragraphs at \
   natural thematic boundaries. The raw text is often one continuous block.

10. **Resolve pronoun markers**: Gardner marks `(pl.)` and `(sg.)` to indicate \
    Coptic plural/singular. You may silently remove these or keep them as \
    translator's notes — your judgment.

11. **Fix OCR artifacts**: Rejoin words broken by OCR across lines. Fix obvious \
    OCR errors where detectable (e.g., `1` for `l`, `º` for `o`).

12. **Preserve `(manuscript page)` markers**: Numbers in parentheses like `(10)`, \
    `(31)`, `(103)` that appear at the start of a line or inline mark manuscript \
    page boundaries. Convert these to `⟨p.N⟩` format.

## CLEANING RULES FOR GARDNER SYNOPSIS

1. Keep Gardner's scholarly commentary intact — every word.
2. Fix only OCR artifacts (broken words, etc.).
3. Keep his manuscript section references like `(30.33 - 33.1)`.
4. Keep his scholarly citations.

## CRITICAL RULES

- **DO NOT alter the meaning of the translation.** Every word of Mani's teaching \
  must be preserved. You are cleaning artifacts, not editing content.
- **DO NOT remove textual apparatus** — lacuna brackets [...], editorial \
  restorations [text]. Only remove LINE NUMBERS and PAGE ARTIFACTS.
- **The Gardner synopsis is ALWAYS recognizable**: it is analytical scholarly \
  English about Mani in third person, never direct speech or teaching formula.
- **The teaching text ALWAYS begins with a formula**: "Once again...", \
  "The first chapter is this...", "Then speaks...", a disciple asking a question, etc.
- **When in doubt about a number**, check: does it fit the 5/10/15/20/25/30/35 \
  pattern of manuscript line numbers? Is it interrupting English text? Then remove it.\
"""


# ---------------------------------------------------------------------------
# Pydantic models (structured output schema)
# ---------------------------------------------------------------------------

class Footnote(BaseModel):
    """A single footnote extracted from the chapter."""
    number: int = Field(description="Footnote number as it appears in the text (e.g. *11 → 11)")
    text: str = Field(description="Full footnote text, with OCR artifacts cleaned")


class CleanedChapter(BaseModel):
    """Structured output for a cleaned Kephalaia chapter."""
    chapter_number: int = Field(
        description="Chapter number from the chapter marker (0 for Introduction)"
    )
    title: str = Field(
        description="Chapter title from the manuscript, cleaned of artifacts. "
        "Usually starts after the chapter marker line."
    )
    teaching_text: str = Field(
        description="The cleaned teaching text — Mani's actual words and the narrative "
        "frame. All OCR artifacts removed, manuscript line numbers removed, page "
        "transitions removed, broken words rejoined, paragraphed at natural boundaries. "
        "Lacunae [...] and editorial restorations [text] preserved."
    )
    gardner_synopsis: str = Field(
        description="Gardner's scholarly commentary paragraphs, kept intact with only "
        "OCR artifacts fixed. This is analytical scholarly English about Mani, always "
        "in third person."
    )
    footnotes: list[Footnote] = Field(
        default_factory=list,
        description="Collected footnotes from the chapter. Each footnote has a number "
        "and text. Empty list if no footnotes present."
    )
    editorial_notes: str = Field(
        default="",
        description="Notes about manuscript condition, OCR corrections made, "
        "significant lacunae, or other editorial observations."
    )
    manuscript_pages: str = Field(
        description="Manuscript page range, e.g. '30,12 - 34,12'. "
        "Extracted from the page reference near the chapter marker."
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
# Chapter parsing
# ---------------------------------------------------------------------------

# Matches chapter markers in various OCR'd forms:
#   ··· N ···           (standard)
#   ··· N               (no closing dots)
#   ... N ...           (plain dots instead of middots)
#   ··· N ... (X,Y-A,B) (page ref on same line)
#   ··· (Introduction) ··· 
#   ··· . ···           (Ch.1 special)
CHAPTER_MARKER_RE = re.compile(
    r'^[·.…]{2,}\s*'                    # opening: 2+ dots/middots
    r'(?:'
    r'(\d+)'                            # capture: chapter number
    r'|\(\s*Introduction\s*\)'          # or: (Introduction)
    r'|\.'                              # or: bare dot (Ch.1)
    r')'
    r'\s*'                              # optional whitespace
    r'(?:[·.…]+\s*)?'                  # optional closing dots
    r'(?:\([\d,.\s\-]+\)\s*)?'         # optional page ref on same line
    r'$',
    re.IGNORECASE
)


def parse_chapters(source_path: Path) -> list[dict]:
    """Parse the source file into chapter chunks.
    
    Returns list of dicts: {number, start_line, end_line, raw_text}
    """
    lines = source_path.read_text(encoding="utf-8").splitlines()
    
    # Find all chapter markers
    markers = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        m = CHAPTER_MARKER_RE.match(stripped)
        if m:
            if m.group(1):
                ch_num = int(m.group(1))
            elif "Introduction" in stripped:
                ch_num = 0
            elif re.match(r'^[·.…]+\s*\.\s*[·.…]+$', stripped):
                ch_num = 1  # special case: ··· . ···
            else:
                continue
            markers.append((ch_num, i))
    
    if not markers:
        print("ERROR: No chapter markers found in source file!")
        sys.exit(1)
    
    # Build chapter chunks
    chapters = []
    for idx, (ch_num, start_line) in enumerate(markers):
        if idx + 1 < len(markers):
            end_line = markers[idx + 1][1]
        else:
            # Last chapter — go to end of file (excluding bibliography etc.)
            end_line = len(lines)
        
        raw_text = "\n".join(lines[start_line:end_line])
        chapters.append({
            "number": ch_num,
            "start_line": start_line + 1,  # 1-based
            "end_line": end_line,           # 1-based exclusive
            "raw_text": raw_text,
        })
    
    return chapters


# ---------------------------------------------------------------------------
# LLM processing
# ---------------------------------------------------------------------------

def clean_chapter(client: OpenAI, deployment: str, chapter: dict) -> CleanedChapter | None:
    """Send a chapter to GPT-5.2 for cleaning using structured output.
    
    Returns a validated CleanedChapter Pydantic model, or None on failure.
    """
    user_msg = (
        "I am a scholar preparing a clean critical edition of the Kephalaia of the Teacher "
        "for academic research. The following is a raw chapter extracted from Gardner's "
        "translation (Brill, 1995). It contains OCR artifacts, embedded manuscript line "
        "numbers, page transition artifacts, and mixed editorial/teaching content. "
        "Please separate and clean it according to your instructions.\n\n"
        f"--- RAW CHAPTER {chapter['number']} ---\n\n"
        f"{chapter['raw_text']}"
    )

    max_retries = 3
    backoff = 2.0
    for attempt in range(1, max_retries + 1):
        try:
            response = client.responses.parse(
                model=deployment,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                text_format=CleanedChapter,
                max_output_tokens=16384,
            )

            result = response.output_parsed
            if result is None:
                raise ValueError("No structured output returned (parsed is None)")
            return result

        except RateLimitError as e:
            wait = 60.0
            print(f"(rate limit, retry {attempt}/{max_retries} in {wait:.0f}s)...",
                  end=" ", flush=True)
            time.sleep(wait)

        except APIStatusError as e:
            err_str = str(e)
            if "content_filter" in err_str.lower() and attempt < max_retries:
                wait = attempt * 10
                print(f"(filter hit, retry {attempt}/{max_retries} in {wait}s)...",
                      end=" ", flush=True)
                time.sleep(wait)
                continue
            print(f"API error: {e}")
            if attempt < max_retries:
                wait = backoff
                time.sleep(wait)
                backoff *= 2
                continue
            return None

        except Exception as e:
            err_str = str(e)
            if "content_filter" in err_str.lower() and attempt < max_retries:
                wait = attempt * 10
                print(f"(filter exception, retry {attempt}/{max_retries} in {wait}s)...",
                      end=" ", flush=True)
                time.sleep(wait)
                continue
            print(f"ERROR: {e}")
            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 2
                continue
            return None

    return None


# ---------------------------------------------------------------------------
# Output assembly
# ---------------------------------------------------------------------------

def save_chapter_json(chapter_result: CleanedChapter, ch_num: int) -> None:
    """Save individual chapter result as JSON (from Pydantic model)."""
    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CHAPTERS_DIR / f"ch_{ch_num:03d}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(chapter_result.model_dump(mode="json"), f, indent=2, ensure_ascii=False)


def load_chapter_json(ch_num: int) -> dict | None:
    """Load a previously cleaned chapter from JSON."""
    path = CHAPTERS_DIR / f"ch_{ch_num:03d}.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def assemble_teaching_file(all_chapters: list[dict]) -> None:
    """Assemble all cleaned chapters into the teaching text file."""
    parts = [
        "# Kephalaia of the Teacher — Teaching Text\n",
        "",
        "A clean reconstruction of the teaching content from Iain Gardner's English "
        "translation of the Coptic Kephalaia (Medinet Madi codex). Editorial commentary, "
        "footnotes, page numbers, running headers, and manuscript line numbers have been "
        "removed. Only the translated teaching text remains.",
        "",
        "**Conventions:**",
        "- `[...]` — Lacuna (text lost due to manuscript damage)",
        "- `[text]` — Editorial restoration of damaged text",
        "- `⟨p.N⟩` — Manuscript page transition marker",
        "- Chapter titles are as given in the manuscript colophons or by Gardner",
        "",
        "---",
        "",
    ]
    
    for ch in sorted(all_chapters, key=lambda c: c.get("chapter_number", 0)):
        ch_num = ch.get("chapter_number", "?")
        title = ch.get("title", "Untitled")
        ms_pages = ch.get("manuscript_pages", "")
        teaching = ch.get("teaching_text", "")
        
        if ch_num == 0:
            parts.append(f"## Introduction")
        else:
            parts.append(f"## Chapter {ch_num}: {title}")
        
        if ms_pages:
            parts.append(f"*Manuscript pages {ms_pages}*")
        parts.append("")
        parts.append(teaching)
        parts.append("")
        parts.append("---")
        parts.append("")
    
    TEACHING_FILE.write_text("\n".join(parts), encoding="utf-8")
    print(f"  Teaching file assembled: {TEACHING_FILE}")


def assemble_apparatus_file(all_chapters: list[dict]) -> None:
    """Assemble all cleaned chapters into the apparatus file."""
    parts = [
        "# Kephalaia of the Teacher — Editorial Apparatus\n",
        "",
        "Scholarly commentary, footnotes, and editorial observations from Iain Gardner's "
        "English translation of the Coptic Kephalaia (Medinet Madi codex). This material "
        "accompanies the clean teaching text in `kephalaia_teaching.md`.",
        "",
        "---",
        "",
    ]
    
    for ch in sorted(all_chapters, key=lambda c: c.get("chapter_number", 0)):
        ch_num = ch.get("chapter_number", "?")
        title = ch.get("title", "Untitled")
        ms_pages = ch.get("manuscript_pages", "")
        synopsis = ch.get("gardner_synopsis", "")
        footnotes = ch.get("footnotes", [])
        notes = ch.get("editorial_notes", "")
        
        if ch_num == 0:
            parts.append(f"## Introduction")
        else:
            parts.append(f"## Chapter {ch_num}: {title}")
        
        if ms_pages:
            parts.append(f"**Manuscript pages**: {ms_pages}")
        parts.append("")
        
        if synopsis:
            parts.append("### Gardner Synopsis")
            parts.append("")
            # Wrap each paragraph in blockquote
            for para in synopsis.split("\n\n"):
                para = para.strip()
                if para:
                    parts.append(f"> {para}")
                    parts.append(">")
            if parts[-1] == ">":
                parts.pop()
            parts.append("")
        
        if footnotes:
            parts.append("### Footnotes")
            parts.append("")
            for fn in footnotes:
                fn_num = fn.get("number", "?")
                fn_text = fn.get("text", "")
                parts.append(f"{fn_num}. {fn_text}")
            parts.append("")
        
        if notes:
            parts.append("### Editorial Notes")
            parts.append("")
            parts.append(notes)
            parts.append("")
        
        parts.append("---")
        parts.append("")
    
    APPARATUS_FILE.write_text("\n".join(parts), encoding="utf-8")
    print(f"  Apparatus file assembled: {APPARATUS_FILE}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Clean Kephalaia chapters with GPT-5.2"
    )
    parser.add_argument(
        "--chapter", type=int,
        help="Process a single chapter number (0 = Introduction)"
    )
    parser.add_argument(
        "--range", type=str,
        help="Process a range of chapters (e.g. 0-10, 50-60)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="List chapters without processing"
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List all chapters with line ranges"
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Reprocess already-cleaned chapters"
    )
    parser.add_argument(
        "--assemble-only", action="store_true",
        help="Skip LLM processing, just assemble output files from existing chapter JSONs"
    )
    args = parser.parse_args()

    if not SOURCE_FILE.exists():
        print(f"ERROR: Source file not found: {SOURCE_FILE}")
        sys.exit(1)

    # Parse all chapters
    print(f"Parsing chapters from: {SOURCE_FILE.name}")
    chapters = parse_chapters(SOURCE_FILE)
    print(f"Found {len(chapters)} chapters")

    # Filter to requested chapters
    if args.chapter is not None:
        chapters = [c for c in chapters if c["number"] == args.chapter]
        if not chapters:
            print(f"ERROR: Chapter {args.chapter} not found")
            sys.exit(1)
    elif args.range:
        range_match = re.match(r"(\d+)-(\d+)", args.range)
        if not range_match:
            print("ERROR: --range must be in format N-M (e.g. 0-10)")
            sys.exit(1)
        lo, hi = int(range_match.group(1)), int(range_match.group(2))
        chapters = [c for c in chapters if lo <= c["number"] <= hi]
        if not chapters:
            print(f"ERROR: No chapters found in range {lo}-{hi}")
            sys.exit(1)

    # List mode
    if args.list or args.dry_run:
        for ch in chapters:
            existing = load_chapter_json(ch["number"])
            status = "DONE" if existing else "PENDING"
            lines = ch["end_line"] - ch["start_line"]
            raw_chars = len(ch["raw_text"])
            print(
                f"  [{status:>7}] Ch.{ch['number']:>3}  "
                f"L{ch['start_line']:>4}-{ch['end_line']:<4}  "
                f"({lines:>3} lines, {raw_chars:>5} chars)"
            )
        return

    # Assemble-only mode
    if args.assemble_only:
        print("Assembling output files from existing chapter JSONs...")
        all_results = []
        for ch in parse_chapters(SOURCE_FILE):
            result = load_chapter_json(ch["number"])
            if result:
                all_results.append(result)
        if all_results:
            assemble_teaching_file(all_results)
            assemble_apparatus_file(all_results)
            print(f"Assembled {len(all_results)} chapters.")
        else:
            print("No cleaned chapter JSONs found.")
        return

    # Process chapters
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)

    client = create_client()
    deployment = get_deployment()

    processed = 0
    skipped = 0
    errors = 0
    start_time = time.time()

    for i, ch in enumerate(chapters, 1):
        ch_num = ch["number"]
        
        # Check if already done
        if not args.overwrite and load_chapter_json(ch_num) is not None:
            print(f"[{i}/{len(chapters)}] Ch.{ch_num:>3} — SKIP (exists)")
            skipped += 1
            continue

        lines_count = ch["end_line"] - ch["start_line"]
        print(
            f"[{i}/{len(chapters)}] Ch.{ch_num:>3} "
            f"({lines_count} lines, {len(ch['raw_text']):,} chars)...",
            end=" ", flush=True,
        )

        result = clean_chapter(client, deployment, ch)
        if result:
            # Override chapter_number with the parsed value from our markers
            result.chapter_number = ch_num
            save_chapter_json(result, ch_num)
            title = result.title or "Untitled"
            teaching_len = len(result.teaching_text or "")
            print(f"OK — \"{title[:50]}\" ({teaching_len:,} chars teaching)")
            processed += 1
        else:
            print(f"FAILED")
            errors += 1

        # Brief pause between API calls
        if i < len(chapters):
            time.sleep(1)

    elapsed = time.time() - start_time
    print(
        f"\nDone in {elapsed:.1f}s — "
        f"Processed: {processed}, Skipped: {skipped}, Errors: {errors}"
    )

    # Auto-assemble if we processed anything
    if processed > 0:
        print("\nAssembling output files...")
        all_results = []
        for ch in parse_chapters(SOURCE_FILE):
            result = load_chapter_json(ch["number"])
            if result:
                all_results.append(result)
        if all_results:
            assemble_teaching_file(all_results)
            assemble_apparatus_file(all_results)


if __name__ == "__main__":
    main()
