#!/usr/bin/env python3
"""Global shape-first clustering of Kephalaia base blobs.

This reruns the clustering layer from existing per-page segmentation artifacts.
It does not rerun Kraken or line/base splitting. Compared with the original
`cluster_base_global.py`, this version preserves glyph aspect ratio in the
patches and uses shape features beyond raw stretched pixels.
"""

from __future__ import annotations

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import cv2
import numpy as np
from sklearn.cluster import MiniBatchKMeans
from tqdm import tqdm

REPO = Path(__file__).resolve().parents[3]
PAGES_DIR = REPO / "output" / "projects" / "kephalaia_ocr" / "pages"
OUT_ROOT = REPO / "output" / "projects" / "kephalaia_ocr"

WARP_HEIGHT = 60
SAUVOLA_W = 12
SAUVOLA_K = 0.2
SAUVOLA_R = 128.0
PATCH = 32
SEED = 42

SPLIT_RE = re.compile(r"^keph_p([0-9]+(?:_cont)?)_lines_base_split\.json$")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_repo_path(value: str | None, default: Path) -> Path:
    if value is None:
        return default
    path = Path(value)
    return path if path.is_absolute() else REPO / path


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
    return binary.astype(np.uint8)


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


def bbox_shape(item: dict) -> tuple[int, int]:
    x0, y0, x1, y1 = item["warped_bbox"]
    return int(x1 - x0 + 1), int(y1 - y0 + 1)


def feature_from_patch(
    patch: np.ndarray,
    item: dict,
    pixel_weight: float,
    profile_weight: float,
    geometry_weight: float,
) -> np.ndarray:
    patch32 = patch.astype(np.float32)
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
    width, height = bbox_shape(item)
    geometry = np.array([
        min(width, 80) / 80.0,
        min(height, 60) / 60.0,
        min(width / max(height, 1), 3.0) / 3.0,
        min(height / max(width, 1), 5.0) / 5.0,
    ], dtype=np.float32) * geometry_weight
    return normalized(np.concatenate([pixels, row_profile, col_profile, centroid, spread, scalar, geometry]))


def collect_page(
    split_path: Path,
    preserve_aspect: bool,
    pixel_weight: float,
    profile_weight: float,
    geometry_weight: float,
) -> tuple[str, list[np.ndarray], list[np.ndarray], list[dict], str | None]:
    match = SPLIT_RE.match(split_path.name)
    if not match:
        return "", [], [], [], "filename did not match"
    page = match.group(1)
    body_path = PAGES_DIR / f"keph_p{page}_body.jpg"
    clean_path = PAGES_DIR / f"kraken_p{page}_body_clean.json"
    if not body_path.exists() or not clean_path.exists():
        return page, [], [], [], "missing body/clean"

    img = cv2.imread(str(body_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return page, [], [], [], "could not read body image"
    clean = load_json(clean_path)
    quad_by_idx = {int(line["index"]): line["quad"] for line in clean.get("lines", [])}
    split = load_json(split_path)
    line_cache: dict[int, np.ndarray] = {}
    features = []
    patches = []
    meta = []

    for line in split.get("lines", []):
        line_index = int(line["line_index"])
        quad = quad_by_idx.get(line_index)
        if quad is None:
            continue
        if line_index not in line_cache:
            warped = warp_quad_to_rect(img, quad, WARP_HEIGHT)
            line_cache[line_index] = sauvola(warped, SAUVOLA_W, SAUVOLA_K, SAUVOLA_R)
        ink = line_cache[line_index]
        for blob in line.get("blobs", []):
            if blob.get("kind") != "base":
                continue
            item = {
                "page": page,
                "line_index": line_index,
                "blob_id": int(blob["id"]),
                "warped_bbox": blob["warped_bbox"],
                "area": int(blob.get("area", 0)),
            }
            for key in (
                "source_blob_id",
                "parent_blob_id",
                "split_child_index",
                "split_child_count",
                "split_expected_text",
                "split_expected_base",
                "split_method",
                "split_reason",
                "split_confidence",
                "parent_warped_bbox",
                "cut_positions",
            ):
                if key in blob:
                    item[key] = blob[key]
            patch = patch_from_blob(ink, item["warped_bbox"], preserve_aspect=preserve_aspect)
            if patch is None:
                continue
            patches.append(patch)
            features.append(feature_from_patch(patch, item, pixel_weight, profile_weight, geometry_weight))
            meta.append(item)
    return page, features, patches, meta, None


def collect(args: argparse.Namespace) -> tuple[np.ndarray, np.ndarray, list[dict], list[dict]]:
    split_dir = resolve_repo_path(args.split_dir, PAGES_DIR)
    files = sorted(split_dir.glob(args.split_glob))
    all_rows: list[tuple[np.ndarray, np.ndarray, dict]] = []
    failures = []
    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {
            executor.submit(
                collect_page,
                path,
                not args.stretch,
                args.pixel_weight,
                args.profile_weight,
                args.geometry_weight,
            ): path
            for path in files
        }
        for future in tqdm(as_completed(futures), total=len(futures), desc="collect pages", unit="page"):
            page, features, patches, meta, error = future.result()
            if error:
                failures.append({"page": page, "path": str(futures[future]), "error": error})
                continue
            all_rows.extend(zip(features, patches, meta))
    if not all_rows:
        raise SystemExit("no features collected")
    all_rows.sort(key=lambda row: (str(row[2]["page"]), int(row[2]["line_index"]), int(row[2]["blob_id"])))
    features = np.stack([row[0] for row in all_rows]).astype(np.float32)
    patches = np.stack([row[1] for row in all_rows]).astype(np.uint8)
    meta = [row[2] for row in all_rows]
    return features, patches, meta, failures


def passthrough_metadata(item: dict) -> dict:
    return {
        key: item[key]
        for key in (
            "source_blob_id",
            "parent_blob_id",
            "split_child_index",
            "split_child_count",
            "split_expected_text",
            "split_expected_base",
            "split_method",
            "split_reason",
            "split_confidence",
            "parent_warped_bbox",
            "cut_positions",
        )
        if key in item
    }


def make_cluster_montage(patches: np.ndarray, indices: np.ndarray, n_max: int) -> np.ndarray:
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


def make_overview(patches: np.ndarray, labels: np.ndarray, sizes: np.ndarray) -> np.ndarray:
    n_clusters = len(sizes)
    cols = 10
    rows = int(np.ceil(n_clusters / cols))
    cell_pad = 4
    label_h = 18
    cell_w = PATCH * 3 + cell_pad * 2
    cell_h = PATCH * 3 + cell_pad * 2 + label_h
    canvas = np.full((rows * cell_h, cols * cell_w, 3), 255, dtype=np.uint8)
    order = np.argsort(-sizes)
    for position, cluster_id in enumerate(order):
        row = position // cols
        col = position % cols
        idxs = np.where(labels == cluster_id)[0]
        mean_patch = patches[idxs].mean(axis=0) if len(idxs) else np.zeros((PATCH, PATCH), dtype=np.float32)
        img = (255 - (mean_patch.reshape(PATCH, PATCH) * 255)).astype(np.uint8)
        img3 = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        big = cv2.resize(img3, (PATCH * 3, PATCH * 3), interpolation=cv2.INTER_NEAREST)
        y = row * cell_h + cell_pad
        x = col * cell_w + cell_pad
        canvas[y:y + PATCH * 3, x:x + PATCH * 3] = big
        label = f"c{cluster_id:03d} n={int(sizes[cluster_id])}"
        cv2.putText(canvas, label, (x, y + PATCH * 3 + label_h - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1, cv2.LINE_AA)
    return canvas


def run(args: argparse.Namespace) -> Path:
    output_name = args.output_name or f"clusters_shape_padded_k{args.n_clusters:03d}"
    out = OUT_ROOT / output_name
    out.mkdir(parents=True, exist_ok=True)

    features, patches, meta, failures = collect(args)
    print(f"FEATURE MATRIX: {features.shape}  blobs={len(meta)}")
    model = MiniBatchKMeans(
        n_clusters=args.n_clusters,
        random_state=SEED,
        batch_size=args.batch_size,
        n_init=args.n_init,
        max_iter=args.max_iter,
    )
    labels = model.fit_predict(features)
    centers = model.cluster_centers_
    distances = np.linalg.norm(features - centers[labels], axis=1)
    sizes = np.bincount(labels, minlength=args.n_clusters)

    cv2.imwrite(str(out / "_overview.png"), make_overview(patches, labels, sizes))
    for cluster_id in tqdm(range(args.n_clusters), desc="write montages", unit="cluster"):
        idxs = np.where(labels == cluster_id)[0]
        if len(idxs) == 0:
            continue
        ordered = idxs[np.argsort(distances[idxs])]
        montage = make_cluster_montage(patches, ordered, args.montage)
        cv2.imwrite(str(out / f"c_{cluster_id:03d}_n{len(idxs):04d}.png"), montage)

    assignments = []
    for index, item in enumerate(meta):
        assignments.append({
            "page": item["page"],
            "line_index": item["line_index"],
            "blob_id": item["blob_id"],
            "warped_bbox": item["warped_bbox"],
            "area": item["area"],
            "cluster": int(labels[index]),
            "distance": float(distances[index]),
        } | passthrough_metadata(item))
    (out / "_assignments.json").write_text(json.dumps(assignments, indent=2), encoding="utf-8")

    coverage = []
    for cluster_id in range(args.n_clusters):
        idxs = np.where(labels == cluster_id)[0]
        pages = sorted({meta[int(idx)]["page"] for idx in idxs})
        widths = []
        heights = []
        for idx in idxs:
            width, height = bbox_shape(meta[int(idx)])
            widths.append(width)
            heights.append(height)
        coverage.append({
            "cluster": int(cluster_id),
            "size": int(len(idxs)),
            "n_pages": len(pages),
            "pages_sample": pages[:10],
            "width_p50": float(np.percentile(widths, 50)) if widths else 0.0,
            "height_p50": float(np.percentile(heights, 50)) if heights else 0.0,
        })
    coverage.sort(key=lambda row: -row["size"])
    summary = {
        "n_blobs": int(len(meta)),
        "n_clusters": int(args.n_clusters),
        "patch": PATCH,
        "preserve_aspect": not args.stretch,
        "weights": {
            "pixel": args.pixel_weight,
            "profile": args.profile_weight,
            "geometry": args.geometry_weight,
        },
        "kmeans": {
            "batch_size": args.batch_size,
            "n_init": args.n_init,
            "max_iter": args.max_iter,
            "random_state": SEED,
        },
        "split_input": {
            "split_dir": str(resolve_repo_path(args.split_dir, PAGES_DIR).relative_to(REPO))
            if resolve_repo_path(args.split_dir, PAGES_DIR).is_relative_to(REPO)
            else str(resolve_repo_path(args.split_dir, PAGES_DIR)),
            "split_glob": args.split_glob,
        },
        "cluster_sizes_desc": sorted(sizes.tolist(), reverse=True),
        "coverage": coverage,
        "failures": failures,
    }
    (out / "_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(out)
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-clusters", type=int, default=120)
    parser.add_argument("--output-name", default=None)
    parser.add_argument("--split-dir", default=None)
    parser.add_argument("--split-glob", default="keph_p*_lines_base_split.json")
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=4096)
    parser.add_argument("--n-init", type=int, default=5)
    parser.add_argument("--max-iter", type=int, default=300)
    parser.add_argument("--montage", type=int, default=128)
    parser.add_argument("--stretch", action="store_true", help="Stretch each blob to a square instead of preserving aspect ratio.")
    parser.add_argument("--pixel-weight", type=float, default=1.0)
    parser.add_argument("--profile-weight", type=float, default=0.75)
    parser.add_argument("--geometry-weight", type=float, default=0.5)
    return parser.parse_args()


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()