#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Apply corpus review corrections to correspondential chapter files.

Pipeline phase:  analyze_corpus  →  apply_review

Reads findings from corpus_review.json, resolves §-references to
manuscript chapters, then sends each affected chapter to Claude
with its applicable corrections for direct text rewriting.

Corrections target THREE data layers (in priority order):
  1. Reconstructions  – gap-filled core text (PRIMARY output)
  2. Fills            – individual gap-fill decisions
  3. Spiritual reading – correspondential translation (secondary)

Corrected files are written to a separate corrected/chapters/ folder,
leaving the correspondential phase output untouched.

No editorial notes, annotations, or bracketed explanations are added.

Primary model: Claude Opus 4.6 via Azure AI Foundry (AnthropicFoundry).
"""

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import argparse
import json
import re
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
from anthropic import AnthropicFoundry

sys.path.insert(0, str(Path(__file__).parent))
import tools.corpus_base as corpus_base
from tools.corpus_base import (
    configure_paths,
    create_claude_client,
    stream_tool_call,
)
from project_config import load_project, list_projects, SECRETS_PATH

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACTIONABLE_CATEGORIES = {
    "mistranslation",
    "inconsistency",
    "opposite_sense_error",
    "untranslated_natural",
    "missed_pre_manichaean",
}

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a text corrector for a Manichaean manuscript reconstruction project.

You receive three data layers for a single chapter plus correction findings
from a corpus-wide analytic review:

  1. RECONSTRUCTIONS — The gap-filled core text. This is the PRIMARY output.
     Each entry is {paragraph, reconstructed_text}. The reconstructed_text
     is the best scholarly reconstruction of what the manuscript originally
     said, with lacunae filled.

  2. FILLS — Individual gap-fill decisions. Each entry is
     {paragraph, gap_id, fill, explanation, ...}. The "fill" field is the
     text that was placed into a lacuna.

  3. SPIRITUAL READING — A correspondential translation that reads the
     natural text through a symbolic lens. Uses **¶N:** paragraph markers
     and [GAP-N] markers. This is a SECONDARY interpretive layer.

You also receive:
  - The original core text (pre-gap-fill) for reference
  - A §-to-¶ mapping for resolving corpus-wide §-references

Your task: Apply the corrections to ALL THREE layers.

RULES — FOLLOW EXACTLY:
• Apply every applicable correction across all layers where it is relevant.
• The reconstructed text is the primary artifact — correct it FIRST.
• If a fill introduced wrong terminology, correct the fill text too.
• Then update the spiritual reading to be consistent.
• Do NOT add editorial notes, footnotes, translator's notes, or bracketed
  annotations of any kind (no "[Note: ...]", no "[Correction: ...]").
• Do NOT add explanatory asides about why a change was made.
• Do NOT change anything that is NOT addressed by a finding.
• Preserve paragraph numbers in reconstructions.
• Preserve **¶N:** paragraph structure in the spiritual reading.
• Preserve ALL [GAP-N] markers in the spiritual reading exactly.
• Maintain the same scholarly register and prose style as the original.

CORRECTION TYPES:
• mistranslation — A figure or concept is identified incorrectly.
  Fix the identification in the reconstruction, fills, and SR.

• inconsistency — The same figure or concept is named differently
  across chapters. Apply the proposed harmonised name/reading.
  This often affects reconstructions directly (e.g. "Mother of Life"
  vs "Mother of the Living" — harmonise the translation).

• opposite_sense_error — A correspondence is read in the wrong sense
  (e.g. interior/exterior inverted). Likely affects SR primarily,
  but check if the error leaked into fill explanations too.

• untranslated_natural — Natural-sense vocabulary that should have been
  translated correspondentially. Likely SR-only.

• missed_pre_manichaean — A Manichaean editorial overlay name masks an
  older teaching figure. In the RECONSTRUCTION, the Manichaean name
  may be the manuscript's actual wording — correct it only if a FILL
  introduced the Manichaean name (i.e. the gap was filled with a
  Manichaean overlay term when something older fits better).
  In the SPIRITUAL READING, replace the Manichaean name with the
  pre-Manichaean identification. For example:
    - "Third Ambassador" → the mediating divine principle
    - "Jesus the Splendour" → the radiance of divine wisdom / xvarənah
  Do NOT add notes about the replacement — just make the change.

OUTPUT:
Use the commit_corrected_chapter tool to return:
  - ALL reconstructions (full list, even unchanged paragraphs)
  - Only MODIFIED fills (by gap_id, with new fill text and explanation)
  - The COMPLETE spiritual reading text
  - A change log describing what was corrected and in which layer\
"""

# ---------------------------------------------------------------------------
# Tool definition
# ---------------------------------------------------------------------------

CORRECT_CHAPTER_TOOL = {
    "name": "commit_corrected_chapter",
    "description": (
        "Submit corrected reconstructions, fills, and spiritual reading "
        "for this chapter."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "corrected_reconstructions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "paragraph": {
                            "type": "integer",
                            "description": "Paragraph number.",
                        },
                        "reconstructed_text": {
                            "type": "string",
                            "description": "Full reconstructed text.",
                        },
                    },
                    "required": ["paragraph", "reconstructed_text"],
                },
                "description": (
                    "The COMPLETE list of reconstructed paragraphs with "
                    "corrections applied. Include ALL paragraphs, even "
                    "unchanged ones."
                ),
            },
            "corrected_fills": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "gap_id": {
                            "type": "string",
                            "description": "The GAP-N identifier.",
                        },
                        "fill": {
                            "type": "string",
                            "description": "The corrected fill text.",
                        },
                        "explanation": {
                            "type": "string",
                            "description": (
                                "Updated explanation for the fill. "
                                "Omit if explanation doesn't change."
                            ),
                        },
                    },
                    "required": ["gap_id", "fill"],
                },
                "description": (
                    "Only the MODIFIED fill entries. Omit fills that "
                    "did not change. Empty array if no fills changed."
                ),
            },
            "corrected_spiritual_reading": {
                "type": "string",
                "description": (
                    "The COMPLETE corrected spiritual reading for this "
                    "chapter, with all findings applied. Must use the same "
                    "**¶N:** paragraph markers as the original. Include "
                    "ALL paragraphs, even unchanged ones."
                ),
            },
            "changes_made": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "finding_id": {
                            "type": "integer",
                            "description": "ID of the finding applied.",
                        },
                        "paragraphs_affected": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": (
                                "Paragraph numbers changed."
                            ),
                        },
                        "description": {
                            "type": "string",
                            "description": (
                                "Brief description of what was changed."
                            ),
                        },
                        "targets": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": [
                                    "reconstruction",
                                    "fill",
                                    "spiritual_reading",
                                ],
                            },
                            "description": (
                                "Which data layers were modified."
                            ),
                        },
                    },
                    "required": [
                        "finding_id",
                        "paragraphs_affected",
                        "description",
                        "targets",
                    ],
                },
                "description": (
                    "List of changes made, one entry per finding applied."
                ),
            },
        },
        "required": [
            "corrected_reconstructions",
            "corrected_fills",
            "corrected_spiritual_reading",
            "changes_made",
        ],
    },
}

# ---------------------------------------------------------------------------
# Review loading and resolution
# ---------------------------------------------------------------------------


def load_review(review_path: Path) -> tuple[dict, dict[int, tuple[int, int]]]:
    """Load corpus review and build chapter→section-range map.

    Returns (review_dict, ch_map) where ch_map maps
    ms_chapter → (section_start, section_end).
    """
    with open(review_path, encoding="utf-8") as f:
        review = json.load(f)

    ch_map: dict[int, tuple[int, int]] = {}
    for entry in review["_section_map"]:
        ch_map[entry["ms_chapter"]] = (
            entry["section_start"],
            entry["section_end"],
        )
    return review, ch_map


def resolve_section_ref(ref: str) -> int | None:
    """Parse '§240' → 240."""
    m = re.search(r"\d+", str(ref))
    return int(m.group()) if m else None


def resolve_to_chapter(
    sec_num: int, ch_map: dict[int, tuple[int, int]]
) -> int | None:
    """Find which ms_chapter contains §sec_num."""
    for ch_num, (start, end) in ch_map.items():
        if start <= sec_num <= end:
            return ch_num
    return None


def group_findings_by_chapter(
    review: dict, ch_map: dict[int, tuple[int, int]]
) -> dict[int, list[dict]]:
    """Group actionable findings by affected chapter number.

    Returns dict of ms_chapter → list of findings (de-duplicated).
    """
    chapter_findings: dict[int, list[dict]] = {}
    for f in review["findings"]:
        if f["category"] not in ACTIONABLE_CATEGORIES:
            continue
        chapters_seen: set[int] = set()
        for ref in f.get("section_refs", []):
            sec_num = resolve_section_ref(ref)
            if sec_num is None:
                continue
            ch = resolve_to_chapter(sec_num, ch_map)
            if ch is not None and ch not in chapters_seen:
                chapters_seen.add(ch)
                chapter_findings.setdefault(ch, []).append(f)

    return chapter_findings


# ---------------------------------------------------------------------------
# §-to-¶ mapping builder
# ---------------------------------------------------------------------------


def build_section_para_map(
    core_data: dict,
    section_start: int,
) -> dict[int, int]:
    """Build mapping from § number to ¶ number for a chapter.

    Returns dict of §N → ¶M based on paragraph ordering in core_data.
    """
    mapping: dict[int, int] = {}
    seq = section_start
    for p in core_data.get("paragraphs", []):
        if p.get("core_text"):
            mapping[seq] = p["paragraph_number"]
            seq += 1
    return mapping


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def build_correction_prompt(
    ch_num: int,
    corr_data: dict,
    core_data: dict,
    findings: list[dict],
    sec_para_map: dict[int, int],
) -> str:
    """Build the user message for correcting one chapter.

    Includes all three data layers: reconstructions, fills, and SR.
    """
    title = corr_data.get("chapter_title", "")

    # --- 1. Reconstructions (PRIMARY) ---
    recs = corr_data.get("reconstructions", [])
    rec_lines = []
    for r in recs:
        rec_lines.append(
            f"¶{r['paragraph']}: {r['reconstructed_text']}"
        )
    rec_text = "\n\n".join(rec_lines) if rec_lines else "(no reconstructions)"

    # --- 2. Fills ---
    fills = corr_data.get("fills", [])
    fill_lines = []
    for fl in fills:
        expl = fl.get("explanation", "")[:120]
        fill_lines.append(
            f"- {fl['gap_id']} (¶{fl['paragraph']}): "
            f"fill={fl['fill']!r}  |  explanation: {expl}"
        )
    fills_text = "\n".join(fill_lines) if fill_lines else "(no fills)"

    # --- 3. Spiritual Reading (secondary) ---
    sr_text = corr_data.get("spiritual_reading", "")

    # --- 4. Original core text (pre-gap-fill, for reference) ---
    core_lines = []
    for p in core_data.get("paragraphs", []):
        if p.get("core_text"):
            core_lines.append(f"¶{p['paragraph_number']}: {p['core_text']}")
    core_text = "\n\n".join(core_lines)

    # §-to-¶ mapping display
    if sec_para_map:
        map_items = [f"§{s}=¶{p}" for s, p in sorted(sec_para_map.items())]
        map_display = ", ".join(map_items)
    else:
        map_display = "(no mapping available)"

    # Format findings
    findings_parts = []
    for f in findings:
        refs = ", ".join(f.get("section_refs", []))
        findings_parts.append(
            f"### Finding #{f['id']} — {f['category']} ({f['severity']})\n"
            f"**Title:** {f['title']}\n"
            f"**Section refs:** {refs}\n"
            f"**Current reading:** {f['current_reading']}\n"
            f"**Proposed reading:** {f['proposed_reading']}\n"
            f"**Explanation:** {f['explanation']}"
        )
    findings_block = "\n\n---\n\n".join(findings_parts)

    return (
        f"## Manuscript Chapter {ch_num}: {title}\n\n"
        f"### §-to-¶ Mapping\n"
        f"{map_display}\n\n"
        f"### Current Reconstructions (PRIMARY — gap-filled text)\n\n"
        f"{rec_text}\n\n"
        f"### Current Fills (gap-fill decisions)\n\n"
        f"{fills_text}\n\n"
        f"### Current Spiritual Reading (secondary)\n\n"
        f"{sr_text}\n\n"
        f"### Original Core Text (pre-gap-fill, for reference)\n\n"
        f"{core_text}\n\n"
        f"### Correction Findings\n\n"
        f"{findings_block}\n\n"
        f"Apply all applicable corrections across ALL layers. "
        f"Correct the reconstructed text first, then fills if affected, "
        f"then the spiritual reading. Return via commit_corrected_chapter."
    )


# ---------------------------------------------------------------------------
# Per-chapter processing
# ---------------------------------------------------------------------------


def process_chapter(
    client: AnthropicFoundry,
    deployment: str,
    ch_num: int,
    findings: list[dict],
    ch_map: dict[int, tuple[int, int]],
    output_dir: Path,
    *,
    debug: bool = False,
) -> dict | None:
    """Process a single chapter: load, correct all layers, save.

    Reads from correspondential/chapters (input), writes to
    output_dir (corrected/chapters). Never overwrites input files.
    Returns a summary dict on success, None on failure.
    """
    corr_path = corpus_base.CORR_CHAPTERS_DIR / f"ch_{ch_num:03d}.json"
    core_path = corpus_base.CORE_CHAPTERS_DIR / f"ch_{ch_num:03d}.json"

    if not corr_path.exists():
        return {"ch": ch_num, "status": "skip", "reason": "no corr file"}
    if not core_path.exists():
        return {"ch": ch_num, "status": "skip", "reason": "no core file"}

    # Load data
    with open(corr_path, encoding="utf-8") as f:
        corr_data = json.load(f)
    with open(core_path, encoding="utf-8") as f:
        core_data = json.load(f)

    # Build §→¶ map
    section_start = ch_map.get(ch_num, (0, 0))[0]
    sec_para_map = build_section_para_map(core_data, section_start)

    # Build prompt
    prompt = build_correction_prompt(
        ch_num, corr_data, core_data, findings, sec_para_map
    )

    if debug:
        print(f"\n--- Prompt for ch_{ch_num:03d} ({len(prompt)} chars) ---")

    # Call Claude
    tool_input, text_output = stream_tool_call(
        client,
        deployment,
        system_prompt=SYSTEM_PROMPT,
        tools=[CORRECT_CHAPTER_TOOL],
        expected_tool_name="commit_corrected_chapter",
        corpus_text=prompt,
        max_tokens=32_000,
        debug=debug,
    )

    if tool_input is None:
        return {
            "ch": ch_num,
            "status": "error",
            "reason": "no tool call returned",
            "text_output": text_output[:500] if text_output else "",
        }

    # --- Extract results ---
    corrected_recs = tool_input.get("corrected_reconstructions", [])
    corrected_fills = tool_input.get("corrected_fills", [])
    corrected_sr = tool_input.get("corrected_spiritual_reading", "")
    changes_made = tool_input.get("changes_made", [])

    # --- Validate reconstructions ---
    original_rec_paras = {
        r["paragraph"] for r in corr_data.get("reconstructions", [])
    }
    corrected_rec_paras = {r["paragraph"] for r in corrected_recs}
    missing_rec_paras = original_rec_paras - corrected_rec_paras
    if missing_rec_paras:
        return {
            "ch": ch_num,
            "status": "error",
            "reason": (
                f"missing paragraphs in corrected reconstructions: "
                f"{sorted(missing_rec_paras)}"
            ),
        }

    # --- Validate SR paragraph markers ---
    if not corrected_sr.strip():
        return {
            "ch": ch_num,
            "status": "error",
            "reason": "empty corrected SR returned",
        }

    original_sr_paras = set(
        int(m)
        for m in re.findall(
            r"\*\*¶(\d+):\*\*", corr_data.get("spiritual_reading", "")
        )
    )
    corrected_sr_paras = set(
        int(m) for m in re.findall(r"\*\*¶(\d+):\*\*", corrected_sr)
    )
    missing_sr_paras = original_sr_paras - corrected_sr_paras
    if missing_sr_paras:
        return {
            "ch": ch_num,
            "status": "error",
            "reason": (
                f"missing paragraphs in corrected SR: "
                f"{sorted(missing_sr_paras)}"
            ),
        }

    # --- Validate fill gap_ids ---
    existing_fill_ids = {
        fl["gap_id"] for fl in corr_data.get("fills", [])
    }
    for cf in corrected_fills:
        if cf["gap_id"] not in existing_fill_ids:
            return {
                "ch": ch_num,
                "status": "error",
                "reason": (
                    f"corrected fill references unknown gap_id: "
                    f"{cf['gap_id']}"
                ),
            }

    # --- Apply reconstructions ---
    corr_data["reconstructions"] = [
        {"paragraph": r["paragraph"], "reconstructed_text": r["reconstructed_text"]}
        for r in corrected_recs
    ]

    # --- Apply fills (merge by gap_id) ---
    if corrected_fills:
        fill_updates = {cf["gap_id"]: cf for cf in corrected_fills}
        for fl in corr_data.get("fills", []):
            if fl["gap_id"] in fill_updates:
                update = fill_updates[fl["gap_id"]]
                fl["fill"] = update["fill"]
                if "explanation" in update and update["explanation"]:
                    fl["explanation"] = update["explanation"]

    # --- Apply spiritual reading ---
    corr_data["spiritual_reading"] = corrected_sr

    # --- Save to corrected/ folder ---
    out_path = output_dir / f"ch_{ch_num:03d}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(corr_data, f, indent=2, ensure_ascii=False)

    # Summarise which layers were touched
    layers_touched = set()
    for c in changes_made:
        for t in c.get("targets", []):
            layers_touched.add(t)

    return {
        "ch": ch_num,
        "status": "ok",
        "changes": changes_made,
        "findings_applied": [f["id"] for f in findings],
        "layers": sorted(layers_touched),
    }


# ---------------------------------------------------------------------------
# CLI & main
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Apply corpus review corrections to chapter files.",
    )
    p.add_argument(
        "--project",
        default="kephalaia",
        help="Project name (default: kephalaia)",
    )
    p.add_argument(
        "--chapter",
        type=int,
        default=None,
        help="Process only this chapter number",
    )
    p.add_argument(
        "--range",
        type=str,
        default=None,
        help="Process chapter range, e.g. '4-11'",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be corrected without calling the API",
    )
    p.add_argument(
        "--debug",
        action="store_true",
        help="Show thinking output and verbose logging",
    )
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-process chapters even if already corrected",
    )
    p.add_argument(
        "-j",
        "--concurrency",
        type=int,
        default=1,
        help="Concurrent API calls (default: 1)",
    )
    p.add_argument(
        "--review-file",
        type=str,
        default=None,
        help="Path to corpus_review.json (default: auto-detect)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    configure_paths(args.project)

    # Locate review file
    if args.review_file:
        review_path = Path(args.review_file)
    else:
        review_path = corpus_base.OUTPUT_DIR / "corpus_review.json"
    if not review_path.exists():
        print(f"ERROR: Review file not found: {review_path}")
        print("  Run analyze_corpus.py first.")
        sys.exit(1)

    print(f"=== Apply Corpus Review: {args.project} ===\n")
    print(f"Review file: {review_path}")

    # Load review and build maps
    review, ch_map = load_review(review_path)
    total_findings = len(review["findings"])
    actionable = [
        f for f in review["findings"]
        if f["category"] in ACTIONABLE_CATEGORIES
    ]
    print(f"Total findings: {total_findings}")
    print(f"Actionable findings: {len(actionable)}")

    # Warn about non-actionable findings (can't be fixed by text rewrite)
    skipped = [
        f for f in review["findings"]
        if f["category"] not in ACTIONABLE_CATEGORIES
    ]
    if skipped:
        print(f"\n  Skipping {len(skipped)} non-actionable findings:")
        for f in skipped:
            title = f["title"][:70].encode("ascii", "replace").decode()
            print(
                f"    WARNING: #{f['id']} [{f['category']}] "
                f"{title}"
            )
        print()

    # Group by chapter
    chapter_findings = group_findings_by_chapter(review, ch_map)
    print(f"Chapters affected: {len(chapter_findings)}")

    # Determine scope
    if args.chapter is not None:
        if args.chapter not in chapter_findings:
            print(f"\nChapter {args.chapter} has no applicable findings.")
            return
        chapters_to_process = {args.chapter: chapter_findings[args.chapter]}
    elif args.range:
        m = re.match(r"(\d+)-(\d+)", args.range)
        if not m:
            print("ERROR: Invalid range. Use '4-11'")
            sys.exit(1)
        rstart, rend = int(m.group(1)), int(m.group(2))
        chapters_to_process = {
            ch: findings
            for ch, findings in chapter_findings.items()
            if rstart <= ch <= rend
        }
    else:
        chapters_to_process = chapter_findings

    if not chapters_to_process:
        print("No chapters to process.")
        return

    # Output directory: corrected/chapters/ under project dir
    corrected_dir = corpus_base.OUTPUT_DIR / "corrected" / "chapters"
    corrected_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output dir: {corrected_dir}")

    # Skip already-corrected (check for output file existence)
    if not args.overwrite:
        to_skip = []
        for ch_num in chapters_to_process:
            out = corrected_dir / f"ch_{ch_num:03d}.json"
            if out.exists():
                to_skip.append(ch_num)
        if to_skip:
            print(f"\n  Skipping {len(to_skip)} already-corrected "
                  f"(use --overwrite): {sorted(to_skip)}")
            for ch in to_skip:
                del chapters_to_process[ch]

    if not chapters_to_process:
        print("All applicable chapters already corrected.")
        return

    # Preview
    print(f"\nWill process {len(chapters_to_process)} chapters:\n")
    for ch_num in sorted(chapters_to_process):
        findings = chapters_to_process[ch_num]
        fids = [f"#{f['id']}" for f in findings]
        corr_path = corpus_base.CORR_CHAPTERS_DIR / f"ch_{ch_num:03d}.json"
        exists = "Y" if corr_path.exists() else "N"
        print(f"  ch_{ch_num:03d} [{exists}]  findings: {', '.join(fids)}")

    if args.dry_run:
        # Show finding details
        print(f"\n{'=' * 60}")
        print("FINDING DETAILS (actionable only)\n")
        seen_ids: set[int] = set()
        for ch_num in sorted(chapters_to_process):
            for f in chapters_to_process[ch_num]:
                if f["id"] not in seen_ids:
                    seen_ids.add(f["id"])
                    print(f"  #{f['id']} [{f['category']}] {f['severity']}")
                    print(f"     {f['title'][:80]}")
        print(f"\n[DRY RUN] No API calls made.")
        return

    # Create client
    client, deployment = create_claude_client()
    concurrency = max(1, args.concurrency)
    print(f"\nUsing model: {deployment}")
    print(f"Concurrency: {concurrency}")
    if args.debug and concurrency > 1:
        print("  (debug output disabled with concurrency > 1)")
    print()

    # Process chapters
    print_lock = threading.Lock()
    results: list[dict] = []
    counter = {"done": 0}
    total = len(chapters_to_process)
    ordered_chapters = sorted(chapters_to_process.keys())

    def process_one(ch_num: int) -> None:
        findings = chapters_to_process[ch_num]
        fids = ", ".join(f"#{f['id']}" for f in findings)

        with print_lock:
            print(
                f"  ch_{ch_num:03d} ({len(findings)} findings: {fids})...",
                end="",
                flush=True,
            )

        show_debug = args.debug and concurrency == 1
        result = process_chapter(
            client,
            deployment,
            ch_num,
            findings,
            ch_map,
            corrected_dir,
            debug=show_debug,
        )

        with print_lock:
            counter["done"] += 1
            if result is None:
                status = "FAILED (unknown)"
            elif result["status"] == "ok":
                n_changes = len(result.get("changes", []))
                status = f"OK — {n_changes} changes"
            elif result["status"] == "skip":
                status = f"SKIP — {result.get('reason', '')}"
            else:
                status = f"ERROR — {result.get('reason', '')}"
            print(
                f"\n[{counter['done']}/{total}] ch_{ch_num:03d} {status}"
            )
            results.append(result or {"ch": ch_num, "status": "error"})

    # Execute
    if concurrency == 1:
        for ch_num in ordered_chapters:
            process_one(ch_num)
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {
                executor.submit(process_one, ch): ch
                for ch in ordered_chapters
            }
            for future in as_completed(futures):
                exc = future.exception()
                if exc:
                    ch = futures[future]
                    with print_lock:
                        print(f"\n  ch_{ch:03d} EXCEPTION: {exc}")
                        results.append({"ch": ch, "status": "error",
                                        "reason": str(exc)})

    # Summary
    ok = [r for r in results if r.get("status") == "ok"]
    errors = [r for r in results if r.get("status") == "error"]
    skipped = [r for r in results if r.get("status") == "skip"]

    print(f"\n{'=' * 60}")
    print("CORRECTION SUMMARY")
    print(f"  Processed: {len(ok)}")
    print(f"  Errors:    {len(errors)}")
    print(f"  Skipped:   {len(skipped)}")

    if errors:
        print(f"\n  Failed chapters:")
        for r in errors:
            print(f"    ch_{r['ch']:03d}: {r.get('reason', 'unknown')}")

    if ok:
        total_changes = sum(len(r.get("changes", [])) for r in ok)
        print(f"\n  Total changes applied: {total_changes}")
        for r in ok:
            ch = r["ch"]
            layers = ", ".join(r.get("layers", []))
            if layers:
                print(f"    ch_{ch:03d} layers: {layers}")
            for change in r.get("changes", []):
                fid = change.get("finding_id", "?")
                desc = change.get("description", "")[:60]
                paras = change.get("paragraphs_affected", [])
                targets = change.get("targets", [])
                tgt = "+".join(targets) if targets else "?"
                print(f"    ch_{ch:03d} #{fid} [{tgt}] ¶{paras}: {desc}")

    # Save log
    log_path = corpus_base.OUTPUT_DIR / "review_applied.json"
    log_data = {
        "review_file": str(review_path),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "chapters_processed": len(ok),
        "chapters_errored": len(errors),
        "chapters_skipped": len(skipped),
        "results": results,
    }
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)
    print(f"\n  Log saved: {log_path}")
    print("Done.")


if __name__ == "__main__":
    main()
