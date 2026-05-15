"""Split v2 Kephalaia page crops into line-number and Coptic body images.

This stage starts from ``output/projects/kephalaia_ocr_v2/pages_cropped``.
The page crops are already aligned, so the line-number column is detected first
in a stable left-side band. Its vertical extent becomes the shared y-range for
both derived artifacts:

* a line-number strip
* a Coptic text-body strip

Both output images have identical height. Review sheets are written alongside
metadata so the split can be inspected page by page.
"""

from __future__ import annotations

import argparse
import json
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from tqdm import tqdm


REPO = Path(__file__).resolve().parents[3]
PROJECT_OUT = REPO / "output" / "projects" / "kephalaia_ocr_v2"
DEFAULT_INPUT_DIR = PROJECT_OUT / "pages_cropped"
DEFAULT_OUTPUT_DIR = PROJECT_OUT / "line_body_split"

RULER_X0 = 35
RULER_X1 = 95
SAMPLE_PAGES = ["010", "057", "100", "127", "185", "196", "283", "288"]
PAGE_Y_POLICIES = {
    "017": {
        "y1_min": 1740,
        "reason": "include unnumbered wrapped continuation letters below line 35",
    },
    "113": {
        "y1_max": 1750,
        "reason": "exclude printed footer apparatus below line 37",
    },
    "114": {
        "y1_max": 1590,
        "reason": "exclude printed footer apparatus below line 33",
    },
}


@dataclass(frozen=True)
class OutputPaths:
    root: Path
    common: Path
    line_numbers: Path
    text_body: Path
    reviews: Path
    metadata: Path

    @classmethod
    def from_root(cls, root: Path) -> "OutputPaths":
        return cls(
            root=root,
            common=root / "common",
            line_numbers=root / "line_numbers",
            text_body=root / "text_body",
            reviews=root / "reviews",
            metadata=root / "metadata",
        )

    def mkdirs(self) -> None:
        for path in (self.root, self.common, self.line_numbers, self.text_body, self.reviews, self.metadata):
            path.mkdir(parents=True, exist_ok=True)


def rel(path: Path) -> str:
    return str(path.relative_to(REPO)).replace("\\", "/")


def normalize_page_id(page: str) -> str:
    return page.removeprefix("keph_p").removeprefix("p").removesuffix(".jpg")


def page_path(input_dir: Path, page_id: str) -> Path:
    return input_dir / f"keph_p{page_id}.jpg"


def filter_small_components(mask: np.ndarray, min_area: int) -> np.ndarray:
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    out = np.zeros(mask.shape, dtype=np.uint8)
    for label in range(1, n_labels):
        if int(stats[label, cv2.CC_STAT_AREA]) >= min_area:
            out[labels == label] = 255
    return out


def threshold_ink(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, mask = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    return filter_small_components(mask, min_area=4)


def adaptive_ink(gray: np.ndarray) -> np.ndarray:
    mask = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV,
        21,
        6,
    )
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), iterations=1)
    return filter_small_components(mask, min_area=4)


def collapse_positions(values: list[float], tolerance: float) -> list[float]:
    if not values:
        return []
    collapsed: list[list[float]] = [[float(values[0])]]
    for value in values[1:]:
        if abs(value - float(np.mean(collapsed[-1]))) <= tolerance:
            collapsed[-1].append(float(value))
        else:
            collapsed.append([float(value)])
    return [float(np.mean(group)) for group in collapsed]


def cadence_rows(rows: list[float], step: float, min_run_len: int) -> list[float]:
    if len(rows) < 2:
        return rows
    min_gap = max(20.0, step * 0.55)
    max_gap = min(76.0, step * 1.80)
    runs: list[list[float]] = []
    current = [rows[0]]
    for prev, cur in zip(rows, rows[1:]):
        gap = cur - prev
        if min_gap <= gap <= max_gap:
            current.append(cur)
        else:
            runs.append(current)
            current = [cur]
    runs.append(current)

    kept: list[float] = []
    for run in runs:
        if len(run) >= min_run_len:
            kept.extend(run)
    if kept:
        return kept

    runs.sort(key=lambda run: (len(run), run[-1] - run[0]), reverse=True)
    return runs[0]


def collect_digit_candidates(mask: np.ndarray, x_hi: int) -> list[dict[str, Any]]:
    n_labels, _labels, stats, centroids = cv2.connectedComponentsWithStats(mask[:, :x_hi], 8)
    candidates: list[dict[str, Any]] = []
    for label in range(1, n_labels):
        x, y, w, h, area = [int(value) for value in stats[label]]
        if not (2 <= w <= 32 and 5 <= h <= 36 and 8 <= area <= 360):
            continue
        cx, cy = centroids[label]
        if cy < 45:
            continue
        candidates.append(
            {
                "x": x,
                "y": y,
                "w": w,
                "h": h,
                "area": area,
                "cx": float(cx),
                "cy": float(cy),
            }
        )
    return candidates


def merge_candidates(primary: list[dict[str, Any]], secondary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = list(primary)
    for item in secondary:
        if any(abs(item["cx"] - old["cx"]) < 5 and abs(item["cy"] - old["cy"]) < 5 for old in merged):
            continue
        merged.append(item)
    return merged


def rows_from_ruler_band(candidates: list[dict[str, Any]], x0: int, x1: int) -> list[dict[str, Any]]:
    band = [item for item in candidates if x0 <= item["cx"] <= x1]
    centers = collapse_positions(sorted(item["cy"] for item in band), tolerance=14.0)
    rows: list[dict[str, Any]] = []
    for center in centers:
        items = [item for item in band if abs(item["cy"] - center) <= 14]
        if not items:
            continue
        rows.append(
            {
                "center": float(center),
                "x0": int(min(item["x"] for item in items)),
                "x1": int(max(item["x"] + item["w"] for item in items)),
                "y0": int(min(item["y"] for item in items)),
                "y1": int(max(item["y"] + item["h"] for item in items)),
                "area": int(sum(item["area"] for item in items)),
                "component_count": len(items),
            }
        )
    return rows


def filter_ruler_row_geometry(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove footer/note rows that sit in the ruler band but not the ruler column.

    Actual two-digit line numbers have a stable x-span once the page reaches
    line 10. Footer notes can put numerals or small words in the same left band,
    but their x-span is usually much narrower, much wider, or shifted relative
    to the true line-number column. Early one-digit rows are kept permissively.
    """
    if len(rows) < 12:
        return rows

    sorted_rows = sorted(rows, key=lambda row: row["center"])
    widths = [int(row["x1"] - row["x0"]) for row in sorted_rows]
    middle_rows = sorted_rows[min(8, len(sorted_rows) // 3):max(min(8, len(sorted_rows) // 3) + 1, len(sorted_rows) - 3)]
    stable = [row for row in middle_rows if 10 <= int(row["x1"] - row["x0"]) <= 36]
    if len(stable) < 6:
        stable = [row for row in sorted_rows if 10 <= int(row["x1"] - row["x0"]) <= 36]
    if len(stable) < 6:
        return rows

    typical_x0 = float(np.median([row["x0"] for row in stable]))
    typical_x1 = float(np.median([row["x1"] for row in stable]))
    typical_width = max(8.0, float(np.median([row["x1"] - row["x0"] for row in stable])))
    first_center = float(sorted_rows[0]["center"])
    plausible_gaps = [
        sorted_rows[i + 1]["center"] - sorted_rows[i]["center"]
        for i in range(len(sorted_rows) - 1)
        if 25 <= sorted_rows[i + 1]["center"] - sorted_rows[i]["center"] <= 65
    ]
    step = float(np.median(plausible_gaps)) if plausible_gaps else 41.0

    filtered: list[dict[str, Any]] = []
    for row, width in zip(sorted_rows, widths):
        center = float(row["center"])
        if center < first_center + step * 9.0:
            filtered.append(row)
            continue
        too_narrow = width <= typical_width * 0.65
        too_wide = width > typical_width * 1.85
        shifted = abs(float(row["x0"]) - typical_x0) >= 12 or abs(float(row["x1"]) - typical_x1) > 14
        tiny_artifact = int(row.get("area", 0)) < 18 or int(row.get("component_count", 0)) <= 0
        if too_narrow or too_wide or shifted or tiny_artifact:
            continue
        filtered.append(row)

    return filtered if len(filtered) >= 8 else rows


def choose_ruler_rows(candidates: list[dict[str, Any]], width: int) -> tuple[list[dict[str, Any]], list[int]]:
    fixed_rows = filter_ruler_row_geometry(rows_from_ruler_band(candidates, min(width - 1, RULER_X0), min(width, RULER_X1)))
    if len(fixed_rows) >= 8:
        return fixed_rows, [min(width - 1, RULER_X0), min(width, RULER_X1)]

    valid_bands: list[tuple[int, int, list[dict[str, Any]], int, float]] = []
    scan_limit = min(width, max(180, int(width * 0.26)))
    for x0 in range(35, max(36, scan_limit - 60), 10):
        x1 = min(width, x0 + 60)
        rows = filter_ruler_row_geometry(rows_from_ruler_band(candidates, x0, x1))
        if len(rows) < 8:
            continue
        centers = [row["center"] for row in rows]
        gaps = [centers[i + 1] - centers[i] for i in range(len(centers) - 1)]
        plausible = [gap for gap in gaps if 25 <= gap <= 65]
        if len(plausible) < 6:
            continue
        median_width = float(np.median([row["x1"] - row["x0"] for row in rows]))
        valid_bands.append((x0, x1, rows, len(plausible), median_width))

    if not valid_bands:
        return [], [min(width - 1, RULER_X0), min(width, RULER_X1)]

    max_rows = max(len(rows) for _x0, _x1, rows, _plausible, _median_width in valid_bands)
    max_plausible = max(plausible for _x0, _x1, _rows, plausible, _median_width in valid_bands)
    complete = [
        item for item in valid_bands
        if len(item[2]) >= max(8, int(round(max_rows * 0.85))) and item[3] >= max(6, max_plausible - 4)
    ]
    x0, x1, rows, _plausible, _median_width = min(
        complete or valid_bands,
        key=lambda item: item[0],
    )
    return rows, [x0, x1]


def detect_line_number_ruler(mask: np.ndarray, gray: np.ndarray, min_run_len: int) -> dict[str, Any]:
    height, width = mask.shape[:2]
    adaptive = adaptive_ink(gray)
    x_scan_hi = min(width, max(140, int(width * 0.18)))
    candidates = merge_candidates(collect_digit_candidates(mask, x_scan_hi), collect_digit_candidates(adaptive, x_scan_hi))
    rows, ruler_band = choose_ruler_rows(candidates, width)
    if len(rows) < 8:
        return {
            "available": False,
            "reason": "too_few_rows_in_fixed_ruler_band",
            "candidate_count": len(candidates),
            "ruler_band": ruler_band,
            "row_count": len(rows),
        }

    centers = [row["center"] for row in rows]
    gaps = [centers[i + 1] - centers[i] for i in range(len(centers) - 1)]
    plausible = [gap for gap in gaps if 25 <= gap <= 65]
    if len(plausible) < 6:
        return {
            "available": False,
            "reason": "no_plausible_line_step",
            "candidate_count": len(candidates),
            "ruler_band": ruler_band,
            "row_count": len(rows),
        }

    line_step = float(np.median(plausible))
    kept_centers = cadence_rows(centers, line_step, min_run_len=min_run_len)
    kept_rows = [row for row in rows if any(abs(row["center"] - center) <= 1.0 for center in kept_centers)]
    if len(kept_rows) < 8:
        return {
            "available": False,
            "reason": "ruler_run_too_short",
            "candidate_count": len(candidates),
            "ruler_band": ruler_band,
            "row_count": len(rows),
            "kept_row_count": len(kept_rows),
        }

    ruler = {
        "available": True,
        "candidate_count": len(candidates),
        "row_count": len(kept_rows),
        "all_row_count": len(rows),
        "line_step": round(line_step, 3),
        "y_top": int(min(row["y0"] for row in kept_rows)),
        "y_bottom": int(max(row["y1"] for row in kept_rows)),
        "col_left": int(min(row["x0"] for row in kept_rows)),
        "col_right": int(max(row["x1"] for row in kept_rows)),
        "ruler_band": ruler_band,
        "first_row_center": round(float(kept_centers[0]), 3),
        "last_row_center": round(float(kept_centers[-1]), 3),
        "discarded_row_centers": [
            round(float(row["center"]), 3)
            for row in rows
            if not any(abs(row["center"] - center) <= 1.0 for center in kept_centers)
        ],
    }
    gap = find_gap_after_line_numbers(mask, ruler)
    if gap is None:
        body_left = first_body_left_after_ruler(mask, ruler)
        ruler["body_left"] = body_left
        ruler["confidence"] = "tentative" if body_left is not None else "line_column_only"
    else:
        gap_start, body_left = gap
        ruler["gap_start"] = int(gap_start)
        ruler["body_left"] = int(body_left)
        ruler["confidence"] = "strong" if body_left - ruler["col_right"] >= 14 else "tentative"
    return ruler


def find_gap_after_line_numbers(mask: np.ndarray, ruler: dict[str, Any]) -> tuple[int, int] | None:
    height, width = mask.shape[:2]
    y0 = max(0, int(ruler["y_top"]) - 8)
    y1 = min(height, int(ruler["y_bottom"]) + 8)
    if y1 - y0 < 120:
        return None
    col = (mask[y0:y1, :] > 0).sum(axis=0).astype(np.float64) / max(1, y1 - y0)
    active = col >= 0.012
    start_x = min(width - 1, int(ruler["col_right"]) + 2)
    stop_x = min(width, start_x + 340)
    in_gap = False
    gap_start = 0
    for x in range(start_x, stop_x):
        if not active[x] and not in_gap:
            in_gap = True
            gap_start = x
        elif active[x] and in_gap:
            gap_end = x - 1
            if gap_end - gap_start + 1 >= 8:
                body_start = x
                sustained = int(active[body_start:min(width, body_start + 200)].sum())
                if sustained >= 8:
                    return gap_start, body_start
            in_gap = False
    return None


def first_body_left_after_ruler(mask: np.ndarray, ruler: dict[str, Any]) -> int | None:
    height, width = mask.shape[:2]
    y0 = max(0, int(ruler["y_top"]) - 8)
    y1 = min(height, int(ruler["y_bottom"]) + 8)
    if y1 - y0 < 120:
        return None
    band = mask[y0:y1, :]
    col = (band > 0).sum(axis=0).astype(np.float64) / max(1, y1 - y0)
    active = col >= 0.012
    start_x = min(width - 1, int(ruler["col_right"]) + 12)
    stop_x = min(width, start_x + 360)
    for x in range(start_x, stop_x):
        if not active[x]:
            continue
        sustained = int(active[x:min(width, x + 180)].sum())
        if sustained >= 12:
            return int(x)
    return None


def find_body_gap(mask: np.ndarray, ruler: dict[str, Any]) -> dict[str, Any]:
    if ruler.get("available") and ruler.get("body_left") is not None:
        col_right = int(ruler["col_right"])
        body_left = int(ruler["body_left"])
        split_x = int(round((col_right + body_left) / 2))
        return {
            "split_x": split_x,
            "confidence": ruler.get("confidence", "strong"),
            "method": "line_number_ruler_gap",
            "line_number_col_right": col_right,
            "body_left": body_left,
            "gap_width": int(body_left - col_right),
        }
    return {"split_x": 0, "confidence": "none", "method": "line_number_ruler_gap", "reason": "no_body_left"}


def clamp_range(start: int, end: int, limit: int, margin: int) -> tuple[int, int]:
    return max(0, start - margin), min(limit, end + margin)


def apply_page_y_policy(page_id: str, y0: int, y1: int, height: int) -> tuple[int, int, dict[str, Any] | None]:
    policy = PAGE_Y_POLICIES.get(page_id)
    if policy is None:
        return y0, y1, None

    new_y0 = y0
    new_y1 = y1
    if "y1_min" in policy:
        new_y1 = max(new_y1, int(policy["y1_min"]))
    if "y1_max" in policy:
        new_y1 = min(new_y1, int(policy["y1_max"]))
    new_y1 = min(height, max(new_y0 + 1, new_y1))

    if new_y0 == y0 and new_y1 == y1:
        return y0, y1, None
    return new_y0, new_y1, {
        "original_y": [int(y0), int(y1)],
        "adjusted_y": [int(new_y0), int(new_y1)],
        "reason": policy["reason"],
    }


def bbox_from_mask(mask: np.ndarray, row_thr: int, col_thr: int) -> tuple[int, int, int, int] | None:
    rows = np.flatnonzero((mask > 0).sum(axis=1) >= row_thr)
    cols = np.flatnonzero((mask > 0).sum(axis=0) >= col_thr)
    if rows.size == 0 or cols.size == 0:
        return None
    return int(cols[0]), int(rows[0]), int(cols[-1] + 1), int(rows[-1] + 1)


def trim_x(
    mask: np.ndarray,
    x0: int,
    x1: int,
    margin: int,
    *,
    col_frac: float = 0.001,
    min_run_width: int = 1,
) -> tuple[int, int] | None:
    if x1 <= x0:
        return None
    region = mask[:, x0:x1]
    height = region.shape[0]
    col_counts = (region > 0).sum(axis=0)
    col_thr = max(1, int(round(height * col_frac)))
    active = col_counts >= col_thr
    cols = np.flatnonzero(active)
    if cols.size == 0:
        return None
    runs: list[tuple[int, int, int]] = []
    start = int(cols[0])
    prev = int(cols[0])
    for value in cols[1:]:
        cur = int(value)
        if cur == prev + 1:
            prev = cur
            continue
        runs.append((start, prev, int(col_counts[start:prev + 1].sum())))
        start = cur
        prev = cur
    runs.append((start, prev, int(col_counts[start:prev + 1].sum())))

    substantial = [
        (start, end, mass)
        for start, end, mass in runs
        if (end - start + 1) >= min_run_width or mass >= max(20, int(height * 0.05))
    ]
    chosen = substantial if substantial else runs
    left = x0 + int(chosen[0][0])
    right = x0 + int(chosen[-1][1] + 1)
    return max(0, left - margin), min(mask.shape[1], right + margin)


def _ruler_centers_in_crop(ruler: dict[str, Any], y0: int) -> list[float]:
    if not ruler.get("available"):
        return []
    first = ruler.get("first_row_center")
    last = ruler.get("last_row_center")
    step = ruler.get("line_step")
    if first is None or last is None or step is None:
        return []
    count = max(1, int(round((float(last) - float(first)) / float(step))) + 1)
    return [float(first) + i * float(step) - y0 for i in range(count)]


def preserve_sparse_right_edge_ink(
    mask: np.ndarray,
    body_x: tuple[int, int] | None,
    common_x: tuple[int, int],
    margin: int,
    ruler: dict[str, Any],
    y0: int,
) -> tuple[tuple[int, int] | None, dict[str, Any] | None]:
    """Extend the body crop for row-aligned sparse ink missed by dense column trimming."""
    if body_x is None:
        return None, None
    body_left, body_right = body_x
    if body_right <= body_left:
        return body_x, None

    raw_right = max(body_left, body_right - margin)
    scan_right = min(mask.shape[1], common_x[1])
    if scan_right <= raw_right:
        return body_x, None

    centers = _ruler_centers_in_crop(ruler, y0)
    line_step = float(ruler.get("line_step") or 42.0)
    row_tol = max(10.0, min(18.0, line_step * 0.38))
    context_px = max(120.0, line_step * 4.0)
    max_gap_from_trim = max(72.0, line_step * 1.75)

    n_labels, _labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
    components: list[dict[str, Any]] = []
    for label in range(1, n_labels):
        x, y, w, h, area = [int(value) for value in stats[label]]
        x1 = x + w
        y1 = y + h
        if area < 4 or x1 <= body_left or x >= scan_right:
            continue
        if w > 80 or h > 80:
            continue
        cx, cy = centroids[label]
        row_index = None
        row_distance = None
        if centers:
            row_index, row_distance = min(
                enumerate(abs(float(cy) - center) for center in centers),
                key=lambda item: item[1],
            )
            if row_distance > row_tol * 1.35:
                continue
        components.append(
            {
                "label": int(label),
                "x0": x,
                "y0": y,
                "x1": x1,
                "y1": y1,
                "w": w,
                "h": h,
                "area": area,
                "cx": float(cx),
                "cy": float(cy),
                "row_index": None if row_index is None else int(row_index),
                "row_distance": None if row_distance is None else float(row_distance),
            }
        )

    candidates = [item for item in components if item["x1"] > raw_right and item["x0"] < scan_right]
    kept: list[dict[str, Any]] = []
    for item in candidates:
        nearby = [
            other
            for other in components
            if other is not item
            and abs(other["cy"] - item["cy"]) <= row_tol
            and other["x1"] <= item["x0"] + 2
            and 0 <= item["x0"] - other["x1"] <= context_px
        ]
        support_area = sum(int(other["area"]) for other in nearby)
        row_support = [
            other
            for other in components
            if other is not item
            and abs(other["cy"] - item["cy"]) <= row_tol
            and other["x0"] >= body_left
            and other["x1"] <= item["x0"] + 2
        ]
        row_support_area = sum(int(other["area"]) for other in row_support)
        gap_from_trim = max(0.0, float(item["x0"] - raw_right))
        small_row_mark = item["area"] >= 8 and item["w"] <= 18 and item["h"] <= 18
        local_supported = small_row_mark and (len(nearby) >= 2 or support_area >= 28)
        row_supported = (
            small_row_mark
            and gap_from_trim <= max_gap_from_trim
            and (len(row_support) >= 3 or row_support_area >= 80)
        )
        if local_supported or row_supported:
            item["support_mode"] = "local" if local_supported else "row"
            item["local_support_count"] = len(nearby)
            item["local_support_area"] = int(support_area)
            item["row_support_count"] = len(row_support)
            item["row_support_area"] = int(row_support_area)
            item["gap_from_trim"] = int(round(gap_from_trim))
            kept.append(item)

    if not kept:
        return body_x, None

    new_raw_right = max(raw_right, max(int(item["x1"]) for item in kept))
    new_right = min(mask.shape[1], common_x[1], new_raw_right + margin)
    if new_right <= body_right:
        return body_x, None

    sample = [
        {
            "bbox": [int(item["x0"]), int(item["y0"]), int(item["x1"]), int(item["y1"])],
            "area": int(item["area"]),
            "support_mode": item.get("support_mode"),
            "gap_from_trim": item.get("gap_from_trim"),
            "row_support_count": item.get("row_support_count"),
            "row_support_area": item.get("row_support_area"),
        }
        for item in sorted(kept, key=lambda value: value["x1"], reverse=True)[:8]
    ]
    adjustment = {
        "method": "row_aligned_sparse_right_ink",
        "original_x_range": [int(body_left), int(body_right)],
        "adjusted_x_range": [int(body_left), int(new_right)],
        "raw_right_before_margin": int(raw_right),
        "raw_right_after_preservation": int(new_raw_right),
        "candidate_count": len(candidates),
        "kept_count": len(kept),
        "max_gap_from_trim": int(round(max_gap_from_trim)),
        "sample_kept_components": sample,
    }
    return (body_left, new_right), adjustment


def crop_with_blank(img: np.ndarray, x_range: tuple[int, int] | None, y0: int, y1: int, min_width: int = 24) -> np.ndarray:
    height = max(1, y1 - y0)
    if x_range is None:
        return np.full((height, min_width, 3), 255, dtype=np.uint8)
    x0, x1 = x_range
    if x1 <= x0:
        return np.full((height, min_width, 3), 255, dtype=np.uint8)
    return img[y0:y1, x0:x1].copy()


def fit_height(img: np.ndarray, target_h: int) -> np.ndarray:
    h, w = img.shape[:2]
    if h == target_h:
        return img
    scale = target_h / max(1, h)
    return cv2.resize(img, (max(1, int(round(w * scale))), target_h), interpolation=cv2.INTER_AREA)


def draw_label(img: np.ndarray, text: str, x: int, y: int, color: tuple[int, int, int]) -> None:
    cv2.rectangle(img, (x - 4, max(0, y - 24)), (x + max(160, len(text) * 11), y + 6), (255, 255, 255), -1)
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1, cv2.LINE_AA)


def make_review(
    img: np.ndarray,
    common: np.ndarray,
    line_numbers: np.ndarray,
    text_body: np.ndarray,
    page_id: str,
    meta: dict[str, Any],
) -> np.ndarray:
    overlay = img.copy()
    y0 = int(meta["common_y"]["y0"])
    y1 = int(meta["common_y"]["y1"])
    split_x = int(meta["body_gap"]["split_x"])
    ln_x = meta["line_numbers"].get("x_range")
    body_x = meta["text_body"].get("x_range")

    cv2.rectangle(overlay, (0, y0), (overlay.shape[1] - 1, y1 - 1), (0, 0, 220), 2)
    if split_x > 0:
        cv2.line(overlay, (split_x, y0), (split_x, y1), (0, 180, 255), 2)
    if ln_x:
        cv2.rectangle(overlay, (ln_x[0], y0), (ln_x[1] - 1, y1 - 1), (255, 110, 0), 2)
    if body_x:
        cv2.rectangle(overlay, (body_x[0], y0), (body_x[1] - 1, y1 - 1), (0, 170, 0), 2)
    title = f"p{page_id} | y={y0}:{y1} | split={split_x} {meta['body_gap']['confidence']} | ruler rows={meta['common_y']['line_numbers'].get('row_count')}"
    draw_label(overlay, title, 18, 32, (0, 0, 0))

    top_h = 900
    bottom_h = 900
    overlay_s = fit_height(overlay, top_h)
    common_s = fit_height(common, bottom_h)
    ln_s = fit_height(line_numbers, bottom_h)
    body_s = fit_height(text_body, bottom_h)

    gap = 18
    header_h = 42
    top_w = overlay_s.shape[1]
    bottom_w = common_s.shape[1] + ln_s.shape[1] + body_s.shape[1] + gap * 4
    width = max(top_w + gap * 2, bottom_w)
    height = header_h + top_h + header_h + bottom_h + gap * 3
    sheet = np.full((height, width, 3), 245, dtype=np.uint8)

    x = gap
    y = header_h
    cv2.putText(sheet, "overlay on current crop", (x, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (40, 40, 40), 2, cv2.LINE_AA)
    sheet[y:y + top_h, x:x + overlay_s.shape[1]] = overlay_s

    y2 = header_h + top_h + gap + header_h
    cv2.putText(sheet, "common trim", (gap, y2 - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (40, 40, 40), 2, cv2.LINE_AA)
    x = gap
    sheet[y2:y2 + bottom_h, x:x + common_s.shape[1]] = common_s
    x += common_s.shape[1] + gap
    cv2.putText(sheet, "line numbers", (x, y2 - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 110, 0), 2, cv2.LINE_AA)
    sheet[y2:y2 + bottom_h, x:x + ln_s.shape[1]] = ln_s
    cv2.rectangle(sheet, (x, y2), (x + ln_s.shape[1] - 1, y2 + bottom_h - 1), (255, 110, 0), 2)
    x += ln_s.shape[1] + gap
    cv2.putText(sheet, "text body", (x, y2 - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 150, 0), 2, cv2.LINE_AA)
    sheet[y2:y2 + bottom_h, x:x + body_s.shape[1]] = body_s
    cv2.rectangle(sheet, (x, y2), (x + body_s.shape[1] - 1, y2 + bottom_h - 1), (0, 150, 0), 2)
    return sheet


def process_page(page_id: str, input_dir: Path, out: OutputPaths, args: argparse.Namespace) -> dict[str, Any]:
    src = page_path(input_dir, page_id)
    img = cv2.imread(str(src))
    if img is None:
        raise RuntimeError(f"could not read {src}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mask = threshold_ink(img)
    ruler = detect_line_number_ruler(mask, gray, min_run_len=args.min_ruler_run)
    body_gap = find_body_gap(mask, ruler)
    split_x = int(body_gap["split_x"])

    if ruler.get("available"):
        y0, y1 = clamp_range(int(ruler["y_top"]), int(ruler["y_bottom"]), img.shape[0], args.y_margin)
        common_y = {"y0": y0, "y1": y1, "method": "line_number_ruler", "line_numbers": ruler}
    else:
        bbox = bbox_from_mask(mask, row_thr=max(1, int(mask.shape[1] * 0.001)), col_thr=1)
        if bbox is None:
            y0, y1 = 0, img.shape[0]
        else:
            _x0, by0, _x1, by1 = bbox
            y0, y1 = clamp_range(by0, by1, img.shape[0], args.y_margin)
        common_y = {"y0": y0, "y1": y1, "method": "fallback_ink_bbox", "line_numbers": ruler}

    y0, y1, page_y_policy = apply_page_y_policy(page_id, y0, y1, img.shape[0])
    common_y["y0"] = y0
    common_y["y1"] = y1
    if page_y_policy is not None:
        common_y["page_y_policy"] = page_y_policy

    y_mask = mask[y0:y1, :]
    if ruler.get("available"):
        line_x = clamp_range(int(ruler["col_left"]), int(ruler["col_right"]), mask.shape[1], args.x_margin)
        body_start = int(body_gap.get("body_left") or split_x)
    else:
        line_x = trim_x(y_mask, 0, split_x, args.x_margin) if split_x > 0 else None
        body_start = split_x
    common_bbox = bbox_from_mask(y_mask, row_thr=1, col_thr=1)
    if common_bbox is None:
        common_x = (0, mask.shape[1])
    else:
        cx0, _cy0, cx1, _cy1 = common_bbox
        common_x = clamp_range(cx0, cx1, mask.shape[1], args.x_margin)

    body_x = trim_x(y_mask, body_start, mask.shape[1], args.x_margin, col_frac=0.003, min_run_width=6)
    body_right_preservation: dict[str, Any] | None = None
    if body_x is not None:
        body_x, body_right_preservation = preserve_sparse_right_edge_ink(
            y_mask,
            body_x,
            common_x,
            args.x_margin,
            ruler,
            y0,
        )
    if line_x is not None and split_x > 0:
        line_x = (line_x[0], min(line_x[1], split_x))
    if body_x is not None and body_x[1] <= body_x[0]:
        body_x = None

    common_img = img[y0:y1, common_x[0]:common_x[1]].copy()
    line_img = crop_with_blank(img, line_x, y0, y1)
    body_img = crop_with_blank(img, body_x, y0, y1)
    review = make_review(
        img,
        common_img,
        line_img,
        body_img,
        page_id,
        {
            "body_gap": body_gap,
            "common_y": common_y,
            "line_numbers": {"x_range": list(line_x) if line_x is not None else None},
            "text_body": {"x_range": list(body_x) if body_x is not None else None},
        },
    )

    common_path = out.common / f"p{page_id}_common.jpg"
    line_path = out.line_numbers / f"p{page_id}_line_numbers.jpg"
    body_path = out.text_body / f"p{page_id}_text_body.jpg"
    review_path = out.reviews / f"p{page_id}_review.jpg"
    cv2.imwrite(str(common_path), common_img, [cv2.IMWRITE_JPEG_QUALITY, 94])
    cv2.imwrite(str(line_path), line_img, [cv2.IMWRITE_JPEG_QUALITY, 94])
    cv2.imwrite(str(body_path), body_img, [cv2.IMWRITE_JPEG_QUALITY, 94])
    cv2.imwrite(str(review_path), review, [cv2.IMWRITE_JPEG_QUALITY, 92])

    meta = {
        "page": page_id,
        "source": rel(src),
        "source_size": [int(img.shape[1]), int(img.shape[0])],
        "body_gap": body_gap,
        "common_y": common_y,
        "common_crop": {
            "path": rel(common_path),
            "x_range": list(common_x),
            "size": [int(common_img.shape[1]), int(common_img.shape[0])],
        },
        "line_numbers": {
            "path": rel(line_path),
            "x_range": list(line_x) if line_x is not None else None,
            "size": [int(line_img.shape[1]), int(line_img.shape[0])],
        },
        "text_body": {
            "path": rel(body_path),
            "x_range": list(body_x) if body_x is not None else None,
            "size": [int(body_img.shape[1]), int(body_img.shape[0])],
            "right_edge_preservation": body_right_preservation,
        },
        "review": {"path": rel(review_path), "size": [int(review.shape[1]), int(review.shape[0])]},
        "margins": {"x": args.x_margin, "y": args.y_margin},
    }
    meta_path = out.metadata / f"p{page_id}.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def resolve_pages(input_dir: Path, args: argparse.Namespace) -> list[str]:
    if args.sample:
        return SAMPLE_PAGES
    if args.pages:
        if args.pages == ["all"]:
            return sorted(normalize_page_id(path.name) for path in input_dir.glob("keph_p*.jpg"))
        return [normalize_page_id(page) for page in args.pages]
    return sorted(normalize_page_id(path.name) for path in input_dir.glob("keph_p*.jpg"))


def run_page(page_id: str, input_dir: Path, out: OutputPaths, args: argparse.Namespace) -> dict[str, Any]:
    try:
        return {"page": page_id, "ok": True, "meta": process_page(page_id, input_dir, out, args)}
    except Exception as exc:
        return {
            "page": page_id,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "trace": traceback.format_exc(),
        }


def load_metadata_summary(out: OutputPaths, fallback_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for meta_path in sorted(out.metadata.glob("p*.json")):
        try:
            rows.append(json.loads(meta_path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return rows or fallback_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pages", nargs="*", help="Page ids, or 'all'. Defaults to all current v2 crops.")
    parser.add_argument("--sample", action="store_true", help="Process representative sample pages instead of all pages.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--x-margin", type=int, default=18)
    parser.add_argument("--y-margin", type=int, default=22)
    parser.add_argument("--min-ruler-run", type=int, default=3)
    parser.add_argument("-j", "--max-workers", type=int, default=6)
    args = parser.parse_args()

    input_dir = args.input_dir.resolve()
    out = OutputPaths.from_root(args.output_dir.resolve())
    out.mkdirs()
    pages = resolve_pages(input_dir, args)
    if not pages:
        parser.error(f"no page crops found in {input_dir}")

    n_workers = max(1, int(args.max_workers))
    print(f"splitting {len(pages)} pages with {n_workers} workers")

    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        futures = {
            executor.submit(run_page, page_id, input_dir, out, args): page_id
            for page_id in pages
        }
        with tqdm(total=len(futures), desc="split pages", unit="page") as progress:
            for future in as_completed(futures):
                result = future.result()
                if result.get("ok"):
                    rows.append(result["meta"])
                else:
                    failures.append(result)
                    tqdm.write(f"p{result['page']}: ERROR {result.get('error')}")
                progress.set_postfix(
                    written=len(rows),
                    failed=len(failures),
                )
                progress.update(1)

    summary_rows = load_metadata_summary(out, rows)
    summary = {
        "input_dir": rel(input_dir),
        "output_dir": rel(out.root),
        "count": len(summary_rows),
        "updated_count": len(rows),
        "failure_count": len(failures),
        "pages": summary_rows,
        "failures": failures,
    }
    (out.root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nwrote {len(rows)} pages, failures={len(failures)} -> {out.root}")


if __name__ == "__main__":
    main()