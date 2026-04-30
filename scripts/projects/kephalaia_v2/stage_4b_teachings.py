#!/usr/bin/env python3
"""
Discover teaching boundaries from the continuous Coptic substrate.

Pipeline stage 4b: runs AFTER stage_4_extract.py, BEFORE stage_5_read.py.

Feeds the complete Coptic corpus to Claude in a single prompt (same
pattern as stage_2_discover.py). The model reads the continuous text
and identifies where one teaching unit ends and the next begins.
Output is a teaching index consumed by stage_5_read.py.

This is a corpus-scale stage (single LLM call, no per-page iteration).

Output: output/projects/kephalaia_v2/teaching_index.json

Usage:
    python scripts/projects/kephalaia_v2/stage_4b_teachings.py
    python scripts/projects/kephalaia_v2/stage_4b_teachings.py --dry-run
    python scripts/projects/kephalaia_v2/stage_4b_teachings.py --debug
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_base import (
    create_client,
    stream_tool_call,
    PROJECT_DIR,
    PAGES_DIR,
)

CORE_DIR = PROJECT_DIR / "core"


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert in the textual criticism of ancient composite texts, \
with deep specialization in the correspondential tradition — the science \
of describing spiritual realities through their natural expressions. You \
have mastered Swedenborg's doctrine of correspondences, the Persian and \
Zoroastrian mēnōg/gētīg ontology, Manichaean cosmology, and the textual \
transmission of what Swedenborg called "the Ancient Word."

## WHAT YOU ARE LOOKING AT

The text you receive is the **oldest teaching substrate** of the Coptic \
Kephalaia of the Teacher — already extracted from its editorial \
compilation. Editorial framing, exhortation, institutional material, \
and later Manichaean additions have been removed. What remains is the \
Persian and Bene Qedem substrate: impersonal cosmological- \
correspondential teaching that maps domain onto domain, being onto \
being, degree onto degree.

The substrate has a distinctive quality: **both sides of every mapping \
stay within the cosmic system.** It maps realm → zoomorphic form, \
being → metal, faculty → element, body → cosmic structure. The voice \
is impersonal, structural, systematic — "how things work." It expounds \
directly.

Each line is prefixed with a continuous section number [§N] running \
from §1 to the end of the corpus. This is a smooth unbroken sequence \
with no gaps. Lacunae within the Coptic are rendered as {N} \
placeholders. Lines that are completely destroyed have been omitted.

## YOUR TASK

Read the substrate and identify where each individual \
**correspondential teaching** begins. A teaching is a self-contained \
unit that takes ONE subject and maps it — describing its structure, \
its parts, its correspondences to other domains, its place in the \
cosmic architecture.

This is what the Kephalaia calls a "kephalaion" — a chapter of the \
teaching. Each kephalaion IS a correspondential mapping: it takes a \
subject ("Concerning the Five Worlds of Darkness," "Concerning the \
Wheel," "Concerning the Body of the First Man") and expounds that \
subject's cosmological structure through correspondence.

### WHAT CONSTITUTES ONE TEACHING

A teaching develops ONE correspondential mapping through as many \
lines as it takes. It may span many pages. Examples:
- "The Five Worlds of Darkness" — maps five realms, their kings, \
  their faces, their elements, their modes
- "The Wheel and its Zones" — maps the wheel's structure, \
  what each zone does, how they relate to purification
- "The Body of the First Man and his Five Sons" — maps body \
  parts to cosmic powers
- "The Three Days" — maps three temporal phases to three \
  processes of transformation

A teaching ends when the mapping is complete and the text moves \
to a DIFFERENT subject — a different thing being mapped.

### WHAT IS NOT A BOUNDARY

- A paragraph break within a single mapping
- An enumeration continuing (First... Second... Third... within \
  the SAME subject)
- A sub-aspect of the larger mapping (e.g. "the eyes of the King" \
  is part of "the King of Darkness," not a separate teaching)

### WHAT IS A BOUNDARY

- The subject itself changes (from "the Wheel" to "the Pillar")
- A new correspondential mapping begins (from mapping the body to \
  mapping the firmaments)
- A title phrase appears ("Concerning X" / "The Chapter of X")

### WHAT TO OUTPUT

For each teaching you identify, provide:
- The §N section number where it STARTS
- A brief title describing what is being mapped (in English)
- Your confidence (high/moderate/low)

Call commit_teachings once with the complete list."""


# ---------------------------------------------------------------------------
# Tool schema
# ---------------------------------------------------------------------------

COMMIT_TEACHINGS_TOOL = {
    "name": "commit_teachings",
    "description": (
        "Commit the complete teaching index. Call exactly once."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "teachings": {
                "type": "array",
                "description": (
                    "Ordered list of teaching boundaries."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "section": {
                            "type": "integer",
                            "description": (
                                "The §N number where this "
                                "kephalaion starts."
                            ),
                        },
                        "title": {
                            "type": "string",
                            "description": (
                                "Brief English title describing the "
                                "subject of this teaching unit."
                            ),
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "moderate", "low"],
                            "description": (
                                "How confident the boundary is."
                            ),
                        },
                    },
                    "required": ["section", "title", "confidence"],
                },
            },
            "total_teachings": {
                "type": "integer",
                "description": "Total number of teachings identified.",
            },
            "notes": {
                "type": "string",
                "description": (
                    "Any notes about ambiguous boundaries or "
                    "structural observations."
                ),
            },
        },
        "required": ["teachings", "total_teachings"],
    },
}


# ---------------------------------------------------------------------------
# Corpus assembly — core segments only (substrate + mixed), with page.line refs
# ---------------------------------------------------------------------------

def load_core_chapters() -> list[dict]:
    """Load all core extraction JSONs sorted by chapter number."""
    chapters = []
    for path in sorted(CORE_DIR.glob("ch_*.json")):
        m = re.match(r"ch_(\d+)\.json", path.name)
        if not m:
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        chapters.append({
            "chapter_num": int(m.group(1)),
            "segments": data.get("segments", []),
        })
    chapters.sort(key=lambda x: x["chapter_num"])
    return chapters


def format_corpus(chapters: list[dict]) -> tuple[str, list[dict]]:
    """Format core segments as continuous §N numbered Coptic text.

    Returns:
        (corpus_text, section_map) where section_map[i] = {chapter, line}
        mapping each §(i+1) back to its original manuscript location.

    Only includes segments classified as cosmological_substrate or mixed.
    """
    parts: list[str] = []
    section_map: list[dict] = []  # index i → §(i+1)

    for ch in chapters:
        cn = ch["chapter_num"]
        for seg in ch["segments"]:
            cls = seg.get("classification", "")
            if cls not in ("cosmological_substrate", "mixed"):
                continue
            coptic = seg.get("core_coptic")
            if not coptic:
                continue
            line_i = seg["i"]
            n = len(section_map) + 1
            parts.append(f"[§{n}] {coptic}")
            section_map.append({"section": n, "chapter": cn, "line": line_i})

    return "\n".join(parts), section_map


# ---------------------------------------------------------------------------
# Result processing
# ---------------------------------------------------------------------------

def process_result(tool_input: dict | None, section_map: list[dict]) -> dict:
    """Process teaching index, mapping §N back to page.line."""
    if tool_input is None:
        print("ERROR: No tool call received.")
        return {}

    chapters = tool_input.get("teachings", [])
    total = tool_input.get("total_teachings", len(chapters))
    notes = tool_input.get("notes", "")

    # Build lookup: §N → {page, line}
    lookup = {entry["section"]: entry for entry in section_map}

    # Resolve each chapter's section back to chapter.line
    resolved = []
    for ch in chapters:
        sec = ch["section"]
        ref = lookup.get(sec)
        if ref:
            resolved.append({
                "section": sec,
                "chapter": ref["chapter"],
                "line": ref["line"],
                "title": ch["title"],
                "confidence": ch.get("confidence", "?"),
            })
        else:
            print(f"  WARNING: §{sec} not found in section map!")
            resolved.append({
                "section": sec,
                "chapter": -1,
                "line": -1,
                "title": ch["title"],
                "confidence": ch.get("confidence", "?"),
            })

    print(f"\n--- Teaching Index: {total} teachings ---")
    for i, ch in enumerate(resolved[:20]):
        conf = ch.get("confidence", "?")
        print(f"  {i+1:3d}. [§{ch['section']:4d}] [{conf:8s}] "
              f"ch.{ch['chapter']},{ch['line']}: {ch['title'][:55]}")
    if len(resolved) > 20:
        print(f"  ... and {len(resolved) - 20} more")

    if notes:
        print(f"\n  Notes: {notes[:200]}")

    # Confidence breakdown
    from collections import Counter
    confs = Counter(ch.get("confidence", "?") for ch in resolved)
    print(f"\n  Confidence: {dict(confs)}")

    return {
        "teachings": resolved,
        "total_teachings": total,
        "notes": notes,
        "section_map": section_map,
    }


# ---------------------------------------------------------------------------
# CLI + main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover teaching boundaries (single LLM call)"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Show thinking output and verbose logging",
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true",
        help="Show corpus statistics without calling the API",
    )
    parser.add_argument(
        "--effort", default="max",
        choices=["low", "medium", "high", "xhigh", "max"],
    )
    args = parser.parse_args()

    print("Stage 4b: Teaching Discovery")
    print("  Teaching boundary identification (corpus-scale)")
    print(f"  Input:  {CORE_DIR}")
    print(f"  Output: {PROJECT_DIR / 'teaching_index.json'}")

    # Load core chapters
    chapters = load_core_chapters()
    if not chapters:
        print(f"\nERROR: No core files found in {CORE_DIR}")
        sys.exit(1)
    print(f"\nLoaded {len(chapters)} core chapters")

    # Format corpus
    corpus_text, section_map = format_corpus(chapters)
    est_tokens = len(corpus_text) / 3.5
    total_segments = len(section_map)
    print(f"  Corpus: {len(corpus_text):,} chars (~{est_tokens:,.0f} tokens)")
    print(f"  Core segments: {total_segments}")
    print(f"  Chapters: {chapters[0]['chapter_num']}-{chapters[-1]['chapter_num']}")
    print(f"  Sections: §1-§{total_segments}")

    if args.dry_run:
        print(f"\n  % of 200K limit: ~{est_tokens / 200_000 * 100:.1f}%")
        print(f"\n--- Sample (first 1500 chars) ---")
        print(corpus_text[:1500])
        print("--- end sample ---")
        print("\n[DRY RUN] No API call made.")
        return

    # Create client
    print("\nConnecting to Claude...")
    client, deployment = create_client()

    # Build messages
    messages = [
        {"role": "user", "content": corpus_text},
    ]

    # Stream
    print(f"\nStreaming analysis (this may take several minutes)...\n")
    t0 = time.time()
    tool_input = stream_tool_call(
        client,
        deployment,
        system=SYSTEM_PROMPT,
        messages=messages,
        tools=[COMMIT_TEACHINGS_TOOL],
        tool_name="commit_teachings",
        page_label="corpus",
        effort=args.effort,
        debug=args.debug,
    )
    elapsed = time.time() - t0
    print(f"\nAnalysis completed in {elapsed:.1f}s")

    # Process
    result = process_result(tool_input, section_map)
    if not result:
        print("FAILED: No teaching index extracted.")
        sys.exit(1)

    # Save
    output_path = PROJECT_DIR / "teaching_index.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\nTeaching index saved to: {output_path}")
    print(f"  Teachings: {len(result.get('teachings', []))}")


if __name__ == "__main__":
    main()
