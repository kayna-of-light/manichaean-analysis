#!/usr/bin/env python3
"""
Correspondential Restoration of the Kephalaia Teaching Core.

Reads the extracted core text through the correspondential lens and
restores lacunae using the spiritual logic of the text itself.

Architecture: the model receives the full chapter text plus a numbered
list of all lacunae (square brackets). It outputs fill text for each
lacuna. The fills are then programmatically inserted into the original
text, guaranteeing that no non-bracket text is ever altered.

Input:  output/core/chapters/ch_NNN.json   (from extract_core.py)
Output: output/correspondential/chapters/ch_NNN.json   (fills)
        output/correspondential/restored_kephalaia.md   (assembled)

Usage:
    python scripts/correspondential_reading.py                  # All
    python scripts/correspondential_reading.py --chapter 38     # Single
    python scripts/correspondential_reading.py --dry-run        # Preview
    python scripts/correspondential_reading.py --overwrite      # Redo
    python scripts/correspondential_reading.py --assemble       # Assemble
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
CORE_CHAPTERS_DIR = PROJECT_ROOT / "output" / "core" / "chapters"
OUTPUT_DIR = PROJECT_ROOT / "output" / "correspondential"
CHAPTERS_OUT_DIR = OUTPUT_DIR / "chapters"
ASSEMBLED_FILE = OUTPUT_DIR / "restored_kephalaia.md"


# ---------------------------------------------------------------------------
# Pydantic models for structured LLM output
# ---------------------------------------------------------------------------

class LacunaFill(BaseModel):
    """Model output for a single lacuna restoration."""
    paragraph: int = Field(
        description="Paragraph number from the input text."
    )
    index: int = Field(
        description=(
            "1-based index of this bracket within the paragraph, "
            "counting left to right."
        )
    )
    fill: str = Field(
        description=(
            "The text to place inside the square brackets. "
            "Do NOT include the brackets themselves. "
            "Return '...' if the gap is unrestorable."
        )
    )
    notes: str = Field(
        description=(
            "Brief correspondential reasoning for the fill. "
            "For trivial letter fills where the reading is certain, "
            "use an empty string."
        )
    )
    confidence: str = Field(
        description=(
            "'strong' = reading is certain or tightly constrained. "
            "'moderate' = direction clear but exact wording uncertain. "
            "'tentative' = plausible but other readings possible. "
            "'minimal' = too damaged for meaningful reconstruction."
        )
    )


class ChapterResult(BaseModel):
    """Restoration result for one chapter."""
    fills: list[LacunaFill] = Field(
        description=(
            "One fill per lacuna listed in the input. Every listed "
            "lacuna must have a corresponding fill entry."
        )
    )
    assessment: str = Field(
        description=(
            "Overall assessment: How much of this chapter's damaged "
            "text could be recovered? How tight were the "
            "correspondential constraints?"
        )
    )


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are restoring the OLDEST TEACHING SUBSTRATE of the Coptic Kephalaia \u2014 \
the pre-Manichaean cosmological teaching that Mani inherited, compiled, \
and overlaid with his own institutional language. Your task is to fill \
lacunae (gaps in square brackets) using the correspondential logic of \
the text, in the vocabulary of the OLDEST LAYER.

## WHAT YOU ARE RESTORING

This is NOT Mani\u2019s text. This is what is UNDERNEATH Mani\u2019s text. The \
Kephalaia is a composite: a pre-existing cosmological teaching tradition \
was compiled by Mani\u2019s community and wrapped in hagiographic frame, \
institutional language, and Christian overlay. The core extraction you \
receive has already stripped the frame and most overlays. But the \
VOCABULARY of the core may still carry Coptic translation artifacts and \
editorial choices that obscure the original register.

### The Three Layers

1. **OLDEST SUBSTRATE** (what we are restoring):
   Pre-Manichaean cosmological teaching from the Eastern tradition. \
   At its deepest, this is the tradition of the Bene Qedem (\u201cChildren \
   of the East\u201d) \u2014 the correspondential science preserved in what \
   Swedenborg called \u201cGreat Tartary.\u201d More immediately, it is Persian/ \
   Iranian cosmological wisdom: Zoroastrian in structure, correspondential \
   in method, impersonal in voice. This layer EXPOUNDS how reality works. \
   It does not cite authorities, it does not preach, it does not exhort.

2. **MANI\u2019S COMPILATION** (Layer 2):
   Mani took this teaching and reframed it. He added dialogue frames \
   (\u201cThen speaks the apostle to him:\u201d), mapped some entities onto \
   Christian names, and inserted institutional categories. The TEACHING \
   CONTENT is often preserved intact; the FRAMING is Mani\u2019s.

3. **LATER COMMUNITY** (Layer 3):
   Pastoral rules, NT exempla, devotional additions.

### Vocabulary Register

The text you receive has been restored to substrate register by the \
extraction pass. The non-bracket text should already be in the register \
of the Persian/Iranian cosmological tradition (or deeper, Bene Qedem).

When you fill brackets, maintain the same register as the surrounding \
text. Match the vocabulary the extraction pass established.

### Previous Editors\u2019 Choices

Existing bracket fills [text] from Gardner and Funk may still carry \
Coptic/Christian register. Evaluate each against the substrate register \
of the surrounding restored text. Accept when it fits. Adjust when the \
correspondential logic and the tradition demand it. Note changes.

## METHOD: CORRESPONDENTIAL READING

Read the text through the theory of correspondences. Correspondence is \
the organic relationship between a natural object and the spiritual \
reality it expresses \u2014 NOT allegory, NOT metaphor. The natural IS the \
spiritual in ultimates. Direction: INSIDE \u2192 OUTSIDE.

Key principles:
- DISCRETE DEGREES: Celestial (love/will), spiritual (wisdom/truth), \
  natural (effects). Complete levels, not a continuum.
- OPPOSITE SENSE: Same image can express good or evil by context.
- CONSTANT STATE, VARIABLE FORM: Underlying reality is constant; forms \
  vary by the receiver\u2019s repertoire.

You are deeply trained on Swedenborg\u2019s writings, the doctrine of \
correspondences, Zoroastrian cosmology (Bundahishn, Avesta), and the \
Manichaean cosmogonic myth. Trust that training. Let the spiritual \
logic of the text and the structure of the Persian substrate constrain \
what can appear at each point.

## NAMES AND ETYMOLOGY

Names are never arbitrary. Understand the ROOT: Semitic, Greek, Aramaic, \
Persian origins. The root illuminates the spiritual function. When a \
name appears in a gap, reconstruct from the FUNCTION the cosmic being \
serves in context, using the naming conventions of the oldest substrate.

## THE BRACKET SYSTEM

The text uses square brackets for editorial apparatus:
- [...] \u2014 complete gap, nothing readable
- [text] \u2014 editor\u2019s reconstruction of damaged text
- [le]tter \u2014 partial word: letters outside brackets are certain, \
  inside brackets are reconstructed
- [text ... ] \u2014 partially readable text followed by a gap
- [text (?) ...] \u2014 uncertain reading followed by a gap

You receive a numbered list of all brackets in the chapter. For each, \
provide the text that should go inside the brackets.

## HOW TO FILL

1. Read the ENTIRE chapter text to grasp its correspondential structure.
2. For each lacuna, determine what the spiritual logic DEMANDS at \
   that point. The text is a correspondence map \u2014 when you read it \
   spiritually, gaps that are opaque on the surface become constrained \
   by the spiritual narrative.
3. Your fill REPLACES the content inside the brackets. Do NOT include \
   brackets in your fill.
4. For mid-word brackets like garm[ents], your fill must produce a \
   valid word with the surrounding text. The letters outside brackets \
   are fixed \u2014 your fill must join them into a coherent word.
5. For [...] gaps, provide your best reconstruction in the register of \
   the OLDEST SUBSTRATE. Think: what would a Persian cosmological \
   teacher say at this point? What does the correspondential structure \
   demand?
6. For existing editor fills, evaluate whether the fill matches the \
   substrate register. Accept if sound. Adjust if the spiritual logic \
   or the substrate vocabulary demands a different reading. Note the \
   change and reasoning.
7. If a gap truly cannot be restored, return "..." as the fill.
8. Use language consistent with the OLDEST LAYER of the text \u2014 \
   cosmological, structural, impersonal. Not devotional, not pastoral, \
   not Christian-soteriological.
9. For trivial single-letter fills where the reading is certain, \
   return the same letter with empty notes and confidence \u2018strong\u2019.
10. For substantial restorations, explain the correspondential \
    reasoning in notes \u2014 including any substrate-register adjustments \
    you made to existing editor fills.
"""


# ---------------------------------------------------------------------------
# Bracket identification
# ---------------------------------------------------------------------------

LACUNA_RE = re.compile(r"\[([^\]]*)\]")


def find_lacunae(
    core_paras: list[dict],
) -> tuple[dict[int, list[dict]], int]:
    """Identify all [bracket] spans in core paragraphs.

    Returns:
        lacunae_map: {paragraph_number: [{'index', 'content', 'original'}, ...]}
        total: total count across chapter
    """
    lacunae_map: dict[int, list[dict]] = {}
    total = 0
    for p in core_paras:
        pnum = p["paragraph_number"]
        text = p["core_text"]
        matches = list(LACUNA_RE.finditer(text))
        if matches:
            lacunae_map[pnum] = []
            for i, m in enumerate(matches, 1):
                lacunae_map[pnum].append(
                    {
                        "index": i,
                        "start": m.start(),
                        "end": m.end(),
                        "original": m.group(0),
                        "content": m.group(1),
                    }
                )
            total += len(matches)
    return lacunae_map, total


# ---------------------------------------------------------------------------
# Message construction
# ---------------------------------------------------------------------------

def build_user_message(
    core_paras: list[dict],
    lacunae_map: dict[int, list[dict]],
    total_lacunae: int,
) -> str:
    """Build user message: full chapter text + numbered lacunae list."""
    lines: list[str] = []
    lines.append(
        "Read the following core text correspondentially and "
        "restore all lacunae listed below.\n"
    )
    lines.append("--- CORE TEXT (oldest teaching layer) ---\n")
    for p in core_paras:
        lines.append(f"\u00b6{p['paragraph_number']}: {p['core_text']}")
        lines.append("")

    lines.append(f"\n--- LACUNAE ({total_lacunae} total) ---\n")
    for pnum in sorted(lacunae_map.keys()):
        for lac in lacunae_map[pnum]:
            lines.append(f"\u00b6{pnum} #{lac['index']}: {lac['original']}")

    lines.append("\n--- END ---")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Azure OpenAI client
# ---------------------------------------------------------------------------

def create_client() -> OpenAI:
    config = dotenv_values(SECRETS_PATH)
    return OpenAI(
        api_key=config["OPENAI_API_KEY"],
        base_url=config["OPENAI_ENDPOINT"],
    )


def get_deployment() -> str:
    config = dotenv_values(SECRETS_PATH)
    return config["OPENAI_DEPLOYMENT"]


# ---------------------------------------------------------------------------
# Load extracted core chapters
# ---------------------------------------------------------------------------

def load_core_chapters() -> list[dict]:
    """Load all extracted core chapter JSON files."""
    chapters = []
    for path in sorted(CORE_CHAPTERS_DIR.glob("ch_*.json")):
        with open(path, encoding="utf-8") as f:
            chapters.append(json.load(f))
    return chapters


def load_core_chapter(ch_num: int) -> dict | None:
    path = CORE_CHAPTERS_DIR / f"ch_{ch_num:03d}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def extract_core_paragraphs(chapter: dict) -> list[dict]:
    """Extract paragraphs that have core_text from an extraction."""
    result = []
    for para in chapter.get("paragraphs", []):
        if para.get("core_text"):
            result.append(
                {
                    "paragraph_number": para["paragraph_number"],
                    "core_text": para["core_text"],
                }
            )
    return result


# ---------------------------------------------------------------------------
# Restoration via LLM
# ---------------------------------------------------------------------------

def restore_chapter(
    client: OpenAI,
    deployment: str,
    core_paras: list[dict],
    lacunae_map: dict[int, list[dict]],
    total_lacunae: int,
    ch_num: int,
) -> ChapterResult | None:
    """Send chapter to GPT-5.2 for per-lacuna restoration."""
    user_msg = build_user_message(core_paras, lacunae_map, total_lacunae)

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
                text_format=ChapterResult,
            )
            result = response.output_parsed
            if result is None:
                raise ValueError("No structured output (parsed is None)")
            return result

        except RateLimitError:
            wait = 60.0
            print(
                f"  (rate limit, retry {attempt}/{max_retries} "
                f"in {wait:.0f}s)...",
                end=" ",
                flush=True,
            )
            time.sleep(wait)

        except APIStatusError as e:
            err_str = str(e)
            if "content_filter" in err_str.lower() and attempt < max_retries:
                wait = attempt * 10
                print(
                    f"  (filter, retry {attempt}/{max_retries} "
                    f"in {wait}s)...",
                    end=" ",
                    flush=True,
                )
                time.sleep(wait)
                continue
            print(f"  API error: {e}")
            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 2
                continue
            return None

        except Exception as e:
            err_str = str(e)
            if "content_filter" in err_str.lower() and attempt < max_retries:
                time.sleep(attempt * 10)
                continue
            print(f"  ERROR Ch.{ch_num}: {e}")
            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 2
                continue
            return None

    return None


# ---------------------------------------------------------------------------
# Post-processing: apply fills to original text
# ---------------------------------------------------------------------------

def apply_fills_to_paragraph(text: str, fills: list[dict]) -> str:
    """Replace [bracket] spans in text with model fills.

    Operates right-to-left to preserve character positions.
    Only touches square brackets -- page markers (angle brackets) and
    text outside brackets are never altered.
    """
    matches = list(LACUNA_RE.finditer(text))
    if not matches:
        return text

    fill_by_idx = {f["index"]: f["fill"] for f in fills}

    # Replace right-to-left to preserve positions
    result = text
    for i in range(len(matches), 0, -1):
        m = matches[i - 1]
        if i in fill_by_idx:
            result = result[: m.start()] + f"[{fill_by_idx[i]}]" + result[m.end() :]

    return result


# ---------------------------------------------------------------------------
# Save / Load
# ---------------------------------------------------------------------------

def save_result(
    ch_num: int,
    title: str,
    result: ChapterResult,
    lacunae_map: dict[int, list[dict]],
    total_lacunae: int,
) -> None:
    CHAPTERS_OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = CHAPTERS_OUT_DIR / f"ch_{ch_num:03d}.json"

    # Serialise lacunae_map with string keys for JSON
    lacunae_serial = {str(k): v for k, v in lacunae_map.items()}

    data = {
        "chapter_number": ch_num,
        "chapter_title": title,
        "total_lacunae": total_lacunae,
        "lacunae_map": lacunae_serial,
        **result.model_dump(),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_result(ch_num: int) -> dict | None:
    path = CHAPTERS_OUT_DIR / f"ch_{ch_num:03d}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def is_done(ch_num: int) -> bool:
    return (CHAPTERS_OUT_DIR / f"ch_{ch_num:03d}.json").exists()


# ---------------------------------------------------------------------------
# Assembly: build the restored document
# ---------------------------------------------------------------------------

def assemble_restored(core_chapters: dict[int, dict]) -> str:
    """Assemble all restorations into a continuous restored document.

    For each chapter, outputs all core paragraphs with fills applied.
    Notes are shown for fills that have non-empty notes (i.e. where
    correspondential reasoning was applied, not trivial letter fills).
    """
    # Load all restoration files
    restorations_by_ch: dict[int, dict] = {}
    for path in sorted(CHAPTERS_OUT_DIR.glob("ch_*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            restorations_by_ch[data["chapter_number"]] = data

    if not restorations_by_ch:
        print("ERROR: No restoration files found.")
        return ""

    lines: list[str] = []
    lines.append("# The Kephalaia Teaching Core \u2014 Restored Text")
    lines.append("")
    lines.append("*The oldest teaching layer of the Kephalaia with lacunae*")
    lines.append("*restored using correspondential constraints. All editorial*")
    lines.append("*content appears in [square brackets]. Unrestorable gaps*")
    lines.append("*remain as [...]*")
    lines.append("")
    lines.append("---")
    lines.append("")

    total_fills = 0
    total_unrestorable = 0

    for ch_num in sorted(
        set(list(core_chapters.keys()) + list(restorations_by_ch.keys()))
    ):
        core_ch = core_chapters.get(ch_num)
        rest_ch = restorations_by_ch.get(ch_num)

        if not core_ch:
            continue

        title = core_ch.get("chapter_title", f"Chapter {ch_num}")
        lines.append(f"## Chapter {ch_num}: {title}")
        lines.append("")

        # Build fill lookup: {paragraph_num: [fill_dicts]}
        fills_by_para: dict[int, list[dict]] = {}
        if rest_ch:
            for fill in rest_ch.get("fills", []):
                para = fill["paragraph"]
                if para not in fills_by_para:
                    fills_by_para[para] = []
                fills_by_para[para].append(fill)

        # Process each paragraph
        for para in core_ch.get("paragraphs", []):
            pnum = para["paragraph_number"]
            core_text = para.get("core_text")
            if not core_text:
                continue

            para_fills = fills_by_para.get(pnum)
            if para_fills:
                # Apply fills programmatically
                restored = apply_fills_to_paragraph(core_text, para_fills)
                lines.append(f"**\u00b6{pnum}** {restored}")
                lines.append("")

                # Collect notes for non-trivial fills
                interesting = [
                    f for f in para_fills if f.get("notes", "").strip()
                ]
                if interesting:
                    for f in interesting:
                        conf = f.get("confidence", "")
                        notes = f["notes"]
                        lines.append(
                            f"> *\u00b6{pnum} #{f['index']} [{conf}]:* {notes}"
                        )
                    lines.append("")

                # Count fills vs unrestorable
                for f in para_fills:
                    if f.get("fill", "...").strip() == "...":
                        total_unrestorable += 1
                    else:
                        total_fills += 1
            else:
                # No lacunae -- original text as-is
                lines.append(f"**\u00b6{pnum}** {core_text}")
                lines.append("")

        # Chapter assessment
        if rest_ch:
            assessment = rest_ch.get("assessment", "")
            if assessment:
                lines.append(f"**Assessment:** {assessment}")
                lines.append("")

        lines.append("---")
        lines.append("")

    # Prepend statistics
    stats_block = [
        f"**Lacunae filled**: {total_fills}",
        f"**Unrestorable**: {total_unrestorable}",
        "",
    ]
    insert_pos = lines.index("---") + 2
    for i, s in enumerate(stats_block):
        lines.insert(insert_pos + i, s)

    return "\n".join(lines)


def save_assembly(text: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(ASSEMBLED_FILE, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  Saved restored text to {ASSEMBLED_FILE}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Correspondential restoration of the Kephalaia "
        "teaching core"
    )
    parser.add_argument(
        "--chapter",
        "-c",
        type=int,
        default=None,
        help="Process a single chapter",
    )
    parser.add_argument(
        "--range",
        "-r",
        type=str,
        default=None,
        help="Process a range of chapters (e.g., '38-55')",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=None,
        help="Process only first N chapters",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Preview without API calls",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Reprocess existing restorations",
    )
    parser.add_argument(
        "--assemble",
        "-a",
        action="store_true",
        help="Skip restoration, assemble existing only",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Load extracted core chapters
    all_chapters = load_core_chapters()
    if not all_chapters:
        print("ERROR: No extracted core chapters found in", CORE_CHAPTERS_DIR)
        print("  Run extract_core.py first.")
        sys.exit(1)

    core_by_num = {ch["chapter_number"]: ch for ch in all_chapters}
    print(f"Found {len(all_chapters)} extracted core chapters")

    # Assembly-only mode
    if args.assemble:
        print("Assembling restored text from existing results...")
        text = assemble_restored(core_by_num)
        if text:
            save_assembly(text)
        return

    # Determine which to process
    if args.chapter is not None:
        chapters = [
            ch for ch in all_chapters if ch["chapter_number"] == args.chapter
        ]
        if not chapters:
            print(f"ERROR: Chapter {args.chapter} not found in extractions")
            sys.exit(1)
    elif args.range:
        m = re.match(r"(\d+)-(\d+)", args.range)
        if not m:
            print("ERROR: Invalid range. Use '38-55'")
            sys.exit(1)
        start, end = int(m.group(1)), int(m.group(2))
        chapters = [
            ch
            for ch in all_chapters
            if start <= ch["chapter_number"] <= end
        ]
    else:
        chapters = all_chapters

    if args.limit:
        chapters = chapters[: args.limit]

    # Skip already processed
    if not args.overwrite:
        to_process = [
            ch for ch in chapters if not is_done(ch["chapter_number"])
        ]
        skipped = len(chapters) - len(to_process)
        if skipped > 0:
            print(
                f"  Skipping {skipped} already-done chapters "
                f"(use --overwrite)"
            )
        chapters = to_process

    if not chapters:
        print("All chapters already processed.")
        text = assemble_restored(core_by_num)
        if text:
            save_assembly(text)
        return

    # Preview
    print(f"\nProcessing {len(chapters)} chapters:")
    for ch in chapters:
        num = ch["chapter_number"]
        title = ch.get("chapter_title", "")[:60]
        core_paras = extract_core_paragraphs(ch)
        _, n_lacunae = find_lacunae(core_paras)
        print(
            f"  Ch.{num:3d}  ({len(core_paras):3d} core \u00b6s, "
            f"{n_lacunae} lacunae)  {title}"
        )

    if args.dry_run:
        print("\n[DRY RUN] No API calls made.")
        return

    # Create client
    client = create_client()
    deployment = get_deployment()
    print(f"\nUsing deployment: {deployment}")
    print()

    # Process
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CHAPTERS_OUT_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    errors = []
    for i, ch in enumerate(chapters, 1):
        ch_num = ch["chapter_number"]
        title = ch.get("chapter_title", "")[:50]

        # Pre-process: identify lacunae
        core_paras = extract_core_paragraphs(ch)
        lacunae_map, total_lacunae = find_lacunae(core_paras)

        if total_lacunae == 0:
            print(f"[{i}/{len(chapters)}] Ch.{ch_num} \u2014 no lacunae, skip")
            continue

        print(
            f"[{i}/{len(chapters)}] Ch.{ch_num} "
            f"({total_lacunae} lacunae) {title}...",
            end=" ",
            flush=True,
        )

        result = restore_chapter(
            client, deployment, core_paras, lacunae_map, total_lacunae, ch_num
        )
        if result is None:
            print("FAILED")
            errors.append(ch_num)
            continue

        # Validate: check for missing fills
        expected = set()
        for pnum, lacs in lacunae_map.items():
            for lac in lacs:
                expected.add((pnum, lac["index"]))

        received = set()
        for fill in result.fills:
            received.add((fill.paragraph, fill.index))

        missing = expected - received
        n_filled = sum(1 for f in result.fills if f.fill.strip() != "...")
        n_unrest = sum(1 for f in result.fills if f.fill.strip() == "...")

        save_result(ch_num, title, result, lacunae_map, total_lacunae)

        status = f"OK \u2014 {n_filled} filled, {n_unrest} unrestorable"
        if missing:
            status += f", {len(missing)} MISSING"
        print(status)

        results.append(ch_num)

        # Brief pause between chapters
        if i < len(chapters):
            time.sleep(0.5)

    # Summary
    print(f"\n{'='*60}")
    print("RESTORATION COMPLETE")
    print(f"  Processed: {len(results)}")
    print(f"  Errors: {len(errors)}")
    if errors:
        print(f"  Failed: {errors}")

    # Assemble
    print("\nAssembling restored document...")
    text = assemble_restored(core_by_num)
    if text:
        save_assembly(text)

    print("Done.")


if __name__ == "__main__":
    main()
