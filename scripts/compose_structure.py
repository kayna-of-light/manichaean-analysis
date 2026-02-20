#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compose the structural architecture of a book from its teaching substrate.

Feeds ALL core texts + spiritual readings to Claude Opus 4.6 in a single
prompt (within its context window). The texts are presented as a continuous
flow — core text and spiritual reading interleaved paragraph by paragraph,
stripped of chapter divisions — so the model can read the entire substrate
holistically and discover its actual structure.

The model outputs structural observations via streaming tool calls. The
result is a structural schema (no text reproduction) that can drive PDF
generation from the existing text files.

Primary model: Claude Opus 4.6 via Azure AI Foundry (AnthropicFoundry).

Usage:
    python compose_structure.py --project kephalaia [--debug] [--dry-run]
"""

import json
from pathlib import Path
from typing import Any

from tools.corpus_base import CorpusAnalysisBase

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert in the doctrine of correspondences as written by \
Emanuel Swedenborg, with deep specialization in ancient cosmological \
vocabulary — Zoroastrian, Manichaean, and Persian-Iranian traditions.

You have been given the COMPLETE teaching substrate of the Coptic \
Kephalaia — both the extracted teaching core (oldest layer) and a \
correspondential reading (translation from natural into spiritual \
sense) of most passages.

The text is presented as a continuous flow of numbered paragraphs. \
Each paragraph has a marker [§N]. Lines marked [§N]* are the \
correspondential reading of that same paragraph.

These paragraph numbers are sequential. The text was extracted from \
an editorial compilation — what you are reading is the teaching \
substrate stripped of editorial structure.

Your task is to read the entire text holistically and determine its \
true structure — the natural divisions, the actual teaching sequence, \
what belongs together, what the parts and chapters should be called, \
and in what order the text should be read.

When you have determined the structure, call the commit_structure \
tool once with the complete result."""

# ---------------------------------------------------------------------------
# Tool definition
# ---------------------------------------------------------------------------

COMMIT_STRUCTURE_TOOL = {
    "name": "commit_structure",
    "description": (
        "Commit the complete book structure. Call this exactly once "
        "with the full result of your analysis."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "parts": {
                "type": "array",
                "description": (
                    "The major divisions of the book, in reading order."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "part_number": {
                            "type": "integer",
                            "description": (
                                "Sequential part number in reading order."
                            ),
                        },
                        "title": {
                            "type": "string",
                            "description": (
                                "Title for this part of the book."
                            ),
                        },
                        "description": {
                            "type": "string",
                            "description": (
                                "What this part covers, its role in "
                                "the book's architecture, and why "
                                "these chapters belong together."
                            ),
                        },
                    },
                    "required": [
                        "part_number", "title", "description",
                    ],
                },
            },
            "chapters": {
                "type": "array",
                "description": (
                    "Every chapter in the book, in reading order."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "part_number": {
                            "type": "integer",
                            "description": (
                                "Which part this chapter belongs to."
                            ),
                        },
                        "position_in_part": {
                            "type": "integer",
                            "description": (
                                "Reading order within the part "
                                "(1, 2, 3, ...)."
                            ),
                        },
                        "section_start": {
                            "type": "integer",
                            "description": (
                                "First § number of this chapter."
                            ),
                        },
                        "section_end": {
                            "type": "integer",
                            "description": (
                                "Last § number of this chapter."
                            ),
                        },
                        "title": {
                            "type": "string",
                            "description": (
                                "Title for this chapter based on "
                                "its content."
                            ),
                        },
                        "role": {
                            "type": "string",
                            "description": (
                                "The chapter's role — e.g. primary "
                                "teaching, elaboration, parallel, "
                                "fragment, summary, transitional."
                            ),
                        },
                        "description": {
                            "type": "string",
                            "description": (
                                "What this chapter teaches and how "
                                "it relates to the book's structure."
                            ),
                        },
                    },
                    "required": [
                        "part_number",
                        "position_in_part",
                        "section_start",
                        "section_end",
                        "title",
                        "role",
                        "description",
                    ],
                },
            },
            "observations": {
                "type": "array",
                "description": (
                    "Structural observations about the text — "
                    "cross-cutting themes, recurring patterns, "
                    "anything that doesn't fit into parts/chapters."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": (
                                "Short title for this observation."
                            ),
                        },
                        "content": {
                            "type": "string",
                            "description": (
                                "The observation. As detailed "
                                "as needed."
                            ),
                        },
                    },
                    "required": ["title", "content"],
                },
            },
        },
        "required": ["parts", "chapters", "observations"],
    },
}


# ---------------------------------------------------------------------------
# Script
# ---------------------------------------------------------------------------


class ComposeStructure(CorpusAnalysisBase):
    """Discover the structural architecture of the corpus."""

    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT

    @property
    def tools(self) -> list[dict]:
        return [COMMIT_STRUCTURE_TOOL]

    @property
    def expected_tool_name(self) -> str:
        return "commit_structure"

    @property
    def default_output_filename(self) -> str:
        return "book_structure.json"

    def process_result(
        self, tool_input: dict | None, text_output: str
    ) -> dict:
        if tool_input is None:
            return {
                "parts": [],
                "chapters": [],
                "observations": [],
                "text_output": text_output,
            }

        # Print summary as we go
        for p in tool_input.get("parts", []):
            print(f"  ✦ Part {p['part_number']}: {p['title']}")
        for i, ch in enumerate(tool_input.get("chapters", []), 1):
            print(
                f"  ✓ [{i}] §{ch['section_start']}–"
                f"§{ch['section_end']}: {ch['title']}  "
                f"(Pt {ch['part_number']}, "
                f"pos {ch['position_in_part']}, "
                f"{ch['role']})"
            )
        for obs in tool_input.get("observations", []):
            print(f"  ○ {obs['title']}")

        tool_input["text_output"] = text_output
        return tool_input

    def save_result(self, result: dict, output_path: Path) -> None:
        # Attach section map for post-processing
        result["_section_map"] = [
            {"ms_chapter": ch, "section_start": s, "section_end": e}
            for ch, s, e in self.section_map
        ]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\nStructure saved to: {output_path}")
        print(f"  Parts defined: {len(result['parts'])}")
        print(f"  Chapters defined: {len(result['chapters'])}")
        print(f"  Observations: {len(result['observations'])}")


if __name__ == "__main__":
    ComposeStructure(
        description="Compose Structure"
    ).run()
