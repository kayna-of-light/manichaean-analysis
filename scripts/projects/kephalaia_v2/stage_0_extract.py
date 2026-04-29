#!/usr/bin/env python3
"""
Extract Coptic pages from the Kephalaia PDFs as high-resolution images.

Pipeline stage 0: runs BEFORE stage_1_translate.py.
Produces JPEG images of Coptic manuscript pages for OCR/HTR processing.

Handles BOTH volumes:
  - First half (Polotsky/Böhlig 1940): printed pages 10-244
  - Second half (Böhlig 1966, Zweite Hälfte): printed pages 244cont-291

The critical edition has facing pages:
  - ODD PDF indices: Coptic text
  - EVEN PDF indices: German translation

Output:
  - output/projects/kephalaia_v2/coptic/images/keph_pNNN.jpg

Usage:
    # Extract all Coptic pages (both volumes):
    python scripts/projects/kephalaia_v2/stage_0_extract.py

    # Extract a specific range (printed page numbers):
    python scripts/projects/kephalaia_v2/stage_0_extract.py --pages 10-20

    # Extract specific pages:
    python scripts/projects/kephalaia_v2/stage_0_extract.py --pages 10,11,250

    # Preview mode (just list pages, don't extract):
    python scripts/projects/kephalaia_v2/stage_0_extract.py --preview

    # Only first half:
    python scripts/projects/kephalaia_v2/stage_0_extract.py --volume first

    # Only second half:
    python scripts/projects/kephalaia_v2/stage_0_extract.py --volume second
"""
import argparse
import sys
from pathlib import Path

import fitz  # PyMuPDF

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = REPO_ROOT / "data"
OUTPUT_DIR = (
    REPO_ROOT / "output" / "projects" / "kephalaia_v2" / "coptic" / "images"
)

# ---------------------------------------------------------------------------
# First half: Polotsky/Böhlig 1940 (pp. 10-244)
# ---------------------------------------------------------------------------

FIRST_HALF_GLOB = "Kephalaia -- Mani*Stuttgart.pdf"
FIRST_HALF_FIRST_IDX = 49    # PDF page index of first Coptic page
FIRST_HALF_LAST_IDX = 517    # PDF page index of last Coptic page
FIRST_HALF_FIRST_PAGE = 10   # Printed page number at FIRST_IDX


def first_half_idx_to_page(pdf_idx: int) -> int:
    """Convert first-half PDF index to printed page number."""
    return FIRST_HALF_FIRST_PAGE + (pdf_idx - FIRST_HALF_FIRST_IDX) // 2


def first_half_page_to_idx(printed_page: int) -> int:
    """Convert printed page number to first-half PDF index."""
    return FIRST_HALF_FIRST_IDX + (printed_page - FIRST_HALF_FIRST_PAGE) * 2


# ---------------------------------------------------------------------------
# Second half: Böhlig 1966 Zweite Hälfte (pp. 244cont-291)
# ---------------------------------------------------------------------------

SECOND_HALF_GLOB = "Kephalaia_ Zweite Hälfte*Band I.pdf"
SECOND_HALF_FIRST_IDX = 3    # PDF page index of first Coptic page
SECOND_HALF_LAST_IDX = 97    # PDF page index of last Coptic page
SECOND_HALF_FIRST_PAGE = 244  # Printed page number at FIRST_IDX


def second_half_idx_to_page(pdf_idx: int) -> int:
    """Convert second-half PDF index to printed page number."""
    return SECOND_HALF_FIRST_PAGE + (pdf_idx - SECOND_HALF_FIRST_IDX) // 2


def second_half_page_to_idx(printed_page: int) -> int:
    """Convert printed page number to second-half PDF index."""
    return SECOND_HALF_FIRST_IDX + (printed_page - SECOND_HALF_FIRST_PAGE) * 2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_pdf(glob_pattern: str) -> Path | None:
    """Find a PDF in the data directory."""
    matches = list(DATA_DIR.glob(glob_pattern))
    return matches[0] if matches else None


def parse_page_spec(spec: str) -> list[int]:
    """Parse page specification like '10-20' or '10,11,12'."""
    pages = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            pages.extend(range(int(start), int(end) + 1))
        else:
            pages.append(int(part))
    return sorted(set(pages))


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def extract_first_half(
    printed_pages: list[int] | None = None,
    dpi: int = 200,
    preview: bool = False,
) -> list[Path]:
    """Extract Coptic pages from the first-half PDF."""
    pdf_path = find_pdf(FIRST_HALF_GLOB)
    if pdf_path is None:
        print(f"  WARNING: First-half PDF not found ({FIRST_HALF_GLOB})")
        return []

    doc = fitz.open(str(pdf_path))
    print(f"\nFirst half: {pdf_path.name}")
    print(f"  PDF pages: {doc.page_count}")

    # Build page pairs
    if printed_pages is None:
        pairs = [
            (idx, first_half_idx_to_page(idx))
            for idx in range(
                FIRST_HALF_FIRST_IDX, FIRST_HALF_LAST_IDX + 1, 2
            )
        ]
    else:
        pairs = []
        for pp in printed_pages:
            if pp > 244:
                continue  # belongs to second half
            idx = first_half_page_to_idx(pp)
            if FIRST_HALF_FIRST_IDX <= idx <= FIRST_HALF_LAST_IDX:
                pairs.append((idx, pp))

    if not pairs:
        doc.close()
        return []

    print(f"  Pages to extract: {len(pairs)} (p.{pairs[0][1]}-p.{pairs[-1][1]})")

    if preview:
        for idx, pp in pairs:
            print(f"    PDF idx {idx:3d} → p.{pp:3d}")
        doc.close()
        return []

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = []

    for i, (idx, pp) in enumerate(pairs):
        page = doc[idx]
        pix = page.get_pixmap(dpi=dpi)
        out_path = OUTPUT_DIR / f"keph_p{pp:03d}.jpg"
        pix.pil_save(str(out_path), format="JPEG", quality=92)
        size_kb = out_path.stat().st_size / 1024
        print(
            f"    [{i+1:3d}/{len(pairs)}] p.{pp:3d} "
            f"({pix.width}×{pix.height}, {size_kb:.0f} KB)"
        )
        outputs.append(out_path)

    doc.close()
    return outputs


def extract_second_half(
    printed_pages: list[int] | None = None,
    dpi: int = 200,
    preview: bool = False,
) -> list[Path]:
    """Extract Coptic pages from the second-half PDF."""
    pdf_path = find_pdf(SECOND_HALF_GLOB)
    if pdf_path is None:
        print(f"  WARNING: Second-half PDF not found ({SECOND_HALF_GLOB})")
        return []

    doc = fitz.open(str(pdf_path))
    print(f"\nSecond half: {pdf_path.name}")
    print(f"  PDF pages: {doc.page_count}")

    # Build page pairs
    if printed_pages is None:
        pairs = [
            (idx, second_half_idx_to_page(idx))
            for idx in range(
                SECOND_HALF_FIRST_IDX, SECOND_HALF_LAST_IDX + 1, 2
            )
        ]
    else:
        pairs = []
        for pp in printed_pages:
            if pp < 244:
                continue  # belongs to first half
            idx = second_half_page_to_idx(pp)
            if SECOND_HALF_FIRST_IDX <= idx <= SECOND_HALF_LAST_IDX:
                pairs.append((idx, pp))

    if not pairs:
        doc.close()
        return []

    print(f"  Pages to extract: {len(pairs)} (p.{pairs[0][1]}-p.{pairs[-1][1]})")

    if preview:
        for idx, pp in pairs:
            suffix = " (continuation, lines 21+)" if pp == 244 else ""
            print(f"    PDF idx {idx:3d} → p.{pp:3d}{suffix}")
        doc.close()
        return []

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = []

    for i, (idx, pp) in enumerate(pairs):
        page = doc[idx]
        pix = page.get_pixmap(dpi=dpi)
        # Page 244 from second half is continuation (lines 21+)
        if pp == 244:
            out_path = OUTPUT_DIR / f"keph_p{pp:03d}_cont.jpg"
        else:
            out_path = OUTPUT_DIR / f"keph_p{pp:03d}.jpg"
        pix.pil_save(str(out_path), format="JPEG", quality=92)
        size_kb = out_path.stat().st_size / 1024
        suffix = " (cont)" if pp == 244 else ""
        print(
            f"    [{i+1:3d}/{len(pairs)}] p.{pp:3d}{suffix} "
            f"({pix.width}×{pix.height}, {size_kb:.0f} KB)"
        )
        outputs.append(out_path)

    doc.close()
    return outputs


# ---------------------------------------------------------------------------
# CLI & Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Stage 0: Extract Coptic pages from Kephalaia PDFs"
    )
    parser.add_argument(
        "--pages", type=str, default=None,
        help="Printed page numbers (e.g. '10-20' or '10,250,260')",
    )
    parser.add_argument(
        "--dpi", type=int, default=200,
        help="Rendering resolution (default: 200)",
    )
    parser.add_argument("--preview", action="store_true")
    parser.add_argument(
        "--volume", choices=["first", "second", "both"], default="both",
        help="Which volume to extract (default: both)",
    )
    args = parser.parse_args()

    print("Stage 0: Extract Coptic Page Images")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"  DPI: {args.dpi}")

    printed_pages = parse_page_spec(args.pages) if args.pages else None
    outputs = []

    if args.volume in ("first", "both"):
        outputs.extend(
            extract_first_half(printed_pages, args.dpi, args.preview)
        )

    if args.volume in ("second", "both"):
        outputs.extend(
            extract_second_half(printed_pages, args.dpi, args.preview)
        )

    if not args.preview:
        print(f"\nTotal extracted: {len(outputs)} pages → {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
