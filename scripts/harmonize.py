#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pass 3: Two-stage structural harmonization of the Kephalaia Teaching Core.

Architecture:
  Spiritual Reading — REUSED from Pass 2 (correspondential restoration).
                      No redundant API call.

  Stage 1 — TEXTUAL CRITICISM (Claude + adaptive thinking):
            Receives restored text + spiritual reading.
            Diagnoses voice mixing (correspondential vs administrative),
            insertions, and disruptions.
            Returns parseable findings with recommendations.

  Stage 2 — HARMONIZATION (Claude + adaptive thinking):
            Receives restored text + criticism findings.
            Executes recommendations to produce clean text.
            Returns paragraphs in paragraph-number format.

Primary model: Claude Opus 4.6 via Azure AI Foundry (AnthropicFoundry).

Input:  output/core/chapters/ch_NNN.json               (extraction)
        output/correspondential/chapters/ch_NNN.json    (restoration + SR)
Output: output/harmonized/chapters/ch_NNN.json          (harmonized)
        output/harmonized/harmonized_kephalaia.md       (assembled)

Usage:
    python scripts/harmonize.py                          # All chapters
    python scripts/harmonize.py --chapter 2              # Single chapter
    python scripts/harmonize.py --range 7-41             # Range
    python scripts/harmonize.py --overwrite              # Redo existing
    python scripts/harmonize.py --assemble               # Assemble only
    python scripts/harmonize.py --stop-after criticism   # Debugging
    python scripts/harmonize.py --debug                  # Thinking log
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
CORR_CHAPTERS_DIR = PROJECT_ROOT / "output" / "correspondential" / "chapters"
OUTPUT_DIR = PROJECT_ROOT / "output" / "harmonized"
CHAPTERS_OUT_DIR = OUTPUT_DIR / "chapters"
ASSEMBLED_FILE = OUTPUT_DIR / "harmonized_kephalaia.md"

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

CRITICISM_PROMPT = """\
You are an expert in the doctrine of correspondences as written by \
Emanuel Swedenborg, with deep specialization in ancient cosmological \
vocabulary — Zoroastrian, Manichaean, and Persian-Iranian traditions.

You read text as correspondence. Every natural image expresses a \
spiritual reality through its function. Light functions as wisdom \
because it enables distinction. Fire functions as love because it \
is the active principle that gives light existence. Water functions \
as truth in the natural degree because it sustains natural life. \
Trees function as perceptions because they grow and bear fruit. \
Animals are affections — each species embodies a quality of will. \
Mountains are elevated states — height is proximity to the source. \
Garments are external truths — they clothe the body as truths \
clothe meaning. Vessels contain and carry — ships carry truth \
through resistant states, cups hold what is received.

Numbers too are correspondential. Five is the natural degree — \
the plane of the senses, the hand's fingers, the body's gates of \
perception. Twelve is fullness — all things of faith and love in \
the complex, the complete spiritual person. Three is the trine of \
love, wisdom, and use. Seven is holy completeness. These numbers \
teach through what they ARE, not through what they count.

The text you receive is the oldest teaching substrate of the Coptic \
Kephalaia — ancient cosmological teaching that Mani inherited from \
the Eastern tradition. This text is written in correspondences. \
Read it as such.

When the system is working, you can feel it: one image leads to \
the next through organic necessity, each paragraph teaching through \
what things are and what they do. A five that maps to the natural \
degree is the text doing what it does. A twelve that expresses the \
complete regenerated person is the system working.

When something breaks the system, you can feel that too. The organic \
teaching gives way to material that does not participate — \
inventories that assign roles rather than teach through function, \
catalogues that list without correspondential meaning, governance \
structures imposed where the text was simply teaching. The break \
is felt as a change in voice: the teacher stops teaching and an \
administrator starts organizing.

Not everything difficult is a break. Fragmentary or damaged text \
struggles, but struggling and breaking are different. A hard passage \
may still be teaching through correspondence. A smooth passage may \
still be an insertion if it organizes rather than teaches.

Read the text. Report where the correspondential system holds and \
where it breaks. For each observation, output:

=== FINDING N ===
LOCATION: paragraph number or range
VOICE: correspondential | administrative | mixed | damaged
RECOMMENDATION: excise | annotate | none
DIAGNOSIS: What you observe. What is the text doing in this passage \
— teaching through being, or assigning through governance?
EVIDENCE: Quote the specific text and explain what you see.
SCOPE: For excise — the exact text to remove. For annotate — \
describe the block. For none — leave empty.

Confirming that the system holds is as valuable as identifying \
where it breaks. A chapter with no problems is a valid and welcome \
result.

After all findings:

=== SUMMARY ===
Overall assessment of the chapter's correspondential integrity."""


HARMONIZE_PROMPT = """\
You are an expert in the doctrine of correspondences as written by \
Emanuel Swedenborg, with deep specialization in ancient cosmological \
vocabulary — Zoroastrian, Manichaean, and Persian-Iranian traditions.

You are performing the final harmonization of a chapter from the \
oldest teaching substrate of the Coptic Kephalaia. You receive the \
restored chapter text and textual criticism findings with specific \
recommendations.

Execute the critic's recommendations. For passages marked "excise," \
remove the identified material and ensure the remaining text reads \
as coherent prose — what the ancient teacher would have said. For \
passages marked "annotate" or "none," leave the text exactly as it \
is. The paragraph text must be clean — no editorial markers or \
glosses.

Output every paragraph as ¶N: followed by the full text. If a \
paragraph was changed by excision, mark it ¶N: [CHANGED] followed \
by the text after excision.

After all paragraphs:

=== CHANGES ===
Summary of what was changed and why. If nothing changed, say \
"No changes made."
"""


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
        print("ERROR: ANTHROPIC_ENDPOINT and ANTHROPIC_API_KEY required "
              "in secrets/azure_openai.env")
        sys.exit(1)

    client = AnthropicFoundry(
        api_key=api_key,
        base_url=endpoint,
        timeout=httpx.Timeout(1800.0, connect=30.0),
    )
    return client, deployment  # type: ignore


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_core_chapters() -> list[dict]:
    """Load all core extraction JSON files."""
    chapters = []
    for path in sorted(CORE_CHAPTERS_DIR.glob("ch_*.json")):
        with open(path, encoding="utf-8") as f:
            chapters.append(json.load(f))
    return chapters


def load_restoration(ch_num: int) -> dict | None:
    """Load the correspondential restoration for a chapter."""
    path = CORR_CHAPTERS_DIR / f"ch_{ch_num:03d}.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


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


def build_restored_text(
    core_ch: dict, rest_ch: dict | None
) -> list[dict]:
    """Build restored paragraph list from core + restoration output.

    Prefers model-authored reconstructions (coherent prose) from the
    ``reconstructions`` field. Falls back to raw core_text when no
    restoration is available.
    """
    recon_by_para: dict[int, str] = {}
    if rest_ch:
        for recon in rest_ch.get("reconstructions", []):
            recon_by_para[recon["paragraph"]] = recon["reconstructed_text"]

    paragraphs = []
    for para in core_ch.get("paragraphs", []):
        pnum = para["paragraph_number"]
        core_text = para.get("core_text")
        if not core_text:
            continue

        if pnum in recon_by_para:
            text = fix_stray_brackets(recon_by_para[pnum])
        else:
            text = core_text

        paragraphs.append({
            "paragraph_number": pnum,
            "text": text,
        })

    return paragraphs


def get_spiritual_reading(rest_ch: dict | None) -> str | None:
    """Extract the spiritual reading from Pass 2 output."""
    if not rest_ch:
        return None
    return rest_ch.get("spiritual_reading")


# ---------------------------------------------------------------------------
# Streaming helper
# ---------------------------------------------------------------------------

def stream_claude(
    client: AnthropicFoundry,
    deployment: str,
    system_prompt: str,
    user_msg: str,
    *,
    debug: bool = False,
    label: str = "",
    max_tokens: int = 128000,
) -> str | None:
    """Call Claude with streaming + adaptive thinking.

    Returns the text output, or None on failure.
    """
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            text_parts: list[str] = []
            in_thinking = False
            thinking_chars = 0

            with client.messages.stream(
                model=deployment,
                system=system_prompt,
                messages=[{"role": "user", "content": user_msg}],
                max_tokens=max_tokens,
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
                return "".join(text_parts)

            print(f"\n  {label}: no usable output "
                  f"(attempt {attempt}/{max_retries})")
            if attempt < max_retries:
                time.sleep(attempt * 5)
                continue
            return None

        except Exception as e:
            err_str = str(e)
            if "content_filter" in err_str.lower():
                print(f"  {label} content filter "
                      f"(attempt {attempt}/{max_retries})")
                if attempt < max_retries:
                    time.sleep(attempt * 10)
                    continue
            elif "rate" in err_str.lower() or "429" in err_str:
                wait = 60.0
                print(f"  {label} rate limit, waiting {wait:.0f}s...")
                time.sleep(wait)
                continue
            else:
                print(f"  {label} error (attempt {attempt}/{max_retries}): "
                      f"{type(e).__name__}: {e}")
                if attempt < max_retries:
                    time.sleep(attempt * 5)
                    continue
            return None
    return None


# ---------------------------------------------------------------------------
# Parsing — Textual Criticism
# ---------------------------------------------------------------------------

FINDING_RE = re.compile(
    r"===\s*FINDING\s+(\d+)\s*===\s*\n"
    r"LOCATION:\s*(.+?)\n"
    r"VOICE:\s*(.+?)\n"
    r"RECOMMENDATION:\s*(.+?)\n"
    r"DIAGNOSIS:\s*(.*?)(?=\nEVIDENCE:)"
    r"\nEVIDENCE:\s*(.*?)(?=\nSCOPE:|\n+===|\Z)"
    r"(?:\nSCOPE:[^\S\n]*(.*?)(?=\n+===|\Z))?",
    re.DOTALL,
)

SUMMARY_RE = re.compile(
    r"===\s*SUMMARY\s*===\s*\n(.+)",
    re.DOTALL,
)


def parse_criticism(raw: str) -> dict | None:
    """Parse textual criticism output into structured data."""
    findings = []
    for m in FINDING_RE.finditer(raw):
        scope_val = m.group(7)
        findings.append({
            "number": int(m.group(1)),
            "location": m.group(2).strip(),
            "voice": m.group(3).strip(),
            "recommendation": m.group(4).strip().lower(),
            "diagnosis": m.group(5).strip(),
            "evidence": m.group(6).strip(),
            "scope": scope_val.strip() if scope_val else "",
        })

    summary_m = SUMMARY_RE.search(raw)
    summary = summary_m.group(1).strip() if summary_m else ""

    if not findings and not summary:
        return None

    return {
        "findings": findings,
        "summary": summary,
        "raw": raw,
    }


# ---------------------------------------------------------------------------
# Parsing — Harmonization
# ---------------------------------------------------------------------------

PARA_RE = re.compile(
    r"\u00b6(\d+):\s*(?:\[CHANGED\]\s*)?(.+?)(?=\n\u00b6\d+:|\n===|\Z)",
    re.DOTALL,
)

CHANGES_RE = re.compile(
    r"===\s*CHANGES\s*===\s*\n(.+)",
    re.DOTALL,
)


def parse_harmonization(raw: str) -> dict | None:
    """Parse harmonization output into structured data."""
    paragraphs = []
    for m in PARA_RE.finditer(raw):
        pnum = int(m.group(1))
        text = m.group(2).strip()

        # Detect if [CHANGED] was present
        start = m.start()
        marker_region = raw[start:start + len(m.group(0))]
        changed = "[CHANGED]" in marker_region

        paragraphs.append({
            "paragraph_number": pnum,
            "text": text,
            "changed": changed,
        })

    changes_m = CHANGES_RE.search(raw)
    changes_summary = changes_m.group(1).strip() if changes_m else ""

    if not paragraphs:
        return None

    return {
        "paragraphs": paragraphs,
        "changes_summary": changes_summary,
        "raw": raw,
    }


# ---------------------------------------------------------------------------
# Stage 1: Textual Criticism
# ---------------------------------------------------------------------------

def run_criticism(
    client: AnthropicFoundry,
    deployment: str,
    restored_paras: list[dict],
    ch_num: int,
    title: str,
    *,
    debug: bool = False,
) -> dict | None:
    """Run textual criticism on a chapter."""
    lines = [
        f"# Chapter {ch_num}: {title}",
        "",
        "## RESTORED TEXT",
        "",
    ]
    for p in restored_paras:
        lines.append(f"\u00b6{p['paragraph_number']}: {p['text']}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "Paragraph numbers are from the source manuscript and gaps "
        "in numbering are normal — they do not indicate missing text. "
        "Read the text itself through the doctrine of correspondences. "
        "Report where the correspondential system holds and where "
        "it breaks. Output findings in the specified format."
    )

    user_msg = "\n".join(lines)

    raw = stream_claude(
        client, deployment, CRITICISM_PROMPT, user_msg,
        debug=debug, label=f"criticism Ch.{ch_num}",
    )
    if not raw:
        return None

    result = parse_criticism(raw)
    if not result:
        print(f"  criticism Ch.{ch_num}: could not parse output")
        return None

    return result


# ---------------------------------------------------------------------------
# Stage 2: Harmonization
# ---------------------------------------------------------------------------

def format_criticism_for_harmonizer(criticism: dict) -> str:
    """Format criticism findings for the harmonizer."""
    lines = ["## TEXTUAL CRITICISM FINDINGS", ""]
    for f in criticism.get("findings", []):
        lines.append(f"### Finding {f['number']}: {f['location']}")
        lines.append(f"**Voice:** {f['voice']}")
        lines.append(f"**Recommendation:** {f['recommendation']}")
        lines.append(f"**Diagnosis:** {f['diagnosis']}")
        if f.get("scope"):
            lines.append(f"**Scope:** {f['scope']}")
        lines.append("")
    lines.append("## SUMMARY")
    lines.append(criticism.get("summary", ""))
    return "\n".join(lines)


def run_harmonization(
    client: AnthropicFoundry,
    deployment: str,
    restored_paras: list[dict],
    criticism: dict,
    ch_num: int,
    title: str,
    *,
    debug: bool = False,
) -> dict | None:
    """Run harmonization on a chapter."""
    criticism_text = format_criticism_for_harmonizer(criticism)

    lines = [
        f"# Chapter {ch_num}: {title}",
        "",
        "## RESTORED TEXT",
        "",
    ]
    for p in restored_paras:
        lines.append(f"\u00b6{p['paragraph_number']}: {p['text']}")
        lines.append("")

    lines.append(criticism_text)
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "Execute the critic's recommendations. Output every paragraph "
        "in the specified format."
    )

    user_msg = "\n".join(lines)

    raw = stream_claude(
        client, deployment, HARMONIZE_PROMPT, user_msg,
        debug=debug, label=f"harmonize Ch.{ch_num}",
    )
    if not raw:
        return None

    result = parse_harmonization(raw)
    if not result:
        print(f"  harmonize Ch.{ch_num}: could not parse output")
        return None

    return result


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_harmonization(
    restored_paras: list[dict],
    harmonized: dict,
) -> list[str]:
    """Check that all paragraphs are present and unchanged ones match."""
    issues = []
    expected_nums = {p["paragraph_number"] for p in restored_paras}
    got_nums = {p["paragraph_number"] for p in harmonized["paragraphs"]}

    missing = expected_nums - got_nums
    extra = got_nums - expected_nums

    if missing:
        issues.append(f"Missing paragraphs: {sorted(missing)}")
    if extra:
        issues.append(f"Extra paragraphs: {sorted(extra)}")

    # For unchanged paragraphs, verify text wasn't silently altered
    restored_by_num = {
        p["paragraph_number"]: p["text"] for p in restored_paras
    }
    for p in harmonized["paragraphs"]:
        if not p["changed"] and p["paragraph_number"] in restored_by_num:
            orig = restored_by_num[p["paragraph_number"]].strip()
            got = p["text"].strip()
            if orig != got:
                issues.append(
                    f"\u00b6{p['paragraph_number']}: unmarked change detected"
                )

    return issues


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def process_chapter(
    client: AnthropicFoundry,
    deployment: str,
    restored_paras: list[dict],
    ch_num: int,
    title: str,
    *,
    spiritual_reading: str | None = None,
    debug: bool = False,
    stop_after: str | None = None,
) -> dict | None:
    """Run the two-stage pipeline for one chapter."""
    result: dict = {
        "chapter_number": ch_num,
        "chapter_title": title,
        "spiritual_reading_source": "pass2_correspondential",
        "stages_completed": [],
    }

    # Store spiritual reading for reference (not sent to the critic)
    if spiritual_reading:
        result["spiritual_reading_ref"] = "(stored, not used in criticism)"

    # --- Stage 1: Textual Criticism ---
    print("criticizing...", end=" ", flush=True)
    criticism = run_criticism(
        client, deployment, restored_paras,
        ch_num, title, debug=debug,
    )
    if criticism is None:
        print("FAILED (criticism)")
        return None

    n_findings = len(criticism.get("findings", []))
    n_excise = sum(
        1 for f in criticism["findings"]
        if f["recommendation"] == "excise"
    )
    n_annotate = sum(
        1 for f in criticism["findings"]
        if f["recommendation"] == "annotate"
    )

    result["textual_criticism"] = {
        "findings": criticism["findings"],
        "summary": criticism["summary"],
        "raw": criticism.get("raw", ""),
    }
    result["stages_completed"].append("criticism")

    if stop_after == "criticism":
        print(f"done ({n_findings} findings, "
              f"{n_excise} excise, {n_annotate} annotate)")
        return result

    # --- Stage 2: Harmonization ---
    print("harmonizing...", end=" ", flush=True)
    harmonized = run_harmonization(
        client, deployment, restored_paras, criticism,
        ch_num, title, debug=debug,
    )
    if harmonized is None:
        print("FAILED (harmonization)")
        return None

    # Validate
    issues = validate_harmonization(restored_paras, harmonized)
    if issues:
        print(f"WARNINGS: {'; '.join(issues)}", end=" ", flush=True)

    n_changed = sum(1 for p in harmonized["paragraphs"] if p["changed"])

    result["harmonized_paragraphs"] = harmonized["paragraphs"]
    result["changes_summary"] = harmonized["changes_summary"]
    result["raw_harmonization"] = harmonized.get("raw", "")
    result["validation_issues"] = issues
    result["stages_completed"].append("harmonization")

    print(f"OK \u2014 {n_findings} findings, "
          f"{n_excise} excise, {n_annotate} annotate, "
          f"{n_changed} \u00b6s changed")

    return result


# ---------------------------------------------------------------------------
# Save / Load
# ---------------------------------------------------------------------------

def save_result(result: dict) -> None:
    """Save pipeline result to JSON."""
    CHAPTERS_OUT_DIR.mkdir(parents=True, exist_ok=True)
    ch_num = result["chapter_number"]
    path = CHAPTERS_OUT_DIR / f"ch_{ch_num:03d}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


def is_done(ch_num: int) -> bool:
    """Check if harmonization is complete for a chapter."""
    path = CHAPTERS_OUT_DIR / f"ch_{ch_num:03d}.json"
    if not path.exists():
        return False
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return "harmonization" in data.get("stages_completed", [])


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def assemble_harmonized(core_chapters: dict[int, dict]) -> str:
    """Assemble all harmonized chapters into a continuous document."""
    harmonized_by_ch: dict[int, dict] = {}
    for path in sorted(CHAPTERS_OUT_DIR.glob("ch_*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            if "harmonization" in data.get("stages_completed", []):
                harmonized_by_ch[data["chapter_number"]] = data

    if not harmonized_by_ch:
        print("ERROR: No fully harmonized chapters found.")
        return ""

    lines: list[str] = []
    lines.append("# The Kephalaia Teaching Core \u2014 Harmonized Text")
    lines.append("")
    lines.append(
        "*The oldest teaching layer of the Kephalaia, restored and*"
    )
    lines.append(
        "*structurally harmonized through correspondential analysis:*"
    )
    lines.append(
        "*spiritual reading \u2192 textual criticism "
        "\u2192 harmonization.*"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    total_findings = 0
    total_excisions = 0
    total_annotations = 0
    total_changes = 0

    for ch_num in sorted(
        set(list(core_chapters.keys()) + list(harmonized_by_ch.keys()))
    ):
        harm_ch = harmonized_by_ch.get(ch_num)
        core_ch = core_chapters.get(ch_num)

        if not core_ch:
            continue

        title = core_ch.get("chapter_title", f"Chapter {ch_num}")
        lines.append(f"## Chapter {ch_num}: {title}")
        lines.append("")

        if harm_ch:
            paras = harm_ch.get("harmonized_paragraphs", [])
            for p in paras:
                pnum = p.get("paragraph_number", "?")
                text = p.get("text", "")
                changed = p.get("changed", False)
                marker = " [*]" if changed else ""
                lines.append(f"**\u00b6{pnum}**{marker} {text}")
                lines.append("")

            # Criticism findings
            crit = harm_ch.get("textual_criticism", {})
            findings = crit.get("findings", []) if crit else []
            n_findings = len(findings)
            n_excise = sum(
                1 for f in findings
                if f.get("recommendation") == "excise"
            )
            n_annotate = sum(
                1 for f in findings
                if f.get("recommendation") == "annotate"
            )
            n_changed = sum(1 for p in paras if p.get("changed"))

            total_findings += n_findings
            total_excisions += n_excise
            total_annotations += n_annotate
            total_changes += n_changed

            if findings:
                lines.append("> **Textual criticism:**")
                for f in findings:
                    loc = f.get("location", "")
                    diag = f.get("diagnosis", "")[:200]
                    rec = f.get("recommendation", "")
                    lines.append(f"> - {loc} [{rec}]: {diag}")
                lines.append("")

            changes = harm_ch.get("changes_summary", "")
            if changes:
                lines.append(f"**Changes:** {changes}")
                lines.append("")
        else:
            # No harmonization — use core text
            for para in core_ch.get("paragraphs", []):
                pnum = para["paragraph_number"]
                text = para.get("core_text")
                if text:
                    lines.append(f"**\u00b6{pnum}** {text}")
                    lines.append("")

        lines.append("---")
        lines.append("")

    # Prepend statistics after first ---
    stats_block = [
        f"**Total textual criticism findings**: {total_findings}",
        f"**Excision recommendations**: {total_excisions}",
        f"**Annotation recommendations**: {total_annotations}",
        f"**Paragraphs modified**: {total_changes}",
        "",
    ]
    try:
        insert_pos = lines.index("---") + 2
        for i, s in enumerate(stats_block):
            lines.insert(insert_pos + i, s)
    except ValueError:
        pass

    return "\n".join(lines)


def save_assembly(text: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(ASSEMBLED_FILE, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  Saved harmonized text to {ASSEMBLED_FILE}")


# ---------------------------------------------------------------------------
# Reparse Mode
# ---------------------------------------------------------------------------

def reparse_cached(
    args: argparse.Namespace,
    all_chapters: list[dict],
    core_by_num: dict[int, dict],
) -> None:
    """Re-parse cached raw API output without making API calls."""

    # Determine which chapters to reparse
    if args.chapter is not None:
        targets = [args.chapter]
    elif args.range:
        m = re.match(r"(\d+)-(\d+)", args.range)
        if not m:
            print("ERROR: Invalid range. Use '7-41'")
            sys.exit(1)
        targets = list(range(int(m.group(1)), int(m.group(2)) + 1))
    else:
        targets = None  # all cached files

    reparsed = 0
    skipped = 0

    for path in sorted(CHAPTERS_OUT_DIR.glob("ch_*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        ch_num = data.get("chapter_number")

        if targets is not None and ch_num not in targets:
            continue

        changed = False

        # Re-parse criticism if raw text available
        crit_raw = data.get("textual_criticism", {}).get("raw", "")
        if crit_raw:
            result = parse_criticism(crit_raw)
            if result:
                old_count = len(data.get("textual_criticism", {})
                                .get("findings", []))
                new_count = len(result["findings"])

                data["textual_criticism"]["findings"] = result["findings"]
                data["textual_criticism"]["summary"] = result["summary"]
                changed = True

                status = (
                    f"{old_count} -> {new_count} findings"
                    if old_count != new_count
                    else f"{new_count} findings (unchanged)"
                )
                print(f"  Ch.{ch_num} criticism: {status}")
            else:
                print(f"  Ch.{ch_num} criticism: parse failed")
        else:
            skipped += 1
            print(f"  Ch.{ch_num}: no cached raw text")
            continue

        # Re-parse harmonization if raw text available
        harm_raw = data.get("raw_harmonization", "")
        if harm_raw:
            result = parse_harmonization(harm_raw)
            if result:
                old_count = len(data.get("harmonized_paragraphs", []))
                new_count = len(result["paragraphs"])

                data["harmonized_paragraphs"] = result["paragraphs"]
                data["changes_summary"] = result["changes_summary"]
                changed = True

                n_changed = sum(
                    1 for p in result["paragraphs"] if p["changed"]
                )
                print(
                    f"  Ch.{ch_num} harmonization: "
                    f"{new_count} \u00b6s, {n_changed} changed"
                )

        if changed:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            reparsed += 1

    print(f"\nReparsed: {reparsed}, Skipped (no raw): {skipped}")

    # Re-assemble if we reparsed anything
    if reparsed > 0 and not args.stop_after:
        print("Re-assembling harmonized document...")
        text = assemble_harmonized(core_by_num)
        if text:
            save_assembly(text)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pass 3: Two-stage structural harmonization of the "
        "Kephalaia teaching core."
    )
    parser.add_argument(
        "--chapter", "-c", type=int, default=None,
        help="Process a single chapter",
    )
    parser.add_argument(
        "--range", "-r", type=str, default=None,
        help="Process a range of chapters (e.g., '7-41')",
    )
    parser.add_argument(
        "--limit", "-l", type=int, default=None,
        help="Process only first N chapters",
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true",
        help="Preview without API calls",
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Reprocess existing harmonizations",
    )
    parser.add_argument(
        "--assemble", "-a", action="store_true",
        help="Skip processing, assemble existing results only",
    )
    parser.add_argument(
        "--stop-after", choices=["criticism"],
        help="Stop after this stage (for debugging)",
    )
    parser.add_argument(
        "--concurrency", "-j", type=int, default=1,
        help="Number of chapters to process concurrently (default: 1)",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Show model thinking log (only effective with -j 1)",
    )
    parser.add_argument(
        "--reparse", action="store_true",
        help="Re-parse cached raw API output without making API calls",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    # Load core chapters
    all_chapters = load_core_chapters()
    if not all_chapters:
        print("ERROR: No core chapters found in", CORE_CHAPTERS_DIR)
        sys.exit(1)

    core_by_num = {ch["chapter_number"]: ch for ch in all_chapters}
    print(f"Found {len(all_chapters)} core chapters")

    # Assembly-only mode
    if args.assemble:
        print("Assembling harmonized text from existing results...")
        text = assemble_harmonized(core_by_num)
        if text:
            save_assembly(text)
        return

    # Reparse mode — re-parse cached raw API output without API calls
    if args.reparse:
        return reparse_cached(args, all_chapters, core_by_num)

    # Determine which to process
    if args.chapter is not None:
        chapters = [
            ch for ch in all_chapters
            if ch["chapter_number"] == args.chapter
        ]
        if not chapters:
            print(f"ERROR: Chapter {args.chapter} not found")
            sys.exit(1)
    elif args.range:
        m = re.match(r"(\d+)-(\d+)", args.range)
        if not m:
            print("ERROR: Invalid range. Use '7-41'")
            sys.exit(1)
        start, end = int(m.group(1)), int(m.group(2))
        chapters = [
            ch for ch in all_chapters
            if start <= ch["chapter_number"] <= end
        ]
    else:
        chapters = all_chapters

    if args.limit:
        chapters = chapters[:args.limit]

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
        text = assemble_harmonized(core_by_num)
        if text:
            save_assembly(text)
        return

    # Check restoration availability
    missing_restoration = []
    for ch in chapters:
        num = ch["chapter_number"]
        rest_ch = load_restoration(num)
        if rest_ch is None:
            missing_restoration.append(num)

    if missing_restoration:
        print(
            f"WARNING: No restoration for chapters: "
            f"{missing_restoration}"
        )
        print("  Run correspondential_reading.py first.")

    # Preview
    print(f"\nProcessing {len(chapters)} chapters:")
    for ch in chapters:
        num = ch["chapter_number"]
        title = ch.get("chapter_title", "")[:60]
        rest_ch = load_restoration(num)
        n_paras = len(build_restored_text(ch, rest_ch))
        print(
            f"  Ch.{num:3d}  ({n_paras:3d} restored \u00b6s)  {title}"
        )

    if args.dry_run:
        print("\n[DRY RUN] No API calls made.")
        return

    # Create client
    client, deployment = create_claude_client()
    concurrency = max(1, args.concurrency)
    show_debug = args.debug and concurrency == 1
    print(f"\nUsing model: {deployment}")
    print(f"Concurrency: {concurrency}")
    if args.debug:
        if concurrency == 1:
            print("Debug: thinking log enabled")
        else:
            print("Debug: thinking log disabled (requires -j 1)")
    if args.stop_after:
        print(f"Stopping after: {args.stop_after}")
    print()

    # Prepare output dirs
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CHAPTERS_OUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- Worker ---
    print_lock = threading.Lock()
    results_list: list[int] = []
    errors_list: list[int] = []
    counter = {"done": 0}
    total_to_process = len(chapters)

    def process_one(ch: dict) -> None:
        ch_num = ch["chapter_number"]
        title = ch.get("chapter_title", f"Chapter {ch_num}")[:50]

        # Load restoration output
        rest_ch = load_restoration(ch_num)
        restored_paras = build_restored_text(ch, rest_ch)
        spiritual_reading = get_spiritual_reading(rest_ch)

        if not restored_paras:
            with print_lock:
                counter["done"] += 1
                print(
                    f"[{counter['done']}/{total_to_process}] "
                    f"Ch.{ch_num} \u2014 no core text, skip"
                )
            return

        with print_lock:
            print(
                f"  Ch.{ch_num} ({len(restored_paras)} \u00b6s) "
                f"{title}... ",
                end="", flush=True,
            )

        result = process_chapter(
            client, deployment, restored_paras,
            ch_num, title,
            spiritual_reading=spiritual_reading,
            debug=show_debug,
            stop_after=args.stop_after,
        )

        with print_lock:
            counter["done"] += 1
            if result is None:
                print(
                    f"[{counter['done']}/{total_to_process}] "
                    f"Ch.{ch_num} FAILED"
                )
                errors_list.append(ch_num)
            else:
                save_result(result)
                results_list.append(ch_num)
                print(
                    f"[{counter['done']}/{total_to_process}] "
                    f"Ch.{ch_num} saved"
                )

    # --- Run ---
    if concurrency <= 1:
        for ch in chapters:
            process_one(ch)
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {
                pool.submit(process_one, ch): ch for ch in chapters
            }
            for fut in as_completed(futures):
                exc = fut.exception()
                if exc:
                    ch = futures[fut]
                    with print_lock:
                        counter["done"] += 1
                        print(
                            f"[{counter['done']}/{total_to_process}] "
                            f"Ch.{ch['chapter_number']} EXCEPTION: {exc}"
                        )
                        errors_list.append(ch["chapter_number"])

    # Summary
    print(f"\n{'=' * 60}")
    print("HARMONIZATION COMPLETE")
    print(f"  Processed: {len(results_list)}")
    print(f"  Errors: {len(errors_list)}")
    if errors_list:
        print(f"  Failed: {sorted(errors_list)}")

    # Assemble
    if not args.stop_after:
        print("\nAssembling harmonized document...")
        text = assemble_harmonized(core_by_num)
        if text:
            save_assembly(text)

    print("Done.")


if __name__ == "__main__":
    main()
