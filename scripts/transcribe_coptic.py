#!/usr/bin/env python3
"""Transcribe printed Coptic pages from the Kephalaia using Claude vision.

Adapted from the nag-hammadi-analysis HTR pipeline for PRINTED scholarly
edition text (Polotsky/Böhlig 1940) rather than handwritten manuscript.

Usage:
    # Transcribe a single page:
    python scripts/transcribe_coptic.py --image output/projects/kephalaia/coptic/images/keph_p010.jpg

    # Transcribe a range of pages:
    python scripts/transcribe_coptic.py --pages 10-15

    # Lower effort for quick test:
    python scripts/transcribe_coptic.py --image output/projects/kephalaia/coptic/images/keph_p010.jpg --effort high
"""

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

import httpx
from anthropic import AnthropicFoundry
from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parent.parent
SECRETS_PATH = REPO_ROOT / "secrets" / "azure_openai.env"
PAGES_DIR = REPO_ROOT / "output" / "projects" / "kephalaia" / "coptic" / "images"
OUTPUT_DIR = REPO_ROOT / "output" / "projects" / "kephalaia" / "coptic" / "transcriptions"
TEMP_DIR = REPO_ROOT / "temp"

# ── Prompts optimized for PRINTED Coptic ──────────────────────────────────────

SYSTEM_PROMPT = (
    "You are an expert Coptic philologist performing OCR transcription of a "
    "printed scholarly edition. This is a 1940 critical edition of Coptic text "
    "(Lycopolitan/sub-Akhmimic dialect). The text is PRINTED in a clear Coptic "
    "typeface — not handwritten. "
    "Your task is to convert the printed Coptic characters into Unicode text. "
    "Use Unicode Coptic (U+2C80–U+2CFF) with combining overline (U+0305) for "
    "supralinear strokes. "
    "CRITICAL RULES: "
    "(1) Transcribe ONLY the Coptic text body. Ignore the German header line at top. "
    "(2) Preserve original line breaks — one printed line per output line. "
    "(3) Include line numbers as they appear (at left margin). "
    "(4) Preserve editorial marks: square brackets [...] indicate lacunae/restorations, "
    "dots . . . indicate missing text, curly braces or parentheses as printed. "
    "(5) Transcribe the chapter header (e.g. ⲛ̄ⲕⲉⲫⲁⲗⲁⲓⲟⲛ) if present. "
    "(6) Ignore footnotes at the bottom of the page (below the main text block). "
    "(7) The word 'leer' in the edition means 'blank/empty' — transcribe it as-is. "
    "Output ONLY the transcription. No commentary, no translation."
)

USER_PROMPT = (
    "Transcribe this printed Coptic page. One line per output line, preserving "
    "line numbers. Include the chapter header if present. Ignore the German "
    "header and any footnotes."
)


def create_client() -> tuple[AnthropicFoundry, str]:
    """Create Claude client from .env credentials."""
    os.environ.pop("ANTHROPIC_FOUNDRY_RESOURCE", None)

    config = dotenv_values(SECRETS_PATH)
    endpoint = config.get("ANTHROPIC_ENDPOINT", "").rstrip("/")
    api_key = config.get("ANTHROPIC_API_KEY", "")
    deployment = config.get("ANTHROPIC_DEPLOYMENT", "claude-opus-4-7-1")

    if not endpoint or not api_key:
        print("ERROR: ANTHROPIC_ENDPOINT and ANTHROPIC_API_KEY required in secrets/azure_openai.env")
        sys.exit(1)

    client = AnthropicFoundry(
        api_key=api_key,
        base_url=endpoint,
        timeout=httpx.Timeout(600.0, connect=30.0),
    )
    return client, deployment


def transcribe_page(client, deployment: str, image_path: Path,
                    effort: str = "high", max_tokens: int = 32000,
                    no_thinking: bool = False) -> dict:
    """Send a page image to Claude for transcription."""
    image_bytes = image_path.read_bytes()
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    media_type = "image/jpeg"

    content = [
        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
        {"type": "text", "text": USER_PROMPT},
    ]

    if no_thinking:
        thinking_config = {"type": "disabled"}
    else:
        thinking_config = {"type": "adaptive", "display": "omitted"}
    kwargs = dict(
        model=deployment,
        system=SYSTEM_PROMPT,
        max_tokens=max_tokens,
        thinking=thinking_config,
        messages=[{"role": "user", "content": content}],
    )
    if effort != "high" and not no_thinking:
        kwargs["output_config"] = {"effort": effort}

    t0 = time.time()
    full_text = ""
    thinking_text = ""
    input_tokens = 0
    output_tokens = 0

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            with client.messages.stream(**kwargs) as stream:
                for event in stream:
                    if event.type == "content_block_delta":
                        delta_type = getattr(event.delta, "type", "")
                        if delta_type == "thinking_delta":
                            chunk = getattr(event.delta, "thinking", "") or ""
                            thinking_text += chunk
                        elif delta_type == "text_delta":
                            chunk = getattr(event.delta, "text", "") or ""
                            full_text += chunk

                msg = stream.get_final_message()
                input_tokens = msg.usage.input_tokens
                output_tokens = msg.usage.output_tokens
            break

        except (httpx.RemoteProtocolError, httpx.ReadError, httpx.ReadTimeout,
                ConnectionError, OSError) as e:
            print(f"  [retry] Connection error on attempt {attempt}/{max_retries}: {e}")
            if attempt == max_retries:
                raise
            time.sleep(5)

    elapsed = time.time() - t0

    return {
        "transcription": full_text,
        "thinking": thinking_text,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "elapsed_seconds": round(elapsed, 1),
    }


def process_page(client, deployment: str, image_path: Path,
                 effort: str, output_dir: Path, no_thinking: bool = False) -> dict:
    """Transcribe a single page and save results."""
    page_name = image_path.stem  # e.g. "keph_p010"
    mode = "no-thinking" if no_thinking else f"effort={effort}"
    print(f"\n{'='*60}")
    print(f"Transcribing: {image_path.name} ({mode})")
    print(f"{'='*60}")

    result = transcribe_page(client, deployment, image_path, effort,
                             no_thinking=no_thinking)

    print(f"  Completed in {result['elapsed_seconds']}s")
    print(f"  Tokens: {result['input_tokens']} in / {result['output_tokens']} out")

    # Show preview
    lines = [l for l in result["transcription"].strip().split("\n") if l.strip()]
    print(f"  Lines: {len(lines)}")
    for line in lines[:5]:
        print(f"    {line}")
    if len(lines) > 5:
        print(f"    ... ({len(lines)} total)")

    # Save transcription as plain text
    output_dir.mkdir(parents=True, exist_ok=True)
    txt_path = output_dir / f"{page_name}.txt"
    txt_path.write_text(result["transcription"], encoding="utf-8")

    # Save full result as JSON
    json_path = output_dir / f"{page_name}.json"
    save_data = {
        "source_image": str(image_path),
        "page_name": page_name,
        "effort": effort,
        "transcription": result["transcription"],
        "transcription_lines": lines,
        "thinking": result["thinking"],
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
        "elapsed_seconds": result["elapsed_seconds"],
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)

    print(f"  Saved: {txt_path.name}, {json_path.name}")
    return save_data


def main():
    parser = argparse.ArgumentParser(description="Transcribe printed Coptic pages")
    parser.add_argument("--image", type=Path, default=None,
                        help="Single image to transcribe")
    parser.add_argument("--pages", type=str, default=None,
                        help="Page range to transcribe (e.g. '10-15'), images must exist")
    parser.add_argument("--effort", default="high",
                        choices=["low", "medium", "high", "xhigh", "max"])
    parser.add_argument("--max-tokens", type=int, default=32000)
    parser.add_argument("--no-thinking", action="store_true", default=True,
                        help="Disable adaptive thinking (default for printed text)")
    parser.add_argument("--thinking", action="store_true",
                        help="Enable adaptive thinking (override default)")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    if args.image is None and args.pages is None:
        print("ERROR: Specify --image or --pages")
        sys.exit(1)

    # --thinking overrides the default --no-thinking
    no_thinking = not args.thinking

    client, deployment = create_client()
    print(f"Model: {deployment}")

    if args.image:
        if not args.image.exists():
            print(f"ERROR: {args.image} not found")
            sys.exit(1)
        process_page(client, deployment, args.image, args.effort, args.output_dir,
                     no_thinking=no_thinking)

    elif args.pages:
        # Parse page range and find corresponding images
        images = []
        for part in args.pages.split(","):
            part = part.strip()
            if "-" in part:
                start, end = part.split("-", 1)
                for p in range(int(start), int(end) + 1):
                    img = PAGES_DIR / f"keph_p{p:03d}.jpg"
                    if img.exists():
                        images.append(img)
                    else:
                        print(f"WARNING: {img.name} not found, skipping")
            else:
                img = PAGES_DIR / f"keph_p{int(part):03d}.jpg"
                if img.exists():
                    images.append(img)
                else:
                    print(f"WARNING: {img.name} not found, skipping")

        if not images:
            print("ERROR: No images found for specified pages")
            sys.exit(1)

        print(f"Pages to transcribe: {len(images)}")
        results = []
        for img in images:
            result = process_page(client, deployment, img, args.effort, args.output_dir,
                                 no_thinking=no_thinking)
            results.append(result)

        # Summary
        print(f"\n{'='*60}")
        print(f"SUMMARY: {len(results)} pages transcribed")
        total_tokens = sum(r["output_tokens"] for r in results)
        total_time = sum(r["elapsed_seconds"] for r in results)
        print(f"  Total output tokens: {total_tokens:,}")
        print(f"  Total time: {total_time:.0f}s")
        print(f"{'='*60}")


if __name__ == "__main__":
    main()
