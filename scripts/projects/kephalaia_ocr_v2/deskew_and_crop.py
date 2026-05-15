"""kephalaia_ocr_v2: deskew + crop pipeline.

Reads kraken baseline JSONs from output/projects/kephalaia_ocr/pages/
and source images from output/projects/kephalaia_v2/coptic/images/,
applies:

  1. Scanner-artifact mask (edge-band dark CCs).
  2. Global rotation from leftmost endpoints of long body baselines
     (with short-baseline-right fallback).
  3. Localized per-baseline y-dewarp.
  4. Binarize (Otsu) and apply left/right/top/bottom clips on the
     binary mask only.
  5. Find ink bbox via row/col projections, add 50 px breathing
     padding, crop the dewarped (unmasked) image.

Writes ONLY the final crop to:
  output/projects/kephalaia_ocr_v2/pages_cropped/keph_pNNN.jpg

No preview, no per-page JSON, no summary.

Usage:
  python scripts/projects/kephalaia_ocr_v2/deskew_and_crop.py            # all pages
  python scripts/projects/kephalaia_ocr_v2/deskew_and_crop.py 010 015    # specific pages
  python scripts/projects/kephalaia_ocr_v2/deskew_and_crop.py all        # explicit all
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from tqdm import tqdm

try:
    from split_line_numbers_body import detect_line_number_ruler, threshold_ink
except ImportError:
    from scripts.projects.kephalaia_ocr_v2.split_line_numbers_body import detect_line_number_ruler, threshold_ink


REPO = Path(__file__).resolve().parents[3]
IMAGES_DIR = REPO / "output" / "projects" / "kephalaia_v2" / "coptic" / "images"
KRAKEN_DIR = REPO / "output" / "projects" / "kephalaia_ocr" / "pages"
OUT_DIR = REPO / "output" / "projects" / "kephalaia_ocr_v2" / "pages_cropped"


MIN_BASELINE_SPAN = 500
FALLBACK_DEWARP_MIN_SPAN = 200
SHORT_BASELINE_MAX_SPAN = 200
RIGHT_X_MIN_SPAN = 10
PHI_FIT_RESIDUAL_MAX_PX = 8.0
PHI_FIT_MIN_POINTS = 6
LEFT_COLUMN_MARGIN_PX = 50
RIGHT_COLUMN_MARGIN_PX = 120
TOP_BOTTOM_MARGIN_PX = 80
BBOX_PAD_PX = 50
RIGHT_EDGE_EXTRA_OFFSET_PX_BY_PAGE = {
    "127": 60,
    "185": 40,
    "196": 50,
}
JPEG_QUALITY = 95
EDGE_BAND_PX = 50  # right/top/bottom scanner-artifact edge band
EDGE_BAND_PX_LEFT = 150  # binding/spine side has worst scanner stains;
                         # phantom kraken detections appear up to ~155 px
                         # from the left edge on pages like p277


def _baseline_at_edge(bl: list[list[float]], W: int, H: int) -> bool:
    """Return True if any baseline endpoint lies within an image edge
    band (wider on the left due to binding stains). These are kraken
    phantom detections from scanner artifacts that
    mask_scanner_artifacts already wiped from the image; we exclude
    them here so they don't pull clip anchors."""
    for p in bl:
        x = float(p[0]); y = float(p[1])
        if (x <= EDGE_BAND_PX_LEFT or x >= W - EDGE_BAND_PX
                or y <= EDGE_BAND_PX or y >= H - EDGE_BAND_PX):
            return True
    return False


# ---------------------------------------------------------------------------
# rotation estimation
# ---------------------------------------------------------------------------

def _fit_vertical_line(
    pts: list[tuple[float, float]],
) -> tuple[float, dict]:
    info: dict = {"n_points": len(pts)}
    if len(pts) < 4:
        info["phi_deg"] = 0.0
        return 0.0, info
    arr = np.asarray(pts, dtype=np.float64)
    x = arr[:, 0]
    y = arr[:, 1]
    med = float(np.median(x))
    mad = float(np.median(np.abs(x - med))) or 1.0
    keep = np.abs(x - med) <= 3.5 * 1.4826 * mad
    info["n_after_mad"] = int(keep.sum())
    if keep.sum() < 4:
        info["phi_deg"] = 0.0
        return 0.0, info
    a, c = np.polyfit(y[keep], x[keep], 1)
    phi = float(np.arctan(a))
    x_pred = a * y[keep] + c
    info["phi_deg"] = round(float(np.degrees(phi)), 4)
    info["residual_std_px"] = round(float(np.std(x[keep] - x_pred)), 2)
    return phi, info


def estimate_vertical_correction(
    lines: list[dict], W: int
) -> tuple[float, dict]:
    primary_pts: list[tuple[float, float]] = []
    short_right_pts: list[tuple[float, float]] = []
    for L in lines:
        bl = L.get("baseline") or []
        if len(bl) < 2:
            continue
        xs = [p[0] for p in bl]
        ys = [p[1] for p in bl]
        span = max(xs) - min(xs)
        if span >= MIN_BASELINE_SPAN:
            i = int(np.argmin(xs))
            primary_pts.append((float(xs[i]), float(ys[i])))
        elif span <= SHORT_BASELINE_MAX_SPAN:
            i = int(np.argmax(xs))
            short_right_pts.append((float(xs[i]), float(ys[i])))

    phi_primary, info_primary = _fit_vertical_line(primary_pts)
    primary_ok = (
        info_primary.get("n_after_mad", 0) >= PHI_FIT_MIN_POINTS
        and info_primary.get("residual_std_px", 1e9)
        <= PHI_FIT_RESIDUAL_MAX_PX
    )
    if primary_ok:
        info_primary["used"] = True
        return phi_primary, info_primary

    phi_fallback, info_fallback = _fit_vertical_line(short_right_pts)
    fallback_ok = (
        info_fallback.get("n_after_mad", 0) >= PHI_FIT_MIN_POINTS
        and info_fallback.get("residual_std_px", 1e9)
        <= PHI_FIT_RESIDUAL_MAX_PX
    )
    combined = {"primary": info_primary, "fallback": info_fallback}
    if fallback_ok:
        combined["used"] = "fallback"
        return phi_fallback, combined
    combined["used"] = "none"
    return 0.0, combined


def rotate_image_and_lines(
    img: np.ndarray, lines: list[dict], phi: float
) -> tuple[np.ndarray, list[dict], np.ndarray]:
    H, W = img.shape[:2]
    cx, cy = W / 2.0, H / 2.0
    deg = -float(np.degrees(phi))
    M = cv2.getRotationMatrix2D((cx, cy), deg, 1.0)
    rotated = cv2.warpAffine(
        img, M, (W, H),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )

    def _xform(poly: list[list[float]]) -> list[list[float]]:
        if not poly:
            return poly
        P = np.asarray(poly, dtype=np.float64)
        ones = np.ones((P.shape[0], 1), dtype=np.float64)
        Q = (np.hstack([P, ones]) @ M.T)
        return Q.tolist()

    new_lines: list[dict] = []
    for L in lines:
        NL = dict(L)
        if L.get("baseline"):
            NL["baseline"] = _xform(L["baseline"])
        if L.get("boundary"):
            NL["boundary"] = _xform(L["boundary"])
        new_lines.append(NL)
    return rotated, new_lines, M


# ---------------------------------------------------------------------------
# dewarp
# ---------------------------------------------------------------------------

def collect_baselines(
    lines: list[dict], W: int, min_span: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    ms: list[float] = []
    bs: list[float] = []
    targets: list[float] = []
    for L in lines:
        bl = L.get("baseline") or []
        if len(bl) < 2:
            continue
        xs = np.array([p[0] for p in bl], dtype=float)
        ys = np.array([p[1] for p in bl], dtype=float)
        span = float(xs.max() - xs.min())
        if span < min_span:
            continue
        slope, intercept = np.polyfit(xs, ys, 1)
        if abs(np.arctan(slope)) > 0.1:
            continue
        ms.append(float(slope))
        bs.append(float(intercept))
        targets.append(float(slope) * (W / 2.0) + float(intercept))
    return (
        np.asarray(ms, dtype=np.float64),
        np.asarray(bs, dtype=np.float64),
        np.asarray(targets, dtype=np.float64),
    )


def build_dewarp_maps(
    lines: list[dict], W: int, H: int
) -> tuple[np.ndarray | None, np.ndarray | None, dict]:
    ms, bs, targets = collect_baselines(lines, W, MIN_BASELINE_SPAN)
    min_span_used = MIN_BASELINE_SPAN
    if len(ms) < 3:
        ms, bs, targets = collect_baselines(lines, W, FALLBACK_DEWARP_MIN_SPAN)
        min_span_used = FALLBACK_DEWARP_MIN_SPAN

    info: dict = {
        "n_baselines_used": int(len(ms)),
        "min_span_used": min_span_used,
    }
    if len(ms) < 3:
        return None, None, info
    order = np.argsort(targets)
    ms = ms[order]
    bs = bs[order]
    targets = targets[order]
    K = len(ms)
    x_grid = np.arange(W, dtype=np.float64)
    src = ms[:, None] * x_grid[None, :] + bs[:, None]
    y_out = np.arange(H, dtype=np.float64)
    idx = np.searchsorted(targets, y_out)
    map_y = np.empty((H, W), dtype=np.float32)
    interior_mask = (idx >= 1) & (idx <= K - 1)
    if interior_mask.any():
        iy = y_out[interior_mask]
        ii = idx[interior_mask]
        t_lo = targets[ii - 1]
        t_hi = targets[ii]
        w = ((iy - t_lo) / (t_hi - t_lo)).astype(np.float32)
        src_lo = src[ii - 1, :].astype(np.float32)
        src_hi = src[ii, :].astype(np.float32)
        map_y[interior_mask, :] = (
            src_lo * (1.0 - w[:, None]) + src_hi * w[:, None]
        )
    top_mask = idx == 0
    if top_mask.any():
        ty = y_out[top_mask].astype(np.float32)
        shift0 = (src[0, :] - targets[0]).astype(np.float32)
        map_y[top_mask, :] = ty[:, None] + shift0[None, :]
    bot_mask = idx == K
    if bot_mask.any():
        by = y_out[bot_mask].astype(np.float32)
        shiftN = (src[-1, :] - targets[-1]).astype(np.float32)
        map_y[bot_mask, :] = by[:, None] + shiftN[None, :]
    map_x = np.tile(
        np.arange(W, dtype=np.float32)[None, :], (H, 1)
    )
    return map_x, map_y, info


def apply_dewarp(
    img: np.ndarray, map_x: np.ndarray, map_y: np.ndarray
) -> np.ndarray:
    return cv2.remap(
        img, map_x, map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )


# ---------------------------------------------------------------------------
# clips & bbox
# ---------------------------------------------------------------------------

def mask_scanner_artifacts(
    img: np.ndarray,
    edge_band_px: int = 50,
    min_area: int = 600,
) -> np.ndarray:
    H, W = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, dark = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU
    )
    n_lbl, labels, stats, _ = cv2.connectedComponentsWithStats(dark, 8)
    mask = np.zeros((H, W), dtype=np.uint8)
    for k in range(1, n_lbl):
        x, y, w, h, area = stats[k]
        touches_edge = (
            x <= edge_band_px
            or y <= edge_band_px
            or x + w >= W - edge_band_px
            or y + h >= H - edge_band_px
        )
        if touches_edge and area >= min_area:
            mask[labels == k] = 255
    cleaned = img.copy()
    cleaned[mask > 0] = (255, 255, 255)
    return cleaned


def compute_column_x_rotated(
    rotated_lines: list[dict], W: int, H: int,
) -> float | None:
    """Left crop anchor from exactly two left-side baselines.

    Primary: separated line-number baseline, computed from the right
    edge of short kraken detections. The returned crop anchor is the
    left ink edge of that kept number cluster, so the normal 50 px
    bbox margin is preserved around the numbers.

    Fallback: fused text-line baseline, computed from the left edge of
    long kraken detections when there are not enough separated numbers.
    """
    number_left: list[float] = []
    number_right: list[float] = []
    text_left: list[float] = []
    for L in rotated_lines:
        bl = L.get("baseline") or []
        if len(bl) < 2:
            continue
        if _baseline_at_edge(bl, W, H):
            continue
        xs = [p[0] for p in bl]
        span = max(xs) - min(xs)
        if span <= SHORT_BASELINE_MAX_SPAN:
            number_left.append(float(min(xs)))
            number_right.append(float(max(xs)))
        elif span >= MIN_BASELINE_SPAN:
            text_left.append(float(min(xs)))

    if len(number_right) >= 6:
        right_arr = np.asarray(number_right, dtype=np.float64)
        left_arr = np.asarray(number_left, dtype=np.float64)
        med = float(np.median(right_arr))
        mad = float(np.median(np.abs(right_arr - med))) or 1.0
        keep = np.abs(right_arr - med) <= 3.5 * 1.4826 * mad
        if keep.sum() >= 6:
            return float(left_arr[keep].min())

    if len(text_left) >= 4:
        arr = np.asarray(text_left, dtype=np.float64)
        med = float(np.median(arr))
        mad = float(np.median(np.abs(arr - med))) or 1.0
        keep = np.abs(arr - med) <= 3.5 * 1.4826 * mad
        if keep.sum() >= 4:
            return float(np.median(arr[keep]))

    return None


def compute_right_x_rotated(rotated_lines: list[dict], W: int, H: int) -> float | None:
    rights: list[float] = []
    for L in rotated_lines:
        bl = L.get("baseline") or []
        if len(bl) < 2:
            continue
        if _baseline_at_edge(bl, W, H):
            continue
        xs = [p[0] for p in bl]
        span = float(max(xs) - min(xs))
        if span < RIGHT_X_MIN_SPAN:
            continue
        rights.append(float(max(xs)))
    if not rights:
        return None
    return float(max(rights))


def compute_top_bottom_y_rotated(
    rotated_lines: list[dict], W: int, H: int,
) -> tuple[float | None, float | None]:
    tops: list[float] = []
    bottoms: list[float] = []
    for L in rotated_lines:
        bl = L.get("baseline") or []
        if len(bl) < 2:
            continue
        if _baseline_at_edge(bl, W, H):
            continue
        ys = [p[1] for p in bl]
        tops.append(float(min(ys)))
        bottoms.append(float(max(ys)))
    if len(tops) < 4:
        return None, None

    def _filter(vals: list[float]) -> np.ndarray | None:
        arr = np.asarray(vals, dtype=np.float64)
        med = float(np.median(arr))
        mad = float(np.median(np.abs(arr - med))) or 1.0
        keep = np.abs(arr - med) <= 6.0 * 1.4826 * mad
        if keep.sum() < 4:
            return None
        return arr[keep]

    tk = _filter(tops)
    bk = _filter(bottoms)
    top_y = float(tk.min()) if tk is not None else None
    bot_y = float(bk.max()) if bk is not None else None
    return top_y, bot_y


def find_ink_bbox(ink: np.ndarray) -> tuple[int, int, int, int]:
    H, W = ink.shape[:2]
    col_proj = ink.sum(axis=0)
    row_proj = ink.sum(axis=1)
    col_thr = max(2, int(0.005 * H))
    row_thr = max(2, int(0.005 * W))
    cols = np.flatnonzero(col_proj >= col_thr)
    rows = np.flatnonzero(row_proj >= row_thr)
    if cols.size == 0 or rows.size == 0:
        return 0, 0, W, H
    return int(cols[0]), int(rows[0]), int(cols[-1] + 1), int(rows[-1] + 1)


def refine_left_edge_from_line_number_ruler(crop: np.ndarray) -> tuple[np.ndarray, int]:
    """Trim excess left margin using the detected line-number ruler.

    The Kraken short-baseline fallback can be pulled left by page-number,
    header, or footer detections. The page crop is still broad enough for a
    pixel-level ruler pass, so use that ruler as the final left anchor.
    """
    if crop.size == 0:
        return crop, 0
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    mask = threshold_ink(crop)
    ruler = detect_line_number_ruler(mask, gray, min_run_len=3)
    if not ruler.get("available"):
        return crop, 0
    trim_left = int(ruler["col_left"]) - LEFT_COLUMN_MARGIN_PX
    if trim_left <= 0:
        return crop, 0
    return crop[:, trim_left:], trim_left


# ---------------------------------------------------------------------------
# main pipeline
# ---------------------------------------------------------------------------

def process(page_id: str) -> tuple[int, int, int, int]:
    img_path = IMAGES_DIR / f"keph_p{page_id}.jpg"
    krk_path = KRAKEN_DIR / f"kraken_p{page_id}_lines.json"
    img = cv2.imread(str(img_path))
    if img is None:
        raise SystemExit(f"could not read {img_path}")
    if not krk_path.exists():
        raise SystemExit(f"missing kraken json: {krk_path}")
    lines = json.loads(krk_path.read_text(encoding="utf-8")).get("lines", [])

    H, W = img.shape[:2]

    cleaned = mask_scanner_artifacts(img)
    phi, _ = estimate_vertical_correction(lines, W)
    rotated, rotated_lines, _ = rotate_image_and_lines(cleaned, lines, phi)

    map_x, map_y, dewarp_info = build_dewarp_maps(rotated_lines, W, H)
    if map_x is None:
        # Heavily damaged pages (e.g. p283, p284) have <3 long body
        # baselines and cannot support per-baseline dewarp. Skip the
        # dewarp and continue with just the global rotation; the rest
        # of the pipeline (clips, bbox) still works.
        warped = rotated
    else:
        warped = apply_dewarp(rotated, map_x, map_y)

    # Binarize on the full warped image so Otsu sees full content.
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    _, binimg = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU
    )

    left_clip_used = 0
    column_x = compute_column_x_rotated(rotated_lines, W, H)
    if column_x is not None:
        left_clip_used = int(max(0, round(column_x - LEFT_COLUMN_MARGIN_PX)))
        if left_clip_used > 0:
            binimg[:, :left_clip_used] = 0

    right_clip_used = W
    right_x = compute_right_x_rotated(rotated_lines, W, H)
    if right_x is not None:
        right_clip_used = int(min(W, round(right_x + RIGHT_COLUMN_MARGIN_PX)))
        if right_clip_used < W:
            binimg[:, right_clip_used:] = 0

    top_clip_used = 0
    bot_clip_used = H
    top_y, bot_y = compute_top_bottom_y_rotated(rotated_lines, W, H)
    if top_y is not None:
        top_clip_used = int(max(0, round(top_y - TOP_BOTTOM_MARGIN_PX)))
        if top_clip_used > 0:
            binimg[:top_clip_used, :] = 0
    if bot_y is not None:
        bot_clip_used = int(min(H, round(bot_y + TOP_BOTTOM_MARGIN_PX)))
        if bot_clip_used < H:
            binimg[bot_clip_used:, :] = 0

    ix0, iy0, ix1, iy1 = find_ink_bbox(binimg > 0)
    # Clamp 50px breathing padding to the clip walls (not image edges).
    # The clipped zones are scanner-artifact regions; the padding must
    # not extend into them, or residual stains leak into the crop.
    ix0 = max(left_clip_used, ix0 - BBOX_PAD_PX)
    iy0 = max(top_clip_used, iy0 - BBOX_PAD_PX)
    ix1 = min(right_clip_used, ix1 + BBOX_PAD_PX)
    iy1 = min(bot_clip_used, iy1 + BBOX_PAD_PX)
    ix1 = min(
        W,
        ix1 + RIGHT_EDGE_EXTRA_OFFSET_PX_BY_PAGE.get(page_id, 0),
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    crop = warped[iy0:iy1, ix0:ix1]
    crop, ruler_left_trim = refine_left_edge_from_line_number_ruler(crop)
    cv2.imwrite(
        str(OUT_DIR / f"keph_p{page_id}.jpg"),
        crop, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY],
    )
    return ix0 + ruler_left_trim, iy0, ix1, iy1


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "pages", nargs="*",
        help="Page IDs (e.g. 010 015). Empty or 'all' = all images.",
    )
    args = ap.parse_args()

    if not args.pages or args.pages == ["all"]:
        page_ids = sorted(
            p.stem.replace("keph_p", "")
            for p in IMAGES_DIR.glob("keph_p*.jpg")
        )
    else:
        page_ids = args.pages

    n_done = 0
    n_skipped = 0
    progress = tqdm(page_ids, desc="crop pages", unit="page")
    for pid in progress:
        progress.set_postfix_str(f"p{pid}")
        krk = KRAKEN_DIR / f"kraken_p{pid}_lines.json"
        if not krk.exists():
            tqdm.write(f"p{pid}: SKIP (no kraken json)")
            n_skipped += 1
            continue
        try:
            x0, y0, x1, y1 = process(pid)
        except SystemExit as e:
            tqdm.write(f"p{pid}: ERROR {e}")
            n_skipped += 1
            continue
        tqdm.write(f"p{pid}: bbox=({x0},{y0})-({x1},{y1})")
        n_done += 1

    print(
        f"\ndone: {n_done} cropped, {n_skipped} skipped -> {OUT_DIR}"
    )


if __name__ == "__main__":
    main()
