#!/usr/bin/env python3
"""Build a constrained LLM-transcription witness for Kephalaia OCR clusters.

The manuscript-derived stream remains authoritative: line order, blob order,
cluster ids, candidate labels, and geometry. The LLM transcription is used only
as a second witness constrained to those candidates. This stage also attaches
non-base blobs, such as overlines and small additions, to nearby base glyphs so
they can be handled in a wider context window.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tqdm import tqdm

REPO = Path(__file__).resolve().parents[3]
OCR_ROOT = REPO / "output" / "projects" / "kephalaia_ocr"
PAGES_DIR = OCR_ROOT / "pages"
BASE_SPLIT_DIR = PAGES_DIR
TRANSCRIPTION_DIR = REPO / "output" / "projects" / "kephalaia_v2" / "coptic" / "transcriptions"
DEFAULT_CONTEXT_DIR = OCR_ROOT / "contextual_review" / "clusters_shape_padded_k120"
DEFAULT_OUT_DIR = OCR_ROOT / "llm_witness" / "clusters_shape_padded_k120"
LINE_OWNERSHIP_TOLERANCE_PX = 6.0

CONNECTED_REVIEW = "_connected_needs_literal_reading"
CONNECTED_DECISION_CONFIDENCE = {"needs_literal_reading", "needs_subcluster"}
BLOCK_CANDIDATE_CONFIDENCES = {
    "needs_editorial_or_shape_split",
    "needs_vertical_split",
    "needs_character_split",
    "needs_noise_split",
    "needs_mark_split",
}
SPECIAL_LABEL_PREFIX = "_"
LINE_NUMBER_RE = re.compile(r"^\s*(\d+)\s+(.*)$")
MARK_TOKEN_LABELS = {"_lacuna_dot", "_unknown"}

OVERLINE_MARKS = {"\u0304", "\u0305"}
DIAERESIS_MARKS = {"\u0308"}
DOT_MARKS = {"\u0307", "\u0323"}

COMBINING_MARKS = {
    "overline": "\u0304",
    "horizontal_mark": "\u0304",
    "above_dot": "\u0307",
    "dot": "\u0307",
    "diaeresis": "\u0308",
    "below_dot": "\u0323",
}
MARK_ORDER = ("overline", "horizontal_mark", "diaeresis", "above_dot", "dot", "below_dot")

# Overlines should not attach on tiny edge overlap; require center crossing
# or meaningful horizontal coverage of the target character slot.
MIN_OVERLINE_SLOT_COVERAGE = 0.30
MAX_OVERLINE_LEFT_EDGE_GAP_PX = 12.0
MIN_OVERLINE_LEFT_EDGE_MARK_TO_SLOT_RATIO = 1.5
FUSED_DIAERESIS_MIN_WIDTH = 8
FUSED_DIAERESIS_MIN_HEIGHT = 28
FUSED_DIAERESIS_MAX_TOP = 20
FUSED_DIAERESIS_WITH_DOT_MIN_WIDTH = 5
MIN_DOT_MARK_HEIGHT = 2
MAX_BELOW_DOT_BASELINE_DELTA = 16


@dataclass
class MatchOption:
    consume: int
    score: float
    text: str
    kind: str
    source: str


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_repo_path(value: str | None, default: Path) -> Path:
    if value is None:
        return default
    path = Path(value)
    return path if path.is_absolute() else REPO / path


def is_coptic_base(char: str) -> bool:
    code = ord(char)
    return 0x2C80 <= code <= 0x2CFF or 0x03E2 <= code <= 0x03EF


def is_coptic_string(value: str | None) -> bool:
    if not value or value.startswith(SPECIAL_LABEL_PREFIX):
        return False
    return any(is_coptic_base(char) for char in unicodedata.normalize("NFD", value))


def split_coptic_units(text: str) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for char in unicodedata.normalize("NFD", text):
        if is_coptic_base(char):
            current = {"base": char, "marks": [], "text": char}
            units.append(current)
            continue
        if current is not None and unicodedata.combining(char):
            current["marks"].append(mark_name(char))
            current["text"] += char
    return units


def mark_name(char: str) -> str:
    if char in OVERLINE_MARKS:
        return "overline"
    if char in DIAERESIS_MARKS:
        return "diaeresis"
    if char in DOT_MARKS:
        return "dot"
    return unicodedata.name(char, "combining_mark").lower().replace(" ", "_")


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
    if not marks or not is_coptic_string(text):
        return text
    units = split_coptic_units(text)
    if not units:
        return text
    apply_to_all = any(kind in {"overline", "horizontal_mark"} for kind in mark_kinds)
    rendered: list[str] = []
    for index, unit in enumerate(units):
        unit_text = str(unit.get("text") or unit.get("base") or "")
        if unit.get("marks"):
            rendered.append(unit_text)
        elif apply_to_all or index == len(units) - 1:
            rendered.append(unit_text + "".join(marks))
        else:
            rendered.append(unit_text)
    return "".join(rendered)


def add_attached_combining_marks(text: str, attached_marks: list[dict[str, Any]]) -> str:
    if not attached_marks or not is_coptic_string(text):
        return text
    units = split_coptic_units(text)
    if not units:
        return text

    rendered: list[str] = []
    for index, unit in enumerate(units):
        unit_text = str(unit.get("text") or unit.get("base") or "")
        if unit.get("marks"):
            rendered.append(unit_text)
            continue

        unit_mark_kinds: list[str] = []
        for mark in attached_marks:
            kind = str(mark.get("kind") or "")
            if not kind:
                continue
            target_positions = mark.get("target_unit_positions")
            if target_positions is not None:
                if index in {int(position) for position in target_positions}:
                    unit_mark_kinds.append(kind)
                continue
            if kind in {"overline", "horizontal_mark"} or len(units) == 1 or index == len(units) - 1:
                unit_mark_kinds.append(kind)

        rendered.append(unit_text + "".join(combining_marks_for(unit_mark_kinds)))
    return "".join(rendered)


def base_sequence(value: str) -> str:
    return "".join(unit["base"] for unit in split_coptic_units(value))


def geometry_base_label(unit: dict[str, Any]) -> tuple[str | None, str]:
    if unit.get("edge_fragment"):
        return None, "edge_fragment"

    editorial_override = unit.get("editorial_override") or {}
    editorial_label = editorial_override.get("label")
    if editorial_label:
        confidence = editorial_override.get("confidence") or "generated"
        marker_text = str(editorial_override.get("marker_text") or "editorial")
        marker_key = re.sub(r"\s+", "_", marker_text.strip().lower()) or "editorial"
        return None, f"editorial_marker:{marker_key}:{confidence}"

    manual_override = unit.get("manual_override") or {}
    manual_label = manual_override.get("label")
    if is_coptic_string(manual_label):
        confidence = manual_override.get("confidence") or "manual"
        return str(manual_label), f"manual_override:{confidence}"
    if manual_label:
        confidence = manual_override.get("confidence") or "manual"
        return None, f"manual_override_non_coptic:{confidence}"

    geometric_override = unit.get("geometric_override") or {}
    geometric_label = geometric_override.get("label")
    if is_coptic_string(geometric_label):
        confidence = geometric_override.get("confidence") or "geometric"
        rule_id = geometric_override.get("id") or "rule"
        return base_sequence(str(geometric_label)), f"geometric:{rule_id}:{confidence}"
    if geometric_label:
        confidence = geometric_override.get("confidence") or "geometric"
        rule_id = geometric_override.get("id") or "rule"
        return None, f"geometric_non_coptic:{rule_id}:{confidence}"

    subcluster_override = unit.get("subcluster_override") or {}
    subcluster_label = subcluster_override.get("label")
    if is_coptic_string(subcluster_label):
        confidence = subcluster_override.get("confidence") or "manual"
        subcluster = subcluster_override.get("subcluster") or "unknown"
        return base_sequence(str(subcluster_label)), f"subcluster:{subcluster}:{confidence}"
    if subcluster_label:
        confidence = subcluster_override.get("confidence") or "manual"
        subcluster = subcluster_override.get("subcluster") or "unknown"
        return None, f"subcluster_non_coptic:{subcluster}:{confidence}"

    label = unit.get("label")
    if is_coptic_string(label):
        return base_sequence(str(label)), "assigned"
    if label:
        return None, "assigned_non_coptic"

    decision = unit.get("review_decision") or {}
    decision_label = decision.get("label")
    if is_coptic_string(decision_label):
        confidence = decision.get("confidence") or "unknown"
        return base_sequence(str(decision_label)), f"context:{confidence}"
    if decision_label:
        confidence = decision.get("confidence") or "unknown"
        return None, f"context_non_coptic:{confidence}"
    if decision.get("confidence") in BLOCK_CANDIDATE_CONFIDENCES:
        return None, f"context:{decision.get('confidence')}"

    for candidate in unit.get("candidates", []) or []:
        if is_coptic_string(str(candidate)):
            return base_sequence(str(candidate)), "candidate"

    return None, "unresolved"


def attach_geometry_final_label(unit: dict[str, Any]) -> dict[str, Any]:
    marked = dict(unit)
    base_label, source = geometry_base_label(marked)
    attached_marks = marked.get("attached_marks", []) or []
    manual_override = marked.get("manual_override") or {}
    suppress_kinds = {str(kind) for kind in manual_override.get("suppress_attached_mark_kinds", []) or []}
    if suppress_kinds:
        attached_marks = [mark for mark in attached_marks if str(mark.get("kind")) not in suppress_kinds]
        marked["attached_marks"] = attached_marks
    mark_kinds = [str(mark.get("kind")) for mark in attached_marks if mark.get("kind")]
    marked["geometry_mark_kinds"] = mark_kinds
    marked["final_label_source"] = source
    marked["final_label"] = add_attached_combining_marks(base_label, attached_marks) if base_label else None
    return marked


def has_attached_mark_kind(unit: dict[str, Any], kinds: set[str]) -> bool:
    return any(mark.get("kind") in kinds for mark in unit.get("attached_marks", []) or [])


def looks_like_fused_diaeresis_i(unit: dict[str, Any], base_label: str | None) -> bool:
    if base_label != "ⲓ":
        return False
    bbox = [int(value) for value in (unit.get("geometry") or {}).get("warped_bbox", [])]
    if len(bbox) != 4:
        return False
    width = bbox[2] - bbox[0] + 1
    height = bbox[3] - bbox[1] + 1
    return width >= FUSED_DIAERESIS_MIN_WIDTH and height >= FUSED_DIAERESIS_MIN_HEIGHT and bbox[1] <= FUSED_DIAERESIS_MAX_TOP


def looks_like_i_with_fused_dot_and_attached_dot(unit: dict[str, Any], base_label: str | None) -> bool:
    if base_label != "ⲓ":
        return False
    bbox = [int(value) for value in (unit.get("geometry") or {}).get("warped_bbox", [])]
    if len(bbox) != 4:
        return False
    attached_above_dots = [mark for mark in unit.get("attached_marks", []) or [] if mark.get("kind") == "above_dot"]
    if len(attached_above_dots) != 1:
        return False
    width = bbox[2] - bbox[0] + 1
    height = bbox[3] - bbox[1] + 1
    if width < FUSED_DIAERESIS_WITH_DOT_MIN_WIDTH or height < FUSED_DIAERESIS_MIN_HEIGHT or bbox[1] > FUSED_DIAERESIS_MAX_TOP:
        return False
    mark_box = [int(value) for value in attached_above_dots[0].get("warped_bbox", [])]
    if len(mark_box) != 4:
        return False
    mark_y_near_top = abs(mark_box[1] - bbox[1]) <= 3
    # Accept the external dot on either side of the iota stem: the fused dot
    # inside the connected component can be on the left or the right, so the
    # *other* trema dot can land on the opposite side.
    mark_adjacent_right = -1 <= mark_box[0] - bbox[2] <= 3
    mark_right_edge = mark_box[2]
    mark_adjacent_left = -3 <= bbox[0] - mark_right_edge <= 1
    return mark_y_near_top and (mark_adjacent_right or mark_adjacent_left)


def attach_fused_internal_marks(unit: dict[str, Any]) -> dict[str, Any]:
    marked = dict(unit)
    alignment = dict(marked.get("llm_alignment") or {})
    llm_marks = {str(mark) for mark in alignment.get("llm_marks", []) or []}

    if has_attached_mark_kind(marked, {"diaeresis"}):
        return marked

    base_label, source = geometry_base_label(marked)
    attached_marks = marked.get("attached_marks", []) or []
    attached_above_dots = [mark for mark in attached_marks if mark.get("kind") == "above_dot"]
    if looks_like_i_with_fused_dot_and_attached_dot(marked, base_label):
        geometry = marked.get("geometry") or {}
        fused_mark = {
            "id": f"fused:{marked.get('blob_id')}:diaeresis_second_dot",
            "kind": "above_dot",
            "warped_bbox": geometry.get("warped_bbox", []),
            "area": int(geometry.get("area", 0) or 0),
            "source": "geometry_fused_diaeresis_completed_single_attached_dot",
        }
        marked.setdefault("attached_marks", []).append(fused_mark)
        marked["geometry_mark_kinds"] = [str(mark.get("kind")) for mark in marked.get("attached_marks", []) if mark.get("kind")]
        marked["final_label_source"] = source
        marked["final_label"] = add_attached_combining_marks(base_label, marked.get("attached_marks", []))
        alignment["mark_status"] = "geometry_fused_diaeresis_completed_single_attached_dot"
        marked["llm_alignment"] = alignment
        return marked

    if "diaeresis" not in llm_marks:
        return marked

    if not looks_like_fused_diaeresis_i(marked, base_label):
        return marked

    geometry = marked.get("geometry") or {}
    fused_mark = {
        "id": f"fused:{marked.get('blob_id')}:diaeresis",
        "kind": "diaeresis",
        "warped_bbox": geometry.get("warped_bbox", []),
        "area": int(geometry.get("area", 0) or 0),
        "source": "fused_component_geometry_llm",
    }
    marked.setdefault("attached_marks", []).append(fused_mark)
    marked["geometry_mark_kinds"] = [str(mark.get("kind")) for mark in marked.get("attached_marks", []) if mark.get("kind")]
    marked["final_label_source"] = source
    marked["final_label"] = add_attached_combining_marks(base_label, marked.get("attached_marks", [])) if base_label else None
    alignment["mark_status"] = "llm_and_fused_geometry_diaeresis"
    marked["llm_alignment"] = alignment
    return marked


def load_line_sequences(path: Path) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if raw:
                lines.append(json.loads(raw))
    return lines


def load_review_decisions(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    rows = load_json(path)
    return {str(row.get("cluster")): row.get("decision", {}) for row in rows}


def transcription_line_source(data: dict[str, Any]) -> tuple[list[str], int]:
    pass2 = data.get("pass2") or {}
    if pass2.get("lines"):
        return [str(line) for line in pass2["lines"]], 3
    if pass2.get("transcription"):
        return str(pass2["transcription"]).splitlines(), 3
    if data.get("transcription_lines"):
        return [str(line) for line in data["transcription_lines"]], 2
    if data.get("lines"):
        return [str(line) for line in data["lines"]], 1
    if data.get("transcription"):
        return str(data["transcription"]).splitlines(), 1
    return [], 0


def load_transcription_lines(transcription_dir: Path) -> dict[tuple[str, int], str]:
    by_line: dict[tuple[str, int], str] = {}
    priority_by_line: dict[tuple[str, int], int] = {}
    for path in sorted(transcription_dir.glob("keph_p*.json")):
        data = load_json(path)
        page_name = str(data.get("page_name") or path.stem)
        page = page_name.removeprefix("keph_p").removesuffix("_twopass")
        raw_lines, priority = transcription_line_source(data)
        numbered_seen = False
        for index, raw_line in enumerate(raw_lines):
            line = str(raw_line)
            match = LINE_NUMBER_RE.match(line)
            if match:
                numbered_seen = True
                key = (page, int(match.group(1)) - 1)
                if priority >= priority_by_line.get(key, -1):
                    by_line[key] = match.group(2).strip()
                    priority_by_line[key] = priority
        if not numbered_seen:
            for index, raw_line in enumerate(raw_lines):
                key = (page, index)
                if priority >= priority_by_line.get(key, -1):
                    by_line[key] = str(raw_line).strip()
                    priority_by_line[key] = priority
    return by_line


def load_split_line(page: str, line_index: int, cache: dict[str, dict[str, Any]], split_dir: Path = BASE_SPLIT_DIR) -> dict[str, Any] | None:
    if page not in cache:
        path = split_dir / f"keph_p{page}_lines_base_split.json"
        cache[page] = load_json(path) if path.exists() else {}
    split = cache.get(page) or {}
    for line in split.get("lines", []):
        if int(line.get("line_index", -1)) == line_index:
            return line
    return None


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


def bbox_shape(blob: dict[str, Any]) -> tuple[int, int]:
    x0, y0, x1, y1 = [int(value) for value in blob["warped_bbox"]]
    return x1 - x0 + 1, y1 - y0 + 1


def classify_other_blob(blob: dict[str, Any], baseline_y: int) -> str:
    x0, y0, x1, y1 = [int(value) for value in blob["warped_bbox"]]
    width, height = bbox_shape(blob)
    center_y = (y0 + y1) / 2.0
    if width <= 7 and height <= 8:
        if height < MIN_DOT_MARK_HEIGHT:
            return "other_mark"
        if center_y < baseline_y - 2:
            return "above_dot"
        if center_y > baseline_y + 2 and center_y <= baseline_y + MAX_BELOW_DOT_BASELINE_DELTA:
            return "below_dot"
    above = y1 < baseline_y - 6
    below = y0 > baseline_y + 6
    if above and width >= 8 and height <= 8:
        return "overline"
    if above and width <= 7 and height <= 8:
        return "above_dot"
    if below and width <= 7 and MIN_DOT_MARK_HEIGHT <= height <= 8 and center_y <= baseline_y + MAX_BELOW_DOT_BASELINE_DELTA:
        return "below_dot"
    if below and width >= 10 and height <= 10:
        return "other_mark"
    if width >= 10 and height <= 10:
        return "horizontal_mark"
    return "other_mark"


def horizontal_overlap(a: list[int], b: list[int]) -> int:
    return max(0, min(int(a[2]), int(b[2])) - max(int(a[0]), int(b[0])) + 1)


def overline_attaches_to_span(mark_bbox: list[int], span_left: float, span_right: float, min_coverage: float = MIN_OVERLINE_SLOT_COVERAGE) -> bool:
    overlap_left = max(float(mark_bbox[0]), span_left)
    overlap_right = min(float(mark_bbox[2]), span_right)
    overlap = max(0, overlap_right - overlap_left + 1)
    span_width = max(1.0, span_right - span_left + 1)
    mark_width = max(1.0, float(mark_bbox[2]) - float(mark_bbox[0]) + 1.0)

    if overlap <= 0:
        left_edge_gap = float(mark_bbox[0]) - span_right
        if 0 < left_edge_gap <= min(MAX_OVERLINE_LEFT_EDGE_GAP_PX, span_width * 0.65):
            return mark_width >= span_width * MIN_OVERLINE_LEFT_EDGE_MARK_TO_SLOT_RATIO
        return False

    span_center = (span_left + span_right) / 2.0
    crosses_center = overlap_left <= span_center <= overlap_right
    coverage = overlap / span_width
    return crosses_center or coverage >= min_coverage


def overline_near_left_edge(mark_bbox: list[int], base_bbox: list[int]) -> bool:
    span_width = max(1.0, float(base_bbox[2]) - float(base_bbox[0]) + 1.0)
    left_edge_gap = float(mark_bbox[0]) - float(base_bbox[2])
    if not (0 < left_edge_gap <= min(MAX_OVERLINE_LEFT_EDGE_GAP_PX, span_width * 0.65)):
        return False
    mark_width = max(1.0, float(mark_bbox[2]) - float(mark_bbox[0]) + 1.0)
    return mark_width >= span_width * MIN_OVERLINE_LEFT_EDGE_MARK_TO_SLOT_RATIO


def overline_target_unit_positions(mark_bbox: list[int], base_bbox: list[int], unit_count: int) -> list[int]:
    if unit_count <= 1:
        return [0] if overline_attaches_to_span(mark_bbox, float(base_bbox[0]), float(base_bbox[2])) else []

    x0 = float(base_bbox[0])
    x1 = float(base_bbox[2])
    width = max(1.0, x1 - x0 + 1.0)
    positions: list[int] = []
    for index in range(unit_count):
        slot_left = x0 + width * index / unit_count
        slot_right = x0 + width * (index + 1) / unit_count - 1.0
        if overline_attaches_to_span(mark_bbox, slot_left, slot_right):
            positions.append(index)
    return positions


def is_dot_like_token(unit: dict[str, Any]) -> bool:
    geometry = unit.get("geometry") or {}
    width = float(geometry.get("width", 999))
    height = float(geometry.get("height", 999))
    area = float(geometry.get("area", 999))
    labels = {str(label) for label in unit.get("candidates", []) or []}
    label = unit.get("label")
    decision = unit.get("review_decision") or {}
    decision_label = decision.get("label")
    has_mark_label = bool(labels & MARK_TOKEN_LABELS) or label in MARK_TOKEN_LABELS or decision_label in MARK_TOKEN_LABELS
    return has_mark_label and width <= 7 and height <= 8 and area <= 35


def token_mark_kind(unit: dict[str, Any], baseline_y: int) -> str | None:
    bbox = [int(value) for value in (unit.get("geometry") or {}).get("warped_bbox", [])]
    if len(bbox) != 4:
        return None
    center_y = (bbox[1] + bbox[3]) / 2.0
    if center_y <= baseline_y - 2:
        return "above_dot"
    if center_y >= baseline_y + 2:
        return "below_dot"
    return None


def dot_mark_plausible_for_base(mark: dict[str, Any], base_bbox: list[int]) -> bool:
    kind = str(mark.get("kind") or "")
    if kind not in {"above_dot", "below_dot"}:
        return True
    mark_bbox = [int(value) for value in mark.get("warped_bbox", [])]
    if len(mark_bbox) != 4 or len(base_bbox) != 4:
        return True
    base_height = max(1, base_bbox[3] - base_bbox[1] + 1)
    mark_center_y = (mark_bbox[1] + mark_bbox[3]) / 2.0
    if kind == "above_dot":
        top_band = max(6.0, base_height * 0.35)
        return mark_center_y <= base_bbox[1] + top_band
    bottom_band = max(4.0, base_height * 0.30)
    return mark_center_y >= base_bbox[3] - bottom_band


def is_iota_like_base_unit(unit: dict[str, Any]) -> bool:
    base_label, _source = geometry_base_label(unit)
    if base_label == "ⲓ":
        return True
    bbox = [int(value) for value in (unit.get("geometry") or {}).get("warped_bbox", [])]
    if len(bbox) != 4:
        return False
    width = bbox[2] - bbox[0] + 1
    height = bbox[3] - bbox[1] + 1
    return width <= 8 and height >= 16


def redirect_below_dot_from_following_iota(
    mark: dict[str, Any],
    target: dict[str, Any],
    units: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if mark.get("kind") != "below_dot" or not is_iota_like_base_unit(target):
        return None
    mark_bbox = [int(value) for value in mark.get("warped_bbox", [])]
    target_bbox = [int(value) for value in (target.get("geometry") or {}).get("warped_bbox", [])]
    if len(mark_bbox) != 4 or len(target_bbox) != 4:
        return None
    # Only redirect when the dot sits clearly to the LEFT of the iota stroke.
    # If the dot's x-range overlaps the iota's at all, the dot belongs to the
    # iota itself; redirecting it to the previous letter steals a real mark.
    if mark_bbox[2] >= target_bbox[0]:
        return None
    mark_center_x = (mark_bbox[0] + mark_bbox[2]) / 2.0

    previous_units: list[tuple[int, dict[str, Any]]] = []
    for unit in units:
        if unit is target:
            continue
        bbox = [int(value) for value in (unit.get("geometry") or {}).get("warped_bbox", [])]
        if len(bbox) != 4 or bbox[2] >= target_bbox[0]:
            continue
        base_label, _source = geometry_base_label(unit)
        if not base_label or is_iota_like_base_unit(unit):
            continue
        previous_units.append((bbox[2], unit))
    if not previous_units:
        return None
    previous_units.sort(key=lambda value: value[0], reverse=True)
    previous = previous_units[0][1]
    previous_bbox = [int(value) for value in previous["geometry"]["warped_bbox"]]
    gap = target_bbox[0] - previous_bbox[2] - 1
    if gap > 8:
        return None
    previous_width = previous_bbox[2] - previous_bbox[0] + 1
    if previous_width < 10:
        return None
    previous_center_x = (previous_bbox[0] + previous_bbox[2]) / 2.0
    target_center_x = (target_bbox[0] + target_bbox[2]) / 2.0
    if abs(mark_center_x - previous_center_x) > abs(mark_center_x - target_center_x) + previous_width:
        return None
    return previous


def fold_mark_like_units(units: list[dict[str, Any]], baseline_y: int) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    pending_marks: list[dict[str, Any]] = []

    for unit in units:
        # Binding Coptic manual_overrides must never be folded into a mark.
        manual_override = unit.get("manual_override") or {}
        manual_label = manual_override.get("label")
        manual_source = str(manual_override.get("source") or "")
        if (
            is_coptic_string(manual_label)
            and manual_source.startswith("manual_binding_")
        ):
            kept.append(unit)
            continue
        if is_dot_like_token(unit):
            kind = token_mark_kind(unit, baseline_y)
            if kind:
                bbox = [int(value) for value in unit["geometry"]["warped_bbox"]]
                pending_marks.append({
                    "id": int(unit["blob_id"]),
                    "kind": kind,
                    "warped_bbox": bbox,
                    "area": int(unit.get("geometry", {}).get("area", 0)),
                    "source": "folded_dot_token",
                    "cluster": unit.get("cluster"),
                })
                continue
        kept.append(unit)

    if not pending_marks:
        return kept

    for mark in pending_marks:
        mark_bbox = mark["warped_bbox"]
        mark_center = (mark_bbox[0] + mark_bbox[2]) / 2.0
        targets: list[tuple[float, dict[str, Any]]] = []
        for unit in kept:
            base_label, _source = geometry_base_label(unit)
            if not base_label:
                continue
            base_bbox = [int(value) for value in (unit.get("geometry") or {}).get("warped_bbox", [])]
            if len(base_bbox) != 4:
                continue
            if not dot_mark_plausible_for_base(mark, base_bbox):
                continue
            expanded = [base_bbox[0] - 4, base_bbox[1], base_bbox[2] + 4, base_bbox[3]]
            if not (expanded[0] <= mark_center <= expanded[2]):
                continue
            overlap = horizontal_overlap(mark_bbox, base_bbox)
            base_center = (base_bbox[0] + base_bbox[2]) / 2.0
            targets.append((abs(mark_center - base_center) - overlap * 0.5, unit))
        if targets:
            targets.sort(key=lambda value: value[0])
            target = redirect_below_dot_from_following_iota(mark, targets[0][1], kept) or targets[0][1]
            target.setdefault("attached_marks", []).append(mark)
        else:
            kept.append({
                "page": kept[0].get("page") if kept else None,
                "line_index": kept[0].get("line_index") if kept else None,
                "blob_id": mark["id"],
                "cluster": mark.get("cluster"),
                "label": None,
                "review": True,
                "candidates": ["_lacuna_dot", "_unknown"],
                "geometry": {"warped_bbox": mark_bbox, "area": mark["area"]},
                "attached_marks": [],
            })

    kept.sort(key=lambda unit: int((unit.get("geometry") or {}).get("warped_bbox", [0])[0]))
    return kept


def attach_non_base_marks(
    line: dict[str, Any],
    split_cache: dict[str, dict[str, Any]],
    clean_cache: dict[str, list[dict[str, Any]]],
    split_dir: Path = BASE_SPLIT_DIR,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    page = str(line["page"])
    line_index = int(line["line_index"])
    split_line = load_split_line(page, line_index, split_cache, split_dir)
    units = [dict(token, attached_marks=[]) for token in line.get("tokens", [])]
    if not split_line:
        return units, []

    baseline_y = int(split_line.get("baseline_y_warped", 39))
    base_by_id = {int(blob["id"]): blob for blob in split_line.get("blobs", []) if blob.get("kind") == "base"}
    unattached: list[dict[str, Any]] = []

    for blob in split_line.get("blobs", []):
        if blob.get("kind") == "base":
            continue
        mark_bbox = [int(value) for value in blob["warped_bbox"]]
        mark_center = (mark_bbox[0] + mark_bbox[2]) / 2.0
        mark = {
            "id": int(blob["id"]),
            "kind": classify_other_blob(blob, baseline_y),
            "warped_bbox": mark_bbox,
            "area": int(blob.get("area", 0)),
        }
        ownership_ok = blob_belongs_to_line(page, line_index, blob, clean_cache)
        if not ownership_ok and mark["kind"] != "overline":
            continue
        if mark["kind"] == "other_mark":
            unattached.append(mark)
            continue

        direct_targets: list[tuple[float, dict[str, Any]]] = []
        fallback_targets: list[tuple[float, dict[str, Any]]] = []
        for unit in units:
            base_blob = base_by_id.get(int(unit["blob_id"]))
            if base_blob is None:
                continue
            base_bbox = [int(value) for value in base_blob["warped_bbox"]]
            if not dot_mark_plausible_for_base(mark, base_bbox):
                continue
            base_center = (base_bbox[0] + base_bbox[2]) / 2.0
            overlap = horizontal_overlap(mark_bbox, base_bbox)
            expanded = [base_bbox[0] - 4, base_bbox[1], base_bbox[2] + 4, base_bbox[3]]
            center_inside = expanded[0] <= mark_center <= expanded[2]
            left_edge_near = ownership_ok and mark["kind"] == "overline" and overline_near_left_edge(mark_bbox, base_bbox)
            if overlap > 0 or center_inside:
                distance = abs(mark_center - base_center)
                direct_targets.append((distance - overlap * 0.5, unit))
            elif left_edge_near:
                fallback_targets.append((abs(mark_center - base_center), unit))

        targets = direct_targets or fallback_targets

        if not targets:
            unattached.append(mark)
            continue

        targets.sort(key=lambda value: value[0])
        if mark["kind"] == "overline":
            attached_any = False
            for _, unit in targets:
                base_bbox = base_by_id[int(unit["blob_id"])]["warped_bbox"]
                base_label, _source = geometry_base_label(unit)
                unit_count = max(1, len(split_coptic_units(base_label or "")))
                target_positions = overline_target_unit_positions(mark_bbox, base_bbox, unit_count)
                if target_positions:
                    attached_mark = dict(mark)
                    if unit_count > 1:
                        attached_mark["target_unit_positions"] = target_positions
                    unit["attached_marks"].append(attached_mark)
                    attached_any = True
            if not attached_any:
                unattached.append(mark)
        else:
            target = redirect_below_dot_from_following_iota(mark, targets[0][1], units) or targets[0][1]
            target["attached_marks"].append(mark)
    return units, unattached


def token_candidate_strings(token: dict[str, Any]) -> list[dict[str, str]]:
    if token.get("edge_fragment"):
        return []

    candidates: list[dict[str, str]] = []
    manual_override = token.get("manual_override") or {}
    manual_label = manual_override.get("label")
    if is_coptic_string(manual_label):
        candidates.append({"text": base_sequence(str(manual_label)), "source": "manual_override"})
    geometric_override = token.get("geometric_override") or {}
    geometric_label = geometric_override.get("label")
    if is_coptic_string(geometric_label):
        candidates.append({"text": base_sequence(str(geometric_label)), "source": "geometric_override"})
    subcluster_override = token.get("subcluster_override") or {}
    subcluster_label = subcluster_override.get("label")
    if is_coptic_string(subcluster_label):
        candidates.append({"text": base_sequence(str(subcluster_label)), "source": "subcluster_override"})
    label = token.get("label")
    if is_coptic_string(label):
        candidates.append({"text": base_sequence(str(label)), "source": "assigned"})
    for candidate in token.get("candidates", []) or []:
        if is_coptic_string(str(candidate)):
            candidates.append({"text": base_sequence(str(candidate)), "source": "candidate"})
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, str]] = []
    for candidate in candidates:
        key = (candidate["text"], candidate["source"])
        if candidate["text"] and key not in seen:
            seen.add(key)
            result.append(candidate)
    return result


def has_connected_candidate(token: dict[str, Any]) -> bool:
    decision = token.get("review_decision") or {}
    if decision.get("label") == CONNECTED_REVIEW:
        return True
    if decision.get("confidence") in CONNECTED_DECISION_CONFIDENCE:
        return True
    return token.get("label") == CONNECTED_REVIEW


def mark_score(token: dict[str, Any], llm_units: list[dict[str, Any]]) -> float:
    llm_marks = {mark for unit in llm_units for mark in unit.get("marks", [])}
    attached_kinds = {mark.get("kind") for mark in token.get("attached_marks", [])}
    score = 0.0
    if "overline" in llm_marks:
        score += 0.8 if "overline" in attached_kinds else -0.35
    if "diaeresis" in llm_marks:
        score += 0.45 if attached_kinds else -0.15
    if "dot" in llm_marks:
        score += 0.35 if attached_kinds else -0.1
    if "overline" in attached_kinds and "overline" not in llm_marks:
        score -= 0.1
    return score


def match_options(token: dict[str, Any], llm_units: list[dict[str, Any]], start: int) -> list[MatchOption]:
    options: list[MatchOption] = []
    remaining = len(llm_units) - start
    if remaining <= 0:
        return options

    for candidate in token_candidate_strings(token):
        text = candidate["text"]
        consume = len(text)
        if consume <= 0 or consume > remaining:
            continue
        span = llm_units[start:start + consume]
        span_text = "".join(unit["base"] for unit in span)
        if span_text != text:
            continue
        base_score = 5.0 if candidate["source"] == "assigned" else 3.4
        if token.get("review"):
            base_score -= 0.35
        options.append(MatchOption(
            consume=consume,
            score=base_score + mark_score(token, span),
            text=text,
            kind="candidate_match",
            source=candidate["source"],
        ))

    if has_connected_candidate(token):
        width = float(token.get("geometry", {}).get("width", 0))
        max_span = min(4, remaining)
        for consume in range(1, max_span + 1):
            span = llm_units[start:start + consume]
            text = "".join(unit["base"] for unit in span)
            if not text:
                continue
            wide_bonus = min(width / 30.0, 1.4)
            span_bonus = 0.45 if consume > 1 else -0.15
            options.append(MatchOption(
                consume=consume,
                score=1.0 + wide_bonus + span_bonus + mark_score(token, span),
                text=text,
                kind="connected_span",
                source="llm_span",
            ))
    return options


def skip_ocr_score(token: dict[str, Any]) -> float:
    if not is_coptic_string(token.get("label")) and not token_candidate_strings(token):
        return -0.05
    if token.get("review"):
        return -0.45
    return -1.2


def align_line(units: list[dict[str, Any]], llm_units: list[dict[str, Any]]) -> tuple[float, list[dict[str, Any]]]:
    n = len(units)
    m = len(llm_units)
    neg_inf = -1_000_000.0
    scores = [[neg_inf for _ in range(m + 1)] for _ in range(n + 1)]
    back: list[list[tuple[int, int, dict[str, Any]] | None]] = [[None for _ in range(m + 1)] for _ in range(n + 1)]
    scores[0][0] = 0.0

    for i in range(n + 1):
        for j in range(m + 1):
            current = scores[i][j]
            if current <= neg_inf / 2:
                continue
            if i < n:
                value = current + skip_ocr_score(units[i])
                if value > scores[i + 1][j]:
                    scores[i + 1][j] = value
                    back[i + 1][j] = (i, j, {"op": "skip_ocr"})
            if j < m:
                value = current - 0.8
                if value > scores[i][j + 1]:
                    scores[i][j + 1] = value
                    back[i][j + 1] = (i, j, {"op": "skip_llm", "llm_index": j})
            if i < n and j < m:
                for option in match_options(units[i], llm_units, j):
                    value = current + option.score
                    ni = i + 1
                    nj = j + option.consume
                    if value > scores[ni][nj]:
                        scores[ni][nj] = value
                        back[ni][nj] = (i, j, {
                            "op": "match",
                            "consume": option.consume,
                            "text": option.text,
                            "kind": option.kind,
                            "source": option.source,
                            "score": round(option.score, 4),
                        })

    alignments: list[dict[str, Any] | None] = [None for _ in range(n)]
    i, j = n, m
    while i > 0 or j > 0:
        step = back[i][j]
        if step is None:
            break
        pi, pj, data = step
        if data["op"] == "match":
            alignments[pi] = data | {
                "llm_start": pj,
                "llm_end": j,
                "llm_units": llm_units[pj:j],
            }
        elif data["op"] == "skip_ocr":
            alignments[pi] = {"op": "skip_ocr"}
        i, j = pi, pj

    aligned_units: list[dict[str, Any]] = []
    for index, unit in enumerate(units):
        alignment = alignments[index] or {"op": "skip_ocr"}
        aligned = dict(unit)
        aligned["llm_alignment"] = summarize_alignment(unit, alignment)
        aligned_units.append(aligned)
    return round(scores[n][m], 4), aligned_units


def summarize_alignment(token: dict[str, Any], alignment: dict[str, Any]) -> dict[str, Any]:
    if alignment.get("op") != "match":
        return {"status": "llm_unaligned", "op": alignment.get("op", "none")}
    llm_units = alignment.get("llm_units", [])
    llm_text = "".join(unit.get("text", unit.get("base", "")) for unit in llm_units)
    llm_bases = "".join(unit.get("base", "") for unit in llm_units)
    llm_marks = sorted({mark for unit in llm_units for mark in unit.get("marks", [])})
    candidate_texts = {candidate["text"] for candidate in token_candidate_strings(token)}
    attached_kinds = sorted({mark.get("kind") for mark in token.get("attached_marks", [])})
    if alignment.get("kind") == "connected_span":
        status = "llm_suggests_connected_reading" if len(llm_bases) > 1 else "llm_supports_connected_single_char"
    elif llm_bases in candidate_texts:
        status = "llm_supports_candidate"
    else:
        status = "llm_outside_candidate_set"
    mark_status = "no_mark_signal"
    if llm_marks or attached_kinds:
        if "overline" in llm_marks and "overline" in attached_kinds:
            mark_status = "llm_and_geometry_overline"
        elif "overline" in llm_marks:
            mark_status = "llm_overline_without_attached_mark"
        elif "overline" in attached_kinds:
            mark_status = "attached_overline_without_llm_mark"
        else:
            mark_status = "non_overline_mark_signal"
    return {
        "status": status,
        "op": "match",
        "kind": alignment.get("kind"),
        "source": alignment.get("source"),
        "llm_text": llm_text,
        "llm_bases": llm_bases,
        "llm_marks": llm_marks,
        "mark_status": mark_status,
        "score": alignment.get("score"),
        "llm_start": alignment.get("llm_start"),
        "llm_end": alignment.get("llm_end"),
    }


def compact_unit(unit: dict[str, Any]) -> dict[str, Any]:
    return {
        "page": unit.get("page"),
        "line_index": unit.get("line_index"),
        "blob_id": unit.get("blob_id"),
        "split_metadata": unit.get("split_metadata"),
        "cluster": unit.get("cluster"),
        "label": unit.get("label"),
        "final_label": unit.get("final_label"),
        "final_label_source": unit.get("final_label_source"),
        "geometry_mark_kinds": unit.get("geometry_mark_kinds", []),
        "review": unit.get("review"),
        "candidates": unit.get("candidates", []),
        "manual_override": unit.get("manual_override"),
        "manual_warning": unit.get("manual_warning"),
        "subcluster_override": unit.get("subcluster_override"),
        "geometric_override": unit.get("geometric_override"),
        "editorial_override": unit.get("editorial_override"),
        "geometry": unit.get("geometry", {}),
        "edge_fragment": unit.get("edge_fragment", False),
        "attached_marks": unit.get("attached_marks", []),
        "llm_alignment": unit.get("llm_alignment", {}),
    }


def build_witness(
    line_sequences: list[dict[str, Any]],
    transcriptions: dict[tuple[str, int], str],
    review_decisions: dict[str, dict[str, Any]],
    split_dir: Path = BASE_SPLIT_DIR,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    split_cache: dict[str, dict[str, Any]] = {}
    clean_cache: dict[str, list[dict[str, Any]]] = {}
    composite_lines: list[dict[str, Any]] = []
    review_units: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "lines": 0,
        "lines_with_transcription": 0,
        "units": 0,
        "review_units": 0,
        "attached_marks": Counter(),
        "unattached_marks": Counter(),
        "witness_status": Counter(),
        "mark_status": Counter(),
        "clusters": defaultdict(Counter),
        "suggestions": defaultdict(Counter),
        "marked_suggestions": defaultdict(Counter),
        "mark_composites": defaultdict(Counter),
        "mark_examples": defaultdict(list),
    }

    for line in tqdm(line_sequences, desc="llm witness", unit="line"):
        page = str(line["page"])
        line_index = int(line["line_index"])
        llm_text = transcriptions.get((page, line_index))
        llm_units = split_coptic_units(llm_text or "")
        units, unattached = attach_non_base_marks(line, split_cache, clean_cache, split_dir)
        for unit in units:
            unit["review_decision"] = review_decisions.get(str(unit.get("cluster")), {})
        split_line = load_split_line(page, line_index, split_cache, split_dir)
        baseline_y = int((split_line or {}).get("baseline_y_warped", 39))
        units = fold_mark_like_units(units, baseline_y)
        units = [attach_geometry_final_label(unit) for unit in units]
        if llm_text is not None:
            summary["lines_with_transcription"] += 1
        score, aligned_units = align_line(units, llm_units) if llm_units else (0.0, [dict(unit, llm_alignment={"status": "llm_unavailable"}) for unit in units])
        aligned_units = [attach_fused_internal_marks(unit) for unit in aligned_units]

        for unit in aligned_units:
            summary["units"] += 1
            for mark in unit.get("attached_marks", []):
                summary["attached_marks"][mark["kind"]] += 1
            alignment = unit.get("llm_alignment", {})
            summary["witness_status"][alignment.get("status", "unknown")] += 1
            mark_status = alignment.get("mark_status", "no_mark_signal")
            summary["mark_status"][mark_status] += 1
            if mark_status != "no_mark_signal" or unit.get("attached_marks"):
                mark_key = unit.get("label") if is_coptic_string(unit.get("label")) else f"c{unit.get('cluster')}"
                marked_text = alignment.get("llm_text") or alignment.get("llm_bases") or ""
                if marked_text:
                    summary["mark_composites"][mark_key][marked_text] += 1
                if len(summary["mark_examples"][mark_status]) < 20:
                    summary["mark_examples"][mark_status].append(compact_unit(unit))
            if unit.get("review"):
                summary["review_units"] += 1
                cluster = str(unit.get("cluster"))
                status = alignment.get("status", "unknown")
                summary["clusters"][cluster][status] += 1
                suggestion = alignment.get("llm_bases") or alignment.get("llm_text") or ""
                if suggestion:
                    summary["suggestions"][cluster][suggestion] += 1
                marked_suggestion = alignment.get("llm_text") or ""
                if marked_suggestion:
                    summary["marked_suggestions"][cluster][marked_suggestion] += 1
                review_units.append(compact_unit(unit))
        for mark in unattached:
            summary["unattached_marks"][mark["kind"]] += 1

        composite_lines.append({
            "page": page,
            "line_index": line_index,
            "llm_text": llm_text,
            "llm_units": llm_units,
            "alignment_score": score,
            "unattached_marks": unattached,
            "units": [compact_unit(unit) for unit in aligned_units],
        })
        summary["lines"] += 1
    return composite_lines, review_units, freeze_summary(summary)


def freeze_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "lines": summary["lines"],
        "lines_with_transcription": summary["lines_with_transcription"],
        "units": summary["units"],
        "review_units": summary["review_units"],
        "attached_marks": dict(summary["attached_marks"]),
        "unattached_marks": dict(summary["unattached_marks"]),
        "witness_status": dict(summary["witness_status"]),
        "mark_status": dict(summary["mark_status"]),
        "clusters": {cluster: dict(counts) for cluster, counts in sorted(summary["clusters"].items())},
        "suggestions": {
            cluster: dict(counts.most_common(10))
            for cluster, counts in sorted(summary["suggestions"].items())
        },
        "marked_suggestions": {
            cluster: dict(counts.most_common(10))
            for cluster, counts in sorted(summary["marked_suggestions"].items())
        },
        "mark_composites": {
            key: dict(counts.most_common(12))
            for key, counts in sorted(summary["mark_composites"].items())
        },
        "mark_examples": dict(summary["mark_examples"]),
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return "; ".join(f"{key}:{value}" for key, value in sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def write_markdown(path: Path, summary: dict[str, Any], review_units: list[dict[str, Any]], max_examples: int) -> None:
    lines = [
        "# Kephalaia OCR LLM Witness",
        "",
        "Authority: blob order, cluster ids, candidate labels, and geometry. The LLM line is a constrained second witness only.",
        "",
        f"Lines: {summary['lines']}",
        f"Lines with LLM transcription: {summary['lines_with_transcription']}",
        f"Units: {summary['units']}",
        f"Review units: {summary['review_units']}",
        f"Attached marks: {format_counts(summary['attached_marks'])}",
        f"Unattached marks: {format_counts(summary['unattached_marks'])}",
        f"Witness statuses: {format_counts(summary['witness_status'])}",
        f"Mark statuses: {format_counts(summary['mark_status'])}",
        "",
        "## Cluster Summary",
        "",
        "| Cluster | Status Counts | Top LLM Suggestions | Top Marked Suggestions |",
        "|---|---|---|---|",
    ]
    for cluster, counts in summary["clusters"].items():
        suggestions = summary["suggestions"].get(cluster, {})
        marked = summary["marked_suggestions"].get(cluster, {})
        lines.append(f"| {cluster} | {format_counts(counts)} | {format_counts(suggestions)} | {format_counts(marked)} |")

    lines.extend(["", "## Review Examples", ""])
    by_status: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for unit in review_units:
        status = unit.get("llm_alignment", {}).get("status", "unknown")
        by_status[status].append(unit)

    for status in sorted(by_status):
        lines.append(f"### {status}")
        lines.append("")
        for unit in by_status[status][:max_examples]:
            alignment = unit.get("llm_alignment", {})
            marks = ",".join(mark["kind"] for mark in unit.get("attached_marks", [])) or "none"
            lines.append(
                f"- p{unit['page']} l{unit['line_index']} b{unit['blob_id']} c{unit['cluster']}: "
                f"label={unit.get('label')} candidates={','.join(unit.get('candidates') or [])} "
                f"llm={alignment.get('llm_text', '')} mark_status={alignment.get('mark_status', '')} attached={marks}"
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def current_label_base(decision: dict[str, Any]) -> str:
    label = decision.get("label") or ""
    return base_sequence(label) if is_coptic_string(label) else ""


def top_count(counts: dict[str, int]) -> tuple[str, int]:
    if not counts:
        return "", 0
    return max(counts.items(), key=lambda item: (item[1], item[0]))


def make_recommendations(summary: dict[str, Any], review_decisions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cluster, status_counts in summary["clusters"].items():
        decision = review_decisions.get(cluster, {})
        suggestions = summary.get("suggestions", {}).get(cluster, {})
        marked = summary.get("marked_suggestions", {}).get(cluster, {})
        total = sum(int(value) for value in status_counts.values())
        unavailable = int(status_counts.get("llm_unavailable", 0))
        available = total - unavailable
        top_suggestion, top_suggestion_count = top_count(suggestions)
        label_base = current_label_base(decision)
        label_support = int(suggestions.get(label_base, 0)) if label_base else 0
        connected_count = int(status_counts.get("llm_suggests_connected_reading", 0))
        candidate_count = int(status_counts.get("llm_supports_candidate", 0))
        confidence = decision.get("confidence") or "needs_review"
        decision_label = decision.get("label") or "review"

        if confidence == "needs_literal_reading":
            recommendation = "inspect_literal_readings"
            rationale = "Cluster-level geometry says connected/literal review; use marked LLM spans only to choose examples for visual confirmation."
        elif confidence == "needs_subcluster":
            recommendation = "subcluster_with_llm_priors"
            rationale = "Cluster is mixed; LLM spans can seed subcluster hypotheses but should not assign the whole cluster."
        elif confidence == "needs_vertical_split":
            if top_suggestion == "ⲓ" and candidate_count >= max(10, available * 0.25):
                recommendation = "split_vertical_iota_vs_margin"
                rationale = "LLM witness frequently supports iota; still split by margin position and lacuna context before assigning."
            else:
                recommendation = "split_vertical_by_geometry"
                rationale = "Vertical ambiguity remains geometry-led; LLM witness is weak or mixed."
        elif confidence in {"needs_mark_split", "needs_noise_split"}:
            recommendation = "keep_mark_noise_review"
            rationale = "LLM alignment is not reliable for lacuna dots/noise; resolve with mark geometry and visual sheets."
        elif confidence == "needs_character_split":
            recommendation = "character_subcluster_contextual"
            rationale = "Character candidates remain mixed; use LLM suggestions as a low-weight language prior after subclustering."
        elif label_base and label_support >= max(10, available * 0.15):
            recommendation = "llm_supports_current_label"
            rationale = "The current candidate receives meaningful constrained LLM support; promote only after visual spot-checking."
        elif label_base and top_suggestion and top_suggestion != label_base and top_suggestion_count >= max(10, label_support * 2):
            recommendation = "llm_conflicts_with_current_label"
            rationale = "The LLM witness prefers a different candidate; do not promote without targeted visual review."
        elif decision_label.startswith("_"):
            recommendation = "geometry_only_special_label"
            rationale = "Special labels such as brackets and marks should remain geometry-led; LLM text is only a locator."
        else:
            recommendation = "insufficient_llm_signal"
            rationale = "Available constrained LLM signal is too sparse or diffuse to change the review state."

        rows.append({
            "cluster": cluster,
            "decision": decision_label,
            "confidence": confidence,
            "available_witness_units": available,
            "status_counts": status_counts,
            "top_suggestions": dict(sorted(suggestions.items(), key=lambda item: (-item[1], item[0]))[:10]),
            "top_marked_suggestions": dict(sorted(marked.items(), key=lambda item: (-item[1], item[0]))[:10]),
            "current_label_support": label_support,
            "connected_span_count": connected_count,
            "recommendation": recommendation,
            "rationale": rationale,
        })
    return rows


def write_recommendations_markdown(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Kephalaia OCR Resolver Recommendations",
        "",
        "These recommendations combine the geometry-first review decision with constrained LLM witness counts. They are not final assignments.",
        "",
        "| Cluster | Current Decision | Witness Available | Recommendation | Top Suggestions | Rationale |",
        "|---|---|---:|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['cluster']} | {row['decision']} ({row['confidence']}) | "
            f"{row['available_witness_units']} | {row['recommendation']} | "
            f"{format_counts(row['top_suggestions'])} | {row['rationale']} |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_mark_witness_markdown(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Kephalaia OCR Mark Witness",
        "",
        "This report summarizes non-base blobs attached to base glyphs and compares them with combining marks in the constrained LLM line witness.",
        "",
        f"Attached marks: {format_counts(summary['attached_marks'])}",
        f"Unattached marks: {format_counts(summary['unattached_marks'])}",
        f"Mark statuses: {format_counts(summary['mark_status'])}",
        "",
        "## Marked Composites",
        "",
        "| Base/Cluster | Top Marked LLM Forms |",
        "|---|---|",
    ]
    for key, counts in summary.get("mark_composites", {}).items():
        lines.append(f"| {key} | {format_counts(counts)} |")

    lines.extend(["", "## Examples", ""])
    for status, examples in sorted(summary.get("mark_examples", {}).items()):
        lines.append(f"### {status}")
        lines.append("")
        for unit in examples:
            alignment = unit.get("llm_alignment", {})
            marks = ",".join(mark["kind"] for mark in unit.get("attached_marks", [])) or "none"
            lines.append(
                f"- p{unit['page']} l{unit['line_index']} b{unit['blob_id']} c{unit['cluster']}: "
                f"label={unit.get('label')} llm={alignment.get('llm_text', '')} "
                f"status={alignment.get('status', '')} attached={marks}"
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> Path:
    context_dir = resolve_repo_path(args.context_dir, DEFAULT_CONTEXT_DIR)
    transcription_dir = resolve_repo_path(args.transcription_dir, TRANSCRIPTION_DIR)
    out_dir = resolve_repo_path(args.out_dir, DEFAULT_OUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    line_sequences = load_line_sequences(context_dir / "line_sequences.jsonl")
    review_decisions = load_review_decisions(context_dir / "review_cluster_context.json")
    transcriptions = load_transcription_lines(transcription_dir)
    # Resolve split-dir from the contextual_review summary if not given.
    # build_contextual_review writes _summary.json with the split layer
    # the clusters_dir was built against; honoring it keeps the witness
    # aligned with the same character segmentation the clusters saw.
    split_default = BASE_SPLIT_DIR
    summary_path = context_dir / "_summary.json"
    if args.split_dir is None and summary_path.exists():
        recorded = (load_json(summary_path) or {}).get("split_dir")
        if recorded:
            recorded_path = Path(str(recorded))
            split_default = recorded_path if recorded_path.is_absolute() else REPO / recorded_path
    split_dir = resolve_repo_path(args.split_dir, split_default)
    composite_lines, review_units, summary = build_witness(line_sequences, transcriptions, review_decisions, split_dir)
    recommendations = make_recommendations(summary, review_decisions)

    write_jsonl(out_dir / "composite_line_sequences.jsonl", composite_lines)
    dump_json(out_dir / "review_llm_witness.json", review_units)
    dump_json(out_dir / "summary.json", summary)
    dump_json(out_dir / "resolver_recommendations.json", recommendations)
    write_markdown(out_dir / "review_llm_witness.md", summary, review_units, args.examples)
    write_recommendations_markdown(out_dir / "resolver_recommendations.md", recommendations)
    write_mark_witness_markdown(out_dir / "mark_witness.md", summary)
    print(out_dir)
    return out_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context-dir", type=str, default=None)
    parser.add_argument("--transcription-dir", type=str, default=None)
    parser.add_argument("--out-dir", type=str, default=None)
    parser.add_argument("--split-dir", type=str, default=None)
    parser.add_argument("--examples", type=int, default=12)
    return parser.parse_args()


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()