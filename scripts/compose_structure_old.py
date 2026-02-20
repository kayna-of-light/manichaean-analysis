#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compose the structural architecture of a book from its teaching substrate.

Feeds ALL core texts + spiritual readings to Claude Opus 4.6 in a single
prompt (within its 1M token context window). The texts are presented as a
continuous flow — core text and spiritual reading interleaved paragraph by
paragraph, stripped of chapter divisions — so the model can read the entire
substrate holistically and discover its actual structure.

The model outputs structural observations via streaming tool calls. The
result is a structural schema (no text reproduction) that can drive PDF
generation from the existing text files.

Primary model: Claude Opus 4.6 via Azure AI Foundry (AnthropicFoundry).

Usage:
    python compose_structure.py --project kephalaia [--debug] [--dry-run]
"""

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import argparse
import json
import re
import sys
import time
import traceback
from pathlib import Path

import httpx
from anthropic import AnthropicFoundry
from dotenv import dotenv_values

from project_config import load_project, list_projects, SECRETS_PATH

# ---------------------------------------------------------------------------
# Paths — set by configure_paths() at startup
# ---------------------------------------------------------------------------

PROJECT_CFG = None
CORE_CHAPTERS_DIR: Path | None = None
CORR_CHAPTERS_DIR: Path | None = None
OUTPUT_DIR: Path | None = None


def configure_paths(project_name: str) -> None:
    """Set module-level path variables from project config."""
    global PROJECT_CFG, CORE_CHAPTERS_DIR, CORR_CHAPTERS_DIR, OUTPUT_DIR

    cfg = load_project(project_name)
    cfg.paths.ensure_dirs()
    PROJECT_CFG = cfg

    CORE_CHAPTERS_DIR = cfg.paths.core_chapters
    CORR_CHAPTERS_DIR = cfg.paths.correspondential_chapters
    OUTPUT_DIR = cfg.paths.project_dir


# ---------------------------------------------------------------------------
# Client setup (same pattern as correspondential_reading.py)
# ---------------------------------------------------------------------------


def create_claude_client() -> tuple[AnthropicFoundry, str]:
    """Create Claude client from .env credentials."""
    config = dotenv_values(SECRETS_PATH)
    endpoint = config.get("ANTHROPIC_ENDPOINT", "").rstrip("/")
    api_key = config.get("ANTHROPIC_API_KEY", "")
    deployment = config.get("ANTHROPIC_DEPLOYMENT", "claude-opus-4-6")

    if not endpoint or not api_key:
        print(
            "ERROR: ANTHROPIC_ENDPOINT and ANTHROPIC_API_KEY required "
            "in secrets/azure_openai.env"
        )
        sys.exit(1)

    client = AnthropicFoundry(
        api_key=api_key,
        base_url=endpoint,
        timeout=httpx.Timeout(3600.0, connect=30.0),  # 60 min read timeout
    )
    return client, deployment


# ---------------------------------------------------------------------------
# Data loading & interleaving
# ---------------------------------------------------------------------------


def parse_spiritual_reading_paragraphs(sr_text: str) -> dict[int, str]:
    """Parse a spiritual reading into paragraph-keyed segments.

    The SRs use **¶N:** markers. This splits the text into a dict
    keyed by paragraph number.
    """
    if not sr_text:
        return {}

    # Split on paragraph markers
    segments = re.split(r"\*\*¶(\d+):\*\*", sr_text)

    result = {}
    # segments[0] is the header (before first ¶), skip it
    # Then pairs: segments[1]=num, segments[2]=text, segments[3]=num, ...
    i = 1
    while i < len(segments) - 1:
        try:
            pnum = int(segments[i])
            text = segments[i + 1].strip()
            # Clean up: remove trailing --- separators
            text = re.sub(r"\n---\s*$", "", text).strip()
            if text:
                result[pnum] = text
        except (ValueError, IndexError):
            pass
        i += 2

    return result


def clean_sr_header(sr_text: str) -> str:
    """Strip the '# Spiritual Translation: ...' header from an SR."""
    # Remove leading header line(s) and separator
    text = re.sub(
        r"^#\s*Spiritual Translation[^\n]*\n+---\n*", "", sr_text
    ).strip()
    return text


def load_all_chapters() -> list[dict]:
    """Load core extractions and merge with spiritual reading paragraphs.

    Returns a list of dicts with:
      - chapter_number
      - core_paragraphs: list of (para_num, core_text)
      - sr_paragraphs: dict of para_num -> sr_text (when parseable)
      - sr_block: str (full SR text when paragraph markers not found)
      - core_percentage
    """
    chapters = []
    core_files = sorted(CORE_CHAPTERS_DIR.glob("ch_*.json"))
    print(f"  Core chapters found: {len(core_files)}")

    for core_path in core_files:
        with open(core_path, encoding="utf-8") as f:
            core_data = json.load(f)

        ch_num = core_data["chapter_number"]
        core_pct = core_data.get("core_percentage", 0.0)

        # Collect core paragraphs
        core_paras = []
        for para in core_data.get("paragraphs", []):
            if para.get("core_text"):
                core_paras.append(
                    (para["paragraph_number"], para["core_text"])
                )

        # Load spiritual reading if available
        corr_path = CORR_CHAPTERS_DIR / f"ch_{ch_num:03d}.json"
        sr_paras = {}
        sr_block = ""
        if corr_path.exists():
            with open(corr_path, encoding="utf-8") as f:
                corr_data = json.load(f)
            sr_text = corr_data.get("spiritual_reading", "")
            sr_paras = parse_spiritual_reading_paragraphs(sr_text)
            # If no paragraph markers found, keep as block
            if not sr_paras and sr_text:
                sr_block = clean_sr_header(sr_text)

        chapters.append({
            "chapter_number": ch_num,
            "core_paragraphs": core_paras,
            "sr_paragraphs": sr_paras,
            "sr_block": sr_block,
            "core_percentage": core_pct,
        })

    return chapters


def format_corpus_interleaved(
    chapters: list[dict],
) -> tuple[str, list[tuple[int, int, int]]]:
    """Format the entire corpus as a continuous interleaved text.

    Uses sequential paragraph markers [§N] with NO chapter numbers
    visible. The model sees a continuous flow of teaching.
    Lines marked [§N]* are the correspondential reading of [§N].

    Returns:
        (corpus_text, section_map)

    The section_map is a list of (ms_chapter, §start, §end) tuples
    kept internally for post-processing — NOT sent to the model.
    """
    lines = []
    seq = 0  # sequential paragraph counter

    # Track §-ranges per manuscript chapter (internal only)
    section_map: list[tuple[int, int, int]] = []  # (ch_num, §start, §end)

    for ch in chapters:
        ch_num = ch["chapter_number"]
        sr_paras = ch["sr_paragraphs"]
        sr_block = ch.get("sr_block", "")
        first_seq = seq + 1

        for _pnum, core_text in ch["core_paragraphs"]:
            seq += 1
            ref = f"[§{seq}]"

            # Core text line
            lines.append(f"{ref} {core_text}")

            # Spiritual reading line (if available for this paragraph)
            if _pnum in sr_paras:
                lines.append(f"{ref}* {sr_paras[_pnum]}")

            lines.append("")  # blank line between paragraphs

        # If this chapter has an SR block (no per-paragraph markers),
        # append it after all core paragraphs
        if sr_block and not sr_paras:
            lines.append(f"[§{first_seq}–§{seq}]* {sr_block}")
            lines.append("")

        section_map.append((ch_num, first_seq, seq))

    corpus_text = "\n".join(lines)
    return corpus_text, section_map


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert in the doctrine of correspondences as written by \
Emanuel Swedenborg, with deep specialization in ancient cosmological \
vocabulary — Zoroastrian, Manichaean, and Persian-Iranian traditions.

You have been given the COMPLETE teaching substrate of the Coptic \
Kephalaia — both the extracted teaching core (oldest layer) and a \
correspondential reading (translation from natural into spiritual \
sense) of most passages.

The text is presented as a continuous flow of numbered paragraphs. \
Each paragraph has a marker [§N]. Lines marked [§N]* are the \
correspondential reading of that same paragraph.

These paragraph numbers are sequential. The text was extracted from \
an editorial compilation — what you are reading is the teaching \
substrate stripped of editorial structure.

Your task is to read the entire text holistically and determine its \
true structure — the natural divisions, the actual teaching sequence, \
what belongs together, what the parts and chapters should be called, \
and in what order the text should be read.

When you have determined the structure, call the commit_structure \
tool once with the complete result.""" 

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

COMMIT_STRUCTURE_TOOL = {
    "name": "commit_structure",
    "description": (
        "Commit the complete book structure. Call this exactly once "
        "with the full result of your analysis."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "parts": {
                "type": "array",
                "description": (
                    "The major divisions of the book, in reading order."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "part_number": {
                            "type": "integer",
                            "description": (
                                "Sequential part number in "
                                "reading order."
                            ),
                        },
                        "title": {
                            "type": "string",
                            "description": (
                                "Title for this part of the book."
                            ),
                        },
                        "description": {
                            "type": "string",
                            "description": (
                                "What this part covers, its role in "
                                "the book's architecture, and why "
                                "these chapters belong together."
                            ),
                        },
                    },
                    "required": [
                        "part_number", "title", "description",
                    ],
                },
            },
            "chapters": {
                "type": "array",
                "description": (
                    "Every chapter in the book, in reading order."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "part_number": {
                            "type": "integer",
                            "description": (
                                "Which part this chapter belongs to."
                            ),
                        },
                        "position_in_part": {
                            "type": "integer",
                            "description": (
                                "Reading order within the part "
                                "(1, 2, 3, ...)."
                            ),
                        },
                        "section_start": {
                            "type": "integer",
                            "description": (
                                "First § number of this chapter."
                            ),
                        },
                        "section_end": {
                            "type": "integer",
                            "description": (
                                "Last § number of this chapter."
                            ),
                        },
                        "title": {
                            "type": "string",
                            "description": (
                                "Title for this chapter based on "
                                "its content."
                            ),
                        },
                        "role": {
                            "type": "string",
                            "description": (
                                "The chapter's role — e.g. primary "
                                "teaching, elaboration, parallel, "
                                "fragment, summary, transitional."
                            ),
                        },
                        "description": {
                            "type": "string",
                            "description": (
                                "What this chapter teaches and how "
                                "it relates to the book's structure."
                            ),
                        },
                    },
                    "required": [
                        "part_number",
                        "position_in_part",
                        "section_start",
                        "section_end",
                        "title",
                        "role",
                        "description",
                    ],
                },
            },
            "observations": {
                "type": "array",
                "description": (
                    "Structural observations about the text — "
                    "cross-cutting themes, recurring patterns, "
                    "anything that doesn't fit into parts/chapters."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": (
                                "Short title for this observation."
                            ),
                        },
                        "content": {
                            "type": "string",
                            "description": (
                                "The observation. As detailed "
                                "as needed."
                            ),
                        },
                    },
                    "required": ["title", "content"],
                },
            },
        },
        "required": ["parts", "chapters", "observations"],
    },
}

TOOLS = [COMMIT_STRUCTURE_TOOL]


# ---------------------------------------------------------------------------
# Streaming tool-call handler
# ---------------------------------------------------------------------------


def stream_structure(
    client: AnthropicFoundry,
    deployment: str,
    corpus_text: str,
    *,
    debug: bool = False,
) -> dict:
    """Stream the structural composition from Claude.

    Single turn: the model reads the corpus, thinks, and calls
    commit_structure once with the complete result.

    Returns:
    {
        "parts": [...],
        "chapters": [...],
        "observations": [...],
        "text_output": "...",
    }
    """
    messages = [{"role": "user", "content": corpus_text}]

    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            thinking_chars = 0

            with client.messages.stream(
                model=deployment,
                system=SYSTEM_PROMPT,
                messages=messages,
                tools=TOOLS,
                max_tokens=128000,
                thinking={"type": "enabled", "budget_tokens": 50000},
            ) as stream:
                for event in stream:
                    etype = getattr(event, "type", "")

                    if etype == "content_block_start":
                        block = getattr(event, "content_block", None)
                        if (
                            block
                            and getattr(block, "type", "") == "thinking"
                            and debug
                        ):
                            print(
                                "\n  [thinking] ",
                                end="",
                                flush=True,
                            )

                    elif etype == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        if delta:
                            dtype = getattr(delta, "type", "")
                            if dtype == "thinking_delta":
                                chunk = getattr(delta, "thinking", "")
                                thinking_chars += len(chunk)
                                if debug:
                                    print(chunk, end="", flush=True)

                    elif etype == "message_stop":
                        if debug:
                            print(flush=True)

                final_msg = stream.get_final_message()

            if debug and thinking_chars:
                print(f" [{thinking_chars} chars]", flush=True)

            # Extract the commit_structure tool call
            structure = None
            text_parts: list[str] = []

            for block in final_msg.content:
                btype = getattr(block, "type", "")
                if btype == "tool_use" and block.name == "commit_structure":
                    structure = block.input
                elif btype == "text":
                    text_parts.append(block.text)

            if structure is None:
                print("  WARNING: Model did not call commit_structure.")
                if text_parts:
                    print(f"  Text output: {' '.join(text_parts)[:500]}")
                return {
                    "parts": [],
                    "chapters": [],
                    "observations": [],
                    "text_output": " ".join(text_parts),
                }

            # Print summary
            for p in structure.get("parts", []):
                print(
                    f"  ✦ Part {p['part_number']}: {p['title']}"
                )
            for i, ch in enumerate(structure.get("chapters", []), 1):
                print(
                    f"  ✓ [{i}] §{ch['section_start']}–"
                    f"§{ch['section_end']}: {ch['title']}  "
                    f"(Pt {ch['part_number']}, "
                    f"pos {ch['position_in_part']}, "
                    f"{ch['role']})"
                )
            for obs in structure.get("observations", []):
                print(f"  ○ {obs['title']}")

            structure["text_output"] = (
                " ".join(text_parts).strip() if text_parts else ""
            )
            return structure

        except Exception as e:
            err_str = str(e)
            if "rate" in err_str.lower() or "429" in err_str:
                wait = 60.0 * attempt
                print(f"  Rate limit, waiting {wait:.0f}s...")
                time.sleep(wait)
                continue
            elif "overloaded" in err_str.lower() or "529" in err_str:
                wait = 30.0 * attempt
                print(f"  Overloaded, waiting {wait:.0f}s...")
                time.sleep(wait)
                continue
            else:
                print(f"  Error attempt {attempt}: {e}")
                if debug:
                    traceback.print_exc()
                if attempt < max_retries:
                    time.sleep(attempt * 10)
                    continue
                raise

    raise RuntimeError(f"Failed after {max_retries} attempts")


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def save_structure(
    structure: dict,
    section_map: list[tuple[int, int, int]],
    output_path: Path,
) -> None:
    """Save the structural schema to JSON.

    Includes the §-to-manuscript-chapter mapping so we can
    resolve the model's §-ranges to source files in post-processing.
    """
    structure["_section_map"] = [
        {"ms_chapter": ch, "section_start": s, "section_end": e}
        for ch, s, e in section_map
    ]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(structure, f, indent=2, ensure_ascii=False)
    print(f"\nStructure saved to: {output_path}")
    print(f"  Parts defined: {len(structure['parts'])}")
    print(f"  Chapters defined: {len(structure['chapters'])}")
    print(f"  Observations: {len(structure['observations'])}")


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------


def dry_run(chapters: list[dict]) -> None:
    """Show corpus statistics without calling the API."""
    corpus_text, section_map = format_corpus_interleaved(chapters)
    est_tokens = len(corpus_text) / 3.5

    print("\n=== DRY RUN ===")
    print(f"Total manuscript chapters: {len(chapters)}")

    with_sr = sum(1 for c in chapters if c["sr_paragraphs"])
    with_sr_block = sum(
        1 for c in chapters
        if c.get("sr_block") and not c["sr_paragraphs"]
    )
    print(f"  With interleaved SR: {with_sr}")
    print(f"  With SR block (no ¶ markers): {with_sr_block}")
    print(f"  Without SR: {len(chapters) - with_sr - with_sr_block}")

    total_core = sum(len(c["core_paragraphs"]) for c in chapters)
    total_sr = sum(len(c["sr_paragraphs"]) for c in chapters)
    last_seq = section_map[-1][2] if section_map else 0
    print(f"\nTotal core paragraphs: {total_core}")
    print(f"Total SR paragraphs (interleaved): {total_sr}")
    print(f"Sequential range: §1–§{last_seq}")

    print(f"\nCorpus: {len(corpus_text):,} chars")
    print(f"Estimated tokens: ~{est_tokens:,.0f}")
    print(f"% of 1M limit: ~{est_tokens / 10000:.1f}%")

    print(f"\nSection map: {len(section_map)} entries (internal, NOT sent to model)")

    # Show a sample of the interleaved format
    print("\n--- Sample (first 800 chars) ---")
    print(corpus_text[:800])
    print("--- end sample ---")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compose the structural architecture of a book"
    )
    parser.add_argument(
        "--project",
        default="kephalaia",
        help="Project name (default: kephalaia)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show thinking output and verbose logging",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show corpus statistics without calling the API",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path (default: <project>/book_structure.json)",
    )
    args = parser.parse_args()

    print(f"=== Compose Structure: {args.project} ===\n")
    configure_paths(args.project)

    # Load all data
    print("Loading corpus...")
    chapters = load_all_chapters()
    print(f"  Loaded {len(chapters)} chapters")

    if args.dry_run:
        dry_run(chapters)
        return

    # Format corpus — continuous interleaved text
    print("\nInterleaving core text + spiritual readings...")
    corpus_text, section_map = format_corpus_interleaved(chapters)
    est_tokens = len(corpus_text) / 3.5
    last_seq = section_map[-1][2] if section_map else 0
    print(f"  Corpus: {len(corpus_text):,} chars (~{est_tokens:,.0f} tokens)")
    print(f"  Sequential range: §1–§{last_seq}")
    print(f"  Section map: {len(section_map)} entries (internal)")

    # Create client
    print("\nConnecting to Claude Opus 4.6...")
    client, deployment = create_claude_client()

    # Stream the structure
    print("\nStreaming structural composition...\n")
    t0 = time.time()
    structure = stream_structure(
        client, deployment, corpus_text, debug=args.debug
    )
    elapsed = time.time() - t0
    print(f"\nComposition completed in {elapsed:.1f}s")

    # Save
    output_path = (
        Path(args.output) if args.output
        else OUTPUT_DIR / "book_structure.json"
    )
    save_structure(structure, section_map, output_path)


if __name__ == "__main__":
    main()
