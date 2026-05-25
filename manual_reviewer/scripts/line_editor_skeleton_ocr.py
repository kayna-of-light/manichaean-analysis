#!/usr/bin/env python3
"""Score line-editor split boxes with the v2 skeleton OCR templates.

Input is a JSON object on stdin:
  {
    "body_path": ".../pNNN_text_body.jpg",
    "row_bbox": [x, y, w, h],
    "boxes": [{"id": "...", "x0": 0, "y0": 0, "x1": 0, "y1": 0}]
  }

The matcher intentionally reuses temp/projects/kephalaia_ocr_v2/char_separation/
skeleton_match_ocr.py so the line editor follows the same forward-only,
structural-width template discipline as the optimized p100 work.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

THIS = Path(__file__).resolve()
REPO = THIS.parents[2]
SCRIPT_DIR = REPO / "temp" / "projects" / "kephalaia_ocr_v2" / "char_separation"
sys.path.insert(0, str(SCRIPT_DIR))

from skeleton_match_ocr import (  # noqa: E402
    FORWARD_THRESHOLD,
    RELAXED_FORWARD_THRESHOLD,
    RELAXED_MAX_STRAY_RATIO,
    RELAXED_MIN_COVERAGE,
    WIDTH_SCALE_MAX,
    WIDTH_SCALE_MIN,
    _candidate_order,
    _score_candidates,
    estimate_row_frame,
    extract_row_binarized,
    frame_choices,
    load_templates,
    read_row,
    transformed_widths,
)


def _fixed_widths(box_w: int):
    def widths(natural_w: int, _remaining_w: int) -> list[int]:
        lo = max(1, int(round(natural_w * WIDTH_SCALE_MIN)))
        hi = int(round(natural_w * WIDTH_SCALE_MAX))
        if lo <= box_w <= hi:
            return [box_w]
        return []

    return widths


def _box_width(box: dict[str, Any]) -> int:
    return max(1, int(round(abs(float(box["x1"]) - float(box["x0"])))))


def _box_x0(box: dict[str, Any], row_x0: int) -> int:
    return max(0, int(round(min(float(box["x0"]), float(box["x1"])) - row_x0)))


def _match_box(box: dict[str, Any], *, row_x0: int, frames, templates, skel_dt, ink_bool) -> dict[str, Any]:
    box_w = _box_width(box)
    start_x = _box_x0(box, row_x0)
    required_right = start_x + box_w - 1
    candidates = _score_candidates(
        start_x,
        frames,
        box_w,
        templates,
        skel_dt,
        ink_bool,
        _fixed_widths(box_w),
        required_right=required_right,
        forward_threshold=FORWARD_THRESHOLD,
    )
    fallback = False
    if not candidates:
        candidates = [
            candidate
            for candidate in _score_candidates(
                start_x,
                frames,
                box_w,
                templates,
                skel_dt,
                ink_bool,
                _fixed_widths(box_w),
                required_right=required_right,
                forward_threshold=RELAXED_FORWARD_THRESHOLD,
            )
            if candidate.coverage >= RELAXED_MIN_COVERAGE
            and candidate.stray_ratio <= RELAXED_MAX_STRAY_RATIO
        ]
        fallback = True

    candidates = sorted(candidates, key=_candidate_order)
    if not candidates:
        return {
            "id": box.get("id"),
            "char": "?",
            "score": 0.0,
            "distortion": None,
            "coverage": 0,
            "stray_ratio": None,
            "fallback": fallback,
            "alternatives": [],
        }

    best = candidates[0]
    alternatives = []
    seen = {best.char}
    for candidate in candidates[1:]:
        if candidate.char in seen:
            continue
        seen.add(candidate.char)
        alternatives.append(
            {
                "char": candidate.char,
                "score": round(1.0 / (1.0 + candidate.residual), 3),
                "distortion": round(candidate.residual, 3),
                "coverage": candidate.coverage,
                "stray_ratio": round(candidate.stray_ratio, 3),
            }
        )
        if len(alternatives) >= 4:
            break

    return {
        "id": box.get("id"),
        "char": best.char,
        "score": round(1.0 / (1.0 + best.residual), 3),
        "distortion": round(best.residual, 3),
        "raw_distortion": round(best.fit.raw, 3),
        "coverage": best.coverage,
        "stray_ink": best.stray_ink,
        "stray_ratio": round(best.stray_ratio, 3),
        "frame_h": best.fit.frame_h,
        "frame_y": best.fit.y_frame_top,
        "fallback": fallback,
        "alternatives": alternatives,
    }


def _apply_relaxed_unknown_postprocess(matches: list[dict[str, Any]], *, frames, templates, binarized) -> list[dict[str, Any]]:
    """Mirror skeleton_match_ocr.py's page-processing replacement pass for ? spans."""
    ink_bool = binarized > 127
    skel_dt = distance_transform_edt(~ink_bool).astype(np.float32)
    out = [dict(match) for match in matches]
    for match_index, match in enumerate(out):
        if match.get("char") != "?":
            continue
        query_x0 = int(match["x0"])
        query_x1 = int(match["x1"])
        query_width = query_x1 - query_x0 + 1
        if query_width < 2:
            continue
        relaxed_candidates = _score_candidates(
            query_x0,
            frames,
            query_width,
            templates,
            skel_dt,
            ink_bool,
            transformed_widths,
            forward_threshold=RELAXED_FORWARD_THRESHOLD,
        )
        good = [
            candidate
            for candidate in relaxed_candidates
            if candidate.coverage >= RELAXED_MIN_COVERAGE
            and candidate.stray_ratio <= RELAXED_MAX_STRAY_RATIO
        ]
        if not good:
            continue
        good.sort(key=_candidate_order)
        best = good[0]
        advance = max(1, min(query_width, best.char_w))
        second = next((candidate for candidate in good[1:] if candidate.char != best.char), None)
        out[match_index] = {
            "char": best.char,
            "x0": best.x,
            "x1": best.x + advance - 1,
            "score": round(1.0 / (1.0 + best.residual), 3),
            "distortion": round(best.residual, 2),
            "raw_distortion": round(best.fit.raw, 2),
            "stroke_shift": round(best.fit.max_stroke_shift, 2),
            "anchor_shift": round(best.fit.max_anchor_shift, 2),
            "frame_h": best.fit.frame_h,
            "frame_y": best.fit.y_frame_top,
            "coverage": best.coverage,
            "stray_ink": best.stray_ink,
            "stray_ratio": round(best.stray_ratio, 3),
            "margin": round(second.residual - best.residual, 2) if second else 0.0,
            "alt": second.char if second else "",
            "alt_score": round(1.0 / (1.0 + second.residual), 3) if second else 0.0,
            "alt_distortion": round(second.residual, 2) if second else 0.0,
            "fallback": True,
        }
    return out


def _absolute_match(match: dict[str, Any], row_x0: int, row_y0: int) -> dict[str, Any]:
    return {
        **match,
        "abs_x0": row_x0 + int(match.get("x0", 0)),
        "abs_x1": row_x0 + int(match.get("x1", 0)),
        "abs_y0": row_y0,
    }


def _box_span(box: dict[str, Any]) -> tuple[float, float]:
    return (
        min(float(box["x0"]), float(box["x1"])),
        max(float(box["x0"]), float(box["x1"])),
    )


def _overlap_width(left_a: float, right_a: float, left_b: float, right_b: float) -> float:
    return max(0.0, min(right_a, right_b) - max(left_a, left_b))


def _project_row_match_to_box(
    box: dict[str, Any],
    row_matches: list[dict[str, Any]],
) -> dict[str, Any]:
    box_left, box_right = _box_span(box)
    box_center = (box_left + box_right) / 2.0
    viable = []
    for match in row_matches:
        if match.get("char") == " ":
            continue
        match_left = float(match["abs_x0"])
        match_right = float(match["abs_x1"] + 1)
        overlap = _overlap_width(box_left, box_right, match_left, match_right)
        center_inside = match_left <= box_center <= match_right
        if overlap <= 0 and not center_inside:
            continue
        match_width = max(1.0, match_right - match_left)
        box_width = max(1.0, box_right - box_left)
        overlap_ratio = overlap / min(match_width, box_width)
        distance = abs(((match_left + match_right) / 2.0) - box_center)
        viable.append((overlap_ratio, -distance, match))

    if not viable:
        return {
            "id": box.get("id"),
            "char": "?",
            "score": 0.0,
            "distortion": None,
            "coverage": 0,
            "stray_ratio": None,
            "fallback": False,
            "alternatives": [],
            "source": "row_scan_unmapped",
        }

    viable.sort(key=lambda item: (-item[0], -item[1]))
    best = viable[0][2]
    alternatives = []
    alt_char = best.get("alt")
    if alt_char:
        alternatives.append({
            "char": alt_char,
            "score": best.get("alt_score", 0.0),
            "distortion": best.get("alt_distortion", 0.0),
            "coverage": 0,
            "stray_ratio": 0.0,
        })
    return {
        "id": box.get("id"),
        "char": best.get("char", "?"),
        "score": best.get("score", 0.0),
        "distortion": best.get("distortion"),
        "raw_distortion": best.get("raw_distortion"),
        "coverage": best.get("coverage", 0),
        "stray_ink": best.get("stray_ink"),
        "stray_ratio": best.get("stray_ratio"),
        "frame_h": best.get("frame_h"),
        "frame_y": best.get("frame_y"),
        "fallback": bool(best.get("fallback")),
        "alternatives": alternatives,
        "source": "row_scan",
        "row_x0": best.get("abs_x0"),
        "row_x1": best.get("abs_x1"),
    }


def run(payload: dict[str, Any]) -> dict[str, Any]:
    body_path = Path(str(payload["body_path"]))
    row_bbox = payload["row_bbox"]
    boxes = payload.get("boxes", [])
    if not body_path.exists():
        raise FileNotFoundError(body_path)

    body = np.asarray(Image.open(body_path).convert("L"))
    row = {"bbox": row_bbox}
    binarized, skeleton, row_x0, row_y0 = extract_row_binarized(body, row)
    if skeleton.sum() == 0:
        return {"ok": True, "template_count": 0, "matches": []}

    templates = load_templates()
    base_top, base_h = estimate_row_frame(binarized)
    frames = frame_choices(base_top, base_h, binarized.shape[0])
    row_matches = read_row(binarized, skeleton > 0, templates, frames=frames)
    row_matches = _apply_relaxed_unknown_postprocess(
        row_matches,
        frames=frames,
        templates=templates,
        binarized=binarized,
    )
    absolute_row_matches = [_absolute_match(match, row_x0, row_y0) for match in row_matches]
    matches = [_project_row_match_to_box(box, absolute_row_matches) for box in boxes]
    return {
        "ok": True,
        "method": "row_scan_projected_to_editor_boxes",
        "template_count": len(templates),
        "frame_count": len(frames),
        "recognized": "".join(match.get("char", "") for match in row_matches),
        "row_matches": absolute_row_matches,
        "matches": matches,
    }


def main() -> None:
    payload = json.loads(sys.stdin.read())
    result = run(payload)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()