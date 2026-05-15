#!/usr/bin/env python3
"""Create derived base-split files with connected Coptic blobs cut into children.

This is the root-fix layer for fused glyphs. It does not overwrite the original
`keph_pNNN_lines_base_split.json` files. Instead it writes a parallel split
directory where selected parent blobs are replaced by child blobs with
`parent_blob_id` and `split_child_index` provenance. The global clusterer can
then classify those children as ordinary single-character shapes.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from tqdm import tqdm

REPO = Path(__file__).resolve().parents[3]
OCR_ROOT = REPO / "output" / "projects" / "kephalaia_ocr"
PAGES_DIR = OCR_ROOT / "pages"
DEFAULT_WITNESS = OCR_ROOT / "llm_witness" / "clusters_shape_padded_k120" / "composite_line_sequences.jsonl"
DEFAULT_OUT_DIR = OCR_ROOT / "pages_base_split_chars"
DEFAULT_CLUSTERS_DIR = OCR_ROOT / "clusters_shape_padded_k120"

WARP_HEIGHT = 60
SAUVOLA_W = 12
SAUVOLA_K = 0.2
SAUVOLA_R = 128.0
LATIN_RE = re.compile(r"[A-Za-zÄÖÜäöüß]")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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


def is_coptic_base(char: str) -> bool:
    code = ord(char)
    return 0x2C80 <= code <= 0x2CFF or 0x03E2 <= code <= 0x03EF


def coptic_bases(value: str | None) -> list[str]:
    if not value or not isinstance(value, str) or value.startswith("_"):
        return []
    return [char for char in unicodedata.normalize("NFD", value) if is_coptic_base(char)]


def normalized_text(value: str | None) -> str | None:
    bases = coptic_bases(value)
    return "".join(bases) if bases else None


def contains_latin(value: str) -> bool:
    return bool(LATIN_RE.search(value))


def bbox(unit: dict[str, Any]) -> list[int]:
    values = (unit.get("geometry") or {}).get("warped_bbox") or unit.get("warped_bbox") or [0, 0, 0, 0]
    return [int(value) for value in values]


def bbox_width(box: list[int]) -> int:
    return int(box[2] - box[0] + 1)


def bbox_height(box: list[int]) -> int:
    return int(box[3] - box[1] + 1)


def unit_target(unit: dict[str, Any], row_text: str, args: argparse.Namespace) -> dict[str, Any] | None:
    source = str(unit.get("final_label_source") or "")
    if source.startswith("editorial_marker"):
        return None

    final_text = normalized_text(unit.get("final_label"))
    alignment = unit.get("llm_alignment") or {}
    llm_text = normalized_text(alignment.get("llm_text"))
    status = str(alignment.get("status") or "")
    box = bbox(unit)
    width = bbox_width(box)
    height = bbox_height(box)
    aspect = width / max(height, 1)

    reason = None
    expected_text = None
    if final_text and len(final_text) > 1:
        reason = "already_multi_char_label"
        expected_text = final_text
    elif "needs_literal" in source:
        reason = "needs_literal_reading"
        expected_text = llm_text if llm_text and 1 < len(llm_text) <= args.max_children else None
    elif status == "llm_suggests_connected_reading":
        reason = "llm_suggests_connected_reading"
        expected_text = llm_text if llm_text and 1 < len(llm_text) <= args.max_children else None
    else:
        return None

    if reason != "already_multi_char_label":
        if not args.include_latin_lines and contains_latin(row_text):
            return None
        if not args.include_empty_llm_rows and not row_text.strip():
            return None
        if not expected_text:
            return None
        expected_count = len(coptic_bases(expected_text))
        if expected_count > 1 and width < expected_count * args.min_child_width:
            return None

    if width < args.min_width and aspect < args.min_aspect and not expected_text:
        return None

    return {
        "page": str(unit["page"]),
        "line_index": int(unit["line_index"]),
        "blob_id": int(unit["blob_id"]),
        "cluster": str(unit.get("cluster")),
        "warped_bbox": box,
        "width": width,
        "height": height,
        "aspect": aspect,
        "reason": reason,
        "expected_text": expected_text,
        "llm_text": row_text,
        "llm_unit_text": str(alignment.get("llm_text") or ""),
        "final_label_source": source,
    }


def collect_targets(witness_path: Path, args: argparse.Namespace) -> dict[tuple[str, int, int], dict[str, Any]]:
    targets: dict[tuple[str, int, int], dict[str, Any]] = {}
    with witness_path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            row = json.loads(raw)
            row_text = str(row.get("llm_text") or "")
            for unit in row.get("units", []):
                item = unit_target(unit, row_text, args)
                if not item:
                    continue
                key = (item["page"], item["line_index"], item["blob_id"])
                targets.setdefault(key, item)
    return targets


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * fraction)))
    return float(ordered[index])


def collect_auto_wide_cluster_targets(
    clusters_dir: Path,
    witness_path: Path,
    args: argparse.Namespace,
    width_priors: dict[str, float],
    median_single_width: float,
) -> tuple[dict[tuple[str, int, int], dict[str, Any]], list[dict[str, Any]]]:
    if args.no_auto_wide_cluster_targets:
        return {}, []

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    assignment_path = clusters_dir / "_assignments.json"
    cluster_to_label = load_single_cluster_labels(clusters_dir)
    for cluster, label in infer_single_cluster_labels_from_witness(witness_path).items():
        cluster_to_label.setdefault(cluster, label)
    if not assignment_path.exists() or not cluster_to_label:
        return {}, []
    for assignment in load_json(assignment_path):
        cluster = f"{int(assignment['cluster']):03d}"
        label = cluster_to_label.get(cluster)
        if not label:
            continue
        box = [int(value) for value in assignment["warped_bbox"]]
        width = bbox_width(box)
        height = bbox_height(box)
        if width <= 0 or height <= 0:
            continue
        aspect = width / max(height, 1)
        item = {
            "page": str(assignment["page"]),
            "line_index": int(assignment["line_index"]),
            "blob_id": int(assignment["blob_id"]),
            "cluster": cluster,
            "warped_bbox": box,
            "width": width,
            "height": height,
            "aspect": aspect,
            "reason": "auto_wide_single_cluster",
            "expected_text": None,
            "llm_text": "",
            "llm_unit_text": "",
            "final_label_source": "auto_wide_cluster_assignment",
            "final_single_base": label,
        }
        grouped[(cluster, label)].append(item)

    targets: dict[tuple[str, int, int], dict[str, Any]] = {}
    selected_groups: list[dict[str, Any]] = []
    for (cluster, label), items in sorted(grouped.items()):
        if len(items) < args.auto_wide_min_cluster_size:
            continue
        prior_width = float(width_priors.get(label, median_single_width))
        widths = [float(item["width"]) for item in items]
        heights = [float(item["height"]) for item in items]
        aspects = [float(item["aspect"]) for item in items]
        median_width = float(np.median(widths))
        tenth_width = percentile(widths, 0.10)
        median_height = float(np.median(heights))
        median_aspect = float(np.median(aspects))
        width_threshold = max(float(args.auto_wide_min_width), prior_width * float(args.auto_wide_factor))
        tenth_threshold = max(float(args.auto_wide_min_width) * 0.8, prior_width * float(args.auto_wide_factor) * 0.85)
        if median_width < width_threshold:
            continue
        if tenth_width < tenth_threshold:
            continue
        if median_aspect < args.auto_wide_min_aspect:
            continue
        if args.auto_wide_max_median_height and median_height > args.auto_wide_max_median_height:
            continue
        expected_child_count = max(2, min(args.max_children, int(math.floor(median_width / max(prior_width, 1.0) + 0.5))))
        if expected_child_count < 2:
            continue
        group_record = {
            "cluster": cluster,
            "final_single_base": label,
            "count": len(items),
            "expected_child_count": expected_child_count,
            "prior_width": round(prior_width, 3),
            "median_width": round(median_width, 3),
            "tenth_width": round(tenth_width, 3),
            "median_height": round(median_height, 3),
            "median_aspect": round(median_aspect, 4),
            "reason": "auto_wide_single_cluster",
        }
        selected_groups.append(group_record)
        per_item_min_width = max(float(args.auto_wide_min_width) * 0.75, prior_width * 1.30)
        for item in items:
            if float(item["width"]) < per_item_min_width:
                continue
            target = dict(item)
            target["expected_child_count"] = expected_child_count
            target["auto_wide_cluster"] = group_record
            key = (target["page"], target["line_index"], target["blob_id"])
            targets[key] = target
    return targets, selected_groups


def collect_force_targets(path: Path | None) -> dict[tuple[str, int, int], dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    data = load_json(path)
    rows = data if isinstance(data, list) else data.get("targets", [])
    targets: dict[tuple[str, int, int], dict[str, Any]] = {}
    for row in rows:
        page = f"{int(row['page']):03d}"
        line_index = int(row["line_index"])
        blob_id = int(row["blob_id"])
        expected_text = normalized_text(row.get("expected_text"))
        expected_child_count = row.get("expected_child_count")
        if expected_text:
            expected_child_count = len(coptic_bases(expected_text))
        target = {
            "page": page,
            "line_index": line_index,
            "blob_id": blob_id,
            "cluster": str(row.get("cluster") or ""),
            "warped_bbox": row.get("warped_bbox") or [0, 0, 0, 0],
            "width": int(row.get("width") or 0),
            "height": int(row.get("height") or 0),
            "aspect": float(row.get("aspect") or 0.0),
            "reason": str(row.get("reason") or "manual_force_connected_split"),
            "expected_text": expected_text,
            "expected_child_count": expected_child_count,
            "llm_text": "",
            "llm_unit_text": "",
            "final_label_source": "manual_force_connected_split",
            "force_source": relative(path),
            "evidence": row.get("evidence"),
        }
        targets[(page, line_index, blob_id)] = target
    return targets


def sauvola(gray: np.ndarray, w: int, k: float, r: float) -> np.ndarray:
    gray32 = gray.astype(np.float32)
    ksize = 2 * w + 1
    mean = cv2.boxFilter(gray32, ddepth=cv2.CV_32F, ksize=(ksize, ksize), normalize=True, borderType=cv2.BORDER_REFLECT)
    sqmean = cv2.boxFilter(gray32 * gray32, ddepth=cv2.CV_32F, ksize=(ksize, ksize), normalize=True, borderType=cv2.BORDER_REFLECT)
    std = np.sqrt(np.maximum(sqmean - mean * mean, 0.0))
    threshold = mean * (1.0 + k * (std / r - 1.0))
    return (gray32 < threshold).astype(np.uint8)


def warp_quad_to_rect(img: np.ndarray, quad: list[list[float]], h_target: int) -> tuple[np.ndarray, np.ndarray, int]:
    quad_arr = np.asarray(quad, dtype=np.float32)
    tl, tr, br, bl = quad_arr
    width = int(round(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl))))
    width = max(width, 1)
    dst = np.array([[0, 0], [width - 1, 0], [width - 1, h_target - 1], [0, h_target - 1]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(quad_arr, dst)
    inverse = cv2.getPerspectiveTransform(dst, quad_arr)
    warped = cv2.warpPerspective(img, matrix, (width, h_target), flags=cv2.INTER_LINEAR, borderValue=255)
    return warped, inverse, width


def estimate_child_count(item: dict[str, Any], median_single_width: float, max_children: int) -> int:
    forced_count = item.get("expected_child_count")
    if forced_count:
        return max(2, min(max_children, int(forced_count)))
    expected = item.get("expected_text")
    if expected:
        return max(2, min(max_children, len(coptic_bases(expected))))
    width = float(item["width"])
    if median_single_width <= 0:
        median_single_width = 14.0
    estimated = int(round(width / median_single_width))
    return max(2, min(max_children, estimated))


def load_width_priors(clusters_dir: Path) -> tuple[dict[str, float], float]:
    label_path = clusters_dir / "_char_assignments_projected.json"
    assignment_path = clusters_dir / "_assignments.json"
    if not label_path.exists() or not assignment_path.exists():
        return {}, 14.0
    label_data = load_json(label_path)
    assignments_map = label_data.get("assignments", label_data)
    cluster_to_label: dict[str, str] = {}
    for label, clusters in assignments_map.items():
        bases = coptic_bases(label)
        if len(bases) != 1:
            continue
        for cluster in clusters:
            cluster_to_label[f"{int(cluster):03d}"] = bases[0]
    widths: dict[str, list[int]] = defaultdict(list)
    all_widths: list[int] = []
    for item in load_json(assignment_path):
        label = cluster_to_label.get(f"{int(item['cluster']):03d}")
        if not label:
            continue
        width = bbox_width([int(value) for value in item["warped_bbox"]])
        if width <= 0:
            continue
        widths[label].append(width)
        all_widths.append(width)
    priors = {label: float(np.median(values)) for label, values in widths.items() if values}
    global_median = float(np.median(all_widths)) if all_widths else 14.0
    return priors, global_median


def load_single_cluster_labels(clusters_dir: Path) -> dict[str, str]:
    label_path = clusters_dir / "_char_assignments_projected.json"
    if not label_path.exists():
        return {}
    label_data = load_json(label_path)
    assignments_map = label_data.get("assignments", label_data)
    cluster_to_label: dict[str, str] = {}
    for label, clusters in assignments_map.items():
        bases = coptic_bases(label)
        if len(bases) != 1:
            continue
        for cluster in clusters:
            cluster_to_label[f"{int(cluster):03d}"] = bases[0]
    return cluster_to_label


def infer_single_cluster_labels_from_witness(witness_path: Path) -> dict[str, str]:
    votes: dict[str, Counter[str]] = defaultdict(Counter)
    if not witness_path.exists():
        return {}
    with witness_path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            row = json.loads(raw)
            for unit in row.get("units", []):
                source = str(unit.get("final_label_source") or "")
                if source.startswith("editorial_marker"):
                    continue
                bases = coptic_bases(unit.get("final_label"))
                if len(bases) != 1:
                    continue
                cluster = unit.get("cluster")
                if cluster is None:
                    continue
                votes[f"{int(cluster):03d}"][bases[0]] += 1
    inferred: dict[str, str] = {}
    for cluster, label_votes in votes.items():
        total = sum(label_votes.values())
        if total < 10:
            continue
        label, count = label_votes.most_common(1)[0]
        if count / total >= 0.80:
            inferred[cluster] = label
    return inferred


def moving_average(values: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0:
        return values.astype(np.float32)
    kernel = np.ones(radius * 2 + 1, dtype=np.float32) / float(radius * 2 + 1)
    return np.convolve(values.astype(np.float32), kernel, mode="same")


def ideal_boundaries(width: int, expected_bases: list[str], width_priors: dict[str, float], median_single_width: float) -> list[float] | None:
    if len(expected_bases) < 2:
        return None
    weights = [max(3.0, float(width_priors.get(base, median_single_width))) for base in expected_bases]
    total = sum(weights)
    if total <= 0:
        return None
    positions = []
    running = 0.0
    for weight in weights[:-1]:
        running += weight
        positions.append(width * running / total)
    return positions


def _column_ink_counts(crop: np.ndarray) -> np.ndarray:
    """Per-column count of ink pixels (binarized crop expected, but tolerates grayscale)."""
    if crop.dtype == bool:
        return crop.sum(axis=0).astype(np.int32)
    # Sauvola output is uint8 with ink as nonzero. Count nonzero pixels per column
    # rather than summing intensities so the gap test is morphological, not weighted.
    return (crop > 0).sum(axis=0).astype(np.int32)


def _line_typical_widths(line: dict[str, Any]) -> tuple[float, float]:
    """Per-line letter-width statistics drawn from the unsplit base blobs already
    present on the line.

    Returns (typical_w, narrow_w). typical_w is the median width of base blobs
    in the [6, 24] px range (filters out specks and obvious multi-letter
    blobs). narrow_w is the 30th percentile (clamped to >= 6) and approximates
    the natural width of narrow letters like ⲓ / ⲱ / ⲋ on this line.

    Falls back to (12.0, 8.0) when the line has no usable base blobs (e.g. a
    very short line). Those defaults trigger as conservative behavior.
    """
    widths: list[int] = []
    for blob in line.get("blobs", []):
        if blob.get("kind") != "base":
            continue
        box = blob.get("warped_bbox")
        if not box or len(box) < 4:
            continue
        width = int(box[2]) - int(box[0]) + 1
        if 6 <= width <= 24:
            widths.append(width)
    if not widths:
        return 12.0, 8.0
    arr = np.asarray(widths, dtype=np.float32)
    typical_w = float(np.median(arr))
    narrow_w = float(max(6.0, np.percentile(arr, 30)))
    return typical_w, narrow_w


def find_morphological_cuts(
    crop: np.ndarray,
    max_cuts_hard: int,
    typical_w: float,
    narrow_w: float,
    tw_factor: float = 1.30,
    single_letter_factor: float = 1.40,
    gap_ratio: float = 0.30,
    min_child_factor: float = 0.55,
    position_prior: float = 0.50,
    smooth_radius: int = 1,
    expected_count: int | None = None,
) -> tuple[list[int], str, float]:
    """Geometry-aware morphological cut detection with positional prior.

    Three principles:

    * **Geometry decides the cut count by default.** ``target_children =
      round(parent_width / (typical_w * tw_factor))``. Parents narrower than
      ``typical_w * single_letter_factor`` are never split — UNLESS
      ``expected_count`` is provided.
    * **Witness, when present, is a hard count constraint.** If
      ``expected_count >= 2`` is supplied (from the LLM transcription /
      witness), it overrides the geometric estimate AND bypasses the
      single-letter-geometry refusal. The splitter then targets exactly
      ``expected_count`` children — never more, never fewer if morphology
      can support them. This prevents both over-split (deep internal gaps
      inside ⲙ / ⲱ / ⲇ being treated as inter-letter boundaries) and the
      false-negative case where a tightly-touching pair has the geometric
      width of a single wide letter.
    * **Morphology decides where cuts can land.** Candidates come from the
      column-ink projection: deep-ink-gap regions (priority 0) are preferred
      over smoothed-profile local minima (priority 1).
    * **Position prior breaks ties between morphological candidates.** Within
      a priority tier, candidates are scored by
      ``depth_norm + position_prior * dist_to_nearest_ideal_norm``,
      where ideal positions are the balanced ``width * k / target`` for
      k=1..target-1.

    Each accepted cut must leave both adjacent children at least
    ``narrow_w * min_child_factor`` columns wide.
    """
    height, width = crop.shape[:2]
    if width < 4 or max_cuts_hard <= 0 or typical_w <= 0 or narrow_w <= 0:
        return [], "too_narrow", 0.0
    has_witness = expected_count is not None and expected_count >= 2
    if not has_witness and width < typical_w * single_letter_factor:
        return [], "single_letter_geometry", 0.0

    if has_witness:
        target_children = int(expected_count)
    else:
        target_children = max(2, int(round(width / max(typical_w * tw_factor, 1.0))))
    cuts_to_find = min(target_children - 1, max_cuts_hard)
    if cuts_to_find <= 0:
        return [], "no_cuts_needed", 0.0

    min_child = max(3, int(round(narrow_w * min_child_factor)))

    cols = _column_ink_counts(crop)
    if cols.max() <= 0:
        return [], "empty_crop", 0.0
    ink_cols = cols[cols > 0]
    typical_ink = float(np.percentile(ink_cols, 70)) if ink_cols.size else 1.0
    low_threshold = max(1, int(round(typical_ink * gap_ratio)))

    # Ideal cut positions for a balanced target-way split. These define the
    # "hot zones" the position prior pulls candidates toward.
    ideal_positions = [width * k / target_children for k in range(1, target_children)]

    # ---- Stage 1: contiguous low-ink regions (the strong signal). ----
    candidates: list[dict[str, Any]] = []
    in_low = False
    start = 0
    for x in range(width):
        if cols[x] <= low_threshold:
            if not in_low:
                start = x
                in_low = True
        else:
            if in_low:
                end = x - 1
                in_low = False
                # interior only (not touching either edge), and at least 2 cols wide
                if start > 0 and end < width - 1 and (end - start + 1) >= 2:
                    region_cols = cols[start:end + 1]
                    candidates.append({
                        "center": (start + end) // 2,
                        "depth": float(region_cols.mean()),
                        "region_width": end - start + 1,
                        "priority": 0,
                    })

    # ---- Stage 2: smoothed local minima (fallback for touching letters). ----
    if len(candidates) < cuts_to_find:
        if smooth_radius > 0:
            kernel = np.ones(smooth_radius * 2 + 1, dtype=np.float32) / float(smooth_radius * 2 + 1)
            smooth = np.convolve(cols.astype(np.float32), kernel, mode="same")
        else:
            smooth = cols.astype(np.float32)
        for i in range(1, width - 1):
            if smooth[i] <= smooth[i - 1] and smooth[i] <= smooth[i + 1] and (
                smooth[i] < smooth[i - 1] or smooth[i] < smooth[i + 1]
            ):
                if any(abs(c["center"] - i) <= 1 for c in candidates):
                    continue
                candidates.append({
                    "center": i,
                    "depth": float(smooth[i]),
                    "region_width": 1,
                    "priority": 1,
                })

    if not candidates:
        return [], "no_candidates", 0.0

    # Combined morphology + position score (lower is better). depth_norm puts
    # all gaps near 0; the position term pulls scoring toward the balanced
    # ideal split positions. Priority 0 still beats priority 1 in lex order.
    for cand in candidates:
        depth_norm = cand["depth"] / max(typical_ink, 1.0)
        dist = min(abs(cand["center"] - ideal) for ideal in ideal_positions)
        dist_norm = dist / max(typical_w, 1.0)
        cand["score"] = depth_norm + position_prior * dist_norm
    candidates.sort(key=lambda c: (c["priority"], c["score"]))

    accepted: list[dict[str, Any]] = []
    for cand in candidates:
        center = cand["center"]
        prev_pos = max(
            [prev["center"] for prev in accepted if prev["center"] < center] + [-1]
        )
        next_pos = min(
            [prev["center"] for prev in accepted if prev["center"] > center] + [width]
        )
        left_w = center - (prev_pos + 1) if prev_pos >= 0 else center
        right_w = (next_pos - 1) - center if next_pos < width else (width - 1 - center)
        if left_w < min_child or right_w < min_child:
            continue
        accepted.append(cand)
        if len(accepted) >= cuts_to_find:
            break

    if not accepted:
        return [], "no_valid_candidate_after_min_child", 0.0

    accepted.sort(key=lambda c: c["center"])
    cuts = [int(c["center"]) for c in accepted]
    deep_count = sum(1 for c in accepted if c["priority"] == 0)
    if deep_count == len(accepted):
        confidence = "deep_gaps"
    elif deep_count == 0:
        confidence = "shallow_minima"
    else:
        confidence = "mixed_signal"
    avg_depth = float(np.mean([c["depth"] for c in accepted]))
    ratio = float(avg_depth / max(typical_ink, 1.0))
    return cuts, confidence, ratio


def child_boxes(
    parent_box: list[int],
    ink: np.ndarray,
    max_cuts: int,
    typical_w: float,
    narrow_w: float,
    tw_factor: float,
    single_letter_factor: float,
    gap_ratio: float,
    min_child_factor: float,
    position_prior: float,
    expected_count: int | None = None,
) -> tuple[list[dict[str, Any]], list[int], str, float]:
    """Cut the parent strip at geometry-aware morphology-detected positions.
    Returns however many children the bitmap supports — 0 if no real cut.

    When ``expected_count >= 2`` is supplied, it caps the cut count to
    ``expected_count - 1`` and bypasses the single-letter-geometry refusal
    so tightly-touching pairs/triples still get split."""
    x0, y0, x1, y1 = parent_box
    crop = ink[y0:y1 + 1, x0:x1 + 1]
    if crop.size == 0:
        return [], [], "empty_parent_crop", 0.0
    cuts, confidence, ratio = find_morphological_cuts(
        crop,
        max_cuts_hard=max_cuts,
        typical_w=typical_w,
        narrow_w=narrow_w,
        tw_factor=tw_factor,
        single_letter_factor=single_letter_factor,
        gap_ratio=gap_ratio,
        min_child_factor=min_child_factor,
        position_prior=position_prior,
        expected_count=expected_count,
    )
    if not cuts:
        return [], [], confidence, ratio
    bounds = [0] + [cut + 1 for cut in cuts] + [crop.shape[1]]
    child_count = len(cuts) + 1
    children: list[dict[str, Any]] = []
    for index in range(child_count):
        start = bounds[index]
        end = bounds[index + 1]
        segment = crop[:, start:end]
        ys, xs = np.nonzero(segment > 0)
        if len(xs) == 0:
            continue
        left = int(x0 + start + xs.min())
        right = int(x0 + start + xs.max())
        top = int(y0 + ys.min())
        bottom = int(y0 + ys.max())
        children.append({
            "child_index": index,
            "warped_bbox": [left, top, right, bottom],
            "area": int(segment.sum()),
        })
    return children, [int(x0 + cut) for cut in cuts], confidence, ratio


def img_quad_for_box(box: list[int], inverse: np.ndarray) -> list[list[float]]:
    x0, y0, x1, y1 = box
    corners = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=np.float32).reshape(-1, 1, 2)
    return cv2.perspectiveTransform(corners, inverse).reshape(-1, 2).tolist()


# --- Iota-with-fused-below-dot splitter -------------------------------------
# When the combining below-dot inks into the bottom of an iota stem, 8-connected
# component analysis emits a single tall blob. The proper fix is segmentation:
# detect the empty/near-empty horizontal seam between stem and dot in the ink
# mask and emit two blobs (stem as base, dot as `other`), so the existing mark
# attachment pipeline picks up the dot like any other free-standing diacritic.

IOTA_BELOWDOT_MAX_WIDTH = 9          # iota stem stays narrow
IOTA_BELOWDOT_MIN_TOTAL_HEIGHT = 22  # full blob: stem + (gap) + dot
IOTA_BELOWDOT_MIN_DESCENT = 4        # bottom must drop at least this far below baseline
IOTA_BELOWDOT_MAX_SEAM_INK_FRAC = 0.20  # seam row ink fraction relative to blob width
IOTA_BELOWDOT_MAX_DOT_HEIGHT = 9     # below-dot piece must be small (a dot)
IOTA_BELOWDOT_MIN_STEM_HEIGHT = 14   # stem alone must remain plausibly iota-shaped


def _detect_iota_belowdot_split(
    blob: dict[str, Any], line_ink: np.ndarray, baseline_y: int
) -> tuple[list[int], list[int]] | None:
    """Return (stem_bbox, dot_bbox) if the blob is an iota with a fused below-dot.

    Strategy: pixel-level. Crop the sauvola mask to the blob bbox, scan rows
    starting at the baseline, and look for a row whose ink count is at most a
    small fraction of blob width AND that separates a large upper region (the
    stem) from a small lower region (the dot). This mirrors how the eye reads
    the page: the dot is a distinct shape with empty space (or a 1-pixel
    bridge) between it and the stem.
    """
    bbox = blob.get("warped_bbox") or []
    if len(bbox) != 4:
        return None
    x0, y0, x1, y1 = (int(v) for v in bbox)
    width = x1 - x0 + 1
    height = y1 - y0 + 1
    if width > IOTA_BELOWDOT_MAX_WIDTH:
        return None
    if height < IOTA_BELOWDOT_MIN_TOTAL_HEIGHT:
        return None
    if y1 - baseline_y < IOTA_BELOWDOT_MIN_DESCENT:
        return None
    if y0 > baseline_y:
        # Whole blob lives below baseline; that's just a dot, not a fused iota.
        return None

    h_img, w_img = line_ink.shape
    cx0 = max(0, x0)
    cy0 = max(0, y0)
    cx1 = min(w_img, x1 + 1)
    cy1 = min(h_img, y1 + 1)
    if cx1 <= cx0 or cy1 <= cy0:
        return None
    crop = line_ink[cy0:cy1, cx0:cx1]
    if crop.size == 0:
        return None
    row_ink = (crop > 0).sum(axis=1).astype(np.int32)
    if row_ink.size == 0:
        return None
    crop_w = cx1 - cx0
    seam_max_ink = max(1, int(round(IOTA_BELOWDOT_MAX_SEAM_INK_FRAC * crop_w)))

    # Search rows from a couple of pixels below baseline down to a few pixels
    # above the bottom; the seam must leave room for both stem and dot.
    seam_search_top = max(1, baseline_y - cy0 - 1)
    seam_search_bot = (cy1 - cy0) - 2
    if seam_search_bot <= seam_search_top:
        return None

    # Pick the seam row with the lowest ink count in the search window; ties
    # broken by being closer to the baseline (smaller row index).
    seam_local = None
    seam_ink = None
    for r in range(seam_search_top, seam_search_bot + 1):
        ink = int(row_ink[r])
        if ink > seam_max_ink:
            continue
        if seam_ink is None or ink < seam_ink:
            seam_ink = ink
            seam_local = r
    if seam_local is None:
        return None

    seam_y = cy0 + seam_local
    stem_bottom = seam_y - 1
    dot_top = seam_y + 1
    if stem_bottom <= y0 or dot_top >= y1:
        return None

    # Validate stem shape (covers baseline, plausible iota height) and dot
    # shape (small, tucked under stem).
    stem_height = stem_bottom - y0 + 1
    dot_height = y1 - dot_top + 1
    if stem_height < IOTA_BELOWDOT_MIN_STEM_HEIGHT:
        return None
    if dot_height < 1 or dot_height > IOTA_BELOWDOT_MAX_DOT_HEIGHT:
        return None
    if stem_bottom < baseline_y - 2:
        # Stem must still reach the baseline to be an iota.
        return None

    # Tighten stem and dot bboxes horizontally to actual ink columns inside
    # their row ranges so the resulting blobs aren't padded with dead space.
    def tight_box(top_local: int, bot_local: int) -> list[int] | None:
        sub = crop[top_local : bot_local + 1]
        if sub.size == 0:
            return None
        col_ink = (sub > 0).sum(axis=0)
        if not col_ink.any():
            return None
        cols = np.flatnonzero(col_ink)
        left = cx0 + int(cols[0])
        right = cx0 + int(cols[-1])
        rows_local = np.flatnonzero((sub > 0).any(axis=1))
        if rows_local.size == 0:
            return None
        top = cy0 + top_local + int(rows_local[0])
        bot = cy0 + top_local + int(rows_local[-1])
        return [left, top, right, bot]

    stem_box = tight_box(0, stem_bottom - cy0)
    dot_box = tight_box(dot_top - cy0, (cy1 - cy0) - 1)
    if stem_box is None or dot_box is None:
        return None
    return stem_box, dot_box


def _split_iota_belowdots_in_line(
    line: dict[str, Any], line_ink: np.ndarray, inverse: np.ndarray, baseline_y: int
) -> int:
    """In-place: replace each iota-with-fused-below-dot base blob with a
    `base` stem blob and an `other` below-dot blob. Returns count of splits."""
    if line_ink is None or inverse is None:
        return 0
    blobs = line.get("blobs") or []
    if not blobs:
        return 0
    next_id = max(int(b.get("id", 0)) for b in blobs) + 1
    new_blobs: list[dict[str, Any]] = []
    splits = 0
    for blob in blobs:
        if blob.get("kind") != "base":
            new_blobs.append(blob)
            continue
        result = _detect_iota_belowdot_split(blob, line_ink, baseline_y)
        if result is None:
            new_blobs.append(blob)
            continue
        stem_box, dot_box = result
        parent_id = int(blob.get("id"))
        stem_blob = dict(blob)
        stem_blob.update({
            "warped_bbox": stem_box,
            "area": int(((line_ink[stem_box[1]:stem_box[3] + 1, stem_box[0]:stem_box[2] + 1]) > 0).sum()),
            "img_quad": img_quad_for_box(stem_box, inverse),
            "split_method": "iota_belowdot_segmentation",
            "split_role": "stem",
            "split_child_index": 0,
            "split_child_count": 2,
            "parent_blob_id": parent_id,
            "parent_warped_bbox": blob.get("warped_bbox"),
        })
        dot_blob = {
            "id": next_id,
            "kind": "other",
            "warped_bbox": dot_box,
            "area": int(((line_ink[dot_box[1]:dot_box[3] + 1, dot_box[0]:dot_box[2] + 1]) > 0).sum()),
            "img_quad": img_quad_for_box(dot_box, inverse),
            "split_method": "iota_belowdot_segmentation",
            "split_role": "below_dot",
            "split_child_index": 1,
            "split_child_count": 2,
            "parent_blob_id": parent_id,
            "parent_warped_bbox": blob.get("warped_bbox"),
        }
        next_id += 1
        new_blobs.append(stem_blob)
        new_blobs.append(dot_blob)
        splits += 1
    if splits:
        line["blobs"] = sorted(
            new_blobs,
            key=lambda row: (int(row["warped_bbox"][0]), int(row["warped_bbox"][1]), int(row["id"])),
        )
    return splits


def split_page(
    page: str,
    targets: dict[tuple[str, int, int], dict[str, Any]],
    out_dir: Path,
    width_priors: dict[str, float],
    median_single_width: float,
    args: argparse.Namespace,
) -> dict[str, Any]:
    source_path = PAGES_DIR / f"keph_p{page}_lines_base_split.json"
    body_path = PAGES_DIR / f"keph_p{page}_body.jpg"
    clean_path = PAGES_DIR / f"kraken_p{page}_body_clean.json"
    out_path = out_dir / source_path.name
    if not source_path.exists():
        return {"page": page, "status": "missing_source"}
    split = load_json(source_path)
    if not body_path.exists() or not clean_path.exists():
        shutil.copy2(source_path, out_path)
        return {"page": page, "status": "copied_missing_body_or_clean"}

    img = cv2.imread(str(body_path), cv2.IMREAD_GRAYSCALE)
    clean = load_json(clean_path)
    quad_by_idx = {int(line["index"]): line["quad"] for line in clean.get("lines", [])}
    line_cache: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    page_targets = {key: value for key, value in targets.items() if key[0] == page}
    split_count = 0
    child_count_total = 0
    iota_belowdot_split_count = 0
    failures: list[dict[str, Any]] = []

    for line in split.get("lines", []):
        line_index = int(line["line_index"])
        if line_index not in line_cache:
            quad = quad_by_idx.get(line_index)
            if quad is not None and img is not None:
                warped, inverse, _width = warp_quad_to_rect(img, quad, WARP_HEIGHT)
                line_cache[line_index] = (sauvola(warped, SAUVOLA_W, SAUVOLA_K, SAUVOLA_R), inverse)
        line_ink, inverse = line_cache.get(line_index, (None, None))
        # Pre-pass: split iotas where a combining below-dot has fused with the
        # stem into a single connected component. Done at the pixel level so
        # downstream cluster/witness stages see two clean blobs (base + other).
        baseline_y = int(line.get("baseline_y_warped", split.get("baseline_y_warped", 39)))
        iota_belowdot_split_count += _split_iota_belowdots_in_line(
            line, line_ink, inverse, baseline_y
        )
        # Per-line letter geometry, computed before any splitting so wide-letter
        # parents already on the line don't bias the median upward.
        typical_w, narrow_w = _line_typical_widths(line)
        next_id = max([int(blob["id"]) for blob in line.get("blobs", [])] or [0]) + 1
        new_blobs: list[dict[str, Any]] = []
        for blob in line.get("blobs", []):
            key = (page, line_index, int(blob["id"]))
            target = page_targets.get(key)
            if not target or blob.get("kind") != "base" or line_ink is None or inverse is None:
                new_blobs.append(blob)
                continue
            target = dict(target)
            target["warped_bbox"] = blob["warped_bbox"]
            target["width"] = bbox_width(blob["warped_bbox"])
            target["height"] = bbox_height(blob["warped_bbox"])
            target["aspect"] = target["width"] / max(target["height"], 1)
            expected_bases = coptic_bases(target.get("expected_text") or "")
            # Geometry-aware morphology splitter:
            # * cut count is bounded by the per-line letter geometry
            #   (parent_width / typical_w / tw_factor), capped at max_children
            # * when the witness gives us an expected base count >= 2, that
            #   count overrides geometry as a hard cap (prevents over-split
            #   on wide letters with internal gaps like ⲇⲇ → ⲉⲟⲇ) AND
            #   bypasses the single-letter-geometry refusal so tightly-
            #   touching pairs still get split.
            # * cut locations come from the column-ink projection (deep gaps
            #   first, smoothed minima as fallback)
            # * each cut must leave both adjacent children >= narrow_w *
            #   min_child_factor wide, which prevents splitting wide single
            #   letters along their natural internal gaps (ⲙ / ⲱ / ϣ).
            max_cuts = max(0, args.max_children - 1)
            expected_count = len(expected_bases) if len(expected_bases) >= 2 else None
            children, cuts, confidence, valley_ratio = child_boxes(
                blob["warped_bbox"],
                line_ink,
                max_cuts=max_cuts,
                typical_w=typical_w,
                narrow_w=narrow_w,
                tw_factor=args.tw_factor,
                single_letter_factor=args.single_letter_factor,
                gap_ratio=args.gap_ratio,
                min_child_factor=args.min_child_factor,
                position_prior=args.position_prior,
                expected_count=expected_count,
            )
            if not children:
                # Morphology found no real interior gap. Leave the parent as is;
                # this is the correct outcome, not a failure.
                new_blobs.append(blob)
                continue
            expected_text = target.get("expected_text") or ""
            produced_count = len(children)
            witness_aligns = bool(expected_bases) and len(expected_bases) == produced_count
            for child in children:
                child_index = int(child["child_index"])
                child_blob = {
                    "id": next_id,
                    "kind": "base",
                    "warped_bbox": child["warped_bbox"],
                    "area": child["area"],
                    "img_quad": img_quad_for_box(child["warped_bbox"], inverse),
                    "source_blob_id": int(blob["id"]),
                    "parent_blob_id": int(blob["id"]),
                    "split_child_index": child_index,
                    "split_child_count": produced_count,
                    "split_expected_text": expected_text or None,
                    "split_expected_base": expected_bases[child_index] if witness_aligns else None,
                    "split_method": "morphological_gap",
                    "split_reason": target.get("reason"),
                    "split_confidence": confidence,
                    "split_valley_ratio": round(float(valley_ratio), 4),
                    "parent_warped_bbox": blob["warped_bbox"],
                    "cut_positions": cuts,
                }
                new_blobs.append(child_blob)
                next_id += 1
                child_count_total += 1
            split_count += 1
        line["blobs"] = sorted(new_blobs, key=lambda row: (int(row["warped_bbox"][0]), int(row["warped_bbox"][1]), int(row["id"])))

    split["source_split"] = relative(source_path)
    split["split_layer"] = {
        "name": "base_split_chars",
        "method": "morphological_gap",
        "targets_on_page": len(page_targets),
        "parents_split": split_count,
        "children_created": child_count_total,
    }
    write_json(out_path, split)
    return {
        "page": page,
        "status": "ok",
        "targets": len(page_targets),
        "parents_split": split_count,
        "children_created": child_count_total,
        "iota_belowdot_splits": iota_belowdot_split_count,
        "failures": failures[:50],
        "failure_count": len(failures),
    }


def run(args: argparse.Namespace) -> None:
    witness_path = resolve_repo_path(args.witness, DEFAULT_WITNESS)
    out_dir = resolve_repo_path(args.out_dir, DEFAULT_OUT_DIR)
    clusters_dir = resolve_repo_path(args.clusters_dir, DEFAULT_CLUSTERS_DIR)
    force_targets_path = resolve_repo_path(args.force_targets, Path("")) if args.force_targets else None
    out_dir.mkdir(parents=True, exist_ok=True)
    width_priors, median_single_width = load_width_priors(clusters_dir)
    targets = collect_targets(witness_path, args)
    auto_wide_targets, auto_wide_groups = collect_auto_wide_cluster_targets(clusters_dir, witness_path, args, width_priors, median_single_width)
    for key, target in auto_wide_targets.items():
        targets.setdefault(key, target)
    force_targets = collect_force_targets(force_targets_path)
    targets.update(force_targets)
    pages = sorted({path.stem.removeprefix("keph_p").removesuffix("_lines_base_split") for path in PAGES_DIR.glob("keph_p*_lines_base_split.json")})
    results = []
    for page in tqdm(pages, desc="split pages", unit="page"):
        results.append(split_page(page, targets, out_dir, width_priors, median_single_width, args))

    reason_counts = Counter(target.get("reason") for target in targets.values())
    summary = {
        "description": "Derived split files where selected connected Coptic parent blobs are cut into child character blobs.",
        "source_witness": relative(witness_path),
        "force_targets": relative(force_targets_path) if force_targets_path else None,
        "source_pages_dir": relative(PAGES_DIR),
        "out_dir": relative(out_dir),
        "parameters": {
            "min_width": args.min_width,
            "min_aspect": args.min_aspect,
            "min_child_width": args.min_child_width,
            "clusters_dir": relative(clusters_dir),
            "median_single_width": median_single_width,
            "max_children": args.max_children,
            "include_latin_lines": args.include_latin_lines,
            "include_empty_llm_rows": args.include_empty_llm_rows,
        },
        "target_count": len(targets),
        "auto_wide_target_count": len(auto_wide_targets),
        "auto_wide_groups": auto_wide_groups,
        "force_target_count": len(force_targets),
        "target_reasons": dict(reason_counts),
        "width_priors": width_priors,
        "pages": results,
        "totals": {
            "parents_split": sum(int(row.get("parents_split", 0)) for row in results),
            "children_created": sum(int(row.get("children_created", 0)) for row in results),
            "failure_count": sum(int(row.get("failure_count", 0)) for row in results),
        },
    }
    write_json(out_dir / "_split_summary.json", summary)
    print(f"targets: {len(targets)}")
    print(f"auto wide targets: {len(auto_wide_targets)}")
    print(f"auto wide groups: {len(auto_wide_groups)}")
    print(f"force targets: {len(force_targets)}")
    print(f"target reasons: {dict(reason_counts)}")
    print(f"parents split: {summary['totals']['parents_split']}")
    print(f"children created: {summary['totals']['children_created']}")
    print(f"failure count: {summary['totals']['failure_count']}")
    print(f"out dir: {relative(out_dir)}")
    print(f"summary: {relative(out_dir / '_split_summary.json')}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--witness", default=None)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--clusters-dir", default=None)
    parser.add_argument("--force-targets", default=None)
    parser.add_argument("--min-width", type=int, default=12)
    parser.add_argument("--min-aspect", type=float, default=1.2)
    parser.add_argument("--min-child-width", type=int, default=6)
    parser.add_argument("--max-children", type=int, default=4)
    parser.add_argument(
        "--min-gap-width",
        type=int,
        default=5,
        help="Minimum width (in columns) of a low-ink region to count as an inter-letter gap. "
             "Narrower dips are treated as intra-letter structure (e.g. ⲙ's internal gap, ϣ's hook).",
    )
    parser.add_argument(
        "--gap-ratio",
        type=float,
        default=0.30,
        help="A column counts as 'low' when its ink density is at most typical * gap-ratio, "
             "where typical is the 70th percentile of inked columns in the parent.",
    )
    parser.add_argument(
        "--tw-factor",
        type=float,
        default=1.30,
        help="Geometric divisor: target_children = round(parent_width / (typical_w * tw_factor)). "
             "Larger values produce fewer children. Tuned to 1.30 by sweep against the witness corpus.",
    )
    parser.add_argument(
        "--single-letter-factor",
        type=float,
        default=1.40,
        help="Parents narrower than typical_w * single-letter-factor are never split (treated as one letter).",
    )
    parser.add_argument(
        "--min-child-factor",
        type=float,
        default=0.55,
        help="Each accepted cut must leave both adjacent children at least narrow_w * min-child-factor wide.",
    )
    parser.add_argument(
        "--position-prior",
        type=float,
        default=0.50,
        help="Weight on the geometric-balance term when ranking morphological cut candidates. "
             "Score = depth/typical_ink + position_prior * dist_to_ideal/typical_w. Higher values "
             "pull cuts toward the balanced split positions and away from incidental deep gaps "
             "inside wide letters (e.g. ⲙ's internal gap). 0 reproduces pure-morphology behavior.",
    )
    parser.add_argument("--no-auto-wide-cluster-targets", action="store_true")
    parser.add_argument("--auto-wide-factor", type=float, default=1.7)
    parser.add_argument("--auto-wide-min-width", type=int, default=24)
    parser.add_argument("--auto-wide-min-cluster-size", type=int, default=25)
    parser.add_argument("--auto-wide-min-aspect", type=float, default=1.45)
    parser.add_argument("--auto-wide-max-median-height", type=float, default=26.0)
    parser.add_argument("--include-latin-lines", action="store_true")
    parser.add_argument("--include-empty-llm-rows", action="store_true")
    return parser.parse_args()


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()