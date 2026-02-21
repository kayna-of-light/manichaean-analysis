#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Apply corpus review corrections to the interleaved text.

Pipeline phase:  stage_6_review  ->  stage_7_correct

Reads findings from corpus_review.json, loads the full interleaved
corpus (same view that stage_6 reviewed), and iterates through each
actionable finding.  For each finding:

  1. A fresh single-turn request presents the CURRENT corpus text
     plus the finding as an action to execute.
  2. Claude responds with CRUD tool calls (replace, delete, insert,
     or skip).
  3. The tool calls are applied to the in-memory text immediately.
  4. A markdown checkpoint is saved.
  5. The loop advances to the next finding with the updated text.

No chat history is kept -- every call is a fresh context with the
latest text and the current finding.  This prevents token inflation
and ensures the model always sees the most up-to-date corpus.

The output is a MARKDOWN document of the fully corrected corpus text.
No editorial notes or annotations are added.  The focus is always on
restoring the most probable core substrate.

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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import tools.corpus_base as corpus_base
from tools.corpus_base import (
    configure_paths,
    create_claude_client,
    stream_tool_calls,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACTIONABLE_CATEGORIES = {
    "naming_overlay",
    "residual_editorial",
    "over_stripped",
    "misplaced_content",
    "inconsistent_extraction",
}

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert in the doctrine of correspondences as written by \
Emanuel Swedenborg, with deep specialization in ancient cosmological \
vocabulary -- Zoroastrian, Manichaean, and Persian-Iranian traditions.

You translate text from its natural sense into its spiritual sense. \
Not annotation, not commentary -- translation. Every natural image is \
replaced by the spiritual reality it expresses through correspondence. \
Light = wisdom, darkness = falsity, fire = love (or self-love in \
opposite sense), water = truth, garments = external truths, \
trees = perceptions, fruits = works, animals = affections, \
mountains = elevated states, seeds = interior truths, \
vessels = containing forms.

CONTEXT:

You are given the COMPLETE extracted teaching substrate of the \
Coptic Kephalaia. This substrate is the oldest layer of the text -- \
Persian correspondential teaching that predates Mani's editorial \
compilation. It IS the Ancient Word in its Persian vessel.

The text is presented as a continuous flow of numbered paragraphs. \
Each paragraph has a marker [SECTION-N]. Lines marked [SECTION-N]* are \
correspondential readings -- translations from the natural into the \
spiritual sense. These help you understand what the text is saying.

TASK:

You receive one FINDING from a corpus-wide analytic review. The \
finding identifies a specific extraction artifact in the text -- \
a naming overlay, residual editorial material, over-stripped \
content, misplaced material, or an inconsistent extraction.

Your job: execute the recommended correction using the tools \
provided. Make targeted, surgical edits. Change ONLY what the \
finding calls for.

CORRECTION PRINCIPLES:

- naming_overlay -- A Manichaean or Christian editorial name was \
  mapped onto a substrate entity. The finding's recommendation \
  contains the proposed replacement name. Apply it. The replacement \
  will be a plausible substrate-native name -- typically the entity \
  title with a Christian prefix stripped (e.g. "Jesus the Splendour" \
  -> "the Splendour"), or a Persian-tradition equivalent. \
  DO NOT replace names with functional descriptions ("the illumined \
  understanding," "the new regenerated faculty"). The core text is \
  the NATURAL sense -- it must read as an authentic ancient teaching \
  text with proper names, not as a correspondential translation. \
  The [SECTION-N]* lines already provide the correspondential reading. \
  ALSO update the correspondential reading ([SECTION-N]* line) only \
  if the name change affects how the passage should be translated \
  into the spiritual sense.

- residual_editorial -- Non-substrate material (bridge connectives, \
  institutional vocabulary, devotional exhortations) that slipped \
  through extraction into the core text. Remove it. If removing \
  material leaves an awkward seam, smooth the transition minimally. \
  Update the correspondential reading to exclude the removed material.

- over_stripped -- Genuine substrate content was removed during \
  extraction, leaving a gap or discontinuity. If the finding and \
  surrounding context provide enough information to reconstruct \
  what was lost, restore it. Write in the register of the text \
  itself -- impersonal, structural, expository. If the content \
  cannot be reconstructed, note a lacuna marker. Update the \
  correspondential reading accordingly.

- misplaced_content -- Text that belongs to a different teaching \
  sequence. Do NOT move it (that requires structural decisions \
  beyond this correction stage). Instead, skip this finding.

- inconsistent_extraction -- The same type of content was treated \
  differently across chapters. Apply the correction that brings \
  consistency with the corpus-wide extraction standard.

RULES:
- Do NOT add editorial notes, footnotes, brackets, or annotations \
  of any kind. No "[Correction: ...]", no "[Note: ...]".
- Do NOT explain your changes in the text itself.
- Preserve [SECTION-N] and [SECTION-N]* markers exactly.
- Maintain the same scholarly register and prose style.
- If a finding is not actionable or would damage the text, use \
  skip_finding.
- Apply corrections to BOTH the core text ([SECTION-N] lines) AND the \
  correspondential readings ([SECTION-N]* lines) when both are affected.
- Make as many tool calls as needed in a single response.\
"""

# Replace placeholder with actual section marker
SYSTEM_PROMPT = SYSTEM_PROMPT.replace("SECTION-N", "\u00a7N")  # §N

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "replace_text",
        "description": (
            "Replace specific text in the corpus. Include enough context "
            "in old_text to uniquely identify the target passage. Use the "
            "section marker as a context anchor for disambiguation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "old_text": {
                    "type": "string",
                    "description": (
                        "The exact text to find and replace. Must match "
                        "the corpus text verbatim, including whitespace. "
                        "Include the section marker or nearby context to "
                        "ensure uniqueness."
                    ),
                },
                "new_text": {
                    "type": "string",
                    "description": (
                        "The replacement text. Must maintain the same "
                        "register and style as the surrounding text."
                    ),
                },
            },
            "required": ["old_text", "new_text"],
        },
    },
    {
        "name": "delete_text",
        "description": (
            "Delete specific text from the corpus. Include enough context "
            "to uniquely identify the target passage."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text_to_delete": {
                    "type": "string",
                    "description": (
                        "The exact text to remove. Must match verbatim."
                    ),
                },
            },
            "required": ["text_to_delete"],
        },
    },
    {
        "name": "insert_after",
        "description": (
            "Insert new text immediately after an anchor passage. Use "
            "this to restore over-stripped content."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "anchor_text": {
                    "type": "string",
                    "description": (
                        "Existing text after which to insert. Must match "
                        "verbatim. Include section marker for disambiguation."
                    ),
                },
                "new_text": {
                    "type": "string",
                    "description": (
                        "The text to insert after the anchor."
                    ),
                },
            },
            "required": ["anchor_text", "new_text"],
        },
    },
    {
        "name": "skip_finding",
        "description": (
            "Explicitly skip this finding -- no textual change needed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": (
                        "Why this finding is being skipped."
                    ),
                },
            },
            "required": ["reason"],
        },
    },
]

# ---------------------------------------------------------------------------
# Review loading
# ---------------------------------------------------------------------------


def load_review(review_path: Path) -> dict:
    """Load corpus review JSON."""
    with open(review_path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Tool-call application
# ---------------------------------------------------------------------------


def apply_tool_call(
    name: str,
    args: dict,
    corpus_text: str,
) -> tuple:
    """Apply a single tool call to the corpus text.

    Returns:
        (updated_text, description)
    """
    if name == "replace_text":
        old = args["old_text"]
        new = args["new_text"]
        count = corpus_text.count(old)
        if count == 0:
            return corpus_text, "WARN: old_text not found ({})".format(old[:60])
        if count > 1:
            # Replace only the first occurrence
            idx = corpus_text.index(old)
            corpus_text = (
                corpus_text[:idx] + new + corpus_text[idx + len(old):]
            )
            return corpus_text, (
                "replace (1/{} occurrences): {}... -> {}...".format(
                    count, old[:50], new[:50]
                )
            )
        return corpus_text.replace(old, new), (
            "replace: {}... -> {}...".format(old[:50], new[:50])
        )

    elif name == "delete_text":
        target = args["text_to_delete"]
        count = corpus_text.count(target)
        if count == 0:
            return corpus_text, "WARN: text not found ({})".format(target[:60])
        # Delete first occurrence, clean up triple-newlines
        idx = corpus_text.index(target)
        corpus_text = (
            corpus_text[:idx] + corpus_text[idx + len(target):]
        )
        corpus_text = re.sub(r"\n{3,}", "\n\n", corpus_text)
        return corpus_text, "delete: {}...".format(target[:60])

    elif name == "insert_after":
        anchor = args["anchor_text"]
        new = args["new_text"]
        if anchor not in corpus_text:
            return corpus_text, (
                "WARN: anchor not found ({})".format(anchor[:60])
            )
        idx = corpus_text.index(anchor) + len(anchor)
        corpus_text = (
            corpus_text[:idx] + "\n\n" + new + corpus_text[idx:]
        )
        return corpus_text, "insert after: {}... (+{} chars)".format(
            anchor[:40], len(new)
        )

    elif name == "skip_finding":
        reason = args.get("reason", "no reason given")
        return corpus_text, "skip: {}".format(reason)

    else:
        return corpus_text, "WARN: unknown tool '{}'".format(name)


# ---------------------------------------------------------------------------
# Finding formatter
# ---------------------------------------------------------------------------


def format_finding(finding: dict) -> str:
    """Format a single finding as the action block for the user message."""
    refs = ", ".join(finding.get("section_refs", []))
    return (
        "## Action: Finding #{} -- {} ({})\n\n"
        "**Title:** {}\n\n"
        "**Section refs:** {}\n\n"
        "**Current state:** {}\n\n"
        "**Recommendation:** {}\n\n"
        "**Explanation:** {}\n\n"
        "Execute this correction using the tools provided. Apply "
        "the recommended change to every occurrence listed in the "
        "section refs. If the finding is not actionable, call "
        "skip_finding."
    ).format(
        finding["id"],
        finding["category"],
        finding["severity"],
        finding["title"],
        refs,
        finding.get("current_state", ""),
        finding.get("recommendation", ""),
        finding.get("explanation", ""),
    )


# ---------------------------------------------------------------------------
# Markdown output
# ---------------------------------------------------------------------------


def save_markdown(corpus_text: str, output_path: Path) -> None:
    """Save the current corpus text as a markdown file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(corpus_text)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Apply corpus review corrections to the interleaved text.",
    )
    p.add_argument(
        "--project",
        default="kephalaia",
        help="Project name (default: kephalaia)",
    )
    p.add_argument(
        "--finding",
        type=int,
        default=None,
        help="Process only this finding number",
    )
    p.add_argument(
        "--range",
        type=str,
        default=None,
        help="Process finding range, e.g. '1-5'",
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
        "--review-file",
        type=str,
        default=None,
        help="Path to corpus_review.json (default: auto-detect)",
    )
    p.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output markdown path (default: <project>/corrected_corpus.md)",
    )
    p.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Resume from a previous run by loading the latest "
            "checkpoint as the starting corpus text"
        ),
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    args = parse_args()
    configure_paths(args.project)

    # Locate review file
    if args.review_file:
        review_path = Path(args.review_file)
    else:
        review_path = corpus_base.OUTPUT_DIR / "corpus_review.json"
    if not review_path.exists():
        print("ERROR: Review file not found: {}".format(review_path))
        print("  Run stage_6_review.py first.")
        sys.exit(1)

    print("=== Apply Corpus Review: {} ===\n".format(args.project))
    print("Review file: {}".format(review_path))

    # Load review
    review = load_review(review_path)
    total_findings = len(review["findings"])
    actionable = [
        f for f in review["findings"]
        if f["category"] in ACTIONABLE_CATEGORIES
    ]
    non_actionable = [
        f for f in review["findings"]
        if f["category"] not in ACTIONABLE_CATEGORIES
    ]
    print("Total findings: {}".format(total_findings))
    print("Actionable: {}".format(len(actionable)))
    print("Non-actionable (skipped): {}".format(len(non_actionable)))

    if non_actionable:
        for f in non_actionable:
            title = f["title"][:70].encode("ascii", "replace").decode()
            print("    skip #{} [{}] {}".format(f["id"], f["category"], title))

    # Determine which findings to process
    if args.finding is not None:
        findings_to_process = [
            f for f in actionable if f["id"] == args.finding
        ]
        if not findings_to_process:
            print("\nFinding #{} not found or not actionable.".format(
                args.finding
            ))
            return
    elif args.range:
        m = re.match(r"(\d+)-(\d+)", args.range)
        if not m:
            print("ERROR: Invalid range. Use '1-5'")
            sys.exit(1)
        rstart, rend = int(m.group(1)), int(m.group(2))
        findings_to_process = [
            f for f in actionable if rstart <= f["id"] <= rend
        ]
    else:
        findings_to_process = actionable

    if not findings_to_process:
        print("No findings to process.")
        return

    # Output paths
    corrected_dir = corpus_base.OUTPUT_DIR / "corrected"
    corrected_dir.mkdir(parents=True, exist_ok=True)
    output_path = (
        Path(args.output) if args.output
        else corrected_dir / "corrected_corpus.md"
    )
    checkpoint_dir = corrected_dir / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    log_path = corrected_dir / "correction_log.json"

    # Load corpus text
    if args.resume and output_path.exists():
        print("\nResuming from: {}".format(output_path))
        with open(output_path, encoding="utf-8") as f:
            corpus_text = f.read()
        print("  Loaded {:,} chars".format(len(corpus_text)))
    else:
        print("\nLoading corpus...")
        chapters = corpus_base.load_all_chapters()
        print("  Loaded {} chapters".format(len(chapters)))
        print("Interleaving core text + spiritual readings...")
        corpus_text, section_map = corpus_base.format_corpus_interleaved(
            chapters
        )
        print("  Corpus: {:,} chars".format(len(corpus_text)))

    est_tokens = len(corpus_text) / 3.5
    print("  Estimated tokens: ~{:,.0f}".format(est_tokens))

    # Preview
    print("\nWill process {} findings:\n".format(len(findings_to_process)))
    for f in findings_to_process:
        title = f["title"][:65].encode("ascii", "replace").decode()
        print("  #{:>2d} [{}] ({}) {}".format(
            f["id"], f["category"], f["severity"], title
        ))

    if args.dry_run:
        print("\n[DRY RUN] No API calls made.")
        return

    # Create client
    print("\nConnecting to Claude Opus 4.6...")
    client, deployment = create_claude_client()
    print("Using model: {}\n".format(deployment))

    # Process findings one at a time
    correction_log = []
    t_total = time.time()

    for idx, finding in enumerate(findings_to_process, 1):
        fid = finding["id"]
        cat = finding["category"]
        title = finding["title"][:60].encode("ascii", "replace").decode()
        n_refs = len(finding.get("section_refs", []))

        print(
            "[{}/{}] Finding #{} [{}] ({} refs) {}".format(
                idx, len(findings_to_process), fid, cat, n_refs, title
            )
        )

        # Build fresh user message: full corpus + action
        action_block = format_finding(finding)
        user_message = (
            "## Corpus Text\n\n"
            "{}\n\n"
            "---\n\n"
            "{}"
        ).format(corpus_text, action_block)

        # Stream
        t0 = time.time()
        tool_calls, text_output = stream_tool_calls(
            client,
            deployment,
            system_prompt=SYSTEM_PROMPT,
            tools=TOOLS,
            user_message=user_message,
            max_tokens=128_000,
            debug=args.debug,
        )
        elapsed = time.time() - t0

        # Apply tool calls
        changes = []
        n_applied = 0
        n_warnings = 0
        skipped = False

        for tool_name, tool_args in tool_calls:
            corpus_text, desc = apply_tool_call(
                tool_name, tool_args, corpus_text
            )
            changes.append("  {}: {}".format(tool_name, desc))
            if tool_name == "skip_finding":
                skipped = True
            elif desc.startswith("WARN:"):
                n_warnings += 1
            else:
                n_applied += 1

        # Summary for this finding
        if skipped:
            status = "skipped"
            print("  -> SKIPPED ({:.1f}s)".format(elapsed))
        elif not tool_calls:
            status = "no_response"
            print("  -> NO TOOL CALLS ({:.1f}s)".format(elapsed))
            if text_output:
                print("    Text: {}".format(text_output[:200]))
        else:
            status = "applied"
            print(
                "  -> {} edits applied, {} warnings ({:.1f}s)".format(
                    n_applied, n_warnings, elapsed
                )
            )

        if args.debug:
            for c in changes:
                print(c)

        # Log
        log_entry = {
            "finding_id": fid,
            "category": cat,
            "status": status,
            "tool_calls": len(tool_calls),
            "edits_applied": n_applied,
            "warnings": n_warnings,
            "elapsed_s": round(elapsed, 1),
            "changes": [
                {"tool": tn, "args_summary": _summarize_args(ta)}
                for tn, ta in tool_calls
            ],
        }
        if text_output and status != "applied":
            log_entry["text_output"] = text_output[:500]
        correction_log.append(log_entry)

        # Save checkpoint
        cp_path = checkpoint_dir / "after_finding_{:03d}.md".format(fid)
        save_markdown(corpus_text, cp_path)

        # Save current state as the main output (resumable)
        save_markdown(corpus_text, output_path)

    # Final summary
    total_elapsed = time.time() - t_total
    applied = [e for e in correction_log if e["status"] == "applied"]
    skipped_entries = [e for e in correction_log if e["status"] == "skipped"]
    no_resp = [e for e in correction_log if e["status"] == "no_response"]
    total_edits = sum(e["edits_applied"] for e in correction_log)
    total_warnings = sum(e["warnings"] for e in correction_log)

    print("\n" + "=" * 60)
    print("CORRECTION SUMMARY")
    print("  Findings processed: {}".format(len(findings_to_process)))
    print("  Applied:  {}".format(len(applied)))
    print("  Skipped:  {}".format(len(skipped_entries)))
    print("  No response: {}".format(len(no_resp)))
    print("  Total edits: {}".format(total_edits))
    print("  Total warnings: {}".format(total_warnings))
    print("  Time: {:.1f}s".format(total_elapsed))
    print("\n  Output: {}".format(output_path))
    print("  Checkpoints: {}".format(checkpoint_dir))

    # Save log
    log_data = {
        "review_file": str(review_path),
        "project": args.project,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "findings_processed": len(findings_to_process),
        "findings_applied": len(applied),
        "findings_skipped": len(skipped_entries),
        "total_edits": total_edits,
        "total_warnings": total_warnings,
        "elapsed_s": round(total_elapsed, 1),
        "entries": correction_log,
    }
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)
    print("  Log: {}".format(log_path))
    print("Done.")


def _summarize_args(args: dict) -> str:
    """Produce a short summary of tool-call args for the log."""
    parts = []
    for k, v in args.items():
        s = str(v)
        if len(s) > 80:
            s = s[:77] + "..."
        parts.append("{}={}".format(k, repr(s)))
    return "; ".join(parts)


if __name__ == "__main__":
    main()
