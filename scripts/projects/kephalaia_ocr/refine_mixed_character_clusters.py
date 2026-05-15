#!/usr/bin/env python3
"""Create blob-level refinements for mixed character clusters.

The global KMeans clusters are useful visual bins, but some bins are mixtures of
nearby glyphs. This script writes a refinement overlay for those cases instead
of forcing a mixed cluster into one character in `_char_assignments.json`.

Currently implemented:
    * cluster 32: split compact theta-like forms from tall mixed forms.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[3]
OCR_DIR = REPO / "output" / "projects" / "kephalaia_ocr"
PAGES_DIR = OCR_DIR / "pages"
CLUSTERS_DIR = OCR_DIR / "clusters"
CONTEXT_DIR = CLUSTERS_DIR / "context_sheets"
OUT_PATH = CLUSTERS_DIR / "_character_cluster_refinements.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def bbox_shape(item: dict) -> tuple[int, int]:
    x0, y0, x1, y1 = item["warped_bbox"]
    return int(x1 - x0 + 1), int(y1 - y0 + 1)


def classify_cluster_32(item: dict) -> tuple[str, str]:
    """Return (label, bucket) for the mixed cluster 32.

    In this manuscript stream, cluster 32 is strongly height-bimodal:
    theta-like forms are compact, while the tall forms need second-stage
    subclustering. Tiny/wide leftovers are not promoted to a character.
    """
    width, height = bbox_shape(item)
    if width <= 8 or height <= 10:
        return "_unknown", "mark_or_noise"
    if width >= 40:
        return "_multi_char_connected", "wide_connected"
    if 12 <= width <= 35 and height >= 30:
        return "_mixed_tall_forms", "tall_mixed_candidate"
    if 12 <= width <= 35 and height <= 28:
        return "ⲑ", "theta_compact"
    return "_unknown", "unclassified_shape"


def crop_blob(sample: dict, margin_x: int, margin_y: int, scale: int) -> np.ndarray | None:
    page = str(sample["page"])
    line_index = int(sample["line_index"])
    blob_id = int(sample["blob_id"])
    split_path = PAGES_DIR / f"keph_p{page}_lines_base_split.json"
    body_path = PAGES_DIR / f"keph_p{page}_body.jpg"
    if not split_path.exists() or not body_path.exists():
        return None
    split = load_json(split_path)
    line = next((line for line in split.get("lines", []) if int(line.get("line_index", -1)) == line_index), None)
    if not line:
        return None
    blob = next((blob for blob in line.get("blobs", []) if int(blob.get("id", -1)) == blob_id), None)
    if not blob or "img_quad" not in blob:
        return None
    img = cv2.imread(str(body_path), cv2.IMREAD_COLOR)
    if img is None:
        return None
    quad = np.array(blob["img_quad"], dtype=np.float32)
    x0 = max(0, int(math.floor(float(quad[:, 0].min()))) - margin_x)
    y0 = max(0, int(math.floor(float(quad[:, 1].min()))) - margin_y)
    x1 = min(img.shape[1], int(math.ceil(float(quad[:, 0].max()))) + margin_x)
    y1 = min(img.shape[0], int(math.ceil(float(quad[:, 1].max()))) + margin_y)
    crop = img[y0:y1, x0:x1].copy()
    q = quad.copy()
    q[:, 0] -= x0
    q[:, 1] -= y0
    cv2.polylines(crop, [q.astype(np.int32)], isClosed=True, color=(0, 0, 255), thickness=2)
    width, height = bbox_shape(sample)
    label = f"p{page} l{line_index} b{blob_id} {width}x{height}"
    cv2.rectangle(crop, (0, 0), (min(crop.shape[1], 225), 22), (255, 255, 255), -1)
    cv2.putText(crop, label, (5, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (0, 0, 0), 1, cv2.LINE_AA)
    if scale != 1:
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
    return crop


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


def refine() -> dict:
    assignments = load_json(CLUSTERS_DIR / "_assignments.json")
    overrides = []
    summary: dict[str, dict] = {}
    cluster_32 = [item for item in assignments if int(item["cluster"]) == 32]
    bucket_counts: Counter = Counter()
    label_counts: Counter = Counter()
    for item in cluster_32:
        label, bucket = classify_cluster_32(item)
        width, height = bbox_shape(item)
        bucket_counts[bucket] += 1
        label_counts[label] += 1
        overrides.append({
            "page": str(item["page"]),
            "line_index": int(item["line_index"]),
            "blob_id": int(item["blob_id"]),
            "cluster": "32",
            "bucket": bucket,
            "label": label,
            "warped_bbox": item["warped_bbox"],
            "width": width,
            "height": height,
        })

    total = len(cluster_32)
    summary["32"] = {
        "total": total,
        "buckets": dict(bucket_counts),
        "labels": dict(label_counts),
        "rules": {
            "tall_mixed_candidate": "12 <= width <= 35 and height >= 30",
            "theta_compact": "12 <= width <= 35 and height <= 28",
            "mark_or_noise": "width <= 8 or height <= 10",
            "wide_connected": "width >= 40",
        },
    }
    return {
        "description": "Blob-level refinements for mixed character clusters.",
        "summary": summary,
        "overrides": overrides,
    }


def make_audit_sheet(refinement: dict, samples_per_bucket: int, tile_w: int, tile_h: int, margin_x: int, margin_y: int, scale: int) -> Path:
    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    by_bucket: dict[str, list[dict]] = defaultdict(list)
    for item in refinement["overrides"]:
        by_bucket[item["bucket"]].append(item)

    bucket_order = ["theta_compact", "tall_mixed_candidate", "mark_or_noise", "wide_connected", "unclassified_shape"]
    rows: list[tuple[str, list[np.ndarray]]] = []
    for bucket in bucket_order:
        crops = []
        for sample in pick_spread(by_bucket.get(bucket, []), samples_per_bucket):
            crop = crop_blob(sample, margin_x, margin_y, scale)
            if crop is not None:
                crops.append(crop)
        if crops:
            rows.append((bucket, crops))

    if not rows:
        raise SystemExit("no audit rows produced")

    label_w = 260
    header_h = 30
    sheet_w = label_w + samples_per_bucket * tile_w
    sheet_h = header_h + len(rows) * tile_h
    sheet = np.full((sheet_h, sheet_w, 3), 255, dtype=np.uint8)
    cv2.putText(sheet, "cluster 32 split", (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(sheet, "samples", (label_w + 8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 0, 0), 1, cv2.LINE_AA)
    for row, (bucket, crops) in enumerate(rows):
        y = header_h + row * tile_h
        label = f"{bucket} ({len(by_bucket[bucket])})"
        cv2.putText(sheet, label, (8, y + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 0, 0), 1, cv2.LINE_AA)
        for col, crop in enumerate(crops[:samples_per_bucket]):
            x = label_w + col * tile_w
            sheet[y:y + tile_h, x:x + tile_w] = fit_tile(crop, (tile_w, tile_h))
        cv2.line(sheet, (0, y + tile_h - 1), (sheet_w, y + tile_h - 1), (225, 225, 225), 1)

    out = CONTEXT_DIR / "character_refinement_c32_shape_buckets.png"
    cv2.imwrite(str(out), sheet)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    parser.add_argument("--samples-per-bucket", type=int, default=8)
    parser.add_argument("--tile-width", type=int, default=320)
    parser.add_argument("--tile-height", type=int, default=220)
    parser.add_argument("--margin-x", type=int, default=95)
    parser.add_argument("--margin-y", type=int, default=50)
    parser.add_argument("--scale", type=int, default=3)
    args = parser.parse_args()
    result = refine()
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    sheet = make_audit_sheet(
        result,
        args.samples_per_bucket,
        args.tile_width,
        args.tile_height,
        args.margin_x,
        args.margin_y,
        args.scale,
    )
    print(args.out)
    print(sheet)
    for cluster, data in result["summary"].items():
        print(cluster, data)


if __name__ == "__main__":
    main()