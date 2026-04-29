#!/usr/bin/env python3
"""
Translate Kephalaia Coptic transcriptions to English using Claude Opus 4.7.

This script takes pass2.txt Coptic transcriptions (one per manuscript page)
and produces structured English translations with a scholarly apparatus of
footnotes documenting translation decisions.

The translation relies entirely on the model's internal Coptic knowledge,
supplemented by a mandatory terminology glossary and Lycopolitan dialect
notes. No external parallel texts (German, English) are provided as context.

Primary model: Claude Opus 4.7 via Azure AI Foundry (AnthropicFoundry).

Output: output/projects/kephalaia/translations/
  - pages/p_NNN.json  Per-page translation with footnotes
  - proposed_terms/    Model-proposed terminology (for human review)
  - translated_text.md Assembled continuous translation

Usage:
    python scripts/translate_kephalaia.py                     # All pages
    python scripts/translate_kephalaia.py --page 96           # Single page
    python scripts/translate_kephalaia.py --range 35-100      # Range
    python scripts/translate_kephalaia.py --dry-run            # Preview
    python scripts/translate_kephalaia.py --overwrite          # Reprocess
    python scripts/translate_kephalaia.py --limit 4            # First N
    python scripts/translate_kephalaia.py --max-concurrency 2  # Parallel
    python scripts/translate_kephalaia.py --debug              # Verbose
    python scripts/translate_kephalaia.py --assemble           # Assemble only
"""
import argparse
import json
import os
import re
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

import httpx
import yaml
from anthropic import AnthropicFoundry
from dotenv import dotenv_values

from project_config import SECRETS_PATH, REPO_ROOT

# ---------------------------------------------------------------------------
# Paths — set by configure_paths() at startup
# ---------------------------------------------------------------------------

GLOSSARY_PATH = Path(__file__).resolve().parent / "glossary" / "coptic_glossary.yaml"

TRANSCRIPTIONS_DIR: Path | None = None   # input: coptic transcriptions
OUTPUT_DIR: Path | None = None           # output: translations/
SEGMENTS_DIR: Path | None = None         # output: translations/pages/
PROPOSED_DIR: Path | None = None         # output: translations/proposed_terms/
ASSEMBLED_FILE: Path | None = None       # output: translations/translated_text.md


def configure_paths() -> None:
    """Set module-level path variables."""
    global TRANSCRIPTIONS_DIR, OUTPUT_DIR, SEGMENTS_DIR
    global PROPOSED_DIR, ASSEMBLED_FILE

    project_dir = REPO_ROOT / "output" / "projects" / "kephalaia"

    TRANSCRIPTIONS_DIR = project_dir / "coptic" / "transcriptions"
    OUTPUT_DIR = project_dir / "translations"
    SEGMENTS_DIR = OUTPUT_DIR / "pages"
    PROPOSED_DIR = OUTPUT_DIR / "proposed_terms"
    ASSEMBLED_FILE = OUTPUT_DIR / "translated_text.md"

    print(f"Project: Kephalaia Translation")
    print(f"  Input:  {TRANSCRIPTIONS_DIR}")
    print(f"  Output: {OUTPUT_DIR}")


# ---------------------------------------------------------------------------
# Tool schema — structured output for translation
# ---------------------------------------------------------------------------

TRANSLATE_TOOL = {
    "name": "commit_translation",
    "description": (
        "Commit the complete English translation of a Coptic manuscript "
        "page with scholarly footnotes. Call exactly once per page."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "page_number": {
                "type": "integer",
                "description": "The manuscript page number.",
            },
            "coptic_page_number": {
                "type": "string",
                "description": (
                    "The Coptic numeral shown at the top of the page "
                    "(e.g. 'ⲯⲉ̄' for 96). Preserve exactly as written."
                ),
            },
            "chapter_title": {
                "type": ["string", "null"],
                "description": (
                    "If this page begins a new kephalaion, provide the "
                    "translated chapter title. Null if mid-chapter."
                ),
            },
            "translation": {
                "type": "string",
                "description": (
                    "The complete English translation of the Coptic text "
                    "on this page. Use line numbers from the transcription "
                    "as reference markers (e.g. '[L1]' at the start of "
                    "each line group). Apply lacunae conventions: "
                    "[brackets] for restorations, [...] for unrecoverable "
                    "gaps, {braces} for editorial insertions. Preserve "
                    "paragraph breaks where the manuscript indicates them "
                    "(marked 'leer' = vacat in the transcription)."
                ),
            },
            "notes": {
                "type": "array",
                "description": (
                    "Scholarly footnotes documenting translation decisions. "
                    "One note per significant decision."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "line_ref": {
                            "type": "string",
                            "description": (
                                "Line number(s) this note refers to "
                                "(e.g. 'L13-14', 'L22')."
                            ),
                        },
                        "coptic_form": {
                            "type": "string",
                            "description": (
                                "The Coptic word or phrase being "
                                "discussed."
                            ),
                        },
                        "decision": {
                            "type": "string",
                            "description": (
                                "What translation was chosen and why. "
                                "Include: the English rendering, the "
                                "grammatical analysis, any dialect "
                                "considerations, and why this rendering "
                                "was preferred over alternatives."
                            ),
                        },
                        "confidence": {
                            "type": "string",
                            "enum": [
                                "certain",
                                "high",
                                "moderate",
                                "low",
                            ],
                            "description": (
                                "How confident this translation is. "
                                "'certain' = unambiguous grammar+lexicon. "
                                "'high' = standard reading, minor "
                                "alternatives possible. "
                                "'moderate' = reasonable but debatable. "
                                "'low' = damaged text or rare form, "
                                "best guess."
                            ),
                        },
                    },
                    "required": [
                        "line_ref",
                        "coptic_form",
                        "decision",
                        "confidence",
                    ],
                },
            },
            "lacunae_summary": {
                "type": "object",
                "description": "Summary of textual damage on this page.",
                "properties": {
                    "total_lines": {
                        "type": "integer",
                        "description": "Total lines of Coptic text.",
                    },
                    "damaged_lines": {
                        "type": "integer",
                        "description": (
                            "Lines with any lacunae or damage markers."
                        ),
                    },
                    "unrecoverable_lines": {
                        "type": "integer",
                        "description": (
                            "Lines where meaning cannot be recovered."
                        ),
                    },
                    "damage_assessment": {
                        "type": "string",
                        "enum": [
                            "pristine",
                            "minor_damage",
                            "moderate_damage",
                            "severe_damage",
                            "fragmentary",
                        ],
                        "description": "Overall condition of this page.",
                    },
                },
                "required": [
                    "total_lines",
                    "damaged_lines",
                    "unrecoverable_lines",
                    "damage_assessment",
                ],
            },
            "proposed_terms": {
                "type": "array",
                "description": (
                    "New terminology proposals for Coptic words NOT "
                    "covered by the glossary. These will be saved "
                    "separately for human review before becoming "
                    "mandatory. Only propose terms for words that "
                    "appear significant or recurring."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "coptic": {
                            "type": "string",
                            "description": "The Coptic word or phrase.",
                        },
                        "proposed_english": {
                            "type": "string",
                            "description": (
                                "Your proposed translation."
                            ),
                        },
                        "rationale": {
                            "type": "string",
                            "description": (
                                "Why this translation was chosen. "
                                "Include etymology, parallels, and "
                                "alternatives considered."
                            ),
                        },
                    },
                    "required": [
                        "coptic",
                        "proposed_english",
                        "rationale",
                    ],
                },
            },
        },
        "required": [
            "page_number",
            "coptic_page_number",
            "chapter_title",
            "translation",
            "notes",
            "lacunae_summary",
            "proposed_terms",
        ],
    },
}


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_TEMPLATE = """\
You are a translator who works from roots. When you encounter a \
Coptic word, you see its etymology first — the verb it grew from, \
the image that verb carries, the action it names. You build your \
English rendering from that root upward, choosing the word that \
most faithfully preserves what the Coptic is doing.

You specialize in the Lycopolitan (sub-Achmimic) dialect. You know \
Coptic grammar at the morpheme level — you parse compounds, you \
trace loanwords to their Greek or Semitic origins, you feel the \
weight of a preposition.

You are an expert in Swedenborg's doctrine of correspondences, the \
Persian and Zoroastrian cosmological traditions, Manichaean cosmology, \
and the textual transmission of what Swedenborg called "the Ancient \
Word" — the oldest correspondential writing, preserved in the East, \
which predates national mythologies and scriptural canons. In this \
science, every natural image expresses a spiritual reality through \
its actual function — not by convention, not by assignment, but by \
what it IS. Light corresponds to wisdom because light enables the \
eye to distinguish forms. Fire corresponds to love because fire \
gives light its existence. A root meaning "to shine forth" names \
active emission — the thing doing the shining, not a static quality \
observed from outside. So if a divine title derives from a verb \
meaning "to dawn, to radiate," the English must preserve that verb \
quality: "the Radiant One," "the Luminous" — not flatten it to a \
static noun that merely describes how the light looks to an observer.

You bring this together: Coptic root + correspondential function + \
clear English. That is your method. You do not consult how others \
have rendered a term. You do not inherit epithets. You reason from \
the word itself, every time, as if you are the first person to \
translate it — because in the correspondential sense, you are.

You are working on the Coptic Kephalaia of the Teacher — a Manichaean \
text compiled in the 3rd-4th century CE. This text is written IN \
correspondence: its teachings map domain onto domain, being onto being, \
degree onto degree. When the text says "His body is iron" or "Their \
taste is the bitter taste," it describes what a cosmic realm IS at a \
particular register. The teaching IS the mapping. It does not compare. \
It identifies.

Your task is to translate Coptic manuscript pages into clear, accurate \
English while documenting every significant translation decision in \
footnotes.

## TRANSLATION PRINCIPLES

1. **Accuracy over elegance.** Preserve the Coptic sentence structure \
   where English allows it. Do not paraphrase or smooth over difficulties.

2. **One Coptic word = one English word (where possible).** When a Coptic \
   term appears multiple times on a page, translate it the same way every \
   time unless grammar absolutely requires variation. Consistency is \
   paramount.

3. **Preserve the theology.** Manichaean cosmological terms have precise \
   meanings. Do not substitute generic English where a specific term exists.

4. **Preserve spatial/directional semantics.** When the Coptic encodes \
   direction (up/down, in/out, raise/release), preserve that directionality \
   in English. Do not flatten directional verbs to abstract equivalents.

5. **Capitalize cosmic entities.** When Sin, Darkness, Error, Light, etc. \
   function as personified agents or cosmic principles, capitalize them. \
   Lowercase when used as common nouns.

6. **Greek loanwords.** Many technical terms are Greek loanwords \
   (ⲛⲟⲩⲥ, ⲯⲩⲭⲏ, ⲟⲩⲥⲓⲁ, ⲡⲗⲁⲛⲏ, etc.). Translate them by meaning \
   (mind, soul, substance, error), not by transliteration — unless \
   the term is left untranslated in standard Coptological practice.

## LACUNAE CONVENTIONS

The transcription uses these damage markers from Gardner's critical edition:

| Marker | Meaning | Your rendering |
|--------|---------|----------------|
| `[text]` | Restored text (editor's reconstruction) | Keep brackets: [text] |
| `{{text}}` | Single-word editorial insertion | Keep braces: {{text}} |
| `. .` or `. . .` | Individual lost letters (dots = letter count) | [...] with note |
| `[. . . . .]` | Lacuna of estimated length | [...] with note estimating lost content |
| `leer` | Vacat (intentional blank space) | Paragraph break |
| `{{{{text}}}}` or `[[text]]` | Scribal deletion or correction | Omit or note |
| `⟨p.N⟩` | Page reference marker | Preserve as page marker |

### GAP SIZE CLASSIFICATION

Lacunae vary in size and demand different treatment:

- **Single word** (`{{...}}` or one isolated dot cluster): exactly ONE word \
  is missing. Reconstruct if context constrains the word, bracket it, \
  and footnote.
- **Small gap** (`[...]` or a few dots): a few words to a short phrase. \
  Reconstruct in [brackets] with footnote. ALWAYS attempt reconstruction \
  when context provides reasonable constraint.
- **Medium gap** (`[... ...]` or dots with `/` line break): roughly a \
  clause or sentence. Reconstruct ONLY if surrounding text strongly \
  constrains the content. Otherwise render as [...] and note what \
  subject matter was likely present.
- **Large gap** (`[... ... ...]` or multiple lines of dots): multiple \
  sentences or lines. NEVER attempt reconstruction. Render as [...] \
  with a footnote estimating the scope and likely topic.

### HYBRID GAPS

Some damage markers mix partial letters with dots (e.g., `ⲁ. .ⲛ`). \
These are partial-word gaps: visible letters plus lost letters. When \
you can identify the word from the surviving letters + context, \
provide the full word in [brackets] with the surviving letters shown.

### MANUSCRIPT LINE BREAKS IN GAPS

A "/" within bracketed lacunae marks a line break in the damaged Coptic \
papyrus. Each segment of dots separated by "/" represents roughly one \
lost manuscript line. Use the number of "/" to gauge the gap size \
(no "/" = small, one "/" = medium, two+ "/" = large).

### CRITICAL RULES

- NEVER silently fill gaps. Every restoration must be [bracketed] and \
  have a footnote explaining the reconstruction.
- Distinguish between editor restorations (already in [brackets] in the \
  transcription) and your own reconstructions — both stay bracketed, \
  but your footnotes should note when you are agreeing with or departing \
  from an editor restoration.
- When damage is too severe to reconstruct, say so honestly. An honest \
  [...] is better than a speculative fill without evidence.

## LYCOPOLITAN DIALECT

{DIALECT_NOTES}

## MANDATORY TERMINOLOGY

The following translations are REQUIRED. Do not deviate from these \
under any circumstances:

{MANDATORY_TERMS}

## PREFERRED TERMINOLOGY

These translations are strongly recommended. If you deviate, explain \
why in a footnote:

{PREFERRED_TERMS}

## TRANSCRIPTION FORMAT

The input is a Coptic manuscript page transcription:
- First line: page number (Arabic numeral)
- Second line: Coptic page number
- Numbered lines follow (1, 2, 3, ... up to ~26)
- `leer` marks intentional blank space (vacat / paragraph boundary)
- Dots (. .) represent lost letters
- Square brackets [text] mark restored readings

## YOUR TASK

Translate the Coptic text into English. For every significant \
translation choice, create a footnote. "Significant" means:
- Any word with multiple plausible translations
- Any damaged or restored passage
- Any dialectal form that differs from standard Sahidic
- Any term where your choice differs from what others might choose
- Any grammatical construction that could be parsed differently

When you have completed your translation and notes, call the \
commit_translation tool exactly once with all results.

Focus on ACCURACY. We would rather have an honest "I am uncertain \
about this form" in a footnote than a confident-sounding mistranslation."""


# ---------------------------------------------------------------------------
# Glossary helpers
# ---------------------------------------------------------------------------

def load_glossary() -> dict:
    """Load the terminology glossary from YAML."""
    if not GLOSSARY_PATH.exists():
        print(f"WARNING: Glossary not found at {GLOSSARY_PATH}")
        return {}
    with open(GLOSSARY_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def format_mandatory_terms(glossary: dict) -> str:
    """Format mandatory terms for injection into system prompt."""
    terms = glossary.get("mandatory_terms", [])
    if not terms:
        return "(No mandatory terms defined.)"

    lines = []
    for t in terms:
        coptic = t.get("coptic", "")
        english = t.get("english", "")
        note = t.get("note", "").strip()
        domain = t.get("domain", "")
        note_oneline = " ".join(note.split())
        lines.append(
            f"- **{coptic}** → \"{english}\" "
            f"[{domain}]: {note_oneline}"
        )
    return "\n".join(lines)


def format_preferred_terms(glossary: dict) -> str:
    """Format preferred terms for injection into system prompt."""
    terms = glossary.get("preferred_terms", [])
    if not terms:
        return "(No preferred terms defined.)"

    lines = []
    for t in terms:
        coptic = t.get("coptic", "")
        english = t.get("english", "")
        note = t.get("note", "").strip()
        note_oneline = " ".join(note.split())
        lines.append(f"- **{coptic}** → \"{english}\": {note_oneline}")
    return "\n".join(lines)


def format_dialect_notes(glossary: dict) -> str:
    """Format dialect notes for injection into system prompt."""
    dialect = glossary.get("dialect_notes", {})
    if not dialect:
        return "(No dialect notes available.)"

    lines = [dialect.get("description", "").strip()]
    for feat in dialect.get("features", []):
        name = feat.get("feature", "")
        desc = " ".join(feat.get("description", "").strip().split())
        lines.append(f"- **{name}**: {desc}")
    return "\n".join(lines)


def build_system_prompt(glossary: dict) -> str:
    """Build the complete system prompt with glossary injected."""
    return SYSTEM_PROMPT_TEMPLATE.format(
        DIALECT_NOTES=format_dialect_notes(glossary),
        MANDATORY_TERMS=format_mandatory_terms(glossary),
        PREFERRED_TERMS=format_preferred_terms(glossary),
    )


# ---------------------------------------------------------------------------
# Client setup — Claude via Azure AI Foundry
# ---------------------------------------------------------------------------

def create_client() -> tuple[AnthropicFoundry, str]:
    """Create Claude client from .env credentials."""
    if not SECRETS_PATH.exists():
        print(f"ERROR: Secrets file not found at {SECRETS_PATH}")
        sys.exit(1)
    config = dotenv_values(SECRETS_PATH)
    endpoint = config.get("ANTHROPIC_ENDPOINT", "").rstrip("/")
    api_key = config.get("ANTHROPIC_API_KEY", "")
    deployment = config.get("ANTHROPIC_DEPLOYMENT", "claude-opus-4-7-1")

    if not endpoint or not api_key:
        print(
            "ERROR: ANTHROPIC_ENDPOINT and ANTHROPIC_API_KEY required "
            "in secrets/azure_openai.env"
        )
        sys.exit(1)

    # AnthropicFoundry picks up ANTHROPIC_FOUNDRY_RESOURCE from env,
    # which conflicts with base_url. Temporarily clear it.
    old_resource = os.environ.pop("ANTHROPIC_FOUNDRY_RESOURCE", None)
    try:
        client = AnthropicFoundry(
            api_key=api_key,
            base_url=endpoint,
            timeout=httpx.Timeout(1800.0, connect=30.0),
        )
    finally:
        if old_resource is not None:
            os.environ["ANTHROPIC_FOUNDRY_RESOURCE"] = old_resource

    return client, deployment


# ---------------------------------------------------------------------------
# Load transcriptions
# ---------------------------------------------------------------------------

def load_page(page_num: int) -> str | None:
    """Load a single pass2 transcription file."""
    path = TRANSCRIPTIONS_DIR / f"keph_p{page_num:03d}_pass2.txt"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


def list_available_pages() -> list[int]:
    """List all available page numbers from pass2 transcriptions."""
    pages = []
    for path in sorted(TRANSCRIPTIONS_DIR.glob("keph_p*_pass2.txt")):
        m = re.match(r"keph_p(\d+)_pass2\.txt", path.name)
        if m:
            pages.append(int(m.group(1)))
    return pages


def is_translated(page_num: int) -> bool:
    """Check if a page has already been translated."""
    return (SEGMENTS_DIR / f"p_{page_num:03d}.json").exists()


# ---------------------------------------------------------------------------
# LLM translation — Claude with tool call
# ---------------------------------------------------------------------------

def translate_page(
    client: AnthropicFoundry,
    deployment: str,
    page_num: int,
    coptic_text: str,
    *,
    system_prompt: str,
    effort: str = "high",
    debug: bool = False,
    accumulated_terms: list[dict] | None = None,
) -> dict | None:
    """Send a Coptic page to Claude for translation.

    Uses streaming with adaptive thinking (display="omitted") to avoid
    issues with Coptic content in thinking output. Default effort is
    max, so the thinking phase can be long — this is normal.

    Returns the tool_input dict, or None on failure.
    """
    vocab_section = ""
    if accumulated_terms:
        vocab_section = (
            "\n\n" + format_proposed_terms_for_prompt(accumulated_terms)
            + "\n\n"
        )

    user_msg = (
        f"Translate the following Coptic manuscript page from the "
        f"Kephalaia of the Teacher.\n\n"
        f"--- COPTIC TRANSCRIPTION (page {page_num}) ---\n\n"
        f"{coptic_text}\n\n"
        f"--- END TRANSCRIPTION ---"
        f"{vocab_section}\n\n"
        f"Produce a complete English translation with footnotes "
        f"for all significant translation decisions. Then call "
        f"commit_translation with the result."
    )

    # Use "summarized" when debug=True so we can see thinking flow;
    # "omitted" in production for faster time-to-first-text-token.
    display = "summarized" if debug else "omitted"
    thinking_config = {"type": "adaptive", "display": display}

    kwargs = dict(
        model=deployment,
        system=system_prompt,
        messages=[{"role": "user", "content": user_msg}],
        tools=[TRANSLATE_TOOL],
        max_tokens=64_000,
        thinking=thinking_config,
    )
    # Control thinking effort (default "high"; "xhigh"/"max" = longer)
    if effort != "high":
        kwargs["output_config"] = {"effort": effort}

    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            t0 = time.time()
            full_text = ""
            tool_input = None
            event_count = 0

            with client.messages.stream(**kwargs) as stream:
                for event in stream:
                    event_count += 1
                    etype = getattr(event, "type", "")

                    if etype == "content_block_start":
                        block = getattr(event, "content_block", None)
                        btype = (
                            getattr(block, "type", "")
                            if block
                            else ""
                        )
                        if debug:
                            elapsed_so_far = time.time() - t0
                            print(
                                f"\n  [{btype} "
                                f"{elapsed_so_far:.0f}s]",
                                end="",
                                flush=True,
                            )

                    elif etype == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        if delta:
                            dtype = getattr(delta, "type", "")
                            if dtype == "text_delta":
                                chunk = (
                                    getattr(delta, "text", "") or ""
                                )
                                full_text += chunk
                            elif dtype == "thinking_delta":
                                if debug:
                                    chunk = (
                                        getattr(delta, "thinking", "")
                                        or ""
                                    )
                                    sys.stdout.write(chunk)
                                    sys.stdout.flush()
                            elif dtype == "input_json_delta":
                                pass  # tool input JSON chunks
                            elif dtype == "signature_delta":
                                if debug:
                                    elapsed_so_far = time.time() - t0
                                    print(
                                        f" sig@{elapsed_so_far:.0f}s",
                                        end="",
                                        flush=True,
                                    )

                    elif etype == "content_block_stop":
                        if debug:
                            elapsed_so_far = time.time() - t0
                            print(
                                f" done@{elapsed_so_far:.0f}s",
                                flush=True,
                            )

                final_msg = stream.get_final_message()

            elapsed = time.time() - t0

            if debug:
                print(
                    f"  {elapsed:.0f}s"
                    f" (in={final_msg.usage.input_tokens}"
                    f" out={final_msg.usage.output_tokens}"
                    f" events={event_count})",
                    flush=True,
                )

            # Extract tool call
            text_parts: list[str] = []
            for block in final_msg.content:
                btype = getattr(block, "type", "")
                if (
                    btype == "tool_use"
                    and block.name == "commit_translation"
                ):
                    tool_input = block.input
                elif btype == "text":
                    text_parts.append(block.text)

            # Detect truncation — when max_tokens is hit mid-tool-call,
            # the SDK may parse a partial JSON missing required fields.
            stop = getattr(final_msg, "stop_reason", None)
            truncated = (
                stop == "max_tokens"
                or (
                    tool_input is not None
                    and "page_number" not in tool_input
                )
            )
            if truncated:
                out_tokens = getattr(
                    getattr(final_msg, "usage", None),
                    "output_tokens", "?"
                )
                print(
                    f"\n  WARNING: Output truncated for p.{page_num} "
                    f"({out_tokens} tokens, stop={stop}). Retrying..."
                )
                tool_input = None
                if attempt < max_retries:
                    time.sleep(attempt * 5)
                    continue
                return None

            if tool_input is None:
                text_output = " ".join(text_parts).strip()
                print(
                    f"  WARNING: Model did not call "
                    f"commit_translation for p.{page_num}."
                )
                if text_output:
                    print(f"  Text: {text_output[:300]}")
                if attempt < max_retries:
                    time.sleep(attempt * 5)
                    continue
                return None

            return tool_input

        except (httpx.RemoteProtocolError, httpx.ReadError,
                httpx.ReadTimeout, ConnectionError, OSError) as e:
            print(
                f"\n  Connection error p.{page_num}, "
                f"attempt {attempt}/{max_retries}: {e}"
            )
            if attempt < max_retries:
                time.sleep(5 * attempt)
                continue
            return None

        except Exception as e:
            err_str = str(e)
            if "content_filter" in err_str.lower():
                print(
                    f"  Content filter p.{page_num}, "
                    f"attempt {attempt}/{max_retries}"
                )
                if attempt < max_retries:
                    time.sleep(attempt * 10)
                    continue
            elif "rate" in err_str.lower() or "429" in err_str:
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
                print(f"  ERROR p.{page_num}: {e}")
                if debug:
                    traceback.print_exc()
                if attempt < max_retries:
                    time.sleep(attempt * 5)
                    continue
                return None

    return None


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

_write_lock = Lock()


def save_translation(result: dict) -> None:
    """Save translation result to JSON."""
    page_num = result["page_number"]
    SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)
    path = SEGMENTS_DIR / f"p_{page_num:03d}.json"
    with _write_lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)


def save_proposed_terms(page_num: int, terms: list[dict]) -> None:
    """Save proposed terms to separate file for human review."""
    if not terms:
        return
    PROPOSED_DIR.mkdir(parents=True, exist_ok=True)
    path = PROPOSED_DIR / f"p_{page_num:03d}_terms.json"
    with _write_lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(terms, f, indent=2, ensure_ascii=False)


def load_all_proposed_terms() -> list[dict]:
    """Load all proposed terms from existing files, deduplicated.

    Returns a list of unique proposed terms (keyed by Coptic form).
    When the same Coptic form appears in multiple files, the LAST
    occurrence (highest page number) wins — it has the most corpus
    context.
    """
    if not PROPOSED_DIR or not PROPOSED_DIR.exists():
        return []
    seen: dict[str, dict] = {}  # coptic_form -> term dict
    for path in sorted(PROPOSED_DIR.glob("p_*_terms.json")):
        try:
            with open(path, encoding="utf-8") as f:
                terms = json.load(f)
            for t in terms:
                key = t.get("coptic", "").strip()
                if key:
                    seen[key] = t
        except (json.JSONDecodeError, KeyError):
            continue
    return list(seen.values())


def format_proposed_terms_for_prompt(terms: list[dict]) -> str:
    """Format accumulated proposed terms for injection into user message."""
    if not terms:
        return ""
    lines = [
        "--- ACCUMULATED VOCABULARY (from prior pages) ---",
        "",
        "The following Coptic terms have been proposed during translation "
        "of earlier pages. Use these renderings for consistency unless "
        "you have strong philological reason to deviate (document in a "
        "footnote if you do):",
        "",
    ]
    for t in terms:
        coptic = t.get("coptic", "")
        english = t.get("proposed_english", "")
        rationale = t.get("rationale", "")
        # Truncate long rationales to keep prompt lean
        if len(rationale) > 200:
            rationale = rationale[:197] + "..."
        lines.append(f"- **{coptic}** → \"{english}\": {rationale}")
    lines.append("")
    lines.append("--- END ACCUMULATED VOCABULARY ---")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Assembly — combine page translations into continuous text
# ---------------------------------------------------------------------------

def assemble_translations() -> str:
    """Assemble all page translations into a single markdown document."""
    pages = sorted(SEGMENTS_DIR.glob("p_*.json"))
    if not pages:
        print("ERROR: No translation files found.")
        return ""

    lines = []
    lines.append("# Kephalaia of the Teacher — English Translation")
    lines.append("")
    lines.append(
        "*Translated from Lycopolitan Coptic by AI (Claude Opus 4.7) "
        "with scholarly footnotes.*"
    )
    lines.append(
        "*Source: Pass-2 OCR transcriptions of the Medinet Madi codex.*"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    total_pages = len(pages)
    total_notes = 0

    for path in pages:
        with open(path, encoding="utf-8") as f:
            tr = json.load(f)

        page_num = tr["page_number"]
        coptic_num = tr.get("coptic_page_number", "")
        chapter_title = tr.get("chapter_title")
        translation = tr.get("translation", "")
        notes = tr.get("notes", [])
        lacunae = tr.get("lacunae_summary", {})
        total_notes += len(notes)

        if chapter_title:
            lines.append(f"## {chapter_title}")
            lines.append("")

        lines.append(f"### Page {page_num} ({coptic_num})")
        damage = lacunae.get("damage_assessment", "unknown")
        lines.append(f"*Condition: {damage}*")
        lines.append("")
        lines.append(translation)
        lines.append("")

        if notes:
            lines.append("**Notes:**")
            for i, note in enumerate(notes, 1):
                ref = note.get("line_ref", "?")
                coptic = note.get("coptic_form", "")
                decision = note.get("decision", "")
                conf = note.get("confidence", "")
                lines.append(
                    f"{i}. [{ref}] **{coptic}** — {decision} "
                    f"({conf})"
                )
            lines.append("")

        lines.append("---")
        lines.append("")

    # Prepend statistics
    stats_block = [
        f"**Pages translated**: {total_pages}",
        f"**Total footnotes**: {total_notes}",
        "",
    ]
    insert_pos = lines.index("---") + 2
    for i, s in enumerate(stats_block):
        lines.insert(insert_pos + i, s)

    return "\n".join(lines)


def save_assembly(text: str) -> None:
    """Save assembled translation document."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(ASSEMBLED_FILE, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  Saved assembled translation to {ASSEMBLED_FILE}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Translate Kephalaia Coptic pages to English "
            "(Claude Opus 4.7)"
        )
    )
    parser.add_argument("--page", "-p", type=int, nargs="+", default=None,
                        help="One or more page numbers (e.g. -p 35 96 15 185)")
    parser.add_argument("--range", "-r", type=str, default=None)
    parser.add_argument("--limit", "-l", type=int, default=None)
    parser.add_argument("--dry-run", "-n", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--effort", default="high",
                        choices=["low", "medium", "high", "xhigh", "max"],
                        help="Thinking effort level (default: high)")
    parser.add_argument("--debug", action="store_true",
                        help="Show thinking output and verbose logging")
    parser.add_argument(
        "--max-concurrency", "-j",
        type=int,
        default=1,
        help="Number of parallel API calls (default: 1)",
    )
    parser.add_argument("--assemble", "-a", action="store_true",
                        help="Skip translation, assemble only")
    parser.add_argument("--no-seed", action="store_true",
                        help="Skip automatic seed run for vocabulary bootstrap")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    configure_paths()

    # Assembly-only mode
    if args.assemble:
        print("Assembling translations from existing pages...")
        text = assemble_translations()
        if text:
            save_assembly(text)
        return

    # Load glossary
    glossary = load_glossary()
    if glossary:
        n_mandatory = len(glossary.get("mandatory_terms", []))
        n_preferred = len(glossary.get("preferred_terms", []))
        print(
            f"Glossary loaded: {n_mandatory} mandatory, "
            f"{n_preferred} preferred terms"
        )
    else:
        print("WARNING: No glossary loaded — running without terminology")

    # Build system prompt
    sys_prompt = build_system_prompt(glossary)
    if args.debug:
        print(f"\n--- SYSTEM PROMPT ({len(sys_prompt)} chars) ---")
        print(sys_prompt[:500] + "...")
        print("--- END ---\n")

    # Discover available pages
    all_pages = list_available_pages()
    if not all_pages:
        print(
            f"ERROR: No pass2 transcriptions found in "
            f"{TRANSCRIPTIONS_DIR}"
        )
        sys.exit(1)
    print(
        f"Found {len(all_pages)} pass2 transcriptions "
        f"(p.{all_pages[0]}-p.{all_pages[-1]})"
    )

    # Determine which pages to process
    if args.page is not None:
        requested = set(args.page)
        pages = [p for p in all_pages if p in requested]
        missing = requested - set(pages)
        if missing:
            print(f"ERROR: Pages not found: {sorted(missing)}")
            sys.exit(1)
    elif args.range:
        m = re.match(r"(\d+)-(\d+)", args.range)
        if not m:
            print("ERROR: Invalid range. Use '35-100'")
            sys.exit(1)
        start, end = int(m.group(1)), int(m.group(2))
        pages = [p for p in all_pages if start <= p <= end]
    else:
        pages = all_pages

    if args.limit:
        pages = pages[:args.limit]

    # Skip already translated
    if not args.overwrite:
        to_process = [p for p in pages if not is_translated(p)]
        skipped = len(pages) - len(to_process)
        if skipped > 0:
            print(
                f"  Skipping {skipped} already-translated "
                f"(use --overwrite)"
            )
        pages = to_process

    if not pages:
        print("All requested pages already translated.")
        text = assemble_translations()
        if text:
            save_assembly(text)
        return

    print(f"\nProcessing {len(pages)} pages:")
    for p in pages:
        text = load_page(p)
        n_lines = len([
            l for l in text.strip().split("\n") if l.strip()
        ]) if text else 0
        print(f"  p.{p:3d}  ({n_lines:2d} lines)")

    if args.dry_run:
        # Show accumulated terms info even in dry-run
        accumulated = load_all_proposed_terms()
        if accumulated:
            print(
                f"\nAccumulated vocabulary: {len(accumulated)} terms "
                f"from prior translations"
            )
        print("\n[DRY RUN] No API calls made.")
        return

    # Create client
    client, deployment = create_client()
    print(f"\nUsing deployment: {deployment}")
    print(f"Thinking effort: {args.effort}")

    # Process pages
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Accumulated vocabulary: load existing proposed terms from prior runs
    # ------------------------------------------------------------------
    accumulated = load_all_proposed_terms()
    results = []
    errors = []

    if accumulated:
        print(
            f"Accumulated vocabulary: {len(accumulated)} terms "
            f"from prior translations"
        )
    else:
        print("No accumulated vocabulary found.")

    # ------------------------------------------------------------------
    # Seed run: if no proposed terms exist and we have >3 pages to do,
    # translate 3 diverse seed pages first to bootstrap vocabulary.
    # ------------------------------------------------------------------
    SEED_PAGES = [35, 96, 15]  # cosmological, five-faculty, autobiographical

    if not accumulated and len(pages) > 3 and not args.no_seed:
        seed_candidates = [
            p for p in SEED_PAGES
            if p in all_pages and p in pages
        ]
        if seed_candidates:
            print(
                f"\n--- SEED RUN: translating {len(seed_candidates)} "
                f"pages to bootstrap vocabulary ---"
            )
            for si, sp in enumerate(seed_candidates, 1):
                seed_text = load_page(sp)
                n_lines = len([
                    l for l in seed_text.strip().split("\n") if l.strip()
                ]) if seed_text else 0
                print(
                    f"  [seed {si}/{len(seed_candidates)}] "
                    f"p.{sp} ({n_lines} lines)...",
                    end=" ",
                    flush=True,
                )
                seed_result = translate_page(
                    client, deployment, sp, seed_text,
                    system_prompt=sys_prompt,
                    effort=args.effort,
                    debug=args.debug,
                    accumulated_terms=accumulated,
                )
                if seed_result:
                    save_translation(seed_result)
                    proposed = seed_result.get("proposed_terms", [])
                    save_proposed_terms(sp, proposed)
                    # Accumulate new terms (deduplicate)
                    existing_keys = {
                        t.get("coptic", "").strip() for t in accumulated
                    }
                    for t in proposed:
                        key = t.get("coptic", "").strip()
                        if key and key not in existing_keys:
                            accumulated.append(t)
                            existing_keys.add(key)
                    n_notes = len(seed_result.get("notes", []))
                    n_proposed = len(proposed)
                    damage = seed_result.get("lacunae_summary", {}).get(
                        "damage_assessment", "?"
                    )
                    print(
                        f"OK — {n_notes} notes, {n_proposed} proposed, "
                        f"{damage}"
                    )
                    results.append(seed_result)
                else:
                    print("FAILED")
                    errors.append(sp)
                time.sleep(0.5)

            # Remove seed pages from the main page list
            pages = [p for p in pages if p not in seed_candidates]
            print(
                f"--- SEED COMPLETE: {len(accumulated)} accumulated "
                f"terms. Continuing with {len(pages)} remaining pages. "
                f"---\n"
            )

    print()

    concurrency = max(1, args.max_concurrency)

    def process_page(
        page_num: int, idx: int,
    ) -> tuple[int, dict | None]:
        """Process a single page (parallel mode — snapshot of terms)."""
        return page_num, translate_page(
            client, deployment, page_num,
            load_page(page_num),
            system_prompt=sys_prompt,
            effort=args.effort,
            debug=args.debug,
            accumulated_terms=accumulated,
        )

    if concurrency == 1:
        # Sequential mode — clean progress output, live accumulation
        for i, page_num in enumerate(pages, 1):
            text = load_page(page_num)
            n_lines = len([
                l for l in text.strip().split("\n") if l.strip()
            ]) if text else 0
            print(
                f"[{i}/{len(pages)}] p.{page_num} "
                f"({n_lines} lines)...",
                end=" ",
                flush=True,
            )

            result = translate_page(
                client, deployment, page_num, text,
                system_prompt=sys_prompt,
                effort=args.effort,
                debug=args.debug,
                accumulated_terms=accumulated,
            )
            if result is None:
                print("FAILED")
                errors.append(page_num)
                continue

            save_translation(result)

            # Save proposed terms separately and accumulate for next page
            proposed = result.get("proposed_terms", [])
            save_proposed_terms(page_num, proposed)
            existing_keys = {
                t.get("coptic", "").strip() for t in accumulated
            }
            for t in proposed:
                key = t.get("coptic", "").strip()
                if key and key not in existing_keys:
                    accumulated.append(t)
                    existing_keys.add(key)

            n_notes = len(result.get("notes", []))
            n_proposed = len(proposed)
            damage = result.get("lacunae_summary", {}).get(
                "damage_assessment", "?"
            )
            print(
                f"OK — {n_notes} notes, {n_proposed} proposed, "
                f"{damage}"
            )
            results.append(result)

            if i < len(pages):
                time.sleep(0.5)
    else:
        # Parallel mode — ThreadPoolExecutor
        print(f"Running with {concurrency} parallel workers\n")
        print_lock = Lock()
        completed = 0
        total = len(pages)

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {
                executor.submit(process_page, p, i): p
                for i, p in enumerate(pages, 1)
            }
            for future in as_completed(futures):
                page_num = futures[future]
                completed += 1
                try:
                    pn, result = future.result()
                except Exception as e:
                    with print_lock:
                        print(
                            f"[{completed}/{total}] p.{page_num} "
                            f"ERROR: {e}"
                        )
                    errors.append(page_num)
                    continue

                if result is None:
                    with print_lock:
                        print(
                            f"[{completed}/{total}] p.{page_num} "
                            f"FAILED"
                        )
                    errors.append(page_num)
                    continue

                save_translation(result)

                proposed = result.get("proposed_terms", [])
                save_proposed_terms(page_num, proposed)

                n_notes = len(result.get("notes", []))
                n_proposed = len(proposed)
                damage = result.get("lacunae_summary", {}).get(
                    "damage_assessment", "?"
                )
                with print_lock:
                    print(
                        f"[{completed}/{total}] p.{page_num} "
                        f"OK — {n_notes} notes, {n_proposed} proposed, "
                        f"{damage}"
                    )
                results.append(result)

    # Summary
    print(f"\n{'='*60}")
    print(f"TRANSLATION COMPLETE")
    print(f"  Translated: {len(results)}")
    print(f"  Errors:     {len(errors)}")
    if errors:
        print(f"  Failed:     {errors}")

    # Assemble
    print(f"\nAssembling translated document...")
    text = assemble_translations()
    if text:
        save_assembly(text)

    print("Done.")


if __name__ == "__main__":
    main()
