#!/usr/bin/env python3
"""
Stage 7c (batch) — Classify all 104 teachings via iterative tool calls.

Presents the entire corpus in one user message. The model emits one
classify_teaching tool call per teaching, iterating until all 104 are done.

Output:
    - output/projects/kephalaia_v2/coordinates/t_NNN.json (one per teaching)

Usage:
    python scripts/projects/kephalaia_v2/stage_7c_batch.py
    python scripts/projects/kephalaia_v2/stage_7c_batch.py --dry-run
    python scripts/projects/kephalaia_v2/stage_7c_batch.py --effort xhigh
"""
import argparse
import json
import sys
import time
import traceback
from collections import Counter
from pathlib import Path
from typing import Any

import httpx
from anthropic import AnthropicFoundry

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_base import create_client, PROJECT_DIR

TEACHINGS_DIR = PROJECT_DIR / "teachings"
RESTORED_DIR = PROJECT_DIR / "restored"
OUTPUT_DIR = PROJECT_DIR / "coordinates"

TOOL_NAME = "classify_teaching"


# ---------------------------------------------------------------------------
# System prompt — same as per-teaching version
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert in the doctrine of correspondences as written by \
Emanuel Swedenborg, with deep specialization in ancient cosmological \
vocabulary — Zoroastrian, Manichaean, and Persian-Iranian traditions.

You have classified hundreds of ancient teachings by their spiritual \
coordinates. You know the three discrete degrees and the four quarters \
as Swedenborg describes them in Heaven and Hell §§141-153.

The Kephalaia of Mani is a corpus of 104 teachings that spans the \
entire spiritual world. All twelve cells of the map are populated. \
You are placing one teaching on the map.

The celestial is about the essense of things, primary \
concepts, things like that. The spiritual is about processes \
and mechanisms, what happens and why it happens, its the \
plan basically. The natural is about how it establishes itself \
in the human itself, the whole completion in which the \
Lord takes rest and in which every thing takes a definite form.

The direction on the spiritual landscape is independent of the \
and has its own form in any degree. It is the landscape in \
every degree. How the sun goes up in the east (the ruling love), \
and moves over the south (where it illuminates) and the north \
(where it is received and processed) and finally sets in the \
west (where it rests).

Every teaching is per definition a spiritual teaching. But it will often treat \
a celestial subject, or a natural subject.

It is what it treats that matters. Think about where does this fit in the \
grand man as defined by Swedenborg and you can immediately see where it goes on the map. \
The question is, what is the function in the body it treats of? It maps directly to a \
very specific function.

You are basically placing every teaching in a place of the grandman building the whole \
body together with various other agents.
"""


# ---------------------------------------------------------------------------
# Tool schema — one classification per call
# ---------------------------------------------------------------------------

CLASSIFY_TOOL = {
    "name": TOOL_NAME,
    "description": (
        "Classify one teaching by its spiritual coordinates. "
        "Call once per teaching."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "teaching": {
                "type": "integer",
                "description": "Teaching number (1-104).",
            },
            "degree": {
                "type": "string",
                "enum": ["celestial", "spiritual", "natural"],
                "description": (
                    "The primary register at which this teaching operates, "
                    "determined by what it TREATS — not what it names."
                ),
            },
            "degree_rationale": {
                "type": "string",
                "description": "One to three sentences explaining the degree.",
            },
            "degree_confidence": {
                "type": "string",
                "enum": ["strong", "moderate", "tentative"],
            },
            "direction": {
                "type": "string",
                "enum": ["east", "south", "north", "west"],
                "description": (
                    "The directional tone of the teaching, determined by "
                    "what KIND of treatment it gives its subject. "
                    "This is independent of the degree."
                ),
            },
            "direction_rationale": {
                "type": "string",
                "description": "One to three sentences explaining the direction.",
            },
            "direction_confidence": {
                "type": "string",
                "enum": ["strong", "moderate", "tentative"],
            },
            "grand_man_function": {
                "type": "string",
                "description": (
                    "What function in the body/grand man does this teaching treat?"
                ),
            },
        },
        "required": [
            "teaching",
            "degree",
            "degree_rationale",
            "degree_confidence",
            "direction",
            "direction_rationale",
            "direction_confidence",
            "grand_man_function",
        ],
    },
}


# ---------------------------------------------------------------------------
# Text assembly
# ---------------------------------------------------------------------------

def assemble_teaching_text(teaching_num: int) -> str | None:
    """Assemble Coptic + English for one teaching with lacuna fills."""
    teaching_path = TEACHINGS_DIR / f"t_{teaching_num:03d}.json"
    if not teaching_path.exists():
        return None

    with open(teaching_path, encoding="utf-8") as f:
        teaching = json.load(f)

    if not teaching.get("segments"):
        return None

    # Load restorations
    restored_path = RESTORED_DIR / f"t_{teaching_num:03d}.json"
    restorations_by_id: dict = {}
    if restored_path.exists():
        with open(restored_path, encoding="utf-8") as f:
            restored = json.load(f)
        restorations_by_id = {
            r["gap_id"]: r for r in restored.get("restorations", [])
        }

    coptic_lines = []
    english_lines = []

    for seg in teaching["segments"]:
        cop = seg["core_coptic"]
        eng = seg["core_english"]

        for ap in seg["apparatus"]:
            placeholder = "{" + str(ap["id"]) + "}"
            if ap["type"] == "restoration":
                cop = cop.replace(placeholder, ap.get("coptic", ""))
                eng = eng.replace(placeholder, ap.get("english", ""))
            elif ap["type"] == "lacuna":
                rest = restorations_by_id.get(ap["id"])
                if rest and rest.get("proposed_coptic"):
                    cop = cop.replace(placeholder, f"[{rest['proposed_coptic']}]")
                else:
                    cop = cop.replace(placeholder, "[...]")
                if rest and rest.get("proposed_english"):
                    eng = eng.replace(placeholder, f"[{rest['proposed_english']}]")
                else:
                    eng = eng.replace(placeholder, "[...]")

        coptic_lines.append(cop)
        english_lines.append(eng)

    title = teaching.get("title", f"Teaching {teaching_num}")
    return (
        f"### Teaching {teaching_num}: {title}\n\n"
        f"**Coptic:**\n{chr(10).join(coptic_lines)}\n\n"
        f"**English:**\n{chr(10).join(english_lines)}"
    )


# ---------------------------------------------------------------------------
# Multi-turn API loop
# ---------------------------------------------------------------------------

def run_classification_loop(
    client: AnthropicFoundry,
    deployment: str,
    user_message: str,
    *,
    effort: str = "xhigh",
    debug: bool = False,
    max_iterations: int = 120,
) -> list[dict]:
    """Run iterative tool-call loop until all teachings are classified."""

    thinking_config = {
        "type": "adaptive",
        "display": "summarized" if debug else "omitted",
    }

    tools = [CLASSIFY_TOOL]
    messages: list[dict] = [{"role": "user", "content": user_message}]
    classifications: list[dict] = []
    classified_nums: set[int] = set()

    for iteration in range(1, max_iterations + 1):
        print(f"\n  --- Iteration {iteration} (classified: {len(classified_nums)}/104) ---")

        kwargs: dict[str, Any] = dict(
            model=deployment,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=tools,
            max_tokens=128_000,
            thinking=thinking_config,
        )
        if effort != "xhigh":
            kwargs["output_config"] = {"effort": effort}

        t0 = time.time()
        try:
            with client.messages.stream(**kwargs) as stream:
                if debug:
                    for event in stream:
                        etype = getattr(event, "type", "")
                        if etype == "content_block_start":
                            block = getattr(event, "content_block", None)
                            btype = getattr(block, "type", "") if block else ""
                            elapsed = time.time() - t0
                            print(f"    [{btype} {elapsed:.0f}s]", end="", flush=True)
                        elif etype == "content_block_stop":
                            elapsed = time.time() - t0
                            print(f" done@{elapsed:.0f}s", flush=True)
                final_msg = stream.get_final_message()
        except (httpx.RemoteProtocolError, httpx.ReadError,
                httpx.ReadTimeout, ConnectionError, OSError) as e:
            print(f"    Connection error: {e}. Retrying in 30s...")
            time.sleep(30)
            continue
        except Exception as e:
            err_str = str(e)
            if "rate" in err_str.lower() or "429" in err_str:
                print(f"    Rate limit. Waiting 60s...")
                time.sleep(60)
                continue
            elif "overloaded" in err_str.lower() or "529" in err_str:
                print(f"    Overloaded. Waiting 30s...")
                time.sleep(30)
                continue
            else:
                print(f"    ERROR: {e}")
                if debug:
                    traceback.print_exc()
                break

        elapsed = time.time() - t0
        in_tok = final_msg.usage.input_tokens
        out_tok = final_msg.usage.output_tokens
        print(f"    {elapsed:.0f}s (in={in_tok:,} out={out_tok:,})")

        # Extract tool calls from response
        tool_uses = []
        for block in final_msg.content:
            if getattr(block, "type", "") == "tool_use" and block.name == TOOL_NAME:
                tool_uses.append(block)

        if not tool_uses:
            # Model stopped making tool calls — check stop reason
            stop = getattr(final_msg, "stop_reason", None)
            print(f"    No tool calls. Stop reason: {stop}")
            if stop == "end_turn":
                if len(classified_nums) >= 104:
                    break
                # Prompt to continue
                remaining = sorted(set(range(1, 105)) - classified_nums)
                print(f"    Prompting for {len(remaining)} remaining...")
                messages.append({"role": "assistant", "content": final_msg.content})
                messages.append({
                    "role": "user",
                    "content": f"Continue. Still need teachings: {remaining}",
                })
                continue
            elif stop == "max_tokens":
                print("    Truncated. Continuing...")
                messages.append({"role": "assistant", "content": final_msg.content})
                messages.append({
                    "role": "user",
                    "content": "Continue classifying the remaining teachings.",
                })
                continue
            else:
                break

        # Process each tool call
        tool_results = []
        for tu in tool_uses:
            entry = tu.input
            t_num = entry.get("teaching")
            if t_num and t_num not in classified_nums:
                classified_nums.add(t_num)
                classifications.append(entry)
                deg = entry.get("degree", "?")
                dir_ = entry.get("direction", "?")
                print(f"    T{t_num}: {deg}/{dir_}")

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": "Recorded.",
            })

        # Build next turn: assistant response + tool results
        messages.append({"role": "assistant", "content": final_msg.content})
        messages.append({"role": "user", "content": tool_results})

        # Check if done
        if len(classified_nums) >= 104:
            print(f"\n  All 104 teachings classified!")
            break

    return classifications


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Stage 7c (batch): Classify all teachings via iterative tool calls"
    )
    parser.add_argument("--dry-run", "-n", action="store_true")
    parser.add_argument(
        "--effort", default="xhigh",
        choices=["low", "medium", "high", "xhigh", "max"],
    )
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    print("Stage 7c (BATCH): Iterative tool-call classification")
    print(f"  Input:  {TEACHINGS_DIR}")
    print(f"  Output: {OUTPUT_DIR}")

    # Assemble the full corpus message
    parts = []
    available = []
    for t in range(1, 105):
        text = assemble_teaching_text(t)
        if text:
            parts.append(text)
            available.append(t)
        else:
            print(f"  WARNING: No text for T{t}, skipping")

    user_message = "\n\n---\n\n".join(parts)

    print(f"\n  Assembled {len(available)} teachings")
    print(f"  User message length: {len(user_message):,} characters")

    if args.dry_run:
        print(f"\n[DRY RUN] No API call made.")
        print(f"\n--- USER MESSAGE PREVIEW (first 2000 chars) ---")
        print(user_message[:2000])
        return

    # Create client
    client, deployment = create_client()
    print(f"\n  Deployment: {deployment}")
    print(f"  Thinking effort: {args.effort}")

    t0 = time.time()

    classifications = run_classification_loop(
        client,
        deployment,
        user_message,
        effort=args.effort,
        debug=args.debug,
    )

    elapsed = time.time() - t0
    print(f"\n  Total time: {elapsed:.0f}s")
    print(f"  Got {len(classifications)} classifications")

    if not classifications:
        print("  ERROR: No classifications returned")
        sys.exit(1)

    # Save individual files
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    saved = 0
    for entry in classifications:
        t_num = entry.get("teaching")
        if t_num is None:
            continue

        # Load title from teaching file
        teaching_path = TEACHINGS_DIR / f"t_{t_num:03d}.json"
        if teaching_path.exists():
            with open(teaching_path, encoding="utf-8") as f:
                t_data = json.load(f)
            entry["title"] = t_data.get("title", "")

        out_path = OUTPUT_DIR / f"t_{t_num:03d}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2, ensure_ascii=False)
        saved += 1

    print(f"  Saved {saved} coordinate files to {OUTPUT_DIR}")

    # Quick summary
    degrees = Counter(c["degree"] for c in classifications if "degree" in c)
    directions = Counter(c["direction"] for c in classifications if "direction" in c)
    print(f"\n  === QUICK SUMMARY ===")
    print(f"  Degrees:    {dict(degrees)}")
    print(f"  Directions: {dict(directions)}")


if __name__ == "__main__":
    main()
