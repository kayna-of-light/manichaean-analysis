#!/usr/bin/env python3
"""Second-stage clustering for a coarse glyph cluster.

Global clustering intentionally bins visually similar shapes. When one bin is
internally mixed, this script reclusters only that bin and emits subcluster
montages plus manuscript-context samples for manual assignment.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from sklearn.cluster import MiniBatchKMeans

REPO = Path(__file__).resolve().parents[3]
OCR_DIR = REPO / "output" / "projects" / "kephalaia_ocr"
PAGES_DIR = OCR_DIR / "pages"
CLUSTERS_DIR = OCR_DIR / "clusters"

WARP_HEIGHT = 60
SAUVOLA_W = 12
SAUVOLA_K = 0.2
SAUVOLA_R = 128.0
PATCH = 32
SEED = 42


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sauvola(gray: np.ndarray, w: int, k: float, r: float) -> np.ndarray:
    gray32 = gray.astype(np.float32)
    ksize = 2 * w + 1
    mean = cv2.boxFilter(gray32, ddepth=cv2.CV_32F, ksize=(ksize, ksize), normalize=True, borderType=cv2.BORDER_REFLECT)
    sqmean = cv2.boxFilter(gray32 * gray32, ddepth=cv2.CV_32F, ksize=(ksize, ksize), normalize=True, borderType=cv2.BORDER_REFLECT)
    std = np.sqrt(np.maximum(sqmean - mean * mean, 0.0))
    threshold = mean * (1.0 + k * (std / r - 1.0))
    return (gray32 < threshold).astype(np.uint8)


def warp_quad_to_rect(img: np.ndarray, quad: list[list[float]], h_target: int) -> np.ndarray:
    quad_arr = np.asarray(quad, dtype=np.float32)
    tl, tr, br, bl = quad_arr
    width = int(round(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl))))
    width = max(width, 1)
    dst = np.array([[0, 0], [width - 1, 0], [width - 1, h_target - 1], [0, h_target - 1]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(quad_arr, dst)
    return cv2.warpPerspective(img, matrix, (width, h_target), flags=cv2.INTER_LINEAR, borderValue=255)


def patch_from_blob(ink: np.ndarray, bbox: list[int], preserve_aspect: bool) -> np.ndarray | None:
    x0, y0, x1, y1 = bbox
    crop = ink[y0:y1 + 1, x0:x1 + 1]
    if crop.size == 0:
        return None
    crop = (crop * 255).astype(np.uint8)
    if preserve_aspect:
        target = PATCH - 4
        height, width = crop.shape[:2]
        factor = min(target / max(width, 1), target / max(height, 1))
        resized = cv2.resize(
            crop,
            (max(1, int(round(width * factor))), max(1, int(round(height * factor)))),
            interpolation=cv2.INTER_AREA,
        )
        canvas = np.zeros((PATCH, PATCH), dtype=np.uint8)
        y = (PATCH - resized.shape[0]) // 2
        x = (PATCH - resized.shape[1]) // 2
        canvas[y:y + resized.shape[0], x:x + resized.shape[1]] = resized
        binary = (canvas.astype(np.float32) / 255.0 > 0.4).astype(np.float32)
    else:
        resized = cv2.resize(crop, (PATCH, PATCH), interpolation=cv2.INTER_AREA)
        binary = (resized.astype(np.float32) / 255.0 > 0.4).astype(np.float32)
    if binary.sum() < 1:
        return None
    return binary


def bbox_shape(item: dict) -> tuple[int, int]:
    x0, y0, x1, y1 = item["warped_bbox"]
    return int(x1 - x0 + 1), int(y1 - y0 + 1)


def normalized(values: np.ndarray) -> np.ndarray:
    values = values.astype(np.float32)
    norm = float(np.linalg.norm(values))
    if norm < 1e-6:
        return values
    return values / norm


def count_holes(patch: np.ndarray) -> float:
    ink = (patch > 0).astype(np.uint8) * 255
    contours, hierarchy = cv2.findContours(ink, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return 0.0
    holes = 0
    for index, contour in enumerate(contours):
        parent = hierarchy[0][index][3]
        if parent >= 0 and cv2.contourArea(contour) >= 3.0:
            holes += 1
    return float(min(holes, 4)) / 4.0


def feature_from_patch(
    patch: np.ndarray,
    item: dict,
    geometry_weight: float,
    feature_mode: str,
    pixel_weight: float,
    profile_weight: float,
) -> np.ndarray:
    patch32 = patch.astype(np.float32)
    if feature_mode == "pixels":
        shape = normalized(patch32.flatten())
    elif feature_mode == "shape":
        pixels = normalized(patch32.flatten()) * pixel_weight
        row_profile = normalized(patch32.mean(axis=1)) * profile_weight
        col_profile = normalized(patch32.mean(axis=0)) * profile_weight
        ys, xs = np.nonzero(patch32 > 0)
        if len(xs):
            centroid = np.array([xs.mean() / PATCH, ys.mean() / PATCH], dtype=np.float32)
            spread = np.array([xs.std() / PATCH, ys.std() / PATCH], dtype=np.float32)
        else:
            centroid = np.zeros(2, dtype=np.float32)
            spread = np.zeros(2, dtype=np.float32)
        scalar = np.array([patch32.mean(), count_holes(patch32)], dtype=np.float32)
        shape = np.concatenate([pixels, row_profile, col_profile, centroid, spread, scalar])
    else:
        raise ValueError(f"unknown feature mode: {feature_mode}")
    width, height = bbox_shape(item)
    geom = np.array([
        min(width, 80) / 80.0,
        min(height, 60) / 60.0,
        min(width / max(height, 1), 3.0) / 3.0,
        min(height / max(width, 1), 5.0) / 5.0,
    ], dtype=np.float32) * geometry_weight
    return normalized(np.concatenate([shape, geom]))


def collect_features(
    cluster: int,
    tall_only: bool,
    geometry_weight: float,
    feature_mode: str,
    preserve_aspect: bool,
    clusters_dir: Path,
    pixel_weight: float,
    profile_weight: float,
) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    assignments = load_json(clusters_dir / "_assignments.json")
    items = [item for item in assignments if int(item["cluster"]) == cluster]
    if tall_only:
        items = [item for item in items if 12 <= bbox_shape(item)[0] <= 35 and bbox_shape(item)[1] >= 30]
    if not items:
        raise SystemExit(f"no items for cluster {cluster:02d}")

    page_cache: dict[str, np.ndarray] = {}
    clean_cache: dict[str, dict[int, list[list[float]]]] = {}
    line_cache: dict[tuple[str, int], np.ndarray] = {}
    features = []
    patches = []
    kept = []

    for item in items:
        page = str(item["page"])
        line_index = int(item["line_index"])
        if page not in page_cache:
            body_path = PAGES_DIR / f"keph_p{page}_body.jpg"
            img = cv2.imread(str(body_path), cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            page_cache[page] = img
        if page not in clean_cache:
            clean_path = PAGES_DIR / f"kraken_p{page}_body_clean.json"
            clean = load_json(clean_path)
            clean_cache[page] = {int(line["index"]): line["quad"] for line in clean.get("lines", [])}
        line_key = (page, line_index)
        if line_key not in line_cache:
            quad = clean_cache[page].get(line_index)
            if quad is None:
                continue
            warped = warp_quad_to_rect(page_cache[page], quad, WARP_HEIGHT)
            line_cache[line_key] = sauvola(warped, SAUVOLA_W, SAUVOLA_K, SAUVOLA_R)
        patch = patch_from_blob(line_cache[line_key], item["warped_bbox"], preserve_aspect=preserve_aspect)
        if patch is None:
            continue
        patches.append(patch)
        features.append(feature_from_patch(
            patch,
            item,
            geometry_weight,
            feature_mode=feature_mode,
            pixel_weight=pixel_weight,
            profile_weight=profile_weight,
        ))
        kept.append(item)

    if not features:
        raise SystemExit("no features extracted")
    return np.stack(features).astype(np.float32), np.stack(patches).astype(np.float32), kept


def make_montage(patches: np.ndarray, indices: np.ndarray, n_max: int) -> np.ndarray:
    selected = indices[:n_max]
    cols = 16
    rows = int(np.ceil(len(selected) / cols))
    pad = 2
    cell = PATCH * 2 + pad * 2
    canvas = np.full((rows * cell, cols * cell, 3), 255, dtype=np.uint8)
    for pos, idx in enumerate(selected):
        row = pos // cols
        col = pos % cols
        img = (patches[idx].reshape(PATCH, PATCH) * 255).astype(np.uint8)
        img = 255 - img
        img3 = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        big = cv2.resize(img3, (PATCH * 2, PATCH * 2), interpolation=cv2.INTER_NEAREST)
        y = row * cell + pad
        x = col * cell + pad
        canvas[y:y + PATCH * 2, x:x + PATCH * 2] = big
    return canvas


def crop_context(sample: dict, margin_x: int, margin_y: int, scale: int) -> np.ndarray | None:
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
    cv2.rectangle(crop, (0, 0), (min(crop.shape[1], 230), 22), (255, 255, 255), -1)
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


def natural_key(path: Path) -> tuple[int, str]:
    match = re.search(r"s_(\d+)_", path.name)
    return (int(match.group(1)) if match else -1, path.name)


def spread_indices(idxs: np.ndarray, distances: np.ndarray, samples: int) -> np.ndarray:
    ordered = idxs[np.argsort(distances[idxs])]
    if len(ordered) <= samples:
        return ordered
    picks = np.linspace(0, len(ordered) - 1, samples, dtype=int)
    return ordered[picks]


def make_context_sheet(out_dir: Path, items: list[dict], labels: np.ndarray, distances: np.ndarray, samples: int, tile_w: int, tile_h: int, sampling: str) -> Path:
    rows = []
    for subcluster in sorted(set(int(label) for label in labels)):
        idxs = np.where(labels == subcluster)[0]
        if sampling == "nearest":
            ordered = idxs[np.argsort(distances[idxs])][:samples]
        elif sampling == "spread":
            ordered = spread_indices(idxs, distances, samples)
        else:
            raise ValueError(f"unknown context sampling: {sampling}")
        crops = []
        for idx in ordered[:samples]:
            crop = crop_context(items[int(idx)], margin_x=95, margin_y=50, scale=3)
            if crop is not None:
                crops.append(crop)
        if crops:
            rows.append((subcluster, len(idxs), crops))

    label_w = 170
    header_h = 28
    sheet_w = label_w + samples * tile_w
    sheet_h = header_h + len(rows) * tile_h
    sheet = np.full((sheet_h, sheet_w, 3), 255, dtype=np.uint8)
    cv2.putText(sheet, "subcluster", (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(sheet, f"{sampling} context samples", (label_w + 8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
    for row, (subcluster, count, crops) in enumerate(rows):
        y = header_h + row * tile_h
        cv2.putText(sheet, f"s{subcluster:02d} n={count}", (8, y + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
        for col, crop in enumerate(crops[:samples]):
            x = label_w + col * tile_w
            sheet[y:y + tile_h, x:x + tile_w] = fit_tile(crop, (tile_w, tile_h))
        cv2.line(sheet, (0, y + tile_h - 1), (sheet_w, y + tile_h - 1), (225, 225, 225), 1)
    out = out_dir / f"_context_sheet_{sampling}.png"
    cv2.imwrite(str(out), sheet)
    return out


def run(
    cluster: int,
    n_subclusters: int,
    tall_only: bool,
    geometry_weight: float,
    feature_mode: str,
    preserve_aspect: bool,
    montage: int,
    samples: int,
    clusters_dir: Path,
    pixel_weight: float,
    profile_weight: float,
) -> tuple[Path, Path, Path]:
    features, patches, items = collect_features(
        cluster,
        tall_only,
        geometry_weight,
        feature_mode,
        preserve_aspect,
        clusters_dir,
        pixel_weight,
        profile_weight,
    )
    model = MiniBatchKMeans(n_clusters=n_subclusters, random_state=SEED, batch_size=512, n_init=20, max_iter=500)
    labels = model.fit_predict(features)
    centers = model.cluster_centers_
    distances = np.linalg.norm(features - centers[labels], axis=1)

    suffix = "tall" if tall_only else "all"
    patch_mode = "padded" if preserve_aspect else "stretched"
    cluster_id = f"{cluster:03d}"
    out_dir = clusters_dir / "subclusters" / f"c{cluster_id}_{suffix}_k{n_subclusters:02d}_{feature_mode}_{patch_mode}"
    out_dir.mkdir(parents=True, exist_ok=True)
    assignments = []
    summary = []
    for subcluster in range(n_subclusters):
        idxs = np.where(labels == subcluster)[0]
        if len(idxs) == 0:
            continue
        ordered = idxs[np.argsort(distances[idxs])]
        montage_img = make_montage(patches, ordered, montage)
        cv2.imwrite(str(out_dir / f"s_{subcluster:02d}_n{len(idxs):04d}.png"), montage_img)
        widths = []
        heights = []
        for idx in idxs:
            width, height = bbox_shape(items[int(idx)])
            widths.append(width)
            heights.append(height)
        summary.append({
            "subcluster": subcluster,
            "size": int(len(idxs)),
            "width_p50": float(np.percentile(widths, 50)),
            "height_p50": float(np.percentile(heights, 50)),
            "nearest_samples": [
                {
                    "page": str(items[int(idx)]["page"]),
                    "line_index": int(items[int(idx)]["line_index"]),
                    "blob_id": int(items[int(idx)]["blob_id"]),
                    "warped_bbox": items[int(idx)]["warped_bbox"],
                }
                for idx in ordered[: min(12, len(ordered))]
            ],
        })
    for idx, item in enumerate(items):
        width, height = bbox_shape(item)
        assignments.append({
            "page": str(item["page"]),
            "line_index": int(item["line_index"]),
            "blob_id": int(item["blob_id"]),
            "cluster": cluster_id,
            "subcluster": f"{int(labels[idx]):02d}",
            "distance": float(distances[idx]),
            "warped_bbox": item["warped_bbox"],
            "width": width,
            "height": height,
        })
    (out_dir / "_subassignments.json").write_text(json.dumps(assignments, indent=2, ensure_ascii=False), encoding="utf-8")
    summary_path = out_dir / "_summary.json"
    summary_path.write_text(json.dumps({
        "cluster": cluster_id,
        "source_clusters_dir": str(clusters_dir.relative_to(REPO)),
        "mode": suffix,
        "n_subclusters": n_subclusters,
        "geometry_weight": geometry_weight,
        "pixel_weight": pixel_weight,
        "profile_weight": profile_weight,
        "feature_mode": feature_mode,
        "preserve_aspect": preserve_aspect,
        "n_items": len(items),
        "summary": summary,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    nearest_context_path = make_context_sheet(out_dir, items, labels, distances, samples=samples, tile_w=330, tile_h=220, sampling="nearest")
    spread_context_path = make_context_sheet(out_dir, items, labels, distances, samples=samples, tile_w=330, tile_h=220, sampling="spread")
    return summary_path, nearest_context_path, spread_context_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cluster", type=int)
    parser.add_argument("--n-subclusters", type=int, default=8)
    parser.add_argument("--tall-only", action="store_true")
    parser.add_argument("--geometry-weight", type=float, default=0.5)
    parser.add_argument("--pixel-weight", type=float, default=1.0)
    parser.add_argument("--profile-weight", type=float, default=0.75)
    parser.add_argument("--feature-mode", choices=["pixels", "shape"], default="shape")
    parser.add_argument("--stretch", action="store_true", help="Stretch each blob to a square instead of preserving aspect ratio.")
    parser.add_argument("--montage", type=int, default=128)
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--clusters-dir", type=Path, default=CLUSTERS_DIR)
    args = parser.parse_args()
    clusters_dir = args.clusters_dir if args.clusters_dir.is_absolute() else REPO / args.clusters_dir
    summary_path, nearest_context_path, spread_context_path = run(
        args.cluster,
        args.n_subclusters,
        args.tall_only,
        args.geometry_weight,
        args.feature_mode,
        not args.stretch,
        args.montage,
        args.samples,
        clusters_dir,
        args.pixel_weight,
        args.profile_weight,
    )
    print(summary_path)
    print(nearest_context_path)
    print(spread_context_path)


if __name__ == "__main__":
    main()