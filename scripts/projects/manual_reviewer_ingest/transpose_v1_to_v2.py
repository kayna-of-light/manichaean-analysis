"""Reproduce manual-reviewer initial data from the review-sheet ground truth.

v2 is leading:
- canvas:  output/projects/kephalaia_ocr_v2/line_body_split/text_body/p{NNN}_text_body.jpg
- rows:    output/projects/kephalaia_ocr_v2/body_geometry/pages/p{NNN}_geometry.json
            (geometry_rows[].baseline_y + x_span in v2 text_body coordinates)

v1 supplies character evidence in the corrected split body's image coordinates:
- tokens:  output/projects/kephalaia_ocr/llm_witness/clusters_shape_padded_split_bodycrop_corrected_k240/composite_line_sequences.jsonl
- boxes:   output/projects/kephalaia_ocr/pages_base_split_chars_bodycrop_corrected/keph_p{NNN}_lines_base_split.json
            (lines[].blobs[].img_quad in the corrected body-crop image frame)

The character labels are resolved by importing the same choose_display_label()
used by build_page_review_sheet.py. The review sheet is the ground truth; this
script does not re-infer labels with a separate fallback chain.

For geometry, transform coordinate systems, not glyphs: corrected v1 body-crop
image coordinates -> original page coordinates -> v2 rotated/dewarped page
coordinates -> saved v2 page crop -> v2 text-body crop. v2 row boxes remain the
final membership gate after the transform.

Output: manual_reviewer/data/ingest/
    initial_baseline/p{NNN}.json
    assets/v2/text_body/p{NNN}_text_body.jpg
    assets/v2/body_geometry/pages/p{NNN}_geometry.json
    artifacts/page_review_sheets/keph_p{NNN}_review.{json,html,png} when present
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
V1_OCR = REPO / "output" / "projects" / "kephalaia_ocr"
V2_OCR = REPO / "output" / "projects" / "kephalaia_ocr_v2"
WEBAPP_DIR = REPO / "manual_reviewer"
OUT_ROOT = WEBAPP_DIR / "data" / "ingest"
INITIAL_DIR = OUT_ROOT / "initial_baseline"
SUMMARY_PATH = OUT_ROOT / "summary.json"
INGEST_TEXT_BODY_DIR = OUT_ROOT / "assets" / "v2" / "text_body"
INGEST_BODY_GEOM_DIR = OUT_ROOT / "assets" / "v2" / "body_geometry" / "pages"
INGEST_REVIEW_SHEET_DIR = OUT_ROOT / "artifacts" / "page_review_sheets"

V1_LINE_SPLIT_DIR = V1_OCR / "pages_base_split_chars_bodycrop_corrected"
V1_CLEAN_DIR = V1_OCR / "pages"
V1_LINE_SEQUENCES = (
    V1_OCR
    / "llm_witness"
    / "clusters_shape_padded_split_bodycrop_corrected_k240"
    / "composite_line_sequences.jsonl"
)
V2_BODY_GEOM_DIR = V2_OCR / "body_geometry" / "pages"
V2_TEXT_BODY_DIR = V2_OCR / "line_body_split" / "text_body"
V2_LINE_BODY_METADATA_DIR = V2_OCR / "line_body_split" / "metadata"
REVIEW_SHEET_SCRIPT = REPO / "scripts" / "projects" / "kephalaia_ocr" / "build_page_review_sheet.py"
V2_DESKEW_SCRIPT = REPO / "scripts" / "projects" / "kephalaia_ocr_v2" / "deskew_and_crop.py"
REVIEW_SHEET_ARTIFACT_DIR = REPO / "temp" / "projects" / "kephalaia_ocr" / "page_review_sheets"
REVIEW_SHEET_IMAGE_DIR = V1_OCR / "page_review_sheets"
V1_CONTEXT_DIR = V1_OCR / "contextual_review" / "clusters_shape_padded_split_bodycrop_corrected_k240"
V1_BODY_FRAME_DIRS = (
    V1_OCR / "pages",
    REPO / "temp" / "projects" / "kephalaia_ocr" / "body_crop_debug",
)

ROW_GATE_X_PAD = 0.0
ROW_GATE_Y_PAD = 0.0
V1_STRIP_MARGIN_X = 8.0
V1_STRIP_MARGIN_Y = 4.0


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO)).replace("\\", "/")
    except ValueError:
        return str(path)


def load_review_sheet_module():
    spec = importlib.util.spec_from_file_location("kephalaia_review_sheet", REVIEW_SHEET_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {REVIEW_SHEET_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REVIEW_SHEET = load_review_sheet_module()


def load_v2_deskew_module():
    if str(V2_DESKEW_SCRIPT.parent) not in sys.path:
        sys.path.insert(0, str(V2_DESKEW_SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("kephalaia_v2_deskew", V2_DESKEW_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {V2_DESKEW_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


V2_DESKEW = load_v2_deskew_module()


def primary_overline_mark_id(token: dict[str, Any]) -> int | None:
    for mark in token.get("attached_marks") or []:
        if mark.get("kind") in {"overline", "horizontal_mark"} and mark.get("id") is not None:
            return int(mark["id"])
    return None


def resolve_review_sheet_label(token: dict[str, Any], review_decisions: dict[str, dict[str, Any]]) -> tuple[str, str, str | None, int | None]:
    text, source, _color, raw_label = REVIEW_SHEET.choose_display_label(
        token,
        review_decisions,
        True,
    )
    return str(text), str(source), (str(raw_label) if raw_label else None), primary_overline_mark_id(token)


def copy_if_exists(src: Path, dst: Path, dry_run: bool) -> bool:
    if not src.exists():
        return False
    if not dry_run:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return True


def copy_page_assets(page: str, dry_run: bool) -> dict[str, Any]:
    copied: dict[str, Any] = {}
    copied["text_body"] = copy_if_exists(
        V2_TEXT_BODY_DIR / f"p{page}_text_body.jpg",
        INGEST_TEXT_BODY_DIR / f"p{page}_text_body.jpg",
        dry_run,
    )
    copied["body_geometry"] = copy_if_exists(
        V2_BODY_GEOM_DIR / f"p{page}_geometry.json",
        INGEST_BODY_GEOM_DIR / f"p{page}_geometry.json",
        dry_run,
    )
    copied["review_manifest"] = copy_if_exists(
        REVIEW_SHEET_ARTIFACT_DIR / f"keph_p{page}_review.json",
        INGEST_REVIEW_SHEET_DIR / f"keph_p{page}_review.json",
        dry_run,
    )
    copied["review_html"] = copy_if_exists(
        REVIEW_SHEET_ARTIFACT_DIR / f"keph_p{page}_review.html",
        INGEST_REVIEW_SHEET_DIR / f"keph_p{page}_review.html",
        dry_run,
    )
    copied["review_png"] = copy_if_exists(
        REVIEW_SHEET_IMAGE_DIR / f"keph_p{page}_review.png",
        INGEST_REVIEW_SHEET_DIR / f"keph_p{page}_review.png",
        dry_run,
    )
    return copied


@dataclass
class V1Blob:
    blob_id: int
    warped_bbox: list[int]
    img_quad: list[list[float]]


@dataclass
class V1Line:
    blobs: list[V1Blob]
    warped_size: tuple[float, float]
    baseline_y_warped: float
    source_x0: float
    source_x1: float
    source_y0: float
    source_y1: float


@dataclass
class V1PageGeometry:
    lines_by_line: dict[int, V1Line]
    image_size: tuple[int, int]
    body_frame: "BodyFrame"


@dataclass
class BodyFrame:
    x0: float
    y0: float
    x1: float
    y1: float
    image_size: tuple[int, int]
    source: str


@dataclass
class V2FrameTransform:
    rotation: Any
    dewarp_map_y: Any | None
    crop_origin: tuple[float, float]
    text_origin: tuple[float, float]
    source_size: tuple[int, int]
    text_size: tuple[int, int]
    inverse_column_cache: dict[int, tuple[Any, Any]]

    def dewarp_point(self, x: float, y: float) -> tuple[float, float]:
        if self.dewarp_map_y is None:
            return x, y
        height, width = self.dewarp_map_y.shape[:2]
        xi = int(round(max(0.0, min(float(width - 1), x))))
        if xi not in self.inverse_column_cache:
            y_out = V2_DESKEW.np.arange(height, dtype=V2_DESKEW.np.float64)
            y_src = V2_DESKEW.np.asarray(self.dewarp_map_y[:, xi], dtype=V2_DESKEW.np.float64)
            order = V2_DESKEW.np.argsort(y_src)
            self.inverse_column_cache[xi] = (y_src[order], y_out[order])
        y_src, y_out = self.inverse_column_cache[xi]
        y2 = float(V2_DESKEW.np.interp(y, y_src, y_out))
        return x, y2

    def point_to_text_body(self, x: float, y: float) -> list[float]:
        vec = V2_DESKEW.np.asarray([x, y, 1.0], dtype=V2_DESKEW.np.float64)
        rotated = vec @ self.rotation.T
        dewarped_x, dewarped_y = self.dewarp_point(float(rotated[0]), float(rotated[1]))
        crop_x = dewarped_x - self.crop_origin[0]
        crop_y = dewarped_y - self.crop_origin[1]
        return [round(crop_x - self.text_origin[0], 3), round(crop_y - self.text_origin[1], 3)]


@dataclass
class V2Row:
    line_index: int
    source: str
    baseline_y: float
    x_span: tuple[float, float]
    bbox: tuple[float, float, float, float] | None


def load_jsonl_by_page(path: Path) -> dict[str, list[dict[str, Any]]]:
    """Return {page: [line_record, ...]} grouped from line_sequences.jsonl."""
    out: dict[str, list[dict[str, Any]]] = {}
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            out.setdefault(rec["page"], []).append(rec)
    for page, recs in out.items():
        recs.sort(key=lambda r: r["line_index"])
    return out


def _bbox_frame_size(bbox: dict[str, Any]) -> tuple[int, int]:
    return (int(round(float(bbox["x1"]) - float(bbox["x0"]))), int(round(float(bbox["y1"]) - float(bbox["y0"]))))


def load_v1_body_frame(page: str, image_size: tuple[int, int]) -> BodyFrame | None:
    candidates: list[tuple[int, BodyFrame]] = []
    for root in V1_BODY_FRAME_DIRS:
        bbox_path = root / f"keph_p{page}_body_bbox.json"
        if not bbox_path.exists():
            continue
        data = json.loads(bbox_path.read_text(encoding="utf-8"))
        bbox = data.get("bbox") or {}
        if not all(key in bbox for key in ("x0", "y0", "x1", "y1")):
            continue
        bbox_size = _bbox_frame_size(bbox)
        score = abs(bbox_size[0] - image_size[0]) + abs(bbox_size[1] - image_size[1])
        img_path = root / f"keph_p{page}_body.jpg"
        if img_path.exists():
            img = V2_DESKEW.cv2.imread(str(img_path))
            if img is not None:
                actual_size = (int(img.shape[1]), int(img.shape[0]))
                score = min(score, abs(actual_size[0] - image_size[0]) + abs(actual_size[1] - image_size[1]))
        frame = BodyFrame(
            x0=float(bbox["x0"]),
            y0=float(bbox["y0"]),
            x1=float(bbox["x1"]),
            y1=float(bbox["y1"]),
            image_size=image_size,
            source=relative(bbox_path),
        )
        if score == 0:
            return frame
        candidates.append((score, frame))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    score, frame = candidates[0]
    frame.source = f"{frame.source} (nearest frame; size delta {score}px)"
    return frame


def load_v1_blobs(page: str) -> V1PageGeometry | None:
    """Return v1 character geometry in corrected body-crop image coordinates."""
    path = V1_LINE_SPLIT_DIR / f"keph_p{page}_lines_base_split.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    img_size = tuple(data.get("image_size") or (0, 0))
    body_frame = load_v1_body_frame(page, img_size)  # type: ignore[arg-type]
    if body_frame is None:
        return None
    clean_by_index: dict[int, dict[str, Any]] = {}
    clean_line_step: float | None = None
    clean_path = V1_CLEAN_DIR / f"kraken_p{page}_body_clean.json"
    if clean_path.exists():
        clean_data = json.loads(clean_path.read_text(encoding="utf-8"))
        if clean_data.get("h_top") is not None and clean_data.get("h_bot") is not None:
            clean_line_step = float(clean_data["h_top"]) + float(clean_data["h_bot"])
        for clean_line in clean_data.get("lines", []):
            clean_by_index[int(clean_line.get("index", -1))] = clean_line

    out: dict[int, V1Line] = {}
    for ln in data.get("lines", []):
        idx = int(ln.get("line_index", -1))
        warped_size_raw = ln.get("warped_size") or [1, 1]
        warped_size = (float(warped_size_raw[0]), float(warped_size_raw[1]))
        baseline_y_warped = float(ln.get("baseline_y_warped", max(warped_size[1] - 1.0, 1.0)))
        source_x0 = V1_STRIP_MARGIN_X
        source_x1 = max(warped_size[0] - 1.0 - V1_STRIP_MARGIN_X, source_x0 + 1.0)
        source_y0 = V1_STRIP_MARGIN_Y
        source_y1 = max(warped_size[1] - 1.0 - V1_STRIP_MARGIN_Y, source_y0 + 1.0)
        if clean_line_step is not None:
            full_step = clean_line_step + (2.0 * V1_STRIP_MARGIN_Y)
            if full_step > 0.0:
                strip_height = max(warped_size[1] - 1.0, 1.0)
                source_y0 = (V1_STRIP_MARGIN_Y / full_step) * strip_height
                source_y1 = ((V1_STRIP_MARGIN_Y + clean_line_step) / full_step) * strip_height
        clean_line = clean_by_index.get(idx)
        if clean_line:
            quad = clean_line.get("quad") or []
            if len(quad) == 4 and clean_line.get("ink_xmin") is not None and clean_line.get("ink_xmax") is not None:
                left_x = (float(quad[0][0]) + float(quad[3][0])) / 2.0
                right_x = (float(quad[1][0]) + float(quad[2][0])) / 2.0
                strip_span = max(right_x - left_x, 1.0)
                strip_width = max(warped_size[0] - 1.0, 1.0)
                source_x0 = (float(clean_line["ink_xmin"]) - left_x) / strip_span * strip_width
                source_x1 = (float(clean_line["ink_xmax"]) - left_x) / strip_span * strip_width
                if source_x1 <= source_x0:
                    source_x0 = V1_STRIP_MARGIN_X
                    source_x1 = max(warped_size[0] - 1.0 - V1_STRIP_MARGIN_X, source_x0 + 1.0)
        blobs: list[V1Blob] = []
        for b in ln.get("blobs", []):
            warped_bbox = b.get("warped_bbox") or []
            img_quad = b.get("img_quad") or []
            if len(warped_bbox) != 4:
                continue
            if len(img_quad) != 4 or any(len(point) != 2 for point in img_quad):
                continue
            blobs.append(
                V1Blob(
                    blob_id=int(b.get("id")),
                    warped_bbox=[int(value) for value in warped_bbox],
                    img_quad=[[float(point[0]), float(point[1])] for point in img_quad],
                )
            )
        out[idx] = V1Line(
            blobs=blobs,
            warped_size=warped_size,
            baseline_y_warped=baseline_y_warped,
            source_x0=source_x0,
            source_x1=source_x1,
            source_y0=source_y0,
            source_y1=max(source_y1, source_y0 + 1.0),
        )
    return V1PageGeometry(
        lines_by_line=out,
        image_size=img_size,  # type: ignore[arg-type]
        body_frame=body_frame,
    )


def load_v2_rows(page: str) -> tuple[list[V2Row], tuple[int, int]] | None:
    path = V2_BODY_GEOM_DIR / f"p{page}_geometry.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    img_size = tuple(data.get("image_size") or (0, 0))
    rows: list[V2Row] = []
    for r in data.get("geometry_rows", []):
        bbox = r.get("bbox")
        baseline_y = r.get("baseline_y")
        if baseline_y is None:
            baseline_y = r.get("median_line_y") or r.get("center_y")
        if baseline_y is None:
            continue
        x_span = r.get("baseline_span") or r.get("x_span") or r.get("median_line_span")
        if not x_span:
            continue
        rows.append(
            V2Row(
                line_index=int(r.get("index", -1)),
                source=str(r.get("source") or ""),
                baseline_y=float(baseline_y),
                x_span=(float(x_span[0]), float(x_span[1])),
                bbox=(
                    tuple(float(v) for v in bbox)  # type: ignore[arg-type]
                    if bbox and len(bbox) == 4
                    else None
                ),
            )
        )
    rows.sort(key=lambda r: r.baseline_y)
    return rows, img_size  # type: ignore[return-value]


def build_v2_frame_transform(page: str) -> V2FrameTransform | None:
    metadata_path = V2_LINE_BODY_METADATA_DIR / f"p{page}.json"
    img_path = V2_DESKEW.IMAGES_DIR / f"keph_p{page}.jpg"
    kraken_path = V2_DESKEW.KRAKEN_DIR / f"kraken_p{page}_lines.json"
    if not metadata_path.exists() or not img_path.exists() or not kraken_path.exists():
        return None

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    source_size = tuple(int(value) for value in metadata.get("source_size") or (0, 0))
    text_body = metadata.get("text_body") or {}
    common_y = metadata.get("common_y") or {}
    text_x_range = text_body.get("x_range") or [0, 0]
    text_size = tuple(int(value) for value in text_body.get("size") or (0, 0))
    text_origin = (float(text_x_range[0]), float(common_y.get("y0", 0)))

    img = V2_DESKEW.cv2.imread(str(img_path))
    if img is None:
        return None
    lines = json.loads(kraken_path.read_text(encoding="utf-8")).get("lines", [])
    height, width = img.shape[:2]

    cleaned = V2_DESKEW.mask_scanner_artifacts(img)
    phi, _info = V2_DESKEW.estimate_vertical_correction(lines, width)
    rotated, rotated_lines, rotation = V2_DESKEW.rotate_image_and_lines(cleaned, lines, phi)
    map_x, map_y, _dewarp_info = V2_DESKEW.build_dewarp_maps(rotated_lines, width, height)
    warped = rotated if map_x is None else V2_DESKEW.apply_dewarp(rotated, map_x, map_y)

    gray = V2_DESKEW.cv2.cvtColor(warped, V2_DESKEW.cv2.COLOR_BGR2GRAY)
    _thr, binimg = V2_DESKEW.cv2.threshold(
        gray,
        0,
        255,
        V2_DESKEW.cv2.THRESH_BINARY_INV | V2_DESKEW.cv2.THRESH_OTSU,
    )

    left_clip_used = 0
    column_x = V2_DESKEW.compute_column_x_rotated(rotated_lines, width, height)
    if column_x is not None:
        left_clip_used = int(max(0, round(column_x - V2_DESKEW.LEFT_COLUMN_MARGIN_PX)))
        if left_clip_used > 0:
            binimg[:, :left_clip_used] = 0

    right_clip_used = width
    right_x = V2_DESKEW.compute_right_x_rotated(rotated_lines, width, height)
    if right_x is not None:
        right_clip_used = int(min(width, round(right_x + V2_DESKEW.RIGHT_COLUMN_MARGIN_PX)))
        if right_clip_used < width:
            binimg[:, right_clip_used:] = 0

    top_clip_used = 0
    bottom_clip_used = height
    top_y, bottom_y = V2_DESKEW.compute_top_bottom_y_rotated(rotated_lines, width, height)
    if top_y is not None:
        top_clip_used = int(max(0, round(top_y - V2_DESKEW.TOP_BOTTOM_MARGIN_PX)))
        if top_clip_used > 0:
            binimg[:top_clip_used, :] = 0
    if bottom_y is not None:
        bottom_clip_used = int(min(height, round(bottom_y + V2_DESKEW.TOP_BOTTOM_MARGIN_PX)))
        if bottom_clip_used < height:
            binimg[bottom_clip_used:, :] = 0

    ix0, iy0, ix1, iy1 = V2_DESKEW.find_ink_bbox(binimg > 0)
    ix0 = max(left_clip_used, ix0 - V2_DESKEW.BBOX_PAD_PX)
    iy0 = max(top_clip_used, iy0 - V2_DESKEW.BBOX_PAD_PX)
    ix1 = min(right_clip_used, ix1 + V2_DESKEW.BBOX_PAD_PX)
    iy1 = min(bottom_clip_used, iy1 + V2_DESKEW.BBOX_PAD_PX)
    ix1 = min(width, ix1 + V2_DESKEW.RIGHT_EDGE_EXTRA_OFFSET_PX_BY_PAGE.get(page, 0))

    pre_trim_size = (int(ix1 - ix0), int(iy1 - iy0))
    crop = warped[iy0:iy1, ix0:ix1]
    _trimmed_crop, ruler_left_trim = V2_DESKEW.refine_left_edge_from_line_number_ruler(crop)
    post_trim_size = (int(ix1 - ix0 - ruler_left_trim), int(iy1 - iy0))
    if source_size == pre_trim_size:
        crop_origin = (float(ix0), float(iy0))
    elif source_size == post_trim_size:
        crop_origin = (float(ix0 + ruler_left_trim), float(iy0))
    else:
        crop_origin = recover_saved_crop_origin(page, warped, source_size, (ix0, iy0), (ix0 + ruler_left_trim, iy0))
        if crop_origin is None:
            crop_origin = (float(ix0), float(iy0))

    return V2FrameTransform(
        rotation=rotation,
        dewarp_map_y=map_y,
        crop_origin=crop_origin,
        text_origin=text_origin,
        source_size=source_size,  # type: ignore[arg-type]
        text_size=text_size,  # type: ignore[arg-type]
        inverse_column_cache={},
    )


def recover_saved_crop_origin(
    page: str,
    warped: Any,
    source_size: tuple[int, int],
    *origins: tuple[int, int],
) -> tuple[float, float] | None:
    saved_path = V2_OCR / "pages_cropped" / f"keph_p{page}.jpg"
    saved = V2_DESKEW.cv2.imread(str(saved_path))
    if saved is None:
        return None
    saved_h, saved_w = saved.shape[:2]
    if (saved_w, saved_h) != source_size:
        return None
    height, width = warped.shape[:2]
    best: tuple[float, int, int] | None = None
    for origin_x, origin_y in origins:
        for y in range(max(0, origin_y - 20), min(height - saved_h, origin_y + 20) + 1):
            for x in range(max(0, origin_x - 20), min(width - saved_w, origin_x + 20) + 1):
                crop = warped[y:y + saved_h, x:x + saved_w]
                if crop.shape[:2] != (saved_h, saved_w):
                    continue
                score = float(V2_DESKEW.cv2.absdiff(saved, crop).mean())
                if best is None or score < best[0]:
                    best = (score, x, y)
    if best is None:
        return None
    return (float(best[1]), float(best[2]))


def transform_img_quad(v1_page: V1PageGeometry, v2_frame: V2FrameTransform, quad: list[list[float]]) -> list[list[float]] | None:
    if len(quad) != 4:
        return None
    src_w, src_h = v1_page.image_size
    if src_w <= 0 or src_h <= 0:
        return None
    frame = v1_page.body_frame
    scale_x = (frame.x1 - frame.x0) / float(src_w)
    scale_y = (frame.y1 - frame.y0) / float(src_h)
    out: list[list[float]] = []
    for x, y in quad:
        full_x = frame.x0 + float(x) * scale_x
        full_y = frame.y0 + float(y) * scale_y
        out.append(v2_frame.point_to_text_body(full_x, full_y))
    return out


def quad_axis_aligned(quad: list[list[float]]) -> list[float]:
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    return [min(xs), min(ys), max(xs), max(ys)]


def transpose_page(
    page: str,
    sequences_by_page: dict[str, list[dict[str, Any]]],
    review_decisions: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    v1_load = load_v1_blobs(page)
    v2_load = load_v2_rows(page)
    v2_frame = build_v2_frame_transform(page)
    if v1_load is None:
        return {"page": page, "status": "missing_v1_geometry"}
    if v2_load is None:
        return {"page": page, "status": "missing_v2_geometry"}
    if v2_frame is None:
        return {"page": page, "status": "missing_v2_frame_transform"}
    v1_lines_by_line = v1_load.lines_by_line
    v2_rows, v2_img_size = v2_load

    sequence_rows = sequences_by_page.get(page) or []
    # Build {line_index: units[]} from the v1 composite witness. This is the
    # same source used by the review sheet: attached marks are already folded
    # into their base unit, and standalone marks remain as their own units.
    v1_tokens_by_line: dict[int, list[dict[str, Any]]] = {}
    for rec in sequence_rows:
        v1_tokens_by_line[int(rec["line_index"])] = rec.get("units") or rec.get("tokens", [])

    # Align by ordinal: take v1 line indices that have BOTH tokens and blobs.
    v1_indices = sorted(
        idx for idx in v1_lines_by_line if idx in v1_tokens_by_line and v1_lines_by_line[idx].blobs
    )
    n_v1 = len(v1_indices)
    n_v2 = len(v2_rows)
    aligned: list[tuple[int, V2Row]] = []
    # Greedy ordinal alignment. If counts differ we still emit as many as match.
    for k, v2_row in enumerate(v2_rows):
        if k >= n_v1:
            break
        aligned.append((v1_indices[k], v2_row))

    out_lines: list[dict[str, Any]] = []
    excluded_token_total = 0
    for v1_idx, v2_row in aligned:
        v1_line = v1_lines_by_line[v1_idx]
        v1_blobs = v1_line.blobs

        # v2 row bbox is the authoritative membership gate after the page-frame transform.
        row_bbox = v2_row.bbox  # (x, y, w, h) or None

        def _inside_v2_row(aabb: list[float]) -> bool:
            if row_bbox is None:
                return True
            rx, ry, rw, rh = row_bbox
            cx = (aabb[0] + aabb[2]) / 2.0
            cy = (aabb[1] + aabb[3]) / 2.0
            return (
                (rx - ROW_GATE_X_PAD) <= cx <= (rx + rw + ROW_GATE_X_PAD)
                and (ry - ROW_GATE_Y_PAD) <= cy <= (ry + rh + ROW_GATE_Y_PAD)
            )

        # Build a map blob_id -> transformed quad and aabb
        blob_geom: dict[int, dict[str, Any]] = {}
        for b in v1_blobs:
            q2 = transform_img_quad(v1_load, v2_frame, b.img_quad)
            if q2 is None:
                continue
            aabb = quad_axis_aligned(q2)
            blob_geom[b.blob_id] = {
                "img_quad": q2,
                "warped_bbox": b.warped_bbox,
                "source_img_quad": b.img_quad,
                "aabb": aabb,
            }

        # Merge v1 composite units with transformed geometry. Drop only units
        # that cannot be placed on the v2 canvas; mark attachment decisions come
        # from the v1 composite witness, not from v2 geometry.
        tokens_out: list[dict[str, Any]] = []
        for tok in v1_tokens_by_line[v1_idx]:
            if tok.get("edge_fragment"):
                excluded_token_total += 1
                continue
            bid = int(tok["blob_id"])
            geom = blob_geom.get(bid)
            if not geom:
                # No geometry: skip (cannot place on canvas)
                excluded_token_total += 1
                continue
            aabb = geom["aabb"]
            # Inside the v2 text_body image?
            img_w, img_h = v2_img_size
            cx = (aabb[0] + aabb[2]) / 2.0
            cy = (aabb[1] + aabb[3]) / 2.0
            if not (0 <= cx <= img_w and 0 <= cy <= img_h):
                excluded_token_total += 1
                continue
            # Inside the v2 row bbox? v2 line geometry is authoritative.
            if not _inside_v2_row(aabb):
                excluded_token_total += 1
                continue
            display_label, display_source, raw_label, overline_mark_id = resolve_review_sheet_label(
                tok,
                review_decisions,
            )
            t = {
                "blob_id": bid,
                "cluster": str(tok.get("cluster") or "unclustered"),
                # Ground truth for the webapp initial state: this is exactly the
                # text resolved by build_page_review_sheet.py.
                "label": display_label,
                "overline_mark_id": overline_mark_id,
                "review_sheet_source": display_source,
                "review_sheet_raw_label": raw_label,
                # Preserve v1 evidence for inspection, but do not expose it as
                # active override fields that can re-overwrite the sheet label.
                "v1_provenance": {
                    "label": tok.get("label"),
                    "final_label": tok.get("final_label"),
                    "final_label_source": tok.get("final_label_source"),
                    "manual_override": tok.get("manual_override"),
                    "manual_warning": tok.get("manual_warning"),
                    "geometric_override": tok.get("geometric_override"),
                    "editorial_override": tok.get("editorial_override"),
                    "subcluster_override": tok.get("subcluster_override"),
                    "attached_marks": tok.get("attached_marks") or [],
                    "geometry_mark_kinds": tok.get("geometry_mark_kinds") or [],
                    "llm_alignment": tok.get("llm_alignment"),
                    "split_metadata": tok.get("split_metadata"),
                },
                "manual_override": None,
                "manual_warning": tok.get("manual_warning"),
                "geometric_override": None,
                "editorial_override": None,
                "subcluster_override": None,
                "candidates": tok.get("candidates") or [],
                "review": bool(tok.get("review")),
                "geometry": {
                    "img_quad": geom["img_quad"],
                    "aabb": geom["aabb"],
                    "warped_bbox": geom["warped_bbox"],
                },
            }
            tokens_out.append(t)
        # Order tokens left-to-right by aabb x-center (manuscript Coptic reads l→r).
        tokens_out.sort(key=lambda t: (t["geometry"]["aabb"][0] + t["geometry"]["aabb"][2]) / 2.0)
        out_lines.append(
            {
                "line_index": v2_row.line_index,
                "v1_line_index": v1_idx,
                "baseline_y": v2_row.baseline_y,
                "x_span": list(v2_row.x_span),
                "tokens": tokens_out,
            }
        )

    text_body_rel = (
        (INGEST_TEXT_BODY_DIR.relative_to(WEBAPP_DIR)).as_posix() + f"/p{page}_text_body.jpg"
    )
    return {
        "page": page,
        "status": "ok",
        "image": text_body_rel,
        "image_size": list(v2_img_size),
        "v1_image_size": list(v1_load.image_size),
        "v1_body_frame": {
            "source": v1_load.body_frame.source,
            "bbox": [v1_load.body_frame.x0, v1_load.body_frame.y0, v1_load.body_frame.x1, v1_load.body_frame.y1],
        },
        "v2_frame": {
            "source_size": list(v2_frame.source_size),
            "crop_origin": list(v2_frame.crop_origin),
            "text_origin": list(v2_frame.text_origin),
        },
        "rows_v1": n_v1,
        "rows_v2": n_v2,
        "rows_aligned": len(out_lines),
        "tokens_excluded": excluded_token_total,
        "lines": out_lines,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", action="append", default=None, help="Process only these pages (e.g. 100). Repeatable.")
    ap.add_argument("--limit", type=int, default=None, help="Process at most N pages.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.dry_run:
        INITIAL_DIR.mkdir(parents=True, exist_ok=True)
        INGEST_TEXT_BODY_DIR.mkdir(parents=True, exist_ok=True)
        INGEST_BODY_GEOM_DIR.mkdir(parents=True, exist_ok=True)
        INGEST_REVIEW_SHEET_DIR.mkdir(parents=True, exist_ok=True)

    # Page set: every page that has v2 geometry. v2 is leading.
    page_set: list[str] = []
    for p in sorted(V2_BODY_GEOM_DIR.glob("p*_geometry.json")):
        stem = p.stem  # e.g. p100_geometry
        if stem.endswith("_cont_geometry"):
            continue
        if not stem.startswith("p") or not stem.endswith("_geometry"):
            continue
        page = stem[1:-len("_geometry")]
        if not page.isdigit():
            continue
        page_set.append(page)

    if args.only:
        want = {p.zfill(3) for p in args.only}
        page_set = [p for p in page_set if p in want]
    if args.limit:
        page_set = page_set[: args.limit]

    print(f"[transpose] loading v1 line_sequences …", file=sys.stderr)
    sequences_by_page = load_jsonl_by_page(V1_LINE_SEQUENCES)
    print(f"[transpose] {len(sequences_by_page)} v1 pages with sequences", file=sys.stderr)
    review_decisions = REVIEW_SHEET.load_review_decisions(V1_CONTEXT_DIR / "review_cluster_context.json")
    print(f"[transpose] loaded {len(review_decisions)} review-sheet cluster decisions", file=sys.stderr)

    summary_pages: list[dict[str, Any]] = []
    n_ok = 0
    for page in page_set:
        result = transpose_page(page, sequences_by_page, review_decisions)
        if not result:
            continue
        if result.get("status") == "ok":
            copied_assets = copy_page_assets(page, args.dry_run)
            out_path = INITIAL_DIR / f"p{page}.json"
            if not args.dry_run:
                out_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            n_ok += 1
            summary_pages.append(
                {
                    "page": page,
                    "status": "ok",
                    "rows_v1": result["rows_v1"],
                    "rows_v2": result["rows_v2"],
                    "rows_aligned": result["rows_aligned"],
                    "tokens_excluded": result["tokens_excluded"],
                    "image_size": result["image_size"],
                    "assets": copied_assets,
                }
            )
            print(
                f"  p{page}: aligned {result['rows_aligned']}/{result['rows_v2']} v2 rows "
                f"(v1 has {result['rows_v1']}); excluded {result['tokens_excluded']} tokens",
                file=sys.stderr,
            )
        else:
            summary_pages.append({"page": page, "status": result["status"]})
            print(f"  p{page}: {result['status']}", file=sys.stderr)

    summary = {
        "total_pages": len(page_set),
        "ok_pages": n_ok,
        "output_root": str(OUT_ROOT.relative_to(REPO)),
        "label_ground_truth": str(REVIEW_SHEET_SCRIPT.relative_to(REPO)),
        "label_source": str(V1_LINE_SEQUENCES.relative_to(REPO)),
        "geometry_source": str(V2_BODY_GEOM_DIR.relative_to(REPO)),
        "text_body_source": str(V2_TEXT_BODY_DIR.relative_to(REPO)),
        "pages": summary_pages,
    }
    if not args.dry_run:
        SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[transpose] done: {n_ok}/{len(page_set)} pages ok", file=sys.stderr)


if __name__ == "__main__":
    main()
