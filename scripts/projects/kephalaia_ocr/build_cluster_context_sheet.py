#!/usr/bin/env python3
"""Build source-context sheets for Kephalaia OCR glyph clusters."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from tqdm import tqdm

REPO = Path(__file__).resolve().parents[3]
PROJECT_DIR = REPO / "output" / "projects" / "kephalaia_ocr"
PAGES_DIR = PROJECT_DIR / "pages"
CLUSTERS_DIR = PROJECT_DIR / "clusters"
CONTEXT_DIR = CLUSTERS_DIR / "context_sheets"


def load_assignments(clusters_dir: Path) -> dict[int, list[dict]]:
    data = json.loads((clusters_dir / "_assignments.json").read_text(encoding="utf-8"))
    by_cluster: dict[int, list[dict]] = defaultdict(list)
    for item in data:
        by_cluster[int(item["cluster"])].append(item)
    return by_cluster


def choose_samples(items: list[dict], n: int) -> list[dict]:
    if len(items) <= n:
        return items
    # Spread samples through the corpus instead of taking adjacent blobs from the same line.
    idxs = np.linspace(0, len(items) - 1, n, dtype=int)
    return [items[int(i)] for i in idxs]


def crop_context(sample: dict, margin_x: int, margin_y: int, scale: int) -> np.ndarray:
    page = sample["page"]
    split_path = PAGES_DIR / f"keph_p{page}_lines_base_split.json"
    body_path = PAGES_DIR / f"keph_p{page}_body.jpg"
    split = json.loads(split_path.read_text(encoding="utf-8"))
    line_index = int(sample["line_index"])
    line = next(line for line in split["lines"] if int(line["line_index"]) == line_index)
    blob_id = int(sample["blob_id"])
    blob = next(b for b in line["blobs"] if int(b["id"]) == blob_id)
    quad = np.array(blob["img_quad"], dtype=np.float32)

    img = cv2.imread(str(body_path), cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError(f"Could not read {body_path}")

    x0 = max(0, int(math.floor(float(quad[:, 0].min()))) - margin_x)
    y0 = max(0, int(math.floor(float(quad[:, 1].min()))) - margin_y)
    x1 = min(img.shape[1], int(math.ceil(float(quad[:, 0].max()))) + margin_x)
    y1 = min(img.shape[0], int(math.ceil(float(quad[:, 1].max()))) + margin_y)
    crop = img[y0:y1, x0:x1].copy()

    q = quad.copy()
    q[:, 0] -= x0
    q[:, 1] -= y0
    cv2.polylines(crop, [q.astype(np.int32)], isClosed=True, color=(0, 0, 255), thickness=2)

    label = f"p{page} l{sample['line_index']} b{blob_id}"
    cv2.rectangle(crop, (0, 0), (min(crop.shape[1], 190), 22), (255, 255, 255), -1)
    cv2.putText(crop, label, (5, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 0, 0), 1, cv2.LINE_AA)

    if scale != 1:
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
    return crop


def fit_tile(img: np.ndarray, size: tuple[int, int], bg: int = 255) -> np.ndarray:
    target_w, target_h = size
    canvas = np.full((target_h, target_w, 3), bg, dtype=np.uint8)
    h, w = img.shape[:2]
    factor = min(target_w / max(w, 1), target_h / max(h, 1), 1.0)
    if factor != 1.0:
        img = cv2.resize(img, (max(1, int(w * factor)), max(1, int(h * factor))), interpolation=cv2.INTER_AREA)
        h, w = img.shape[:2]
    x = (target_w - w) // 2
    y = (target_h - h) // 2
    canvas[y:y + h, x:x + w] = img
    return canvas


def make_sheet(
    cluster_ids: list[int],
    samples_per_cluster: int,
    row_h: int,
    cluster_w: int,
    context_w: int,
    margin_x: int,
    margin_y: int,
    scale: int,
    clusters_dir: Path,
    context_dir: Path,
) -> Path:
    by_cluster = load_assignments(clusters_dir)
    context_dir.mkdir(parents=True, exist_ok=True)

    label_h = 28
    cols = 1 + samples_per_cluster
    sheet_w = cluster_w + samples_per_cluster * context_w
    sheet_h = label_h + len(cluster_ids) * row_h
    sheet = np.full((sheet_h, sheet_w, 3), 255, dtype=np.uint8)

    headers = ["cluster"] + [f"context {i+1}" for i in range(samples_per_cluster)]
    x_positions = [0] + [cluster_w + i * context_w for i in range(samples_per_cluster)]
    widths = [cluster_w] + [context_w] * samples_per_cluster
    for header, x, width in zip(headers, x_positions, widths):
        cv2.putText(sheet, header, (x + 8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
        cv2.line(sheet, (x, label_h - 1), (x + width, label_h - 1), (210, 210, 210), 1)

    for row, cluster_id in enumerate(tqdm(cluster_ids, desc="context sheets", unit="cluster")):
        y = label_h + row * row_h
        cid = f"{cluster_id:03d}"
        cluster_files = sorted(clusters_dir.glob(f"c_{cid}_n*.png"))
        if not cluster_files:
            cid = f"{cluster_id:02d}"
            cluster_files = sorted(clusters_dir.glob(f"c_{cid}_n*.png"))
        if not cluster_files:
            raise FileNotFoundError(f"Missing montage for cluster {cid}")
        montage = cv2.imread(str(cluster_files[0]), cv2.IMREAD_COLOR)
        if montage is None:
            raise RuntimeError(f"Could not read {cluster_files[0]}")
        cv2.putText(sheet, f"c{cid}", (8, y + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2, cv2.LINE_AA)
        sheet[y:y + row_h, 0:cluster_w] = fit_tile(montage, (cluster_w, row_h))

        samples = choose_samples(by_cluster[cluster_id], samples_per_cluster)
        for col, sample in enumerate(samples):
            x = cluster_w + col * context_w
            context = crop_context(sample, margin_x=margin_x, margin_y=margin_y, scale=scale)
            sheet[y:y + row_h, x:x + context_w] = fit_tile(context, (context_w, row_h))

        cv2.line(sheet, (0, y + row_h - 1), (sheet_w, y + row_h - 1), (225, 225, 225), 1)

    width = 3 if max(cluster_ids) >= 100 else 2
    name = f"context_{cluster_ids[0]:0{width}d}_{cluster_ids[-1]:0{width}d}.png"
    out = context_dir / name
    cv2.imwrite(str(out), sheet)
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("clusters", nargs="+", type=int, help="Cluster ids to include, e.g. 0 1 2")
    parser.add_argument("--samples", type=int, default=4, help="Context samples per cluster")
    parser.add_argument("--row-height", type=int, default=270)
    parser.add_argument("--cluster-width", type=int, default=250)
    parser.add_argument("--context-width", type=int, default=330)
    parser.add_argument("--margin-x", type=int, default=90)
    parser.add_argument("--margin-y", type=int, default=38)
    parser.add_argument("--scale", type=int, default=2)
    parser.add_argument("--clusters-dir", type=Path, default=CLUSTERS_DIR)
    parser.add_argument("--context-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out = make_sheet(
        args.clusters,
        args.samples,
        row_h=args.row_height,
        cluster_w=args.cluster_width,
        context_w=args.context_width,
        margin_x=args.margin_x,
        margin_y=args.margin_y,
        scale=args.scale,
        clusters_dir=args.clusters_dir,
        context_dir=args.context_dir or args.clusters_dir / "context_sheets",
    )
    print(out)


if __name__ == "__main__":
    main()
