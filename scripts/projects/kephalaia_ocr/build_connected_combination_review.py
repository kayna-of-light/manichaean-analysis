#!/usr/bin/env python3
"""Diagnose unresolved connected Coptic parent blobs.

This sheet is diagnostic only. It is useful for estimating recurring fused-shape
families, but it is not the correction surface. The root correction surface is
the split-derived child layer produced by `split_connected_base_blobs.py`, then
child clustering/classification.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from sklearn.cluster import MiniBatchKMeans

REPO = Path(__file__).resolve().parents[3]
OCR_ROOT = REPO / "output" / "projects" / "kephalaia_ocr"
PAGES_DIR = OCR_ROOT / "pages"
DEFAULT_CLUSTER_NAME = "clusters_shape_padded_k120"
DEFAULT_WITNESS = OCR_ROOT / "llm_witness" / DEFAULT_CLUSTER_NAME / "composite_line_sequences.jsonl"
DEFAULT_OUT_DIR = REPO / "temp" / "projects" / "kephalaia_ocr" / "connected_combination_review"

WARP_HEIGHT = 60
SAUVOLA_W = 12
SAUVOLA_K = 0.2
SAUVOLA_R = 128.0
PATCH = 40
SEED = 42


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_repo_path(value: str | None, default: Path) -> Path:
    if value is None:
        return default
    path = Path(value)
    return path if path.is_absolute() else REPO / path


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO)).replace("\\", "/")
    except ValueError:
        return str(path)


def bbox(unit: dict[str, Any]) -> list[int]:
    values = (unit.get("geometry") or {}).get("warped_bbox") or unit.get("warped_bbox") or [0, 0, 0, 0]
    return [int(value) for value in values]


def bbox_shape(item: dict[str, Any]) -> tuple[int, int]:
    x0, y0, x1, y1 = item["warped_bbox"]
    return int(x1 - x0 + 1), int(y1 - y0 + 1)


def coptic_base_len(value: str | None) -> int:
    if not value or not isinstance(value, str) or value.startswith("_"):
        return 0
    return sum(1 for char in value if not unicodedata.combining(char))


def normalize_suggestion(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = "".join(char for char in str(value).strip() if not unicodedata.combining(char))
    cleaned = re.sub(r"\s+", "", cleaned)
    return cleaned or None


def is_connected_target(unit: dict[str, Any]) -> bool:
    source = str(unit.get("final_label_source") or "")
    status = str((unit.get("llm_alignment") or {}).get("status") or "")
    if source.startswith("editorial_marker"):
        return False
    if coptic_base_len(unit.get("final_label")) > 1:
        return False
    if "needs_literal" in source:
        return True
    if status == "llm_suggests_connected_reading":
        return True
    return False


LATIN_RE = re.compile(r"[A-Za-zÄÖÜäöüß]")


def contains_latin(value: str) -> bool:
    return bool(LATIN_RE.search(value))


def collect_targets(witness_path: Path, include_latin_lines: bool, include_empty_llm_rows: bool) -> tuple[list[dict[str, Any]], int, int]:
    targets: list[dict[str, Any]] = []
    excluded_latin_lines = 0
    excluded_empty_llm_lines = 0
    with witness_path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            row = json.loads(raw)
            row_text = str(row.get("llm_text") or "")
            has_connected_target = any(is_connected_target(unit) for unit in row.get("units", []))
            if not include_empty_llm_rows and not row_text.strip():
                if has_connected_target:
                    excluded_empty_llm_lines += 1
                continue
            if not include_latin_lines and contains_latin(row_text):
                if has_connected_target:
                    excluded_latin_lines += 1
                continue
            for unit in row.get("units", []):
                if not is_connected_target(unit):
                    continue
                geometry = unit.get("geometry") or {}
                box = bbox(unit)
                width = int(geometry.get("width") or (box[2] - box[0] + 1))
                height = int(geometry.get("height") or (box[3] - box[1] + 1))
                if width <= 0 or height <= 0:
                    continue
                alignment = unit.get("llm_alignment") or {}
                suggestion = normalize_suggestion(alignment.get("llm_text"))
                targets.append({
                    "page": str(row["page"]),
                    "line_index": int(row["line_index"]),
                    "blob_id": int(unit["blob_id"]),
                    "cluster": str(unit.get("cluster")),
                    "warped_bbox": box,
                    "width": width,
                    "height": height,
                    "area": int(geometry.get("area") or width * height),
                    "final_label_source": str(unit.get("final_label_source") or ""),
                    "llm_status": str(alignment.get("status") or ""),
                    "llm_text": row_text,
                    "llm_unit_text": str(alignment.get("llm_text") or ""),
                    "llm_suggestion": suggestion,
                    "candidates": unit.get("candidates") or [],
                })
    return targets, excluded_latin_lines, excluded_empty_llm_lines


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


def patch_from_blob(ink: np.ndarray, box: list[int]) -> np.ndarray | None:
    x0, y0, x1, y1 = box
    crop = ink[y0:y1 + 1, x0:x1 + 1]
    if crop.size == 0:
        return None
    crop = (crop * 255).astype(np.uint8)
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
    if binary.sum() < 1:
        return None
    return binary


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


def feature_from_patch(patch: np.ndarray, item: dict[str, Any], geometry_weight: float) -> np.ndarray:
    patch32 = patch.astype(np.float32)
    pixels = normalized(patch32.flatten())
    row_profile = normalized(patch32.mean(axis=1)) * 0.75
    col_profile = normalized(patch32.mean(axis=0)) * 0.75
    ys, xs = np.nonzero(patch32 > 0)
    if len(xs):
        centroid = np.array([xs.mean() / PATCH, ys.mean() / PATCH], dtype=np.float32)
        spread = np.array([xs.std() / PATCH, ys.std() / PATCH], dtype=np.float32)
    else:
        centroid = np.zeros(2, dtype=np.float32)
        spread = np.zeros(2, dtype=np.float32)
    scalar = np.array([patch32.mean(), count_holes(patch32)], dtype=np.float32)
    width, height = bbox_shape(item)
    geom = np.array([
        min(width, 100) / 100.0,
        min(height, 70) / 70.0,
        min(width / max(height, 1), 5.0) / 5.0,
        min(height / max(width, 1), 6.0) / 6.0,
    ], dtype=np.float32) * geometry_weight
    return normalized(np.concatenate([pixels, row_profile, col_profile, centroid, spread, scalar, geom]))


def collect_features(targets: list[dict[str, Any]], geometry_weight: float) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    page_cache: dict[str, np.ndarray] = {}
    clean_cache: dict[str, dict[int, list[list[float]]]] = {}
    line_cache: dict[tuple[str, int], np.ndarray] = {}
    patches: list[np.ndarray] = []
    features: list[np.ndarray] = []
    kept: list[dict[str, Any]] = []

    for item in targets:
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
            if not clean_path.exists():
                continue
            clean = load_json(clean_path)
            clean_cache[page] = {int(line["index"]): line["quad"] for line in clean.get("lines", [])}
        line_key = (page, line_index)
        if line_key not in line_cache:
            quad = clean_cache[page].get(line_index)
            if quad is None:
                continue
            warped = warp_quad_to_rect(page_cache[page], quad, WARP_HEIGHT)
            line_cache[line_key] = sauvola(warped, SAUVOLA_W, SAUVOLA_K, SAUVOLA_R)
        patch = patch_from_blob(line_cache[line_key], item["warped_bbox"])
        if patch is None:
            continue
        patches.append(patch)
        features.append(feature_from_patch(patch, item, geometry_weight))
        kept.append(item)

    if not features:
        raise SystemExit("no connected combination features extracted")
    return np.stack(features).astype(np.float32), np.stack(patches).astype(np.float32), kept


def geometry_filtered_targets(targets: list[dict[str, Any]], min_width: int, min_aspect: float) -> tuple[list[dict[str, Any]], int]:
    if min_width <= 0 and min_aspect <= 0:
        return targets, 0
    kept: list[dict[str, Any]] = []
    for item in targets:
        width = float(item.get("width") or 0)
        height = float(item.get("height") or 1)
        if min_width > 0 and width < min_width:
            continue
        if min_aspect > 0 and width / max(height, 1.0) < min_aspect:
            continue
        kept.append(item)
    return kept, len(targets) - len(kept)


def crop_context(sample: dict[str, Any], margin_x: int, margin_y: int, scale: int) -> Image.Image | None:
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
    label = f"p{page} l{line_index} b{blob_id} c{sample['cluster']}"
    cv2.rectangle(crop, (0, 0), (min(crop.shape[1], 245), 22), (255, 255, 255), -1)
    cv2.putText(crop, label, (5, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (0, 0, 0), 1, cv2.LINE_AA)
    if scale != 1:
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def fit_tile(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    canvas = Image.new("RGB", size, "white")
    w, h = img.size
    factor = min(target_w / max(w, 1), target_h / max(h, 1), 1.0)
    if factor != 1.0:
        img = img.resize((max(1, int(w * factor)), max(1, int(h * factor))), Image.Resampling.LANCZOS)
        w, h = img.size
    canvas.paste(img, ((target_w - w) // 2, (target_h - h) // 2))
    return canvas


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/seguihis.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                pass
    return ImageFont.load_default()


def pick_spread(indices: np.ndarray, count: int) -> list[int]:
    if len(indices) <= count:
        return [int(index) for index in indices]
    picks = np.linspace(0, len(indices) - 1, count, dtype=int)
    return [int(indices[int(index)]) for index in picks]


def cluster_suggestion(items: list[dict[str, Any]]) -> dict[str, Any]:
    suggestions = Counter(item["llm_suggestion"] for item in items if item.get("llm_suggestion"))
    if not suggestions:
        return {"guess": "?", "evidence": "no LLM connected span", "top": []}
    top = suggestions.most_common(5)
    guess, count = top[0]
    evidence_total = sum(suggestions.values())
    confidence = count / max(evidence_total, 1)
    if count < 2 or confidence < 0.35:
        return {
            "guess": "?",
            "evidence": f"weak LLM suggestions: {count}/{evidence_total}",
            "top": top,
        }
    return {
        "guess": guess,
        "evidence": f"LLM mode {count}/{evidence_total}",
        "top": top,
    }


def summarize_clusters(
    labels: np.ndarray,
    distances: np.ndarray,
    items: list[dict[str, Any]],
    samples_per_cluster: int,
) -> tuple[list[dict[str, Any]], dict[int, str]]:
    raw_rows: list[dict[str, Any]] = []
    for label in sorted(set(int(value) for value in labels)):
        idxs = np.where(labels == label)[0]
        cluster_items = [items[int(index)] for index in idxs]
        ordered = idxs[np.argsort(distances[idxs])]
        spread = pick_spread(ordered, samples_per_cluster)
        suggestion = cluster_suggestion(cluster_items)
        raw_rows.append({
            "kmeans_label": int(label),
            "count": int(len(idxs)),
            "suggestion": suggestion["guess"],
            "suggestion_evidence": suggestion["evidence"],
            "top_suggestions": suggestion["top"],
            "top_coarse_clusters": Counter(item["cluster"] for item in cluster_items).most_common(6),
            "top_statuses": Counter(item["llm_status"] for item in cluster_items).most_common(6),
            "sample_indices": spread,
        })
    raw_rows.sort(key=lambda row: (-int(row["count"]), int(row["kmeans_label"])))
    id_by_label = {int(row["kmeans_label"]): f"CC{index:03d}" for index, row in enumerate(raw_rows)}
    for row in raw_rows:
        row["review_id"] = id_by_label[int(row["kmeans_label"])]
    return raw_rows, id_by_label


def make_sheet(
    rows: list[dict[str, Any]],
    items: list[dict[str, Any]],
    out_path: Path,
    samples_per_cluster: int,
    tile_w: int,
    tile_h: int,
) -> None:
    label_w = 470
    header_h = 38
    row_h = tile_h
    sheet_w = label_w + samples_per_cluster * tile_w
    sheet_h = header_h + len(rows) * row_h
    sheet = Image.new("RGB", (sheet_w, sheet_h), "white")
    draw = ImageDraw.Draw(sheet)
    font = load_font(18)
    small = load_font(14)
    draw.text((8, 8), "connected combination clusters", fill="black", font=font)
    draw.text((label_w + 8, 10), "sample crops, red box = target blob", fill="black", font=small)

    for row_index, row in enumerate(rows):
        y = header_h + row_index * row_h
        draw.line((0, y + row_h - 1, sheet_w, y + row_h - 1), fill=(225, 225, 225), width=1)
        coarse = ", ".join(f"c{cluster}:{count}" for cluster, count in row["top_coarse_clusters"][:4])
        top = ", ".join(f"{text}:{count}" for text, count in row["top_suggestions"][:3]) or "none"
        lines = [
            f"{row['review_id']}  n={row['count']}  guess={row['suggestion']}",
            str(row["suggestion_evidence"]),
            f"coarse {coarse}",
            f"llm {top}",
        ]
        for offset, text in enumerate(lines):
            draw.text((8, y + 10 + offset * 22), text, fill="black", font=font if offset == 0 else small)
        for col, sample_index in enumerate(row["sample_indices"][:samples_per_cluster]):
            item = items[int(sample_index)]
            crop = crop_context(item, margin_x=85, margin_y=44, scale=3)
            if crop is None:
                continue
            tile = fit_tile(crop, (tile_w, tile_h - 22))
            x = label_w + col * tile_w
            sheet.paste(tile, (x, y + 20))
            sample_label = f"{row['review_id']}.{col + 1} p{item['page']} l{item['line_index']} b{item['blob_id']}"
            draw.rectangle((x, y, x + tile_w, y + 21), fill=(255, 255, 255))
            draw.text((x + 4, y + 3), sample_label, fill="black", font=small)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def write_markdown(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Connected Combination Review",
        "",
        "| index | n | quick suggestion | evidence | top coarse clusters | top LLM suggestions |",
        "|---|---:|---|---|---|---|",
    ]
    for row in rows:
        coarse = ", ".join(f"c{cluster}:{count}" for cluster, count in row["top_coarse_clusters"][:5])
        top = ", ".join(f"{text}:{count}" for text, count in row["top_suggestions"][:5]) or "none"
        lines.append(
            f"| {row['review_id']} | {row['count']} | {row['suggestion']} | "
            f"{row['suggestion_evidence']} | {coarse} | {top} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> None:
    witness_path = resolve_repo_path(args.witness, DEFAULT_WITNESS)
    out_dir = resolve_repo_path(args.out_dir, DEFAULT_OUT_DIR)
    targets, excluded_latin_lines, excluded_empty_llm_lines = collect_targets(
        witness_path,
        args.include_latin_lines,
        args.include_empty_llm_rows,
    )
    targets, excluded_by_geometry = geometry_filtered_targets(targets, args.min_width, args.min_aspect)
    features, _patches, items = collect_features(targets, args.geometry_weight)
    k = min(args.k, len(items))
    model = MiniBatchKMeans(n_clusters=k, random_state=SEED, batch_size=512, n_init=20, max_iter=500)
    labels = model.fit_predict(features)
    centers = model.cluster_centers_
    distances = np.linalg.norm(features - centers[labels], axis=1)
    rows, id_by_label = summarize_clusters(labels, distances, items, args.samples)

    assignments = []
    for index, item in enumerate(items):
        label = int(labels[index])
        assignments.append(item | {
            "review_id": id_by_label[label],
            "kmeans_label": label,
            "distance": float(distances[index]),
        })

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "connected_combination_review_manifest.json"
    sheet_path = out_dir / "connected_combination_review_sheet.png"
    table_path = out_dir / "connected_combination_review_table.md"
    manifest = {
        "description": "Visual clustering of unresolved connected/combined Coptic blobs.",
        "generated_from": relative(witness_path),
        "parameters": {
            "k": k,
            "geometry_weight": args.geometry_weight,
            "samples_per_cluster": args.samples,
            "include_latin_lines": args.include_latin_lines,
            "include_empty_llm_rows": args.include_empty_llm_rows,
            "min_width": args.min_width,
            "min_aspect": args.min_aspect,
        },
        "excluded_latin_apparatus_lines": excluded_latin_lines,
        "excluded_empty_llm_lines": excluded_empty_llm_lines,
        "excluded_by_geometry": excluded_by_geometry,
        "target_count_before_feature_filter": len(targets),
        "target_count_clustered": len(items),
        "review_cluster_count": len(rows),
        "rows": rows,
        "assignments": assignments,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(table_path, rows)
    make_sheet(rows, items, sheet_path, args.samples, args.tile_width, args.tile_height)

    print(f"targets before feature filter: {len(targets)}")
    print(f"excluded latin/apparatus lines: {excluded_latin_lines}")
    print(f"excluded empty LLM rows: {excluded_empty_llm_lines}")
    print(f"excluded by geometry: {excluded_by_geometry}")
    print(f"targets clustered: {len(items)}")
    print(f"review clusters: {len(rows)}")
    print(f"sheet: {relative(sheet_path)}")
    print(f"manifest: {relative(manifest_path)}")
    print(f"table: {relative(table_path)}")
    print("largest rows:")
    for row in rows[:12]:
        print(f"  {row['review_id']} n={row['count']} guess={row['suggestion']} {row['suggestion_evidence']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--witness", default=None)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--k", type=int, default=64)
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--geometry-weight", type=float, default=0.8)
    parser.add_argument("--tile-width", type=int, default=260)
    parser.add_argument("--tile-height", type=int, default=190)
    parser.add_argument("--include-latin-lines", action="store_true")
    parser.add_argument("--include-empty-llm-rows", action="store_true")
    parser.add_argument("--min-width", type=int, default=0)
    parser.add_argument("--min-aspect", type=float, default=0.0)
    return parser.parse_args()


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()