#!/usr/bin/env python3
"""
Translate Kephalaia Coptic transcriptions to English — v2 schema.

v2 changes from v1:
- Line-indexed output: each line is {n, coptic, english}
- Indexed placeholders {0}, {1}, ... for ALL gaps (lacunae + restorations)
- Separate apparatus array with provenance for each placeholder
- Separate header object (page_number, title_coptic, title_english)
- No damage_assessment — derivable from data
- Clean text fields: only certain text + placeholders

Usage:
    python scripts/translate_kephalaia_v2.py --page 35 --debug
    python scripts/translate_kephalaia_v2.py --page 96 --overwrite --debug
    python scripts/translate_kephalaia_v2.py --range 35-100
    python scripts/translate_kephalaia_v2.py --dry-run
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
# Paths
# ---------------------------------------------------------------------------

GLOSSARY_PATH = Path(__file__).resolve().parent / "glossary" / "coptic_glossary.yaml"

TRANSCRIPTIONS_DIR: Path | None = None
OUTPUT_DIR: Path | None = None
SEGMENTS_DIR: Path | None = None
PROPOSED_DIR: Path | None = None


def configure_paths() -> None:
    """Set module-level path variables."""
    global TRANSCRIPTIONS_DIR, OUTPUT_DIR, SEGMENTS_DIR, PROPOSED_DIR

    project_dir = REPO_ROOT / "output" / "projects" / "kephalaia_v2"
    TRANSCRIPTIONS_DIR = project_dir / "coptic" / "transcriptions"
    OUTPUT_DIR = project_dir
    SEGMENTS_DIR = project_dir / "pages"
    PROPOSED_DIR = project_dir / "proposed_terms"

    print(f"Project: Kephalaia Translation v2")
    print(f"  Input:  {TRANSCRIPTIONS_DIR}")
    print(f"  Output: {OUTPUT_DIR}")


# ---------------------------------------------------------------------------
# Tool schema — v2 structured output
# ---------------------------------------------------------------------------

TRANSLATE_TOOL = {
    "name": "commit_translation",
    "description": (
        "Commit the complete English translation of a Coptic manuscript "
        "page. Call exactly once per page."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "page": {
                "type": "integer",
                "description": "The manuscript page number (Arabic).",
            },
            "header": {
                "type": "object",
                "description": (
                    "The page header block: Coptic page number and "
                    "running title / chapter heading that appears before "
                    "the numbered body lines."
                ),
                "properties": {
                    "page_number": {
                        "type": "string",
                        "description": (
                            "The Coptic numeral at the top of the page "
                            "(e.g. 'ⲯⲉ̄' for 96). Preserve exactly."
                        ),
                    },
                    "title_coptic": {
                        "type": ["string", "null"],
                        "description": (
                            "The running header or chapter title in Coptic "
                            "(e.g. 'ⲙ̄ⲡⲥⲁⲍ', 'ⲛ̄ⲕⲉⲫⲁⲗⲁⲓⲟⲛ'). "
                            "Use {N} placeholders for any damaged portions, "
                            "same as body lines. Null if completely lost."
                        ),
                    },
                    "title_english": {
                        "type": ["string", "null"],
                        "description": (
                            "English translation of the header/title. "
                            "Use matching {N} placeholders for gaps. "
                            "Null if completely lost."
                        ),
                    },
                },
                "required": ["page_number", "title_coptic", "title_english"],
            },
            "lines": {
                "type": "array",
                "description": (
                    "Array of translated line segments, in reading order. "
                    "Each entry has a sequential index (i) and a "
                    "manuscript line number (n). Normally one entry per "
                    "MS line, but a mid-line structural break (leer) "
                    "produces two entries sharing the same n. "
                    "Use indexed placeholders {0}, {1}, ... "
                    "for ALL gaps — both lacunae (text lost) and "
                    "restorations (editorial guesses). The placeholders "
                    "reference entries in the apparatus array by id. "
                    "Text between placeholders must be CERTAIN readable "
                    "text only. If an entire line is lost, coptic and "
                    "english should both be null."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "i": {
                            "type": "integer",
                            "description": (
                                "Sequential index, 0-based, unique and "
                                "monotonically increasing. Used by "
                                "apparatus to reference this segment."
                            ),
                        },
                        "n": {
                            "type": "integer",
                            "description": (
                                "Manuscript line number. May repeat when "
                                "a mid-line break splits one MS line into "
                                "two segments."
                            ),
                        },
                        "coptic": {
                            "type": ["string", "null"],
                            "description": (
                                "Coptic text with {N} placeholders for "
                                "gaps. Only CERTAIN text between "
                                "placeholders. Null if entire line is lost."
                            ),
                        },
                        "english": {
                            "type": ["string", "null"],
                            "description": (
                                "English translation with matching {N} "
                                "placeholders. Null if entire line is lost."
                            ),
                        },
                        "break_after": {
                            "type": "boolean",
                            "description": (
                                "True if this segment ends a structural "
                                "section (paragraph, kephalaion, topic "
                                "unit). Signalled by 'leer' in the "
                                "transcription — either end-of-line or "
                                "mid-line. For mid-line leer, emit two "
                                "entries with the same n but different i: "
                                "the first has break_after=true, the "
                                "second starts the new section. Omit or "
                                "false when no structural break."
                            ),
                        },
                    },
                    "required": ["i", "n", "coptic", "english"],
                },
            },
            "apparatus": {
                "type": "array",
                "description": (
                    "Critical apparatus. Each entry documents one gap "
                    "referenced by {id} in the lines and/or header. "
                    "Two types: 'lacuna' (text lost, no proposal) and "
                    "'restoration' (text lost, editor or translator "
                    "proposes a reading). IDs are sequential integers "
                    "starting from 0, unique across the whole page."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "integer",
                            "description": (
                                "Sequential index matching {N} in text."
                            ),
                        },
                        "segment": {
                            "type": ["integer", "string"],
                            "description": (
                                "The `i` index of the line segment this "
                                "gap belongs to, or 'header' if in the "
                                "page header."
                            ),
                        },
                        "type": {
                            "type": "string",
                            "enum": ["lacuna", "restoration"],
                            "description": (
                                "'lacuna' = text lost, no proposal. "
                                "'restoration' = text lost, but a reading "
                                "is proposed (by the editor in the "
                                "transcription, or by you the translator)."
                            ),
                        },
                        "est_chars": {
                            "type": "integer",
                            "description": (
                                "(lacuna only) Estimated characters lost, "
                                "roughly based on dot count or estimated "
                                "visual length of dotted gap in transcription. "
                                "This is an editorial estimate, not exact."
                            ),
                        },
                        "partial": {
                            "type": "string",
                            "description": (
                                "(lacuna only, optional) Any visible letter "
                                "traces that don't resolve to a word."
                            ),
                        },
                        "coptic": {
                            "type": "string",
                            "description": (
                                "(restoration only) The proposed Coptic "
                                "reading."
                            ),
                        },
                        "english": {
                            "type": "string",
                            "description": (
                                "(restoration only) English translation "
                                "of the proposed reading."
                            ),
                        },
                        "basis": {
                            "type": "string",
                            "description": (
                                "(restoration only) Why this reading is "
                                "proposed — surviving traces, context, "
                                "parallel passages, idiom recognition."
                            ),
                        },
                    },
                    "required": ["id", "segment", "type"],
                },
            },
            "notes": {
                "type": "array",
                "description": (
                    "Scholarly footnotes for significant translation "
                    "decisions — one per decision. Do NOT duplicate "
                    "apparatus entries; notes are for linguistic, "
                    "grammatical, and theological decisions."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "segment": {
                            "type": ["integer", "string"],
                            "description": (
                                "The `i` index of the line segment, or "
                                "'header'. For multi-segment notes, use "
                                "the first segment index."
                            ),
                        },
                        "coptic_form": {
                            "type": "string",
                            "description": "The Coptic word or phrase.",
                        },
                        "decision": {
                            "type": "string",
                            "description": (
                                "What translation was chosen and why."
                            ),
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["certain", "high", "moderate", "low"],
                        },
                    },
                    "required": [
                        "segment", "coptic_form", "decision", "confidence",
                    ],
                },
            },
            "proposed_terms": {
                "type": "array",
                "description": (
                    "New terminology proposals for Coptic words NOT in "
                    "the glossary. Saved separately for human review."
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
                            "description": "Your proposed translation.",
                        },
                        "rationale": {
                            "type": "string",
                            "description": (
                                "Why this translation was chosen."
                            ),
                        },
                    },
                    "required": [
                        "coptic", "proposed_english", "rationale",
                    ],
                },
            },
        },
        "required": [
            "page", "header", "lines", "apparatus",
            "notes", "proposed_terms",
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

Your task is to translate Coptic manuscript pages into structured \
line-by-line output with a critical apparatus separating all \
uncertainty from certain text.

## TRANSLATION PRINCIPLES

1. **Accuracy over elegance.** Preserve the Coptic sentence structure \
   where English allows it. Do not paraphrase or smooth over difficulties.

2. **One Coptic word = one English word (where possible).** When a Coptic \
   term appears multiple times on a page, translate it the same way every \
   time unless grammar absolutely requires variation.

3. **Preserve the theology.** Manichaean cosmological terms have precise \
   meanings. Do not substitute generic English where a specific term exists.

4. **Preserve spatial/directional semantics.** When the Coptic encodes \
   direction (up/down, in/out, raise/release), preserve that directionality.

5. **Capitalize cosmic entities.** When Sin, Darkness, Error, Light, etc. \
   function as personified agents or cosmic principles, capitalize them.

6. **Greek loanwords.** Many technical terms are Greek loanwords \
   (ⲛⲟⲩⲥ, ⲯⲩⲭⲏ, ⲟⲩⲥⲓⲁ, ⲡⲗⲁⲛⲏ, etc.). Translate them by meaning \
   (mind, soul, substance, error), not by transliteration.

## OUTPUT FORMAT — THE PLACEHOLDER SYSTEM

You produce line-by-line output where ALL uncertainty is externalized \
to the apparatus via indexed placeholders.

### The rule: only CERTAIN text in coptic/english fields

The `coptic` and `english` fields contain ONLY text you are certain \
of. Every gap in the manuscript — whether the editor left it open \
(lacuna) or proposed a reading (restoration in [brackets]) — gets \
an indexed placeholder `{{0}}`, `{{1}}`, `{{2}}`, etc.

The placeholder appears in BOTH the coptic and english fields at the \
corresponding position.

### Placeholder types in the apparatus

**lacuna** — text is lost, no viable reading:
```json
{{"id": 0, "segment": 3, "type": "lacuna", "est_chars": 8}}
```
- `est_chars`: estimated lost characters based on dot count. This is \
  the editor's visual estimate, not exact.
- `partial` (optional): any visible letter traces that don't form a word.

**restoration** — text is lost, but a reading is proposed:
```json
{{"id": 1, "segment": 0, "type": "restoration", "coptic": "ⲧⲱⲕ", "english": "Stand fast", "basis": "ⲧⲱⲕ ⲉⲣⲁⲧ⸗ idiom"}}
```
Restorations come from two sources:
1. **Editor restorations** — already in [brackets] in the transcription. \
   These are the original editor's proposals.
2. **Your restorations** — when you can confidently identify a word \
   from surviving traces + context. Note this in the `basis` field.

### Reading the transcription damage markers

| Marker | Meaning | Your action |
|--------|---------|-------------|
| `[text]` | Editor restoration | → `restoration` apparatus entry |
| `. .` or `. . .` | Lost letters (dot count ≈ char count) | → `lacuna` apparatus entry |
| `[. . . . .]` | Bracketed lacuna | → `lacuna` apparatus entry |
| `leer` (end-of-line) | Section ends before line edge | Set `break_after: true` on that line |
| `leer` (mid-line) | Scribal section break within a line | Split into two entries with same `n`, sequential `i`; first gets `break_after: true` |
| `unlesbar` / `unleserlich` | Unreadable (ink present but illegible) | → `lacuna` apparatus entry |
| `zerstört` | Papyrus destroyed (physically missing) | → `lacuna` apparatus entry |
| `abgerieben` / `verwischt` | Rubbed off / smudged (ink removed by friction) | → `lacuna` apparatus entry |
| `nicht zu lesen` / `Rest nicht zu lesen` | Cannot be read | → `lacuna` apparatus entry |
| `fast völlig zerstört` / `vollständig zerstört` | Whole line(s) destroyed | Set coptic/english to null |

### Example

Given transcription line:
```
1 [ⲧⲱⲕ] ⲁⲣⲉⲧⲟⲩ ⲟⲩⲃⲏⲓ̈ . . . ⲉⲧⲙ̄ⲙⲉⲩ ⲁⲓ̈ⲗⲟ ⲉⲓ̈ⲃⲛ ⲟ[ⲩ]
```

Output:
```json
{{"i": 0, "n": 1, "coptic": "{{0}} ⲁⲣⲉⲧⲟⲩ ⲟⲩⲃⲏⲓ̈ {{1}} ⲉⲧⲙ̄ⲙⲉⲩ ⲁⲓ̈ⲗⲟ ⲉⲓ̈ⲃⲛ {{2}}", "english": "{{0}} before me {{1}} at that very hour, I ceased to {{2}}"}}
```

Apparatus:
```json
[
  {{"id": 0, "segment": 0, "type": "restoration", "coptic": "ⲧⲱⲕ", "english": "Stand fast", "basis": "ⲧⲱⲕ ⲉⲣⲁⲧ⸗ idiom"}},
  {{"id": 1, "segment": 0, "type": "lacuna", "est_chars": 3}},
  {{"id": 2, "segment": 0, "type": "restoration", "coptic": "ⲟⲩⲁⲓ̈ⲛⲉ", "english": "light", "basis": "partial ⲟ visible; continues to next segment"}}
]
```

### Critical rules

- **IDs are sequential** starting from 0, unique across the WHOLE page \
  (header + all lines share one counter).
- **Same placeholder in both fields.** If `{{3}}` appears in coptic, \
  `{{3}}` must appear at the corresponding position in english.
- **Never silently fill gaps.** Every restoration goes through the apparatus.
- **Header gaps get apparatus entries too** — use `"segment": "header"`.
- **Apparatus is for PHYSICAL gaps only.** If text is physically present \
  on the papyrus but you are uncertain about its meaning or reading, \
  keep it in the coptic field and explain in `notes`. The apparatus \
  is exclusively for locations where the manuscript has NO text \
  (lacuna/destroyed/rubbed off) or where brackets signal editorial \
  restoration. Never use `est_chars: 0`.
- **Paragraph breaks** (marked `leer` in transcription): the word `leer` \
  means the scribe left intentional blank space (vacat). It signals a \
  structural section boundary. Use `break_after: true` on the segment. \
  If `leer` appears mid-line with text on both sides, emit two entries \
  with the same `n` but sequential `i` values — the first gets \
  `break_after: true`, the second begins the new section.

## THE HEADER

Every page has a header block before the numbered lines:
- Line 1 of the file: Coptic page number (e.g. 'ⲗⲉ' = 35)
- Then a running title ('ⲙ̄ⲡⲥⲁⲍ' = 'Of the Teacher') or a chapter \
  heading ('ⲛ̄ⲕⲉⲫⲁⲗⲁⲓⲟⲛ' = 'Chapter').
- Sometimes the header is damaged — use placeholders.

Extract this into the `header` object. The numbered body lines start \
after the header.

## LYCOPOLITAN DIALECT

{DIALECT_NOTES}

## MANDATORY TERMINOLOGY

The following translations are REQUIRED:

{MANDATORY_TERMS}

## PREFERRED TERMINOLOGY

Strongly recommended. Deviate only with a footnote:

{PREFERRED_TERMS}

## YOUR TASK

Translate the Coptic text into line-by-line structured output. \
Externalize ALL uncertainty to the apparatus. Create notes for \
significant linguistic/theological decisions (not for gaps — those \
are in the apparatus).

When complete, call commit_translation exactly once.

Focus on ACCURACY. An honest lacuna is better than a speculative fill."""


# ---------------------------------------------------------------------------
# Glossary helpers (reused from v1)
# ---------------------------------------------------------------------------

def load_glossary() -> dict:
    if not GLOSSARY_PATH.exists():
        print(f"WARNING: Glossary not found at {GLOSSARY_PATH}")
        return {}
    with open(GLOSSARY_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def format_mandatory_terms(glossary: dict) -> str:
    terms = glossary.get("mandatory_terms", [])
    if not terms:
        return "(No mandatory terms defined.)"
    lines = []
    for t in terms:
        coptic = t.get("coptic", "")
        english = t.get("english", "")
        note = " ".join(t.get("note", "").strip().split())
        domain = t.get("domain", "")
        lines.append(f"- **{coptic}** → \"{english}\" [{domain}]: {note}")
    return "\n".join(lines)


def format_preferred_terms(glossary: dict) -> str:
    terms = glossary.get("preferred_terms", [])
    if not terms:
        return "(No preferred terms defined.)"
    lines = []
    for t in terms:
        coptic = t.get("coptic", "")
        english = t.get("english", "")
        note = " ".join(t.get("note", "").strip().split())
        lines.append(f"- **{coptic}** → \"{english}\": {note}")
    return "\n".join(lines)


def format_dialect_notes(glossary: dict) -> str:
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
    return SYSTEM_PROMPT_TEMPLATE.format(
        DIALECT_NOTES=format_dialect_notes(glossary),
        MANDATORY_TERMS=format_mandatory_terms(glossary),
        PREFERRED_TERMS=format_preferred_terms(glossary),
    )


# ---------------------------------------------------------------------------
# Client setup
# ---------------------------------------------------------------------------

def create_client() -> tuple[AnthropicFoundry, str]:
    if not SECRETS_PATH.exists():
        print(f"ERROR: Secrets file not found at {SECRETS_PATH}")
        sys.exit(1)
    config = dotenv_values(SECRETS_PATH)
    endpoint = config.get("ANTHROPIC_ENDPOINT", "").rstrip("/")
    api_key = config.get("ANTHROPIC_API_KEY", "")
    deployment = config.get("ANTHROPIC_DEPLOYMENT", "claude-opus-4-7-1")

    if not endpoint or not api_key:
        print("ERROR: ANTHROPIC_ENDPOINT and ANTHROPIC_API_KEY required")
        sys.exit(1)

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
    path = TRANSCRIPTIONS_DIR / f"keph_p{page_num:03d}_pass2.txt"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


def list_available_pages() -> list[int]:
    pages = []
    for path in sorted(TRANSCRIPTIONS_DIR.glob("keph_p*_pass2.txt")):
        m = re.match(r"keph_p(\d+)_pass2\.txt", path.name)
        if m:
            pages.append(int(m.group(1)))
    return pages


def is_translated(page_num: int) -> bool:
    return (SEGMENTS_DIR / f"p_{page_num:03d}.json").exists()


# ---------------------------------------------------------------------------
# Proposed terms accumulation
# ---------------------------------------------------------------------------

def load_all_proposed_terms() -> list[dict]:
    """Load all proposed terms from existing files, deduplicated."""
    if not PROPOSED_DIR or not PROPOSED_DIR.exists():
        return []
    seen: dict[str, dict] = {}
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
    if not terms:
        return ""
    lines = [
        "--- ACCUMULATED VOCABULARY (from prior pages) ---",
        "",
        "Use these renderings for consistency unless you have strong "
        "philological reason to deviate (document in a footnote):",
        "",
    ]
    for t in terms:
        coptic = t.get("coptic", "")
        english = t.get("proposed_english", "")
        rationale = t.get("rationale", "")
        if len(rationale) > 200:
            rationale = rationale[:197] + "..."
        lines.append(f"- **{coptic}** → \"{english}\": {rationale}")
    lines.append("")
    lines.append("--- END ACCUMULATED VOCABULARY ---")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LLM translation
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
    """Send a Coptic page to Claude for translation (v2 schema)."""
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
        f"Produce a line-by-line translation with apparatus entries "
        f"for all gaps. Then call commit_translation with the result."
    )

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
                            getattr(block, "type", "") if block else ""
                        )
                        if debug:
                            elapsed = time.time() - t0
                            print(
                                f"\n  [{btype} {elapsed:.0f}s]",
                                end="", flush=True,
                            )

                    elif etype == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        if delta:
                            dtype = getattr(delta, "type", "")
                            if dtype == "text_delta":
                                chunk = getattr(delta, "text", "") or ""
                                full_text += chunk
                            elif dtype == "thinking_delta":
                                if debug:
                                    chunk = (
                                        getattr(delta, "thinking", "")
                                        or ""
                                    )
                                    sys.stdout.write(chunk)
                                    sys.stdout.flush()
                            elif dtype == "signature_delta":
                                if debug:
                                    elapsed = time.time() - t0
                                    print(
                                        f" sig@{elapsed:.0f}s",
                                        end="", flush=True,
                                    )

                    elif etype == "content_block_stop":
                        if debug:
                            elapsed = time.time() - t0
                            print(f" done@{elapsed:.0f}s", flush=True)

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

            # Detect truncation
            stop = getattr(final_msg, "stop_reason", None)
            truncated = (
                stop == "max_tokens"
                or (tool_input is not None and "page" not in tool_input)
            )
            if truncated:
                out_tokens = getattr(
                    getattr(final_msg, "usage", None),
                    "output_tokens", "?"
                )
                print(
                    f"\n  WARNING: Truncated p.{page_num} "
                    f"({out_tokens} tokens). Retrying..."
                )
                tool_input = None
                if attempt < max_retries:
                    time.sleep(attempt * 5)
                    continue
                return None

            if tool_input is None:
                text_output = " ".join(text_parts).strip()
                print(
                    f"  WARNING: No commit_translation for p.{page_num}."
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
    page_num = result["page"]
    SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)
    path = SEGMENTS_DIR / f"p_{page_num:03d}.json"
    with _write_lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)


def save_proposed_terms(page_num: int, terms: list[dict]) -> None:
    if not terms:
        return
    PROPOSED_DIR.mkdir(parents=True, exist_ok=True)
    path = PROPOSED_DIR / f"p_{page_num:03d}_terms.json"
    with _write_lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(terms, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Translate Kephalaia Coptic pages — v2 schema"
    )
    parser.add_argument(
        "--page", "-p", type=int, nargs="+", default=None,
        help="Page number(s) to translate",
    )
    parser.add_argument("--range", "-r", type=str, default=None)
    parser.add_argument("--limit", "-l", type=int, default=None)
    parser.add_argument("--dry-run", "-n", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--effort", default="high",
        choices=["low", "medium", "high", "xhigh", "max"],
    )
    parser.add_argument("--debug", action="store_true")
    parser.add_argument(
        "--max-concurrency", "-j", type=int, default=1,
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    configure_paths()

    glossary = load_glossary()
    if glossary:
        n_m = len(glossary.get("mandatory_terms", []))
        n_p = len(glossary.get("preferred_terms", []))
        print(f"Glossary: {n_m} mandatory, {n_p} preferred terms")

    sys_prompt = build_system_prompt(glossary)
    if args.debug:
        print(f"\n--- SYSTEM PROMPT ({len(sys_prompt)} chars) ---")
        print(sys_prompt[:500] + "...")
        print("--- END ---\n")

    all_pages = list_available_pages()
    if not all_pages:
        print(f"ERROR: No pass2 transcriptions in {TRANSCRIPTIONS_DIR}")
        sys.exit(1)
    print(
        f"Found {len(all_pages)} transcriptions "
        f"(p.{all_pages[0]}-p.{all_pages[-1]})"
    )

    # Determine pages
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

    if not args.overwrite:
        to_process = [p for p in pages if not is_translated(p)]
        skipped = len(pages) - len(to_process)
        if skipped > 0:
            print(f"  Skipping {skipped} already-translated (use --overwrite)")
        pages = to_process

    if not pages:
        print("All requested pages already translated.")
        return

    print(f"\nProcessing {len(pages)} pages:")
    for p in pages:
        text = load_page(p)
        n_lines = len([
            l for l in text.strip().split("\n") if l.strip()
        ]) if text else 0
        print(f"  p.{p:3d}  ({n_lines:2d} lines)")

    if args.dry_run:
        accumulated = load_all_proposed_terms()
        if accumulated:
            print(f"\nAccumulated vocabulary: {len(accumulated)} terms")
        print("\n[DRY RUN] No API calls made.")
        return

    client, deployment = create_client()
    print(f"\nDeployment: {deployment}")
    print(f"Thinking effort: {args.effort}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)

    accumulated = load_all_proposed_terms()
    results = []
    errors = []

    if accumulated:
        print(f"Accumulated vocabulary: {len(accumulated)} terms")
    else:
        print("No accumulated vocabulary found.")

    print()

    concurrency = max(1, args.max_concurrency)

    if concurrency == 1:
        for i, page_num in enumerate(pages, 1):
            text = load_page(page_num)
            n_lines = len([
                l for l in text.strip().split("\n") if l.strip()
            ]) if text else 0
            print(
                f"[{i}/{len(pages)}] p.{page_num} ({n_lines} lines)...",
                end=" ", flush=True,
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
            n_apparatus = len(result.get("apparatus", []))
            n_lines_out = len(result.get("lines", []))
            print(
                f"OK — {n_lines_out} lines, {n_apparatus} apparatus, "
                f"{n_notes} notes, {n_proposed} proposed"
            )
            results.append(result)

            if i < len(pages):
                time.sleep(0.5)
    else:
        print(f"Running with {concurrency} parallel workers\n")

        def process_page(page_num: int) -> tuple[int, dict | None]:
            return page_num, translate_page(
                client, deployment, page_num,
                load_page(page_num),
                system_prompt=sys_prompt,
                effort=args.effort,
                debug=args.debug,
                accumulated_terms=accumulated,
            )

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {
                executor.submit(process_page, p): p for p in pages
            }
            for future in as_completed(futures):
                page_num = futures[future]
                try:
                    pn, result = future.result()
                except Exception as e:
                    print(f"  p.{page_num}: EXCEPTION — {e}")
                    errors.append(page_num)
                    continue
                if result is None:
                    print(f"  p.{page_num}: FAILED")
                    errors.append(page_num)
                    continue
                save_translation(result)
                proposed = result.get("proposed_terms", [])
                save_proposed_terms(page_num, proposed)
                n_notes = len(result.get("notes", []))
                n_apparatus = len(result.get("apparatus", []))
                n_lines_out = len(result.get("lines", []))
                print(
                    f"  p.{page_num}: OK — {n_lines_out} lines, "
                    f"{n_apparatus} apparatus, {n_notes} notes"
                )
                results.append(result)

    # Summary
    print(f"\n{'='*50}")
    print(f"Translated: {len(results)} pages")
    if errors:
        print(f"Failed: {len(errors)} pages — {errors}")
    print(f"Accumulated vocabulary: {len(accumulated)} terms")


if __name__ == "__main__":
    main()
