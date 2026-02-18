#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Correspondential restoration of the Kephalaia teaching core.

Architecture:
  Phase 1 — Spiritual Reading (Claude): Translate whole chapter from
            natural sense into spiritual sense via correspondences.
  Phase 2 — Restoration (Claude + adaptive thinking): Receive original
            text + spiritual reading, output complete restored paragraphs
            with brackets marking additions. Whole chapter in one call.
  Validation — Diff model output against original to extract fills and
               detect any unauthorized changes outside brackets.

Primary model: Claude Opus 4.6 via Azure AI Foundry (AnthropicFoundry).
Fallback: GPT-5.2 via OpenAI-compatible endpoint.
"""

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import argparse
import json
import re
import sys
import time
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
from anthropic import AnthropicFoundry
from dotenv import dotenv_values

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
# Bracket pattern
# ---------------------------------------------------------------------------

LACUNA_RE = re.compile(r"\[([^\]]*)\]")

# ---------------------------------------------------------------------------
# Prompts — minimal, profile-based
# ---------------------------------------------------------------------------

SPIRITUAL_READING_PROMPT = """\
You are an expert in the doctrine of correspondences as written by \
Emanuel Swedenborg, with deep specialization in ancient cosmological \
vocabulary — Zoroastrian, Manichaean, and Persian-Iranian traditions.

You translate text from its natural sense into its spiritual sense. \
Not annotation, not commentary — translation. Every natural image is \
replaced by the spiritual reality it expresses through correspondence.

The text you receive is the oldest teaching substrate of the Coptic \
Kephalaia — pre-Manichaean cosmological teaching that Mani inherited \
from the Eastern tradition. Read it as correspondence: light = wisdom, \
darkness = falsity, fire = love (or self-love in opposite sense), \
water = truth, garments = external truths, trees = perceptions, \
fruits = works, animals = affections, mountains = elevated states, \
seeds = interior truths, vessels = containing forms.

Translate paragraph by paragraph. Replace every natural object. \
Produce continuous prose about spiritual states and processes. \
If an image resists translation, say so briefly and give your \
best reading."""

RESTORATION_PROMPT = """\
You are an expert in the doctrine of correspondences as written by \
Emanuel Swedenborg, with deep specialization in ancient cosmological \
vocabulary — Zoroastrian, Manichaean, and Persian-Iranian traditions.

You are restoring the oldest teaching substrate of the Coptic \
Kephalaia. The text has lacunae — gaps marked with square brackets. \
Your task is to fill these gaps using the correspondential logic of \
the text.

You receive two things:
1. The ORIGINAL TEXT with brackets marking gaps
2. A SPIRITUAL READING that translates the text into its spiritual sense

The spiritual reading tells you WHAT spiritual reality each passage \
describes. Your fills must express that reality in the text's own \
natural-plane vocabulary — the language of the Kephalaia itself.

Rules:
- Output COMPLETE PARAGRAPHS with your additions in [square brackets]
- Mark each paragraph with ¶N (matching the input numbering)
- Text OUTSIDE brackets is FIXED — do not change it at all
- For partial words like [te]aching, your fill + the adjacent letters \
  must form a real word
- For [...] gaps, let the spiritual reading and the correspondential \
  logic constrain what belongs there
- If a gap truly cannot be restored, keep it as [...]
- Write in the register of ancient cosmological teaching — impersonal, \
  structural, expository
- Do NOT use forward slash (/) in fills
- Output every paragraph as ¶N: followed by the complete text"""


# ---------------------------------------------------------------------------
# Client setup
# ---------------------------------------------------------------------------


def create_claude_client() -> tuple[AnthropicFoundry, str]:
    """Create Claude client from .env credentials."""
    config = dotenv_values(SECRETS_PATH)
    endpoint = config.get("ANTHROPIC_ENDPOINT", "").rstrip("/")  # type: ignore
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
        timeout=httpx.Timeout(1800.0, connect=30.0),  # 30 min read
    )
    return client, deployment  # type: ignore


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_core_chapters() -> list[dict]:
    """Load all extracted core chapter JSON files."""
    chapters = []
    for path in sorted(CORE_CHAPTERS_DIR.glob("ch_*.json")):
        with open(path, encoding="utf-8") as f:
            chapters.append(json.load(f))
    return chapters


def extract_core_paragraphs(chapter: dict) -> list[dict]:
    """Extract paragraphs that have core_text from an extraction."""
    result = []
    for para in chapter.get("paragraphs", []):
        if para.get("core_text"):
            result.append(
                {
                    "paragraph_number": para["paragraph_number"],
                    "core_text": clean_core_text(para["core_text"]),
                }
            )
    return result


# Regex for page markers like ⟨p.18⟩ or ⟨p.N⟩
PAGE_MARKER_RE = re.compile(r"\s*\u27E8p\.\d+\u27E9\s*")
# Bare ellipsis (2+ dots)
BARE_DOTS_RE = re.compile(r"\.{2,}")


def clean_core_text(text: str) -> str:
    """Clean core text before processing.

    1. Strip manuscript page markers (e.g. ⟨p.20⟩)
    2. Wrap bare ... in [ ... ] so they are counted as lacunae
    3. Collapse multiple whitespace / newlines
    """
    # Strip page markers
    text = PAGE_MARKER_RE.sub(" ", text)
    # Protect existing bracketed content with placeholder
    placeholders: list[str] = []

    def _save_bracket(m: re.Match) -> str:
        placeholders.append(m.group(0))
        return f"\x00BRACKET{len(placeholders) - 1}\x00"

    text = LACUNA_RE.sub(_save_bracket, text)
    # Now wrap any remaining bare dots
    text = BARE_DOTS_RE.sub("[ ... ]", text)
    # Restore bracketed content
    for i, orig in enumerate(placeholders):
        text = text.replace(f"\x00BRACKET{i}\x00", orig)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def find_lacunae(
    core_paras: list[dict],
) -> tuple[dict[int, list[dict]], int]:
    """Identify all [bracket] spans in core paragraphs."""
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
# Phase 1: Spiritual Reading
# ---------------------------------------------------------------------------


def generate_spiritual_reading(
    client: AnthropicFoundry,
    deployment: str,
    core_paras: list[dict],
    ch_num: int,
    *,
    debug: bool = False,
) -> str | None:
    """Generate a correspondential reading of the whole chapter."""
    lines = [
        "Translate the following chapter from its natural sense "
        "into its spiritual sense.\n",
        "--- CORE TEXT (oldest teaching layer) ---\n",
    ]
    for p in core_paras:
        lines.append(f"¶{p['paragraph_number']}: {p['core_text']}")
        lines.append("")
    lines.append("--- END ---")
    user_msg = "\n".join(lines)

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            text_parts = []
            in_thinking = False
            thinking_chars = 0

            with client.messages.stream(
                model=deployment,
                system=SPIRITUAL_READING_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
                max_tokens=16000,
                thinking={"type": "adaptive"},
            ) as stream:
                for event in stream:
                    etype = getattr(event, "type", "")

                    # Thinking block started
                    if etype == "content_block_start":
                        block = getattr(event, "content_block", None)
                        if block and getattr(block, "type", "") == "thinking":
                            in_thinking = True
                            thinking_chars = 0
                            if debug:
                                print("\n  [thinking] ", end="", flush=True)
                        elif block and getattr(block, "type", "") == "text":
                            in_thinking = False
                            if debug:
                                print("\n  [output] ", end="", flush=True)

                    # Thinking delta
                    elif etype == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        if delta:
                            dtype = getattr(delta, "type", "")
                            if dtype == "thinking_delta":
                                chunk = getattr(delta, "thinking", "")
                                thinking_chars += len(chunk)
                                if debug:
                                    print(chunk, end="", flush=True)
                            elif dtype == "text_delta":
                                chunk = getattr(delta, "text", "")
                                text_parts.append(chunk)
                                if debug:
                                    print(chunk, end="", flush=True)

                    # Block ended
                    elif etype == "content_block_stop":
                        if in_thinking:
                            if debug:
                                print(f" [{thinking_chars} chars]", flush=True)
                            in_thinking = False

                    # Message ended
                    elif etype == "message_stop":
                        if debug:
                            print(flush=True)

            return "\n".join(text_parts) if text_parts else None

        except Exception as e:
            err_str = str(e)
            if "content_filter" in err_str.lower():
                print(
                    f"  Phase 1 content filter Ch.{ch_num}, "
                    f"attempt {attempt}/{max_retries}"
                )
                if attempt < max_retries:
                    time.sleep(attempt * 10)
                    continue
            elif "rate" in err_str.lower() or "429" in err_str:
                wait = 60.0
                print(f"  Phase 1 rate limit, waiting {wait:.0f}s...")
                time.sleep(wait)
                continue
            else:
                print(f"  Phase 1 error Ch.{ch_num}: {e}")
                if attempt < max_retries:
                    time.sleep(attempt * 5)
                    continue
            return None
    return None


# ---------------------------------------------------------------------------
# Phase 2: Restoration (single call — streaming + adaptive, text output)
# ---------------------------------------------------------------------------


def restore_chapter(
    client: AnthropicFoundry,
    deployment: str,
    core_paras: list[dict],
    spiritual_reading: str,
    ch_num: int,
    *,
    debug: bool = False,
) -> dict[int, str] | None:
    """Restore all lacunae in one call.

    Uses streaming + adaptive thinking. Model outputs text with
    paragraph-number prefixes. Parsed with regex.

    Returns {paragraph_number: restored_text} or None on failure.
    """
    lines = [
        "Below is the original chapter text followed by its spiritual reading.",
        "Restore all lacunae (gaps in square brackets).",
        "",
        "--- ORIGINAL TEXT ---",
        "",
    ]
    for p in core_paras:
        lines.append(f"¶{p['paragraph_number']}: {p['core_text']}")
        lines.append("")
    lines.append("--- SPIRITUAL READING ---")
    lines.append("")
    lines.append(spiritual_reading)
    lines.append("")
    lines.append("--- END ---")
    lines.append("")
    lines.append(
        "Restore the lacunae and output every paragraph with your "
        "additions in [square brackets]. Mark each paragraph with ¶N:"
    )
    user_msg = "\n".join(lines)

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            text_parts = []
            in_thinking = False
            thinking_chars = 0

            with client.messages.stream(
                model=deployment,
                system=RESTORATION_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
                max_tokens=128000,
                thinking={"type": "adaptive"},
            ) as stream:
                for event in stream:
                    etype = getattr(event, "type", "")

                    # Thinking block started
                    if etype == "content_block_start":
                        block = getattr(event, "content_block", None)
                        if block and getattr(block, "type", "") == "thinking":
                            in_thinking = True
                            thinking_chars = 0
                            if debug:
                                print("\n  [thinking] ", end="", flush=True)
                        elif block and getattr(block, "type", "") == "text":
                            in_thinking = False
                            if debug:
                                print("\n  [output] ", end="", flush=True)

                    # Thinking delta
                    elif etype == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        if delta:
                            dtype = getattr(delta, "type", "")
                            if dtype == "thinking_delta":
                                chunk = getattr(delta, "thinking", "")
                                thinking_chars += len(chunk)
                                if debug:
                                    print(chunk, end="", flush=True)
                            elif dtype == "text_delta":
                                chunk = getattr(delta, "text", "")
                                text_parts.append(chunk)
                                if debug:
                                    print(chunk, end="", flush=True)

                    # Block ended
                    elif etype == "content_block_stop":
                        if in_thinking:
                            if debug:
                                print(f" [{thinking_chars} chars]", flush=True)
                            in_thinking = False

                    # Message ended
                    elif etype == "message_stop":
                        if debug:
                            print(flush=True)

            if text_parts:
                raw = "".join(text_parts)
                parsed = parse_restored_paragraphs(raw)
                if parsed:
                    return parsed

            print(
                f"\n  Phase 2 Ch.{ch_num}: no usable output "
                f"(attempt {attempt}/{max_retries})"
            )
            if attempt < max_retries:
                time.sleep(attempt * 5)
                continue
            return None

        except Exception as e:
            err_str = str(e)
            if "content_filter" in err_str.lower():
                print(
                    f"  Phase 2 content filter Ch.{ch_num}, "
                    f"attempt {attempt}/{max_retries}"
                )
                if attempt < max_retries:
                    time.sleep(attempt * 10)
                    continue
            elif "rate" in err_str.lower() or "429" in err_str:
                wait = 60.0
                print(f"  Phase 2 rate limit, waiting {wait:.0f}s...")
                time.sleep(wait)
                continue
            else:
                print(
                    f"  Phase 2 error Ch.{ch_num} "
                    f"(attempt {attempt}/{max_retries}): "
                    f"{type(e).__name__}: {e}"
                )
                traceback.print_exc()
                if attempt < max_retries:
                    time.sleep(attempt * 5)
                    continue
            return None
    return None


# ---------------------------------------------------------------------------
# Phase 2b: Retry rejected paragraphs individually
# ---------------------------------------------------------------------------

RETRY_PROMPT = """\
You are an expert in the doctrine of correspondences as written by \
Emanuel Swedenborg, with deep specialization in ancient cosmological \
vocabulary — Zoroastrian, Manichaean, and Persian-Iranian traditions.

You are restoring lacunae (square-bracket gaps) in the oldest \
teaching substrate of the Coptic Kephalaia.

A previous restoration attempt for some paragraphs was REJECTED \
because text outside the brackets was altered. This is never allowed. \
The text outside brackets is FIXED — sacred, untouchable.

You receive:
1. PARAGRAPHS TO RESTORE — the original text with brackets
2. ACCEPTED CONTEXT — nearby paragraphs that were already restored \
   successfully (for continuity and logic)
3. The SPIRITUAL READING that translates the passage into its \
   spiritual sense

Rules:
- Output COMPLETE PARAGRAPHS with additions ONLY inside [square brackets]
- Text OUTSIDE brackets must be EXACTLY as given — do not add, remove, \
  or change a single character
- For partial words like [te]aching, your fill + adjacent letters \
  must form a real word
- If a gap truly cannot be restored, keep it as [...]
- Write in the register of ancient cosmological teaching
- Do NOT use forward slash (/) in fills
- Output every paragraph as ¶N: followed by the complete text"""


def retry_failed_paragraphs(
    client: AnthropicFoundry,
    deployment: str,
    failed_paras: list[dict],
    spiritual_reading: str,
    accepted: dict[int, str],
    ch_num: int,
    *,
    debug: bool = False,
) -> dict[int, str] | None:
    """Retry rejected paragraphs with accepted context.

    Single call: streaming + adaptive thinking, text output.
    """
    lines = [
        "Some paragraphs in Chapter {} were rejected because text "
        "outside brackets was altered. Restore ONLY the following "
        "paragraphs. DO NOT change any text outside brackets.".format(ch_num),
        "",
    ]

    # Provide accepted context (neighboring paragraphs)
    if accepted:
        lines.append("--- ACCEPTED CONTEXT (already restored, for reference) ---")
        lines.append("")
        for pnum in sorted(accepted):
            lines.append(f"¶{pnum}: {accepted[pnum]}")
            lines.append("")
        lines.append("--- END CONTEXT ---")
        lines.append("")

    # Provide the paragraphs that need restoration
    lines.append("--- PARAGRAPHS TO RESTORE ---")
    lines.append("")
    for p in failed_paras:
        lines.append(f"¶{p['paragraph_number']}: {p['core_text']}")
        lines.append("")
    lines.append("--- END ---")
    lines.append("")

    # Include relevant spiritual reading
    lines.append("--- SPIRITUAL READING ---")
    lines.append("")
    lines.append(spiritual_reading)
    lines.append("")
    lines.append("--- END ---")
    lines.append("")
    lines.append(
        "Restore ONLY the paragraphs listed under PARAGRAPHS TO RESTORE. "
        "Output each as ¶N: followed by the complete text."
    )

    user_msg = "\n".join(lines)

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            text_parts = []
            in_thinking = False
            thinking_chars = 0

            with client.messages.stream(
                model=deployment,
                system=RETRY_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
                max_tokens=128000,
                thinking={"type": "adaptive"},
            ) as stream:
                for event in stream:
                    etype = getattr(event, "type", "")

                    # Thinking block started
                    if etype == "content_block_start":
                        block = getattr(event, "content_block", None)
                        if block and getattr(block, "type", "") == "thinking":
                            in_thinking = True
                            thinking_chars = 0
                            if debug:
                                print("\n  [thinking] ", end="", flush=True)
                        elif block and getattr(block, "type", "") == "text":
                            in_thinking = False
                            if debug:
                                print("\n  [output] ", end="", flush=True)

                    # Thinking delta
                    elif etype == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        if delta:
                            dtype = getattr(delta, "type", "")
                            if dtype == "thinking_delta":
                                chunk = getattr(delta, "thinking", "")
                                thinking_chars += len(chunk)
                                if debug:
                                    print(chunk, end="", flush=True)
                            elif dtype == "text_delta":
                                chunk = getattr(delta, "text", "")
                                text_parts.append(chunk)
                                if debug:
                                    print(chunk, end="", flush=True)

                    # Block ended
                    elif etype == "content_block_stop":
                        if in_thinking:
                            if debug:
                                print(f" [{thinking_chars} chars]", flush=True)
                            in_thinking = False

                    # Message ended
                    elif etype == "message_stop":
                        if debug:
                            print(flush=True)
            if text_parts:
                raw = "\n".join(text_parts)
                parsed = parse_restored_paragraphs(raw)
                if parsed:
                    return parsed

            print(
                f"  Retry Ch.{ch_num}: no usable output "
                f"(attempt {attempt}/{max_retries})"
            )
            if attempt < max_retries:
                time.sleep(attempt * 5)
                continue
            return None

        except Exception as e:
            err_str = str(e)
            if "content_filter" in err_str.lower():
                print(
                    f"  Retry content filter Ch.{ch_num}, "
                    f"attempt {attempt}/{max_retries}"
                )
                if attempt < max_retries:
                    time.sleep(attempt * 10)
                    continue
            elif "rate" in err_str.lower() or "429" in err_str:
                wait = 60.0
                print(f"  Retry rate limit, waiting {wait:.0f}s...")
                time.sleep(wait)
                continue
            else:
                print(
                    f"  Retry error Ch.{ch_num} "
                    f"(attempt {attempt}/{max_retries}): "
                    f"{type(e).__name__}: {e}"
                )
                traceback.print_exc()
                if attempt < max_retries:
                    time.sleep(attempt * 5)
                    continue
            return None
    return None


# ---------------------------------------------------------------------------
# Validation: skeleton-based integrity check
# ---------------------------------------------------------------------------


def normalize_skeleton(text: str) -> str:
    """Strip all [bracket content] and normalize whitespace + punctuation.

    The skeleton is the INVARIANT — it must be identical between
    original and restored text. Any change to the skeleton means the
    model altered text it was not allowed to touch.

    Normalization handles trivial model-injected differences:
    - Curly quotes → straight quotes  (" " ' ' → " ')
    - Strip surrounding quotes from the entire text
    - Normalize ellipsis character (… → ...)
    - Normalize em/en dashes (— – → --)
    - Collapse whitespace
    """
    stripped = LACUNA_RE.sub("", text)

    # Curly quotes → straight quotes
    stripped = stripped.replace("\u201c", '"')   # "
    stripped = stripped.replace("\u201d", '"')   # "
    stripped = stripped.replace("\u2018", "'")   # '
    stripped = stripped.replace("\u2019", "'")   # '

    # Normalize ellipsis character → three dots
    stripped = stripped.replace("\u2026", "...")

    # Normalize em-dash and en-dash → double hyphen
    stripped = stripped.replace("\u2014", "--")   # —
    stripped = stripped.replace("\u2013", "--")   # –

    # Collapse whitespace first
    stripped = " ".join(stripped.split())

    # Strip surrounding quotes (model sometimes wraps entire output)
    stripped = stripped.strip('"\'')

    return stripped


def skeleton_matches(original: str, restored: str) -> bool:
    """Check whether restored text preserves the original skeleton."""
    return normalize_skeleton(original) == normalize_skeleton(restored)


def parse_restored_paragraphs(model_output: str) -> dict[int, str]:
    """Parse ¶N-prefixed paragraphs from model output.

    Returns {paragraph_number: restored_text}.
    """
    result: dict[int, str] = {}
    pattern = re.compile(r"¶(\d+)[:\s]\s*(.*?)(?=\n¶\d|\Z)", re.DOTALL)
    for m in pattern.finditer(model_output):
        pnum = int(m.group(1))
        text = m.group(2).strip()
        if text:
            result[pnum] = text
    return result


def extract_fills_by_diff(
    original: str,
    restored: str,
    pnum: int,
) -> list[dict]:
    """Extract fills from bracket pairs between original and restored.

    PRECONDITION: skeleton_matches(original, restored) is True.
    """
    orig_brackets = list(LACUNA_RE.finditer(original))
    rest_brackets = list(LACUNA_RE.finditer(restored))

    fills = []
    for i, (orig_m, rest_m) in enumerate(zip(orig_brackets, rest_brackets), 1):
        orig_content = orig_m.group(1)
        rest_content = rest_m.group(1)

        if orig_content != rest_content:
            fills.append(
                {
                    "paragraph": pnum,
                    "index": i,
                    "fill": rest_content,
                    "original": orig_content,
                    "notes": "",
                    "confidence": "moderate",
                }
            )
        else:
            fills.append(
                {
                    "paragraph": pnum,
                    "index": i,
                    "fill": rest_content,
                    "original": orig_content,
                    "notes": "unchanged",
                    "confidence": "strong" if rest_content.strip() != "..." else "",
                }
            )

    return fills


def validate_restoration(
    core_paras: list[dict],
    restored_paras: dict[int, str],
    lacunae_map: dict[int, list[dict]],
) -> tuple[
    dict[int, str],  # accepted {pnum: restored_text}
    dict[int, str],  # rejected {pnum: reason}
    list[dict],  # fills
    list[dict],  # reconstructions
    list[str],  # violations (informational)
]:
    """Validate restored paragraphs using skeleton invariant.

    A paragraph is ACCEPTED only if:
      1. Its skeleton (text outside brackets) is identical to the original
      2. Bracket count matches

    Returns (accepted, rejected, fills, reconstructions, violations).
    """
    accepted: dict[int, str] = {}
    rejected: dict[int, str] = {}
    all_fills: list[dict] = []
    all_reconstructions: list[dict] = []
    all_violations: list[str] = []

    originals = {p["paragraph_number"]: p["core_text"] for p in core_paras}

    for pnum, restored_text in sorted(restored_paras.items()):
        original = originals.get(pnum)
        if original is None:
            all_violations.append(f"¶{pnum}: not in original")
            rejected[pnum] = "not in original"
            continue

        restored_text = fix_stray_brackets(restored_text)

        # --- SKELETON CHECK (the invariant) ---
        if not skeleton_matches(original, restored_text):
            reason = (
                f"skeleton altered: "
                f"'{normalize_skeleton(original)[:80]}' vs "
                f"'{normalize_skeleton(restored_text)[:80]}'"
            )
            all_violations.append(f"¶{pnum}: REJECTED — {reason}")
            rejected[pnum] = reason
            continue

        # --- BRACKET COUNT CHECK ---
        orig_n = len(list(LACUNA_RE.finditer(original)))
        rest_n = len(list(LACUNA_RE.finditer(restored_text)))
        if orig_n != rest_n:
            reason = f"bracket count mismatch: {orig_n} vs {rest_n}"
            all_violations.append(f"¶{pnum}: REJECTED — {reason}")
            rejected[pnum] = reason
            continue

        # --- ACCEPTED ---
        accepted[pnum] = restored_text
        all_reconstructions.append(
            {
                "paragraph": pnum,
                "reconstructed_text": restored_text,
            }
        )

        # Extract fills if paragraph had lacunae
        if pnum in lacunae_map:
            fills = extract_fills_by_diff(original, restored_text, pnum)
            all_fills.extend(fills)

    return accepted, rejected, all_fills, all_reconstructions, all_violations


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def fix_stray_brackets(text: str) -> str:
    """Remove unmatched brackets from reconstruction text."""
    stack: list[int] = []
    to_remove: set[int] = set()
    for i, ch in enumerate(text):
        if ch == "[":
            stack.append(i)
        elif ch == "]":
            if stack:
                stack.pop()
            else:
                to_remove.add(i)
    to_remove.update(stack)
    if not to_remove:
        return text
    return "".join(ch for i, ch in enumerate(text) if i not in to_remove)


# ---------------------------------------------------------------------------
# Save / Load
# ---------------------------------------------------------------------------


def save_result(
    ch_num: int,
    title: str,
    all_fills: list[dict],
    all_reconstructions: list[dict],
    lacunae_map: dict[int, list[dict]],
    total_lacunae: int,
    spiritual_reading: str | None = None,
    violations: list[str] | None = None,
    thinking_summary: str | None = None,
) -> None:
    """Save restoration result as JSON."""
    CHAPTERS_OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = CHAPTERS_OUT_DIR / f"ch_{ch_num:03d}.json"

    lacunae_serial = {str(k): v for k, v in lacunae_map.items()}

    n_filled = sum(
        1
        for f in all_fills
        if f.get("fill", "...").strip() != "..."
        and f.get("fill", "") != f.get("original", "")
    )
    n_unchanged = sum(
        1 for f in all_fills if f.get("fill", "") == f.get("original", "")
    )

    data = {
        "chapter_number": ch_num,
        "chapter_title": title,
        "total_lacunae": total_lacunae,
        "lacunae_map": lacunae_serial,
        "spiritual_reading": spiritual_reading,
        "reconstructions": all_reconstructions,
        "fills": all_fills,
        "violations": violations or [],
        "assessment": (
            f"{n_filled} fills changed, "
            f"{n_unchanged} unchanged, "
            f"{len(violations or [])} violations"
        ),
    }
    if thinking_summary:
        data["thinking_summary"] = thinking_summary

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def is_done(ch_num: int) -> bool:
    return (CHAPTERS_OUT_DIR / f"ch_{ch_num:03d}.json").exists()


# ---------------------------------------------------------------------------
# Assembly: build the restored document
# ---------------------------------------------------------------------------


def assemble_restored(core_chapters: dict[int, dict]) -> str:
    """Assemble all restorations into a continuous restored document."""
    restorations_by_ch: dict[int, dict] = {}
    for path in sorted(CHAPTERS_OUT_DIR.glob("ch_*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            restorations_by_ch[data["chapter_number"]] = data

    if not restorations_by_ch:
        print("ERROR: No restoration files found.")
        return ""

    lines: list[str] = []
    lines.append("# The Kephalaia Teaching Core — Restored Text")
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

        # Build lookup
        recon_by_para: dict[int, str] = {}
        fills_by_para: dict[int, list[dict]] = {}
        if rest_ch:
            for recon in rest_ch.get("reconstructions", []):
                recon_by_para[recon["paragraph"]] = recon["reconstructed_text"]
            for fill in rest_ch.get("fills", []):
                para = fill["paragraph"]
                if para not in fills_by_para:
                    fills_by_para[para] = []
                fills_by_para[para].append(fill)

        for para in core_ch.get("paragraphs", []):
            pnum = para["paragraph_number"]
            core_text = para.get("core_text")
            if not core_text:
                continue

            if pnum in recon_by_para:
                restored = fix_stray_brackets(recon_by_para[pnum])
                lines.append(f"**¶{pnum}** {restored}")
                lines.append("")

                # Count fills
                para_fills = fills_by_para.get(pnum, [])
                for f in para_fills:
                    if f.get("fill", "...").strip() == "...":
                        total_unrestorable += 1
                    elif f.get("fill", "") != f.get("original", ""):
                        total_fills += 1
            else:
                lines.append(f"**¶{pnum}** {core_text}")
                lines.append("")

        # Chapter assessment
        if rest_ch:
            assessment = rest_ch.get("assessment", "")
            violations = rest_ch.get("violations", [])
            if assessment:
                lines.append(f"**Assessment:** {assessment}")
            if violations:
                lines.append(f"**Violations:** {len(violations)}")
                for v in violations[:5]:
                    lines.append(f"> {v}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Statistics header
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
        description="Correspondential restoration of the Kephalaia " "teaching core"
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
    parser.add_argument(
        "--concurrency",
        "-j",
        type=int,
        default=1,
        help="Number of chapters to process in parallel (default: 1)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show model thinking log (only effective with -j 1)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


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
        chapters = [ch for ch in all_chapters if ch["chapter_number"] == args.chapter]
        if not chapters:
            print(f"ERROR: Chapter {args.chapter} not found")
            sys.exit(1)
    elif args.range:
        m = re.match(r"(\d+)-(\d+)", args.range)
        if not m:
            print("ERROR: Invalid range. Use '38-55'")
            sys.exit(1)
        start, end = int(m.group(1)), int(m.group(2))
        chapters = [ch for ch in all_chapters if start <= ch["chapter_number"] <= end]
    else:
        chapters = all_chapters

    if args.limit:
        chapters = chapters[: args.limit]

    # Skip already processed
    if not args.overwrite:
        to_process = [ch for ch in chapters if not is_done(ch["chapter_number"])]
        skipped = len(chapters) - len(to_process)
        if skipped > 0:
            print(f"  Skipping {skipped} already-done (use --overwrite)")
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
            f"  Ch.{num:3d}  ({len(core_paras):3d} core ¶s, "
            f"{n_lacunae} lacunae)  {title}"
        )

    if args.dry_run:
        print("\n[DRY RUN] No API calls made.")
        return

    # Create client
    client, deployment = create_claude_client()
    concurrency = max(1, args.concurrency)
    print(f"\nUsing model: {deployment}")
    print(f"Concurrency: {concurrency}")
    if args.debug:
        if concurrency == 1:
            print("Debug: thinking log enabled")
        else:
            print("Debug: thinking log disabled (requires -j 1)")
    print()

    # Prepare output dirs
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CHAPTERS_OUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- Worker ---
    show_debug = args.debug and concurrency == 1
    print_lock = threading.Lock()
    results_list: list[int] = []
    errors_list: list[int] = []
    counter = {"done": 0}
    total_to_process = len(chapters)

    def process_one(ch: dict) -> None:
        ch_num = ch["chapter_number"]
        title = ch.get("chapter_title", "")[:50]

        core_paras = extract_core_paragraphs(ch)
        lacunae_map, total_lacunae = find_lacunae(core_paras)

        if total_lacunae == 0:
            with print_lock:
                counter["done"] += 1
                print(
                    f"[{counter['done']}/{total_to_process}] "
                    f"Ch.{ch_num} — no lacunae, skip"
                )
            return

        with print_lock:
            print(
                f"  Ch.{ch_num} ({total_lacunae} lacunae) " f"{title}...",
                end="",
                flush=True,
            )

        # --- Phase 1: Spiritual Reading (use cache if available) ---
        cached_path = CHAPTERS_OUT_DIR / f"ch_{ch_num:03d}.json"
        cached_reading = None
        if cached_path.exists():
            try:
                with open(cached_path, encoding="utf-8") as f:
                    cached_data = json.load(f)
                cached_reading = cached_data.get("spiritual_reading")
            except Exception:
                pass

        if cached_reading:
            spiritual_reading = cached_reading
            with print_lock:
                print(f" [cached reading]", end="", flush=True)
        else:
            with print_lock:
                print(f" phase 1...", end="", flush=True)
            spiritual_reading = generate_spiritual_reading(
                client, deployment, core_paras, ch_num, debug=show_debug
            )
            if not spiritual_reading:
                with print_lock:
                    counter["done"] += 1
                    errors_list.append(ch_num)
                    print(
                        f"\n[{counter['done']}/{total_to_process}] "
                        f"Ch.{ch_num} FAILED (spiritual reading)"
                    )
                return

        with print_lock:
            print(f" phase 2...", end="", flush=True)

        # --- Phase 2: Restoration (single call) ---
        restored_paras = restore_chapter(
            client,
            deployment,
            core_paras,
            spiritual_reading,
            ch_num,
            debug=show_debug,
        )
        if not restored_paras:
            with print_lock:
                counter["done"] += 1
                errors_list.append(ch_num)
                print(
                    f"\n[{counter['done']}/{total_to_process}] "
                    f"Ch.{ch_num} FAILED (restoration)"
                )
            return

        # --- Validation with skeleton check ---
        accepted, rejected, all_fills, all_recons, violations = validate_restoration(
            core_paras, restored_paras, lacunae_map
        )

        # --- Retry loop for rejected paragraphs ---
        max_para_retries = 2
        for retry_round in range(1, max_para_retries + 1):
            if not rejected:
                break

            with print_lock:
                print(
                    f"  Ch.{ch_num} retry {retry_round}: "
                    f"{len(rejected)} rejected ¶s "
                    f"({', '.join(str(p) for p in sorted(rejected))})",
                    flush=True,
                )

            # Build context: only paragraphs that need retrying,
            # plus accepted restorations as surrounding context
            retry_paras = [p for p in core_paras if p["paragraph_number"] in rejected]
            retry_result = retry_failed_paragraphs(
                client,
                deployment,
                retry_paras,
                spiritual_reading,
                accepted,
                ch_num,
            )
            if not retry_result:
                break

            # Validate retried paragraphs
            new_accepted, still_rejected, new_fills, new_recons, new_viols = (
                validate_restoration(retry_paras, retry_result, lacunae_map)
            )

            # Merge newly accepted
            accepted.update(new_accepted)
            all_fills.extend(new_fills)
            all_recons.extend(new_recons)
            violations.extend(new_viols)

            # Update rejected set
            rejected = still_rejected

        # For any still-rejected paragraphs, keep original text
        originals = {p["paragraph_number"]: p["core_text"] for p in core_paras}
        for pnum in rejected:
            violations.append(
                f"¶{pnum}: KEPT ORIGINAL after {max_para_retries} retries"
            )
            all_recons.append(
                {
                    "paragraph": pnum,
                    "reconstructed_text": originals.get(pnum, ""),
                }
            )

        n_changed = sum(
            1
            for f in all_fills
            if f.get("fill", "") != f.get("original", "")
            and f.get("fill", "...").strip() != "..."
        )

        save_result(
            ch_num,
            title,
            all_fills,
            all_recons,
            lacunae_map,
            total_lacunae,
            spiritual_reading=spiritual_reading,
            violations=violations,
        )

        status = f"OK — {n_changed}/{total_lacunae} filled"
        if rejected:
            status += f", {len(rejected)} kept original"
        if violations:
            status += f", {len(violations)} notes"

        with print_lock:
            counter["done"] += 1
            results_list.append(ch_num)
            print(f"\n[{counter['done']}/{total_to_process}] " f"Ch.{ch_num} {status}")

    # --- Execute ---
    if concurrency == 1:
        for ch in chapters:
            process_one(ch)
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {executor.submit(process_one, ch): ch for ch in chapters}
            for future in as_completed(futures):
                exc = future.exception()
                if exc:
                    ch = futures[future]
                    with print_lock:
                        print(f"  Ch.{ch['chapter_number']} EXCEPTION: {exc}")
                        errors_list.append(ch["chapter_number"])

    # Summary
    print(f"\n{'='*60}")
    print("RESTORATION COMPLETE")
    print(f"  Processed: {len(results_list)}")
    print(f"  Errors: {len(errors_list)}")
    if errors_list:
        print(f"  Failed: {sorted(errors_list)}")

    # Assemble
    print("\nAssembling restored document...")
    text = assemble_restored(core_by_num)
    if text:
        save_assembly(text)
    print("Done.")


if __name__ == "__main__":
    main()
