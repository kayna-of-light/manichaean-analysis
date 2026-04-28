#!/usr/bin/env python3
"""End-to-end Coptic transcription pipeline: PDF extraction → two-pass OCR.

Pass 1: Expert Coptic extraction from image (no English context — prevents bias)
Pass 2: Validation with English translation as semantic guide, correcting
        known character-level errors

Usage:
    # Single page (extracts from PDF, auto-extracts English from Gardner):
    python scripts/transcribe_coptic_v2.py --pages 12

    # Page range:
    python scripts/transcribe_coptic_v2.py --pages 10-20

    # Multiple pages:
    python scripts/transcribe_coptic_v2.py --pages 10,11,12

    # All Coptic pages (10-244):
    python scripts/transcribe_coptic_v2.py --pages all

    # All pages, 12 in parallel, resumable:
    python scripts/transcribe_coptic_v2.py --pages all --concurrency 12 --skip-existing

    # From pre-extracted image (backward compat):
    python scripts/transcribe_coptic_v2.py --image output/projects/kephalaia/coptic/images/keph_p012.jpg

    # Reuse existing pass1 output:
    python scripts/transcribe_coptic_v2.py --pages 12 --reuse-pass1

    # Skip pages that already have pass2 output:
    python scripts/transcribe_coptic_v2.py --pages 10-20 --skip-existing
"""

import argparse
import base64
import concurrent.futures
import json
import os
import re
import sys
import time
from pathlib import Path

import fitz  # PyMuPDF
import httpx
from anthropic import AnthropicFoundry
from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parent.parent
SECRETS_PATH = REPO_ROOT / "secrets" / "azure_openai.env"
DATA_DIR = REPO_ROOT / "data"
PAGES_DIR = REPO_ROOT / "output" / "projects" / "kephalaia" / "coptic" / "images"
OUTPUT_DIR = REPO_ROOT / "output" / "projects" / "kephalaia" / "coptic" / "transcriptions"
GARDNER_PATH = REPO_ROOT / "output" / "texts" / "Kephalaia_of_the_Teacher.md"

# PDF page mapping
PDF_GLOB = "Kephalaia -- Mani*Stuttgart.pdf"
FIRST_COPTIC_IDX = 49   # PDF page index of first Coptic page
LAST_COPTIC_IDX = 517    # PDF page index of last Coptic page


# ── PDF extraction helpers ──────────────────────────────────────────────────

def pdf_idx_to_printed_page(pdf_idx: int) -> int:
    """Convert PDF page index to printed page number."""
    return 10 + (pdf_idx - FIRST_COPTIC_IDX) // 2


def printed_page_to_pdf_idx(printed_page: int) -> int:
    """Convert printed page number to PDF page index."""
    return FIRST_COPTIC_IDX + (printed_page - 10) * 2


def find_pdf() -> Path:
    """Find the Kephalaia PDF in the data directory."""
    matches = list(DATA_DIR.glob(PDF_GLOB))
    if not matches:
        print(f"ERROR: No PDF matching '{PDF_GLOB}' found in {DATA_DIR}")
        sys.exit(1)
    return matches[0]


def parse_page_spec(spec: str) -> list[int]:
    """Parse page specification like '10-20' or '10,11,12' into printed page numbers."""
    if spec.lower() == "all":
        return list(range(10, 245))
    pages = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            pages.extend(range(int(start), int(end) + 1))
        else:
            pages.append(int(part))
    return sorted(set(pages))


def extract_page_image(pdf_path: Path, printed_page: int,
                       dpi: int = 200) -> Path:
    """Extract a single Coptic page from the PDF as JPEG.

    Returns the path to the extracted image. Uses cached image if it exists.
    """
    out_path = PAGES_DIR / f"keph_p{printed_page:03d}.jpg"
    if out_path.exists():
        return out_path

    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    pdf_idx = printed_page_to_pdf_idx(printed_page)
    if pdf_idx < FIRST_COPTIC_IDX or pdf_idx > LAST_COPTIC_IDX:
        print(f"  WARNING: Page {printed_page} (PDF idx {pdf_idx}) out of range")
        return out_path

    doc = fitz.open(str(pdf_path))
    page = doc[pdf_idx]
    pix = page.get_pixmap(dpi=dpi)
    pix.pil_save(str(out_path), format="JPEG", quality=92)
    doc.close()

    size_kb = out_path.stat().st_size / 1024
    print(f"  Extracted page {printed_page} ({pix.width}x{pix.height}, {size_kb:.0f} KB)")
    return out_path


# ── Pass 1: Expert extraction (no English context) ──────────────────────────

PASS1_SYSTEM = (
    "You are an expert Coptic philologist performing OCR transcription of a "
    "printed scholarly edition. This is a 1940 critical edition of Coptic text "
    "(Lycopolitan/sub-Akhmimic dialect). The text is PRINTED in a clear Coptic "
    "typeface — not handwritten. "
    "Your task is to convert the printed Coptic characters into Unicode text. "
    "Use Unicode Coptic block (U+2C80–U+2CFF) for Coptic letters. "
    "Use combining overline (U+0305) for supralinear strokes above letters. "
    "CRITICAL RULES: "
    "(1) Transcribe ONLY the Coptic text body. Ignore the German header line at top. "
    "(2) Preserve original line breaks — one printed line per output line. "
    "(3) Include line numbers as they appear (at left margin). "
    "(4) Preserve editorial marks: square brackets [...] indicate lacunae/restorations, "
    "dots . . . indicate missing text, curly braces or parentheses as printed. "
    "(5) Include the chapter header (e.g. ⲛ̄ⲕⲉⲫⲁⲗⲁⲓⲟⲛ) if present. "
    "(6) Include the page number at the top of the page if visible. "
    "(7) Ignore footnotes at the bottom of the page (below the main text block). "
    "(8) The word 'leer' in the edition means 'blank/empty' — transcribe it as-is. "
    "LETTER GUIDANCE for Lycopolitan dialect: "
    "The Lycopolitan dialect has distinctive letters not found in Sahidic. "
    "Pay careful attention to each letter shape. In particular distinguish: "
    "- ⲉ (epsilon) from the dialect-specific letter that resembles a numeral 6 "
    "- ⲝ (ksi) from ⲭ (khi) — check context carefully "
    "- ⲡ (pi) from similar vertical-stroke letters "
    "- ⲣ (rho) from similar shapes "
    "Use one consistent Unicode codepoint for each distinct letter shape throughout. "
    "Output ONLY the transcription. No commentary, no translation."
)

PASS1_USER = (
    "Transcribe this printed Coptic page exactly as you see it. "
    "One line per output line, preserving line numbers."
)

# ── Pass 2: Validation with English translation ─────────────────────────────

PASS2_SYSTEM = (
    "You are a Coptic philologist correcting an OCR transcription of a 1940 "
    "critical edition (Polotsky/Böhlig) of the Manichaean Kephalaia. The text "
    "is in the Lycopolitan (sub-Akhmimic) dialect of Coptic.\n"
    "\n"
    "THE SITUATION:\n"
    "A first-pass extraction was performed on this page image by a vision "
    "model. The model can read most of the Coptic text, but it has systematic "
    "weaknesses: it confuses visually similar characters, renders the same "
    "letter with different Unicode codepoints across lines, and sometimes "
    "misreads letterforms that are distinctive to the Lycopolitan dialect. "
    "The result is a transcription that is MOSTLY correct but has scattered "
    "character-level errors throughout.\n"
    "\n"
    "YOUR TASK:\n"
    "You receive three things: the page image, the first-pass Coptic extraction, "
    "and a published English translation (Gardner). The English tells you WHAT "
    "the text says — which words are there, what the sentences mean. Use it as "
    "a red thread: when the English says 'apostles', you know ⲁⲡⲟⲥⲧⲟⲗⲟⲥ should "
    "be there; when it says 'flesh', you know ⲥⲁⲣⲝ should be there; when it "
    "says 'Zarathustra', you know exactly what name to look for.\n"
    "\n"
    "But the English translation is NOT the goal. The goal is an accurate COPTIC "
    "transcription. The English is your semantic guide — it tells you where to "
    "look and what to expect. The Coptic captures what the English cannot: "
    "the actual morphology, the dialect-specific forms, the grammatical "
    "constructions, the prefixes and suffixes that have no English equivalent. "
    "That is the whole reason we want the Coptic transcription.\n"
    "\n"
    "So: follow the English meaning through the text, and wherever the first-pass "
    "Coptic doesn't match what the English says should be there, re-examine the "
    "image and correct the Coptic. Where the Coptic has features the English "
    "doesn't show (dialect forms, grammatical particles, word boundaries), "
    "preserve them exactly — those are the valuable parts.\n"
    "\n"
    "SPECIFIC CHARACTER ERRORS TO WATCH FOR:\n"
    "\n"
    "1. THE LYCOPOLITAN LETTER: This dialect has a distinctive letter that "
    "resembles a numeral '6' or reversed '6'. The first pass often renders "
    "it as plain ⲉ (epsilon), or switches between ⲋ, ⲍ, and ϩ for the same "
    "letter across different lines. Look at the image: if you see that "
    "distinctive '6' shape, use ONE consistent codepoint for it everywhere.\n"
    "\n"
    "2. ⲝ vs ⲭ: These look almost identical in this typeface. The English "
    "disambiguates: 'flesh' = ⲥⲁⲣⲝ (ksi); 'that/because' = ⲭⲉ (khi); "
    "'Christ' = ⲭⲣⲥ (khi). Check every occurrence.\n"
    "\n"
    "3. SUPRALINEAR STROKES: The overline mark (combining overline U+0305) "
    "above abbreviated forms is often missed or inconsistently applied. "
    "Common: ⲛ̄, ⲙ̄, ⲣ̄, ϥ̄, ⲥ̄.\n"
    "\n"
    "4. GREEK LOANWORDS: These should be spelled correctly — cross-check "
    "against the English: ⲁⲡⲟⲥⲧⲟⲗⲟⲥ (apostle), ⲉⲕⲕⲗⲏⲥⲓⲁ (church), "
    "ⲕⲟⲥⲙⲟⲥ (world), ⲕⲁⲧⲏⲭⲟⲩⲙⲉⲛⲟⲥ (catechumen), ⲙⲟⲣⲫⲏ (form), "
    "ⲥⲁⲣⲝ (flesh), ⲃⲟⲏⲑⲟⲥ (helper), ⲫⲑⲟⲛⲟⲥ (envy), "
    "ⲥⲁⲧⲁⲛⲁⲥ (Satan), ⲡⲟⲛⲏⲣⲟⲥ (evil one), ⲥⲡⲉⲓⲣⲁ (cohort).\n"
    "\n"
    "5. PROPER NAMES: ⲥⲏⲑⲏⲗ (Sethel), ⲁⲇⲁⲙ (Adam), ⲉⲛⲱϣ (Enosh), "
    "ⲉⲛⲱⲭ (Enoch), ⲥⲏⲙ (Sem), ⲃⲟⲩⲇⲇⲁⲥ (Buddha), ⲁⲩⲣⲉⲛⲧⲏⲥ (Aurentes), "
    "ⲍⲁⲣⲁⲑⲟⲩⲥⲧⲣⲁ (Zarathustra), ⲓⲏⲥ (Jesus), ⲓⲟⲩⲇⲁⲥ (Judas), "
    "ⲓⲥⲕⲁⲣⲓⲱⲧⲏⲥ (Iscariot), ⲡⲁⲩⲗⲟⲥ (Paul), "
    "ⲍⲩⲥⲧⲁⲥⲡⲏⲥ (Hystaspes), ⲡⲉⲣⲥⲓⲥ (Persia).\n"
    "\n"
    "6. PAGE NUMBER: Include the printed page number if visible at the top.\n"
    "\n"
    "Output the CORRECTED Coptic transcription. Same format: one line per "
    "output line, with line numbers. Output ONLY the corrected text — "
    "no commentary, no explanations, no change log."
)


def create_client():
    """Create Claude client from .env credentials."""
    os.environ.pop("ANTHROPIC_FOUNDRY_RESOURCE", None)
    config = dotenv_values(SECRETS_PATH)
    endpoint = config.get("ANTHROPIC_ENDPOINT", "").rstrip("/")
    api_key = config.get("ANTHROPIC_API_KEY", "")
    deployment = config.get("ANTHROPIC_DEPLOYMENT", "claude-opus-4-7-1")
    if not endpoint or not api_key:
        print("ERROR: credentials required in secrets/azure_openai.env")
        sys.exit(1)
    client = AnthropicFoundry(
        api_key=api_key,
        base_url=endpoint,
        timeout=httpx.Timeout(600.0, connect=30.0),
    )
    return client, deployment


def image_to_b64(image_path: Path) -> tuple[str, str]:
    """Read image and return (base64, media_type)."""
    data = image_path.read_bytes()
    b64 = base64.standard_b64encode(data).decode("utf-8")
    suffix = image_path.suffix.lower()
    mt = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
    return b64, mt.get(suffix, "image/jpeg")


def call_claude(client, deployment, system, user_content, max_tokens=32000):
    """Call Claude with thinking disabled. Returns text + metadata."""
    t0 = time.time()
    full_text = ""
    input_tokens = output_tokens = 0

    kwargs = dict(
        model=deployment,
        system=system,
        max_tokens=max_tokens,
        thinking={"type": "disabled"},
        messages=[{"role": "user", "content": user_content}],
    )

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            with client.messages.stream(**kwargs) as stream:
                for event in stream:
                    if event.type == "content_block_delta":
                        if getattr(event.delta, "type", "") == "text_delta":
                            chunk = getattr(event.delta, "text", "") or ""
                            full_text += chunk
                msg = stream.get_final_message()
                input_tokens = msg.usage.input_tokens
                output_tokens = msg.usage.output_tokens
            break
        except (httpx.RemoteProtocolError, httpx.ReadError, httpx.ReadTimeout,
                ConnectionError, OSError) as e:
            print(f"  [retry] attempt {attempt}/{max_retries}: {e}")
            if attempt == max_retries:
                raise
            time.sleep(5)

    return {
        "text": full_text,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "elapsed": round(time.time() - t0, 1),
    }


def extract_english_for_page(page_num: int) -> str:
    """Extract English translation for a printed page from Gardner.

    Gardner's translation uses inline (N) markers for Coptic page numbers.
    We extract text between (page_num) and (page_num+1).
    """
    if not GARDNER_PATH.exists():
        return ""

    text = GARDNER_PATH.read_text(encoding="utf-8")

    start_match = re.search(rf'\({page_num}\)', text)
    if not start_match:
        return ""

    end_match = re.search(rf'\({page_num + 1}\)', text[start_match.end():])
    if end_match:
        end_pos = start_match.end() + end_match.start()
        section = text[start_match.start():end_pos]
    else:
        section = text[start_match.start():start_match.start() + 3000]

    return section.strip()


def run_pass1(client, deployment, image_path):
    """Pass 1: Blind extraction — image only, no English, no bias."""
    print("  [Pass 1] Blind extraction (image only)...")
    b64, media_type = image_to_b64(image_path)
    content = [
        {"type": "image", "source": {"type": "base64",
                                      "media_type": media_type, "data": b64}},
        {"type": "text", "text": PASS1_USER},
    ]
    return call_claude(client, deployment, PASS1_SYSTEM, content)


def run_pass2(client, deployment, image_path, pass1_text, english_text):
    """Pass 2: Validation — image + raw transcription + English."""
    print("  [Pass 2] Validation (image + raw text + English)...")
    b64, media_type = image_to_b64(image_path)

    user_text = (
        "Here is the raw OCR transcription from the first pass. It is mostly "
        "correct but contains character-level errors due to model limitations "
        "with Coptic letterforms:\n\n"
        "<raw_transcription>\n"
        f"{pass1_text}\n"
        "</raw_transcription>\n\n"
        "Here is the published English translation (Gardner) covering this page. "
        "Use it as your red thread — it tells you what each line MEANS, so you "
        "can verify whether the Coptic words in the extraction match that meaning:\n\n"
        "<english_translation>\n"
        f"{english_text}\n"
        "</english_translation>\n\n"
        "Now re-examine the image. Walk through the English line by line: what "
        "does it say? Look at the corresponding Coptic in the extraction — does "
        "it match? Where the English says 'apostle', is ⲁⲡⲟⲥⲧⲟⲗⲟⲥ spelled "
        "correctly? Where it says 'flesh', is ⲥⲁⲣⲝ there with the right ⲝ? "
        "Where it says 'church', is ⲉⲕⲕⲗⲏⲥⲓⲁ intact?\n\n"
        "The English guides you to the errors. But preserve everything the "
        "English CANNOT show: the Coptic morphology, dialect forms, prefixes, "
        "suffixes, grammatical particles. Those are the reason we want this "
        "transcription.\n\n"
        "Output the corrected Coptic text only."
    )

    content = [
        {"type": "image", "source": {"type": "base64",
                                      "media_type": media_type, "data": b64}},
        {"type": "text", "text": user_text},
    ]
    return call_claude(client, deployment, PASS2_SYSTEM, content)


def process_page(client, deployment, image_path: Path, english_text: str,
                 output_dir: Path, reuse_pass1: bool = False) -> str:
    """Run two-pass transcription for one page. Returns the final transcription."""
    page_name = image_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Two-pass transcription: {image_path.name}")
    print(f"{'='*60}")

    # ── Pass 1 ──
    pass1_path = output_dir / f"{page_name}_pass1.txt"
    if reuse_pass1 and pass1_path.exists():
        print(f"  [Pass 1] Reusing: {pass1_path.name}")
        pass1_text = pass1_path.read_text(encoding="utf-8")
        p1 = {"text": pass1_text, "input_tokens": 0,
              "output_tokens": 0, "elapsed": 0}
    else:
        p1 = run_pass1(client, deployment, image_path)
        pass1_text = p1["text"]
        pass1_path.write_text(pass1_text, encoding="utf-8")

    lines1 = [l for l in pass1_text.strip().split("\n") if l.strip()]
    print(f"  [Pass 1] {len(lines1)} lines | {p1['elapsed']}s | "
          f"{p1['input_tokens']}in / {p1['output_tokens']}out")

    # ── Pass 2 ──
    if not english_text:
        print("  [Pass 2] SKIPPED — no English translation available")
        # Fall back to pass1 as final result
        return pass1_text

    print(f"  English context: {len(english_text)} chars")
    p2 = run_pass2(client, deployment, image_path, pass1_text, english_text)
    pass2_text = p2["text"]
    pass2_path = output_dir / f"{page_name}_pass2.txt"
    pass2_path.write_text(pass2_text, encoding="utf-8")

    lines2 = [l for l in pass2_text.strip().split("\n") if l.strip()]
    print(f"  [Pass 2] {len(lines2)} lines | {p2['elapsed']}s | "
          f"{p2['input_tokens']}in / {p2['output_tokens']}out")

    # ── Save combined JSON ──
    json_path = output_dir / f"{page_name}_twopass.json"
    save_data = {
        "source_image": str(image_path),
        "page_name": page_name,
        "pass1": {
            "transcription": pass1_text,
            "lines": lines1,
            "input_tokens": p1["input_tokens"],
            "output_tokens": p1["output_tokens"],
            "elapsed_seconds": p1["elapsed"],
        },
        "pass2": {
            "transcription": pass2_text,
            "lines": lines2,
            "english_chars": len(english_text),
            "input_tokens": p2["input_tokens"],
            "output_tokens": p2["output_tokens"],
            "elapsed_seconds": p2["elapsed"],
        },
        "english_text": english_text,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)

    # ── Quick diff ──
    changed = sum(1 for a, b in zip(lines1, lines2) if a != b)
    total = max(len(lines1), len(lines2))
    print(f"  Lines changed by Pass 2: {changed}/{total}")
    print(f"  Saved: {pass1_path.name}, {pass2_path.name}, {json_path.name}")

    return pass2_text


def main():
    parser = argparse.ArgumentParser(
        description="End-to-end Coptic transcription: PDF → two-pass OCR")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pages", type=str,
                       help="Printed page numbers: '12', '10-20', '10,11,12', or 'all'")
    group.add_argument("--image", type=Path,
                       help="Pre-extracted page image (backward compat)")
    parser.add_argument("--english", type=Path, default=None,
                        help="Text file with English translation (overrides auto)")
    parser.add_argument("--no-auto-english", action="store_true",
                        help="Disable auto-extraction from Gardner")
    parser.add_argument("--reuse-pass1", action="store_true",
                        help="Reuse existing pass1 output if available")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip pages that already have pass2 output")
    parser.add_argument("--concurrency", type=int, default=1,
                        help="Number of pages to process in parallel (default: 1)")
    parser.add_argument("--dpi", type=int, default=200,
                        help="PDF rendering resolution (default: 200)")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    client, deployment = create_client()
    print(f"Model: {deployment}")

    # ── Build list of (image_path, english_text) to process ──
    work_items: list[tuple[Path, str]] = []

    if args.image:
        # Single pre-extracted image (backward compat)
        if not args.image.exists():
            print(f"ERROR: {args.image} not found")
            sys.exit(1)
        english_text = ""
        if args.english:
            english_text = args.english.read_text(encoding="utf-8")
        elif not args.no_auto_english:
            match = re.search(r'p(\d+)', args.image.stem)
            if match:
                english_text = extract_english_for_page(int(match.group(1)))
        work_items.append((args.image, english_text))
    else:
        # --pages: extract from PDF
        printed_pages = parse_page_spec(args.pages)
        pdf_path = find_pdf()
        print(f"PDF: {pdf_path.name}")
        print(f"Pages to process: {len(printed_pages)}")

        for pp in printed_pages:
            page_name = f"keph_p{pp:03d}"
            if args.skip_existing:
                pass2_path = args.output_dir / f"{page_name}_pass2.txt"
                if pass2_path.exists():
                    print(f"  Skipping page {pp} (pass2 exists)")
                    continue

            image_path = extract_page_image(pdf_path, pp, dpi=args.dpi)
            if not image_path.exists():
                print(f"  WARNING: Could not extract page {pp}, skipping")
                continue

            english_text = ""
            if args.english:
                english_text = args.english.read_text(encoding="utf-8")
            elif not args.no_auto_english:
                english_text = extract_english_for_page(pp)
                if not english_text:
                    print(f"  WARNING: No English found for page {pp}")

            work_items.append((image_path, english_text))

    if not work_items:
        print("Nothing to process.")
        sys.exit(0)

    # ── Process all pages ──
    total = len(work_items)
    results: list[tuple[str, str]] = []   # (page_name, final_text)
    total_elapsed = 0.0
    concurrency = max(1, args.concurrency)

    def _process_one(idx: int, image_path: Path, english_text: str) -> tuple[str, str, float]:
        """Process a single page (thread-safe — each page writes unique files)."""
        if total > 1:
            print(f"\n[{idx}/{total}] Processing {image_path.name}")
        t0 = time.time()
        final_text = process_page(
            client, deployment, image_path, english_text,
            args.output_dir, reuse_pass1=args.reuse_pass1,
        )
        elapsed = time.time() - t0
        return (image_path.stem, final_text, elapsed)

    if concurrency > 1 and total > 1:
        print(f"\nProcessing {total} pages with concurrency={concurrency}")
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            future_to_idx = {
                executor.submit(_process_one, i, img, eng): i
                for i, (img, eng) in enumerate(work_items, 1)
            }
            for future in concurrent.futures.as_completed(future_to_idx):
                try:
                    page_name, final_text, elapsed = future.result()
                    total_elapsed += elapsed
                    results.append((page_name, final_text))
                except Exception as exc:
                    idx = future_to_idx[future]
                    print(f"\n  ERROR on page {idx}: {exc}")
    else:
        for i, (image_path, english_text) in enumerate(work_items, 1):
            page_name, final_text, elapsed = _process_one(i, image_path, english_text)
            total_elapsed += elapsed
            results.append((page_name, final_text))

    # ── Summary ──
    print(f"\n{'='*60}")
    print(f"PIPELINE COMPLETE — {len(results)} page(s) in {total_elapsed:.1f}s")
    for page_name, text in results:
        lines = [l for l in text.strip().split("\n") if l.strip()]
        print(f"  {page_name}: {len(lines)} lines")
    print(f"Output directory: {args.output_dir}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
