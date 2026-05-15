#!/usr/bin/env python3
"""Build a special review sheet showing all blobs that resolve to '?' across the manuscript.

For each ? blob, shows:
  - A crop of the manuscript around the blob (with context)
  - The blob's cluster, source, line, page, and bbox
  - Neighboring blobs for context

Output: a single PNG review sheet.
"""
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

# ── paths ──────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[3]
PAGES_DIR = ROOT / "output" / "projects" / "kephalaia_ocr" / "pages"
REVIEW_DIR = ROOT / "temp" / "projects" / "kephalaia_ocr" / "page_review_sheets"
OUT_PATH = ROOT / "output" / "projects" / "kephalaia_ocr" / "page_review_sheets" / "question_mark_audit.png"

# ── layout constants ───────────────────────────────────────────────────
CONTEXT_PX = 60          # pixels of context around the blob crop
CROP_HEIGHT = 80         # fixed height for each crop row
LABEL_HEIGHT = 22        # height for text label below crop
ROW_PAD = 8              # padding between rows
SHEET_WIDTH = 1200
BG = (245, 240, 230)     # warm paper background
HIGHLIGHT = (220, 60, 40, 80)  # semi-transparent red highlight
TEXT_COLOR = (40, 40, 40)
HEADER_COLOR = (180, 100, 20)


def load_question_blobs() -> list[dict[str, Any]]:
    """Scan all review JSONs and collect items with text='?'."""
    q_items = []
    for pf in sorted(REVIEW_DIR.glob("keph_p*_review.json")):
        page = pf.stem.replace("keph_", "").replace("_review", "")
        data = json.load(open(pf, encoding="utf-8"))
        for row in data.get("rows", []):
            li = row.get("line_index", -1)
            for it in row.get("items", []):
                if str(it.get("text")) == "?":
                    q_items.append(it | {"page": page, "line_index": li})
    return q_items


def load_page_image(page: str) -> Image.Image:
    """Load the body image for a page."""
    path = PAGES_DIR / f"keph_{page}_body.jpg"
    if not path.exists():
        raise FileNotFoundError(path)
    return Image.open(path)


def crop_blob_context(img: Image.Image, bbox: list[float], context: int = CONTEXT_PX) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """Crop around a blob with context. Returns (crop, (rel_x0, rel_y0, rel_x1, rel_y1))."""
    iw, ih = img.size
    bx0, by0, bx1, by1 = [int(round(v)) for v in bbox]
    cx0 = max(0, bx0 - context)
    cy0 = max(0, by0 - context)
    cx1 = min(iw, bx1 + context)
    cy1 = min(ih, by1 + context)
    crop = img.crop((cx0, cy0, cx1, cy1))
    rel = (bx0 - cx0, by0 - cy0, bx1 - cx0, by1 - cy0)
    return crop, rel


def build_sheet(q_items: list[dict[str, Any]]) -> Image.Image:
    """Build the full review sheet image."""
    # Pre-load page images
    pages_needed = sorted(set(it["page"] for it in q_items))
    page_imgs: dict[str, Image.Image] = {}
    for p in pages_needed:
        page_imgs[p] = load_page_image(p)

    # Prepare crops
    crops: list[dict[str, Any]] = []
    for it in q_items:
        bbox = it.get("img_bbox", [0, 0, 10, 10])
        img = page_imgs[it["page"]]
        crop, rel = crop_blob_context(img, bbox)
        crops.append({
            "crop": crop,
            "rel_bbox": rel,
            "item": it,
        })

    # Calculate layout
    try:
        font = ImageFont.truetype("arial.ttf", 14)
        font_header = ImageFont.truetype("arial.ttf", 18)
        font_small = ImageFont.truetype("arial.ttf", 11)
    except Exception:
        font = ImageFont.load_default()
        font_header = font
        font_small = font

    # Each entry: scaled crop + highlight + label
    # Two columns
    cols = 2
    col_width = SHEET_WIDTH // cols
    entries_per_col = math.ceil(len(crops) / cols)
    entry_height = CROP_HEIGHT + LABEL_HEIGHT + 18 + ROW_PAD  # crop + label + sublabel + pad

    header_height = 60
    sheet_height = header_height + entries_per_col * entry_height + 20
    sheet = Image.new("RGB", (SHEET_WIDTH, sheet_height), BG)
    draw = ImageDraw.Draw(sheet)

    # Header
    draw.text((20, 12), "Question Mark Audit — All '?' Blobs", fill=HEADER_COLOR, font=font_header)
    draw.text((20, 36), f"{len(crops)} unresolved blobs across {len(pages_needed)} pages", fill=TEXT_COLOR, font=font_small)

    for i, entry in enumerate(crops):
        col = i // entries_per_col
        row = i % entries_per_col
        x_off = col * col_width + 10
        y_off = header_height + row * entry_height

        crop_img = entry["crop"]
        rel = entry["rel_bbox"]
        it = entry["item"]

        # Scale crop to fit CROP_HEIGHT
        cw, ch = crop_img.size
        if ch > 0:
            scale = CROP_HEIGHT / ch
            new_w = max(1, int(cw * scale))
            new_h = CROP_HEIGHT
            crop_scaled = crop_img.resize((new_w, new_h), Image.LANCZOS)
            # Clamp width
            if new_w > col_width - 20:
                crop_scaled = crop_scaled.crop((0, 0, col_width - 20, new_h))
                new_w = col_width - 20
        else:
            crop_scaled = crop_img
            new_w, new_h = cw, ch
            scale = 1.0

        # Paste crop
        sheet.paste(crop_scaled, (x_off, y_off))

        # Draw highlight rectangle on the blob
        overlay = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        rx0 = int(rel[0] * scale)
        ry0 = int(rel[1] * scale)
        rx1 = int(rel[2] * scale)
        ry1 = int(rel[3] * scale)
        odraw.rectangle([rx0, ry0, rx1, ry1], outline=(220, 40, 40), width=2)
        odraw.rectangle([rx0 - 1, ry0 - 1, rx1 + 1, ry1 + 1], fill=(220, 60, 40, 50))
        sheet.paste(Image.alpha_composite(Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0)), overlay),
                    (x_off, y_off), overlay)

        # Label
        page = it["page"]
        li = it["line_index"]
        bid = it.get("blob_id", "?")
        idx = it.get("index", "?")
        cl = it.get("cluster", "?")
        src = it.get("source", "?")
        bbox = it.get("img_bbox", [])
        bw = round(bbox[2] - bbox[0], 1) if len(bbox) >= 4 else "?"
        bh = round(bbox[3] - bbox[1], 1) if len(bbox) >= 4 else "?"

        label = f"{page} L{li:02d}  blob={bid}  idx={idx}  cluster={cl}  {bw}x{bh}px"
        sublabel = f"source: {src}"
        draw.text((x_off, y_off + CROP_HEIGHT + 2), label, fill=TEXT_COLOR, font=font)
        draw.text((x_off, y_off + CROP_HEIGHT + 16), sublabel, fill=(120, 80, 40), font=font_small)

    return sheet


def main() -> None:
    q_items = load_question_blobs()
    if not q_items:
        print("No '?' blobs found.")
        return
    print(f"Found {len(q_items)} '?' blobs, building review sheet...")
    sheet = build_sheet(q_items)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(str(OUT_PATH), dpi=(150, 150))
    print(f"Saved: {OUT_PATH}")


if __name__ == "__main__":
    main()
