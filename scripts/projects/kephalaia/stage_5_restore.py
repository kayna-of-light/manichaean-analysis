#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Correspondential restoration of the Kephalaia teaching core.

Architecture:
  Phase 1 — Spiritual Reading (Claude): Translate whole chapter from
            natural sense into spiritual sense via correspondences.
  Phase 2 — Tool-Call Restoration (Claude): Multi-turn conversation
            where the model uses the restore_lacuna tool for each gap.
            Each fill is individually validated. The model receives
            feedback and continues until all gaps are processed.

Primary model: Claude Opus 4.6 via Azure AI Foundry (AnthropicFoundry).
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

from project_config import load_project, list_projects, SECRETS_PATH

# ---------------------------------------------------------------------------
# Paths — set by configure_paths() at startup
# ---------------------------------------------------------------------------

PROJECT_CFG = None                     # ProjectConfig — set by configure_paths()
CORE_CHAPTERS_DIR: Path | None = None   # input: core/chapters/
OUTPUT_DIR: Path | None = None          # output: restored/
CHAPTERS_OUT_DIR: Path | None = None    # output: restored/chapters/
ASSEMBLED_FILE: Path | None = None      # output: assembled markdown


def configure_paths(project_name: str) -> None:
    """Set module-level path variables from project config."""
    global PROJECT_CFG
    global CORE_CHAPTERS_DIR, OUTPUT_DIR, CHAPTERS_OUT_DIR, ASSEMBLED_FILE

    cfg = load_project(project_name)
    cfg.paths.ensure_dirs()
    PROJECT_CFG = cfg

    CORE_CHAPTERS_DIR = cfg.paths.core_chapters
    OUTPUT_DIR = cfg.paths.restored
    CHAPTERS_OUT_DIR = cfg.paths.restored_chapters
    ASSEMBLED_FILE = cfg.paths.restored_assembled

    print(f"Project: {cfg.display_name}")
    print(f"  Type:   {cfg.document_type}")
    print(f"  Input:  {CORE_CHAPTERS_DIR}")
    print(f"  Output: {OUTPUT_DIR}")


def _get_system_prompt(base_prompt: str) -> str:
    """Adapt a base system prompt for the current project's tradition.

    For composite_text (Kephalaia) the prompt is returned unchanged.
    For fragment_collection the Kephalaia-specific references are
    replaced with the current project's name and language.
    """
    if not PROJECT_CFG or PROJECT_CFG.document_type == "composite_text":
        return base_prompt

    name = PROJECT_CFG.display_name
    lang = PROJECT_CFG.language.replace("_", " ")

    prompt = base_prompt

    # Replace text-origin description in spiritual reading prompt
    prompt = prompt.replace(
        "The text you receive is the oldest teaching substrate of the Coptic "
        "Kephalaia \u2014 pre-Manichaean cosmological teaching that Mani inherited "
        "from the Eastern tradition.",
        f"The text you receive is from the {name}, a {lang} "
        f"Manichaean text ({PROJECT_CFG.edition}).",
    )
    # Replace text-origin in restoration prompt
    prompt = prompt.replace(
        "the oldest teaching substrate of the \nCoptic Kephalaia.",
        f"the {name}, a {lang} Manichaean text.",
    )
    # Ownership references
    prompt = prompt.replace("The Kephalaia\u2019s", f"The {name}\u2019s")
    prompt = prompt.replace("the Kephalaia\u2019s", f"the {name}\u2019s")
    prompt = prompt.replace(
        "the Coptic Kephalaia", f"the {name}"
    )
    prompt = prompt.replace("the Kephalaia", f"the {name}")
    prompt = prompt.replace("The Kephalaia", f"The {name}")
    # Manuscript type
    prompt = prompt.replace("Coptic papyrus", f"{lang} manuscript")

    # Note about original text
    if PROJECT_CFG.include_original_text:
        prompt += (
            f"\n\nADDITIONAL CONTEXT: The original {lang} transliteration "
            f"is provided alongside the English translation. Technical terms "
            f"in the original language may clarify correspondences where the "
            f"English is ambiguous."
        )

    return prompt

# ---------------------------------------------------------------------------
# Gap patterns — square brackets [...] and curly braces {...}
# ---------------------------------------------------------------------------

LACUNA_RE = re.compile(r"\[([^\]]*)\]")
CURLY_GAP_RE = re.compile(r"\{([^}]*)\}")


def find_all_gaps(
    text: str,
) -> list[tuple[int, int, str, str, str]]:
    """Find all gap markers (both [] and {}) sorted by position.

    Returns list of (start, end, full_match, content, gap_type)
    where gap_type is 'square' or 'curly'.
    """
    gaps: list[tuple[int, int, str, str, str]] = []
    for m in LACUNA_RE.finditer(text):
        gaps.append((m.start(), m.end(), m.group(0), m.group(1), "square"))
    for m in CURLY_GAP_RE.finditer(text):
        gaps.append((m.start(), m.end(), m.group(0), m.group(1), "curly"))
    gaps.sort(key=lambda x: x[0])
    return gaps


def count_all_gaps(text: str) -> int:
    """Count total gap markers (both [] and {}) in text."""
    return len(list(LACUNA_RE.finditer(text))) + len(
        list(CURLY_GAP_RE.finditer(text))
    )


def _clean_streaming_output(text: str) -> str:
    """Trim leading/trailing whitespace from streaming output."""
    return text.strip()


# ---------------------------------------------------------------------------
# Gap classification
# ---------------------------------------------------------------------------

# Page markers inside gaps: (N) where N is digits
_PAGE_IN_GAP_RE = re.compile(r"\(\d+\)")


def is_actual_gap(content: str) -> bool:
    """Check if bracket content is an actual gap (not translator fill).

    Actual gaps contain only dots, spaces, page markers, or are empty.
    Translator fills contain real word characters.

    HYBRID gaps (e.g. "[ower ...]", "[... which]") contain BOTH readable
    letters AND ellipsis dots.  The letters are the partially-readable
    portion; the dots represent still-missing text.  These are gaps too.
    """
    stripped = content.strip()
    if not stripped:
        return True  # empty brackets
    # Hybrid check: if content has ellipsis dots, it's a gap even if
    # some letters are also readable (partial reconstruction + lacuna).
    if re.search(r"\.{2,}", stripped):
        return True
    # Remove dots, spaces, page markers, slashes
    cleaned = re.sub(r"[\s./()\d]", "", stripped)
    return not cleaned  # True if only whitespace/dots/numbers remain


def classify_gap_size(content: str, gap_type: str) -> str:
    """Classify gap size based on content pattern.

    Returns: 'single', 'small', 'medium', or 'large'.
    """
    if gap_type == "curly":
        return "single"
    content = content.strip()
    if not content:
        return "single"  # empty square brackets
    # Strip page markers before counting dots
    cleaned = _PAGE_IN_GAP_RE.sub("", content).strip()
    # Count dot groups (... or . . .)
    n_ellipsis = len(re.findall(r"\.{2,}", cleaned))
    n_spaced = len(re.findall(r"\.\s\.\s\.", cleaned))
    total = max(n_ellipsis, n_spaced)
    if total <= 1:
        return "small"
    elif total == 2:
        return "medium"
    else:
        return "large"


# ---------------------------------------------------------------------------
# Prompts
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
best reading.

IMPORTANT — Gap anchors:
The text contains numbered gap markers like [GAP-1: ...], [GAP-2: ...], \
or {GAP-3}. These are lacunae (missing text) that will be restored \
later using your spiritual reading as a guide.

As you translate each passage, PRESERVE these gap markers inline in \
your spiritual prose at the corresponding position. When you reach \
a gap, write what the spiritual sense requires at that point and \
embed the marker so a restorer can see exactly what spiritual \
reality belongs there.

Example:
  Original: "the great [GAP-1: ...], the battle that the Darkness spread"
  Spiritual: "the great [GAP-1] assault that falsity from evil propagated"

The marker anchors the spiritual insight to the specific gap. \
Do NOT fill in the natural-plane word — just show what spiritual \
reality the gap expresses. The restorer will translate back to \
the text's own vocabulary."""


RESTORATION_PROMPT = """\
You are an expert in the doctrine of correspondences as written by \
Emanuel Swedenborg, with deep specialization in ancient cosmological \
vocabulary — Zoroastrian, Manichaean, and Persian-Iranian traditions.

You are restoring lacunae in the oldest teaching substrate of the \
Coptic Kephalaia. The text has gaps marked with numbered identifiers \
(GAP-1, GAP-2, etc.). Your task is to fill these gaps using the \
correspondential logic of the text.

You receive:
1. The ORIGINAL TEXT with numbered gaps: [GAP-N: ...] or {GAP-N}
2. A SPIRITUAL READING that translates the text into its spiritual sense

The Kephalaia's oldest substrate describes systems that Swedenborg \
also describes. Before working on gap fills you think about and identify \
the Swedeborgian system being described. Knowing the system equivalent \
will help fill gaps accurately throughout the rest of the process. \
You output this as a message to the user first before working on the actual fills.

The spiritual reading tells you WHAT spiritual reality each passage \
describes. It contains GAP-N anchor markers at each gap position, \
showing exactly what spiritual reality belongs at that point. \
Your fills must express that spiritual reality in the text's own \
natural-plane vocabulary — the language of the Kephalaia itself.

For each gap, find its GAP-N marker in the spiritual reading to see \
what spiritual reality the gap expresses, then translate that back \
into the Kephalaia's natural-plane register.

Brackets WITHOUT a GAP-N identifier are translator fills — do not \
modify them. Only fill gaps that have a GAP-N label.

Lacuna types by size:
- {GAP-N} — exactly ONE word missing. Fill with exactly one word.
- [GAP-N: ...]next_letters — partial word gap. Your fill + the \
  adjacent letters must form a real word.
- [GAP-N: ...] — small gap (a few words to a short phrase)
- [GAP-N: ... ...] — medium gap (roughly a clause or sentence)
- [GAP-N: ... ... ...] — large gap (multiple sentences or lines)
- [GAP-N: REVIEW word(s)] — editorial review. The translator supplied \
  "word(s)" but the manuscript is damaged; this is the editor's guess \
  without correspondential awareness. Review the editor's choice through \
  the correspondential lens. If the editor's word fits the spiritual sense, \
  confirm it by submitting the same word. If the spiritual reading suggests \
  a more precise or accurate word, submit the better word instead.

Gap-size restoration policy:
- {GAP-N} and [GAP-N: ...] — ALWAYS restore.
- [GAP-N: REVIEW ...] — ALWAYS review. Either confirm or correct.
- [GAP-N: ... ...] (medium) — restore ONLY if surrounding context \
  strongly constrains what belongs. Otherwise skip it.
- [GAP-N: ... ... ...] (large) — NEVER restore. Skip entirely.

Manuscript notation within gap content:
- "/" in gap content marks a line break in the damaged Coptic papyrus. \
  Each "..." separated by "/" represents roughly one lost manuscript \
  line. Do NOT include "/" in your fills — bridge the semantic gap \
  with continuous prose.
- The gap SIZE already accounts for line breaks: \
  [...] = small, [... / ...] = medium, [... / ... / ...] = large.

For each gap you can fill, call the restore_lacuna tool with:
- lacuna_id: the gap ID (e.g., "GAP-1")
- fill: your restored text (just the words — no brackets)
- explanation: why this fill fits (one sentence)
- confidence: "high", "moderate", or "low"

Rules:
- {GAP-N} fills must be exactly one word
- Do NOT start fills with punctuation (comma, period, semicolon)
- Do NOT use forward slash (/) in fills
- Do NOT include manuscript page numbers in fills
- Write in the register of ancient cosmological teaching — impersonal, \
  structural, expository
- Skip gaps you cannot confidently restore — do not force a fill
- When you have filled every gap you can confidently restore, STOP. \
  Do not fill remaining gaps with low confidence just because they \
  exist. Skipping is the correct action for uncertain gaps."""


# ---------------------------------------------------------------------------
# Tool definition
# ---------------------------------------------------------------------------

RESTORE_LACUNA_TOOL = {
    "name": "restore_lacuna",
    "description": (
        "Fill a single lacuna (gap) in the text. "
        "Call this once per gap you want to restore. "
        "For gaps you cannot confidently fill, simply skip them — "
        "do not call this tool for those gaps."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "lacuna_id": {
                "type": "string",
                "description": "The gap identifier (e.g., 'GAP-1')",
            },
            "fill": {
                "type": "string",
                "description": (
                    "The restored text. For single-word gaps ({GAP-N}), "
                    "exactly one word. For phrase gaps ([GAP-N: ...]), "
                    "the complete phrase. No brackets — just the words."
                ),
            },
            "explanation": {
                "type": "string",
                "description": (
                    "One-sentence explanation of why this fill fits "
                    "based on correspondential logic and context."
                ),
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "moderate", "low"],
                "description": (
                    "high = grammar/context uniquely determine the fill; "
                    "moderate = strong constraints but alternatives exist; "
                    "low = educated guess based on theme"
                ),
            },
        },
        "required": ["lacuna_id", "fill", "explanation", "confidence"],
    },
}


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


# ---------------------------------------------------------------------------
# Core text processing
# ---------------------------------------------------------------------------

# Regex for page markers like ⟨p.18⟩ or ⟨p.N⟩
PAGE_MARKER_RE = re.compile(r"\s*\u27E8p\.\d+\u27E9\s*")
# Bare ellipsis: consecutive ... groups (possibly separated by /)
# Groups them so "... ..." becomes ONE medium gap, not two smalls.
BARE_DOTS_RE = re.compile(r"\.{3,}(?:\s*(?:/\s*)?\.{3,})*")


def fix_source_brackets(text: str) -> str:
    """Repair unbalanced brackets in source core_text.

    Handles four categories found in the Kephalaia corpus:

    1. UNCLOSED TRAILING — text ends with `[...` or `[ht ...`
       → Close with `]`
    2. DOUBLE CLOSE — `]]` (e.g. `a[l]]` or `[ ... ]]ife`)
       → Remove the extra `]`
    3. STRAY CLOSE — `]` without matching `[`
       → Remove the orphan `]`
    4. UNCLOSED MID — `[` without matching `]` in middle of text
       → Close with `]` before next `[` or at text end
    """
    # Pass 1: Fix double brackets `]]` → single `]`
    text = text.replace("]]", "]")

    # Pass 2: Walk through and fix remaining imbalances
    result = []
    depth = 0
    for i, ch in enumerate(text):
        if ch == "[":
            if depth > 0:
                # Already inside a bracket — close the previous one first
                result.append("]")
                depth -= 1
            result.append(ch)
            depth += 1
        elif ch == "]":
            if depth > 0:
                result.append(ch)
                depth -= 1
            else:
                # Stray close bracket — skip it
                pass
        else:
            result.append(ch)

    # If we end with unclosed bracket(s), close them
    while depth > 0:
        result.append("]")
        depth -= 1

    return "".join(result)


def clean_core_text(text: str) -> str:
    """Clean core text before processing.

    1. Strip manuscript page markers (e.g. ⟨p.20⟩) — structural metadata
    2. Strip braces from uncertain readings: {word} → word
       (the word is there, braces are translatorial uncertainty)
    3. Preserve empty {} as single-word lacuna markers
    4. Fix unbalanced square brackets (common in OCR/extraction)
    5. Wrap bare ... in [ ... ] so they are counted as lacunae
    6. Collapse multiple whitespace / newlines
    """
    # Strip page markers (structural metadata, not content)
    text = PAGE_MARKER_RE.sub(" ", text)

    # Strip braces from uncertain readings {word} → word
    # (but leave empty {} as single-word gap markers)
    text = re.sub(r"\{([^}.]+)\}", r"\1", text)

    # --- Fix unbalanced square brackets ---
    text = fix_source_brackets(text)

    # Protect existing bracketed content with placeholder
    placeholders: list[str] = []

    def _save_bracket(m: re.Match) -> str:
        placeholders.append(m.group(0))
        return f"\x00BRACKET{len(placeholders) - 1}\x00"

    text = LACUNA_RE.sub(_save_bracket, text)
    # Now wrap any remaining bare dots (preserving original content for sizing)
    text = BARE_DOTS_RE.sub(lambda m: "[ " + m.group(0) + " ]", text)
    # Restore bracketed content
    for i, orig in enumerate(placeholders):
        text = text.replace(f"\x00BRACKET{i}\x00", orig)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def find_lacunae(
    core_paras: list[dict],
) -> tuple[dict[int, list[dict]], int]:
    """Identify all gap markers ([brackets] and {curly}) in core paragraphs."""
    lacunae_map: dict[int, list[dict]] = {}
    total = 0
    for p in core_paras:
        pnum = p["paragraph_number"]
        text = p["core_text"]
        gaps = find_all_gaps(text)
        if gaps:
            lacunae_map[pnum] = []
            for i, (start, end, full, content, gap_type) in enumerate(gaps, 1):
                lacunae_map[pnum].append(
                    {
                        "index": i,
                        "start": start,
                        "end": end,
                        "original": full,
                        "content": content,
                        "gap_type": gap_type,
                    }
                )
            total += len(gaps)
    return lacunae_map, total


# ---------------------------------------------------------------------------
# Phase 1: Spiritual Reading
# ---------------------------------------------------------------------------


def generate_spiritual_reading(
    client: AnthropicFoundry,
    deployment: str,
    numbered_text: str,
    ch_num: int,
    *,
    original_text: str = "",
    debug: bool = False,
) -> str | None:
    """Generate a correspondential reading of the whole chapter.

    Receives the numbered text (with GAP-N markers) so the spiritual
    reading can embed anchor points for Phase 2 restoration.

    If *original_text* is provided (for fragment collections with
    interleaved original language), it is appended as additional
    context for the model.
    """
    lines = [
        "Translate the following chapter from its natural sense "
        "into its spiritual sense.\n",
        "The text contains GAP-N markers for lacunae. Preserve these "
        "markers inline in your spiritual translation at the "
        "corresponding positions.\n",
        "--- CORE TEXT (oldest teaching layer) ---\n",
        numbered_text,
        "",
        "--- END CORE TEXT ---",
    ]

    # Include original language text when available
    if original_text:
        lang = (
            PROJECT_CFG.language.replace("_", " ").title()
            if PROJECT_CFG
            else "Original"
        )
        lines.extend([
            "",
            f"--- ORIGINAL TEXT ({lang} transliteration) ---\n",
            original_text,
            "",
            "--- END ORIGINAL TEXT ---",
        ])

    user_msg = "\n".join(lines)

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            text_parts: list[str] = []
            in_thinking = False
            thinking_chars = 0

            with client.messages.stream(
                model=deployment,
                system=_get_system_prompt(SPIRITUAL_READING_PROMPT),
                messages=[{"role": "user", "content": user_msg}],
                max_tokens=128_000,
                thinking={"type": "adaptive"},
            ) as stream:
                for event in stream:
                    etype = getattr(event, "type", "")

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

                    elif etype == "content_block_stop":
                        if in_thinking:
                            if debug:
                                print(f" [{thinking_chars} chars]", flush=True)
                            in_thinking = False

                    elif etype == "message_stop":
                        if debug:
                            print(flush=True)

            if text_parts:
                return _clean_streaming_output("".join(text_parts))
            return None

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
# Phase 2: Tool-Call Restoration
# ---------------------------------------------------------------------------


def _is_free_editorial(text: str, start: int, end: int) -> bool:
    """True if bracket at text[start:end] is a free-standing editorial fill.

    A free editorial choice is a bracket whose content has real letters
    but is NOT glued to adjacent word characters (i.e. not a letter
    repair like Mi[nd] or [fashio]ned).
    """
    char_before = text[start - 1] if start > 0 else " "
    char_after = text[end] if end < len(text) else " "
    return not (char_before.isalpha() or char_before == "-") and not (
        char_after.isalpha() or char_after == "-"
    )


def number_chapter_gaps(
    core_paras: list[dict],
) -> tuple[str, list[dict]]:
    """Number all actual gaps AND free editorial choices for restoration.

    Three categories of brackets:
    1. Actual gaps (dots/empty) → GAP-N for filling
    2. Free editorial choices (full words, not glued) → GAP-N for review
    3. Letter repairs (glued to adjacent text) → kept unchanged

    Returns (numbered_text_for_prompt, gap_registry).
    Each registry entry is a dict with: gap_id, paragraph, gap_index,
    gap_type, size, original, full_match, start, end, filled, fill,
    explanation, confidence.
    """
    gap_registry: list[dict] = []
    gap_counter = 0
    para_gap_counts: dict[int, int] = {}
    lines: list[str] = []

    for p in core_paras:
        pnum = p["paragraph_number"]
        text = p["core_text"]
        gaps = find_all_gaps(text)

        parts: list[str] = []
        prev_end = 0

        for start, end, full_match, content, gap_type in gaps:
            # Add text before this gap
            parts.append(text[prev_end:start])

            if is_actual_gap(content):
                gap_counter += 1
                gap_id = f"GAP-{gap_counter}"
                size = classify_gap_size(content, gap_type)

                # Track per-paragraph index
                para_gap_counts.setdefault(pnum, 0)
                para_gap_counts[pnum] += 1

                # Build numbered marker for prompt
                if gap_type == "curly":
                    parts.append(f"{{{gap_id}}}")
                else:
                    # Strip page markers from content shown to model
                    clean_content = _PAGE_IN_GAP_RE.sub("", content).strip()
                    clean_content = re.sub(r"\s+", " ", clean_content)
                    parts.append(f"[{gap_id}: {clean_content}]")

                gap_registry.append(
                    {
                        "gap_id": gap_id,
                        "paragraph": pnum,
                        "gap_index": para_gap_counts[pnum],
                        "gap_type": gap_type,
                        "size": size,
                        "original": content,
                        "full_match": full_match,
                        "start": start,
                        "end": end,
                        "filled": False,
                        "fill": None,
                        "explanation": None,
                        "confidence": None,
                    }
                )
            elif (
                gap_type == "square"
                and re.search(r"[a-zA-Z]", content)
                and _is_free_editorial(text, start, end)
            ):
                # Free editorial choice — editor supplied a word/phrase
                # without manuscript support.  Flag for review.
                gap_counter += 1
                gap_id = f"GAP-{gap_counter}"

                para_gap_counts.setdefault(pnum, 0)
                para_gap_counts[pnum] += 1

                parts.append(f"[{gap_id}: REVIEW {content.strip()}]")

                gap_registry.append(
                    {
                        "gap_id": gap_id,
                        "paragraph": pnum,
                        "gap_index": para_gap_counts[pnum],
                        "gap_type": "editorial",
                        "size": "editorial",
                        "original": content,
                        "full_match": full_match,
                        "start": start,
                        "end": end,
                        "filled": False,
                        "fill": None,
                        "explanation": None,
                        "confidence": None,
                    }
                )
            else:
                # Letter repair — keep unchanged
                parts.append(full_match)

            prev_end = end

        # Add remaining text after last gap
        parts.append(text[prev_end:])

        numbered = "".join(parts)
        lines.append(f"\u00b6{pnum}: {numbered}")

    return "\n\n".join(lines), gap_registry


def validate_fill(gap: dict, fill: str) -> tuple[bool, str]:
    """Validate a proposed fill against rules.

    Returns (accepted, reason_message).
    """
    # Rule: large gaps must not be filled
    if gap["size"] == "large":
        return (
            False,
            "Large gaps ([ ... ... ... ]) must not be restored per policy.",
        )

    # Rule: single-word gaps must be exactly one word
    if gap["size"] == "single":
        words = fill.strip().split()
        if len(words) != 1:
            return (
                False,
                f"Single-word gap requires exactly 1 word, got {len(words)}.",
            )

    # Rule: no leading punctuation
    if fill and fill[0] in ",.;:!?":
        return (
            False,
            f"Fill starts with punctuation '{fill[0]}'. "
            f"Punctuation belongs outside brackets.",
        )

    # Rule: no forward slash
    if "/" in fill:
        return False, "Fill contains forward slash (/)."

    # Rule: no page numbers
    if re.search(r"\(\d+\)", fill):
        return False, "Fill contains what looks like a page number."

    # Rule: fill must not be empty
    if not fill.strip():
        return False, "Empty fill. Skip the gap instead of submitting empty."

    return True, "Accepted."


def apply_fills_to_paragraph(
    original_text: str,
    para_gaps: list[dict],
) -> str:
    """Apply fills to a paragraph text, producing the reconstructed version.

    Filled gaps get [fill] (always square brackets in output).
    Unfilled gaps keep their original marker.
    """
    text = original_text
    # Sort by position descending (apply end-to-start to preserve positions)
    sorted_gaps = sorted(para_gaps, key=lambda g: g["start"], reverse=True)
    for gap in sorted_gaps:
        if gap["filled"] and gap["fill"]:
            # Always use square brackets for restored text
            replacement = f"[{gap['fill']}]"
        else:
            # Keep original gap marker
            replacement = gap["full_match"]
        text = text[: gap["start"]] + replacement + text[gap["end"] :]
    return text


def _stream_with_tools(
    client: AnthropicFoundry,
    deployment: str,
    messages: list[dict],
    ch_num: int,
    turn: int,
    *,
    debug: bool = False,
) -> tuple[list[tuple[str, str, dict]], str, str, list]:
    """Stream an API call with tools.

    Shows thinking output in real-time when debug=True.
    Uses get_final_message() for structured access to content blocks.

    Returns (tool_uses, text_output, stop_reason, content_for_history).
    - tool_uses: list of (tool_use_id, tool_name, parsed_input) tuples
    - text_output: concatenated text blocks
    - stop_reason: "end_turn" or "tool_use"
    - content_for_history: content blocks for assistant message in history
    """
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            thinking_chars = 0

            with client.messages.stream(
                model=deployment,
                system=_get_system_prompt(RESTORATION_PROMPT),
                messages=messages,
                tools=[RESTORE_LACUNA_TOOL],
                max_tokens=128_000,
                thinking={"type": "adaptive"},
            ) as stream:
                # Stream events for debug output (thinking)
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
                                f"\n  [thinking t{turn}] ",
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

                    elif etype == "content_block_stop":
                        if debug and thinking_chars:
                            # Only print once per thinking block
                            pass

                # Get the fully assembled message
                final_msg = stream.get_final_message()

            if debug and thinking_chars:
                print(f" [{thinking_chars} chars]", flush=True)

            # Extract tool uses and text from final message
            tool_uses: list[tuple[str, str, dict]] = []
            text_parts: list[str] = []

            for block in final_msg.content:
                btype = getattr(block, "type", "")
                if btype == "tool_use":
                    tool_uses.append(
                        (block.id, block.name, block.input)
                    )
                elif btype == "text":
                    text_parts.append(block.text)

            text_output = " ".join(text_parts).strip()

            # Build content for message history (serializable)
            content_for_history: list[dict] = []
            for block in final_msg.content:
                btype = getattr(block, "type", "")
                if btype == "text":
                    content_for_history.append(
                        {"type": "text", "text": block.text}
                    )
                elif btype == "tool_use":
                    content_for_history.append(
                        {
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        }
                    )
                elif btype == "thinking":
                    entry: dict = {
                        "type": "thinking",
                        "thinking": block.thinking,
                    }
                    if hasattr(block, "signature") and block.signature:
                        entry["signature"] = block.signature
                    content_for_history.append(entry)

            return (
                tool_uses,
                text_output,
                final_msg.stop_reason,
                content_for_history,
            )

        except Exception as e:
            err_str = str(e)
            if "rate" in err_str.lower() or "429" in err_str:
                wait = 60.0
                print(
                    f"\n  Rate limit Ch.{ch_num} t{turn}, "
                    f"waiting {wait:.0f}s..."
                )
                time.sleep(wait)
                continue
            elif "content_filter" in err_str.lower():
                print(
                    f"\n  Content filter Ch.{ch_num} t{turn}, "
                    f"attempt {attempt}/{max_retries}"
                )
                if attempt < max_retries:
                    time.sleep(attempt * 10)
                    continue
            elif attempt < max_retries:
                print(
                    f"\n  Error Ch.{ch_num} t{turn} "
                    f"attempt {attempt}/{max_retries}: "
                    f"{type(e).__name__}: {e}"
                )
                time.sleep(attempt * 5)
                continue
            else:
                print(
                    f"\n  FATAL Ch.{ch_num} t{turn}: "
                    f"{type(e).__name__}: {e}"
                )
                traceback.print_exc()
                raise

    # All retries exhausted
    return [], "", "error", []


def restore_chapter_with_tools(
    client: AnthropicFoundry,
    deployment: str,
    core_paras: list[dict],
    spiritual_reading: str,
    ch_num: int,
    *,
    original_text: str = "",
    debug: bool = False,
) -> list[dict] | None:
    """Restore lacunae via multi-turn tool-call conversation.

    Each lacuna is filled individually via the restore_lacuna tool.
    Fills are validated against rules. The model receives feedback
    and continues until all restorable gaps are processed.

    If *original_text* is provided, it is included as additional
    context for the model.

    Returns the gap_registry (list of gap dicts) or None on total failure.
    """
    # Number all gaps
    numbered_text, gap_registry = number_chapter_gaps(core_paras)

    total_gaps = len(gap_registry)
    if total_gaps == 0:
        return []

    # Count restorable vs large (will be skipped)
    n_large = sum(1 for g in gap_registry if g["size"] == "large")
    n_editorial = sum(1 for g in gap_registry if g["size"] == "editorial")
    n_restorable = total_gaps - n_large

    # Use project-appropriate unit label
    unit = "Section" if (
        PROJECT_CFG and PROJECT_CFG.document_type == "fragment_collection"
    ) else "Chapter"

    # Build first user message
    msg_lines = [
        f"Restore the lacunae in {unit} {ch_num}.",
        f"Total gaps: {total_gaps}.",
    ]
    if n_large:
        msg_lines.append(
            f"({n_large} are large gaps — skip these per policy, "
            f"do not call restore_lacuna for them.)"
        )
    if n_editorial:
        msg_lines.append(
            f"({n_editorial} are editorial reviews [GAP-N: REVIEW ...] — "
            f"confirm or correct the editor's word choice.)"
        )
    msg_lines.append(f"Restorable gaps: {n_restorable}.")
    msg_lines.append("")
    msg_lines.append("--- ORIGINAL TEXT (with numbered gaps) ---")
    msg_lines.append("")
    msg_lines.append(numbered_text)
    msg_lines.append("")
    # Include original-language text when available
    if original_text:
        lang = (
            PROJECT_CFG.language.replace("_", " ").title()
            if PROJECT_CFG else "Original"
        )
        msg_lines.append(f"--- ORIGINAL LANGUAGE ({lang} transliteration) ---")
        msg_lines.append("")
        msg_lines.append(original_text)
        msg_lines.append("")
    msg_lines.append("--- SPIRITUAL READING ---")
    msg_lines.append("")
    msg_lines.append(spiritual_reading)
    msg_lines.append("")
    msg_lines.append("--- END ---")
    msg_lines.append("")
    msg_lines.append(
        "Use the restore_lacuna tool for each gap you can fill. "
        "Work through all restorable gaps systematically. "
        "Skip any you cannot confidently restore."
    )

    messages: list[dict] = [
        {"role": "user", "content": "\n".join(msg_lines)}
    ]

    max_turns = 10

    for turn in range(max_turns):
        # --- API call with streaming ---
        try:
            tool_uses, text_output, stop_reason, assistant_content = (
                _stream_with_tools(
                    client, deployment, messages, ch_num, turn, debug=debug
                )
            )
        except Exception as e:
            print(f"\n  Ch.{ch_num} API failure on turn {turn}: {e}")
            return gap_registry if turn > 0 else None

        # Add assistant message to history
        messages.append({"role": "assistant", "content": assistant_content})

        if not tool_uses:
            # Model didn't make any tool calls — it's done
            if debug:
                print(
                    f"  Ch.{ch_num} t{turn}: "
                    f"no tool calls, model finished"
                )
                if text_output:
                    print(f"  Model said: {text_output[:200]}")
            break

        # Process each tool call
        tool_results: list[dict] = []
        n_accepted_this_turn = 0
        n_rejected_this_turn = 0
        rejection_notes: list[str] = []

        for tc_id, tc_name, tc_input in tool_uses:
            gap_id = tc_input.get("lacuna_id", "")
            fill = tc_input.get("fill", "")
            explanation = tc_input.get("explanation", "")
            confidence = tc_input.get("confidence", "moderate")

            # Find the gap in registry
            gap = next(
                (g for g in gap_registry if g["gap_id"] == gap_id), None
            )

            if gap is None:
                result_text = f"REJECTED: Unknown gap ID '{gap_id}'."
                n_rejected_this_turn += 1
                rejection_notes.append(f"  {gap_id}: unknown ID")
            elif gap["filled"]:
                result_text = f"REJECTED: {gap_id} was already filled."
                n_rejected_this_turn += 1
            else:
                accepted, reason = validate_fill(gap, fill)
                if accepted:
                    gap["filled"] = True
                    gap["fill"] = fill
                    gap["explanation"] = explanation
                    gap["confidence"] = confidence
                    result_text = (
                        f"ACCEPTED: {gap_id} filled."
                    )
                    n_accepted_this_turn += 1
                else:
                    result_text = f"REJECTED: {reason}"
                    n_rejected_this_turn += 1
                    rejection_notes.append(f"  {gap_id}: {reason}")

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tc_id,
                    "content": result_text,
                }
            )

        # Count overall progress
        n_filled = sum(1 for g in gap_registry if g["filled"])
        n_remaining = n_restorable - n_filled

        if debug:
            print(
                f"  Ch.{ch_num} t{turn}: "
                f"+{n_accepted_this_turn} accepted, "
                f"{n_rejected_this_turn} rejected | "
                f"{n_filled}/{n_restorable} total, "
                f"{n_remaining} remaining"
            )

        # Build follow-up user message
        progress_parts = [
            f"Turn {turn + 1}: {n_accepted_this_turn} accepted, "
            f"{n_rejected_this_turn} rejected.",
            f"Overall: {n_filled}/{n_restorable} restorable gaps filled, "
            f"{n_remaining} remaining.",
        ]
        if rejection_notes:
            progress_parts.append("Rejections this turn:")
            progress_parts.extend(rejection_notes)

        if n_remaining > 0:
            remaining_ids = [
                g["gap_id"]
                for g in gap_registry
                if not g["filled"] and g["size"] != "large"
            ]
            if len(remaining_ids) <= 30:
                progress_parts.append(
                    f"Remaining gaps: {', '.join(remaining_ids)}"
                )
            else:
                progress_parts.append(
                    f"Remaining: {len(remaining_ids)} gaps "
                    f"({remaining_ids[0]}...{remaining_ids[-1]})"
                )
            progress_parts.append(
                "If you can confidently fill more gaps, continue. "
                "Otherwise you are done — do not force low-confidence fills."
            )
        else:
            progress_parts.append("All restorable gaps processed. Done.")

        follow_up_content: list[dict] = tool_results + [
            {"type": "text", "text": "\n".join(progress_parts)}
        ]
        messages.append({"role": "user", "content": follow_up_content})

        # Check if done
        if n_remaining == 0:
            break
        if n_accepted_this_turn == 0:
            # Model made tool calls but none were new accepted fills
            # (all rejected or duplicates) — no progress, stop.
            if debug:
                print(
                    f"  Ch.{ch_num}: no new fills this turn, "
                    f"{n_remaining} gaps deliberately skipped"
                )
            break
        if stop_reason == "end_turn":
            if debug:
                print(
                    f"  Ch.{ch_num}: model ended turn with "
                    f"{n_remaining} gaps remaining"
                )
            break

    return gap_registry


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def fix_stray_brackets(text: str) -> str:
    """Remove unmatched brackets (both [] and {}) from text."""
    # Fix square brackets
    sq_stack: list[int] = []
    to_remove: set[int] = set()
    for i, ch in enumerate(text):
        if ch == "[":
            sq_stack.append(i)
        elif ch == "]":
            if sq_stack:
                sq_stack.pop()
            else:
                to_remove.add(i)
    to_remove.update(sq_stack)

    # Fix curly braces
    cu_stack: list[int] = []
    for i, ch in enumerate(text):
        if ch == "{":
            cu_stack.append(i)
        elif ch == "}":
            if cu_stack:
                cu_stack.pop()
            else:
                to_remove.add(i)
    to_remove.update(cu_stack)

    if not to_remove:
        return text
    return "".join(ch for i, ch in enumerate(text) if i not in to_remove)


# ---------------------------------------------------------------------------
# Save / Load
# ---------------------------------------------------------------------------


def save_result(
    ch_num: int,
    title: str,
    gap_registry: list[dict],
    core_paras: list[dict],
    lacunae_map: dict[int, list[dict]],
    total_lacunae: int,
    spiritual_reading: str | None = None,
) -> None:
    """Save restoration result as JSON.

    Builds reconstructions by applying fills from gap_registry to
    original paragraphs. No skeleton validation needed — we control
    the reconstruction directly.
    """
    CHAPTERS_OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = CHAPTERS_OUT_DIR / f"ch_{ch_num:03d}.json"

    lacunae_serial = {str(k): v for k, v in lacunae_map.items()}

    # Group gaps by paragraph
    gaps_by_para: dict[int, list[dict]] = {}
    for gap in gap_registry:
        pnum = gap["paragraph"]
        if pnum not in gaps_by_para:
            gaps_by_para[pnum] = []
        gaps_by_para[pnum].append(gap)

    # Build reconstructions
    all_reconstructions: list[dict] = []
    for p in core_paras:
        pnum = p["paragraph_number"]
        para_gaps = gaps_by_para.get(pnum, [])
        reconstructed = apply_fills_to_paragraph(p["core_text"], para_gaps)
        all_reconstructions.append(
            {
                "paragraph": pnum,
                "reconstructed_text": reconstructed,
            }
        )

    # Build fills list
    all_fills: list[dict] = []
    for gap in gap_registry:
        orig_stripped = gap["original"].strip()
        orig_is_gap = (
            orig_stripped in ("...", ". . .", "")
            or orig_stripped.replace(".", "")
            .replace("/", "")
            .replace(" ", "")
            .replace("(", "")
            .replace(")", "")
            .replace("0", "")
            .replace("1", "")
            .replace("2", "")
            .replace("3", "")
            .replace("4", "")
            .replace("5", "")
            .replace("6", "")
            .replace("7", "")
            .replace("8", "")
            .replace("9", "")
            == ""
        )

        fill_content = gap["fill"] if gap["filled"] else gap["original"]
        notes = ""
        if gap["gap_type"] == "editorial":
            if gap["filled"]:
                if gap["fill"].strip() == gap["original"].strip():
                    notes = "editorial confirmed"
                else:
                    notes = "editorial corrected"
            else:
                notes = "editorial unreviewed"
        elif not orig_is_gap:
            notes = "already filled by translator"
        elif not gap["filled"]:
            notes = "unfilled gap"
        elif gap["size"] == "large":
            notes = "large gap — skipped per policy"

        all_fills.append(
            {
                "paragraph": gap["paragraph"],
                "index": gap["gap_index"],
                "gap_id": gap["gap_id"],
                "fill": fill_content,
                "original": gap["original"],
                "gap_type": gap["gap_type"],
                "gap_size": gap["size"],
                "explanation": gap.get("explanation") or "",
                "confidence": gap.get("confidence") or "",
                "notes": notes,
            }
        )

    # Categorize for assessment
    n_restored = sum(
        1 for f in all_fills
        if f["notes"] == "" and f["fill"] != f["original"]
    )
    n_already = sum(
        1 for f in all_fills if f["notes"] == "already filled by translator"
    )
    n_unfilled = sum(1 for f in all_fills if f["notes"] == "unfilled gap")
    n_large_skipped = sum(
        1
        for f in all_fills
        if f["notes"] == "large gap — skipped per policy"
    )
    n_editorial_confirmed = sum(
        1 for f in all_fills if f["notes"] == "editorial confirmed"
    )
    n_editorial_corrected = sum(
        1 for f in all_fills if f["notes"] == "editorial corrected"
    )
    n_editorial_unreviewed = sum(
        1 for f in all_fills if f["notes"] == "editorial unreviewed"
    )

    parts = [f"{n_restored} restored"]
    if n_already:
        parts.append(f"{n_already} already filled")
    if n_editorial_confirmed or n_editorial_corrected:
        parts.append(
            f"{n_editorial_confirmed + n_editorial_corrected} editorial reviewed "
            f"({n_editorial_confirmed} confirmed, {n_editorial_corrected} corrected)"
        )
    if n_editorial_unreviewed:
        parts.append(f"{n_editorial_unreviewed} editorial unreviewed")
    if n_unfilled:
        parts.append(f"{n_unfilled} unfilled gaps")
    if n_large_skipped:
        parts.append(f"{n_large_skipped} large (skipped)")
    assessment = ", ".join(parts)

    data = {
        "chapter_number": ch_num,
        "chapter_title": title,
        "total_lacunae": total_lacunae,
        "lacunae_map": lacunae_serial,
        "spiritual_reading": spiritual_reading,
        "reconstructions": all_reconstructions,
        "fills": all_fills,
        "violations": [],  # No violations — fills are validated individually
        "assessment": assessment,
    }

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

    # Project-aware header
    if PROJECT_CFG and PROJECT_CFG.document_type == "fragment_collection":
        unit_label = "Section"
        proj_name = PROJECT_CFG.display_name
        lines.append(f"# {proj_name} \u2014 Correspondential Reading")
        lines.append("")
        lines.append(
            f"*{proj_name} ({PROJECT_CFG.edition}) with lacunae*"
        )
    else:
        unit_label = "Chapter"
        lines.append("# The Kephalaia Teaching Core \u2014 Restored Text")
        lines.append("")
        lines.append(
            "*The oldest teaching layer of the Kephalaia with lacunae*"
        )
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

        title = core_ch.get("chapter_title", f"{unit_label} {ch_num}")
        lines.append(f"## {unit_label} {ch_num}: {title}")
        lines.append("")

        # Build lookup
        recon_by_para: dict[int, str] = {}
        fills_by_para: dict[int, list[dict]] = {}
        if rest_ch:
            for recon in rest_ch.get("reconstructions", []):
                recon_by_para[recon["paragraph"]] = recon[
                    "reconstructed_text"
                ]
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
                lines.append(f"**\u00b6{pnum}** {restored}")
                lines.append("")

                # Count fills
                para_fills = fills_by_para.get(pnum, [])
                for f in para_fills:
                    fill_val = f.get("fill", "...").strip()
                    orig_val = f.get("original", "").strip()
                    notes = f.get("notes", "")
                    if notes == "unfilled gap":
                        total_unrestorable += 1
                    elif notes == "" and fill_val != orig_val:
                        total_fills += 1
            else:
                lines.append(f"**\u00b6{pnum}** {core_text}")
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
        description="Correspondential restoration of a Manichaean "
        "teaching core"
    )
    parser.add_argument(
        "--project",
        "-p",
        type=str,
        default="kephalaia",
        help=f"Project to process (available: {', '.join(list_projects()) or 'none'})",
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
    configure_paths(args.project)

    # Load extracted core chapters
    all_chapters = load_core_chapters()
    if not all_chapters:
        print("ERROR: No extracted core chapters found in", CORE_CHAPTERS_DIR)
        print("  Run stage_4_extract.py first.")
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
            print(f"ERROR: Chapter {args.chapter} not found")
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
            f"  Ch.{num:3d}  ({len(core_paras):3d} core \u00b6s, "
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
        orig_text = ch.get("original_text", "")

        core_paras = extract_core_paragraphs(ch)
        lacunae_map, total_lacunae = find_lacunae(core_paras)

        if total_lacunae == 0:
            with print_lock:
                counter["done"] += 1
                print(
                    f"[{counter['done']}/{total_to_process}] "
                    f"Ch.{ch_num} \u2014 no lacunae, skip"
                )
            return

        with print_lock:
            print(
                f"  Ch.{ch_num} ({total_lacunae} lacunae) "
                f"{title}...",
                end="",
                flush=True,
            )

        # --- Number gaps (shared by Phase 1 and 2) ---
        numbered_text, gap_registry_pre = number_chapter_gaps(core_paras)

        # --- Phase 1: Spiritual Reading (use cache if available) ---
        cached_path = CHAPTERS_OUT_DIR / f"ch_{ch_num:03d}.json"
        cached_reading = None
        if cached_path.exists():
            try:
                with open(cached_path, encoding="utf-8") as f:
                    cached_data = json.load(f)
                cached_sr = cached_data.get("spiritual_reading", "")
                # Only use cache if it contains GAP anchors
                if cached_sr and "GAP-" in cached_sr:
                    cached_reading = cached_sr
            except Exception:
                pass

        if cached_reading:
            spiritual_reading = cached_reading
            with print_lock:
                print(" [cached reading]", end="", flush=True)
        else:
            with print_lock:
                print(" phase 1...", end="", flush=True)
            spiritual_reading = generate_spiritual_reading(
                client, deployment, numbered_text, ch_num,
                original_text=orig_text, debug=show_debug
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
            print(" phase 2 (tool-calls)...", end="", flush=True)

        # --- Phase 2: Tool-Call Restoration ---
        gap_registry = restore_chapter_with_tools(
            client,
            deployment,
            core_paras,
            spiritual_reading,
            ch_num,
            original_text=orig_text,
            debug=show_debug,
        )
        if gap_registry is None:
            with print_lock:
                counter["done"] += 1
                errors_list.append(ch_num)
                print(
                    f"\n[{counter['done']}/{total_to_process}] "
                    f"Ch.{ch_num} FAILED (restoration)"
                )
            return

        # Count stats
        n_restorable = sum(
            1 for g in gap_registry if g["size"] != "large"
        )
        n_filled = sum(1 for g in gap_registry if g["filled"])
        n_high = sum(
            1 for g in gap_registry
            if g["filled"] and g["confidence"] == "high"
        )
        n_mod = sum(
            1 for g in gap_registry
            if g["filled"] and g["confidence"] == "moderate"
        )
        n_low = sum(
            1 for g in gap_registry
            if g["filled"] and g["confidence"] == "low"
        )
        n_large = sum(1 for g in gap_registry if g["size"] == "large")

        # --- Save ---
        save_result(
            ch_num,
            title,
            gap_registry,
            core_paras,
            lacunae_map,
            total_lacunae,
            spiritual_reading=spiritual_reading,
        )

        status = f"OK \u2014 {n_filled}/{n_restorable} gaps restored"
        if n_large:
            status += f", {n_large} large skipped"
        confidence_parts = []
        if n_high:
            confidence_parts.append(f"{n_high}H")
        if n_mod:
            confidence_parts.append(f"{n_mod}M")
        if n_low:
            confidence_parts.append(f"{n_low}L")
        if confidence_parts:
            status += f" ({'/'.join(confidence_parts)})"

        with print_lock:
            counter["done"] += 1
            results_list.append(ch_num)
            print(
                f"\n[{counter['done']}/{total_to_process}] "
                f"Ch.{ch_num} {status}"
            )

    # --- Execute ---
    if concurrency == 1:
        for ch in chapters:
            process_one(ch)
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {
                executor.submit(process_one, ch): ch for ch in chapters
            }
            for future in as_completed(futures):
                exc = future.exception()
                if exc:
                    ch = futures[future]
                    with print_lock:
                        print(
                            f"  Ch.{ch['chapter_number']} "
                            f"EXCEPTION: {exc}"
                        )
                        errors_list.append(ch["chapter_number"])

    # Summary
    print(f"\n{'=' * 60}")
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
