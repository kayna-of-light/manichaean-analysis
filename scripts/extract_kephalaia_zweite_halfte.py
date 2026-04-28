#!/usr/bin/env python3
"""Extract Coptic pages from the Kephalaia Zweite Hälfte (Second Half) PDF.

The Böhlig 1966 continuation (Lieferung 11/12) has facing pages:
  - ODD PDF indices (3, 5, 7, ..., 97): Coptic text (printed pp 244-291)
  - EVEN PDF indices (4, 6, 8, ..., 98): German translation

PDF pages 0-2 are front matter (title, foreword), page 99 is back cover.

NOTE: Printed page 244 lines 1-20 are already in the first-half PDF.
      The second-half PDF starts page 244 at line 21. We extract it as
      keph_p244_cont.jpg to avoid overwriting the first-half extraction.

Usage:
    # Extract all Coptic pages (245-291 + 244 continuation):
    python scripts/extract_kephalaia_zweite_halfte.py

    # Extract specific range:
    python scripts/extract_kephalaia_zweite_halfte.py --pages 245-260

    # Preview mode:
    python scripts/extract_kephalaia_zweite_halfte.py --preview
"""

import argparse
import sys
from pathlib import Path

import fitz  # PyMuPDF

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
OUTPUT_DIR = REPO_ROOT / "output" / "projects" / "kephalaia" / "coptic" / "images"

# The PDF filename
PDF_GLOB = "Kephalaia_ Zweite Hälfte*Band I.pdf"

# Page mapping for the Zweite Hälfte PDF:
# PDF index 3 = printed page 244 (continuation, lines 21+)
# PDF index 5 = printed page 245
# ...
# PDF index 97 = printed page 291
FIRST_COPTIC_IDX = 3
LAST_COPTIC_IDX = 97
FIRST_PRINTED_PAGE = 244


def pdf_idx_to_printed_page(pdf_idx: int) -> int:
    """Convert PDF page index to printed page number."""
    return FIRST_PRINTED_PAGE + (pdf_idx - FIRST_COPTIC_IDX) // 2


def printed_page_to_pdf_idx(printed_page: int) -> int:
    """Convert printed page number to PDF page index."""
    return FIRST_COPTIC_IDX + (printed_page - FIRST_PRINTED_PAGE) * 2


def find_pdf() -> Path:
    """Find the Zweite Hälfte PDF in the data directory."""
    matches = list(DATA_DIR.glob(PDF_GLOB))
    if not matches:
        print(f"ERROR: No PDF matching '{PDF_GLOB}' found in {DATA_DIR}")
        sys.exit(1)
    return matches[0]


def parse_page_spec(spec: str) -> list[int]:
    """Parse page specification like '245-260' or '245,250,260' into printed page numbers."""
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
    """Extract Coptic pages from the Zweite Hälfte PDF as JPEG images.

    Page 244 is saved as keph_p244_cont.jpg (continuation lines 21+).
    Pages 245-291 are saved as keph_pNNN.jpg (standard naming).
    """
    doc = fitz.open(str(pdf_path))
    print(f"PDF: {pdf_path.name}")
    print(f"Total PDF pages: {doc.page_count}")

    # Build list of (pdf_index, printed_page) pairs
    if printed_pages is None:
        # All Coptic pages (244-291)
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
            suffix = " (continuation, lines 21+)" if pp == 244 else ""
            print(f"  PDF idx {idx:3d} → printed page {pp:3d}{suffix}")
        doc.close()
        return []

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = []

    for i, (idx, pp) in enumerate(pairs):
        page = doc[idx]
        pix = page.get_pixmap(dpi=dpi)

        # Page 244 gets special suffix to avoid overwriting first-half extraction
        if pp == 244:
            out_name = f"keph_p{pp:03d}_cont.jpg"
        else:
            out_name = f"keph_p{pp:03d}.jpg"

        out_path = OUTPUT_DIR / out_name
        pix.pil_save(str(out_path), format="JPEG", quality=92)
        size_kb = out_path.stat().st_size / 1024

        suffix = " (continuation)" if pp == 244 else ""
        print(f"  [{i+1:3d}/{len(pairs)}] PDF idx {idx} → {out_name} "
              f"({pix.width}×{pix.height}, {size_kb:.0f} KB){suffix}")
        outputs.append(out_path)

    doc.close()
    print(f"\nExtracted {len(outputs)} pages to {OUTPUT_DIR}")
    return outputs


def main():
    parser = argparse.ArgumentParser(
        description="Extract Coptic pages from Kephalaia Zweite Hälfte PDF")
    parser.add_argument("--pages", type=str, default=None,
                        help="Printed page numbers to extract (e.g. '245-260' or '245,250')")
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
