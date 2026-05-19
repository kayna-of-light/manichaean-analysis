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
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# German editorial marker patterns (from detect_editorial_markers.py)
_GERMAN_EDITORIAL_RE = re.compile(
    r"\b(?:leer|abgerieben|verwischt|zerst[öo]rt|unleserlich|undeutlich|"
    r"unlesbar|Spuren|nicht\s+zu\s+lesen|nicht\s+gelesen|nicht\s+lesbar|"
    r"v[öo]llig|\xdcberschrift)\b",
    re.IGNORECASE,
)
# Coptic Unicode block (U+2C80–U+2CFF)
_COPTIC_RE = re.compile(r'[\u2C80-\u2CFF]')
# Content that's NOT structural (dots, brackets, pipes, spaces)
_SUBSTANTIVE_CONTENT_RE = re.compile(r'[^\s.|,\[\]\(\){}]')


def _is_pure_editorial_line(llm_text: str) -> bool:
    """True if llm_text is purely German editorial (markers + dots, no Coptic).

    Also returns True for blank lines where the LLM found no readable content
    (just dots/brackets/pipes) — these blobs shouldn't display as Coptic.
    """
    if not llm_text:
        return False
    # If the line contains Coptic characters, it's a mixed/Coptic line
    if _COPTIC_RE.search(llm_text):
        return False
    # If it has German editorial markers → pure editorial
    if _GERMAN_EDITORIAL_RE.search(llm_text):
        return True
    # If there's no substantive content at all (just dots, brackets, pipes, spaces)
    # → blank editorial line
    if not _SUBSTANTIVE_CONTENT_RE.search(llm_text):
        return True
    return False


def _editorial_marker_chars(text: str | None) -> list[str]:
    if not text:
        return []
    return re.findall(r"[A-Za-zÄÖÜäöüß]", str(text))


def _has_exact_editorial_fingerprint(editorial_override: dict[str, Any]) -> bool:
    """True only when one marker character maps to one blob cluster.

    Editorial overrides must be fingerprints, not line-level text spread across
    whatever blobs happened to be unclaimed. Spaces in the German marker do not
    count as characters.
    """
    marker_chars = _editorial_marker_chars(editorial_override.get("marker_text") or editorial_override.get("marker_type"))
    blob_ids = editorial_override.get("blob_ids") or []
    display_chars = editorial_override.get("display_chars") or []
    if not marker_chars or len(blob_ids) != len(marker_chars):
        return False
    if display_chars and display_chars != marker_chars:
        return False
    return True

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


def find_crop_origin_by_template_match(
    page: str,
    image_size: tuple[int, int],
    blobs_data: list[dict[str, Any]],
    hint_x: int = 400,
    hint_y: int = 250,
) -> tuple[float, float] | None:
    """Find (x0, y0) where the v1 image frame sits in the full page using ink matching.

    The v1 img_quad coordinates are in a frame that is a 1:1 crop of the full page.
    This function finds the crop origin by matching blob center positions against
    ink pixels in the full-page binarized image.
    """
    img_path = V2_DESKEW.IMAGES_DIR / f"keph_p{page}.jpg"
    if not img_path.exists():
        return None

    # Collect blob centers from raw split data
    centers: list[tuple[float, float]] = []
    for ln in blobs_data:
        for b in ln.get("blobs", []):
            quad = b.get("img_quad")
            if quad and len(quad) == 4 and all(len(p) == 2 for p in quad):
                cx = sum(p[0] for p in quad) / 4.0
                cy = sum(p[1] for p in quad) / 4.0
                centers.append((cx, cy))

    if len(centers) < 20:
        return None

    # Subsample for speed (use every 5th center)
    sampled = centers[::5]

    # Load and binarize full page
    full = V2_DESKEW.cv2.imread(str(img_path), V2_DESKEW.cv2.IMREAD_GRAYSCALE)
    if full is None:
        return None
    full_h, full_w = full.shape
    _, full_bin = V2_DESKEW.cv2.threshold(full, 0, 255, V2_DESKEW.cv2.THRESH_BINARY_INV | V2_DESKEW.cv2.THRESH_OTSU)

    img_w, img_h = image_size
    max_x0 = full_w - img_w
    max_y0 = full_h - img_h

    # Coarse search: step=8, range ±120 around hint
    best_score = -1
    best_x0, best_y0 = hint_x, hint_y
    for dy in range(-120, 121, 8):
        for dx in range(-120, 121, 8):
            x0 = hint_x + dx
            y0 = hint_y + dy
            if x0 < 0 or y0 < 0 or x0 > max_x0 or y0 > max_y0:
                continue
            hits = 0
            for cx, cy in sampled:
                px = int(round(x0 + cx))
                py = int(round(y0 + cy))
                if 0 <= px < full_w and 0 <= py < full_h and full_bin[py, px] > 0:
                    hits += 1
            if hits > best_score:
                best_score = hits
                best_x0 = x0
                best_y0 = y0

    # Fine search: step=1, range ±10 around coarse best
    coarse_x, coarse_y = best_x0, best_y0
    for dy in range(-10, 11):
        for dx in range(-10, 11):
            x0 = coarse_x + dx
            y0 = coarse_y + dy
            if x0 < 0 or y0 < 0 or x0 > max_x0 or y0 > max_y0:
                continue
            hits = 0
            for cx, cy in sampled:
                px = int(round(x0 + cx))
                py = int(round(y0 + cy))
                if 0 <= px < full_w and 0 <= py < full_h and full_bin[py, px] > 0:
                    hits += 1
            if hits > best_score:
                best_score = hits
                best_x0 = x0
                best_y0 = y0

    accuracy = best_score / len(sampled) if sampled else 0
    if accuracy < 0.3:
        return None  # Not confident enough
    return (float(best_x0), float(best_y0))


def load_v1_body_frame(page: str, image_size: tuple[int, int], blobs_data: list[dict[str, Any]] | None = None) -> BodyFrame | None:
    """Load or compute the body frame origin for the v1 image coordinate system.

    The v1 img_quad coordinates are in a frame that is a 1:1 crop of the full page.
    We need the (x0, y0) origin of that crop. Strategy:
    1. Check body_bbox files for an exact-size match (score=0) — use directly
    2. Otherwise, template-match blob centers against full-page ink to find origin
    3. Fall back to best-available bbox with a warning
    """
    img_w, img_h = image_size

    # Step 1: look for an exact-match body_bbox (size == image_size)
    for root in V1_BODY_FRAME_DIRS:
        bbox_path = root / f"keph_p{page}_body_bbox.json"
        if not bbox_path.exists():
            continue
        data = json.loads(bbox_path.read_text(encoding="utf-8"))
        bbox = data.get("bbox") or {}
        if not all(key in bbox for key in ("x0", "y0", "x1", "y1")):
            continue
        bbox_size = _bbox_frame_size(bbox)
        if bbox_size == image_size:
            # Exact match: this bbox describes the correct crop origin
            return BodyFrame(
                x0=float(bbox["x0"]),
                y0=float(bbox["y0"]),
                x1=float(bbox["x0"]) + float(img_w),
                y1=float(bbox["y0"]) + float(img_h),
                image_size=image_size,
                source=relative(bbox_path),
            )

    # Step 2: template-match to find correct origin
    if blobs_data is not None:
        # Get a hint from any available bbox
        hint_x, hint_y = 400, 250
        for root in V1_BODY_FRAME_DIRS:
            bbox_path = root / f"keph_p{page}_body_bbox.json"
            if bbox_path.exists():
                data = json.loads(bbox_path.read_text(encoding="utf-8"))
                bbox = data.get("bbox") or {}
                if "x0" in bbox and "y0" in bbox:
                    hint_x = int(float(bbox["x0"]))
                    hint_y = int(float(bbox["y0"]))
                    break

        origin = find_crop_origin_by_template_match(page, image_size, blobs_data, hint_x, hint_y)
        if origin is not None:
            x0, y0 = origin
            return BodyFrame(
                x0=x0,
                y0=y0,
                x1=x0 + float(img_w),
                y1=y0 + float(img_h),
                image_size=image_size,
                source=f"template_match (page {page})",
            )

    # Step 3: fallback — use nearest bbox but force scale=1
    for root in V1_BODY_FRAME_DIRS:
        bbox_path = root / f"keph_p{page}_body_bbox.json"
        if not bbox_path.exists():
            continue
        data = json.loads(bbox_path.read_text(encoding="utf-8"))
        bbox = data.get("bbox") or {}
        if "x0" in bbox and "y0" in bbox:
            return BodyFrame(
                x0=float(bbox["x0"]),
                y0=float(bbox["y0"]),
                x1=float(bbox["x0"]) + float(img_w),
                y1=float(bbox["y0"]) + float(img_h),
                image_size=image_size,
                source=f"{relative(bbox_path)} (fallback, scale=1 forced)",
            )

    return None


def load_v1_blobs(page: str) -> V1PageGeometry | None:
    """Return v1 character geometry in corrected body-crop image coordinates."""
    path = V1_LINE_SPLIT_DIR / f"keph_p{page}_lines_base_split.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    img_size = tuple(data.get("image_size") or (0, 0))
    body_frame = load_v1_body_frame(page, img_size, blobs_data=data.get("lines"))  # type: ignore[arg-type]
    # body_frame is no longer required for the affine transform, but we store
    # it for diagnostics if available.
    if body_frame is None:
        body_frame = BodyFrame(x0=0, y0=0, x1=float(img_size[0]), y1=float(img_size[1]), image_size=img_size, source="synthetic_identity")  # type: ignore[arg-type]
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


def _v1_ink_width(v1_line: V1Line) -> float:
    """Compute ink width from warped_bbox (known coordinate system)."""
    xs: list[float] = []
    for b in v1_line.blobs:
        xs.extend([float(b.warped_bbox[0]), float(b.warped_bbox[2])])
    return max(xs) - min(xs) if xs else 0.0


def _v1_img_y_center(v1_line: V1Line) -> float | None:
    """Compute y-center from img_quad (for ordering/matching only)."""
    ys: list[float] = []
    for b in v1_line.blobs:
        for pt in b.img_quad:
            ys.append(pt[1])
    return (min(ys) + max(ys)) / 2.0 if ys else None


def match_rows_by_width(
    v1_lines_by_line: dict[int, V1Line],
    v1_indices: list[int],
    v2_rows: list["V2Row"],
) -> list[tuple[int, "V2Row"]]:
    """Match v1 lines to v2 rows using ink width + y-proximity.

    Algorithm:
    1. Sort v1 lines by y-position (top-to-bottom, same as v2)
    2. Pre-filter obvious noise: v1 lines far narrower than the page norm
       (mirrors v2's min_row_x_span filter)
    3. Estimate per-page width scale from median full-width lines
    4. Greedy forward matching using combined width + y-ordinal score

    This handles pages where v1 has extra lines (fragments, headers, footers)
    because noise is pre-filtered and width incompatibility skips the rest.
    """
    import statistics

    n_v2 = len(v2_rows)
    if not v1_indices or n_v2 == 0:
        return []

    # Build v1 data sorted by y-position
    v1_data: list[tuple[int, float, float]] = []  # (line_idx, y_center, ink_width)
    for idx in v1_indices:
        v1_line = v1_lines_by_line[idx]
        y = _v1_img_y_center(v1_line)
        if y is None:
            continue
        w = _v1_ink_width(v1_line)
        v1_data.append((idx, y, w))
    v1_data.sort(key=lambda x: x[1])

    if not v1_data:
        return []

    # --- PRE-FILTER: remove obvious noise lines ---
    # Mirrors v2's min_row_x_span (70px) and min_row_components (3).
    # Also remove lines whose width is < 15% of the page's median full-width,
    # as these are scattered marks that v2 never detects as rows.
    v1_ws_all = [w for _, _, w in v1_data]
    v1_max_w = max(v1_ws_all) if v1_ws_all else 1.0
    v1_full_ws = [w for w in v1_ws_all if w > v1_max_w * 0.5]
    median_full_w = statistics.median(v1_full_ws) if v1_full_ws else v1_max_w

    # Threshold: at least 15% of median full-width, and at least 70px (v2's absolute min)
    noise_threshold = max(median_full_w * 0.15, 70.0)

    # Also compute the minimum v2 width to avoid over-filtering
    v2_widths = [r.x_span[1] - r.x_span[0] for r in v2_rows]
    min_v2_w = min(v2_widths) if v2_widths else 0.0

    # Keep lines that are either above the noise threshold, or at least as wide
    # as the narrowest v2 row (so we don't filter out real short rows)
    v1_filtered: list[tuple[int, float, float]] = []
    for idx, y, w in v1_data:
        v1_line = v1_lines_by_line[idx]
        n_blobs = len(v1_line.blobs)
        # Keep if: width above noise threshold, OR width compatible with a v2 row,
        # OR has many blobs (real text line, just narrow)
        if w >= noise_threshold or w >= min_v2_w * 0.5 or n_blobs >= 10:
            v1_filtered.append((idx, y, w))

    v1_data = v1_filtered
    if not v1_data:
        return []

    # If v1 count <= v2 count after filtering, ordinal match
    if len(v1_data) <= n_v2:
        return [(v1_data[k][0], v2_rows[k]) for k in range(min(len(v1_data), n_v2))]

    # Estimate width scale: median of full-width lines (>50% of max)
    v1_ws = [w for _, _, w in v1_data]
    v1_max = max(v1_ws) if v1_ws else 1.0
    v2_max = max(v2_widths) if v2_widths else 1.0
    v1_full = [w for w in v1_ws if w > v1_max * 0.5]
    v2_full = [w for w in v2_widths if w > v2_max * 0.5]
    if v1_full and v2_full:
        scale = statistics.median(v2_full) / statistics.median(v1_full)
    else:
        scale = 1.0

    # Greedy forward matching using width similarity + y-ordinal proximity
    v1_cursor = 0
    aligned: list[tuple[int, "V2Row"]] = []

    for j in range(n_v2):
        v2_w = v2_widths[j]
        # Expected v1 ordinal position for this v2 row
        expected_v1_frac = j / max(n_v2 - 1, 1)

        # Look-ahead window
        remaining_v2 = n_v2 - j
        remaining_v1 = len(v1_data) - v1_cursor
        max_look = v1_cursor + (remaining_v1 - remaining_v2) + 1

        best_i = -1
        best_score = float("inf")

        for i in range(v1_cursor, min(max_look, len(v1_data))):
            v1_w_scaled = v1_data[i][2] * scale
            # Width difference (0 = perfect match, 1 = completely different)
            w_max = max(v1_w_scaled, v2_w, 1.0)
            w_diff = abs(v1_w_scaled - v2_w) / w_max

            # Y-ordinal proximity (how far is this v1 line from its expected position)
            v1_frac = i / max(len(v1_data) - 1, 1)
            y_diff = abs(v1_frac - expected_v1_frac)

            # Combined score: width is primary (weight 1.0), y-ordinal is tiebreaker (weight 0.3)
            score = w_diff + 0.3 * y_diff

            if score < best_score:
                best_score = score
                best_i = i

        if best_i >= 0 and best_score < 0.7:
            aligned.append((v1_data[best_i][0], v2_rows[j]))
            v1_cursor = best_i + 1
        else:
            # No good match found - skip this v2 row
            pass

    return aligned






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
    if v1_load is None:
        return {"page": page, "status": "missing_v1_geometry"}
    if v2_load is None:
        return {"page": page, "status": "missing_v2_geometry"}
    v1_lines_by_line = v1_load.lines_by_line
    v2_rows, v2_img_size = v2_load

    # Build the full geometric transform: v1 bodycrop → full page → v2 text_body.
    # This gives pixel-accurate placement without heuristic matching.
    v2_frame = build_v2_frame_transform(page)
    if v2_frame is None:
        return {"page": page, "status": "missing_v2_frame_transform"}

    sequence_rows = sequences_by_page.get(page) or []
    v1_tokens_by_line: dict[int, list[dict[str, Any]]] = {}
    llm_text_by_line: dict[int, str] = {}
    for rec in sequence_rows:
        line_idx = int(rec["line_index"])
        v1_tokens_by_line[line_idx] = rec.get("units") or rec.get("tokens", [])
        llm_text_by_line[line_idx] = str(rec.get("llm_text") or "")

    v1_indices = sorted(
        idx for idx in v1_lines_by_line if idx in v1_tokens_by_line and v1_lines_by_line[idx].blobs
    )
    n_v1 = len(v1_indices)
    n_v2 = len(v2_rows)

    # Phase 1: Transform ALL v1 blobs to v2 text_body coordinates.
    # blob_key = (v1_line_idx, blob_id) → transformed geometry
    all_blob_geom: dict[tuple[int, int], dict[str, Any]] = {}
    for v1_idx in v1_indices:
        v1_line = v1_lines_by_line[v1_idx]
        for b in v1_line.blobs:
            transformed_quad = transform_img_quad(v1_load, v2_frame, b.img_quad)
            if transformed_quad is None:
                continue
            xs = [p[0] for p in transformed_quad]
            ys = [p[1] for p in transformed_quad]
            aabb = [round(min(xs), 3), round(min(ys), 3), round(max(xs), 3), round(max(ys), 3)]
            # Round quad corners
            q2 = [[round(p[0], 3), round(p[1], 3)] for p in transformed_quad]
            all_blob_geom[(v1_idx, b.blob_id)] = {
                "img_quad": q2,
                "aabb": aabb,
                "warped_bbox": b.warped_bbox,
            }

    # Phase 2: Assign each transformed blob to the nearest v2 row by y-center.
    v2_baselines = [r.baseline_y for r in v2_rows]
    img_w, img_h = v2_img_size

    # blob_key → v2_row_index
    blob_row_assignment: dict[tuple[int, int], int] = {}
    for key, geom in all_blob_geom.items():
        aabb = geom["aabb"]
        cy = (aabb[1] + aabb[3]) / 2.0
        cx = (aabb[0] + aabb[2]) / 2.0
        # Skip blobs outside the text_body canvas
        if not (0 <= cx <= img_w and 0 <= cy <= img_h):
            continue
        # Find nearest v2 row by y-distance to baseline
        best_row_idx = 0
        best_dist = abs(cy - v2_baselines[0])
        for ri in range(1, n_v2):
            d = abs(cy - v2_baselines[ri])
            if d < best_dist:
                best_dist = d
                best_row_idx = ri
            elif d > best_dist:
                # baselines are sorted, so once distance increases, stop
                break
        blob_row_assignment[key] = best_row_idx

    # Phase 3: Build output lines grouped by v2 row.
    # For each v2 row, collect all blobs assigned to it and merge with token data.
    out_lines: list[dict[str, Any]] = []
    excluded_token_total = 0

    # Invert assignment: v2_row_index → list of (v1_line_idx, blob_id)
    row_blobs: dict[int, list[tuple[int, int]]] = {i: [] for i in range(n_v2)}
    for key, row_idx in blob_row_assignment.items():
        row_blobs[row_idx].append(key)

    for row_idx in range(n_v2):
        v2_row = v2_rows[row_idx]
        assigned_keys = row_blobs[row_idx]
        if not assigned_keys:
            continue

        # Determine which v1 lines contribute to this row (for v1_line_index field)
        v1_lines_in_row = sorted(set(k[0] for k in assigned_keys))
        # Use the v1 line that contributes the most blobs
        v1_line_counts = {}
        for k in assigned_keys:
            v1_line_counts[k[0]] = v1_line_counts.get(k[0], 0) + 1
        primary_v1_line = max(v1_line_counts, key=v1_line_counts.get)

        # Build blob_id set for quick lookup
        assigned_blob_ids: dict[int, set[int]] = {}
        for v1_idx, bid in assigned_keys:
            assigned_blob_ids.setdefault(v1_idx, set()).add(bid)

        # Merge with token data from the v1 composite witness
        tokens_out: list[dict[str, Any]] = []
        for v1_idx in v1_lines_in_row:
            if v1_idx not in v1_tokens_by_line:
                continue
            blob_ids_for_line = assigned_blob_ids.get(v1_idx, set())
            for tok in v1_tokens_by_line[v1_idx]:
                if tok.get("edge_fragment"):
                    excluded_token_total += 1
                    continue
                bid = int(tok["blob_id"])
                if bid not in blob_ids_for_line:
                    continue
                key = (v1_idx, bid)
                geom = all_blob_geom.get(key)
                if not geom:
                    excluded_token_total += 1
                    continue

                # The upstream editorial override file is no longer a source of
                # truth for Manual Reviewer ingest. The reviewer baseline must
                # be the pre-overlay token stream; clean editorial fingerprints
                # are built separately from that stream.
                tok = {**tok, "editorial_override": None}

                display_label, display_source, raw_label, overline_mark_id = resolve_review_sheet_label(
                    tok,
                    review_decisions,
                )
                t = {
                    "blob_id": bid,
                    "v1_line_index": v1_idx,
                    "cluster": str(tok.get("cluster") or "unclustered"),
                    "label": display_label,
                    "overline_mark_id": overline_mark_id,
                    "review_sheet_source": display_source,
                    "review_sheet_raw_label": raw_label,
                    "v1_provenance": {
                        "label": tok.get("label"),
                        "final_label": tok.get("final_label"),
                        "final_label_source": tok.get("final_label_source"),
                        "manual_override": tok.get("manual_override"),
                        "manual_warning": tok.get("manual_warning"),
                        "geometric_override": tok.get("geometric_override"),
                        "editorial_override": None,
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

        if not tokens_out:
            continue

        # Order tokens: group by v1 line first, then left-to-right within each line.
        # This prevents editorial text from one v1 line appearing between Coptic
        # from another v1 line when multiple v1 lines merge into a single v2 row.
        tokens_out.sort(key=lambda t: (t["v1_line_index"], (t["geometry"]["aabb"][0] + t["geometry"]["aabb"][2]) / 2.0))

        # Post-process: suppress editorial false positives.
        # Short editorial markers (like "leer", 4 chars) can false-match on Coptic
        # blobs whose shapes happen to match. Real markers appear at the EDGE of
        # their line's content (end or beginning), not embedded between Coptic.
        # Rule: if a short editorial run (< 8 consecutive tokens) is BETWEEN Coptic
        # tokens on the same v1 line, it's a false positive — revert to the
        # non-editorial label from v1_provenance.
        for v1_idx in v1_lines_in_row:
            line_tokens = [t for t in tokens_out if t["v1_line_index"] == v1_idx]
            n = len(line_tokens)
            if n == 0:
                continue
            # Identify runs of consecutive editorial tokens
            i = 0
            while i < n:
                if "editorial" not in line_tokens[i].get("review_sheet_source", ""):
                    i += 1
                    continue
                # Found start of editorial run
                j = i
                while j < n and "editorial" in line_tokens[j].get("review_sheet_source", ""):
                    j += 1
                run_len = j - i
                # Long runs (>= 8 tokens) are trusted — they can't false-match
                if run_len >= 8:
                    i = j
                    continue
                # Check if this short run is BETWEEN Coptic tokens
                has_coptic_before = any(
                    "editorial" not in line_tokens[k].get("review_sheet_source", "")
                    and _COPTIC_RE.search(line_tokens[k].get("label", ""))
                    for k in range(0, i)
                )
                has_coptic_after = any(
                    "editorial" not in line_tokens[k].get("review_sheet_source", "")
                    and _COPTIC_RE.search(line_tokens[k].get("label", ""))
                    for k in range(j, n)
                )
                if has_coptic_before and has_coptic_after:
                    # False positive: revert these tokens to their non-editorial label
                    for k in range(i, j):
                        prov = line_tokens[k].get("v1_provenance", {}) or {}
                        fallback = prov.get("final_label") or prov.get("label") or "?"
                        line_tokens[k]["label"] = str(fallback)
                        line_tokens[k]["review_sheet_source"] = "final:assigned"
                i = j

        out_lines.append(
            {
                "line_index": v2_row.line_index,
                "v1_line_index": primary_v1_line,
                "baseline_y": v2_row.baseline_y,
                "x_span": list(v2_row.x_span),
                "tokens": tokens_out,
            }
        )

    # Count tokens that had no geometry or were outside canvas
    for v1_idx in v1_indices:
        if v1_idx not in v1_tokens_by_line:
            continue
        for tok in v1_tokens_by_line[v1_idx]:
            if tok.get("edge_fragment"):
                continue
            bid = int(tok["blob_id"])
            key = (v1_idx, bid)
            if key not in all_blob_geom and key not in blob_row_assignment:
                excluded_token_total += 1

    text_body_rel = (
        (INGEST_TEXT_BODY_DIR.relative_to(WEBAPP_DIR)).as_posix() + f"/p{page}_text_body.jpg"
    )
    return {
        "page": page,
        "status": "ok",
        "image": text_body_rel,
        "image_size": list(v2_img_size),
        "v1_image_size": list(v1_load.image_size),
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
