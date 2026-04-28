#!/usr/bin/env python3
"""Extract Coptic pages from the Kephalaia PDF as high-resolution images.

The Polotsky/Böhlig 1940 critical edition has facing pages:
  - ODD PDF indices (49, 51, 53, ..., 517): Coptic text
  - EVEN PDF indices (48, 50, 52, ..., 518): German translation

This script extracts the Coptic pages as images for OCR/HTR processing.

Usage:
    # Extract all Coptic pages:
    python scripts/extract_kephalaia_pages.py

    # Extract a specific range (printed page numbers):
    python scripts/extract_kephalaia_pages.py --pages 10-20

    # Extract specific pages:
    python scripts/extract_kephalaia_pages.py --pages 10,11,12

    # Preview mode (just list pages, don't extract):
    python scripts/extract_kephalaia_pages.py --preview
"""

import argparse
import sys
from pathlib import Path

import fitz  # PyMuPDF

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
OUTPUT_DIR = REPO_ROOT / "output" / "projects" / "kephalaia" / "coptic" / "images"

# The PDF filename (long IA-style name)
PDF_GLOB = "Kephalaia -- Mani*Stuttgart.pdf"

# Page mapping: PDF index → printed page number
# Coptic pages are at odd PDF indices starting from 49
# PDF index 49 = printed page 10 (first Coptic page)
# PDF index 517 = printed page 244 (last Coptic page)
FIRST_COPTIC_IDX = 49   # PDF page index of first Coptic page
LAST_COPTIC_IDX = 517    # PDF page index of last Coptic page


def pdf_idx_to_printed_page(pdf_idx: int) -> int:
    """Convert PDF page index to printed page number."""
    # PDF index 49 = printed page 10
    # Each Coptic page increments by 1, every 2 PDF pages
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
    pages = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            pages.extend(range(int(start), int(end) + 1))
        else:
            pages.append(int(part))
    return sorted(set(pages))


def extract_pages(pdf_path: Path, printed_pages: list[int] | None = None,
                  dpi: int = 200, preview: bool = False) -> list[Path]:
    """Extract Coptic pages from the PDF as JPEG images.

    Args:
        pdf_path: Path to the Kephalaia PDF
        printed_pages: List of printed page numbers to extract, or None for all
        dpi: Resolution for rendering (200 = good balance of quality/size)
        preview: If True, just list pages without extracting

    Returns:
        List of output file paths
    """
    doc = fitz.open(str(pdf_path))
    print(f"PDF: {pdf_path.name}")
    print(f"Total PDF pages: {doc.page_count}")

    # Build list of (pdf_index, printed_page) pairs
    if printed_pages is None:
        # All Coptic pages
        pairs = []
        for idx in range(FIRST_COPTIC_IDX, LAST_COPTIC_IDX + 1, 2):
            pairs.append((idx, pdf_idx_to_printed_page(idx)))
    else:
        pairs = []
        for pp in printed_pages:
            idx = printed_page_to_pdf_idx(pp)
            if FIRST_COPTIC_IDX <= idx <= LAST_COPTIC_IDX:
                pairs.append((idx, pp))
            else:
                print(f"  WARNING: Printed page {pp} (PDF idx {idx}) out of range, skipping")

    print(f"Coptic pages to extract: {len(pairs)}")
    if not pairs:
        doc.close()
        return []

    if preview:
        for idx, pp in pairs:
            print(f"  PDF idx {idx:3d} → printed page {pp:3d}")
        doc.close()
        return []

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = []

    for i, (idx, pp) in enumerate(pairs):
        page = doc[idx]
        pix = page.get_pixmap(dpi=dpi)

        out_name = f"keph_p{pp:03d}.jpg"
        out_path = OUTPUT_DIR / out_name

        # Save as JPEG
        pix.pil_save(str(out_path), format="JPEG", quality=92)
        size_kb = out_path.stat().st_size / 1024

        print(f"  [{i+1:3d}/{len(pairs)}] PDF idx {idx} → {out_name} "
              f"({pix.width}×{pix.height}, {size_kb:.0f} KB)")
        outputs.append(out_path)

    doc.close()
    print(f"\nExtracted {len(outputs)} pages to {OUTPUT_DIR}")
    return outputs


def main():
    parser = argparse.ArgumentParser(description="Extract Coptic pages from Kephalaia PDF")
    parser.add_argument("--pages", type=str, default=None,
                        help="Printed page numbers to extract (e.g. '10-20' or '10,11,12')")
    parser.add_argument("--dpi", type=int, default=200,
                        help="Rendering resolution (default: 200)")
    parser.add_argument("--preview", action="store_true",
                        help="List pages without extracting")
    args = parser.parse_args()

    pdf_path = find_pdf()
    printed_pages = parse_page_spec(args.pages) if args.pages else None

    extract_pages(pdf_path, printed_pages, args.dpi, args.preview)


if __name__ == "__main__":
    main()
