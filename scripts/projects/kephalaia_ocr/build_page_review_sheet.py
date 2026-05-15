#!/usr/bin/env python3
"""Build page-level manuscript review sheets for Kephalaia OCR output.

Each output image contains one row per manuscript line:
  1. a cut-out of the manuscript line,
  2. the current most probable character labels aligned below the blobs,
  3. a page-local index number below each displayed character.

The sheet is a review aid only. Labels are derived from current assignments,
contextual review decisions, and constrained witness evidence; the manuscript
image and blob geometry remain authoritative.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import unicodedata
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

REPO = Path(__file__).resolve().parents[3]
OCR_ROOT = REPO / "output" / "projects" / "kephalaia_ocr"
PAGES_DIR = OCR_ROOT / "pages"
BASE_SPLIT_DIR = PAGES_DIR
DEFAULT_CLUSTER_NAME = "clusters_shape_padded_k120"
DEFAULT_CONTEXT_DIR = OCR_ROOT / "contextual_review" / DEFAULT_CLUSTER_NAME
DEFAULT_WITNESS_DIR = OCR_ROOT / "llm_witness" / DEFAULT_CLUSTER_NAME
DEFAULT_OUT_DIR = OCR_ROOT / "page_review_sheets"
DEFAULT_ARTIFACT_DIR = REPO / "temp" / "projects" / "kephalaia_ocr" / "page_review_sheets"
LINE_OWNERSHIP_TOLERANCE_PX = 6.0

def resolve_repo_path(path: Path | None) -> Path | None:
    if path is None or path.is_absolute():
        return path
    return REPO / path

SPECIAL_DISPLAY = {
    "_lacuna_dot": ".",
    "_middle_dot": "·",
    "_unknown": "?",
    "_left_square_bracket": "[",
    "_right_square_bracket": "]",
    "_connected_needs_literal_reading": "?",
    "_literal_connected_reference": "?",
    "_editorial_marker": "E",
}

COMBINING_MARKS = {
    "overline": "\u0304",
    "horizontal_mark": "\u0304",
    "above_dot": "\u0307",
    "dot": "\u0307",
    "diaeresis": "\u0308",
    "below_dot": "\u0323",
}

MARK_ORDER = ("overline", "horizontal_mark", "diaeresis", "above_dot", "dot", "below_dot")
OVERLINE_MARK_KINDS = {"overline", "horizontal_mark"}
OVERLINE_CODEPOINTS = {"\u0304", "\u0305", "\ufe24", "\ufe25", "\ufe26"}
CONJOINING_MACRON_LEFT = "\ufe24"
CONJOINING_MACRON_RIGHT = "\ufe25"
CONJOINING_MACRON_MIDDLE = "\ufe26"

MARK_COLORS = {
    "overline": (20, 80, 180),
    "horizontal_mark": (20, 80, 180),
    "above_dot": (145, 45, 150),
    "below_dot": (30, 130, 80),
    "other_mark": (180, 95, 0),
}

COLOR_ASSIGNED = (20, 20, 20)
COLOR_PROBABLE = (20, 70, 170)
COLOR_CONTEXT = COLOR_PROBABLE
COLOR_LLM = COLOR_PROBABLE
COLOR_CANDIDATE = COLOR_PROBABLE
COLOR_SPECIAL = COLOR_PROBABLE
COLOR_UNKNOWN = COLOR_PROBABLE
COLOR_EDITORIAL = (185, 95, 0)
COLOR_INDEX = (80, 80, 80)
COLOR_ROW_LABEL = (120, 120, 120)
COLOR_BACKGROUND = (248, 248, 246)
BLOCK_CANDIDATE_CONFIDENCES = {
    "needs_editorial_or_shape_split",
    "needs_vertical_split",
    "needs_character_split",
    "needs_noise_split",
    "needs_mark_split",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_clean_lines(page: str, cache: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    if page not in cache:
        path = PAGES_DIR / f"kraken_p{page}_body_clean.json"
        data = load_json(path) if path.exists() else {}
        cache[page] = [line for line in data.get("lines", []) if line.get("baseline")]
    return cache[page]


def baseline_y_at_x(line: dict[str, Any], x: float) -> float | None:
    baseline = line.get("baseline") or []
    if len(baseline) < 2:
        return None
    x0, y0 = [float(value) for value in baseline[0]]
    x1, y1 = [float(value) for value in baseline[1]]
    if x1 == x0:
        return y0
    ratio = (x - x0) / (x1 - x0)
    return y0 + ratio * (y1 - y0)


def blob_img_center(blob: dict[str, Any]) -> tuple[float, float] | None:
    quad = blob.get("img_quad") or []
    if not quad:
        return None
    xs = [float(point[0]) for point in quad]
    ys = [float(point[1]) for point in quad]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def line_distance_candidates(page: str, x: float, y: float, clean_cache: dict[str, list[dict[str, Any]]]) -> list[tuple[float, int]]:
    candidates: list[tuple[float, int]] = []
    for line in load_clean_lines(page, clean_cache):
        baseline_y = baseline_y_at_x(line, x)
        if baseline_y is None:
            continue
        candidates.append((abs(y - baseline_y), int(line["index"])))
    candidates.sort(key=lambda item: item[0])
    return candidates


def nearest_clean_line_index(page: str, x: float, y: float, clean_cache: dict[str, list[dict[str, Any]]]) -> int | None:
    candidates = line_distance_candidates(page, x, y, clean_cache)
    if not candidates:
        return None
    return candidates[0][1]


def blob_belongs_to_line(page: str, line_index: int, blob: dict[str, Any], clean_cache: dict[str, list[dict[str, Any]]]) -> bool:
    center = blob_img_center(blob)
    if center is None:
        return True
    candidates = line_distance_candidates(page, center[0], center[1], clean_cache)
    if not candidates:
        return True
    owner_distance, owner = candidates[0]
    if owner == line_index:
        return True
    current_distances = [distance for distance, index in candidates if index == line_index]
    return bool(current_distances and current_distances[0] <= owner_distance + LINE_OWNERSHIP_TOLERANCE_PX)


def normalize_page(page: str | int) -> str:
    text = str(page)
    return f"{int(text):03d}" if text.isdigit() else text


def is_coptic_text(value: str | None) -> bool:
    if not value:
        return False
    for char in value:
        if unicodedata.combining(char):
            continue
        codepoint = ord(char)
        if 0x03E2 <= codepoint <= 0x03EF:
            continue
        if 0x2C80 <= codepoint <= 0x2CFF:
            continue
        return False
    return True


def split_display_units(text: str) -> list[str]:
    units: list[str] = []
    for char in text:
        if unicodedata.combining(char) and units:
            units[-1] += char
        else:
            units.append(char)
    return units or ["?"]


def strip_combining_marks(text: str) -> str:
    return "".join(char for char in text if not unicodedata.combining(char))


def combining_marks_for(mark_kinds: list[str]) -> list[str]:
    counts = Counter(mark_kinds)
    marks: list[str] = []
    for kind in MARK_ORDER:
        if counts[kind] <= 0:
            continue
        if kind == "above_dot" and counts[kind] >= 2:
            marks.append(COMBINING_MARKS["diaeresis"])
            continue
        mark = COMBINING_MARKS.get(kind)
        if mark:
            marks.append(mark)
    return marks


def add_combining_marks(text: str, mark_kinds: list[str]) -> str:
    marks = combining_marks_for(mark_kinds)
    if not marks or not is_coptic_text(text):
        return text
    units = split_display_units(text)
    marked = []
    for index, unit in enumerate(units):
        if any(unicodedata.combining(char) for char in unit):
            marked.append(unit)
        elif len(units) == 1 or any(kind in {"overline", "horizontal_mark"} for kind in mark_kinds):
            marked.append(unit + "".join(marks))
        elif index == len(units) - 1:
            marked.append(unit + "".join(marks))
        else:
            marked.append(unit)
    return "".join(marked)


def label_to_text(label: str | None) -> str | None:
    if label is None:
        return None
    if is_coptic_text(label):
        return label
    return SPECIAL_DISPLAY.get(label)


def token_is_dot_like(token: dict[str, Any]) -> bool:
    geometry = token.get("geometry") or {}
    width = float(geometry.get("width", 999))
    height = float(geometry.get("height", 999))
    area = float(geometry.get("area", 999))
    return width <= 7 and height <= 8 and area <= 35


def special_label_to_text(label: str | None, token: dict[str, Any]) -> str | None:
    if label == "_unknown" and token_is_dot_like(token):
        return "."
    return label_to_text(label)


def first_displayable_candidate(candidates: list[str]) -> tuple[str | None, str]:
    for candidate in candidates:
        text = label_to_text(candidate)
        if text is not None:
            return text, candidate
    return None, ""


def load_review_decisions(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    decisions: dict[str, dict[str, Any]] = {}
    for item in load_json(path):
        decisions[str(item.get("cluster"))] = item.get("decision", {})
    return decisions


def load_page_sequences(
    pages: set[str], witness_path: Path, line_sequences_path: Path, use_witness: bool
) -> tuple[dict[str, dict[int, list[dict[str, Any]]]], Path, str]:
    source_path = witness_path if use_witness and witness_path.exists() else line_sequences_path
    unit_key = "units" if source_path == witness_path else "tokens"
    page_lines: dict[str, dict[int, list[dict[str, Any]]]] = {page: {} for page in pages}
    with source_path.open("r", encoding="utf-8") as stream:
        for raw_line in stream:
            if not raw_line.strip():
                continue
            line = json.loads(raw_line)
            page = normalize_page(line.get("page"))
            if page not in pages:
                continue
            page_lines[page][int(line["line_index"])] = line.get(unit_key, [])
    return page_lines, source_path, unit_key


def choose_display_label(
    token: dict[str, Any], review_decisions: dict[str, dict[str, Any]], inline_marks: bool
) -> tuple[str, str, tuple[int, int, int], str]:
    editorial_override = token.get("editorial_override") or {}
    editorial_label = editorial_override.get("label")
    if editorial_label:
        confidence = editorial_override.get("confidence") or "generated"
        if "display_text" in editorial_override:
            text = str(editorial_override.get("display_text"))
        else:
            text = str(SPECIAL_DISPLAY.get(editorial_label) or "E")
        return text, f"editorial_marker:{confidence}", COLOR_EDITORIAL, str(editorial_label)

    final_label = token.get("final_label")
    final_source = str(token.get("final_label_source") or "")
    if inline_marks and final_label and is_coptic_text(str(final_label)):
        geometry_marks = token.get("geometry_mark_kinds", [])
        color = COLOR_ASSIGNED if final_source == "assigned" and not geometry_marks else COLOR_PROBABLE
        return str(final_label), f"final:{final_source or 'geometry'}", color, str(token.get("label") or final_label)

    manual_override = token.get("manual_override") or {}
    manual_label = manual_override.get("label")
    text = special_label_to_text(manual_label, token)
    if text is not None:
        confidence = manual_override.get("confidence") or "manual"
        return text, f"manual_override:{confidence}", COLOR_CONTEXT, str(manual_label)

    geometric_override = token.get("geometric_override") or {}
    geometric_label = geometric_override.get("label")
    text = special_label_to_text(geometric_label, token)
    if text is not None:
        confidence = geometric_override.get("confidence") or "geometric"
        rule_id = geometric_override.get("id") or "rule"
        return text, f"geometric:{rule_id}:{confidence}", COLOR_CONTEXT, str(geometric_label)

    subcluster_override = token.get("subcluster_override") or {}
    subcluster_label = subcluster_override.get("label")
    text = special_label_to_text(subcluster_label, token)
    if text is not None:
        confidence = subcluster_override.get("confidence") or "manual"
        subcluster = subcluster_override.get("subcluster") or "unknown"
        return text, f"subcluster:{subcluster}:{confidence}", COLOR_CONTEXT, str(subcluster_label)

    raw_label = token.get("label")
    text = special_label_to_text(raw_label, token)
    source = "assigned"
    color = COLOR_ASSIGNED
    if text is None:
        decision = review_decisions.get(str(token.get("cluster")), {})
        decision_label = decision.get("label")
        text = special_label_to_text(decision_label, token)
        source = f"context:{decision.get('confidence', 'unknown')}"
        color = COLOR_CONTEXT
        raw_label = decision_label
        if text is None and decision.get("confidence") in BLOCK_CANDIDATE_CONFIDENCES:
            text = "?"
            color = COLOR_UNKNOWN

    if text is None:
        text, raw_candidate = first_displayable_candidate([str(c) for c in token.get("candidates", [])])
        source = "top_candidate"
        color = COLOR_CANDIDATE
        raw_label = raw_candidate or raw_label

    alignment = token.get("llm_alignment", {}) or {}
    llm_bases = alignment.get("llm_bases")
    llm_text = alignment.get("llm_text")
    if text is None and llm_bases and is_coptic_text(llm_bases):
        text = llm_text if llm_text and is_coptic_text(llm_text) else llm_bases
        source = "llm_rescue"
        color = COLOR_LLM
        raw_label = llm_bases

    if text is None:
        text = "?"
        source = "unresolved"
        color = COLOR_UNKNOWN

    if raw_label in SPECIAL_DISPLAY or not is_coptic_text(text):
        color = COLOR_PROBABLE

    mark_kinds = [str(mark.get("kind")) for mark in token.get("attached_marks", []) if mark.get("kind")]
    text_base = strip_combining_marks(text)
    if inline_marks and source != "llm_rescue":
        text = add_combining_marks(text, mark_kinds)
    else:
        text = text if source == "llm_rescue" else text_base

    return text, source, color, str(raw_label or "")


def attached_marks_for_display_unit(token: dict[str, Any], unit_position: int) -> list[dict[str, Any]]:
    marks: list[dict[str, Any]] = []
    for mark in token.get("attached_marks", []) or []:
        target_positions = mark.get("target_unit_positions")
        if target_positions is not None and unit_position not in {int(position) for position in target_positions}:
            continue
        marks.append(mark)
    return marks


def bbox_shape(blob: dict[str, Any]) -> tuple[int, int]:
    x0, y0, x1, y1 = [int(value) for value in blob["warped_bbox"]]
    return x1 - x0 + 1, y1 - y0 + 1


def classify_other_blob(blob: dict[str, Any], baseline_y: int) -> str:
    x0, y0, x1, y1 = [int(value) for value in blob["warped_bbox"]]
    width, height = bbox_shape(blob)
    center_y = (y0 + y1) / 2.0
    if width <= 7 and height <= 8:
        if center_y < baseline_y - 2:
            return "above_dot"
        if center_y > baseline_y + 2:
            return "below_dot"
    above = y1 < baseline_y - 6
    below = y0 > baseline_y + 6
    if above and width >= 8 and height <= 8:
        return "overline"
    if above and width <= 7 and height <= 8:
        return "above_dot"
    if below and width <= 7 and height <= 8:
        return "below_dot"
    if width >= 10 and height <= 10:
        return "horizontal_mark"
    return "other_mark"


def quad_bounds(quad: list[list[float]]) -> tuple[float, float, float, float]:
    xs = [float(point[0]) for point in quad]
    ys = [float(point[1]) for point in quad]
    return min(xs), min(ys), max(xs), max(ys)


def line_bounds(line: dict[str, Any], image_height: int, margin_y: int) -> tuple[int, int]:
    points = []
    for blob in line.get("blobs", []):
        points.extend(blob.get("img_quad", []))
    if not points:
        return 0, image_height
    ys = [float(point[1]) for point in points]
    y0 = max(0, int(min(ys)) - margin_y)
    y1 = min(image_height, int(max(ys)) + margin_y)
    if y1 <= y0:
        y1 = min(image_height, y0 + 1)
    return y0, y1


def font_candidates() -> list[Path]:
    return [
        REPO / "scripts" / "tools" / "fonts" / "NotoSansCoptic-Regular.ttf",
        REPO / "scripts" / "tools" / "fonts" / "Junicode-Regular.ttf",
        Path(r"C:\Windows\Fonts\NotoSansCoptic-Regular.ttf"),
        Path(r"C:\Windows\Fonts\Antinoou.ttf"),
        Path(r"C:\Windows\Fonts\NewAthenaUnicode.ttf"),
        Path(r"C:\Windows\Fonts\seguisym.ttf"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\times.ttf"),
    ]


def ui_font_candidates() -> list[Path]:
    return [
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\times.ttf"),
    ]


def make_row_items(
    line: dict[str, Any],
    units: list[dict[str, Any]],
    review_decisions: dict[str, dict[str, Any]],
    scale: float,
    next_index: int,
    inline_marks: bool,
) -> tuple[list[dict[str, Any]], int, Counter[str]]:
    blobs_by_id = {int(blob["id"]): blob for blob in line.get("blobs", []) if "img_quad" in blob}
    items: list[dict[str, Any]] = []
    source_counts: Counter[str] = Counter()
    for token in units:
        if token.get("edge_fragment"):
            next_index += 1
            continue
        blob = blobs_by_id.get(int(token.get("blob_id", -1)))
        if not blob:
            continue
        text, source, color, raw_label = choose_display_label(token, review_decisions, inline_marks)
        source_counts[source] += 1
        x0, y0, x1, y1 = quad_bounds(blob["img_quad"])
        display_units = split_display_units(text)
        if len(display_units) == 1:
            xs = [((x0 + x1) / 2.0) * scale]
        else:
            left = x0 + (x1 - x0) * 0.15
            right = x1 - (x1 - x0) * 0.15
            if right <= left:
                right = x1
                left = x0
            step = (right - left) / max(len(display_units) - 1, 1)
            xs = [(left + step * index) * scale for index in range(len(display_units))]
        for subindex, unit_text in enumerate(display_units):
            item_attached_marks = attached_marks_for_display_unit(token, subindex)
            item_geometry_mark_kinds = [
                str(mark.get("kind")) for mark in item_attached_marks if mark.get("kind")
            ]
            item_color = color
            if source == "final:assigned" and not item_geometry_mark_kinds:
                item_color = COLOR_ASSIGNED
            items.append({
                "index": next_index,
                "text": unit_text,
                "x": xs[subindex],
                "color": item_color,
                "source": source,
                "page": token.get("page"),
                "line_index": token.get("line_index"),
                "blob_id": token.get("blob_id"),
                "split_metadata": token.get("split_metadata"),
                "cluster": token.get("cluster"),
                "raw_label": raw_label,
                "final_label": token.get("final_label"),
                "final_label_source": token.get("final_label_source"),
                "geometry_mark_kinds": item_geometry_mark_kinds,
                "display_label": text,
                "unit_position": subindex,
                "unit_count": len(display_units),
                "candidates": token.get("candidates", []),
                "attached_marks": item_attached_marks,
                "manual_override": token.get("manual_override"),
                "manual_warning": token.get("manual_warning"),
                "subcluster_override": token.get("subcluster_override"),
                "geometric_override": token.get("geometric_override"),
                "editorial_override": token.get("editorial_override"),
                "llm_alignment": token.get("llm_alignment", {}),
                "img_bbox": [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
            })
            next_index += 1
    return items, next_index, source_counts


def make_row_marks(
    page: str,
    line: dict[str, Any],
    scale: float,
    clean_cache: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    baseline_y = int(line.get("baseline_y_warped", 39))
    line_index = int(line.get("line_index", -1))
    marks: list[dict[str, Any]] = []
    for blob in line.get("blobs", []):
        if blob.get("kind") != "other" or "img_quad" not in blob:
            continue
        if not blob_belongs_to_line(page, line_index, blob, clean_cache):
            continue
        img_x0, img_y0, img_x1, img_y1 = quad_bounds(blob["img_quad"])
        kind = classify_other_blob(blob, baseline_y)
        marks.append({
            "id": int(blob["id"]),
            "kind": kind,
            "x0": img_x0 * scale,
            "x1": img_x1 * scale,
            "x": ((img_x0 + img_x1) / 2.0) * scale,
            "color": MARK_COLORS.get(kind, COLOR_CANDIDATE),
            "warped_bbox": [int(value) for value in blob.get("warped_bbox", [])],
            "img_bbox": [round(img_x0, 2), round(img_y0, 2), round(img_x1, 2), round(img_y1, 2)],
            "area": int(blob.get("area", 0)),
        })
    return marks


def image_to_data_uri(image: Image.Image) -> str:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def css_rgb(color: tuple[int, int, int] | list[int]) -> str:
    r, g, b = [int(value) for value in color]
    return f"rgb({r},{g},{b})"


def font_face_uri(path: Path) -> str:
    return path.resolve().as_uri()


def first_existing_font(candidates: list[Path]) -> Path:
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError("No usable font found")


def html_label_class(text: str) -> str:
    return "label coptic" if is_coptic_text(text) else "label ui"


def html_escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def mark_style(mark: dict[str, Any], y: int) -> str:
    color = css_rgb(mark.get("color", COLOR_CANDIDATE))
    kind = str(mark.get("kind"))
    x = float(mark.get("x", 0))
    if kind in {"overline", "horizontal_mark"}:
        x0 = float(mark.get("x0", x - 5))
        x1 = float(mark.get("x1", x + 5))
        width = max(8.0, x1 - x0)
        return (
            f"left:{x0:.2f}px;top:{y:.2f}px;width:{width:.2f}px;height:3px;"
            f"background:{color};border-radius:1px;"
        )
    radius = 3
    shape = "border-radius:50%;" if kind in {"above_dot", "below_dot"} else ""
    fill = f"background:{color};" if kind == "above_dot" else f"border:2px solid {color};"
    return (
        f"left:{x - radius:.2f}px;top:{y - radius:.2f}px;"
        f"width:{radius * 2}px;height:{radius * 2}px;{shape}{fill}"
    )


def primary_overline_mark_id(item: dict[str, Any]) -> str | None:
    for mark in item.get("attached_marks", []) or []:
        if mark.get("kind") in OVERLINE_MARK_KINDS and mark.get("id") is not None:
            return str(mark["id"])
    return None


def without_overline_codepoints(text: str) -> str:
    return "".join(char for char in text if char not in OVERLINE_CODEPOINTS)


def conjoining_macron_for(index: int, count: int) -> str:
    if count <= 1:
        return COMBINING_MARKS["overline"]
    if index == 0:
        return CONJOINING_MACRON_LEFT
    if index == count - 1:
        return CONJOINING_MACRON_RIGHT
    return CONJOINING_MACRON_MIDDLE


def overline_group_text(items: list[dict[str, Any]]) -> str:
    if len(items) <= 1:
        return str(items[0]["text"])
    rendered: list[str] = []
    count = len(items)
    for index, item in enumerate(items):
        rendered.append(without_overline_codepoints(str(item["text"])) + conjoining_macron_for(index, count))
    return "".join(rendered)


def label_groups_for_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    index = 0
    while index < len(items):
        item = items[index]

        # --- Editorial span: merge all blobs into one label ---
        eo = item.get("editorial_override") or {}
        if eo.get("label") and eo.get("span_position") == 0:
            span_count = int(eo.get("span_count", 1))
            marker_type = str(eo.get("marker_type", eo.get("label", "editorial")))
            # Claim exactly span_count items — absorb gaps without breaking
            end = min(index + span_count, len(items))
            run = items[index:end]
            # Bounding box from first and last blob for width-based rendering
            x0 = float(run[0]["x"])
            x1 = float(run[-1]["x"])
            # Estimate half-char width from first blob's bbox if available
            bbox = run[0].get("img_bbox")
            pad = ((bbox[2] - bbox[0]) / 2.0) if bbox else 5.0
            groups.append({
                "kind": "editorial_span",
                "text": marker_type,
                "x": (x0 + x1) / 2.0,
                "x0": x0 - pad,
                "x1": x1 + pad,
                "color": COLOR_EDITORIAL,
                "item_indices": [entry["index"] for entry in run],
                "blob_ids": [entry["blob_id"] for entry in run],
            })
            index = end
            continue

        # --- Skip non-first blobs of an editorial span ---
        if eo.get("label") and (eo.get("span_position") or 0) > 0:
            index += 1
            continue

        # --- Overline group ---
        overline_id = primary_overline_mark_id(item)
        if overline_id and is_coptic_text(str(item["text"])):
            end = index + 1
            while (
                end < len(items)
                and primary_overline_mark_id(items[end]) == overline_id
                and is_coptic_text(str(items[end]["text"]))
            ):
                end += 1
            run = items[index:end]
            if len(run) > 1:
                colors = [tuple(entry["color"]) for entry in run]
                color = COLOR_PROBABLE if any(color != COLOR_ASSIGNED for color in colors) else COLOR_ASSIGNED
                groups.append({
                    "kind": "shared_overline",
                    "overline_mark_id": overline_id,
                    "text": overline_group_text(run),
                    "x": (float(run[0]["x"]) + float(run[-1]["x"])) / 2.0,
                    "color": color,
                    "item_indices": [entry["index"] for entry in run],
                    "blob_ids": [entry["blob_id"] for entry in run],
                })
                index = end
                continue
        groups.append({
            "kind": "single",
            "text": str(item["text"]),
            "x": float(item["x"]),
            "color": tuple(item["color"]),
            "item_indices": [item["index"]],
            "blob_ids": [item["blob_id"]],
        })
        index += 1
    return groups


def build_html_sheet(
    page: str,
    body: Image.Image,
    body_width: int,
    row_data: list[dict[str, Any]],
    total_height: int,
    args: argparse.Namespace,
) -> str:
    coptic_font = first_existing_font([args.font] if args.font else font_candidates())
    ui_font = first_existing_font(ui_font_candidates())
    rows_html: list[str] = []
    for row in row_data:
        crop_y0 = int(row["crop_y0"])
        crop_y1 = int(row["crop_y1"])
        scaled_height = int(row["scaled_height"])
        crop = body.crop((0, crop_y0, body_width, crop_y1))
        data_uri = image_to_data_uri(crop)
        label_y = scaled_height + int(row["mark_band_height"]) + args.label_y_offset
        index_y = scaled_height + int(row["mark_band_height"]) + args.label_band_height + args.index_y_offset
        mark_y = scaled_height + args.mark_y_offset
        mark_html = ""
        if args.show_mark_row:
            mark_parts = [
                f'<span class="mark" style="{mark_style(mark, mark_y)}"></span>'
                for mark in row["marks"]
            ]
            mark_html = "".join(mark_parts)
        label_parts = []
        index_parts = []
        for group in label_groups_for_items(row["items"]):
            text = str(group["text"])
            color = css_rgb(group["color"])
            if group["kind"] == "editorial_span":
                x0 = float(group["x0"])
                x1 = float(group["x1"])
                w = x1 - x0
                label_parts.append(
                    f'<span class="{html_label_class(text)}" '
                    f'style="left:{x0:.2f}px;top:{label_y}px;'
                    f'width:{w:.2f}px;text-align:center;'
                    f'transform:none;color:{color};">'
                    f'{html_escape(text)}</span>'
                )
            else:
                x = float(group["x"])
                label_parts.append(
                    f'<span class="{html_label_class(text)}" '
                    f'style="left:{x:.2f}px;top:{label_y}px;color:{color};">'
                    f'{html_escape(text)}</span>'
                )
        for item in row["items"]:
            x = float(item["x"])
            index_parts.append(
                f'<span class="index" style="left:{x:.2f}px;top:{index_y}px;">'
                f'{int(item["index"])}</span>'
            )
        rows_html.append(
            f'<section class="row" style="height:{int(row["row_height"])}px;">'
            f'<img class="crop" src="{data_uri}" style="height:{scaled_height}px;" />'
            f'<span class="row-label">L{int(row["line_index"]):02d}</span>'
            f'{mark_html}{"".join(label_parts)}{"".join(index_parts)}</section>'
        )

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<style>
@font-face {{ font-family: 'NotoCopticReview'; src: url('{font_face_uri(coptic_font)}') format('truetype'); }}
@font-face {{ font-family: 'ReviewUI'; src: url('{font_face_uri(ui_font)}') format('truetype'); }}
html, body {{ margin: 0; padding: 0; width: {args.sheet_width}px; background: {css_rgb(COLOR_BACKGROUND)}; }}
body {{ font-family: ReviewUI, Arial, sans-serif; }}
.sheet {{ width: {args.sheet_width}px; min-height: {total_height}px; background: {css_rgb(COLOR_BACKGROUND)}; padding-top: {args.page_margin}px; box-sizing: border-box; }}
.header {{ height: {args.header_height + args.page_margin}px; padding-left: {args.page_margin}px; box-sizing: border-box; }}
.title {{ font-size: {args.label_font_size}px; line-height: 1.1; color: rgb(20,20,20); }}
.subtitle {{ margin-top: 8px; font-size: {args.index_font_size}px; line-height: 1.2; color: {css_rgb(COLOR_INDEX)}; }}
.row {{ position: relative; width: {args.sheet_width}px; overflow: hidden; margin: 0; }}
.crop {{ position: absolute; left: 0; top: 0; width: {args.sheet_width}px; object-fit: fill; }}
.row-label {{ position: absolute; left: 8px; top: 4px; color: {css_rgb(COLOR_ROW_LABEL)}; font-size: {args.row_label_font_size}px; line-height: 1; }}
.label {{ position: absolute; transform: translateX(-50%); white-space: pre; font-size: {args.label_font_size}px; line-height: 1; }}
.label.coptic {{ font-family: NotoCopticReview; font-variant-ligatures: normal; }}
.label.ui {{ font-family: ReviewUI, Arial, sans-serif; }}
.index {{ position: absolute; transform: translateX(-50%); white-space: pre; font-size: {args.index_font_size}px; line-height: 1; color: {css_rgb(COLOR_INDEX)}; }}
.mark {{ position: absolute; display: block; box-sizing: border-box; }}
</style>
</head>
<body>
<main class="sheet">
  <header class="header">
    <div class="title">Kephalaia p{html_escape(page)} OCR review sheet</div>
    <div class="subtitle">Black = plain assigned glyph; blue = best probable or inferred glyph for review.</div>
  </header>
  {''.join(rows_html)}
</main>
</body>
</html>
"""


def render_html_to_png(html_path: Path, image_path: Path, width: int, height: int) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is required for shaped Coptic sheet rendering") from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": min(max(height, 600), 12000)}, device_scale_factor=1)
        page.goto(html_path.resolve().as_uri())
        page.evaluate("() => document.fonts.ready.then(() => true)")
        page.screenshot(path=str(image_path), full_page=True)
        browser.close()


def build_sheet_for_page(
    page: str,
    page_units: dict[int, list[dict[str, Any]]],
    review_decisions: dict[str, dict[str, Any]],
    args: argparse.Namespace,
    source_path: Path,
) -> tuple[Path, Path]:
    split_path = args.split_dir / f"keph_p{page}_lines_base_split.json"
    body_path = PAGES_DIR / f"keph_p{page}_body.jpg"
    if not split_path.exists():
        raise FileNotFoundError(split_path)
    if not body_path.exists():
        raise FileNotFoundError(body_path)

    body = Image.open(body_path).convert("RGB")
    body_width, body_height = body.size
    scale = args.sheet_width / body_width
    split = load_json(split_path)
    lines = sorted(split.get("lines", []), key=lambda item: int(item["line_index"]))

    row_data: list[dict[str, Any]] = []
    clean_cache: dict[str, list[dict[str, Any]]] = {}
    next_index = 1
    source_counts: Counter[str] = Counter()
    total_height = args.page_margin * 2 + args.header_height
    for line in lines:
        line_index = int(line["line_index"])
        y0, y1 = line_bounds(line, body_height, args.line_margin_y)
        crop_height = y1 - y0
        scaled_height = max(1, int(round(crop_height * scale)))
        items, next_index, row_sources = make_row_items(
            line,
            page_units.get(line_index, []),
            review_decisions,
            scale,
            next_index,
            args.inline_marks,
        )
        marks = make_row_marks(page, line, scale, clean_cache) if args.show_mark_row else []
        source_counts.update(row_sources)
        mark_band_height = args.mark_band_height if args.show_mark_row else 0
        row_height = scaled_height + mark_band_height + args.label_band_height + args.index_band_height + args.row_gap
        row_data.append({
            "line_index": line_index,
            "crop_y0": y0,
            "crop_y1": y1,
            "scaled_height": scaled_height,
            "mark_band_height": mark_band_height,
            "row_y": total_height,
            "row_height": row_height,
            "items": items,
            "marks": marks,
        })
        total_height += row_height

    manifest_rows = []
    for row in row_data:
        row_y = int(row["row_y"])
        crop_y0 = int(row["crop_y0"])
        crop_y1 = int(row["crop_y1"])
        mark_y = row_y + int(row["scaled_height"]) + args.mark_y_offset
        label_y = row_y + int(row["scaled_height"]) + int(row["mark_band_height"]) + args.label_y_offset
        index_y = row_y + int(row["scaled_height"]) + int(row["mark_band_height"]) + args.label_band_height + args.index_y_offset
        manifest_rows.append({
            "line_index": row["line_index"],
            "crop_y0": crop_y0,
            "crop_y1": crop_y1,
            "row_y": row_y,
            "scaled_height": row["scaled_height"],
            "mark_y": mark_y if args.show_mark_row else None,
            "label_y": label_y,
            "index_y": index_y,
            "marks": [
                {key: value for key, value in mark.items() if key not in {"color"}}
                for mark in row["marks"]
            ],
            "label_groups": [
                {key: value for key, value in group.items() if key not in {"color"}}
                for group in label_groups_for_items(row["items"])
            ],
            "items": [
                {key: value for key, value in item.items() if key not in {"color"}}
                for item in row["items"]
            ],
        })

    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.artifact_dir.mkdir(parents=True, exist_ok=True)
    image_path = args.out_dir / f"keph_p{page}_review.png"
    html_path = args.artifact_dir / f"keph_p{page}_review.html"
    manifest_path = args.artifact_dir / f"keph_p{page}_review.json"
    html_path.write_text(
        build_html_sheet(page, body, body_width, row_data, total_height, args),
        encoding="utf-8",
    )
    render_html_to_png(html_path, image_path, args.sheet_width, total_height)
    dump_json(manifest_path, {
        "page": page,
        "body_image": str(body_path.relative_to(REPO)),
        "split_source": str(split_path.relative_to(REPO)),
        "label_source": str(source_path.relative_to(REPO)),
        "review_decisions": str((args.context_dir / "review_cluster_context.json").relative_to(REPO)),
        "sheet_image": str(image_path.relative_to(REPO)),
        "sheet_html": str(html_path.relative_to(REPO)),
        "renderer": "playwright_chromium_html",
        "coptic_font": str(first_existing_font([args.font] if args.font else font_candidates()).relative_to(REPO)),
        "sheet_width": args.sheet_width,
        "sheet_height": total_height,
        "scale": scale,
        "displayed_characters": next_index - 1,
        "label_source_counts": dict(source_counts),
        "inline_marks": args.inline_marks,
        "show_mark_row": args.show_mark_row,
        "color_note": "Black labels are plain assigned glyphs. Blue labels are probable, inferred, context-derived, or rescue labels needing visual review.",
        "mark_row_note": "Optional --mark-row draws kind=other blobs at image positions; normal output uses Unicode combining marks in the labels.",
        "rows": manifest_rows,
    })
    return image_path, manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", action="append", default=[], help="Page number, e.g. 010. May be repeated.")
    parser.add_argument("--pages", nargs="*", default=[], help="Additional page numbers.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR, help="Directory for renderer HTML and manifest JSON artifacts.")
    parser.add_argument("--sheet-width", type=int, default=2200)
    parser.add_argument("--line-margin-y", type=int, default=16)
    parser.add_argument("--label-band-height", type=int, default=42)
    parser.add_argument("--mark-band-height", type=int, default=18)
    parser.add_argument("--index-band-height", type=int, default=28)
    parser.add_argument("--mark-y-offset", type=int, default=7)
    parser.add_argument("--label-y-offset", type=int, default=4)
    parser.add_argument("--index-y-offset", type=int, default=0)
    parser.add_argument("--row-gap", type=int, default=18)
    parser.add_argument("--page-margin", type=int, default=20)
    parser.add_argument("--header-height", type=int, default=70)
    parser.add_argument("--label-font-size", type=int, default=28)
    parser.add_argument("--index-font-size", type=int, default=13)
    parser.add_argument("--row-label-font-size", type=int, default=14)
    parser.add_argument("--font", type=Path, default=None, help="Optional TrueType/OpenType font path.")
    parser.add_argument("--context-dir", type=Path, default=DEFAULT_CONTEXT_DIR)
    parser.add_argument("--witness-dir", type=Path, default=DEFAULT_WITNESS_DIR)
    parser.add_argument("--split-dir", type=Path, default=None,
                        help="Per-line split JSON directory. Defaults to the split layer recorded in <context-dir>/_summary.json, "
                             "falling back to output/projects/kephalaia_ocr/pages.")
    parser.add_argument("--no-witness", action="store_true", help="Use contextual line sequences rather than composite LLM witness lines.")
    parser.add_argument("--inline-marks", dest="inline_marks", action="store_true", help="Render geometry-attached marks directly on base labels. This is the default.")
    parser.add_argument("--base-only-labels", dest="inline_marks", action="store_false", help="Strip combining marks from labels for diagnostic review.")
    parser.add_argument("--mark-row", dest="show_mark_row", action="store_true", help="Draw a separate diagnostic row for raw manuscript mark blobs.")
    parser.add_argument("--no-mark-row", dest="show_mark_row", action="store_false", help="Do not draw the diagnostic manuscript mark row. This is the default.")
    parser.set_defaults(inline_marks=True, show_mark_row=False)
    args = parser.parse_args()
    pages = [normalize_page(page) for page in [*args.page, *args.pages]]
    if not pages:
        parser.error("provide --page or --pages")
    args.pages = pages
    args.out_dir = resolve_repo_path(args.out_dir)
    args.artifact_dir = resolve_repo_path(args.artifact_dir)
    args.context_dir = resolve_repo_path(args.context_dir)
    args.witness_dir = resolve_repo_path(args.witness_dir)
    if args.split_dir is None:
        # Honor the split layer the clusters_dir was built against, recorded
        # by build_contextual_review in <context-dir>/_summary.json. Without
        # this, defaulting to OCR_ROOT / "pages" silently drops blobs that
        # only exist in the split-chars layer.
        summary_path = args.context_dir / "_summary.json"
        recorded: str | None = None
        if summary_path.exists():
            recorded = (load_json(summary_path) or {}).get("split_dir")
        if recorded:
            recorded_path = Path(str(recorded))
            args.split_dir = recorded_path if recorded_path.is_absolute() else REPO / recorded_path
        else:
            args.split_dir = BASE_SPLIT_DIR
    args.split_dir = resolve_repo_path(args.split_dir)
    args.font = resolve_repo_path(args.font)
    return args


def main() -> None:
    args = parse_args()
    selected_pages = set(args.pages)
    review_decisions = load_review_decisions(args.context_dir / "review_cluster_context.json")
    witness_path = args.witness_dir / "composite_line_sequences.jsonl"
    line_sequences_path = args.context_dir / "line_sequences.jsonl"
    page_sequences, source_path, _unit_key = load_page_sequences(
        selected_pages, witness_path, line_sequences_path, use_witness=not args.no_witness
    )
    for page in args.pages:
        image_path, manifest_path = build_sheet_for_page(
            page, page_sequences.get(page, {}), review_decisions, args, source_path
        )
        print(f"p{page}: {image_path.relative_to(REPO)}")
        print(f"p{page}: {manifest_path.relative_to(REPO)}")


if __name__ == "__main__":
    main()