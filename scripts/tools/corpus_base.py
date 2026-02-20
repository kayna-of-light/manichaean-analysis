#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Base class for corpus-level Claude analysis scripts.

Provides shared infrastructure for feeding the complete interleaved
corpus (core text + spiritual readings) to Claude Opus 4.6 and
processing the streaming tool-call result.

Subclasses override:
    - system_prompt      (str property)
    - tools              (list property)
    - expected_tool_name (str property)
    - process_result()   — post-processing of the tool call output
    - save_result()      — write output to disk
    - add_arguments()    — extra CLI flags (optional)
    - print_summary()    — display result summary (optional)

Usage pattern:
    class MyAnalysis(CorpusAnalysisBase):
        ...

    if __name__ == "__main__":
        MyAnalysis(description="...").run()
"""

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

from __future__ import annotations

import abc
import argparse
import json
import re
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import httpx
from anthropic import AnthropicFoundry
from dotenv import dotenv_values

from project_config import load_project, list_projects, SECRETS_PATH

# ---------------------------------------------------------------------------
# Paths — set by configure_paths() at startup
# ---------------------------------------------------------------------------

PROJECT_CFG = None
CORE_CHAPTERS_DIR: Path | None = None
RESTORED_CHAPTERS_DIR: Path | None = None
OUTPUT_DIR: Path | None = None


def configure_paths(project_name: str) -> None:
    """Set module-level path variables from project config."""
    global PROJECT_CFG, CORE_CHAPTERS_DIR, RESTORED_CHAPTERS_DIR, OUTPUT_DIR

    cfg = load_project(project_name)
    cfg.paths.ensure_dirs()
    PROJECT_CFG = cfg

    CORE_CHAPTERS_DIR = cfg.paths.core_chapters
    RESTORED_CHAPTERS_DIR = cfg.paths.restored_chapters
    OUTPUT_DIR = cfg.paths.project_dir


# ---------------------------------------------------------------------------
# Client setup
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
        timeout=httpx.Timeout(3600.0, connect=30.0),
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

    segments = re.split(r"\*\*¶(\d+):\*\*", sr_text)

    result = {}
    i = 1
    while i < len(segments) - 1:
        try:
            pnum = int(segments[i])
            text = segments[i + 1].strip()
            text = re.sub(r"\n---\s*$", "", text).strip()
            if text:
                result[pnum] = text
        except (ValueError, IndexError):
            pass
        i += 2

    return result


def clean_sr_header(sr_text: str) -> str:
    """Strip the '# Spiritual Translation: ...' header from an SR."""
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

        core_paras = []
        for para in core_data.get("paragraphs", []):
            if para.get("core_text"):
                core_paras.append(
                    (para["paragraph_number"], para["core_text"])
                )

        # Load restored file for spiritual reading + reconstructions
        corr_path = RESTORED_CHAPTERS_DIR / f"ch_{ch_num:03d}.json"
        sr_paras = {}
        sr_block = ""
        reconstruction_map: dict[int, str] = {}
        if corr_path.exists():
            with open(corr_path, encoding="utf-8") as f:
                corr_data = json.load(f)
            sr_text = corr_data.get("spiritual_reading", "")
            sr_paras = parse_spiritual_reading_paragraphs(sr_text)
            if not sr_paras and sr_text:
                sr_block = clean_sr_header(sr_text)
            # Build reconstruction map: paragraph -> gap-filled text
            for rec in corr_data.get("reconstructions", []):
                pnum = rec.get("paragraph")
                rtext = rec.get("reconstructed_text", "")
                if pnum is not None and rtext:
                    reconstruction_map[pnum] = rtext

        # Prefer reconstructed (gap-filled) text over raw core_text
        final_paras = []
        for pnum, raw_text in core_paras:
            final_paras.append(
                (pnum, reconstruction_map.get(pnum, raw_text))
            )

        chapters.append({
            "chapter_number": ch_num,
            "core_paragraphs": final_paras,
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
    Lines marked [§N]* are the restored reading of [§N].

    Returns:
        (corpus_text, section_map)

    The section_map is a list of (ms_chapter, §start, §end) tuples
    kept internally for post-processing — NOT sent to the model.
    """
    lines = []
    seq = 0

    section_map: list[tuple[int, int, int]] = []

    for ch in chapters:
        ch_num = ch["chapter_number"]
        sr_paras = ch["sr_paragraphs"]
        sr_block = ch.get("sr_block", "")
        first_seq = seq + 1

        for _pnum, core_text in ch["core_paragraphs"]:
            seq += 1
            ref = f"[§{seq}]"

            lines.append(f"{ref} {core_text}")

            if _pnum in sr_paras:
                lines.append(f"{ref}* {sr_paras[_pnum]}")

            lines.append("")

        if sr_block and not sr_paras:
            lines.append(f"[§{first_seq}–§{seq}]* {sr_block}")
            lines.append("")

        section_map.append((ch_num, first_seq, seq))

    corpus_text = "\n".join(lines)
    return corpus_text, section_map


# ---------------------------------------------------------------------------
# Streaming mechanics
# ---------------------------------------------------------------------------


def stream_tool_call(
    client: AnthropicFoundry,
    deployment: str,
    *,
    system_prompt: str,
    tools: list[dict],
    expected_tool_name: str,
    corpus_text: str,
    max_tokens: int = 128_000,
    max_retries: int = 5,
    debug: bool = False,
) -> tuple[dict | None, str]:
    """Stream a single-turn tool call from Claude.

    Returns:
        (tool_input, text_output)
        tool_input is None if the model didn't call the expected tool.
    """
    messages = [{"role": "user", "content": corpus_text}]

    for attempt in range(1, max_retries + 1):
        try:
            thinking_chars = 0

            with client.messages.stream(
                model=deployment,
                system=system_prompt,
                messages=messages,
                tools=tools,
                max_tokens=max_tokens,
                thinking={"type": "adaptive"},
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

            # Extract tool call and text
            tool_input = None
            text_parts: list[str] = []

            for block in final_msg.content:
                btype = getattr(block, "type", "")
                if btype == "tool_use" and block.name == expected_tool_name:
                    tool_input = block.input
                elif btype == "text":
                    text_parts.append(block.text)

            text_output = " ".join(text_parts).strip() if text_parts else ""

            if tool_input is None:
                print(
                    f"  WARNING: Model did not call {expected_tool_name}."
                )
                if text_output:
                    print(f"  Text output: {text_output[:500]}")

            return tool_input, text_output

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
# Dry-run
# ---------------------------------------------------------------------------


def print_dry_run(chapters: list[dict]) -> None:
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
    print(f"% of 200K limit: ~{est_tokens / 2000:.1f}%")

    print(f"\nSection map: {len(section_map)} entries (internal, NOT sent to model)")

    print("\n--- Sample (first 800 chars) ---")
    print(corpus_text[:800])
    print("--- end sample ---")


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class CorpusAnalysisBase(abc.ABC):
    """Base class for corpus-level Claude analysis scripts.

    Subclass and implement the abstract properties/methods, then call run().
    """

    def __init__(self, description: str) -> None:
        self.description = description
        self.chapters: list[dict] = []
        self.corpus_text: str = ""
        self.section_map: list[tuple[int, int, int]] = []

    # -- Abstract interface --------------------------------------------------

    @property
    @abc.abstractmethod
    def system_prompt(self) -> str:
        """The system prompt for Claude."""
        ...

    @property
    @abc.abstractmethod
    def tools(self) -> list[dict]:
        """Tool definitions for Claude."""
        ...

    @property
    @abc.abstractmethod
    def expected_tool_name(self) -> str:
        """The name of the tool the model should call."""
        ...

    @abc.abstractmethod
    def process_result(
        self, tool_input: dict | None, text_output: str
    ) -> dict:
        """Process the raw tool call output into a result dict."""
        ...

    @abc.abstractmethod
    def save_result(
        self,
        result: dict,
        output_path: Path,
    ) -> None:
        """Save the result to disk."""
        ...

    # -- Optional overrides --------------------------------------------------

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add script-specific CLI arguments. Override if needed."""
        pass

    def print_summary(self, result: dict) -> None:
        """Print a summary of the result. Override for custom display."""
        pass

    @property
    def default_output_filename(self) -> str:
        """Default output filename. Override per script."""
        return "output.json"

    @property
    def thinking_budget(self) -> int:
        """Thinking token budget. Override if needed."""
        return 50_000

    @property
    def max_tokens(self) -> int:
        """Max output tokens. Override if needed."""
        return 128_000

    # -- Core run method -----------------------------------------------------

    def run(self) -> None:
        """Parse CLI args, load data, call Claude, save result."""
        parser = argparse.ArgumentParser(description=self.description)
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
            help="Output file path (default: <project>/<default_name>)",
        )
        self.add_arguments(parser)
        args = parser.parse_args()

        print(f"=== {self.description}: {args.project} ===\n")
        configure_paths(args.project)

        # Load data
        print("Loading corpus...")
        self.chapters = load_all_chapters()
        print(f"  Loaded {len(self.chapters)} chapters")

        if args.dry_run:
            print_dry_run(self.chapters)
            return

        # Format corpus
        print("\nInterleaving core text + spiritual readings...")
        self.corpus_text, self.section_map = format_corpus_interleaved(
            self.chapters
        )
        est_tokens = len(self.corpus_text) / 3.5
        last_seq = self.section_map[-1][2] if self.section_map else 0
        print(
            f"  Corpus: {len(self.corpus_text):,} chars "
            f"(~{est_tokens:,.0f} tokens)"
        )
        print(f"  Sequential range: §1–§{last_seq}")
        print(f"  Section map: {len(self.section_map)} entries (internal)")

        # Create client
        print("\nConnecting to Claude Opus 4.6...")
        client, deployment = create_claude_client()

        # Stream
        print(f"\nStreaming analysis...\n")
        t0 = time.time()
        tool_input, text_output = stream_tool_call(
            client,
            deployment,
            system_prompt=self.system_prompt,
            tools=self.tools,
            expected_tool_name=self.expected_tool_name,
            corpus_text=self.corpus_text,
            max_tokens=self.max_tokens,
            debug=args.debug,
        )
        elapsed = time.time() - t0
        print(f"\nAnalysis completed in {elapsed:.1f}s")

        # Process
        result = self.process_result(tool_input, text_output)
        self.print_summary(result)

        # Save
        output_path = (
            Path(args.output) if args.output
            else OUTPUT_DIR / self.default_output_filename
        )
        self.save_result(result, output_path)
