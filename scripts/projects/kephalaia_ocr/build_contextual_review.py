#!/usr/bin/env python3
"""Build contextual review tables for ambiguous Kephalaia OCR clusters.

This script uses only blob order, cluster ids, current cluster assignments, and
geometry. It does not read AI-derived Coptic text.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any

from tqdm import tqdm

REPO = Path(__file__).resolve().parents[3]
OCR_ROOT = REPO / "output" / "projects" / "kephalaia_ocr"
BASELINE_Y = 39
WARP_HEIGHT = 60
EDGE_FRAGMENT_MARGIN_PX = 2

CONNECTED_REVIEW = "_connected_needs_literal_reading"
CONNECTED_REFERENCE = "_literal_connected_reference"
EDITORIAL_MARKER = "_editorial_marker"
EXCLUDED_PROJECTION_LABELS = {"?", "_mixed_character"}
BRACKET_LABELS = {"_left_square_bracket", "_right_square_bracket"}
MARK_LABELS = {"_lacuna_dot", "_middle_dot", "_unknown"}
SPECIAL_LABELS = BRACKET_LABELS | MARK_LABELS | {CONNECTED_REVIEW, EDITORIAL_MARKER}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_repo_path(value: str | None, default: Path) -> Path:
    if value is None:
        return default
    path = Path(value)
    return path if path.is_absolute() else REPO / path


def cluster_key(value: str | int) -> str:
    return f"{int(value):03d}"


def split_dir_from_cluster_summary(clusters_dir: Path) -> Path | None:
    summary_path = clusters_dir / "_summary.json"
    if not summary_path.exists():
        return None
    split_dir = (load_json(summary_path).get("split_input") or {}).get("split_dir")
    if not split_dir:
        return None
    path = Path(str(split_dir))
    return path if path.is_absolute() else REPO / path


def load_line_widths(split_dir: Path | None) -> dict[tuple[str, int], int]:
    widths: dict[tuple[str, int], int] = {}
    if split_dir is None or not split_dir.exists():
        return widths
    for path in sorted(split_dir.glob("keph_p*_lines_base_split.json")):
        data = load_json(path)
        page = str(data.get("page") or path.stem.removeprefix("keph_p").removesuffix("_lines_base_split"))
        for line in data.get("lines", []):
            warped_size = line.get("warped_size") or []
            if warped_size:
                widths[(page, int(line["line_index"]))] = int(warped_size[0])
    return widths


def normalize_projection_label(label: str) -> str:
    if label == "_multi_char_connected":
        return CONNECTED_REVIEW
    return label


def active_reverse_map(assignments_by_label: dict[str, list[str]]) -> dict[str, str]:
    reverse: dict[str, str] = {}
    for label, cluster_ids in assignments_by_label.items():
        for cluster_id in cluster_ids:
            reverse[cluster_key(cluster_id)] = label
    return reverse


def is_manual_warning(row: dict[str, Any]) -> bool:
    source = str(row.get("source") or "")
    migration = str(row.get("migration") or "")
    return source.startswith("manual_review_") or migration in {
        "old_subcluster_effect_preserved_by_stable_blob_key",
        "old_stable_blob_label_carried_into_split_stack",
    }


def load_manual_overrides(path: Path, *, include_warning_rows: bool = False) -> dict[tuple[str, int, int], dict[str, Any]]:
    if not path.exists():
        return {}
    rows = load_json(path).get("overrides", [])
    return {
        (str(row["page"]), int(row["line_index"]), int(row["blob_id"])): row
        for row in rows
        if include_warning_rows or not is_manual_warning(row)
    }


def load_subcluster_overrides(clusters_dir: Path) -> dict[tuple[str, int, int], dict[str, Any]]:
    overrides: dict[tuple[str, int, int], dict[str, Any]] = {}
    subcluster_root = clusters_dir / "subclusters"
    if not subcluster_root.exists():
        return overrides
    for label_path in sorted(subcluster_root.glob("*/_subcluster_labels.json")):
        assignment_path = label_path.parent / "_subassignments.json"
        if not assignment_path.exists():
            continue
        label_data = load_json(label_path)
        labels = label_data.get("labels", {})
        for item in load_json(assignment_path):
            subcluster = str(item["subcluster"]).zfill(2)
            metadata = labels.get(subcluster)
            if not metadata or not metadata.get("label"):
                continue
            key = (str(item["page"]), int(item["line_index"]), int(item["blob_id"]))
            overrides[key] = {
                "label": metadata["label"],
                "confidence": metadata.get("confidence", "needs_review"),
                "evidence": metadata.get("evidence", ""),
                "source": str(label_path.relative_to(REPO)),
                "cluster": str(item.get("cluster", "")),
                "subcluster": subcluster,
            }
    return overrides


def load_editorial_overrides(path: Path) -> dict[tuple[str, int, int], dict[str, Any]]:
    if not path.exists():
        return {}
    rows = load_json(path).get("overrides", [])
    overrides: dict[tuple[str, int, int], dict[str, Any]] = {}
    for row in rows:
        page = str(row["page"])
        line_index = int(row["line_index"])
        blob_ids = [int(blob_id) for blob_id in row.get("blob_ids", [])]
        display_chars = [str(char) for char in row.get("display_chars", [])]
        for position, blob_id in enumerate(blob_ids):
            metadata = dict(row)
            metadata["label"] = row.get("label") or EDITORIAL_MARKER
            metadata["span_position"] = position
            metadata["span_count"] = len(blob_ids)
            if position < len(display_chars):
                metadata["display_text"] = display_chars[position]
            overrides[(page, line_index, blob_id)] = metadata
    return overrides


def range_contains(value: float, bounds: list[float] | None) -> bool:
    if not bounds:
        return True
    if len(bounds) != 2:
        raise ValueError(f"Expected two bounds, got {bounds!r}")
    return float(bounds[0]) <= value <= float(bounds[1])


def load_geometric_overrides(path: Path, clusters_dir: Path) -> dict[tuple[str, int, int], dict[str, Any]]:
    if not path.exists():
        return {}
    config = load_json(path)
    overrides: dict[tuple[str, int, int], dict[str, Any]] = {}
    for rule in config.get("rules", []):
        label = rule.get("label")
        subassignments_value = rule.get("subassignments")
        if not label or not subassignments_value:
            continue
        subassignments_path = Path(str(subassignments_value))
        if not subassignments_path.is_absolute():
            subassignments_path = clusters_dir / subassignments_path
        if not subassignments_path.exists():
            continue
        cluster = str(rule.get("cluster", "")).zfill(3) if rule.get("cluster") is not None else None
        subcluster = str(rule.get("subcluster", "")).zfill(2) if rule.get("subcluster") is not None else None
        geometry = rule.get("geometry", {}) or {}
        for item in load_json(subassignments_path):
            item_cluster = str(item.get("cluster", "")).zfill(3)
            item_subcluster = str(item.get("subcluster", "")).zfill(2)
            if cluster and item_cluster != cluster:
                continue
            if subcluster and item_subcluster != subcluster:
                continue
            bbox = [int(value) for value in item.get("warped_bbox", [])]
            if len(bbox) != 4:
                continue
            width = float(item.get("width", bbox[2] - bbox[0] + 1))
            height = float(item.get("height", bbox[3] - bbox[1] + 1))
            center_y = (bbox[1] + bbox[3]) / 2.0
            if not range_contains(width, geometry.get("width")):
                continue
            if not range_contains(height, geometry.get("height")):
                continue
            if not range_contains(center_y, geometry.get("center_y")):
                continue
            key = (str(item["page"]), int(item["line_index"]), int(item["blob_id"]))
            overrides[key] = {
                "id": rule.get("id"),
                "label": label,
                "confidence": rule.get("confidence", "geometric"),
                "evidence": rule.get("evidence", ""),
                "source": str(path.relative_to(REPO)),
                "subassignments": str(subassignments_path.relative_to(REPO)),
                "cluster": item_cluster,
                "subcluster": item_subcluster,
                "geometry": {
                    "width": int(width),
                    "height": int(height),
                    "center_y": round(center_y, 2),
                    "warped_bbox": bbox,
                },
            }
    return overrides


def candidate_counts(review_item: dict[str, Any]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for raw_label, count in review_item.get("top", []):
        if raw_label in EXCLUDED_PROJECTION_LABELS:
            continue
        label = normalize_projection_label(str(raw_label))
        counts[label] += int(count)
    return counts


def candidate_list(review_item: dict[str, Any]) -> list[str]:
    total = max(1, int(review_item.get("total", 0)))
    threshold = max(3, int(total * 0.01))
    candidates: list[str] = []
    for label, count in candidate_counts(review_item).most_common():
        if count >= threshold or len(candidates) < 3:
            candidates.append(label)
    return candidates


def geometry_from_item(item: dict[str, Any], line_width: int, previous_gap: int | None, next_gap: int | None) -> dict[str, Any]:
    left, top, right, bottom = [int(value) for value in item["warped_bbox"]]
    width = right - left + 1
    height = bottom - top + 1
    return {
        "warped_bbox": [left, top, right, bottom],
        "width": width,
        "height": height,
        "area": int(item.get("area", 0)),
        "aspect": round(width / max(height, 1), 4),
        "center_x": round(((left + right) / 2) / max(line_width, 1), 4),
        "center_y": round(((top + bottom) / 2) / WARP_HEIGHT, 4),
        "baseline_touch": top <= BASELINE_Y <= bottom,
        "baseline_delta": abs(bottom - BASELINE_Y),
        "previous_gap": previous_gap,
        "next_gap": next_gap,
    }


def is_edge_fragment(item: dict[str, Any], line_width: int, allow_right_edge: bool) -> bool:
    left, _top, right, _bottom = [int(value) for value in item["warped_bbox"]]
    if left <= EDGE_FRAGMENT_MARGIN_PX:
        return True
    return allow_right_edge and line_width > 1 and right >= line_width - 1 - EDGE_FRAGMENT_MARGIN_PX


def is_coptic_assigned_label(label: str | None) -> bool:
    return bool(label and not str(label).startswith("_"))


def item_has_coptic_label(
    item: dict[str, Any],
    page: str,
    line_index: int,
    reverse: dict[str, str],
    manual_overrides: dict[tuple[str, int, int], dict[str, Any]],
    subcluster_overrides: dict[tuple[str, int, int], dict[str, Any]],
    geometric_overrides: dict[tuple[str, int, int], dict[str, Any]],
) -> bool:
    key = (page, line_index, int(item["blob_id"]))
    for override_map in (manual_overrides, subcluster_overrides, geometric_overrides):
        override = override_map.get(key) or {}
        if is_coptic_assigned_label(override.get("label")):
            return True
    return is_coptic_assigned_label(reverse.get(cluster_key(item["cluster"])))


def is_unresolved_mark_like(item: dict[str, Any], label: str | None) -> bool:
    if label is not None:
        return False
    left, top, right, bottom = [int(value) for value in item["warped_bbox"]]
    width = right - left + 1
    height = bottom - top + 1
    return width <= 8 and height <= 10


def neighboring_coptic_within(
    ordered: list[dict[str, Any]],
    position: int,
    page: str,
    line_index: int,
    reverse: dict[str, str],
    manual_overrides: dict[tuple[str, int, int], dict[str, Any]],
    subcluster_overrides: dict[tuple[str, int, int], dict[str, Any]],
    geometric_overrides: dict[tuple[str, int, int], dict[str, Any]],
    direction: int,
    max_gap: int,
) -> bool:
    if direction not in {-1, 1}:
        raise ValueError(f"Expected direction -1 or 1, got {direction}")
    current_bbox = [int(value) for value in ordered[position]["warped_bbox"]]
    cursor = position + direction
    while 0 <= cursor < len(ordered):
        other = ordered[cursor]
        other_bbox = [int(value) for value in other["warped_bbox"]]
        if direction < 0:
            gap = current_bbox[0] - other_bbox[2] - 1
        else:
            gap = other_bbox[0] - current_bbox[2] - 1
        if gap > max_gap:
            return False
        label = reverse.get(cluster_key(other["cluster"]))
        if item_has_coptic_label(other, page, line_index, reverse, manual_overrides, subcluster_overrides, geometric_overrides):
            return True
        # Brackets are transparent for Coptic-neighbor scans: an iota nestled
        # between editorial brackets like `[ⲓ]` should still see the Coptic
        # context on the far side of the bracket pair.
        if label in MARK_LABELS or label in BRACKET_LABELS or is_unresolved_mark_like(other, label):
            cursor += direction
            continue
        return False
    return False


def has_nearby_coptic(
    ordered: list[dict[str, Any]],
    position: int,
    page: str,
    line_index: int,
    reverse: dict[str, str],
    manual_overrides: dict[tuple[str, int, int], dict[str, Any]],
    subcluster_overrides: dict[tuple[str, int, int], dict[str, Any]],
    geometric_overrides: dict[tuple[str, int, int], dict[str, Any]],
    max_gap: int,
) -> bool:
    return neighboring_coptic_within(
        ordered,
        position,
        page,
        line_index,
        reverse,
        manual_overrides,
        subcluster_overrides,
        geometric_overrides,
        -1,
        max_gap,
    ) or neighboring_coptic_within(
        ordered,
        position,
        page,
        line_index,
        reverse,
        manual_overrides,
        subcluster_overrides,
        geometric_overrides,
        1,
        max_gap,
    )


def has_matching_bracket_pair(
    ordered: list[dict[str, Any]],
    position: int,
    reverse: dict[str, str],
    label: str | None,
    max_gap: int,
    max_tokens: int,
) -> bool:
    if label == "_left_square_bracket":
        direction = 1
        target = "_right_square_bracket"
    elif label == "_right_square_bracket":
        direction = -1
        target = "_left_square_bracket"
    else:
        return False
    current_bbox = [int(value) for value in ordered[position]["warped_bbox"]]
    cursor = position + direction
    steps = 0
    while 0 <= cursor < len(ordered) and steps < max_tokens:
        other = ordered[cursor]
        other_bbox = [int(value) for value in other["warped_bbox"]]
        gap = other_bbox[0] - current_bbox[2] - 1 if direction > 0 else current_bbox[0] - other_bbox[2] - 1
        if gap > max_gap:
            return False
        other_label = reverse.get(cluster_key(other["cluster"]))
        if other_label == target:
            return True
        if other_label == label:
            return False
        current_bbox = other_bbox
        cursor += direction
        steps += 1
    return False


def vertical_word_context_iota_override(
    item: dict[str, Any],
    position: int,
    ordered: list[dict[str, Any]],
    page: str,
    line_index: int,
    reverse: dict[str, str],
    manual_overrides: dict[tuple[str, int, int], dict[str, Any]],
    subcluster_overrides: dict[tuple[str, int, int], dict[str, Any]],
    geometric_overrides: dict[tuple[str, int, int], dict[str, Any]],
    label: str | None,
    candidates: list[str],
    decision: dict[str, Any],
    line_width: int,
) -> dict[str, Any] | None:
    bracket_labeled = label in BRACKET_LABELS
    unresolved_vertical = (
        label is None
        and "ⲓ" in {str(candidate) for candidate in candidates}
    )
    if not bracket_labeled and not unresolved_vertical:
        return None
    left, top, right, bottom = [int(value) for value in item["warped_bbox"]]
    width = right - left + 1
    height = bottom - top + 1
    baseline_tolerance = 3
    if width > 11 or height < 13 or height > 34 or not (top <= BASELINE_Y + baseline_tolerance and bottom >= BASELINE_Y - baseline_tolerance):
        return None
    if is_edge_fragment(item, line_width, allow_right_edge=False):
        return None
    full_height_editorial_bracket = height > 34
    if bracket_labeled and full_height_editorial_bracket and has_matching_bracket_pair(
        ordered,
        position,
        reverse,
        label,
        max_gap=24,
        max_tokens=8,
    ):
        return None
    coptic_max_gap = 40
    has_coptic = has_nearby_coptic(
        ordered,
        position,
        page,
        line_index,
        reverse,
        manual_overrides,
        subcluster_overrides,
        geometric_overrides,
        max_gap=coptic_max_gap,
    )
    if not has_coptic:
        # No Coptic neighbors — assign as bracket based on position
        rel_pos = left / max(1, line_width)
        if rel_pos < 0.15:
            return {
                "id": "vertical_margin_left_bracket",
                "label": "_left_square_bracket",
                "confidence": "geometry_margin_position",
                "evidence": "Vertical stroke near left margin with no nearby Coptic context; assigned as opening bracket.",
                "source": "build_contextual_review.py",
                "geometry": {
                    "width": width,
                    "height": height,
                    "warped_bbox": [left, top, right, bottom],
                },
            }
        elif rel_pos > 0.85:
            return {
                "id": "vertical_margin_right_bracket",
                "label": "_right_square_bracket",
                "confidence": "geometry_margin_position",
                "evidence": "Vertical stroke near right margin with no nearby Coptic context; assigned as closing bracket.",
                "source": "build_contextual_review.py",
                "geometry": {
                    "width": width,
                    "height": height,
                    "warped_bbox": [left, top, right, bottom],
                },
            }
        return None
    rule_id = "vertical_bracket_word_context_iota" if bracket_labeled else "vertical_split_word_context_iota"
    evidence = (
        "Short baseline-crossing vertical stroke assigned as a bracket, but embedded between nearby Coptic base glyphs."
        if bracket_labeled
        else "Short baseline-crossing vertical stroke in an unresolved vertical-split cluster; iota candidate is supported by nearby Coptic base glyphs."
    )
    return {
        "id": rule_id,
        "label": "ⲓ",
        "confidence": "geometry_word_context",
        "evidence": evidence,
        "source": "build_contextual_review.py",
        "geometry": {
            "width": width,
            "height": height,
            "warped_bbox": [left, top, right, bottom],
        },
    }


def split_metadata_from_item(item: dict[str, Any]) -> dict[str, Any] | None:
    if "parent_blob_id" not in item:
        return None
    fields = [
        "source_blob_id",
        "parent_blob_id",
        "split_child_index",
        "split_child_count",
        "split_expected_text",
        "split_expected_base",
        "split_method",
        "split_reason",
        "split_confidence",
        "split_valley_ratio",
        "parent_warped_bbox",
        "cut_positions",
    ]
    return {field: item.get(field) for field in fields if field in item}


def build_line_sequences(
    assignments: list[dict[str, Any]],
    reverse: dict[str, str],
    review_by_cluster: dict[str, dict[str, Any]],
    manual_overrides: dict[tuple[str, int, int], dict[str, Any]],
    manual_warnings: dict[tuple[str, int, int], dict[str, Any]],
    subcluster_overrides: dict[tuple[str, int, int], dict[str, Any]],
    geometric_overrides: dict[tuple[str, int, int], dict[str, Any]],
    editorial_overrides: dict[tuple[str, int, int], dict[str, Any]],
    line_widths: dict[tuple[str, int], int] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for item in assignments:
        grouped[(str(item["page"]), int(item["line_index"]))].append(item)

    missing: list[dict[str, Any]] = []
    line_sequences: list[dict[str, Any]] = []
    line_widths = line_widths or {}
    for (page, line_index), line_items in tqdm(sorted(grouped.items()), desc="line sequences", unit="line"):
        ordered = sorted(line_items, key=lambda row: (int(row["warped_bbox"][0]), int(row["warped_bbox"][1]), int(row["blob_id"])))
        fallback_width = max(int(row["warped_bbox"][2]) for row in ordered) + 1 if ordered else 1
        has_actual_line_width = (page, line_index) in line_widths
        line_width = line_widths.get((page, line_index), fallback_width)
        tokens = []
        for position, item in enumerate(ordered):
            previous_gap = None
            next_gap = None
            if position > 0:
                previous_gap = int(item["warped_bbox"][0]) - int(ordered[position - 1]["warped_bbox"][2]) - 1
            if position + 1 < len(ordered):
                next_gap = int(ordered[position + 1]["warped_bbox"][0]) - int(item["warped_bbox"][2]) - 1

            cluster_id = cluster_key(item["cluster"])
            label = reverse.get(cluster_id)
            key = (page, line_index, int(item["blob_id"]))
            manual_override = manual_overrides.get(key)
            manual_warning = manual_warnings.get(key)
            subcluster_override = subcluster_overrides.get(key)
            geometric_override = geometric_overrides.get(key)
            editorial_override = editorial_overrides.get(key)
            review = cluster_id in review_by_cluster
            review_item = review_by_cluster.get(cluster_id, {}) if review else {}
            candidates = candidate_list(review_item) if review else []
            review_decision = review_item.get("decision", {}) if review else {}
            word_context_iota = vertical_word_context_iota_override(
                item,
                position,
                ordered,
                page,
                line_index,
                reverse,
                manual_overrides,
                subcluster_overrides,
                geometric_overrides,
                label,
                candidates,
                review_decision,
                line_width,
            )
            if geometric_override is None and word_context_iota is not None:
                geometric_override = word_context_iota
                # Cascade: make this iota visible to subsequent neighbor checks
                geometric_overrides[key] = word_context_iota
            split_expected_base = item.get("split_expected_base")
            if split_expected_base and split_expected_base not in candidates:
                candidates.insert(0, str(split_expected_base))
            edge_fragment = is_edge_fragment(item, line_width, has_actual_line_width)
            if edge_fragment:
                label = None
                manual_override = None
                manual_warning = None
                subcluster_override = None
                geometric_override = None
                editorial_override = None
                review = False
                candidates = []
            if (
                label is None
                and not review
                and not split_expected_base
                and not edge_fragment
                and manual_override is None
                and subcluster_override is None
                and geometric_override is None
                and editorial_override is None
            ):
                missing.append({
                    "page": page,
                    "line_index": line_index,
                    "blob_id": int(item["blob_id"]),
                    "cluster": cluster_id,
                })
            tokens.append({
                "page": page,
                "line_index": line_index,
                "blob_id": int(item["blob_id"]),
                "split_metadata": split_metadata_from_item(item),
                "split_expected_base": split_expected_base,
                "split_expected_text": item.get("split_expected_text"),
                "cluster": cluster_id,
                "label": label,
                "manual_override": manual_override,
                "manual_warning": manual_warning,
                "subcluster_override": subcluster_override,
                "geometric_override": geometric_override,
                "editorial_override": editorial_override,
                "review": review,
                "candidates": candidates,
                "edge_fragment": edge_fragment,
                "geometry": geometry_from_item(item, line_width, previous_gap, next_gap),
            })
        line_sequences.append({"page": page, "line_index": line_index, "tokens": tokens})
    return line_sequences, missing


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * percent / 100.0
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return float(ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction)


def geometry_summary(tokens: list[dict[str, Any]]) -> dict[str, float]:
    widths = [float(token["geometry"]["width"]) for token in tokens]
    heights = [float(token["geometry"]["height"]) for token in tokens]
    areas = [float(token["geometry"]["area"]) for token in tokens]
    aspects = [float(token["geometry"]["aspect"]) for token in tokens]
    baseline = [float(token["geometry"]["baseline_delta"]) for token in tokens]
    return {
        "width_p10": round(percentile(widths, 10), 2),
        "width_p50": round(percentile(widths, 50), 2),
        "width_p90": round(percentile(widths, 90), 2),
        "height_p10": round(percentile(heights, 10), 2),
        "height_p50": round(percentile(heights, 50), 2),
        "height_p90": round(percentile(heights, 90), 2),
        "area_p50": round(percentile(areas, 50), 2),
        "aspect_p50": round(percentile(aspects, 50), 4),
        "baseline_delta_p50": round(percentile(baseline, 50), 2),
    }


def collect_reference_stats(line_sequences: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    values: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for line in line_sequences:
        for token in line["tokens"]:
            label = token.get("label")
            if not label:
                continue
            geometry = token["geometry"]
            labels = [label]
            if not label.startswith("_") and len(label) > 1:
                labels.append(CONNECTED_REFERENCE)
            for stats_label in labels:
                for field in ("width", "height", "area", "aspect", "baseline_delta"):
                    values[stats_label][field].append(float(geometry[field]))

    stats: dict[str, dict[str, Any]] = {}
    for label, field_values in values.items():
        stats[label] = {}
        for field, numbers in field_values.items():
            center = median(numbers)
            deviations = [abs(number - center) for number in numbers]
            stats[label][field] = {
                "median": round(float(center), 4),
                "mad": round(float(max(median(deviations), 0.5)), 4),
            }
    return stats


def build_bigrams(line_sequences: list[dict[str, Any]]) -> tuple[Counter[tuple[str, str]], Counter[str], set[str]]:
    bigrams: Counter[tuple[str, str]] = Counter()
    totals: Counter[str] = Counter()
    vocabulary: set[str] = set()
    for line in line_sequences:
        labels = [token.get("label") for token in line["tokens"]]
        for label in labels:
            if label:
                vocabulary.add(label)
        previous = "<BOL>"
        for label in labels:
            if label is None:
                previous = "<GAP>"
                continue
            bigrams[(previous, label)] += 1
            totals[previous] += 1
            previous = label
        bigrams[(previous, "<EOL>")] += 1
        totals[previous] += 1
    vocabulary.update({"<BOL>", "<EOL>", "<GAP>"})
    return bigrams, totals, vocabulary


def context_probability_score(
    left_label: str | None,
    candidate: str,
    right_label: str | None,
    bigrams: Counter[tuple[str, str]],
    totals: Counter[str],
    vocabulary_size: int,
) -> float:
    if candidate == CONNECTED_REVIEW:
        return 0.0
    smoothing = 0.5
    score = 0.0
    if left_label:
        numerator = bigrams[(left_label, candidate)] + smoothing
        denominator = totals[left_label] + smoothing * vocabulary_size
        score += math.log(numerator / max(denominator, 1e-9))
    if right_label:
        numerator = bigrams[(candidate, right_label)] + smoothing
        denominator = totals[candidate] + smoothing * vocabulary_size
        score += math.log(numerator / max(denominator, 1e-9))
    return score


def geometry_fit_score(candidate: str, geometry: dict[str, Any], reference_stats: dict[str, dict[str, Any]]) -> float:
    stats_key = CONNECTED_REFERENCE if candidate == CONNECTED_REVIEW else candidate
    stats = reference_stats.get(stats_key)
    if not stats:
        return 0.0
    weights = {
        "width": 0.7,
        "height": 0.7,
        "area": 0.35,
        "aspect": 0.45,
        "baseline_delta": 0.25,
    }
    penalty = 0.0
    for field, weight in weights.items():
        center = float(stats[field]["median"])
        spread = max(float(stats[field]["mad"]) * 1.4826, 0.75)
        penalty += weight * abs(float(geometry[field]) - center) / spread
    return -penalty


def score_candidates(
    token: dict[str, Any],
    candidates: list[str],
    projection_counts: Counter[str],
    projection_total: int,
    left_label: str | None,
    right_label: str | None,
    reference_stats: dict[str, dict[str, Any]],
    bigrams: Counter[tuple[str, str]],
    bigram_totals: Counter[str],
    vocabulary_size: int,
) -> list[dict[str, Any]]:
    scored = []
    for candidate in candidates:
        share = projection_counts.get(candidate, 0) / max(projection_total, 1)
        prior_score = 3.0 * math.log(max(share, 0.001))
        if candidate == CONNECTED_REVIEW and share < 0.5:
            prior_score -= 10.0
        if candidate == CONNECTED_REVIEW and share < 0.2:
            prior_score -= 6.0
        total = (
            prior_score
            + geometry_fit_score(candidate, token["geometry"], reference_stats)
            + 0.6 * context_probability_score(left_label, candidate, right_label, bigrams, bigram_totals, vocabulary_size)
        )
        scored.append({
            "candidate": candidate,
            "total": round(total, 4),
            "prior_share": round(share, 4),
        })
    return sorted(scored, key=lambda item: item["total"], reverse=True)


def immediate_context(tokens: list[dict[str, Any]], position: int) -> tuple[str | None, str | None]:
    left_label = tokens[position - 1].get("label") if position > 0 else "<BOL>"
    right_label = tokens[position + 1].get("label") if position + 1 < len(tokens) else "<EOL>"
    return left_label, right_label


def context_value(label: str | None) -> str:
    return label if label is not None else "?"


def token_window(tokens: list[dict[str, Any]], position: int, window: int) -> str:
    start = max(0, position - window)
    end = min(len(tokens), position + window + 1)
    parts = []
    for index in range(start, end):
        token = tokens[index]
        if index == position:
            parts.append(f"[c{token['cluster']}]")
        else:
            parts.append(token.get("label") or "?")
    return "".join(parts)


def top_projection_label(counts: Counter[str]) -> tuple[str | None, int]:
    if not counts:
        return None, 0
    label, count = counts.most_common(1)[0]
    return label, int(count)


def character_candidates(candidates: list[str]) -> list[str]:
    return [candidate for candidate in candidates if not candidate.startswith("_")]


def make_decision(
    candidates: list[str],
    counts: Counter[str],
    total: int,
    geometry: dict[str, float],
) -> dict[str, str | None]:
    top_label, top_count = top_projection_label(counts)
    top_share = top_count / max(total, 1)
    connected_share = counts.get(CONNECTED_REVIEW, 0) / max(total, 1)
    dot_share = counts.get("_lacuna_dot", 0) / max(total, 1)
    unknown_share = counts.get("_unknown", 0) / max(total, 1)
    bracket_shares = {label: counts.get(label, 0) / max(total, 1) for label in BRACKET_LABELS}
    iota_share = counts.get("ⲓ", 0) / max(total, 1)
    letters = character_candidates(candidates)
    is_vertical = geometry["width_p50"] <= 10 and geometry["height_p50"] >= 16
    is_dot_like = geometry["width_p50"] <= 6 and geometry["height_p50"] <= 8

    if top_label == CONNECTED_REVIEW and top_share >= 0.75:
        return {
            "label": CONNECTED_REVIEW,
            "confidence": "needs_literal_reading",
            "action": "Inspect page-line examples and assign a literal connected reading only if stable.",
        }
    if connected_share >= 0.2 and top_share < 0.75:
        return {
            "label": None,
            "confidence": "needs_subcluster",
            "action": "Mixed connected and single-character evidence; split before assigning.",
        }
    if is_dot_like and top_label == "_lacuna_dot" and dot_share >= 0.8:
        return {
            "label": "_lacuna_dot",
            "confidence": "strong_contextual",
            "action": "Safe mark/lacuna-dot assignment candidate.",
        }
    if is_dot_like and top_label in MARK_LABELS:
        if abs(dot_share - unknown_share) <= 0.2:
            return {
                "label": None,
                "confidence": "needs_mark_split",
                "action": "Dot/unknown mixture; keep as review or split marks from noise.",
            }
        return {
            "label": top_label,
            "confidence": "moderate_contextual",
            "action": "Mark-like cluster; verify against image before assignment.",
        }
    for bracket_label, share in bracket_shares.items():
        if share >= 0.75:
            if geometry["height_p50"] < 30 or geometry["width_p50"] > 11:
                return {
                    "label": None,
                    "confidence": "needs_editorial_or_shape_split",
                    "action": "Bracket projection dominates, but shape is not full-height bracket geometry; keep unresolved and split editorial/noise families before assigning.",
                }
            return {
                "label": bracket_label,
                "confidence": "moderate_contextual",
                "action": "Bracket-like projection dominates; verify against line margins and lacuna context.",
            }
    if is_vertical and (top_label == "ⲓ" or iota_share >= 0.1 or any(share > 0.05 for share in bracket_shares.values())):
        return {
            "label": None,
            "confidence": "needs_vertical_split",
            "action": "Vertical stroke/bracket ambiguity; split by margin position, height, and neighboring lacuna marks.",
        }
    if top_label in MARK_LABELS and geometry["width_p50"] >= 12:
        return {
            "label": None,
            "confidence": "needs_noise_split",
            "action": "Wide mark/line contamination; do not assign as a character.",
        }
    if letters and top_label in letters:
        if top_share >= 0.85:
            return {
                "label": top_label,
                "confidence": "strong_contextual",
                "action": "High projection purity; verify sample contexts before moving from review.",
            }
        if top_share >= 0.7:
            return {
                "label": top_label,
                "confidence": "tentative_primary",
                "action": "Primary character is plausible, but contamination remains; inspect or subcluster.",
            }
        return {
            "label": None,
            "confidence": "needs_character_split",
            "action": "Character candidates are mixed; use context and geometry for per-blob resolution.",
        }
    return {
        "label": top_label,
        "confidence": "needs_review",
        "action": "No safe global assignment.",
    }


def pick_examples(cluster_tokens: list[tuple[dict[str, Any], int, list[dict[str, Any]], list[dict[str, Any]]]], limit: int) -> list[tuple[dict[str, Any], int, list[dict[str, Any]], list[dict[str, Any]]]]:
    if len(cluster_tokens) <= limit:
        return cluster_tokens
    picked = []
    seen_pages = set()
    step = max(1, len(cluster_tokens) // (limit * 3))
    for item in cluster_tokens[::step]:
        token = item[0]
        if token["page"] in seen_pages and len(seen_pages) < limit:
            continue
        picked.append(item)
        seen_pages.add(token["page"])
        if len(picked) >= limit:
            break
    if len(picked) < limit:
        for item in cluster_tokens:
            if item not in picked:
                picked.append(item)
            if len(picked) >= limit:
                break
    return picked


def build_review_context(
    line_sequences: list[dict[str, Any]],
    review_by_cluster: dict[str, dict[str, Any]],
    examples_per_cluster: int,
    window: int,
) -> list[dict[str, Any]]:
    reference_stats = collect_reference_stats(line_sequences)
    bigrams, bigram_totals, vocabulary = build_bigrams(line_sequences)
    vocabulary_size = max(1, len(vocabulary))
    cluster_tokens: dict[str, list[tuple[dict[str, Any], int, list[dict[str, Any]], list[dict[str, Any]]]]] = defaultdict(list)

    for line in line_sequences:
        tokens = line["tokens"]
        for position, token in enumerate(tokens):
            if token["review"]:
                cluster_tokens[token["cluster"]].append((token, position, tokens, token["candidates"]))

    review_rows = []
    for cluster_id in tqdm(sorted(review_by_cluster), desc="review clusters", unit="cluster"):
        review_item = review_by_cluster[cluster_id]
        tokens_for_cluster = cluster_tokens.get(cluster_id, [])
        tokens_only = [item[0] for item in tokens_for_cluster]
        counts = candidate_counts(review_item)
        candidates = candidate_list(review_item)
        total = int(review_item.get("total", len(tokens_only)))
        geometry = geometry_summary(tokens_only)
        left_context = Counter()
        right_context = Counter()
        windows = Counter()
        score_wins = Counter()
        scores_by_candidate: dict[str, list[float]] = defaultdict(list)
        example_rows = []

        for token, position, line_tokens, _candidate_list in tokens_for_cluster:
            left_label, right_label = immediate_context(line_tokens, position)
            left_context[context_value(left_label)] += 1
            right_context[context_value(right_label)] += 1
            windows[token_window(line_tokens, position, window)] += 1
            scored = score_candidates(
                token,
                candidates,
                counts,
                total,
                left_label,
                right_label,
                reference_stats,
                bigrams,
                bigram_totals,
                vocabulary_size,
            )
            if scored:
                score_wins[scored[0]["candidate"]] += 1
                for score in scored:
                    scores_by_candidate[score["candidate"]].append(float(score["total"]))

        for token, position, line_tokens, _candidate_list in pick_examples(tokens_for_cluster, examples_per_cluster):
            left_label, right_label = immediate_context(line_tokens, position)
            scored = score_candidates(
                token,
                candidates,
                counts,
                total,
                left_label,
                right_label,
                reference_stats,
                bigrams,
                bigram_totals,
                vocabulary_size,
            )[:3]
            example_rows.append({
                "page": token["page"],
                "line_index": token["line_index"],
                "blob_id": token["blob_id"],
                "cluster": token["cluster"],
                "position": position,
                "window": token_window(line_tokens, position, window),
                "left_context": context_value(left_label),
                "right_context": context_value(right_label),
                "candidates": candidates,
                "geometry": token["geometry"],
                "scores": scored,
            })

        decision = make_decision(candidates, counts, total, geometry)
        review_rows.append({
            "cluster": cluster_id,
            "occurrences": len(tokens_only),
            "projection": review_item,
            "candidates": candidates,
            "decision": decision,
            "candidate_scores": [
                {
                    "candidate": candidate,
                    "wins": int(score_wins[candidate]),
                    "win_rate": round(score_wins[candidate] / max(len(tokens_only), 1), 4),
                    "mean_total_score": round(sum(scores_by_candidate[candidate]) / max(len(scores_by_candidate[candidate]), 1), 4),
                }
                for candidate in sorted(scores_by_candidate, key=lambda value: (-score_wins[value], value))
            ],
            "geometry": geometry,
            "left_context": [{"value": label, "count": count} for label, count in left_context.most_common(8)],
            "right_context": [{"value": label, "count": count} for label, count in right_context.most_common(8)],
            "windows": [{"value": value, "count": count} for value, count in windows.most_common(8)],
            "examples": example_rows,
        })
    return review_rows


def projection_cell(review_item: dict[str, Any], max_items: int = 3) -> str:
    total = max(1, int(review_item.get("total", 0)))
    parts = []
    for label, count in candidate_counts(review_item).most_common(max_items):
        parts.append(f"{label}:{count} ({count / total:.1%})")
    return "; ".join(parts)


def score_cell(row: dict[str, Any], max_items: int = 2) -> str:
    parts = []
    for score in row.get("candidate_scores", [])[:max_items]:
        parts.append(f"{score['candidate']} {score['win_rate']:.1%}")
    return "; ".join(parts) if parts else ""


def context_cell(values: list[dict[str, Any]], max_items: int = 3) -> str:
    return "; ".join(f"{item['value']}:{item['count']}" for item in values[:max_items])


def write_line_sequences(path: Path, line_sequences: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for line in line_sequences:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")


def write_markdown_reports(
    context_path: Path,
    decision_path: Path,
    clusters_dir: Path,
    line_sequences: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
    missing: list[dict[str, Any]],
) -> None:
    total_units = sum(len(line["tokens"]) for line in line_sequences)
    review_units = sum(row["occurrences"] for row in review_rows)
    lines_with_review = sum(1 for line in line_sequences if any(token["review"] for token in line["tokens"]))

    header = [
        "# Kephalaia OCR Contextual Sequence Review",
        "",
        f"Clusters directory: `{clusters_dir.relative_to(REPO)}`",
        "Source basis: blob order, cluster ids, active cluster assignments, and geometry only.",
        f"Lines exported: {len(line_sequences)}",
        f"Lines with review clusters: {lines_with_review}",
        f"Total units: {total_units}",
        f"Review units: {review_units}",
        f"Missing assignment links: {len(missing)}",
        "",
    ]
    table_header = [
        "## Review Cluster Decision Table",
        "",
        "| Cluster | N | Projection | Candidates | Geometry p50 | Decision | Confidence | Action | Context |",
        "|---|---:|---|---|---|---|---|---|---|",
    ]
    table_rows = []
    for row in review_rows:
        decision = row["decision"]
        geometry = row["geometry"]
        table_rows.append(
            "| "
            + " | ".join([
                row["cluster"],
                str(row["occurrences"]),
                projection_cell(row["projection"]),
                ", ".join(row["candidates"]),
                f"w{geometry['width_p50']} h{geometry['height_p50']} a{geometry['area_p50']}",
                decision.get("label") or "review",
                decision.get("confidence") or "needs_review",
                decision.get("action") or "",
                f"L {context_cell(row['left_context'])}; R {context_cell(row['right_context'])}",
            ])
            + " |"
        )

    decision_text = "\n".join(header + table_header + table_rows) + "\n"
    decision_path.write_text(decision_text, encoding="utf-8")

    example_lines = [
        *header,
        *table_header,
        *table_rows,
        "",
        "## Examples",
        "",
    ]
    for row in review_rows:
        example_lines.append(f"### Cluster {row['cluster']}")
        example_lines.append("")
        for example in row["examples"]:
            scores = ", ".join(f"{score['candidate']}:{score['total']}" for score in example["scores"])
            geometry = example["geometry"]
            example_lines.append(
                f"- p{example['page']} l{example['line_index']} b{example['blob_id']}: "
                f"`{example['window']}`; w={geometry['width']} h={geometry['height']} "
                f"area={geometry['area']} gap=({geometry['previous_gap']},{geometry['next_gap']}); scores={scores}"
            )
        example_lines.append("")
    context_path.write_text("\n".join(example_lines), encoding="utf-8")


def run(args: argparse.Namespace) -> Path:
    clusters_dir = resolve_repo_path(args.clusters_dir, OCR_ROOT / "clusters_shape_padded_k120")
    context_dir = resolve_repo_path(args.context_dir, OCR_ROOT / "contextual_review" / clusters_dir.name)
    context_dir.mkdir(parents=True, exist_ok=True)

    char_assignment_path = clusters_dir / "_char_assignments_projected.json"
    manual_override_path = clusters_dir / "_manual_glyph_overrides.json"
    split_child_override_path = clusters_dir / "_split_child_glyph_overrides.json"
    carried_blob_override_path = clusters_dir / "_carried_blob_glyph_overrides.json"
    geometric_override_path = clusters_dir / "_geometric_glyph_overrides.json"
    editorial_override_path = clusters_dir / "_editorial_word_overrides.json"
    blob_assignment_path = clusters_dir / "_assignments.json"
    char_data = load_json(char_assignment_path)
    blob_assignments = load_json(blob_assignment_path)
    assignments_by_label = char_data.get("assignments", char_data)
    review_by_cluster = {cluster_key(item["cluster"]): item for item in char_data.get("review_clusters", [])}
    reverse = active_reverse_map(assignments_by_label)
    manual_warnings: dict[tuple[str, int, int], dict[str, Any]] = {}
    manual_warnings.update(load_manual_overrides(carried_blob_override_path, include_warning_rows=True))
    manual_warnings.update(load_manual_overrides(manual_override_path, include_warning_rows=True))
    manual_overrides = load_manual_overrides(manual_override_path)
    carried_blob_overrides = load_manual_overrides(carried_blob_override_path)
    split_child_overrides = load_manual_overrides(split_child_override_path)
    merged_manual_overrides: dict[tuple[str, int, int], dict[str, Any]] = {}
    merged_manual_overrides.update(split_child_overrides)
    merged_manual_overrides.update(carried_blob_overrides)
    merged_manual_overrides.update(manual_overrides)
    manual_overrides = merged_manual_overrides
    subcluster_overrides = load_subcluster_overrides(clusters_dir)
    geometric_overrides = load_geometric_overrides(geometric_override_path, clusters_dir)
    editorial_overrides = load_editorial_overrides(editorial_override_path)
    split_dir = resolve_repo_path(args.split_dir, OCR_ROOT / "pages") if args.split_dir else split_dir_from_cluster_summary(clusters_dir)
    line_widths = load_line_widths(split_dir)

    line_sequences, missing = build_line_sequences(
        blob_assignments,
        reverse,
        review_by_cluster,
        manual_overrides,
        manual_warnings,
        subcluster_overrides,
        geometric_overrides,
        editorial_overrides,
        line_widths,
    )
    review_rows = build_review_context(line_sequences, review_by_cluster, args.examples, args.window)

    write_line_sequences(context_dir / "line_sequences.jsonl", line_sequences)
    dump_json(context_dir / "missing_assignments.json", missing)
    dump_json(context_dir / "review_cluster_context.json", review_rows)
    write_markdown_reports(
        context_dir / "review_cluster_context.md",
        context_dir / "review_cluster_decision_table.md",
        clusters_dir,
        line_sequences,
        review_rows,
        missing,
    )
    # Record provenance so downstream stages (build_llm_witness,
    # build_page_review_sheet) can resolve the matching split layer
    # automatically. Without this, defaulting to OCR_ROOT / "pages"
    # silently drops blobs that only exist in the split-chars layer
    # this clusters_dir was built against.
    try:
        clusters_rel = str(clusters_dir.relative_to(REPO)).replace("\\", "/")
    except ValueError:
        clusters_rel = str(clusters_dir)
    try:
        split_rel = str(split_dir.relative_to(REPO)).replace("\\", "/") if split_dir else None
    except ValueError:
        split_rel = str(split_dir) if split_dir else None
    dump_json(
        context_dir / "_summary.json",
        {
            "clusters_dir": clusters_rel,
            "split_dir": split_rel,
        },
    )
    print(context_dir)
    return context_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clusters-dir", default=None)
    parser.add_argument("--context-dir", default=None)
    parser.add_argument("--split-dir", default=None)
    parser.add_argument("--max-workers", type=int, default=4, help="Reserved for compatibility with OCR pipeline commands.")
    parser.add_argument("--examples", type=int, default=8)
    parser.add_argument("--window", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()