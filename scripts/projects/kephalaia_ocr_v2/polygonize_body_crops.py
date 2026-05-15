"""Derive geometry from reviewed v2 Coptic body crops.

This computes ink geometry directly from the accepted body crops:

- high-resolution ink components and contour polygons;
- ink-profile median-line candidates derived from the body crop itself;
- row outline polygons derived from the ink elements assigned to each median line;
- small dot-like component rows, including lacuna-dot-only rows;
- edge-touching artifacts recorded but excluded from row evidence;
- review images that show the body crop, mask, polygons, dot rows, and row
    outline geometry together.
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from tqdm import tqdm


REPO = Path(__file__).resolve().parents[3]
PROJECT_OUT = REPO / "output" / "projects" / "kephalaia_ocr_v2"
DEFAULT_BODY_DIR = PROJECT_OUT / "line_body_split" / "text_body"
DEFAULT_OUT_DIR = PROJECT_OUT / "body_geometry"
SAMPLE_PAGES = ["010", "017", "057", "100", "113", "114", "127", "185", "196", "283", "288"]


@dataclass(frozen=True)
class Band:
    y0: int
    y1: int
    source: str

    @property
    def center(self) -> float:
        return (self.y0 + self.y1) / 2.0


def rel(path: Path) -> str:
    return str(path.relative_to(REPO)).replace("\\", "/")


def normalize_page_id(page: str) -> str:
    name = Path(page).name
    return (
        name.removeprefix("keph_p")
        .removeprefix("p")
        .removesuffix("_text_body.jpg")
        .removesuffix(".jpg")
        .removesuffix(".json")
    )


def body_path(body_dir: Path, page_id: str) -> Path:
    return body_dir / f"p{page_id}_text_body.jpg"


def resolve_pages(args: argparse.Namespace, body_dir: Path) -> list[str]:
    if args.sample:
        return SAMPLE_PAGES
    if args.pages and args.pages != ["all"]:
        return [normalize_page_id(page) for page in args.pages]
    if args.pages == ["all"]:
        return sorted(normalize_page_id(path.name) for path in body_dir.glob("p*_text_body.jpg"))
    return sorted(normalize_page_id(path.name) for path in body_dir.glob("p*_text_body.jpg"))


def odd_at_least(value: int, minimum: int) -> int:
    value = max(minimum, int(value))
    return value if value % 2 else value + 1


def threshold_ink_high_res(img: np.ndarray, scale: int, *, contrast_threshold: int) -> tuple[np.ndarray, np.ndarray]:
    if scale < 1:
        raise ValueError("scale must be >= 1")
    if scale == 1:
        work = img
    else:
        work = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, otsu = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    block = odd_at_least(31 * scale, 31)
    adaptive_raw = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        block,
        12,
    )
    background = cv2.medianBlur(gray, odd_at_least(41 * scale, 41))
    local_contrast = cv2.subtract(background, gray)
    _, contrast = cv2.threshold(local_contrast, max(1, contrast_threshold), 255, cv2.THRESH_BINARY)
    adaptive = cv2.bitwise_and(adaptive_raw, contrast)
    mask = cv2.bitwise_or(cv2.bitwise_or(otsu, adaptive), contrast)

    low_threshold = max(5, contrast_threshold - 6)
    _, low_contrast = cv2.threshold(local_contrast, low_threshold, 255, cv2.THRESH_BINARY)
    weak_adaptive = cv2.bitwise_and(adaptive_raw, low_contrast)
    weak_extra = cv2.bitwise_and(weak_adaptive, cv2.bitwise_not(mask))
    recovery = np.zeros_like(mask)
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(weak_extra, connectivity=8)
    for label in range(1, n_labels):
        x, y, w, h, area = [int(v) for v in stats[label]]
        width_orig = w / scale
        height_orig = h / scale
        area_orig = area / float(scale * scale)
        aspect = width_orig / max(1.0, height_orig)
        thin_horizontal = width_orig >= 7 and height_orig <= 6.0 and aspect >= 2.4 and area_orig >= 5
        weak_character = 3 <= width_orig <= 55 and 7 <= height_orig <= 42 and area_orig >= 16 and aspect <= 4.5
        if thin_horizontal or weak_character:
            recovery[labels == label] = 255
    mask = cv2.bitwise_or(mask, recovery)
    return work, mask


def contour_to_polygon(contour: np.ndarray, epsilon_ratio: float, min_epsilon: float) -> list[list[int]]:
    perimeter = cv2.arcLength(contour, True)
    epsilon = max(float(min_epsilon), float(epsilon_ratio) * perimeter)
    approx = cv2.approxPolyDP(contour, epsilon, True)
    points = [[int(point[0][0]), int(point[0][1])] for point in approx]
    if len(points) >= 3:
        return points
    x, y, w, h = cv2.boundingRect(contour)
    return [[int(x), int(y)], [int(x + w), int(y)], [int(x + w), int(y + h)], [int(x), int(y + h)]]


def contour_holes(mask: np.ndarray, component_mask: np.ndarray) -> int:
    contours, hierarchy = cv2.findContours(component_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return 0
    holes = 0
    for index, contour in enumerate(contours):
        parent = int(hierarchy[0][index][3])
        if parent >= 0 and cv2.contourArea(contour) >= 3.0:
            holes += 1
    return holes


def collect_components(
    mask: np.ndarray,
    *,
    scale: int,
    min_component_area: int,
    epsilon_ratio: float,
    min_epsilon: float,
) -> tuple[list[dict[str, Any]], np.ndarray]:
    n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    components: list[dict[str, Any]] = []
    kept_mask = np.zeros_like(mask)
    for label in range(1, n_labels):
        x, y, w, h, area = [int(v) for v in stats[label]]
        if area < min_component_area:
            continue
        component_mask = np.zeros_like(mask)
        component_mask[labels == label] = 255
        contours, _ = cv2.findContours(component_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if not contours:
            continue
        contour = max(contours, key=cv2.contourArea)
        polygon = contour_to_polygon(contour, epsilon_ratio, min_epsilon)
        cx, cy = centroids[label]
        kept_mask[labels == label] = 255
        width_orig = w / scale
        height_orig = h / scale
        area_orig = area / float(scale * scale)
        is_dot_like = (
            width_orig <= 17
            and height_orig <= 17
            and area_orig <= 115
            and 0.35 <= width_orig / max(1.0, height_orig) <= 2.8
        )
        is_thin_horizontal_mark = (
            width_orig >= 7
            and height_orig <= 6.5
            and width_orig / max(1.0, height_orig) >= 2.4
            and area_orig <= 140
        )
        components.append(
            {
                "id": len(components),
                "bbox_scaled": [x, y, w, h],
                "bbox": [round(x / scale, 2), round(y / scale, 2), round(w / scale, 2), round(h / scale, 2)],
                "centroid_scaled": [round(float(cx), 2), round(float(cy), 2)],
                "centroid": [round(float(cx) / scale, 2), round(float(cy) / scale, 2)],
                "area_scaled_px": area,
                "area_px": round(area_orig, 2),
                "contour_area_scaled": round(float(cv2.contourArea(contour)), 2),
                "holes": contour_holes(mask, component_mask),
                "is_dot_like": bool(is_dot_like),
                "is_thin_horizontal_mark": bool(is_thin_horizontal_mark),
                "polygon_scaled": polygon,
            }
        )
    components.sort(key=lambda item: (item["bbox_scaled"][1], item["bbox_scaled"][0]))
    for index, component in enumerate(components):
        component["id"] = index
    return components, kept_mask


def mark_edge_artifacts(
    components: list[dict[str, Any]],
    *,
    image_width: int,
    image_height: int,
    edge_margin: float,
    side_edge_margin: float,
    side_artifact_band: float,
    tall_artifact_height_ratio: float,
) -> None:
    def has_nearby_text_context(candidate: dict[str, Any]) -> bool:
        cx, cy, cwidth, cheight = [float(value) for value in candidate["bbox"]]
        candidate_x1 = cx + cwidth
        candidate_y1 = cy + cheight
        for other in components:
            if other is candidate:
                continue
            if other.get("is_dot_like") or other.get("is_thin_horizontal_mark"):
                continue
            ox, oy, owidth, oheight = [float(value) for value in other["bbox"]]
            if float(other.get("area_px", 0.0)) < 80.0 or oheight < 10.0 or owidth < 6.0:
                continue
            other_center_y = oy + oheight / 2.0
            if other_center_y < cy - 18.0 or other_center_y > candidate_y1 + 18.0:
                continue
            horizontal_gap = ox - candidate_x1
            if 0.0 <= horizontal_gap <= 320.0:
                return True
        return False

    for component in components:
        x, y, width, height = [float(value) for value in component["bbox"]]
        touches_top = y <= edge_margin
        touches_bottom = y + height >= image_height - edge_margin
        touches_left = x <= side_edge_margin
        touches_right = x + width >= image_width - side_edge_margin
        top_bottom_fragment = (touches_top or touches_bottom) and (
            float(component["area_px"]) <= 90
            or height <= 10
            or (component.get("is_dot_like") and float(component["area_px"]) <= 120)
            or component.get("is_thin_horizontal_mark")
        )
        small_side_fragment = (touches_left or touches_right) and (
            float(component["area_px"]) <= 90 or width <= 8 or height <= 10
        )
        tall_side_rule = (
            height >= image_height * tall_artifact_height_ratio
            and width <= 24
            and (x <= side_artifact_band or x + width >= image_width - side_artifact_band)
        )
        rescued_side_marker = bool(
            tall_side_rule
            and width >= 7.0
            and float(component.get("area_px", 0.0)) >= 100.0
            and has_nearby_text_context(component)
        )
        is_edge_artifact = top_bottom_fragment or small_side_fragment or (tall_side_rule and not rescued_side_marker)
        component["edge"] = {
            "touches_top": bool(touches_top),
            "touches_bottom": bool(touches_bottom),
            "touches_left": bool(touches_left),
            "touches_right": bool(touches_right),
            "top_bottom_fragment": bool(top_bottom_fragment),
            "tall_side_rule": bool(tall_side_rule),
            "rescued_side_marker": bool(rescued_side_marker),
            "is_edge_artifact": bool(is_edge_artifact),
        }


def bbox_gap(a: list[float], b: list[float]) -> tuple[float, float]:
    ax0, ay0, aw, ah = [float(value) for value in a]
    bx0, by0, bw, bh = [float(value) for value in b]
    ax1 = ax0 + aw
    ay1 = ay0 + ah
    bx1 = bx0 + bw
    by1 = by0 + bh
    x_gap = max(0.0, bx0 - ax1, ax0 - bx1)
    y_gap = max(0.0, by0 - ay1, ay0 - by1)
    return x_gap, y_gap


def mark_tiny_dot_artifacts(
    components: list[dict[str, Any]],
    *,
    max_area_px: float,
    neighbor_px: float,
    min_dot_row_count: int,
    dot_row_y_tolerance: float,
    dot_row_size_ratio: float,
    char_x_pad_px: float,
) -> None:
    eligible_dots = [
        component for component in components
        if component.get("is_dot_like") and not component.get("edge", {}).get("is_edge_artifact")
    ]
    dot_groups: list[list[dict[str, Any]]] = []
    for dot in sorted(eligible_dots, key=lambda item: (item["centroid"][1], item["centroid"][0])):
        cy = float(dot["centroid"][1])
        placed = False
        for group in dot_groups:
            median_y = float(np.median([item["centroid"][1] for item in group]))
            if abs(cy - median_y) <= dot_row_y_tolerance:
                group.append(dot)
                placed = True
                break
        if not placed:
            dot_groups.append([dot])

    dot_row_supported_ids: set[int] = set()
    for group in dot_groups:
        if len(group) < min_dot_row_count:
            continue
        median_area = max(1.0, float(np.median([float(item["area_px"]) for item in group])))
        median_width = max(1.0, float(np.median([float(item["bbox"][2]) for item in group])))
        median_height = max(1.0, float(np.median([float(item["bbox"][3]) for item in group])))
        for item in group:
            width = float(item["bbox"][2])
            height = float(item["bbox"][3])
            area = float(item["area_px"])
            if (
                area >= median_area * dot_row_size_ratio
                and width >= median_width * dot_row_size_ratio
                and height >= median_height * dot_row_size_ratio
            ):
                dot_row_supported_ids.add(int(item["id"]))

    support_components = [
        component for component in components
        if not component.get("edge", {}).get("is_edge_artifact")
        and not component.get("is_dot_like")
        and float(component.get("area_px", 0.0)) >= max(10.0, max_area_px)
    ]
    contextless_area_px = max(max_area_px, 18.0)
    small_lacuna_dot_ids: set[int] = set()
    small_dot_candidates = []
    for component in eligible_dots:
        x, y, width, height = [float(value) for value in component["bbox"]]
        area = float(component.get("area_px", 0.0))
        if area <= contextless_area_px * 1.45 and width <= 7.0 and height <= 7.0:
            small_dot_candidates.append(component)

    small_dot_groups: list[list[dict[str, Any]]] = []
    for dot in sorted(small_dot_candidates, key=lambda item: (float(item["centroid"][1]), float(item["centroid"][0]))):
        cx, cy = [float(value) for value in dot["centroid"]]
        best_index: int | None = None
        best_gap: float | None = None
        for index, group in enumerate(small_dot_groups):
            median_y = float(np.median([float(item["centroid"][1]) for item in group]))
            if abs(cy - median_y) > dot_row_y_tolerance:
                continue
            nearest_x_gap = min(abs(cx - float(item["centroid"][0])) for item in group)
            if nearest_x_gap > 36.0:
                continue
            if best_gap is None or nearest_x_gap < best_gap:
                best_index = index
                best_gap = nearest_x_gap
        if best_index is None:
            small_dot_groups.append([dot])
        else:
            small_dot_groups[best_index].append(dot)
    for group in small_dot_groups:
        if len(group) >= min_dot_row_count:
            small_lacuna_dot_ids.update(int(item["id"]) for item in group)

    for component in components:
        is_excluded = False
        reason = None
        near_character_supported = False
        if component.get("is_dot_like") and not component.get("edge", {}).get("is_edge_artifact"):
            x, y, width, height = [float(value) for value in component["bbox"]]
            center_x = x + width / 2.0
            area = float(component["area_px"])
            tiny = area <= max_area_px or width <= 2.5 or height <= 2.5
            contextless_small = area <= contextless_area_px and (width <= 5.5 or height <= 5.5)
            supported = False
            if tiny or contextless_small:
                if int(component["id"]) in dot_row_supported_ids or int(component["id"]) in small_lacuna_dot_ids:
                    supported = True
                elif not tiny:
                    max_attach_gap = min(neighbor_px, 7.0)
                    for other in support_components:
                        other_x, other_y, other_width, other_height = [float(value) for value in other["bbox"]]
                        _, y_gap = bbox_gap(component["bbox"], other["bbox"])
                        vertically_separated = y_gap >= 0.5
                        horizontally_under_glyph = (
                            other_x <= center_x <= other_x + other_width
                        )
                        if vertically_separated and horizontally_under_glyph and y_gap <= max_attach_gap:
                            supported = True
                            near_character_supported = True
                            break
            if (tiny or contextless_small) and not supported:
                is_excluded = True
                reason = "tiny_isolated_dot" if tiny else "small_contextless_dot"
        component["artifact"] = {
            "is_excluded": bool(is_excluded),
            "reason": reason,
            "dot_row_supported": bool(int(component["id"]) in dot_row_supported_ids or int(component["id"]) in small_lacuna_dot_ids),
            "small_lacuna_row_supported": bool(int(component["id"]) in small_lacuna_dot_ids),
            "near_character_supported": bool(near_character_supported),
        }


def component_is_excluded(component: dict[str, Any]) -> bool:
    return bool(component.get("edge", {}).get("is_edge_artifact") or component.get("artifact", {}).get("is_excluded"))


def component_mask(
    components: list[dict[str, Any]],
    shape: tuple[int, int],
    *,
    component_ids: set[int] | None = None,
    exclude_edge_artifacts: bool = True,
    exclude_artifacts: bool = True,
    exclude_thin_horizontal_marks: bool = False,
) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    for component in components:
        if component_ids is not None and int(component["id"]) not in component_ids:
            continue
        if exclude_edge_artifacts and component.get("edge", {}).get("is_edge_artifact"):
            continue
        if exclude_artifacts and component.get("artifact", {}).get("is_excluded"):
            continue
        if exclude_thin_horizontal_marks and component.get("is_thin_horizontal_mark"):
            continue
        points = np.asarray(component["polygon_scaled"], dtype=np.int32).reshape((-1, 1, 2))
        cv2.fillPoly(mask, [points], 255, cv2.LINE_AA)
    return mask


def ink_baseline_candidates(
    mask: np.ndarray,
    *,
    scale: int,
    min_activity: int,
    smooth_px: int,
    min_gap_px: float,
) -> list[dict[str, Any]]:
    profile = (mask > 0).sum(axis=1).astype(np.float32)
    if smooth_px > 1:
        kernel_len = odd_at_least(smooth_px * scale, 3)
        profile = cv2.GaussianBlur(profile.reshape(-1, 1), (1, kernel_len), 0).ravel()
    nonzero = profile[profile > 0]
    if nonzero.size == 0:
        return []
    threshold = max(float(min_activity * scale), float(np.percentile(nonzero, 35)))
    min_gap_scaled = max(1, int(round(min_gap_px * scale)))
    selected: list[dict[str, Any]] = []
    for y_scaled in np.argsort(profile)[::-1]:
        score = float(profile[int(y_scaled)])
        if score < threshold:
            break
        if any(abs(int(y_scaled) - int(item["baseline_y_scaled"])) <= min_gap_scaled for item in selected):
            continue
        selected.append(
            {
                "baseline_y": round(float(y_scaled) / scale, 2),
                "baseline_y_scaled": int(y_scaled),
                "score": round(score, 2),
                "source": "ink_profile",
                "seed_component_ids": [],
            }
        )
    selected.sort(key=lambda item: float(item["baseline_y"]))
    return selected


def merge_baseline_candidates(
    ink_candidates: list[dict[str, Any]],
    dot_row_items: list[dict[str, Any]],
    *,
    merge_px: float,
    dot_attach_px: float,
) -> list[dict[str, Any]]:
    candidates = [dict(item) for item in ink_candidates]
    for row in dot_row_items:
        center_y = float(row["center_y"])
        nearest_index = None
        nearest_delta = None
        for index, candidate in enumerate(candidates):
            if "ink_profile" not in str(candidate.get("source", "")):
                continue
            delta = abs(float(candidate["baseline_y"]) - center_y)
            if nearest_delta is None or delta < nearest_delta:
                nearest_delta = delta
                nearest_index = index
        if nearest_index is not None and nearest_delta is not None and nearest_delta <= dot_attach_px:
            candidate = candidates[nearest_index]
            candidate["seed_component_ids"] = sorted(
                set(candidate.get("seed_component_ids", [])) | set(row["component_ids"])
            )
            candidate["source"] = "+".join(sorted(set(str(candidate["source"]).split("+")) | {"dot_row_attached"}))
            candidate["score"] = round(float(candidate.get("score", 0.0)) + float(row["dot_count"]), 2)
        else:
            candidates.append(
                {
                    "baseline_y": center_y,
                    "baseline_y_scaled": None,
                    "score": float(row["dot_count"]),
                    "source": "dot_row_standalone",
                    "seed_component_ids": list(row["component_ids"]),
                }
            )
    if not candidates:
        return []
    candidates.sort(key=lambda item: float(item["baseline_y"]))
    merged: list[dict[str, Any]] = []
    for candidate in candidates:
        if merged and abs(float(candidate["baseline_y"]) - float(merged[-1]["baseline_y"])) <= merge_px:
            previous = merged[-1]
            previous_weight = max(1.0, float(previous.get("score", 1.0)))
            candidate_weight = max(1.0, float(candidate.get("score", 1.0)))
            previous["baseline_y"] = round(
                (float(previous["baseline_y"]) * previous_weight + float(candidate["baseline_y"]) * candidate_weight)
                / (previous_weight + candidate_weight),
                2,
            )
            previous["score"] = round(previous_weight + candidate_weight, 2)
            previous_sources = set(str(previous["source"]).split("+"))
            candidate_sources = set(str(candidate["source"]).split("+"))
            previous["source"] = "+".join(sorted(previous_sources | candidate_sources))
            previous["seed_component_ids"] = sorted(
                set(previous.get("seed_component_ids", [])) | set(candidate.get("seed_component_ids", []))
            )
        else:
            merged.append(dict(candidate))
    for index, candidate in enumerate(merged, start=1):
        candidate["index"] = index
    return merged


def row_outline_polygons(
    components: list[dict[str, Any]],
    component_ids: set[int],
    mask_shape: tuple[int, int],
    *,
    scale: int,
    pad_px: int,
    close_x_px: int,
    close_y_px: int,
) -> tuple[list[list[list[int]]], list[list[list[float]]]]:
    row_mask = component_mask(components, mask_shape, component_ids=component_ids, exclude_edge_artifacts=False)
    if pad_px > 0:
        radius = max(1, int(round(pad_px * scale)))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius * 2 + 1, radius * 2 + 1))
        row_mask = cv2.dilate(row_mask, kernel, iterations=1)
    if close_x_px > 0 or close_y_px > 0:
        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (max(1, int(round(close_x_px * scale))), max(1, int(round(close_y_px * scale)))),
        )
        row_mask = cv2.morphologyEx(row_mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    contours, _ = cv2.findContours(row_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = [contour for contour in contours if cv2.contourArea(contour) >= max(8, 8 * scale * scale)]
    contours.sort(key=lambda contour: cv2.boundingRect(contour)[0])
    scaled_polygons: list[list[list[int]]] = []
    original_polygons: list[list[list[float]]] = []
    for contour in contours:
        polygon = contour_to_polygon(contour, 0.002, 0.6)
        scaled_polygons.append(polygon)
        original_polygons.append([[round(x / scale, 2), round(y / scale, 2)] for x, y in polygon])
    return scaled_polygons, original_polygons


def component_span(component: dict[str, Any]) -> tuple[float, float]:
    x, _, width, _ = [float(value) for value in component["bbox"]]
    return x, x + width


def components_span(components: list[dict[str, Any]]) -> tuple[float, float]:
    return (
        min(component_span(component)[0] for component in components),
        max(component_span(component)[1] for component in components),
    )


def unique_components(components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[int, dict[str, Any]] = {}
    for component in components:
        by_id[int(component["id"])] = component
    return sorted(by_id.values(), key=lambda item: (float(item["bbox"][0]), float(item["bbox"][1])))


def is_main_text_baseline_anchor(component: dict[str, Any], line_y: float) -> bool:
    if component.get("is_dot_like") or component.get("is_thin_horizontal_mark") or component_is_excluded(component):
        return False
    x, y, width, height = [float(value) for value in component["bbox"]]
    area = float(component.get("area_px", 0.0))
    if width < 2.0 or height < 5.0 or area < 10.0:
        return False
    center_y = y + height / 2.0
    vertical_tolerance = max(6.0, min(18.0, height * 0.75))
    return y - 2.0 <= line_y <= y + height + 2.0 or abs(center_y - line_y) <= vertical_tolerance


def baseline_anchor_components(
    touched: list[dict[str, Any]],
    *,
    line_y: float,
    is_dot_only_candidate: bool,
    min_segment_width_px: float,
) -> tuple[list[dict[str, Any]], str, list[dict[str, Any]], list[dict[str, Any]]]:
    dot_anchors = [component for component in touched if component.get("is_dot_like") and not component_is_excluded(component)]
    if is_dot_only_candidate:
        if dot_anchors:
            return dot_anchors, "standalone_dot_row", [], dot_anchors
        return touched, "all_row_fallback", [], []

    text_anchors = [component for component in touched if is_main_text_baseline_anchor(component, line_y)]
    anchors = unique_components(text_anchors + dot_anchors)
    if text_anchors:
        left, right = components_span(text_anchors)
        if len(text_anchors) >= 2 or right - left >= min_segment_width_px:
            source = "main_text_components"
            if dot_anchors:
                source += "+lacuna_points"
            return anchors, source, text_anchors, dot_anchors
    if dot_anchors:
        return dot_anchors, "lacuna_points", [], dot_anchors
    return touched, "all_row_fallback", [], []


def robust_row_baseline_y(
    *,
    profile_y: float,
    text_anchors: list[dict[str, Any]],
    dot_anchors: list[dict[str, Any]],
    bottom_percentile: float,
) -> float:
    if text_anchors:
        bottoms = np.asarray(
            [float(component["bbox"][1]) + float(component["bbox"][3]) for component in text_anchors],
            dtype=np.float32,
        )
        return round(float(np.percentile(bottoms, bottom_percentile)), 2)
    if dot_anchors:
        centers = np.asarray([float(component["centroid"][1]) for component in dot_anchors], dtype=np.float32)
        return round(float(np.median(centers)), 2)
    return round(float(profile_y), 2)


def component_bbox_edges(component: dict[str, Any]) -> tuple[float, float, float, float]:
    x, y, width, height = [float(value) for value in component["bbox"]]
    return x, y, x + width, y + height


def component_center(component: dict[str, Any]) -> tuple[float, float]:
    x0, y0, x1, y1 = component_bbox_edges(component)
    return (x0 + x1) / 2.0, (y0 + y1) / 2.0


def component_is_horizontal_rule_like(component: dict[str, Any]) -> bool:
    x0, y0, x1, y1 = component_bbox_edges(component)
    width = x1 - x0
    height = y1 - y0
    if height <= 0.0:
        return False
    aspect = width / height
    area = float(component.get("area_px", 0.0))
    return width >= 18.0 and height <= 8.5 and aspect >= 3.0 and area >= 35.0


def component_is_box_bottom_rule_for_group(component: dict[str, Any], group: dict[str, Any]) -> bool:
    if component.get("is_dot_like") or not component_is_horizontal_rule_like(component):
        return False
    rule_x0, rule_y0, rule_x1, _ = component_bbox_edges(component)
    rule_width = rule_x1 - rule_x0
    if rule_width > 140.0:
        return False
    group_center = float(group["center_y"])
    group_bottom = float(group["bottom"])
    if rule_y0 < group_center or not (-2.0 <= rule_y0 - group_bottom <= 10.0):
        return False
    left_side = False
    right_side = False
    for seed_component in group.get("seed_components", []):
        seed_x0, seed_y0, seed_x1, seed_y1 = component_bbox_edges(seed_component)
        seed_width = seed_x1 - seed_x0
        seed_height = seed_y1 - seed_y0
        if seed_width > 14.0 or seed_height < 20.0:
            continue
        if interval_gap(seed_y0, seed_y1, group_center - 28.0, group_bottom + 4.0) > 0.0:
            continue
        seed_center_x = (seed_x0 + seed_x1) / 2.0
        if rule_x0 - 6.0 <= seed_center_x <= rule_x0 + 16.0:
            left_side = True
        if rule_x1 - 16.0 <= seed_center_x <= rule_x1 + 6.0:
            right_side = True
    return left_side and right_side


def component_is_leading_side_marker_like(component: dict[str, Any]) -> bool:
    x0, y0, x1, y1 = component_bbox_edges(component)
    width = x1 - x0
    height = y1 - y0
    if width <= 0.0:
        return False
    return x0 <= 40.0 and width <= 24.0 and height >= 65.0 and height >= width * 4.0


def component_is_side_marker_continuation_like(component: dict[str, Any]) -> bool:
    if component.get("is_dot_like") or component.get("is_thin_horizontal_mark") or component_is_horizontal_rule_like(component):
        return False
    x0, y0, x1, y1 = component_bbox_edges(component)
    width = x1 - x0
    height = y1 - y0
    area = float(component.get("area_px", 0.0))
    if width <= 0.0:
        return False
    return x0 <= 45.0 and width <= 24.0 and height >= 35.0 and area >= 95.0 and height >= width * 3.0


def component_is_row_side_marker_like(component: dict[str, Any]) -> bool:
    return component_is_leading_side_marker_like(component) or component_is_side_marker_continuation_like(component)


def row_should_include_leading_side_markers(touched: list[dict[str, Any]]) -> bool:
    side_markers = [item for item in touched if component_is_row_side_marker_like(item)]
    if not side_markers:
        return False
    content = [item for item in touched if not component_is_row_side_marker_like(item)]
    if not content:
        return False
    content_x0 = min(component_bbox_edges(item)[0] for item in content)
    content_y0 = min(component_bbox_edges(item)[1] for item in content)
    content_x1 = max(component_bbox_edges(item)[2] for item in content)
    content_y1 = max(component_bbox_edges(item)[3] for item in content)
    content_width = content_x1 - content_x0
    non_dot_count = sum(1 for item in content if not item.get("is_dot_like"))
    for marker in side_markers:
        marker_x0, marker_y0, marker_x1, marker_y1 = component_bbox_edges(marker)
        marker_height = marker_y1 - marker_y0
        if marker_height < 95.0:
            continue
        if marker_x1 > content_x0 + 8.0:
            continue
        if interval_gap(marker_x0, marker_x1, content_x0, content_x1) > 180.0:
            continue
        if interval_gap(marker_y0, marker_y1, content_y0, content_y1) <= 6.0:
            return True
    if content_width > 340.0 or non_dot_count > 24:
        return False
    for marker in side_markers:
        marker_x0, marker_y0, marker_x1, marker_y1 = component_bbox_edges(marker)
        if marker_x1 > content_x0 + 8.0:
            continue
        if interval_gap(marker_x0, marker_x1, content_x0, content_x1) > 78.0:
            continue
        if interval_gap(marker_y0, marker_y1, content_y0, content_y1) <= 18.0:
            return True
    return False


def is_main_outline_seed(component: dict[str, Any], *, min_height_px: float, min_area_px: float) -> bool:
    if component_is_excluded(component):
        return False
    if component.get("is_dot_like") or component.get("is_thin_horizontal_mark") or component_is_horizontal_rule_like(component):
        return False
    _, y0, _, y1 = component_bbox_edges(component)
    height = y1 - y0
    area = float(component.get("area_px", 0.0))
    return height >= min_height_px or area >= min_area_px


def keep_outline_seed_group(
    group: list[dict[str, Any]],
    stats: dict[str, float],
    *,
    min_components: int,
    min_x_span: float,
) -> bool:
    if len(group) >= min_components or stats["x1"] - stats["x0"] >= min_x_span:
        return True
    if len(group) != 1:
        return False
    component = group[0]
    x0, y0, x1, y1 = component_bbox_edges(component)
    return (x1 - x0) >= 30.0 and (y1 - y0) >= 10.0 and float(component.get("area_px", 0.0)) >= 140.0


def robust_center(values: list[float]) -> float:
    return float(np.median(np.asarray(values, dtype=np.float32)))


def row_group_stats(components: list[dict[str, Any]]) -> dict[str, float]:
    x0s: list[float] = []
    y0s: list[float] = []
    x1s: list[float] = []
    y1s: list[float] = []
    centers: list[float] = []
    for component in components:
        x0, y0, x1, y1 = component_bbox_edges(component)
        x0s.append(x0)
        y0s.append(y0)
        x1s.append(x1)
        y1s.append(y1)
        centers.append((y0 + y1) / 2.0)
    return {
        "x0": min(x0s),
        "x1": max(x1s),
        "top": float(np.percentile(np.asarray(y0s, dtype=np.float32), 15)),
        "bottom": float(np.percentile(np.asarray(y1s, dtype=np.float32), 85)),
        "center_y": robust_center(centers),
    }


def outline_seed_groups(
    components: list[dict[str, Any]],
    *,
    seed_y_tolerance_px: float,
    min_components: int,
    min_x_span: float,
) -> list[dict[str, Any]]:
    groups: list[list[dict[str, Any]]] = []
    for component in sorted(components, key=lambda item: (component_center(item)[1], component_center(item)[0])):
        _, center_y = component_center(component)
        best_index: int | None = None
        best_delta: float | None = None
        for index, group in enumerate(groups):
            group_center = robust_center([component_center(item)[1] for item in group])
            delta = abs(center_y - group_center)
            if delta <= seed_y_tolerance_px and (best_delta is None or delta < best_delta):
                best_index = index
                best_delta = delta
        if best_index is None:
            groups.append([component])
        else:
            groups[best_index].append(component)

    out: list[dict[str, Any]] = []
    for group in groups:
        stats = row_group_stats(group)
        if not keep_outline_seed_group(group, stats, min_components=min_components, min_x_span=min_x_span):
            continue
        out.append({"seed_components": group, **stats})
    out.sort(key=lambda item: item["center_y"])
    return out


def component_fits_outline_group(
    component: dict[str, Any],
    group: dict[str, Any],
    *,
    attach_y_pad_px: float,
    detached_mark_max_height_px: float,
) -> bool:
    x0, y0, x1, y1 = component_bbox_edges(component)
    _, center_y = component_center(component)
    top = float(group["top"]) - attach_y_pad_px
    bottom = float(group["bottom"]) + attach_y_pad_px
    height = y1 - y0
    fully_captured = y0 >= top and y1 <= bottom
    detached_overlap = (
        (
            component.get("is_dot_like")
            or component.get("is_thin_horizontal_mark")
            or component_is_horizontal_rule_like(component)
            or height <= detached_mark_max_height_px
        )
        and y0 <= bottom
        and y1 >= top
    )
    center_captured = top <= center_y <= bottom
    return fully_captured or detached_overlap or center_captured


def assign_components_to_outline_groups(
    eligible: list[dict[str, Any]],
    groups: list[dict[str, Any]],
    *,
    attach_y_pad_px: float,
    detached_mark_max_height_px: float,
    mark_attach_x_gap_px: float,
) -> list[set[int]]:
    assignments = [set(int(component["id"]) for component in group["seed_components"]) for group in groups]
    for component in eligible:
        component_id = int(component["id"])
        x0, y0, x1, y1 = component_bbox_edges(component)
        _, center_y = component_center(component)
        component_height = y1 - y0
        mark_like = bool(
            not component.get("is_dot_like")
            and (
                component.get("is_thin_horizontal_mark")
                or component_is_horizontal_rule_like(component)
                or component_height <= detached_mark_max_height_px
            )
        )
        best_index: int | None = None
        best_delta: float | None = None
        for index, group in enumerate(groups):
            fits_group = component_fits_outline_group(
                component,
                group,
                attach_y_pad_px=attach_y_pad_px,
                detached_mark_max_height_px=detached_mark_max_height_px,
            )
            if mark_like:
                group_center = float(group["center_y"])
                group_top = float(group["top"])
                group_bottom = float(group["bottom"])
                if center_y > group_center + max(2.0, attach_y_pad_px * 0.25) and y0 > group_center:
                    if not component_is_box_bottom_rule_for_group(component, group):
                        continue
                above_target_gap = max(0.0, group_top - y1)
                above_target = center_y <= group_center and above_target_gap <= max(26.0, attach_y_pad_px + 18.0)
                if not (fits_group or above_target):
                    continue
                seed_gaps = [
                    interval_gap(x0, x1, *component_bbox_edges(seed_component)[0::2])
                    for seed_component in group.get("seed_components", [])
                ]
                horizontal_gap = min(seed_gaps) if seed_gaps else interval_gap(x0, x1, float(group["x0"]), float(group["x1"]))
                gap_limit = mark_attach_x_gap_px
                if y0 <= group_bottom + attach_y_pad_px and y1 >= group_top - max(attach_y_pad_px, 18.0):
                    gap_limit = max(gap_limit, mark_attach_x_gap_px + 18.0)
                if horizontal_gap > gap_limit:
                    continue
                delta = above_target_gap + abs(center_y - group_center) * 0.10 + horizontal_gap * 0.45
            else:
                if not fits_group:
                    continue
                delta = abs(center_y - float(group["center_y"]))
            if best_delta is None or delta < best_delta:
                best_index = index
                best_delta = delta
        if best_index is not None:
            assignments[best_index].add(component_id)
    return assignments


def normal_inlier_mask(values: np.ndarray, *, sigma: float, iterations: int = 2) -> np.ndarray:
    if values.size == 0:
        return np.zeros(0, dtype=bool)
    valid = np.ones(values.shape, dtype=bool)
    for _ in range(iterations):
        sample = values[valid]
        if sample.size < 4:
            break
        mean = float(np.mean(sample))
        std = float(np.std(sample))
        if std < 0.35:
            break
        valid &= np.abs(values - mean) <= sigma * std
    return valid


def split_column_runs(xs: np.ndarray, *, max_gap: int) -> list[np.ndarray]:
    if xs.size == 0:
        return []
    runs: list[list[int]] = [[int(xs[0])]]
    for value in xs[1:]:
        int_value = int(value)
        if int_value - runs[-1][-1] <= max_gap:
            runs[-1].append(int_value)
        else:
            runs.append([int_value])
    return [np.asarray(run, dtype=np.int32) for run in runs]


def interval_gap(a0: float, a1: float, b0: float, b1: float) -> float:
    if a1 < b0:
        return b0 - a1
    if b1 < a0:
        return a0 - b1
    return 0.0


def attach_dot_rows_to_outline_assignments(
    eligible_by_id: dict[int, dict[str, Any]],
    groups: list[dict[str, Any]],
    assignments: list[set[int]],
    dot_row_items: list[dict[str, Any]],
    *,
    attach_y_pad_px: float,
    dot_row_attach_px: float,
    bridge_gap_px: float,
) -> None:
    already_assigned: set[int] = set().union(*assignments) if assignments else set()
    for dot_row in dot_row_items:
        dot_ids = [int(item_id) for item_id in dot_row.get("component_ids", [])]
        unassigned_ids = [item_id for item_id in dot_ids if item_id in eligible_by_id and item_id not in already_assigned]
        if not unassigned_ids:
            continue
        touched = [eligible_by_id[item_id] for item_id in unassigned_ids]
        dot_x0 = min(float(item["bbox"][0]) for item in touched)
        dot_y0 = min(float(item["bbox"][1]) for item in touched)
        dot_x1 = max(float(item["bbox"][0]) + float(item["bbox"][2]) for item in touched)
        dot_y1 = max(float(item["bbox"][1]) + float(item["bbox"][3]) for item in touched)
        dot_center_y = float(dot_row.get("center_y", (dot_y0 + dot_y1) / 2.0))

        best_index: int | None = None
        best_score: float | None = None
        for index, group in enumerate(groups):
            group_top = float(group["top"]) - attach_y_pad_px
            group_bottom = float(group["bottom"]) + attach_y_pad_px
            vertical_gap = interval_gap(dot_y0, dot_y1, group_top, group_bottom)
            center_delta = abs(dot_center_y - float(group["center_y"]))
            center_inside = group_top <= dot_center_y <= group_bottom
            if not center_inside and center_delta > dot_row_attach_px:
                continue
            horizontal_gap = interval_gap(dot_x0, dot_x1, float(group["x0"]), float(group["x1"]))
            if horizontal_gap > bridge_gap_px:
                continue
            score = center_delta + horizontal_gap * 0.25 + vertical_gap * 0.5
            if best_score is None or score < best_score:
                best_index = index
                best_score = score
        if best_index is not None:
            assignments[best_index].update(unassigned_ids)
            already_assigned.update(unassigned_ids)


def attach_apparatus_side_markers_to_outline_assignments(
    eligible_by_id: dict[int, dict[str, Any]],
    groups: list[dict[str, Any]],
    assignments: list[set[int]],
) -> None:
    already_assigned: set[int] = set().union(*assignments) if assignments else set()
    for component in eligible_by_id.values():
        component_id = int(component["id"])
        if component_id in already_assigned:
            continue
        if not component_is_leading_side_marker_like(component):
            continue
        x0, y0, x1, y1 = component_bbox_edges(component)
        best_index: int | None = None
        best_score: float | None = None
        for index, group in enumerate(groups):
            gx0 = float(group["x0"])
            gx1 = float(group["x1"])
            group_width = gx1 - gx0
            if group_width > 340.0 or len(group.get("seed_components", [])) > 24:
                continue
            if x1 > gx0 + 8.0:
                continue
            x_gap = interval_gap(x0, x1, gx0, gx1)
            if x_gap > 78.0:
                continue
            gy0 = float(group["top"])
            gy1 = float(group["bottom"])
            y_gap = interval_gap(y0, y1, gy0, gy1)
            if y_gap > 18.0:
                continue
            score = x_gap + y_gap * 2.0 + abs(((y0 + y1) / 2.0) - float(group["center_y"])) * 0.05
            if best_score is None or score < best_score:
                best_index = index
                best_score = score
        if best_index is not None:
            assignments[best_index].add(component_id)
            already_assigned.add(component_id)


def attach_side_marker_continuations_to_assignments(
    eligible_by_id: dict[int, dict[str, Any]],
    assignments: list[set[int]],
) -> None:
    already_assigned: set[int] = set().union(*assignments) if assignments else set()
    for component in eligible_by_id.values():
        component_id = int(component["id"])
        if component_id in already_assigned:
            continue
        if not component_is_side_marker_continuation_like(component):
            continue
        x0, y0, x1, y1 = component_bbox_edges(component)
        best_index: int | None = None
        best_score: float | None = None
        for index, component_ids in enumerate(assignments):
            marker_components = [
                eligible_by_id[item_id]
                for item_id in component_ids
                if item_id in eligible_by_id and component_is_side_marker_continuation_like(eligible_by_id[item_id])
            ]
            for marker in marker_components:
                mx0, my0, mx1, my1 = component_bbox_edges(marker)
                x_gap = interval_gap(x0, x1, mx0, mx1)
                y_gap = interval_gap(y0, y1, my0, my1)
                if x_gap > 10.0 or y_gap > 12.0:
                    continue
                score = x_gap * 2.0 + y_gap + abs(((x0 + x1) / 2.0) - ((mx0 + mx1) / 2.0)) * 0.25
                if best_score is None or score < best_score:
                    best_index = index
                    best_score = score
        if best_index is not None:
            assignments[best_index].add(component_id)
            already_assigned.add(component_id)


def prune_isolated_fringe_dot_assignments(
    eligible_by_id: dict[int, dict[str, Any]],
    assignments: list[set[int]],
) -> None:
    for component_ids in assignments:
        touched = [eligible_by_id[item_id] for item_id in component_ids if item_id in eligible_by_id]
        non_dot_components = [
            item for item in touched
            if not item.get("is_dot_like")
            and not item.get("is_thin_horizontal_mark")
            and not component_is_horizontal_rule_like(item)
            and not component_is_row_side_marker_like(item)
        ]
        if len(non_dot_components) < 2:
            continue
        non_dot_x0 = min(component_bbox_edges(item)[0] for item in non_dot_components)
        non_dot_x1 = max(component_bbox_edges(item)[2] for item in non_dot_components)
        dot_components = [item for item in touched if item.get("is_dot_like")]
        for dot in dot_components:
            dot_id = int(dot["id"])
            x0, y0, x1, y1 = component_bbox_edges(dot)
            width = x1 - x0
            height = y1 - y0
            area = float(dot.get("area_px", 0.0))
            if area > 40.0 or width > 7.0 or height > 7.0:
                continue
            center_x, center_y = component_center(dot)
            if center_x < non_dot_x0:
                fringe_gap = non_dot_x0 - center_x
            elif center_x > non_dot_x1:
                fringe_gap = center_x - non_dot_x1
            else:
                continue
            if fringe_gap <= 70.0:
                continue
            nearby_dot = False
            for other in dot_components:
                other_id = int(other["id"])
                if other_id == dot_id:
                    continue
                other_center_x, other_center_y = component_center(other)
                if abs(other_center_x - center_x) <= 28.0 and abs(other_center_y - center_y) <= 8.0:
                    nearby_dot = True
                    break
            if not nearby_dot:
                component_ids.discard(dot_id)


def baseline_anchor_points(
    components: list[dict[str, Any]],
    *,
    baseline_percent: float,
    min_height_px: float,
) -> list[dict[str, Any]]:
    anchors: list[dict[str, Any]] = []
    for component in components:
        if component_is_excluded(component) or component.get("edge", {}).get("is_edge_artifact"):
            continue
        x0, y0, x1, y1 = component_bbox_edges(component)
        width = x1 - x0
        height = y1 - y0
        if width <= 0.0 or height <= 0.0:
            continue
        center_x = (x0 + x1) / 2.0
        if component.get("is_dot_like"):
            centroid = component.get("centroid") or [center_x, (y0 + y1) / 2.0]
            baseline_y = float(centroid[1])
            kind = "lacuna_dot"
        elif component.get("is_thin_horizontal_mark") or component_is_horizontal_rule_like(component):
            continue
        elif component_is_row_side_marker_like(component):
            continue
        else:
            area = float(component.get("area_px", 0.0))
            if height < min_height_px or area < 10.0:
                continue
            baseline_y = y0 + float(baseline_percent) * height
            kind = "main_text"
        anchors.append(
            {
                "component_id": int(component["id"]),
                "x": center_x,
                "y": baseline_y,
                "x0": x0,
                "x1": x1,
                "kind": kind,
            }
        )
    anchors.sort(key=lambda item: (float(item["x"]), float(item["y"])))
    return anchors


def robust_linear_baseline(anchors: list[dict[str, Any]], *, sigma: float) -> tuple[float, float, np.ndarray]:
    xs = np.asarray([float(anchor["x"]) for anchor in anchors], dtype=np.float32)
    ys = np.asarray([float(anchor["y"]) for anchor in anchors], dtype=np.float32)
    if xs.size == 0:
        return 0.0, 0.0, np.zeros(0, dtype=bool)
    if xs.size == 1 or float(xs.max() - xs.min()) < 4.0:
        return 0.0, float(np.median(ys)), np.ones(xs.shape, dtype=bool)

    valid = np.ones(xs.shape, dtype=bool)
    dot_anchor = np.asarray([anchor["kind"] == "lacuna_dot" for anchor in anchors], dtype=bool)
    slope = 0.0
    intercept = float(np.median(ys))
    for _ in range(3):
        sample_x = xs[valid]
        sample_y = ys[valid]
        if sample_x.size < 2 or float(sample_x.max() - sample_x.min()) < 4.0:
            break
        slope, intercept = [float(value) for value in np.polyfit(sample_x, sample_y, 1)]
        residuals = ys - (slope * xs + intercept)
        sample_residuals = residuals[valid]
        std = float(np.std(sample_residuals))
        if std < 0.75:
            break
        limit = max(5.0, float(sigma) * std)
        next_valid = (np.abs(residuals) <= limit) | dot_anchor
        if int(next_valid.sum()) < max(2, int(0.55 * valid.size)):
            break
        if np.array_equal(next_valid, valid):
            break
        valid = next_valid
    return slope, intercept, valid


def anchor_runs(
    anchors: list[dict[str, Any]],
    *,
    max_gap_px: float,
    min_segment_width_px: float,
) -> list[tuple[float, float]]:
    if not anchors:
        return []
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_right: float | None = None
    for anchor in sorted(anchors, key=lambda item: (float(item["x0"]), float(item["x1"]))):
        x0 = float(anchor["x0"])
        x1 = float(anchor["x1"])
        if current and current_right is not None and x0 - current_right > max_gap_px:
            groups.append(current)
            current = [anchor]
            current_right = x1
            continue
        current.append(anchor)
        current_right = x1 if current_right is None else max(current_right, x1)
    if current:
        groups.append(current)

    runs: list[tuple[float, float]] = []
    for group in groups:
        x0 = min(float(anchor["x0"]) for anchor in group)
        x1 = max(float(anchor["x1"]) for anchor in group)
        group_is_dot_only = all(anchor["kind"] == "lacuna_dot" for anchor in group)
        min_width = 1.0 if group_is_dot_only else min_segment_width_px
        if x1 - x0 >= min_width:
            runs.append((x0, x1))
    return runs


def row_baseline_polylines_from_components(
    components: list[dict[str, Any]],
    component_ids: set[int],
    *,
    image_width: int,
    baseline_percent: float,
    sigma: float,
    max_gap_px: float,
    sample_step_px: float,
    min_segment_width_px: float,
    min_height_px: float,
) -> tuple[list[list[list[float]]], float, str]:
    touched = [component for component in components if int(component["id"]) in component_ids]
    anchors = baseline_anchor_points(
        touched,
        baseline_percent=baseline_percent,
        min_height_px=min_height_px,
    )
    if not anchors:
        return [], 0.0, "empty_component_baseline"

    slope, intercept, valid = robust_linear_baseline(anchors, sigma=sigma)
    valid_anchors = [anchor for anchor, is_valid in zip(anchors, valid) if bool(is_valid)]
    if not valid_anchors:
        valid_anchors = anchors
    runs = anchor_runs(
        anchors,
        max_gap_px=max_gap_px,
        min_segment_width_px=min_segment_width_px,
    )
    polylines: list[list[list[float]]] = []
    sample_step = max(24.0, float(sample_step_px))
    for run_x0, run_x1 in runs:
        segment_left = max(0.0, run_x0)
        segment_right = min(float(image_width), run_x1)
        if segment_right - segment_left < 1.0:
            continue
        sample_xs = [segment_left]
        next_x = segment_left + sample_step
        while next_x < segment_right - 1.0:
            sample_xs.append(next_x)
            next_x += sample_step
        sample_xs.append(segment_right)
        polyline = [[round(x, 2), round(slope * x + intercept, 2)] for x in sample_xs]
        polylines.append(polyline)

    if not polylines:
        return [], 0.0, "component_baseline_filtered_empty"
    all_y = [point[1] for polyline in polylines for point in polyline]
    source = "smoothed_component_baseline"
    if any(anchor["kind"] == "lacuna_dot" for anchor in valid_anchors):
        source += "+lacuna_points"
    return polylines, round(float(np.median(np.asarray(all_y, dtype=np.float32))), 2), source


def unassigned_chapter_marker_groups(
    eligible_by_id: dict[int, dict[str, Any]],
    assigned_component_ids: set[int],
    rows: list[dict[str, Any]],
    *,
    image_width: int,
) -> list[set[int]]:
    def is_standalone_chapter_glyph(component: dict[str, Any]) -> bool:
        x0, y0, x1, y1 = component_bbox_edges(component)
        width = x1 - x0
        height = y1 - y0
        area = float(component.get("area_px", 0.0))
        center_x = (x0 + x1) / 2.0
        return (
            width >= 8.0
            and width <= 45.0
            and height >= 8.0
            and height <= 34.0
            and area >= 80.0
            and area <= 650.0
            and center_x >= float(image_width) * 0.12
            and center_x <= float(image_width) * 0.88
        )

    candidates = []
    for component in eligible_by_id.values():
        component_id = int(component["id"])
        if component_id in assigned_component_ids:
            continue
        is_horizontal_marker = bool(component.get("is_thin_horizontal_mark") or component_is_horizontal_rule_like(component))
        if component.get("is_dot_like") and not is_horizontal_marker:
            continue
        if component_is_excluded(component):
            continue
        x0, y0, x1, y1 = component_bbox_edges(component)
        width = x1 - x0
        height = y1 - y0
        area = float(component.get("area_px", 0.0))
        if width < 4.0 or height < 4.0 or area < 20.0:
            continue
        candidates.append(component)

    groups: list[list[dict[str, Any]]] = []
    for component in sorted(candidates, key=lambda item: (float(item["bbox"][1]), float(item["bbox"][0]))):
        x0, y0, x1, y1 = component_bbox_edges(component)
        best_index: int | None = None
        best_gap: float | None = None
        for index, group in enumerate(groups):
            gx0 = min(component_bbox_edges(item)[0] for item in group)
            gy0 = min(component_bbox_edges(item)[1] for item in group)
            gx1 = max(component_bbox_edges(item)[2] for item in group)
            gy1 = max(component_bbox_edges(item)[3] for item in group)
            x_gap = interval_gap(x0, x1, gx0, gx1)
            y_gap = interval_gap(y0, y1, gy0, gy1)
            if x_gap <= 32.0 and y_gap <= 14.0:
                score = x_gap + y_gap * 2.0
                if best_gap is None or score < best_gap:
                    best_index = index
                    best_gap = score
        if best_index is None:
            groups.append([component])
        else:
            groups[best_index].append(component)

    out: list[set[int]] = []
    for group in groups:
        gx0 = min(component_bbox_edges(item)[0] for item in group)
        gy0 = min(component_bbox_edges(item)[1] for item in group)
        gx1 = max(component_bbox_edges(item)[2] for item in group)
        gy1 = max(component_bbox_edges(item)[3] for item in group)
        group_width = gx1 - gx0
        group_height = gy1 - gy0
        if group_width > 125.0 or group_height > 62.0 or len(group) > 6:
            continue
        total_area = sum(float(item.get("area_px", 0.0)) for item in group)
        has_rule = any(item.get("is_thin_horizontal_mark") or component_is_horizontal_rule_like(item) for item in group)
        has_standalone_chapter_glyph = any(is_standalone_chapter_glyph(item) for item in group)
        if total_area < 80.0 or not (has_rule or has_standalone_chapter_glyph):
            continue
        if has_standalone_chapter_glyph and not has_rule:
            if len(group) > 2 or group_width > 55.0 or group_height > 48.0:
                continue

        group_center_x = (gx0 + gx1) / 2.0
        supported_below = False
        for row in rows:
            rx0, ry0, rwidth, rheight = [float(value) for value in row["bbox"]]
            rx1 = rx0 + rwidth
            row_gap = ry0 - gy1
            row_width = rx1 - rx0
            if row_gap < -8.0 or row_gap > 90.0:
                continue
            if row_width > float(image_width) * 0.78:
                continue
            if rx0 - 80.0 <= group_center_x <= rx1 + 80.0:
                supported_below = True
                break
        if supported_below:
            out.append(set(int(item["id"]) for item in group))
    return out


def unassigned_word_like_groups(
    eligible_by_id: dict[int, dict[str, Any]],
    assigned_component_ids: set[int],
) -> list[set[int]]:
    candidates: list[dict[str, Any]] = []
    horizontal_mark_candidates: list[dict[str, Any]] = []
    side_marker_candidates: list[dict[str, Any]] = []
    dot_fragment_candidates: list[dict[str, Any]] = []
    for component in eligible_by_id.values():
        component_id = int(component["id"])
        if component_id in assigned_component_ids:
            continue
        if component_is_excluded(component):
            continue
        x0, y0, x1, y1 = component_bbox_edges(component)
        width = x1 - x0
        height = y1 - y0
        area = float(component.get("area_px", 0.0))
        if component.get("is_dot_like"):
            if width >= 6.0 and height >= 8.0 and area >= 55.0:
                dot_fragment_candidates.append(component)
            continue
        if component.get("is_thin_horizontal_mark") or component_is_horizontal_rule_like(component):
            if width >= 12.0 and height <= 8.5 and area >= 30.0:
                horizontal_mark_candidates.append(component)
            continue
        if component_is_leading_side_marker_like(component):
            side_marker_candidates.append(component)
            continue
        if width < 3.0 or height < 6.0 or width > 64.0 or height > 32.0:
            continue
        if area < 24.0 or area > 850.0:
            continue
        candidates.append(component)

    groups: list[list[dict[str, Any]]] = []
    for component in sorted(candidates, key=lambda item: (component_center(item)[1], component_bbox_edges(item)[0])):
        x0, y0, x1, y1 = component_bbox_edges(component)
        _, center_y = component_center(component)
        best_index: int | None = None
        best_score: float | None = None
        for index, group in enumerate(groups):
            gx0 = min(component_bbox_edges(item)[0] for item in group)
            gy0 = min(component_bbox_edges(item)[1] for item in group)
            gx1 = max(component_bbox_edges(item)[2] for item in group)
            gy1 = max(component_bbox_edges(item)[3] for item in group)
            group_center_y = robust_center([component_center(item)[1] for item in group])
            x_gap = interval_gap(x0, x1, gx0, gx1)
            y_gap = interval_gap(y0, y1, gy0, gy1)
            if abs(center_y - group_center_y) > 9.5 or y_gap > 8.0 or x_gap > 24.0:
                continue
            score = x_gap + abs(center_y - group_center_y) * 2.0
            if best_score is None or score < best_score:
                best_index = index
                best_score = score
        if best_index is None:
            groups.append([component])
        else:
            groups[best_index].append(component)

    for group in groups:
        gx0 = min(component_bbox_edges(item)[0] for item in group)
        gy0 = min(component_bbox_edges(item)[1] for item in group)
        gx1 = max(component_bbox_edges(item)[2] for item in group)
        gy1 = max(component_bbox_edges(item)[3] for item in group)
        for marker in horizontal_mark_candidates:
            mx0, my0, mx1, my1 = component_bbox_edges(marker)
            x_gap = interval_gap(mx0, mx1, gx0, gx1)
            marker_above_gap = gy0 - my1
            marker_inside_top = my0 >= gy0 - 22.0 and my1 <= gy1
            if x_gap <= 18.0 and ((0.0 <= marker_above_gap <= 18.0) or marker_inside_top):
                group.append(marker)

    for group in groups:
        gx0 = min(component_bbox_edges(item)[0] for item in group)
        gy0 = min(component_bbox_edges(item)[1] for item in group)
        gx1 = max(component_bbox_edges(item)[2] for item in group)
        gy1 = max(component_bbox_edges(item)[3] for item in group)
        if gx1 - gx0 > 340.0 or len(group) > 24:
            continue
        for marker in side_marker_candidates:
            mx0, my0, mx1, my1 = component_bbox_edges(marker)
            if mx1 > gx0 + 8.0:
                continue
            if interval_gap(mx0, mx1, gx0, gx1) > 78.0:
                continue
            if interval_gap(my0, my1, gy0, gy1) <= 18.0:
                group.append(marker)

    used_dot_fragment_ids: set[int] = set()
    for group in groups:
        gx0 = min(component_bbox_edges(item)[0] for item in group)
        gy0 = min(component_bbox_edges(item)[1] for item in group)
        gx1 = max(component_bbox_edges(item)[2] for item in group)
        gy1 = max(component_bbox_edges(item)[3] for item in group)
        for dot_fragment in dot_fragment_candidates:
            dot_fragment_id = int(dot_fragment["id"])
            if dot_fragment_id in used_dot_fragment_ids:
                continue
            dx0, dy0, dx1, dy1 = component_bbox_edges(dot_fragment)
            if interval_gap(dy0, dy1, gy0, gy1) > 4.0:
                continue
            if interval_gap(dx0, dx1, gx0, gx1) > 18.0:
                continue
            group.append(dot_fragment)
            used_dot_fragment_ids.add(dot_fragment_id)
            gx0 = min(gx0, dx0)
            gy0 = min(gy0, dy0)
            gx1 = max(gx1, dx1)
            gy1 = max(gy1, dy1)

    out: list[set[int]] = []
    for group in groups:
        gx0 = min(component_bbox_edges(item)[0] for item in group)
        gy0 = min(component_bbox_edges(item)[1] for item in group)
        gx1 = max(component_bbox_edges(item)[2] for item in group)
        gy1 = max(component_bbox_edges(item)[3] for item in group)
        group_width = gx1 - gx0
        group_height = gy1 - gy0
        total_area = sum(float(item.get("area_px", 0.0)) for item in group)
        if group_width > 210.0 or group_height > 38.0:
            continue
        if len(group) < 2 and group_width < 24.0:
            continue
        if total_area < 95.0:
            continue
        out.append(set(int(item["id"]) for item in group))
    return out


def row_cell_outline_geometry(
    touched: list[dict[str, Any]],
    *,
    image_width: int,
    image_height: int,
    scale: int,
    pad_px: float,
    include_leading_side_markers: bool = False,
) -> tuple[list[list[list[int]]], list[list[list[float]]], list[float], list[float]]:
    outline_items = touched if include_leading_side_markers else [item for item in touched if not component_is_row_side_marker_like(item)]
    if not outline_items:
        outline_items = touched
    x0 = max(0.0, min(float(item["bbox"][0]) for item in outline_items) - pad_px)
    x1 = min(float(image_width), max(float(item["bbox"][0]) + float(item["bbox"][2]) for item in outline_items) + pad_px)
    y0 = max(0.0, min(float(item["bbox"][1]) for item in outline_items) - pad_px)
    y1 = min(float(image_height), max(float(item["bbox"][1]) + float(item["bbox"][3]) for item in outline_items) + pad_px)
    if y1 - y0 < 10.0:
        center_y = (y0 + y1) / 2.0
        y0 = max(0.0, center_y - 5.0)
        y1 = min(float(image_height), center_y + 5.0)
    outline_original = [
        [round(x0, 2), round(y0, 2)],
        [round(x1, 2), round(y0, 2)],
        [round(x1, 2), round(y1, 2)],
        [round(x0, 2), round(y1, 2)],
    ]
    outline_scaled = [[int(round(x * scale)), int(round(y * scale))] for x, y in outline_original]
    return [outline_scaled], [outline_original], [round(x0, 2), round(x1, 2)], [round(x0, 2), round(y0, 2), round(x1 - x0, 2), round(y1 - y0, 2)]


def leading_bracket_like_outline_polygons(
    touched: list[dict[str, Any]],
    *,
    row_x0: float,
    scale: int,
) -> tuple[list[list[list[int]]], list[list[list[float]]]]:
    scaled: list[list[list[int]]] = []
    original: list[list[list[float]]] = []
    for component in touched:
        if component.get("is_dot_like") or component.get("is_thin_horizontal_mark") or component_is_horizontal_rule_like(component):
            continue
        x0, y0, x1, y1 = component_bbox_edges(component)
        width = x1 - x0
        height = y1 - y0
        leading = x0 <= row_x0 + 34.0 or x0 < 90.0
        slender_bracket = width <= 13.0 and height >= 20.0
        footed_bracket = width <= 28.0 and height >= 14.0 and height >= width * 0.75
        bracket_like = slender_bracket or footed_bracket
        if not (leading and bracket_like):
            continue
        polygon_scaled = [[int(point[0]), int(point[1])] for point in component["polygon_scaled"]]
        polygon_original = [[round(float(point[0]) / scale, 2), round(float(point[1]) / scale, 2)] for point in polygon_scaled]
        scaled.append(polygon_scaled)
        original.append(polygon_original)
    return scaled, original


def component_is_lacuna_row_bracket_like(component: dict[str, Any]) -> bool:
    if component.get("is_dot_like") or component.get("is_thin_horizontal_mark") or component_is_horizontal_rule_like(component):
        return False
    x0, y0, x1, y1 = component_bbox_edges(component)
    width = x1 - x0
    height = y1 - y0
    area = float(component.get("area_px", 0.0))
    return (
        5.0 <= width <= 32.0
        and 18.0 <= height <= 42.0
        and height >= width * 0.72
        and 70.0 <= area <= 700.0
    )


def standalone_dot_row_marker_component_ids(
    eligible_by_id: dict[int, dict[str, Any]],
    assigned_component_ids: set[int],
    dot_components: list[dict[str, Any]],
) -> set[int]:
    if not dot_components:
        return set()
    dot_x0 = min(float(item["bbox"][0]) for item in dot_components)
    dot_y0 = min(float(item["bbox"][1]) for item in dot_components)
    dot_x1 = max(float(item["bbox"][0]) + float(item["bbox"][2]) for item in dot_components)
    dot_y1 = max(float(item["bbox"][1]) + float(item["bbox"][3]) for item in dot_components)
    marker_ids: set[int] = set()
    for component_id, component in eligible_by_id.items():
        if component_id in assigned_component_ids:
            continue
        if not component_is_lacuna_row_bracket_like(component):
            continue
        x0, y0, x1, y1 = component_bbox_edges(component)
        y_gap = max(dot_y0 - y1, y0 - dot_y1, 0.0)
        if y_gap > 8.0:
            continue
        if x1 < dot_x0 - 42.0 or x0 > dot_x1 + 42.0:
            continue
        marker_ids.add(component_id)
    return marker_ids


def extend_baseline_polylines_to_x_span(
    baseline_polylines: list[list[list[float]]],
    row_x_span: list[float],
) -> None:
    if not baseline_polylines or not row_x_span:
        return
    left = round(float(row_x_span[0]), 2)
    right = round(float(row_x_span[1]), 2)
    if left < float(baseline_polylines[0][0][0]):
        baseline_polylines[0][0][0] = left
    if right > float(baseline_polylines[-1][-1][0]):
        baseline_polylines[-1][-1][0] = right


def standalone_dot_row_geometry(
    touched: list[dict[str, Any]],
    *,
    image_width: int,
    image_height: int,
    scale: int,
    pad_px: float,
    sigma: float,
) -> tuple[list[list[list[int]]], list[list[list[float]]], list[list[list[float]]], float, list[float], list[float]]:
    x0 = max(0.0, min(float(item["bbox"][0]) for item in touched) - pad_px)
    x1 = min(float(image_width), max(float(item["bbox"][0]) + float(item["bbox"][2]) for item in touched) + pad_px)
    y0 = max(0.0, min(float(item["bbox"][1]) for item in touched) - pad_px)
    y1 = min(float(image_height), max(float(item["bbox"][1]) + float(item["bbox"][3]) for item in touched) + pad_px)
    if y1 - y0 < 6.0:
        center_y = (y0 + y1) / 2.0
        y0 = max(0.0, center_y - 3.0)
        y1 = min(float(image_height), center_y + 3.0)

    outline_original = [
        [round(x0, 2), round(y0, 2)],
        [round(x1, 2), round(y0, 2)],
        [round(x1, 2), round(y1, 2)],
        [round(x0, 2), round(y1, 2)],
    ]
    outline_scaled = [[int(round(x * scale)), int(round(y * scale))] for x, y in outline_original]

    anchors = baseline_anchor_points(touched, baseline_percent=0.5, min_height_px=0.0)
    slope, intercept, _ = robust_linear_baseline(anchors, sigma=sigma)
    y_left = slope * x0 + intercept
    y_right = slope * x1 + intercept
    baseline_segments = [[[round(x0, 2), round(y_left, 2)], [round(x1, 2), round(y_right, 2)]]]
    baseline_y = round(float(np.median([y_left, y_right])), 2)
    return [outline_scaled], [outline_original], baseline_segments, baseline_y, [round(x0, 2), round(x1, 2)], [round(x0, 2), round(y0, 2), round(x1 - x0, 2), round(y1 - y0, 2)]


def build_outline_rows(
    components: list[dict[str, Any]],
    mask_shape: tuple[int, int],
    dot_row_items: list[dict[str, Any]],
    *,
    image_width: int,
    image_height: int,
    scale: int,
    min_components: int,
    min_x_span: float,
    outline_pad_px: int,
    outline_close_x_px: int,
    outline_close_y_px: int,
    seed_min_height_px: float,
    seed_min_area_px: float,
    seed_y_tolerance_px: float,
    attach_y_pad_px: float,
    detached_mark_max_height_px: float,
    dot_row_attach_px: float,
    baseline_percent: float,
    baseline_sigma: float,
    baseline_gap_px: float,
    baseline_sample_step_px: float,
    baseline_min_segment_width_px: float,
    baseline_min_height_px: float,
    standalone_dot_min_count: int,
    standalone_dot_pad_px: float,
) -> list[dict[str, Any]]:
    eligible = [component for component in components if not component_is_excluded(component)]
    eligible_by_id = {int(component["id"]): component for component in eligible}
    seed_components = [
        component for component in eligible
        if is_main_outline_seed(component, min_height_px=seed_min_height_px, min_area_px=seed_min_area_px)
    ]
    groups = outline_seed_groups(
        seed_components,
        seed_y_tolerance_px=seed_y_tolerance_px,
        min_components=min_components,
        min_x_span=min_x_span,
    )
    assignments = assign_components_to_outline_groups(
        eligible,
        groups,
        attach_y_pad_px=attach_y_pad_px,
        detached_mark_max_height_px=detached_mark_max_height_px,
        mark_attach_x_gap_px=baseline_gap_px,
    )
    attach_dot_rows_to_outline_assignments(
        eligible_by_id,
        groups,
        assignments,
        dot_row_items,
        attach_y_pad_px=attach_y_pad_px,
        dot_row_attach_px=dot_row_attach_px,
        bridge_gap_px=baseline_gap_px,
    )
    attach_apparatus_side_markers_to_outline_assignments(eligible_by_id, groups, assignments)
    attach_side_marker_continuations_to_assignments(eligible_by_id, assignments)
    prune_isolated_fringe_dot_assignments(eligible_by_id, assignments)

    rows: list[dict[str, Any]] = []
    assigned_component_ids: set[int] = set()
    for group, component_id_set in zip(groups, assignments):
        assigned_component_ids.update(component_id_set)
        touched = [eligible_by_id[item_id] for item_id in sorted(component_id_set) if item_id in eligible_by_id]
        if not touched:
            continue
        x0 = min(float(item["bbox"][0]) for item in touched)
        y0 = min(float(item["bbox"][1]) for item in touched)
        x1 = max(float(item["bbox"][0]) + float(item["bbox"][2]) for item in touched)
        y1 = max(float(item["bbox"][1]) + float(item["bbox"][3]) for item in touched)
        include_leading_side_markers = row_should_include_leading_side_markers(touched)
        outline_scaled, outline_original, row_x_span, row_bbox = row_cell_outline_geometry(
            touched,
            image_width=image_width,
            image_height=image_height,
            scale=scale,
            pad_px=outline_pad_px,
            include_leading_side_markers=include_leading_side_markers,
        )
        marker_scaled, marker_original = leading_bracket_like_outline_polygons(
            touched,
            row_x0=row_x_span[0],
            scale=scale,
        )
        if not outline_scaled:
            continue
        baseline_polylines, baseline_y, baseline_source = row_baseline_polylines_from_components(
            components,
            set(component_id_set),
            image_width=image_width,
            baseline_percent=baseline_percent,
            sigma=baseline_sigma,
            max_gap_px=baseline_gap_px,
            sample_step_px=baseline_sample_step_px,
            min_segment_width_px=baseline_min_segment_width_px,
            min_height_px=baseline_min_height_px,
        )
        if not baseline_polylines:
            fallback_y = robust_row_baseline_y(
                profile_y=float(group["center_y"]),
                text_anchors=touched,
                dot_anchors=[],
                bottom_percentile=72.0,
            )
            baseline_polylines = [[[round(max(0.0, x0), 2), fallback_y], [round(min(float(image_width), x1), 2), fallback_y]]]
            baseline_y = fallback_y
            baseline_source = "component_bottom_fallback"
        if include_leading_side_markers:
            extend_baseline_polylines_to_x_span(baseline_polylines, row_x_span)
        baseline_span = [baseline_polylines[0][0][0], baseline_polylines[-1][-1][0]]
        rows.append(
            {
                "ink_profile_y": round(float(group["center_y"]), 2),
                "median_line_y": round(float(group["center_y"]), 2),
                "median_line_segments": baseline_polylines,
                "median_line_segment_count": len(baseline_polylines),
                "median_line_span": baseline_span,
                "median_line_span_source": baseline_source,
                "baseline_y": baseline_y,
                "baseline_span": baseline_span,
                "baseline_span_source": baseline_source,
                "baseline_segments": baseline_polylines,
                "baseline": baseline_polylines[0],
                "row_cell_y": [row_bbox[1], round(row_bbox[1] + row_bbox[3], 2)],
                "source": "outline_first",
                "score": len(touched),
                "component_ids": sorted(int(item) for item in component_id_set),
                "component_count": len(touched),
                "dot_like_component_count": sum(1 for item in touched if item.get("is_dot_like")),
                "x_span": row_x_span,
                "bbox": row_bbox,
                "outline_polygons_scaled": outline_scaled,
                "outline_polygons": outline_original,
                "outline_polygon_count": len(outline_scaled),
                "attached_marker_polygons_scaled": marker_scaled,
                "attached_marker_polygons": marker_original,
                "attached_marker_polygon_count": len(marker_scaled),
                "outline_seed_component_count": len(group["seed_components"]),
            }
        )

    for component_id_set in unassigned_chapter_marker_groups(
        eligible_by_id,
        assigned_component_ids,
        rows,
        image_width=image_width,
    ):
        touched = [eligible_by_id[item_id] for item_id in sorted(component_id_set) if item_id in eligible_by_id]
        if not touched:
            continue
        assigned_component_ids.update(component_id_set)
        x0 = min(float(item["bbox"][0]) for item in touched)
        y0 = min(float(item["bbox"][1]) for item in touched)
        x1 = max(float(item["bbox"][0]) + float(item["bbox"][2]) for item in touched)
        y1 = max(float(item["bbox"][1]) + float(item["bbox"][3]) for item in touched)
        include_leading_side_markers = row_should_include_leading_side_markers(touched)
        outline_scaled, outline_original, row_x_span, row_bbox = row_cell_outline_geometry(
            touched,
            image_width=image_width,
            image_height=image_height,
            scale=scale,
            pad_px=outline_pad_px,
            include_leading_side_markers=include_leading_side_markers,
        )
        if not outline_scaled:
            continue
        baseline_y = robust_row_baseline_y(
            profile_y=(y0 + y1) / 2.0,
            text_anchors=touched,
            dot_anchors=[],
            bottom_percentile=72.0,
        )
        baseline_segments = [[[round(x0, 2), baseline_y], [round(x1, 2), baseline_y]]]
        rows.append(
            {
                "ink_profile_y": round((y0 + y1) / 2.0, 2),
                "median_line_y": round((y0 + y1) / 2.0, 2),
                "median_line_segments": baseline_segments,
                "median_line_segment_count": 1,
                "median_line_span": [round(x0, 2), round(x1, 2)],
                "median_line_span_source": "chapter_marker_row",
                "baseline_y": baseline_y,
                "baseline_span": [round(x0, 2), round(x1, 2)],
                "baseline_span_source": "chapter_marker_row",
                "baseline_segments": baseline_segments,
                "baseline": baseline_segments[0],
                "row_cell_y": [row_bbox[1], round(row_bbox[1] + row_bbox[3], 2)],
                "source": "chapter_marker_row",
                "score": len(touched),
                "component_ids": sorted(component_id_set),
                "component_count": len(touched),
                "dot_like_component_count": sum(1 for item in touched if item.get("is_dot_like")),
                "x_span": row_x_span,
                "bbox": row_bbox,
                "outline_polygons_scaled": outline_scaled,
                "outline_polygons": outline_original,
                "outline_polygon_count": len(outline_scaled),
                "attached_marker_polygons_scaled": [],
                "attached_marker_polygons": [],
                "attached_marker_polygon_count": 0,
                "outline_seed_component_count": 0,
            }
        )

    for component_id_set in unassigned_word_like_groups(eligible_by_id, assigned_component_ids):
        touched = [eligible_by_id[item_id] for item_id in sorted(component_id_set) if item_id in eligible_by_id]
        if not touched:
            continue
        assigned_component_ids.update(component_id_set)
        x0 = min(float(item["bbox"][0]) for item in touched)
        y0 = min(float(item["bbox"][1]) for item in touched)
        x1 = max(float(item["bbox"][0]) + float(item["bbox"][2]) for item in touched)
        y1 = max(float(item["bbox"][1]) + float(item["bbox"][3]) for item in touched)
        include_leading_side_markers = row_should_include_leading_side_markers(touched)
        outline_scaled, outline_original, row_x_span, row_bbox = row_cell_outline_geometry(
            touched,
            image_width=image_width,
            image_height=image_height,
            scale=scale,
            pad_px=outline_pad_px,
            include_leading_side_markers=include_leading_side_markers,
        )
        if not outline_scaled:
            continue
        baseline_polylines, baseline_y, baseline_source = row_baseline_polylines_from_components(
            components,
            set(component_id_set),
            image_width=image_width,
            baseline_percent=baseline_percent,
            sigma=baseline_sigma,
            max_gap_px=baseline_gap_px,
            sample_step_px=baseline_sample_step_px,
            min_segment_width_px=baseline_min_segment_width_px,
            min_height_px=0.0,
        )
        if not baseline_polylines:
            baseline_y = robust_row_baseline_y(
                profile_y=(y0 + y1) / 2.0,
                text_anchors=touched,
                dot_anchors=[],
                bottom_percentile=72.0,
            )
            baseline_polylines = [[[round(x0, 2), baseline_y], [round(x1, 2), baseline_y]]]
            baseline_source = "word_like_row_fallback"
        if include_leading_side_markers:
            extend_baseline_polylines_to_x_span(baseline_polylines, row_x_span)
        baseline_span = [baseline_polylines[0][0][0], baseline_polylines[-1][-1][0]]
        rows.append(
            {
                "ink_profile_y": round((y0 + y1) / 2.0, 2),
                "median_line_y": round((y0 + y1) / 2.0, 2),
                "median_line_segments": baseline_polylines,
                "median_line_segment_count": len(baseline_polylines),
                "median_line_span": baseline_span,
                "median_line_span_source": baseline_source,
                "baseline_y": baseline_y,
                "baseline_span": baseline_span,
                "baseline_span_source": baseline_source,
                "baseline_segments": baseline_polylines,
                "baseline": baseline_polylines[0],
                "row_cell_y": [row_bbox[1], round(row_bbox[1] + row_bbox[3], 2)],
                "source": "word_like_row",
                "score": len(touched),
                "component_ids": sorted(component_id_set),
                "component_count": len(touched),
                "dot_like_component_count": sum(1 for item in touched if item.get("is_dot_like")),
                "x_span": row_x_span,
                "bbox": row_bbox,
                "outline_polygons_scaled": outline_scaled,
                "outline_polygons": outline_original,
                "outline_polygon_count": len(outline_scaled),
                "attached_marker_polygons_scaled": [],
                "attached_marker_polygons": [],
                "attached_marker_polygon_count": 0,
                "outline_seed_component_count": 0,
            }
        )

    for dot_row in dot_row_items:
        dot_ids = [int(item_id) for item_id in dot_row.get("component_ids", [])]
        unassigned_ids = [item_id for item_id in dot_ids if item_id in eligible_by_id and item_id not in assigned_component_ids]
        if len(unassigned_ids) < standalone_dot_min_count:
            continue
        component_id_set = set(unassigned_ids)
        touched = [eligible_by_id[item_id] for item_id in sorted(component_id_set)]
        if not touched:
            continue
        marker_ids = standalone_dot_row_marker_component_ids(
            eligible_by_id,
            assigned_component_ids | component_id_set,
            touched,
        )
        if marker_ids:
            component_id_set.update(marker_ids)
            touched = [eligible_by_id[item_id] for item_id in sorted(component_id_set)]
        outline_scaled, outline_original, baseline_segments, baseline_y, row_x_span, row_bbox = standalone_dot_row_geometry(
            touched,
            image_width=image_width,
            image_height=image_height,
            scale=scale,
            pad_px=max(float(outline_pad_px), float(standalone_dot_pad_px)),
            sigma=baseline_sigma,
        )
        if not outline_scaled:
            continue
        baseline_span = [baseline_segments[0][0][0], baseline_segments[-1][1][0]]
        rows.append(
            {
                "ink_profile_y": baseline_y,
                "median_line_y": baseline_y,
                "median_line_segments": baseline_segments,
                "median_line_segment_count": len(baseline_segments),
                "median_line_span": baseline_span,
                "median_line_span_source": "standalone_dot_row",
                "baseline_y": baseline_y,
                "baseline_span": baseline_span,
                "baseline_span_source": "standalone_dot_row",
                "baseline_segments": baseline_segments,
                "baseline": baseline_segments[0],
                "row_cell_y": [row_bbox[1], round(row_bbox[1] + row_bbox[3], 2)],
                "source": "standalone_dot_row",
                "score": len(touched),
                "component_ids": sorted(component_id_set),
                "component_count": len(touched),
                "dot_like_component_count": sum(1 for item in touched if item.get("is_dot_like")),
                "x_span": row_x_span,
                "bbox": row_bbox,
                "outline_polygons_scaled": outline_scaled,
                "outline_polygons": outline_original,
                "outline_polygon_count": len(outline_scaled),
                "attached_marker_polygons_scaled": [],
                "attached_marker_polygons": [],
                "attached_marker_polygon_count": 0,
                "outline_seed_component_count": 0,
            }
        )

    rows.sort(key=lambda item: (float(item["median_line_y"]), float(item["x_span"][0])))
    for index, row in enumerate(rows, start=1):
        row["index"] = index
    return rows


def line_segments_from_components(
    components: list[dict[str, Any]],
    line_y: float,
    *,
    image_width: int,
    gap_px: float,
    pad_px: float,
    min_segment_width_px: float,
) -> list[list[list[float]]]:
    segments: list[list[list[float]]] = []
    ordered = sorted(components, key=lambda item: (float(item["bbox"][0]), float(item["bbox"][1])))
    groups: list[list[dict[str, Any]]] = []
    current_group: list[dict[str, Any]] = []
    current_right: float | None = None
    for component in ordered:
        component_left = float(component["bbox"][0])
        component_right = component_left + float(component["bbox"][2])
        if current_group and current_right is not None and component_left - current_right > gap_px:
            groups.append(current_group)
            current_group = [component]
            current_right = component_right
            continue
        current_group.append(component)
        current_right = component_right if current_right is None else max(current_right, component_right)
    if current_group:
        groups.append(current_group)

    for group in groups:
        segment_left = min(float(component["bbox"][0]) for component in group)
        segment_right = max(float(component["bbox"][0]) + float(component["bbox"][2]) for component in group)
        group_is_dot_only = all(component.get("is_dot_like") for component in group)
        group_min_width_px = 1.0 if group_is_dot_only else min_segment_width_px
        if segment_right - segment_left < group_min_width_px:
            continue
        segment_left = max(0.0, segment_left - pad_px)
        segment_right = min(float(image_width), segment_right + pad_px)
        if segment_right - segment_left >= 3.0:
            segments.append([[round(segment_left, 2), round(line_y, 2)], [round(segment_right, 2), round(line_y, 2)]])
    segments.sort(key=lambda item: item[0][0])
    return segments


def baseline_segments_from_anchor_sets(
    *,
    text_anchors: list[dict[str, Any]],
    dot_anchors: list[dict[str, Any]],
    fallback_anchors: list[dict[str, Any]],
    line_y: float,
    image_width: int,
    gap_px: float,
    pad_px: float,
    dot_pad_px: float,
    min_segment_width_px: float,
) -> list[list[list[float]]]:
    segments: list[list[list[float]]] = []
    if text_anchors:
        segments.extend(
            line_segments_from_components(
                text_anchors,
                line_y,
                image_width=image_width,
                gap_px=gap_px,
                pad_px=pad_px,
                min_segment_width_px=min_segment_width_px,
            )
        )
    if dot_anchors:
        segments.extend(
            line_segments_from_components(
                dot_anchors,
                line_y,
                image_width=image_width,
                gap_px=0.0,
                pad_px=dot_pad_px,
                min_segment_width_px=1.0,
            )
        )
    if not segments and fallback_anchors:
        segments.extend(
            line_segments_from_components(
                fallback_anchors,
                line_y,
                image_width=image_width,
                gap_px=gap_px,
                pad_px=pad_px,
                min_segment_width_px=min_segment_width_px,
            )
        )
    segments.sort(key=lambda item: item[0][0])
    return segments


def median_line_segments_for_row(
    touched: list[dict[str, Any]],
    *,
    profile_y: float,
    image_width: int,
    is_dot_only_candidate: bool,
    gap_px: float,
    pad_px: float,
    dot_pad_px: float,
    min_segment_width_px: float,
    baseline_bottom_percentile: float,
) -> tuple[list[list[list[float]]], str, float]:
    anchors, segment_source, text_anchors, dot_anchors = baseline_anchor_components(
        touched,
        line_y=profile_y,
        is_dot_only_candidate=is_dot_only_candidate,
        min_segment_width_px=min_segment_width_px,
    )
    baseline_y = robust_row_baseline_y(
        profile_y=profile_y,
        text_anchors=text_anchors,
        dot_anchors=dot_anchors,
        bottom_percentile=baseline_bottom_percentile,
    )

    segments = baseline_segments_from_anchor_sets(
        text_anchors=text_anchors,
        dot_anchors=dot_anchors,
        fallback_anchors=anchors,
        line_y=baseline_y,
        image_width=image_width,
        gap_px=gap_px,
        pad_px=pad_px,
        dot_pad_px=dot_pad_px,
        min_segment_width_px=min_segment_width_px,
    )
    if segments:
        return segments, segment_source, baseline_y

    fallback_left = min(float(component["bbox"][0]) for component in anchors)
    fallback_right = max(float(component["bbox"][0]) + float(component["bbox"][2]) for component in anchors)
    fallback = [
        [round(max(0.0, fallback_left), 2), round(baseline_y, 2)],
        [round(min(float(image_width), fallback_right), 2), round(baseline_y, 2)],
    ]
    return [fallback], segment_source, baseline_y


def build_ink_rows(
    components: list[dict[str, Any]],
    mask_shape: tuple[int, int],
    candidates: list[dict[str, Any]],
    *,
    image_width: int,
    image_height: int,
    scale: int,
    cell_margin_px: float,
    min_components: int,
    min_x_span: float,
    outline_pad_px: int,
    outline_close_x_px: int,
    outline_close_y_px: int,
    median_line_gap_px: float,
    median_line_pad_px: float,
    lacuna_baseline_pad_px: float,
    median_line_min_segment_width_px: float,
    baseline_bottom_percentile: float,
) -> list[dict[str, Any]]:
    eligible = [component for component in components if not component_is_excluded(component)]
    eligible_by_id = {int(component["id"]): component for component in eligible}
    sorted_candidates = sorted(candidates, key=lambda item: float(item["baseline_y"]))
    rows: list[dict[str, Any]] = []
    for candidate_index, candidate in enumerate(sorted_candidates):
        profile_y = float(candidate["baseline_y"])
        seed_ids = set(int(item) for item in candidate.get("seed_component_ids", []))
        source = str(candidate.get("source", ""))
        is_dot_only_candidate = "ink_profile" not in source and bool(seed_ids)
        if candidate_index == 0:
            upper_y = 0.0
        else:
            upper_y = (float(sorted_candidates[candidate_index - 1]["baseline_y"]) + profile_y) / 2.0
        if candidate_index == len(sorted_candidates) - 1:
            lower_y = float(image_height)
        else:
            lower_y = (profile_y + float(sorted_candidates[candidate_index + 1]["baseline_y"])) / 2.0
        upper_y = max(0.0, upper_y - cell_margin_px)
        lower_y = min(float(image_height), lower_y + cell_margin_px)
        if is_dot_only_candidate:
            touched = [eligible_by_id[item_id] for item_id in sorted(seed_ids) if item_id in eligible_by_id]
        else:
            touched = []
            for component in eligible:
                x, y, width, height = [float(value) for value in component["bbox"]]
                center_y = y + height / 2.0
                belongs_to_cell = upper_y <= center_y <= lower_y
                is_detached_mark = component.get("is_dot_like") or component.get("is_thin_horizontal_mark") or height <= 8.0
                overlaps_cell = (
                    is_detached_mark
                    and y <= lower_y
                    and y + height >= upper_y
                    and height <= (lower_y - upper_y) * 1.25
                )
                if belongs_to_cell or overlaps_cell or int(component["id"]) in seed_ids:
                    touched.append(component)
        if not touched:
            continue
        x0 = min(float(item["bbox"][0]) for item in touched)
        y0 = min(float(item["bbox"][1]) for item in touched)
        x1 = max(float(item["bbox"][0]) + float(item["bbox"][2]) for item in touched)
        y1 = max(float(item["bbox"][1]) + float(item["bbox"][3]) for item in touched)
        component_ids = sorted(int(item["id"]) for item in touched)
        if len(component_ids) < min_components and x1 - x0 < min_x_span:
            continue
        component_id_set = set(component_ids)
        outline_scaled, outline_original = row_outline_polygons(
            components,
            component_id_set,
            mask_shape,
            scale=scale,
            pad_px=outline_pad_px,
            close_x_px=outline_close_x_px,
            close_y_px=outline_close_y_px,
        )
        if not outline_scaled:
            continue
        median_line_segments, median_line_span_source, baseline_y = median_line_segments_for_row(
            touched,
            profile_y=profile_y,
            image_width=image_width,
            is_dot_only_candidate=is_dot_only_candidate,
            gap_px=median_line_gap_px,
            pad_px=median_line_pad_px,
            dot_pad_px=lacuna_baseline_pad_px,
            min_segment_width_px=median_line_min_segment_width_px,
            baseline_bottom_percentile=baseline_bottom_percentile,
        )
        median_line_span = [median_line_segments[0][0][0], median_line_segments[-1][1][0]]
        baseline = median_line_segments[0]
        rows.append(
            {
                "ink_profile_y": round(profile_y, 2),
                "median_line_y": round(profile_y, 2),
                "median_line_segments": median_line_segments,
                "median_line_segment_count": len(median_line_segments),
                "median_line_span": median_line_span,
                "median_line_span_source": median_line_span_source,
                "median_line_gap_px": median_line_gap_px,
                "baseline_y": round(baseline_y, 2),
                "row_cell_y": [round(upper_y, 2), round(lower_y, 2)],
                "source": candidate["source"],
                "score": candidate.get("score"),
                "component_ids": component_ids,
                "component_count": len(component_ids),
                "dot_like_component_count": sum(1 for item in touched if item.get("is_dot_like")),
                "x_span": [round(max(0.0, x0), 2), round(min(float(image_width), x1), 2)],
                "baseline_span": median_line_span,
                "baseline_span_source": median_line_span_source,
                "bbox": [round(x0, 2), round(y0, 2), round(x1 - x0, 2), round(y1 - y0, 2)],
                "outline_polygons_scaled": outline_scaled,
                "outline_polygons": outline_original,
                "outline_polygon_count": len(outline_scaled),
                "baseline": baseline,
                "baseline_segments": median_line_segments,
            }
        )

    deduped: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda item: (float(item.get("ink_profile_y", item["baseline_y"])), float(item["x_span"][0]))):
        row_ids = set(row["component_ids"])
        duplicate_index: int | None = None
        for index, existing in enumerate(deduped):
            existing_ids = set(existing["component_ids"])
            overlap = len(row_ids & existing_ids) / max(1, min(len(row_ids), len(existing_ids)))
            if overlap >= 0.70:
                duplicate_index = index
                break
        if duplicate_index is None:
            deduped.append(row)
            continue
        existing = deduped[duplicate_index]
        if row["component_count"] > existing["component_count"] or row.get("score", 0) > existing.get("score", 0):
            deduped[duplicate_index] = row

    for index, row in enumerate(deduped, start=1):
        row["index"] = index
        if not row.get("baseline_segments"):
            row["baseline_segments"] = [[[row["x_span"][0], row["baseline_y"]], [row["x_span"][1], row["baseline_y"]]]]
        if not row.get("median_line_segments"):
            row["median_line_segments"] = row["baseline_segments"]
        row["baseline"] = row["baseline_segments"][0]
    return deduped


def component_row_bands(
    components: list[dict[str, Any]],
    *,
    min_components: int,
    min_x_span: float,
    y_gap_px: float,
    pad_px: int,
) -> list[Band]:
    candidates = []
    for component in components:
        if component.get("edge", {}).get("is_edge_artifact"):
            continue
        if component.get("is_dot_like"):
            continue
        x, y, width, height = [float(value) for value in component["bbox"]]
        if height < 5 or float(component["area_px"]) < 16:
            continue
        candidates.append({"component": component, "y0": y, "y1": y + height, "x0": x, "x1": x + width})
    candidates.sort(key=lambda item: (item["y0"], item["x0"]))

    groups: list[list[dict[str, Any]]] = []
    for candidate in candidates:
        placed = False
        for group in groups:
            group_y0 = min(item["y0"] for item in group)
            group_y1 = max(item["y1"] for item in group)
            if candidate["y0"] <= group_y1 + y_gap_px and candidate["y1"] >= group_y0 - y_gap_px:
                group.append(candidate)
                placed = True
                break
        if not placed:
            groups.append([candidate])

    bands: list[Band] = []
    for group in groups:
        x0 = min(item["x0"] for item in group)
        x1 = max(item["x1"] for item in group)
        y0 = min(item["y0"] for item in group)
        y1 = max(item["y1"] for item in group)
        if len(group) < min_components and x1 - x0 < min_x_span:
            continue
        bands.append(Band(max(0, int(round(y0 - pad_px))), int(round(y1 + pad_px)), "component"))
    return merge_close_bands(bands, max_gap=max(2, int(round(y_gap_px / 2))))


def projection_bands(mask: np.ndarray, *, scale: int, min_activity: int, smooth_px: int, pad_px: int) -> list[Band]:
    """Legacy broad projection witness, kept for comparison only."""
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, 5 * scale), max(1, 1 * scale)))
    profile = (mask > 0).sum(axis=1).astype(np.float32)
    if smooth_px > 1:
        kernel_len = odd_at_least(smooth_px * scale, 3)
        profile = cv2.GaussianBlur(profile.reshape(-1, 1), (1, kernel_len), 0).ravel()
    active = profile >= max(1, min_activity * scale)
    bands: list[Band] = []
    start: int | None = None
    for y, is_active in enumerate(active):
        if is_active and start is None:
            start = y
        elif not is_active and start is not None:
            if y - start >= max(2, 3 * scale):
                y0 = max(0, int(round((start - pad_px * scale) / scale)))
                y1 = int(round((y + pad_px * scale) / scale))
                bands.append(Band(y0, y1, "projection"))
            start = None
    if start is not None and len(active) - start >= max(2, 3 * scale):
        y0 = max(0, int(round((start - pad_px * scale) / scale)))
        y1 = int(round((len(active) + pad_px * scale) / scale))
        bands.append(Band(y0, y1, "projection"))
    return merge_close_bands(bands, max_gap=4)


def dot_rows(components: list[dict[str, Any]], *, min_dots: int, y_tolerance: float) -> list[dict[str, Any]]:
    dots = [
        component for component in components
        if component.get("is_dot_like") and not component_is_excluded(component)
    ]
    dots.sort(key=lambda item: (item["centroid"][1], item["centroid"][0]))
    rows: list[list[dict[str, Any]]] = []
    for dot in dots:
        cy = float(dot["centroid"][1])
        placed = False
        for row in rows:
            median_y = float(np.median([item["centroid"][1] for item in row]))
            if abs(cy - median_y) <= y_tolerance:
                row.append(dot)
                placed = True
                break
        if not placed:
            rows.append([dot])

    out: list[dict[str, Any]] = []
    for row in rows:
        if len(row) < min_dots:
            continue
        x0 = min(item["bbox"][0] for item in row)
        y0 = min(item["bbox"][1] for item in row)
        x1 = max(item["bbox"][0] + item["bbox"][2] for item in row)
        y1 = max(item["bbox"][1] + item["bbox"][3] for item in row)
        out.append(
            {
                "dot_count": len(row),
                "component_ids": [item["id"] for item in row],
                "bbox": [round(x0, 2), round(y0, 2), round(x1 - x0, 2), round(y1 - y0, 2)],
                "center_y": round(float(np.median([item["centroid"][1] for item in row])), 2),
                "x_span": [round(x0, 2), round(x1, 2)],
            }
        )
    out.sort(key=lambda item: (item["center_y"], item["x_span"][0]))
    return out


def merge_close_bands(bands: list[Band], max_gap: int) -> list[Band]:
    if not bands:
        return []
    sorted_bands = sorted(bands, key=lambda band: (band.y0, band.y1))
    merged = [sorted_bands[0]]
    for band in sorted_bands[1:]:
        last = merged[-1]
        if band.y0 <= last.y1 + max_gap:
            sources = "+".join(sorted(set(last.source.split("+") + band.source.split("+"))))
            merged[-1] = Band(min(last.y0, band.y0), max(last.y1, band.y1), sources)
        else:
            merged.append(band)
    return merged


def combined_bands(projection: list[Band], dot_row_items: list[dict[str, Any]], *, pad: int) -> list[Band]:
    bands = list(projection)
    for row in dot_row_items:
        cy = float(row["center_y"])
        bands.append(Band(max(0, int(round(cy - pad))), int(round(cy + pad)), "dot_row"))
    return merge_close_bands(bands, max_gap=8)


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    row_items = []
    for index, row in enumerate(rows, start=1):
        median_line_y = round(float(row.get("ink_profile_y", row.get("median_line_y", row["baseline_y"]))), 2)
        baseline_y = round(float(row["baseline_y"]), 2)
        baseline_segments = row.get("baseline_segments", row.get("median_line_segments", []))
        median_line_segments = row.get("median_line_segments", baseline_segments)
        row_items.append(
            {
                "index": index,
                "ink_profile_y": median_line_y,
                "median_line_y": median_line_y,
                "center_y": median_line_y,
                "source": row["source"],
                "component_ids": sorted(int(item) for item in row.get("component_ids", [])),
                "component_count": row["component_count"],
                "dot_like_component_count": row["dot_like_component_count"],
                "x_span": row["x_span"],
                "baseline_span": row.get("baseline_span", row.get("median_line_span")),
                "baseline_span_source": row.get("baseline_span_source", row.get("median_line_span_source")),
                "median_line_span": row.get("median_line_span", row.get("baseline_span")),
                "median_line_segment_count": len(median_line_segments),
                "median_line_segments": median_line_segments,
                "median_line_span_source": row.get("median_line_span_source", row.get("baseline_span_source")),
                "bbox": row["bbox"],
                "outline_polygon_count": row["outline_polygon_count"],
                "baseline_y": baseline_y,
                "baseline_segment_count": len(baseline_segments),
                "baseline_segments": baseline_segments,
            }
        )
    return {
        "geometry_rows": row_items,
        "geometry_row_count": len(row_items),
    }


def draw_translucent_rect(image: np.ndarray, pt1: tuple[int, int], pt2: tuple[int, int], color: tuple[int, int, int], alpha: float) -> None:
    overlay = image.copy()
    cv2.rectangle(overlay, pt1, pt2, color, -1)
    cv2.addWeighted(overlay, alpha, image, 1.0 - alpha, 0, image)


def draw_review(
    work: np.ndarray,
    mask: np.ndarray,
    components: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    dot_row_items: list[dict[str, Any]],
    page_id: str,
    image_width: int,
    image_height: int,
) -> np.ndarray:
    height, width = work.shape[:2]
    component_canvas = work.copy()
    row_canvas = work.copy()
    sx = work.shape[1] / image_width
    sy = work.shape[0] / image_height

    for component in components:
        points = np.asarray(component["polygon_scaled"], dtype=np.int32).reshape((-1, 1, 2))
        if component.get("edge", {}).get("is_edge_artifact"):
            color = (165, 165, 165)
        elif component.get("artifact", {}).get("is_excluded"):
            color = (115, 115, 115)
        elif component["is_dot_like"]:
            color = (255, 0, 255)
        else:
            color = (0, 185, 255)
        cv2.polylines(component_canvas, [points], True, color, 1, cv2.LINE_AA)

    for row_index, row in enumerate(rows, start=1):
        row_outline_color = (45, 190, 70)
        attached_marker_color = (0, 160, 255)
        baseline_color = (40, 70, 255)
        for polygon in row["outline_polygons_scaled"]:
            points = np.asarray(polygon, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(row_canvas, [points], True, row_outline_color, 1, cv2.LINE_AA)
        for polygon in row.get("attached_marker_polygons_scaled", []):
            points = np.asarray(polygon, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(row_canvas, [points], True, attached_marker_color, 2, cv2.LINE_AA)
        baseline_segments = row.get("baseline_segments") or row.get("median_line_segments") or [
            row.get("baseline") or [[row["x_span"][0], row["baseline_y"]], [row["x_span"][1], row["baseline_y"]]]
        ]
        for segment in baseline_segments:
            points = np.asarray(
                [[int(round(float(point[0]) * sx)), int(round(float(point[1]) * sy))] for point in segment],
                dtype=np.int32,
            ).reshape((-1, 1, 2))
            if len(points) >= 2:
                cv2.polylines(row_canvas, [points], False, baseline_color, 2, cv2.LINE_AA)
        label_x = int(round(float(baseline_segments[0][0][0]) * sx))
        label_y = int(round(float(row["baseline_y"]) * sy))
        cv2.putText(row_canvas, f"b{row_index:02d}", (max(4, label_x), max(14, label_y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, baseline_color, 1, cv2.LINE_AA)

    mask_bgr = cv2.cvtColor(255 - mask, cv2.COLOR_GRAY2BGR)
    target_h = 1300
    panels = []
    for panel in (work, mask_bgr, component_canvas, row_canvas):
        h, w = panel.shape[:2]
        factor = target_h / h
        panels.append(cv2.resize(panel, (int(round(w * factor)), target_h), interpolation=cv2.INTER_AREA))

    gap = 22
    header_h = 118
    sheet_w = sum(panel.shape[1] for panel in panels) + gap * 4
    sheet = np.full((header_h + target_h + 10, sheet_w, 3), 255, dtype=np.uint8)
    title = (
        f"p{page_id} body geometry | components={len(components)} dot_rows={len(dot_row_items)} "
        f"geom_rows={len(rows)}"
    )
    cv2.putText(sheet, title, (gap, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(sheet, "char polygons are unchanged; row outline/baseline is a separate derived layer", (gap, 64), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (60, 60, 60), 1, cv2.LINE_AA)

    labels = ["body crop", "high-res ink mask", "component polygons", "row outline + baseline"]
    x = gap
    for label, panel in zip(labels, panels):
        cv2.putText(sheet, label, (x, header_h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (45, 45, 45), 1, cv2.LINE_AA)
        sheet[header_h:header_h + target_h, x:x + panel.shape[1]] = panel
        x += panel.shape[1] + gap
    return sheet


def process_page(page_id: str, args: argparse.Namespace) -> dict[str, Any]:
    img_path = body_path(args.body_dir, page_id)
    image = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"could not read {img_path}")
    h, w = image.shape[:2]

    work, mask = threshold_ink_high_res(image, args.scale, contrast_threshold=args.contrast_threshold)
    components, kept_mask = collect_components(
        mask,
        scale=args.scale,
        min_component_area=args.min_component_area,
        epsilon_ratio=args.epsilon_ratio,
        min_epsilon=args.min_epsilon,
    )
    mark_edge_artifacts(
        components,
        image_width=w,
        image_height=h,
        edge_margin=args.edge_margin_px,
        side_edge_margin=args.side_edge_margin_px,
        side_artifact_band=args.side_artifact_band_px,
        tall_artifact_height_ratio=args.tall_artifact_height_ratio,
    )
    mark_tiny_dot_artifacts(
        components,
        max_area_px=args.tiny_dot_artifact_area_px,
        neighbor_px=args.tiny_dot_neighbor_px,
        min_dot_row_count=args.min_dot_row_count,
        dot_row_y_tolerance=args.dot_row_y_tolerance,
        dot_row_size_ratio=args.tiny_dot_row_size_ratio,
        char_x_pad_px=args.tiny_dot_char_x_pad_px,
    )
    evidence_mask = component_mask(
        components,
        kept_mask.shape,
        exclude_edge_artifacts=True,
        exclude_artifacts=True,
        exclude_thin_horizontal_marks=True,
    )
    cleaned_mask = component_mask(
        components,
        kept_mask.shape,
        exclude_edge_artifacts=True,
        exclude_artifacts=True,
        exclude_thin_horizontal_marks=False,
    )
    ink_candidates = ink_baseline_candidates(
        evidence_mask,
        scale=args.scale,
        min_activity=args.min_row_activity,
        smooth_px=args.row_smooth_px,
        min_gap_px=args.baseline_min_gap_px,
    )
    dot_row_items = dot_rows(components, min_dots=args.min_dot_row_count, y_tolerance=args.dot_row_y_tolerance)
    baseline_candidates = merge_baseline_candidates(
        ink_candidates,
        dot_row_items,
        merge_px=args.baseline_merge_px,
        dot_attach_px=args.dot_row_attach_px,
    )
    rows = build_outline_rows(
        components,
        kept_mask.shape,
        dot_row_items,
        image_width=w,
        image_height=h,
        scale=args.scale,
        min_components=args.min_row_components,
        min_x_span=args.min_row_x_span,
        outline_pad_px=args.row_outline_pad_px,
        outline_close_x_px=args.row_outline_close_x_px,
        outline_close_y_px=args.row_outline_close_y_px,
        seed_min_height_px=args.outline_seed_min_height_px,
        seed_min_area_px=args.outline_seed_min_area_px,
        seed_y_tolerance_px=args.outline_seed_y_tolerance_px,
        attach_y_pad_px=args.outline_attach_y_pad_px,
        detached_mark_max_height_px=args.outline_detached_mark_max_height_px,
        dot_row_attach_px=args.dot_row_attach_px,
        baseline_percent=args.outline_baseline_percent,
        baseline_sigma=args.outline_baseline_sigma,
        baseline_gap_px=args.outline_baseline_gap_px,
        baseline_sample_step_px=args.outline_baseline_sample_step_px,
        baseline_min_segment_width_px=args.outline_baseline_min_segment_width_px,
        baseline_min_height_px=args.outline_baseline_min_height_px,
        standalone_dot_min_count=args.min_dot_row_count,
        standalone_dot_pad_px=args.lacuna_baseline_pad_px,
    )
    projection_witness = projection_bands(
        evidence_mask,
        scale=args.scale,
        min_activity=args.min_row_activity,
        smooth_px=args.row_smooth_px,
        pad_px=args.row_pad_px,
    )
    row_summary = summarize_rows(rows)

    out_page = args.out_dir / "pages"
    out_reviews = args.out_dir / "reviews"
    out_masks = args.out_dir / "masks"
    out_page.mkdir(parents=True, exist_ok=True)
    out_reviews.mkdir(parents=True, exist_ok=True)
    out_masks.mkdir(parents=True, exist_ok=True)

    payload = {
        "page": page_id,
        "input": rel(img_path),
        "scale": args.scale,
        "contrast_threshold": args.contrast_threshold,
        "baseline_bottom_percentile": args.baseline_bottom_percentile,
        "outline_baseline_percent": args.outline_baseline_percent,
        "row_builder": "outline_first",
        "image_size": [w, h],
        "mask_size": [int(mask.shape[1]), int(mask.shape[0])],
        "component_count": len(components),
        "dot_like_component_count": sum(1 for item in components if item.get("is_dot_like")),
        "edge_artifact_component_count": sum(1 for item in components if item.get("edge", {}).get("is_edge_artifact")),
        "excluded_artifact_component_count": sum(1 for item in components if item.get("artifact", {}).get("is_excluded")),
        "thin_horizontal_mark_component_count": sum(1 for item in components if item.get("is_thin_horizontal_mark")),
        "ink_median_line_candidates": ink_candidates,
        "median_line_candidates": baseline_candidates,
        "ink_baseline_candidates": ink_candidates,
        "baseline_candidates": baseline_candidates,
        "ink_rows": rows,
        "projection_rows_legacy_witness": [{"index": i, "y0": row.y0, "y1": row.y1, "center_y": round(row.center, 2), "source": row.source} for i, row in enumerate(projection_witness, start=1)],
        "dot_rows": dot_row_items,
        "geometry_rows": row_summary["geometry_rows"],
        "geometry_row_count": row_summary["geometry_row_count"],
        "components": components,
    }
    (out_page / f"p{page_id}_geometry.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    cv2.imwrite(str(out_masks / f"p{page_id}_mask.png"), cleaned_mask)
    review = draw_review(work, cleaned_mask, components, rows, dot_row_items, page_id, w, h)
    cv2.imwrite(str(out_reviews / f"p{page_id}_geometry_review.jpg"), review, [int(cv2.IMWRITE_JPEG_QUALITY), 92])

    return {
        "page": page_id,
        "component_count": len(components),
        "dot_like_component_count": payload["dot_like_component_count"],
        "edge_artifact_component_count": payload["edge_artifact_component_count"],
        "excluded_artifact_component_count": payload["excluded_artifact_component_count"],
        "thin_horizontal_mark_component_count": payload["thin_horizontal_mark_component_count"],
        "ink_baseline_candidate_count": len(ink_candidates),
        "median_line_candidate_count": len(baseline_candidates),
        "baseline_candidate_count": len(baseline_candidates),
        "projection_witness_row_count": len(projection_witness),
        "dot_row_count": len(dot_row_items),
        "geometry_row_count": row_summary["geometry_row_count"],
        "review": rel(out_reviews / f"p{page_id}_geometry_review.jpg"),
        "json": rel(out_page / f"p{page_id}_geometry.json"),
    }


def run_page(page_id: str, args: argparse.Namespace) -> dict[str, Any]:
    try:
        result = process_page(page_id, args)
        result["ok"] = True
        return result
    except Exception as exc:
        return {"page": page_id, "ok": False, "message": f"{type(exc).__name__}: {exc}"}


def summary_result_from_payload(payload: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    page_id = str(payload["page"])
    return {
        "page": page_id,
        "component_count": int(payload.get("component_count", 0)),
        "dot_like_component_count": int(payload.get("dot_like_component_count", 0)),
        "edge_artifact_component_count": int(payload.get("edge_artifact_component_count", 0)),
        "excluded_artifact_component_count": int(payload.get("excluded_artifact_component_count", 0)),
        "thin_horizontal_mark_component_count": int(payload.get("thin_horizontal_mark_component_count", 0)),
        "ink_baseline_candidate_count": len(payload.get("ink_baseline_candidates", [])),
        "median_line_candidate_count": len(payload.get("median_line_candidates", [])),
        "baseline_candidate_count": len(payload.get("baseline_candidates", [])),
        "projection_witness_row_count": len(payload.get("projection_rows_legacy_witness", [])),
        "dot_row_count": len(payload.get("dot_rows", [])),
        "geometry_row_count": int(payload.get("geometry_row_count", len(payload.get("geometry_rows", [])))),
        "review": rel(out_dir / "reviews" / f"p{page_id}_geometry_review.jpg"),
        "json": rel(out_dir / "pages" / f"p{page_id}_geometry.json"),
    }


def collect_existing_summary_results(out_dir: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    pages_dir = out_dir / "pages"
    if not pages_dir.exists():
        return results
    for path in sorted(pages_dir.glob("p*_geometry.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        results.append(summary_result_from_payload(payload, out_dir))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pages", nargs="*", help="Page IDs, or 'all'. Empty = all body-crop pages.")
    parser.add_argument("--sample", action="store_true", help="Process the review/test page set instead of all pages.")
    parser.add_argument("--body-dir", type=Path, default=DEFAULT_BODY_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--scale", type=int, default=2, help="High-resolution analysis scale.")
    parser.add_argument("--contrast-threshold", type=int, default=14, help="Local contrast threshold for ink capture.")
    parser.add_argument("--epsilon-ratio", type=float, default=0.0015)
    parser.add_argument("--min-epsilon", type=float, default=0.35)
    parser.add_argument("--min-component-area", type=int, default=6)
    parser.add_argument("--tiny-dot-artifact-area-px", type=float, default=8.0)
    parser.add_argument("--tiny-dot-neighbor-px", type=float, default=12.0)
    parser.add_argument("--tiny-dot-row-size-ratio", type=float, default=0.55)
    parser.add_argument("--tiny-dot-char-x-pad-px", type=float, default=2.5)
    parser.add_argument("--edge-margin-px", type=float, default=8.0)
    parser.add_argument("--side-edge-margin-px", type=float, default=3.0)
    parser.add_argument("--side-artifact-band-px", type=float, default=72.0)
    parser.add_argument("--tall-artifact-height-ratio", type=float, default=0.12)
    parser.add_argument("--min-row-activity", type=int, default=16)
    parser.add_argument("--row-smooth-px", type=int, default=9)
    parser.add_argument("--row-pad-px", type=int, default=6)
    parser.add_argument("--baseline-min-gap-px", type=float, default=22.0)
    parser.add_argument("--baseline-merge-px", type=float, default=12.0)
    parser.add_argument("--dot-row-attach-px", type=float, default=18.0)
    parser.add_argument("--row-cell-margin-px", type=float, default=4.0)
    parser.add_argument("--min-row-components", type=int, default=3)
    parser.add_argument("--min-row-x-span", type=float, default=70.0)
    parser.add_argument("--row-outline-pad-px", type=int, default=2)
    parser.add_argument("--row-outline-close-x-px", type=int, default=30)
    parser.add_argument("--row-outline-close-y-px", type=int, default=10)
    parser.add_argument("--median-line-gap-px", type=float, default=20.0, help="Maximum x gap to bridge within one baseline segment.")
    parser.add_argument("--median-line-pad-px", type=float, default=2.0, help="Horizontal padding added to median-line segments.")
    parser.add_argument("--lacuna-baseline-pad-px", type=float, default=1.25, help="Horizontal padding added to lacuna-point baseline ticks.")
    parser.add_argument("--median-line-min-segment-width-px", type=float, default=8.0, help="Drop shorter median-line segments as isolated flecks.")
    parser.add_argument("--baseline-bottom-percentile", type=float, default=72.0, help="Percentile of main text component bottoms used for the drawn row baseline y.")
    parser.add_argument("--outline-seed-min-height-px", type=float, default=18.0)
    parser.add_argument("--outline-seed-min-area-px", type=float, default=105.0)
    parser.add_argument("--outline-seed-y-tolerance-px", type=float, default=13.0)
    parser.add_argument("--outline-attach-y-pad-px", type=float, default=9.0)
    parser.add_argument("--outline-detached-mark-max-height-px", type=float, default=8.0)
    parser.add_argument("--outline-baseline-percent", type=float, default=0.82)
    parser.add_argument("--outline-baseline-sigma", type=float, default=2.35)
    parser.add_argument("--outline-baseline-gap-px", type=float, default=42.0)
    parser.add_argument("--outline-baseline-sample-step-px", type=float, default=64.0)
    parser.add_argument("--outline-baseline-min-segment-width-px", type=float, default=8.0)
    parser.add_argument("--outline-baseline-min-height-px", type=float, default=6.0)
    parser.add_argument("--min-dot-row-count", type=int, default=4)
    parser.add_argument("--dot-row-y-tolerance", type=float, default=6.5)
    parser.add_argument("--dot-row-pad-px", type=int, default=9)
    parser.add_argument("-j", "--max-workers", type=int, default=6)
    args = parser.parse_args()

    args.body_dir = args.body_dir.resolve()
    args.out_dir = args.out_dir.resolve()
    pages = resolve_pages(args, args.body_dir)
    all_body_pages = sorted(normalize_page_id(path.name) for path in args.body_dir.glob("p*_text_body.jpg"))
    if not pages:
        parser.error(f"no body crop pages found in {args.body_dir}")

    n_workers = max(1, int(args.max_workers))
    print(f"polygonizing {len(pages)} body-crop geometry pages with {n_workers} workers -> {args.out_dir}")
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        futures = {executor.submit(run_page, page_id, args): page_id for page_id in pages}
        with tqdm(total=len(futures), desc="body geometry", unit="page") as progress:
            for future in as_completed(futures):
                page_id = futures[future]
                result = future.result()
                if result.get("ok"):
                    result.pop("ok", None)
                    results.append(result)
                    tqdm.write(
                        f"p{page_id}: components={result['component_count']} median_lines={result['median_line_candidate_count']} "
                        f"rows={result['geometry_row_count']} dots={result['dot_like_component_count']}"
                    )
                else:
                    failures.append({"page": page_id, "message": result.get("message", "unknown error")})
                    tqdm.write(f"FAIL p{page_id}: {result.get('message')}")
                progress.set_postfix(written=len(results), failed=len(failures))
                progress.update(1)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    processed_full_corpus = pages == all_body_pages
    summary_results = sorted(results if processed_full_corpus else collect_existing_summary_results(args.out_dir), key=lambda item: item["page"])
    summary = {
        "body_dir": rel(args.body_dir),
        "out_dir": rel(args.out_dir),
        "count": len(summary_results),
        "failure_count": len(failures),
        "scale": args.scale,
        "results": summary_results,
        "failures": failures,
    }
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"done: {len(results)}/{len(pages)} ok, failures={len(failures)}")


if __name__ == "__main__":
    main()