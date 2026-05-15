#!/usr/bin/env python3
"""Build manuscript-image evidence sheets for candidate Coptic characters.

The Coptic text is used only to locate candidate lines. The sheet itself is
image-grounded: it shows the manuscript line crop and the detected blob cluster
ids over the page image.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[3]
OCR_DIR = REPO / "output" / "projects" / "kephalaia_ocr"
PAGES_DIR = OCR_DIR / "pages"
CLUSTERS_DIR = OCR_DIR / "clusters"
V2_PAGES_DIR = REPO / "output" / "projects" / "kephalaia_v2" / "pages"
OUT_DIR = CLUSTERS_DIR / "context_sheets"

DEFAULT_CHARS = ["ⲅ", "ⲍ", "ⲝ", "ⲫ", "ⲯ", "ϫ"]


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def fit_tile(img: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    target_w, target_h = size
    canvas = np.full((target_h, target_w, 3), 255, dtype=np.uint8)
    h, w = img.shape[:2]
    factor = min(target_w / max(w, 1), target_h / max(h, 1), 1.0)
    if factor != 1.0:
        img = cv2.resize(img, (max(1, int(w * factor)), max(1, int(h * factor))), interpolation=cv2.INTER_AREA)
        h, w = img.shape[:2]
    x = (target_w - w) // 2
    y = (target_h - h) // 2
    canvas[y:y + h, x:x + w] = img
    return canvas


def pick_spread(items: list[dict], n: int) -> list[dict]:
    if len(items) <= n:
        return items
    idxs = np.linspace(0, len(items) - 1, n, dtype=int)
    return [items[int(i)] for i in idxs]


def assignment_index() -> dict[tuple[str, int, int], int]:
    data = load_json(CLUSTERS_DIR / "_assignments.json")
    return {
        (str(item["page"]), int(item["line_index"]), int(item["blob_id"])): int(item["cluster"])
        for item in data
    }


def char_map_reverse() -> dict[str, str]:
    data = load_json(CLUSTERS_DIR / "_char_assignments.json")
    return {cid: label for label, ids in data.items() for cid in ids}


def collect_candidate_lines(chars: list[str]) -> dict[str, list[dict]]:
    by_char: dict[str, list[dict]] = defaultdict(list)
    for path in sorted(V2_PAGES_DIR.glob("p_*.json")):
        page = path.stem.removeprefix("p_")
        data = load_json(path)
        for line in data.get("lines", []):
            text = line.get("coptic", "") or ""
            for char in chars:
                if char in text:
                    by_char[char].append({
                        "page": page,
                        "line_index": int(line.get("i", -1)),
                        "count": text.count(char),
                        "coptic": text,
                    })
    return by_char


def crop_line(page: str, line_index: int, cluster_by_blob: dict[tuple[str, int, int], int], reverse: dict[str, str]) -> np.ndarray | None:
    split_path = PAGES_DIR / f"keph_p{page}_lines_base_split.json"
    body_path = PAGES_DIR / f"keph_p{page}_body.jpg"
    if not split_path.exists() or not body_path.exists():
        return None
    split = load_json(split_path)
    line = next((line for line in split.get("lines", []) if int(line.get("line_index", -1)) == line_index), None)
    if not line:
        return None
    blobs = line.get("blobs", [])
    if not blobs:
        return None
    img = cv2.imread(str(body_path), cv2.IMREAD_COLOR)
    if img is None:
        return None

    quads = [np.array(blob["img_quad"], dtype=np.float32) for blob in blobs if "img_quad" in blob]
    if not quads:
        return None
    all_pts = np.concatenate(quads, axis=0)
    margin_x = 45
    margin_y = 32
    x0 = max(0, int(math.floor(float(all_pts[:, 0].min()))) - margin_x)
    y0 = max(0, int(math.floor(float(all_pts[:, 1].min()))) - margin_y)
    x1 = min(img.shape[1], int(math.ceil(float(all_pts[:, 0].max()))) + margin_x)
    y1 = min(img.shape[0], int(math.ceil(float(all_pts[:, 1].max()))) + margin_y)
    crop = img[y0:y1, x0:x1].copy()

    for blob in blobs:
        quad = np.array(blob["img_quad"], dtype=np.float32)
        q = quad.copy()
        q[:, 0] -= x0
        q[:, 1] -= y0
        blob_id = int(blob["id"])
        cid = cluster_by_blob.get((page, line_index, blob_id))
        if cid is None:
            color = (0, 165, 255)
            label = "oth"
        else:
            cid_s = f"{cid:02d}"
            mapped = reverse.get(cid_s, "?")
            color = (255, 0, 0) if mapped == "_lacuna_dot" else (0, 180, 0)
            if mapped == "_unknown":
                color = (0, 0, 255)
            label = f"c{cid_s}"
        cv2.polylines(crop, [q.astype(np.int32)], isClosed=True, color=color, thickness=1)
        lx = int(max(0, q[:, 0].min()))
        ly = int(max(10, q[:, 1].min() - 3))
        cv2.putText(crop, label, (lx, ly), cv2.FONT_HERSHEY_SIMPLEX, 0.32, color, 1, cv2.LINE_AA)
    return crop


def make_sheet(chars: list[str], samples_per_char: int, tile_w: int, row_h: int) -> tuple[Path, Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates = collect_candidate_lines(chars)
    cluster_by_blob = assignment_index()
    reverse = char_map_reverse()
    rows: list[tuple[str, dict, np.ndarray]] = []
    manifest = {"chars": chars, "samples": []}

    for char in chars:
        picked = pick_spread(candidates.get(char, []), samples_per_char)
        for sample in picked:
            crop = crop_line(sample["page"], sample["line_index"], cluster_by_blob, reverse)
            if crop is None:
                continue
            rows.append((char, sample, crop))
            manifest["samples"].append(sample | {"char": char})

    if not rows:
        raise SystemExit("no evidence rows produced")

    label_w = 240
    header_h = 32
    sheet = np.full((header_h + row_h * len(rows), label_w + tile_w, 3), 255, dtype=np.uint8)
    cv2.putText(sheet, "candidate", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(sheet, "manuscript line crop with cluster ids", (label_w + 8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)

    for row, (char, sample, crop) in enumerate(rows):
        y = header_h + row * row_h
        label = f"{char} p{sample['page']} l{sample['line_index']} x{sample['count']}"
        cv2.putText(sheet, label, (8, y + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 0, 0), 1, cv2.LINE_AA)
        sheet[y:y + row_h, label_w:label_w + tile_w] = fit_tile(crop, (tile_w, row_h))
        cv2.line(sheet, (0, y + row_h - 1), (sheet.shape[1], y + row_h - 1), (225, 225, 225), 1)

    name = "letter_image_evidence_" + "_".join(f"u{ord(ch):04x}" for ch in chars)
    image_path = OUT_DIR / f"{name}.png"
    manifest_path = OUT_DIR / f"{name}.json"
    cv2.imwrite(str(image_path), sheet)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return image_path, manifest_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("chars", nargs="*", default=DEFAULT_CHARS)
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--tile-width", type=int, default=1500)
    parser.add_argument("--row-height", type=int, default=230)
    args = parser.parse_args()
    image_path, manifest_path = make_sheet(args.chars, args.samples, args.tile_width, args.row_height)
    print(image_path)
    print(manifest_path)


if __name__ == "__main__":
    main()