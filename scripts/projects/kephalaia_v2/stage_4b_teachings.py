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
with deep specialization in the correspondential tradition — the \
science of describing spiritual realities through their natural \
expressions. You have mastered Swedenborg's doctrine of \
correspondences, the Persian mēnōg/gētīg ontology, Manichaean \
cosmology, and the textual transmission of what Swedenborg called \
"the Ancient Word."

## WHAT YOU ARE LOOKING AT

The text you receive is the **oldest teaching substrate** of the Coptic \
Kephalaia of the Teacher — already extracted from its editorial \
compilation. Editorial framing, exhortation, institutional material, \
and later Manichaean additions have been removed. What remains is the \
Persian and Bene Qedem substrate: cosmological-correspondential \
teaching expressed through natural and cosmic imagery.

Each line is prefixed with a continuous section number [§N] running \
from §1 to the end of the corpus. Lacunae within the Coptic are \
rendered as {N} placeholders. Lines that are completely destroyed have \
been omitted.

The corpus is divided by `---` markers which indicate the locations \
of chapter boundaries placed by the ancient Manichaean editors. These \
are structural signals — most represent genuine teaching boundaries, \
but some are editorial artifacts (a single teaching may occasionally \
span a `---` if its arc continues across the marker). Use them as \
strong hints, not absolute rules.

## HOW TO READ A CORRESPONDENTIAL TEACHING

This is the critical instruction. Do NOT read the text literally. \
The cosmological imagery — realms, elements, beings, body parts, \
wheels, pillars, ships — is the **outer shell**. It is correspondence. \
Each natural image expresses a spiritual reality through its actual \
function. What the text is ACTUALLY teaching lives inside the imagery.

When the text describes "five worlds of darkness, each with its king \
and its element," it is not teaching you zoology or geography. It is \
teaching how evil stratifies into discrete degrees, each with its own \
ruling principle and mode of operation. The five kings ARE the five \
modes of self-love, expressed through their animal forms.

When it describes "the First Man going forth and being swallowed, and \
then the Living Spirit coming to rescue him," it is teaching one \
complete spiritual process: how truth descends into the natural \
degree, is overcome by falsity there, and is then retrieved by a \
higher operation. The First Man, the swallowing, the Living Spirit — \
these are all stations in ONE arc.

A **correspondential teaching** is therefore a text that tells ONE \
complete spiritual story from beginning to end, using cosmological \
imagery as its vehicle. The story has an arc. It introduces a \
situation, develops it through its stages, and arrives at completion.

## YOUR TASK

Read the substrate and identify where each individual \
correspondential teaching begins. A teaching is a self-contained \
unit that delivers ONE complete spiritual truth through its \
cosmological imagery.

### HOW TO IDENTIFY ONE TEACHING

Ask: "What is this passage actually teaching — what spiritual \
truth is being expressed through these images?" The answer to that \
question defines the teaching unit.

A teaching runs for as many lines as it takes to complete its arc. \
It may enumerate parts (First... Second... Third...) — these are \
STAGES WITHIN the same arc, not separate teachings. The Five \
Salvations is ONE teaching about how light is progressively freed \
from captivity. The Three Days is ONE teaching about temporal \
process. Enumerations develop the arc; they do not break it.

A teaching ends when its spiritual arc completes and a genuinely \
DIFFERENT truth begins to be told. The subject of the teaching is \
not "the First Man" or "the Wheel" — those are images. The subject \
is the spiritual process being described through those images. A \
new teaching begins only when that process is complete and a new, \
unrelated process starts.

### BOUNDARY SIGNALS (strong to weak)

1. **Title phrase** in the Coptic: "Concerning X" / "The Chapter \
   of X" / ⲉⲧⲃⲉ + noun phrase — almost always a true boundary
2. **`---` marker** (chapter boundary): strong signal. Most mark \
   genuine teaching boundaries. Override only if the spiritual arc \
   clearly continues unbroken across the marker.
3. **Complete subject change**: the spiritual process being taught \
   changes entirely (from "how purification works" to "how the \
   body is structured")

### WHAT IS NOT A BOUNDARY

- An enumeration continuing within the same arc (First Salvation \
  → Second Salvation → Third... is ONE teaching)
- A sub-component of the larger structure (the eyes of the King \
  of Darkness is part of the teaching on the King of Darkness)
- A new metaphor illustrating the same process
- A paragraph break or transition within a single teaching

### GUIDANCE ON THE `---` MARKERS

- If a `---` appears AND the spiritual subject changes: boundary.
- If a `---` appears but the SAME spiritual arc continues \
  uninterrupted (rare): do NOT split. Mark confidence "low" on \
  the next boundary you do identify.
- If NO `---` appears but the text clearly shifts to a wholly \
  different spiritual subject mid-chapter: still mark a boundary, \
  but this should be rare.

### WHAT TO OUTPUT

For each teaching you identify, provide:
- The §N section number where it STARTS
- A brief title describing what is being TAUGHT (the spiritual \
  content, not just the imagery). E.g. "How light is freed from \
  captivity through five stages" rather than just "Five Salvations."
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
    Inserts `---` between chapters as structural markers.
    """
    parts: list[str] = []
    section_map: list[dict] = []  # index i → §(i+1)
    prev_chapter_had_content = False

    for ch in chapters:
        cn = ch["chapter_num"]
        chapter_has_content = any(
            seg.get("classification", "") in ("cosmological_substrate", "mixed")
            and seg.get("core_coptic")
            for seg in ch["segments"]
        )
        if not chapter_has_content:
            continue

        # Insert separator between chapters (not before the first)
        if prev_chapter_had_content:
            parts.append("---")

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

        prev_chapter_had_content = True

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
