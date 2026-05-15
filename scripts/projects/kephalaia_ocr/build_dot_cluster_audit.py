#!/usr/bin/env python3
"""Build visual audit sheets for dot-like cluster contamination.

This deliberately samples within each cluster by geometry buckets, because the
problem is internal mixing: a cluster can be mostly lacuna dots while still
containing strokes, letter fragments, or other residue.
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
OUT_DIR = CLUSTERS_DIR / "context_sheets"

DEFAULT_CLUSTERS = [2, 34, 35, 46]


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def bbox_shape(item: dict) -> tuple[int, int]:
    x0, y0, x1, y1 = item["warped_bbox"]
    return int(x1 - x0 + 1), int(y1 - y0 + 1)


def bucket_for(item: dict) -> str:
    w, h = bbox_shape(item)
    if w <= 4 and h <= 5:
        return "tiny_dot"
    if w <= 6 and h <= 8:
        return "dot_like"
    if w <= 8 and h >= 14:
        return "tall_stroke"
    if w >= 10 and h <= 10:
        return "wide_mark"
    return "other_mixed"


def pick_spread(items: list[dict], n: int) -> list[dict]:
    if len(items) <= n:
        return items
    idxs = np.linspace(0, len(items) - 1, n, dtype=int)
    return [items[int(i)] for i in idxs]


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
    w, h = bbox_shape(sample)
    label = f"p{page} l{line_index} b{blob_id} {w}x{h}"
    cv2.rectangle(crop, (0, 0), (min(crop.shape[1], 210), 22), (255, 255, 255), -1)
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


def make_audit(clusters: list[int], samples_per_bucket: int, tile_w: int, tile_h: int, margin_x: int, margin_y: int, scale: int) -> tuple[Path, Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    assignments = load_json(CLUSTERS_DIR / "_assignments.json")
    by_cluster: dict[int, list[dict]] = defaultdict(list)
    for item in assignments:
        by_cluster[int(item["cluster"])].append(item)

    rows: list[tuple[int, str, list[np.ndarray]]] = []
    manifest = {"clusters": clusters, "summary": {}}
    for cluster in clusters:
        items = by_cluster.get(cluster, [])
        buckets: dict[str, list[dict]] = defaultdict(list)
        for item in items:
            buckets[bucket_for(item)].append(item)
        manifest["summary"][f"{cluster:02d}"] = {
            "n": len(items),
            "buckets": dict(Counter(bucket_for(item) for item in items)),
        }
        for bucket in ["tiny_dot", "dot_like", "tall_stroke", "wide_mark", "other_mixed"]:
            picked = pick_spread(buckets.get(bucket, []), samples_per_bucket)
            crops = []
            for sample in picked:
                crop = crop_blob(sample, margin_x, margin_y, scale)
                if crop is not None:
                    crops.append(crop)
            if crops:
                rows.append((cluster, bucket, crops))

    if not rows:
        raise SystemExit("no audit rows produced")

    label_w = 245
    header_h = 28
    sheet_w = label_w + samples_per_bucket * tile_w
    sheet_h = header_h + len(rows) * tile_h
    sheet = np.full((sheet_h, sheet_w, 3), 255, dtype=np.uint8)
    cv2.putText(sheet, "cluster/bucket", (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(sheet, "samples", (label_w + 8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)

    for row, (cluster, bucket, crops) in enumerate(rows):
        y = header_h + row * tile_h
        label = f"c{cluster:02d} {bucket}"
        cv2.putText(sheet, label, (8, y + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
        for col, crop in enumerate(crops[:samples_per_bucket]):
            x = label_w + col * tile_w
            sheet[y:y + tile_h, x:x + tile_w] = fit_tile(crop, (tile_w, tile_h))
        cv2.line(sheet, (0, y + tile_h - 1), (sheet_w, y + tile_h - 1), (225, 225, 225), 1)

    suffix = "_".join(f"{cluster:02d}" for cluster in clusters)
    image_path = OUT_DIR / f"dot_cluster_audit_{suffix}.png"
    manifest_path = OUT_DIR / f"dot_cluster_audit_{suffix}.json"
    cv2.imwrite(str(image_path), sheet)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return image_path, manifest_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("clusters", nargs="*", type=int, default=DEFAULT_CLUSTERS)
    parser.add_argument("--samples-per-bucket", type=int, default=6)
    parser.add_argument("--tile-width", type=int, default=260)
    parser.add_argument("--tile-height", type=int, default=190)
    parser.add_argument("--margin-x", type=int, default=75)
    parser.add_argument("--margin-y", type=int, default=42)
    parser.add_argument("--scale", type=int, default=3)
    args = parser.parse_args()
    image_path, manifest_path = make_audit(
        args.clusters,
        args.samples_per_bucket,
        args.tile_width,
        args.tile_height,
        args.margin_x,
        args.margin_y,
        args.scale,
    )
    print(image_path)
    print(manifest_path)


if __name__ == "__main__":
    main()