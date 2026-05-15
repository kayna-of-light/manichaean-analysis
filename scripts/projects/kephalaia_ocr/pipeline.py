"""Generalized Kephalaia per-page pipeline.

Stages:
  1. kraken_full   : Kraken segment full page         -> kraken_pNNN_lines.json
  2. crop_body     : compute body bbox + crop         -> keph_pNNN_body.jpg, keph_pNNN_body_bbox.json
  3. kraken_body   : Kraken segment body crop         -> kraken_pNNN_body_lines.json
  4. clean         : clean baselines + gap fill       -> kraken_pNNN_body_clean.json
  5. base_split    : Sauvola + CC + base/other split  -> keph_pNNN_lines_base_split.json + visual

Usage:
  python pipeline_kephalaia.py --page 050
  python pipeline_kephalaia.py --page 050 --force
  python pipeline_kephalaia.py --pages 050 120 200

Existing outputs are skipped unless --force.

Stages 1 + 3 shell out to Kraken in WSL Ubuntu (/opt/miniconda/envs/kraken/bin/kraken).
All other stages run in-process with cv2/numpy.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import cv2
import numpy as np
import math
from tqdm import tqdm

REPO = Path(__file__).resolve().parents[3]
IMAGES_DIR = REPO / "output" / "projects" / "kephalaia_v2" / "coptic" / "images"
PAGES_DIR = REPO / "output" / "projects" / "kephalaia_ocr" / "pages"
PAGES_DIR.mkdir(parents=True, exist_ok=True)

KRAKEN_BIN = "/opt/miniconda/envs/kraken/bin/kraken"
WSL_DISTRO = "Ubuntu"

# ---------------------------------------------------------------- constants
INK_MIN_PIXELS = 2
MARGIN_X = 8
MARGIN_Y = 4

WARP_HEIGHT = 60
SAUVOLA_W = 12
SAUVOLA_K = 0.2
SAUVOLA_R = 128.0
BASELINE_TOL = 5
BLEED_BOTTOM_MAX_Y = 6
NOISE_AREA_FRAC = 0.0015

COLOR_BASE = (60, 220, 60)
COLOR_OTHER = (60, 60, 240)

BODY_TEXT_MIN_WIDTH = 350
BODY_RUN_CLOSE_GAP = 34
# Margin preferences. We prefer whitespace around the body crop, never
# adjacent content. Padding is the IDEAL margin from the body content; the
# actual left/right edges are then clamped to the line-number-column gap
# so we don't include line numbers / margin marginalia.
BODY_X_PAD_LEFT = 30
BODY_X_PAD_RIGHT = 30
BODY_Y_PAD_TOP = 25
BODY_Y_PAD_BOTTOM = 25
# Line-number / left-margin column detection.
LN_COL_SCAN_MAX_DIST = 220   # how far left of body to look for line-number column
LN_COL_INK_FRAC_MIN = 0.04   # column must have ≥4% of body-height worth of ink
LN_COL_GAP_MIN = 14          # min whitespace from line-number col to body
LN_COL_PREFERRED_MARGIN = 12 # preferred whitespace from detected col edge

# Horizontal-rule detection (separator lines between header/body and body/footnote).
RULE_MIN_WIDTH_FRAC = 0.25         # rule must span at least this fraction of page width
RULE_MIN_WIDTH_FRAC_FOOTER = 0.06  # below the 60% page line, footer-rules are short (often ~150px)
RULE_INK_DENSITY_MIN = 0.80        # within its run, this fraction of pixels must be ink
RULE_VERTICAL_THICKNESS_MAX = 6    # consecutive ink rows allowed for a single rule
RULE_MERGE_GAP_PX = 4              # merge nearby rule rows into a single rule

# Body-line step-regularity filter.
BODY_STEP_TOLERANCE_FRAC = 0.30    # a line is body-step-regular if its neighbour gap is within this frac of median step
BODY_STEP_MIN_NEIGHBOURS = 1       # need at least this many step-regular neighbours
FOOTNOTE_LINE_HEIGHT_MAX_FRAC = 0.65  # lines whose height < frac * median body line height are footnote-like


# ============================================================ paths
class Paths:
    def __init__(self, page: str) -> None:
        self.page = page
        self.src = IMAGES_DIR / f"keph_p{page}.jpg"
        self.kraken_full = PAGES_DIR / f"kraken_p{page}_lines.json"
        self.body_jpg = PAGES_DIR / f"keph_p{page}_body.jpg"
        self.body_bbox = PAGES_DIR / f"keph_p{page}_body_bbox.json"
        self.body_preview = PAGES_DIR / f"keph_p{page}_body_preview.png"
        self.kraken_body = PAGES_DIR / f"kraken_p{page}_body_lines.json"
        self.clean = PAGES_DIR / f"kraken_p{page}_body_clean.json"
        self.clean_visual = PAGES_DIR / f"kraken_p{page}_body_clean_visual.png"
        self.split_json = PAGES_DIR / f"keph_p{page}_lines_base_split.json"
        self.split_visual = PAGES_DIR / f"keph_p{page}_lines_base_split_visual.png"


# ============================================================ helpers
def win_to_wsl(path: Path) -> str:
    """Convert C:\\foo\\bar to /mnt/c/foo/bar."""
    s = str(path).replace("\\", "/")
    if len(s) > 1 and s[1] == ":":
        s = "/mnt/" + s[0].lower() + s[2:]
    return s


def run_kraken(input_img: Path, output_json: Path,
               max_retries: int = 4) -> None:
    """Run kraken in WSL with retry on transient WSL/service failures."""
    cmd = [
        "wsl", "-d", WSL_DISTRO, "-e", "bash", "-c",
        f"{KRAKEN_BIN} -i {win_to_wsl(input_img)} {win_to_wsl(output_json)} segment -bl",
    ]
    last_err = ""
    for attempt in range(1, max_retries + 1):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=300)
        except subprocess.TimeoutExpired as e:
            last_err = f"timeout: {e}"
        else:
            if proc.returncode == 0 and output_json.exists():
                return
            last_err = (f"rc={proc.returncode} "
                        f"stdout={proc.stdout[-300:]!r} "
                        f"stderr={proc.stderr[-300:]!r}")
        # Backoff before retry — gives WSL time to recover.
        import time
        time.sleep(2 + attempt * 3)
    raise RuntimeError(f"kraken failed for {input_img.name} after "
                       f"{max_retries} attempts: {last_err}")


def pct(arr: list[float], q: float) -> float:
    if not arr:
        raise ValueError("cannot take percentile of an empty list")
    ordered = sorted(arr)
    idx = max(0, min(len(ordered) - 1, int(len(ordered) * q)))
    return float(ordered[idx])


def runs_from_mask(mask: np.ndarray) -> list[tuple[int, int]]:
    idx = np.flatnonzero(mask)
    if len(idx) == 0:
        return []
    runs: list[tuple[int, int]] = []
    start = int(idx[0])
    prev = int(idx[0])
    for value in idx[1:]:
        x = int(value)
        if x == prev + 1:
            prev = x
            continue
        runs.append((start, prev))
        start = x
        prev = x
    runs.append((start, prev))
    return runs


def merge_close_runs(runs: list[tuple[int, int]], max_gap: int) -> list[tuple[int, int]]:
    if not runs:
        return []
    merged = [runs[0]]
    for start, end in runs[1:]:
        prev_start, prev_end = merged[-1]
        if start - prev_end - 1 <= max_gap:
            merged[-1] = (prev_start, end)
        else:
            merged.append((start, end))
    return merged


def infer_body_text_span(
    ink: np.ndarray,
    x0: float,
    x1: float,
    y0: float,
    y1: float,
) -> tuple[int, int] | None:
    h, w = ink.shape[:2]
    xlo = max(0, int(round(x0)) - 20)
    xhi = min(w, int(round(x1)) + 20)
    ylo = max(0, int(round(y0)) - 30)
    yhi = min(h, int(round(y1)) + 24)
    if xhi <= xlo or yhi <= ylo:
        return None

    col_has_ink = ink[ylo:yhi, xlo:xhi].sum(axis=0) >= INK_MIN_PIXELS
    runs = [(a + xlo, b + xlo) for a, b in runs_from_mask(col_has_ink)]
    runs = merge_close_runs(runs, BODY_RUN_CLOSE_GAP)
    runs = [(a, b) for a, b in runs if b - a + 1 >= 8]
    if not runs:
        return None

    widest = max(runs, key=lambda run: run[1] - run[0])
    chosen = runs[0]
    if len(runs) > 1:
        first_width = runs[0][1] - runs[0][0] + 1
        widest_width = widest[1] - widest[0] + 1
        first_gap = runs[1][0] - runs[0][1] - 1
        if first_width < 0.45 * widest_width and first_gap > 20:
            chosen = runs[1]
    return chosen


def regular_y_runs(lines: list[dict]) -> tuple[list[list[dict]], float]:
    if len(lines) < 3:
        return [lines], 41.0
    ordered = sorted(lines, key=lambda row: row["ymid"])
    gaps = [
        ordered[i + 1]["ymid"] - ordered[i]["ymid"]
        for i in range(len(ordered) - 1)
    ]
    plausible_gaps = [gap for gap in gaps if 20.0 <= gap <= 70.0]
    line_step = float(np.median(plausible_gaps)) if plausible_gaps else 41.0
    max_gap = max(90.0, line_step * 2.35)

    runs: list[list[dict]] = []
    current = [ordered[0]]
    for prev, cur in zip(ordered, ordered[1:]):
        if cur["ymid"] - prev["ymid"] <= max_gap:
            current.append(cur)
        else:
            runs.append(current)
            current = [cur]
    runs.append(current)
    return runs, line_step


def select_body_line_runs(lines: list[dict]) -> tuple[list[dict], float, list[int]]:
    runs, line_step = regular_y_runs(lines)
    if not runs:
        return [], line_step, []
    best_len = max(len(run) for run in runs)
    # Accept runs of ≥3 lines or ≥25% of the longest run, whichever is smaller.
    # Pages can legitimately have a short top run (chapter ending) plus a long bottom run.
    min_run_len = max(3, int(round(best_len * 0.20)))
    selected = [run for run in runs if len(run) >= min_run_len]
    if not selected:
        selected = [max(runs, key=len)]
    body_lines = [row for run in selected for row in run]
    return sorted(body_lines, key=lambda row: row["ymid"]), line_step, [len(run) for run in selected]


def find_horizontal_rules(ink: np.ndarray) -> list[dict]:
    """Find horizontal separator rule lines on the page.

    Returns a list of {y_mid, y_top, y_bot, x_left, x_right, width_frac} dicts,
    sorted top-to-bottom. A rule is a near-continuous horizontal ink stripe of
    limited vertical thickness (≤ RULE_VERTICAL_THICKNESS_MAX rows).

    Width threshold is tiered:
      - Above the 60% page line: requires RULE_MIN_WIDTH_FRAC of page width
        (e.g. 25% — for header/body separators that span the column).
      - Below the 60% page line: requires only RULE_MIN_WIDTH_FRAC_FOOTER
        (e.g. 6%) — footnote separators are conventionally short, often only
        100-200px wide regardless of page width.
    """
    H, W = ink.shape[:2]
    body_min_run = int(W * RULE_MIN_WIDTH_FRAC)
    footer_min_run = int(W * RULE_MIN_WIDTH_FRAC_FOOTER)
    footer_y_threshold = int(0.60 * H)
    # For each row, find the longest contiguous ink run and its bounds.
    row_records: list[tuple[int, int, int, int]] = []  # (y, run_len, x0, x1)
    for y in range(H):
        row = ink[y]
        if not row.any():
            continue
        # Find longest run of True
        idx = np.flatnonzero(row)
        if len(idx) == 0:
            continue
        # Allow tiny gaps within a rule (≤ 3 px)
        runs = []
        start = idx[0]
        prev = idx[0]
        for v in idx[1:]:
            if v - prev <= 3:
                prev = v
                continue
            runs.append((int(start), int(prev)))
            start = v
            prev = v
        runs.append((int(start), int(prev)))
        # Pick the widest run
        widest = max(runs, key=lambda r: r[1] - r[0])
        run_len = widest[1] - widest[0] + 1
        # Apply tiered width threshold based on Y position.
        min_run = footer_min_run if y >= footer_y_threshold else body_min_run
        if run_len < min_run:
            continue
        # Density check: within the widest run, must be mostly ink
        density = float(row[widest[0]:widest[1] + 1].sum()) / max(1, run_len)
        if density < RULE_INK_DENSITY_MIN:
            continue
        row_records.append((y, run_len, widest[0], widest[1]))

    if not row_records:
        return []

    # Group consecutive (or near-consecutive) ink-rich rows into single rules.
    rules: list[dict] = []
    current: list[tuple[int, int, int, int]] = [row_records[0]]
    for rec in row_records[1:]:
        if rec[0] - current[-1][0] <= RULE_MERGE_GAP_PX:
            current.append(rec)
        else:
            if len(current) <= RULE_VERTICAL_THICKNESS_MAX:
                rules.append(_rule_from_rows(current, W))
            current = [rec]
    if len(current) <= RULE_VERTICAL_THICKNESS_MAX:
        rules.append(_rule_from_rows(current, W))

    return sorted(rules, key=lambda r: r["y_mid"])


def _rule_from_rows(rows: list[tuple[int, int, int, int]], W: int) -> dict:
    ys = [r[0] for r in rows]
    x_left = min(r[2] for r in rows)
    x_right = max(r[3] for r in rows)
    return {
        "y_top": min(ys),
        "y_bot": max(ys),
        "y_mid": (min(ys) + max(ys)) / 2.0,
        "x_left": x_left,
        "x_right": x_right,
        "width_frac": (x_right - x_left + 1) / float(W),
    }


def filter_body_band_by_rules(rules: list[dict], H: int) -> tuple[float, float]:
    """Given detected rule lines, return (band_top, band_bottom) y-bounds for the body.

    Strategy:
      - Rules above the page midline are header separators -> band_top = below the lowest such rule
      - Rules below the page midline are footnote separators -> band_bottom = above the topmost such rule
      - If none on a side, fall back to default page margins (8% / 92%).
    """
    midline = 0.5 * H
    upper_rules = [r for r in rules if r["y_mid"] < midline]
    lower_rules = [r for r in rules if r["y_mid"] >= midline]

    if upper_rules:
        # The lowest upper rule (closest to body) is the header separator
        band_top = max(r["y_bot"] for r in upper_rules) + 4
    else:
        band_top = 0.08 * H

    if lower_rules:
        # The topmost lower rule (closest to body) is the footnote separator
        band_bottom = min(r["y_top"] for r in lower_rules) - 4
    else:
        band_bottom = 0.92 * H

    return float(band_top), float(band_bottom)


def filter_body_lines_by_step(
    lines: list[dict],
    expected_step: float | None = None,
) -> tuple[list[dict], float]:
    """Keep only lines whose y-step to a neighbour matches the dominant body step.

    Returns (filtered_lines, dominant_step). Footnote lines (which use a
    much tighter step than body lines) are dropped.
    """
    if len(lines) < 3:
        return lines, expected_step or 41.0

    ordered = sorted(lines, key=lambda row: row["ymid"])
    gaps = [
        ordered[i + 1]["ymid"] - ordered[i]["ymid"]
        for i in range(len(ordered) - 1)
    ]
    # Body lines typically step 35-55 px. Anything below 22 is footnote.
    body_gaps = [g for g in gaps if 30.0 <= g <= 60.0]
    if not body_gaps:
        # Pages where Kraken merged or split lines weirdly; just return as-is
        return ordered, expected_step or float(np.median(gaps)) if gaps else 41.0

    dominant_step = float(np.median(body_gaps))
    tol = max(8.0, dominant_step * BODY_STEP_TOLERANCE_FRAC)

    # For each line, count how many neighbours are within step tolerance.
    # Allow gap = N * step for N in 1..4 (skipping over short top runs / missed lines).
    keep = []
    for i, line in enumerate(ordered):
        ok_neighbours = 0
        for j in (i - 1, i + 1):
            if 0 <= j < len(ordered):
                gap = abs(ordered[i]["ymid"] - ordered[j]["ymid"])
                for n in (1, 2, 3, 4):
                    if abs(gap - n * dominant_step) <= n * tol:
                        ok_neighbours += 1
                        break
        if ok_neighbours >= BODY_STEP_MIN_NEIGHBOURS:
            keep.append(line)

    if len(keep) < 6:
        # Filter was too aggressive; back off
        return ordered, dominant_step
    return keep, dominant_step


def _collect_digit_blobs(
    mask: np.ndarray, x_offset: int, y_offset: int
) -> list[tuple[float, float, int, int]]:
    """Run CCs on a binary mask and return digit-shaped blobs as
    (cy_abs, cx_abs, w, h)."""
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    out = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if 4 <= w <= 55 and 8 <= h <= 40 and area >= 14:
            cy = y + h / 2 + y_offset
            cx = x + w / 2 + x_offset
            out.append((cy, cx, int(w), int(h)))
    return out


def _validate_ln_column(
    digits: list[tuple[float, float, int, int]],
    band_lo: float,
    band_hi: float,
    body_line_step: float,
) -> tuple[list[tuple[float, float, int, int]], float, float] | None:
    """Given digit blobs and an X band, verify it forms a regular vertical
    stack at body_line_step. Returns (validated_digits, y_top, y_bot) or None."""
    in_band = [d for d in digits if band_lo <= d[1] <= band_hi]
    if len(in_band) < 6:
        return None

    in_band.sort(key=lambda d: d[0])
    # Collapse digits at the same Y (two-digit pairs).
    collapsed = []
    for d in in_band:
        if collapsed and abs(d[0] - collapsed[-1][0]) <= 6:
            continue
        collapsed.append(d)
    if len(collapsed) < 6:
        return None

    cys_c = [d[0] for d in collapsed]
    tol = max(8.0, body_line_step * 0.25)
    tol_skip = max(4.0, body_line_step * 0.10)

    # Find the longest run of digits at integer multiples of body_line_step.
    # Try each possible starting digit and pick the longest accepted run.
    best_accepted: list[int] = []
    for start in range(len(cys_c)):
        accepted = [start]
        last = cys_c[start]
        for i in range(start + 1, len(cys_c)):
            gap = cys_c[i] - last
            if abs(gap - body_line_step) <= tol:
                accepted.append(i)
                last = cys_c[i]
                continue
            matched = False
            for k in (2, 3):
                if abs(gap - k * body_line_step) <= tol_skip:
                    accepted.append(i)
                    last = cys_c[i]
                    matched = True
                    break
            if matched:
                continue
            if gap > body_line_step + tol:
                break
        if len(accepted) > len(best_accepted):
            best_accepted = accepted

    if len(best_accepted) < 6:
        return None

    in_band = [collapsed[j] for j in best_accepted]

    cys = [d[0] for d in in_band]
    gaps = [cys[i + 1] - cys[i] for i in range(len(cys) - 1)]
    plausible = [g for g in gaps if 20.0 <= g <= 70.0]
    if not plausible:
        return None
    med_gap = float(np.median(plausible))
    if abs(med_gap - body_line_step) > max(8.0, body_line_step * 0.30):
        return None

    y_tops = [d[0] - d[3] / 2 for d in in_band]
    y_bots = [d[0] + d[3] / 2 for d in in_band]
    return in_band, float(min(y_tops)), float(max(y_bots))


def _find_line_number_column_extent(
    ink: np.ndarray,
    gray: np.ndarray,
    body_text_left: float,
    band_top: float,
    band_bottom: float,
    body_line_step: float,
) -> tuple[int, int, int, int] | None:
    """Detect the line-number column and return its geometry:
    (y_top, y_bottom, col_left, col_right).

    The line numbers (e.g. "1", "2", ..., "32") form a tight vertical stack
    of small digit blobs in a narrow column, with a clear horizontal
    whitespace gap to their right (separating them from body text).

    Algorithm:
      1. Build a digit candidate set from both the standard Otsu `ink` mask
         and a local adaptive threshold (catches faint scans where line
         numbers are too light for global Otsu).
      2. Search a wide window around `body_text_left` (which is a noisy
         estimate — kraken sometimes includes line numbers in the text-line
         boundary, so the line-number column may sit near or slightly right
         of `body_text_left`).
      3. Histogram cx and identify peaks. For each peak:
           a. Validate it forms a regular vertical stack at body_line_step.
           b. Require a clear horizontal whitespace gap (≥12 empty
              ink-columns) within 30px to the RIGHT of the peak — this
              proves it's a real column separated from body text.
      4. Return the LEFTMOST valid peak (line numbers are leftmost; any
         body-text-start peak that happens to look digit-like would be to
         its right).
    """
    H, W = ink.shape[:2]
    x_lo = max(0, int(body_text_left) - LN_COL_SCAN_MAX_DIST)
    # Allow window to extend slightly RIGHT of body_text_left in case kraken
    # included line numbers in its text boundary (then body_text_left is
    # actually pointing AT the line-number column).
    x_hi = min(W, int(body_text_left) + 80)
    y_lo = max(0, int(band_top))
    y_hi = min(H, int(band_bottom))
    if x_hi - x_lo < 30 or y_hi - y_lo < 100:
        return None

    # Otsu-based digit candidates.
    ink_region = (ink[y_lo:y_hi, x_lo:x_hi].astype(np.uint8)) * 255
    digits_otsu = _collect_digit_blobs(ink_region, x_lo, y_lo)

    # Adaptive-threshold candidates (catches faint line numbers that Otsu drops).
    gray_region = gray[y_lo:y_hi, x_lo:x_hi]
    if gray_region.size > 0:
        # Use a small block size (sensitive to local contrast) and modest C.
        adapt = cv2.adaptiveThreshold(
            gray_region, 255,
            cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 21, 6,
        )
        # Light open to remove single-pixel noise that adaptive threshold creates.
        adapt = cv2.morphologyEx(
            adapt, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), iterations=1
        )
        digits_adapt = _collect_digit_blobs(adapt, x_lo, y_lo)
    else:
        digits_adapt = []

    # Merge: dedupe by (cx, cy) proximity.
    digits = list(digits_otsu)
    for d in digits_adapt:
        if not any(abs(d[0] - e[0]) < 5 and abs(d[1] - e[1]) < 5 for e in digits_otsu):
            digits.append(d)

    if len(digits) < 6:
        return None

    cxs = np.array([d[1] for d in digits], dtype=np.float64)
    bin_w = 8.0
    cx_min = float(cxs.min()); cx_max = float(cxs.max())
    n_bins = max(1, int(math.ceil((cx_max - cx_min + 1.0) / bin_w)))
    counts, edges = np.histogram(cxs, bins=n_bins, range=(cx_min, cx_max + 1.0))
    if counts.size == 0:
        return None

    # Identify candidate peaks (local maxima with count >= 4).
    peak_threshold = max(4, int(0.3 * counts.max()))
    sig = counts >= peak_threshold
    # Group contiguous sig bins into peak windows.
    peak_windows: list[tuple[float, float]] = []
    i = 0
    while i < len(sig):
        if sig[i]:
            j = i
            while j + 1 < len(sig) and sig[j + 1]:
                j += 1
            peak_windows.append((edges[i] - 4.0, edges[j + 1] + 6.0))
            i = j + 1
        else:
            i += 1

    # Vertical projection of ink (Otsu) over the BAND y-range — used for the
    # whitespace-gap test.
    band_proj = ink[y_lo:y_hi, x_lo:x_hi].astype(np.uint8).sum(axis=0)

    def has_right_gap(peak_x_left: float, peak_x_right: float) -> bool:
        """True if there's a notable drop in ink density immediately right of
        this peak. Compares the per-column ink in the next 25px to the ink
        within the peak itself; the right region should be at most 30% as
        dense (proving the line-number column is followed by whitespace
        before body text starts)."""
        local_l = max(0, int(round(peak_x_left - x_lo)))
        local_r = int(round(peak_x_right - x_lo))
        if local_r <= local_l:
            return False
        peak_density = float(band_proj[local_l:local_r + 1].mean())
        if peak_density <= 0:
            return False
        gap_lo = local_r + 2  # skip 2px right of peak
        gap_hi = min(len(band_proj), gap_lo + 25)
        if gap_hi - gap_lo < 8:
            return False
        gap_density = float(band_proj[gap_lo:gap_hi].mean())
        return gap_density < 0.30 * peak_density

    # Validate peaks left-to-right and pick the FIRST that passes.
    for (band_lo, band_hi) in peak_windows:
        result = _validate_ln_column(digits, band_lo, band_hi, body_line_step)
        if result is None:
            continue
        in_band, col_y_top, col_y_bot = result
        peak_x_right = max(d[1] + d[2] / 2 for d in in_band)
        peak_x_left = min(d[1] - d[2] / 2 for d in in_band)
        if not has_right_gap(peak_x_left, peak_x_right):
            continue

        # Capture second digit of two-digit numbers within Y-range, slightly
        # right of the peak's primary x_right but BEFORE the whitespace gap.
        x_right_extended = peak_x_right
        wy_lo = max(0, int(col_y_top) - 4)
        wy_hi = min(H, int(col_y_bot) + 4)
        wide_x_hi = min(W, int(peak_x_right) + 25)
        if wide_x_hi > x_lo and wy_hi > wy_lo:
            wide_region = ink[wy_lo:wy_hi, x_lo:wide_x_hi].astype(np.uint8) * 255
            wn, _, wstats, _ = cv2.connectedComponentsWithStats(wide_region, connectivity=8)
            for i in range(1, wn):
                x, y, w, h, area = wstats[i]
                if not (4 <= w <= 55 and 8 <= h <= 40 and area >= 14):
                    continue
                cx = x + w / 2 + x_lo
                r = x + w + x_lo
                if peak_x_right < cx <= peak_x_right + 25 and r > x_right_extended:
                    x_right_extended = r

        return (
            int(round(col_y_top)),
            int(round(col_y_bot)),
            int(round(peak_x_left)),
            int(round(x_right_extended)),
        )

    return None


def _find_left_column_edges_by_projection(
    ink: np.ndarray,
    gray: np.ndarray,
    body_y_top: int,
    body_y_bot: int,
    body_text_left_hint: float,
) -> tuple[int, int] | None:
    """Find the line-number column and the gap before body text using a
    column-ink projection over the (already-trimmed) body Y-band.

    Algorithm:
      1. Compute per-column ink density over y in [body_y_top, body_y_bot]
         using BOTH the global Otsu mask and a local adaptive threshold
         (the latter rescues faint scans).
      2. Scanning the X range [body_text_left_hint - 220, body_text_left_hint + 60]
         from LEFT to RIGHT:
           a. Skip leading whitespace (low-density columns at the left).
           b. The first run of "active" columns (density above threshold)
              is the line-number column.
           c. After that run, look for a clear "gap" — a stretch of ≥10
              low-density columns. The gap is the whitespace between the
              line-number column and body text.
           d. Body text begins at the first active column after the gap.
      3. Return (line_number_column_right_edge, body_text_left_edge).

    If no convincing column+gap pattern is found, return None.
    """
    H, W = ink.shape[:2]
    body_y_top = max(0, int(body_y_top))
    body_y_bot = min(H, int(body_y_bot))
    if body_y_bot - body_y_top < 100:
        return None

    x_lo = max(0, int(body_text_left_hint) - 220)
    # Extend right far enough to confirm body text has started AND continues
    # for a substantial run. We need at least ~150px of body context to
    # reliably distinguish "real body" from a stray ink mark.
    x_hi = min(W, int(body_text_left_hint) + 200)
    if x_hi - x_lo < 60:
        return None

    band = ink[body_y_top:body_y_bot, x_lo:x_hi].astype(np.uint8)
    band_h = band.shape[0]

    # Adaptive-threshold rescue for faint line numbers.
    gband = gray[body_y_top:body_y_bot, x_lo:x_hi]
    adapt = cv2.adaptiveThreshold(
        gband, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV, 21, 6,
    )
    adapt = cv2.morphologyEx(adapt, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), iterations=1)
    # Combine: any pixel that is ink in EITHER mask counts as ink.
    combined = np.maximum(band, (adapt > 0).astype(np.uint8))

    # Per-column ink fraction over Y.
    col_ink = combined.sum(axis=0).astype(np.float64) / max(1, band_h)

    # Threshold for "active" column. Body text columns typically have
    # 0.05-0.20 ink fraction. Line numbers are sparser (only N digits in
    # ~30 lines = ~0.03-0.08). Use a low threshold to catch line numbers.
    active_thresh = 0.012  # ~1.2% of column has ink
    active = col_ink >= active_thresh

    # Find runs.
    runs: list[tuple[int, int, str]] = []  # (lo, hi, kind)
    i = 0
    while i < len(active):
        if active[i]:
            j = i
            while j + 1 < len(active) and active[j + 1]:
                j += 1
            runs.append((i, j, "active"))
            i = j + 1
        else:
            j = i
            while j + 1 < len(active) and not active[j + 1]:
                j += 1
            runs.append((i, j, "gap"))
            i = j + 1

    # Walk the runs left-to-right looking for the FIRST active run
    # (= line-number column) followed by the FIRST clear gap.
    # We do not require what comes after the gap to "look like body" —
    # the Y-band has already been trimmed of header/footer, so anything
    # right of the gap is body content (or a centered heading, page
    # marker, etc., which is still body-region content we want to keep).
    n = len(runs)
    for k, (lo, hi, kind) in enumerate(runs):
        if kind != "active":
            continue
        ln_width = hi - lo + 1
        # The line-number column should be narrow. Two-digit numbers
        # spread to ~25-35px; allow up to 60px for safety.
        if ln_width > 60:
            # Too wide — first ink column is already body text.
            # No line-number column on this page.
            return None
        # Need a following gap.
        if k + 1 >= n:
            return None
        gap_lo, gap_hi, gap_kind = runs[k + 1]
        if gap_kind != "gap":
            return None
        gap_width = gap_hi - gap_lo + 1
        # Require a substantive gap so we are not picking the
        # space between two digits of a two-digit line number.
        if gap_width < 10:
            return None
        ln_right_global = x_lo + hi
        # Body left = first column of whatever run comes after the gap,
        # OR the right edge of the gap itself if no further run exists.
        if k + 2 < n and runs[k + 2][2] == "active":
            body_left_global = x_lo + runs[k + 2][0]
        else:
            body_left_global = x_lo + gap_hi
        return ln_right_global, body_left_global

    return None


def _find_marginal_column_edge(
    ink: np.ndarray,
    body_y_top: float,
    body_y_bot: float,
    body_x: float,
    direction: int,
    max_distance: int = LN_COL_SCAN_MAX_DIST,
) -> int | None:
    """Find the edge (facing the body) of a marginal text column (line numbers
    on the left, marginalia on the right) within the body Y band.

    direction = -1 -> scan leftward from body_x looking for line-number column;
                returns the right edge of the leftmost ink column found.
    direction = +1 -> scan rightward from body_x looking for marginalia;
                returns the left edge of the rightmost ink column found.

    Returns None if no marginal column is detected within max_distance.
    """
    H, W = ink.shape[:2]
    y0 = max(0, int(body_y_top))
    y1 = min(H, int(body_y_bot))
    if y1 - y0 < 50:
        return None
    band = ink[y0:y1, :].astype(np.uint8)
    col_ink = band.sum(axis=0)
    body_h = y1 - y0
    threshold = max(8, int(LN_COL_INK_FRAC_MIN * body_h))

    if direction < 0:
        x_start = max(1, int(body_x) - 5)
        x_stop = max(0, x_start - max_distance)
        # Walk left until we find an ink-heavy column
        ink_x: int | None = None
        for x in range(x_start, x_stop, -1):
            if col_ink[x] >= threshold:
                ink_x = x
                break
        if ink_x is None:
            return None
        # Now walk left from ink_x to find the LEFT edge of this column
        # (so we get its full extent and can return its right edge correctly).
        # We expand right first to find the right edge of the column.
        right = ink_x
        x = ink_x
        while x + 1 < W and col_ink[x + 1] >= threshold * 0.5 and (x + 1) < int(body_x):
            x += 1
            if col_ink[x] >= threshold:
                right = x
        return int(right)
    else:
        x_start = min(W - 2, int(body_x) + 5)
        x_stop = min(W, x_start + max_distance)
        ink_x = None
        for x in range(x_start, x_stop):
            if col_ink[x] >= threshold:
                ink_x = x
                break
        if ink_x is None:
            return None
        # Walk right to find left edge of column (smallest x with continuous ink)
        left = ink_x
        x = ink_x
        while x - 1 >= 0 and col_ink[x - 1] >= threshold * 0.5 and (x - 1) > int(body_x):
            x -= 1
            if col_ink[x] >= threshold:
                left = x
        return int(left)


def _detect_footnote_y_cap(lines: list[dict], page_h: int = 2258) -> float | None:
    """Pre-detect the y-coordinate at which a footnote block begins.

    A footnote block must satisfy ALL of:
      - Located in the lower 30% of the page (y > 0.70 * page_h)
      - Median line_height < 0.78 * leading-window median line_height
      - Median pairwise gap < 0.85 * leading-window median gap
    The leading window must be \u22656 lines for the detection to fire.

    Returns the y of the first footnote line, or None.
    """
    if len(lines) < 9:
        return None
    ordered = sorted(lines, key=lambda c: c["ymid"])
    K = 3  # window size for footnote candidate
    LEAD_MIN = 6
    y_lower_threshold = 0.70 * page_h

    for i in range(LEAD_MIN, len(ordered) - K + 1):
        leading = ordered[:i]
        candidate = ordered[i:i + K]

        if candidate[0]["ymid"] < y_lower_threshold:
            continue  # too high on page to be footnote

        lead_heights = [float(c.get("line_height", 0)) for c in leading if c.get("line_height", 0) > 0]
        cand_heights = [float(c.get("line_height", 0)) for c in candidate if c.get("line_height", 0) > 0]
        if not lead_heights or not cand_heights:
            continue
        lead_h = float(np.median(lead_heights))
        cand_h = float(np.median(cand_heights))

        lead_gaps = [leading[j + 1]["ymid"] - leading[j]["ymid"] for j in range(len(leading) - 1)]
        lead_gaps_filt = [g for g in lead_gaps if 25.0 <= g <= 70.0]
        if not lead_gaps_filt:
            continue
        lead_gap = float(np.median(lead_gaps_filt))

        cand_gaps = [candidate[j + 1]["ymid"] - candidate[j]["ymid"] for j in range(K - 1)]
        med_cand_gap = float(np.median(cand_gaps))

        small_height = cand_h < 0.78 * lead_h
        tight_gap = med_cand_gap < 0.85 * lead_gap

        # Require BOTH height AND gap signals (and lower-page position above)
        if small_height and tight_gap:
            return float(candidate[0]["ymid"])
    return None


def detect_footnote_top(
    candidates: list[dict],
    body_lines: list[dict],
    body_y_max: float,
) -> float | None:
    """Find the top y of the footnote block.

    Footnote text uses smaller font AND tighter line spacing than body text.
    Look for the first ymid > body_y_max where the next 3 candidates form a
    block whose median pairwise spacing is < 0.80 * body_step OR whose median
    height is < 0.80 * body_height. Either signal qualifies.
    """
    if not candidates or not body_lines:
        return None

    # Body baseline metrics (use only the actual selected body_lines)
    body_ymids = sorted(float(b["ymid"]) for b in body_lines)
    if len(body_ymids) < 3:
        return None
    body_gaps = [body_ymids[i + 1] - body_ymids[i] for i in range(len(body_ymids) - 1)]
    body_step = float(np.median([g for g in body_gaps if 25.0 <= g <= 70.0])) if body_gaps else 0.0
    body_heights = [float(b.get("line_height", 0)) for b in body_lines if b.get("line_height", 0) > 0]
    body_h = float(np.median(body_heights)) if body_heights else 0.0

    if body_step <= 0 and body_h <= 0:
        return None

    step_max = 0.80 * body_step if body_step > 0 else 1e9
    height_max = 0.80 * body_h if body_h > 0 else 1e9

    ordered = sorted(candidates, key=lambda c: c["ymid"])
    # Look for first index i with ymid > body_y_max where the 3-line block i..i+2
    # has either tight median spacing or small median height.
    for i in range(len(ordered) - 2):
        if ordered[i]["ymid"] <= body_y_max:
            continue
        block = [ordered[i + j] for j in range(3)]
        gaps = [block[j + 1]["ymid"] - block[j]["ymid"] for j in range(2)]
        med_gap = float(np.median(gaps))
        med_h = float(np.median([c.get("line_height", body_h) for c in block]))
        if med_gap < step_max or med_h < height_max:
            return float(ordered[i]["ymid"])
    return None


# ============================================================ stage: crop_body
def _find_line_number_column_pure(
    ink: np.ndarray,
    gray: np.ndarray,
    band_top: int,
    band_bottom: int,
    page_width: int,
) -> dict | None:
    """Pure-logic line-number column + body-left detector via projection.

    Every Kephalaia page has the same gross structure inside the rule band:

        [LN col left-digit]  [LN col right-digit]   <gap>   [BODY TEXT ...]
        narrow run (~10px)    narrow run (~10px)    40-100  very wide run (500-800px)

    Some pages have a single combined narrow run. We:

      1. Compute the vertical ink projection of the rule band.
      2. Find runs of "active" columns (≥ 4% of band height has ink).
      3. The first 1-2 narrow runs (width ≤ 40px) form the LN column.
         Merge two consecutive narrow runs if separated by ≤ 25px (two
         digits of a two-digit line number).
      4. The first WIDE run (width ≥ 100px) after a clear gap is the body.

    Returns dict with x_left, x_right, body_left, y_first, y_last
    or None if structure does not match.

    y_first / y_last come from a horizontal projection of the body x-range
    so we capture the true first/last text line, with chapter title /
    page marker excluded (those are typically above line 1 with no LN).
    """
    H, W = ink.shape[:2]
    y_lo = max(0, int(band_top))
    y_hi = min(H, int(band_bottom))
    band_h = y_hi - y_lo
    if band_h < 200 or page_width < 200:
        return None

    # 1. Vertical ink projection of the band.
    band_proj = ink[y_lo:y_hi, :].astype(np.uint8).sum(axis=0)
    active_thr = max(8, int(0.04 * band_h))
    active = band_proj >= active_thr

    # 2. Active runs (start, end_inclusive, width).
    runs: list[tuple[int, int, int]] = []
    x = 0
    while x < page_width:
        if active[x]:
            x0 = x
            while x < page_width and active[x]:
                x += 1
            runs.append((x0, x - 1, x - x0))
        else:
            x += 1
    if len(runs) < 2:
        return None

    # 3. Find the LN col: scan from the left for narrow runs.
    #    - Width ≤ 40px is "narrow".
    #    - If two consecutive narrow runs are ≤ 25px apart, merge them
    #      (two-digit line numbers).
    #    - The narrow group must be followed by a clear gap (≥ 30px) and
    #      then a WIDE run (≥ 100px) — the body text.
    NARROW_MAX = 40
    MERGE_GAP = 25
    REQUIRED_BODY_GAP = 18
    BODY_WIDE_MIN = 100

    # Skip any tiny isolated runs in the far left margin (≤ 4px wide and
    # far from anything else).
    ln_start_idx = None
    for i, (rs, re_, rw) in enumerate(runs):
        if rw <= NARROW_MAX and rw >= 4:
            ln_start_idx = i
            break
    if ln_start_idx is None:
        return None

    # Build LN group by merging consecutive narrow runs separated by ≤ 25px.
    ln_runs: list[tuple[int, int, int]] = [runs[ln_start_idx]]
    j = ln_start_idx + 1
    while j < len(runs):
        prev_end = ln_runs[-1][1]
        rs, re_, rw = runs[j]
        gap = rs - prev_end - 1
        if rw <= NARROW_MAX and gap <= MERGE_GAP:
            ln_runs.append(runs[j])
            j += 1
        else:
            break

    ln_left = ln_runs[0][0]
    ln_right = ln_runs[-1][1]
    ln_width = ln_right - ln_left + 1

    # The LN col should never be very wide.
    if ln_width > 60:
        return None

    # 4. After LN group, find body_left = first active run that starts at
    #    least REQUIRED_BODY_GAP after the LN col. body_right = last active
    #    column in the band (some pages have fragmented body with many
    #    narrow runs instead of one wide run).
    body_left = None
    for k in range(j, len(runs)):
        rs, re_, rw = runs[k]
        if rs - ln_right - 1 >= REQUIRED_BODY_GAP:
            body_left = rs
            break
    if body_left is None:
        return None
    # body_right: last active column overall.
    active_idx = np.flatnonzero(active)
    if active_idx.size == 0:
        return None
    body_right = int(active_idx[-1])
    if body_right <= body_left:
        return None

    # 5. Y-bounds: horizontal ink projection across the body x-range.
    #    Find first/last y with sustained ink → captures real first/last
    #    body line. Page marker / chapter title above line 1 (without LN)
    #    typically have a horizontal-projection gap separating them from
    #    body text, so they get excluded.
    body_strip = ink[y_lo:y_hi, body_left:body_right + 1].astype(np.uint8)
    h_proj = body_strip.sum(axis=1)
    h_thr = max(4, int(0.02 * (body_right - body_left + 1)))
    h_active = h_proj >= h_thr

    # Find all y-runs of active rows.
    y_runs: list[tuple[int, int]] = []
    yy = 0
    while yy < band_h:
        if h_active[yy]:
            y0 = yy
            while yy < band_h and h_active[yy]:
                yy += 1
            y_runs.append((y0, yy - 1))
        else:
            yy += 1
    if not y_runs:
        return None

    # The largest contiguous "text region" is the body lines (separated
    # by short inter-line gaps). Group y-runs into clusters where the
    # gap between consecutive runs is ≤ 50px (one line step is ~41px,
    # but we allow extra slack for sparse lacuna lines).
    LINE_GAP_MAX = 55
    clusters: list[tuple[int, int, int]] = []  # (y_first, y_last, n_runs)
    cur_y0 = y_runs[0][0]
    cur_y1 = y_runs[0][1]
    cur_n = 1
    for (a, b) in y_runs[1:]:
        if a - cur_y1 <= LINE_GAP_MAX:
            cur_y1 = b
            cur_n += 1
        else:
            clusters.append((cur_y0, cur_y1, cur_n))
            cur_y0, cur_y1, cur_n = a, b, 1
    clusters.append((cur_y0, cur_y1, cur_n))

    # Pick the cluster with the largest y-extent. That's the body text.
    body_cluster = max(clusters, key=lambda c: c[1] - c[0])
    y_first = body_cluster[0] + y_lo
    y_last = body_cluster[1] + y_lo

    return {
        "x_left": int(ln_left),
        "x_right": int(ln_right),
        "y_first": int(y_first),
        "y_last": int(y_last),
        "body_left": int(body_left),
        "body_right": int(body_right),
        "ln_runs": [list(r) for r in ln_runs],
        "ln_width": int(ln_width),
        "n_digits": None,
        "step": None,
    }


def stage_crop_body(p: Paths) -> None:
    """Compute body bounding box using PURE LOGIC — no kraken dependency.

    The page layout is simple and consistent:
      • Header (page-num + chapter title) at top, then a horizontal rule.
      • Body region containing:
          - Line-number column (1..32 in narrow column on the left).
          - Body text column.
      • Optional footer rule, then optional footnotes.

    Strategy:
      1. Detect horizontal rules → broad y-band.
      2. Scan left 40% of page within band, find the line-number column via
         CC on digit-sized blobs at regular y-spacing.
      3. Body y-bounds = first..last digit y (with padding).
      4. Body x-left = first sustained ink column after LN col (the body text).
      5. Body x-right = page-width minus margin.
    """
    img = cv2.imread(str(p.src))
    if img is None:
        raise SystemExit(f"could not read {p.src}")
    H, W = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binimg = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    ink = binimg > 0

    # 1. Rules → broad y-band.
    rules = find_horizontal_rules(ink)
    band_top, band_bottom = filter_body_band_by_rules(rules, H)
    band_top_i = int(max(0, round(band_top)))
    band_bottom_i = int(min(H, round(band_bottom)))
    if band_bottom_i - band_top_i < 200:
        band_top_i = int(0.08 * H)
        band_bottom_i = int(0.92 * H)

    # 2. Line-number column → bx0 + precise y-bounds.
    ln = _find_line_number_column_pure(ink, gray, band_top_i, band_bottom_i, W)

    if ln is not None:
        # Body Y-bounds: first/last body-line y with padding for tall
        # glyphs / overlines / lacuna brackets that extend above/below.
        by0 = max(band_top_i, ln["y_first"] - 18)
        by1 = min(band_bottom_i, ln["y_last"] + 18)
        # Body X-left: place in the gap between LN col right and body text.
        gap = ln["body_left"] - ln["x_right"]
        if gap >= 2 * LN_COL_PREFERRED_MARGIN:
            bx0 = ln["x_right"] + max(LN_COL_PREFERRED_MARGIN, int(gap / 2))
        elif gap >= LN_COL_GAP_MIN:
            bx0 = ln["x_right"] + max(LN_COL_GAP_MIN // 2, int(gap / 2))
        else:
            bx0 = max(ln["x_right"] + 4, ln["body_left"] - 4)
        crop_method = "projection_pure"
    else:
        # Fallback: use the rule band with a conservative left margin
        # placed well to the right of any plausible LN col.
        by0 = band_top_i + BODY_Y_PAD_TOP
        by1 = band_bottom_i - BODY_Y_PAD_BOTTOM
        bx0 = int(0.30 * W)
        crop_method = "rules_only_fallback"

    bx0 = max(0, int(bx0))
    bx1 = max(bx0 + 100, W - 30)
    by0 = int(by0)
    by1 = int(by1)

    p.body_bbox.write_text(json.dumps({
        "page_size": [W, H],
        "bbox": {"x0": bx0, "y0": by0, "x1": bx1, "y1": by1},
        "crop_method": crop_method,
        "rules_detected": [
            {"y_mid": r["y_mid"], "width_frac": round(r["width_frac"], 3)}
            for r in rules
        ],
        "band_top": band_top,
        "band_bottom": band_bottom,
        "ln_column": ln,
    }, indent=2), encoding="utf-8")

    crop = img[by0:by1, bx0:bx1]
    cv2.imwrite(str(p.body_jpg), crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
    viz = img.copy()
    cv2.rectangle(viz, (bx0, by0), (bx1, by1), (0, 0, 255), 3)
    for r in rules:
        cv2.line(viz, (r["x_left"], int(r["y_mid"])), (r["x_right"], int(r["y_mid"])), (0, 200, 0), 2)
    if ln is not None:
        # Draw the detected LN column in blue.
        cv2.rectangle(viz, (ln["x_left"], ln["y_first"]),
                      (ln["x_right"], ln["y_last"]), (255, 100, 0), 2)
    cv2.imwrite(str(p.body_preview), viz)


def _stage_crop_body_OLD_KRAKEN_BASED(p: Paths) -> None:
    img = cv2.imread(str(p.src))
    if img is None:
        raise SystemExit(f"could not read {p.src}")
    H, W = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binimg = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    ink = binimg > 0

    # 1. Detect horizontal rule lines (header/body and body/footnote separators)
    rules = find_horizontal_rules(ink)
    band_top, band_bottom = filter_body_band_by_rules(rules, H)

    seg = json.loads(p.kraken_full.read_text(encoding="utf-8"))
    lines = seg.get("lines", [])

    # 2. Build candidates inside the body band only
    cand = []
    for L in lines:
        bl = L.get("baseline") or []
        if not bl:
            continue
        xs = [pt[0] for pt in bl]
        ys = [pt[1] for pt in bl]
        width = max(xs) - min(xs)
        ymid = (max(ys) + min(ys)) / 2
        if width < 80:
            continue
        if not (band_top <= ymid <= band_bottom):
            continue
        x0 = float(min(xs))
        x1 = float(max(xs))
        y0 = float(min(ys))
        y1 = float(max(ys))
        # Line height from boundary polygon (enclosing the line region).
        boundary = L.get("boundary") or []
        if boundary:
            by_pts = [pt[1] for pt in boundary]
            line_height = float(max(by_pts) - min(by_pts))
        else:
            line_height = float(max(1.0, y1 - y0))
        text_span = infer_body_text_span(ink, x0, x1, y0, y1)
        cand.append({
            "x0": x0,
            "x1": x1,
            "y0": y0,
            "y1": y1,
            "ymid": float(ymid),
            "width": float(width),
            "line_height": line_height,
            "text_span": text_span,
        })
    if not cand:
        raise RuntimeError(f"no body candidates for p{p.page}")

    long_text_lines = [
        c for c in cand
        if c["width"] >= BODY_TEXT_MIN_WIDTH and c["text_span"] is not None
    ]
    if len(long_text_lines) < 6:
        long_text_lines = [c for c in cand if c["text_span"] is not None]
    if not long_text_lines:
        long_text_lines = cand

    # 2b. Pre-detect footnote band by scanning candidates from top to bottom
    # and looking for a change point where line_height drops noticeably (footnote
    # uses smaller German font). This caps the band_bottom BEFORE we run
    # run-detection, so footnote lines don't pollute the body line set.
    # Use ALL candidates (including short body lines), not just wide ones.
    footnote_y_cap = _detect_footnote_y_cap(cand, page_h=H)
    if footnote_y_cap is not None:
        band_bottom = min(band_bottom, footnote_y_cap)
        long_text_lines = [c for c in long_text_lines if c["ymid"] < footnote_y_cap]

    rough_text_start = pct([c["text_span"][0] for c in long_text_lines if c["text_span"]], 0.25)
    x_compatible = [
        c for c in long_text_lines
        if c["text_span"] is None or abs(c["text_span"][0] - rough_text_start) <= 125
    ]
    if len(x_compatible) < 6:
        x_compatible = long_text_lines
    body_lines, body_line_step, body_run_lengths = select_body_line_runs(x_compatible)
    if len(body_lines) < 6:
        body_lines = long_text_lines
        body_run_lengths = [len(body_lines)]

    # 3. Step-regularity filter — drops footnote lines that slipped past the rules
    body_lines, dominant_step = filter_body_lines_by_step(body_lines, body_line_step)

    # 3b. Line-height filter — drop any remaining lines whose line_height is
    # far below the median (these are footnote lines with smaller German font).
    if body_lines:
        heights = [float(b.get("line_height", 0)) for b in body_lines if b.get("line_height", 0) > 0]
        if heights:
            median_h = float(np.median(heights))
            min_body_h = FOOTNOTE_LINE_HEIGHT_MAX_FRAC * median_h
            kept = [b for b in body_lines if b.get("line_height", median_h) >= min_body_h]
            if len(kept) >= 6:
                body_lines = kept

    text_starts = [c["text_span"][0] for c in body_lines if c["text_span"]]
    text_ends = [c["text_span"][1] for c in body_lines if c["text_span"]]
    if not text_starts or not text_ends:
        text_starts = [c["x0"] for c in body_lines]
        text_ends = [c["x1"] for c in body_lines]

    # 4. Compute bbox. Strategy: prefer whitespace margins around the body,
    # but never include adjacent content. Use the leftmost / rightmost body
    # glyph columns as anchors, then clamp to the line-number column gap.
    body_text_left = float(min(text_starts))
    body_text_right = float(max(text_ends))
    body_text_start_q15 = pct(text_starts, 0.15)
    body_text_start_median = pct(text_starts, 0.50)

    # Ideal padded edges
    ideal_bx0 = body_text_left - BODY_X_PAD_LEFT
    ideal_bx1 = body_text_right + BODY_X_PAD_RIGHT

    # Body Y range for the gap detection
    line_y0_min = min(c["y0"] for c in body_lines)
    line_y1_max = max(c["y1"] for c in body_lines)

    # Detect line-number column edge to the left of body content.
    ln_right_edge = _find_marginal_column_edge(
        ink, line_y0_min, line_y1_max, body_text_left, direction=-1
    )
    if ln_right_edge is not None:
        # Place bx0 in the gap, with preferred margin from both sides.
        gap = body_text_left - ln_right_edge
        if gap >= 2 * LN_COL_PREFERRED_MARGIN:
            # Lots of room: center the cut, then bias toward body for whitespace
            bx0_clamped = ln_right_edge + max(LN_COL_PREFERRED_MARGIN, int(gap / 2))
        elif gap >= LN_COL_GAP_MIN:
            # Small gap: split it
            bx0_clamped = ln_right_edge + max(LN_COL_GAP_MIN // 2, int(gap / 2))
        else:
            # Very narrow gap: hug body to avoid line numbers
            bx0_clamped = max(ln_right_edge + 4, int(body_text_left) - 4)
        bx0_final = max(int(round(ideal_bx0)), bx0_clamped)
    else:
        bx0_final = int(round(ideal_bx0))

    # Detect right marginalia column edge.
    rm_left_edge = _find_marginal_column_edge(
        ink, line_y0_min, line_y1_max, body_text_right, direction=+1
    )
    if rm_left_edge is not None:
        gap = rm_left_edge - body_text_right
        if gap >= 2 * LN_COL_PREFERRED_MARGIN:
            bx1_clamped = rm_left_edge - max(LN_COL_PREFERRED_MARGIN, int(gap / 2))
        elif gap >= LN_COL_GAP_MIN:
            bx1_clamped = rm_left_edge - max(LN_COL_GAP_MIN // 2, int(gap / 2))
        else:
            bx1_clamped = min(rm_left_edge - 4, int(body_text_right) + 4)
        bx1_final = min(int(round(ideal_bx1)), bx1_clamped)
    else:
        bx1_final = int(round(ideal_bx1))

    bx0 = int(max(0, bx0_final))
    bx1 = int(min(W, bx1_final))

    by0 = int(max(0, round(line_y0_min - BODY_Y_PAD_TOP)))
    by1 = int(min(H, round(line_y1_max + BODY_Y_PAD_BOTTOM)))

    # Hard-clamp to rule boundaries — never cross a detected rule
    by0 = max(by0, int(round(band_top)))
    by1 = min(by1, int(round(band_bottom)))

    # RIGHT-EDGE GUARANTEE: never clip body ink. Kraken sometimes underestimates
    # the rightmost glyph extent (especially on pages from secondary editions
    # like p244+ where glyph segmentation is imperfect). Extend bx1 to include
    # any ink in the body Y-band that sits right of the current bx1, stopping
    # only when we hit a clear horizontal gap (≥30px of empty columns) or the
    # page edge. The right side carries no marginalia in this corpus, so this
    # is safe.
    if by1 > by0:
        right_band = ink[by0:by1, :].astype(np.uint8)
        col_ink_full = right_band.sum(axis=0)
        ext_x = bx1
        gap_run = 0
        for x in range(bx1, W):
            if col_ink_full[x] > 0:
                ext_x = x
                gap_run = 0
            else:
                gap_run += 1
                if gap_run >= 30:
                    break
        if ext_x > bx1:
            bx1 = min(W, ext_x + BODY_X_PAD_RIGHT)

    # Line-height footnote detection — caps by1 if a sequence of small-font
    # lines is found below the body. Catches footnotes when no horizontal
    # rule was detected.
    footnote_top = detect_footnote_top(cand, body_lines, line_y1_max)
    if footnote_top is not None:
        # Pull bbox up to just above the footnote's first line.
        by1 = min(by1, int(round(footnote_top - 8)))

    # Line-number column detection — defines body Y-extent by digit positions.
    # This is the most reliable signal: line numbers appear at every body line,
    # including short / centered / drop-out lines that elude baseline-based
    # detection. We search the FULL band (not the baseline-derived by1) so
    # that line numbers below the last detected baseline can still be found.
    ln_search_y_top = int(round(band_top))
    ln_search_y_bot = int(round(band_bottom))
    if footnote_top is not None:
        ln_search_y_bot = min(ln_search_y_bot, int(round(footnote_top - 8)))
    ln_col_extent = _find_line_number_column_extent(
        ink, gray, body_text_start_q15, ln_search_y_top, ln_search_y_bot, body_line_step
    )
    if ln_col_extent is not None:
        ln_y_top, ln_y_bot, ln_col_left, ln_col_right = ln_col_extent
        # Determine confidence: how many body-line slots does the line-number
        # column actually span? A typical body has 28-36 lines. If we found
        # ≥24 line slots, the column is reliable as the authoritative bottom
        # — including when baselines spuriously extend into footnotes.
        ln_span_lines = (ln_y_bot - ln_y_top) / max(1.0, body_line_step)
        baseline_y_bot = int(round(line_y1_max + BODY_Y_PAD_BOTTOM))
        col_y_bot = ln_y_bot + BODY_Y_PAD_BOTTOM

        by0 = int(max(int(round(band_top)),
                      min(int(round(line_y0_min - BODY_Y_PAD_TOP)),
                          ln_y_top - BODY_Y_PAD_TOP)))
        if ln_span_lines >= 24:
            # Trust ln_col exclusively for the bottom.
            by1 = int(min(int(round(band_bottom)), col_y_bot))
        else:
            # ln_col is short (missing lines); take MAX with baselines.
            by1 = int(min(int(round(band_bottom)),
                          max(baseline_y_bot, col_y_bot)))
        # Re-apply footnote cap if it sits above the chosen bottom.
        if footnote_top is not None:
            by1 = min(by1, int(round(footnote_top - 8)))
        # Refine left edge using the actual line-number column, not the
        # generic ink-density scan.
        gap = body_text_left - ln_col_right
        if gap >= 2 * LN_COL_PREFERRED_MARGIN:
            bx0 = max(int(round(ideal_bx0)),
                      ln_col_right + max(LN_COL_PREFERRED_MARGIN, int(gap / 2)))
        elif gap >= LN_COL_GAP_MIN:
            bx0 = max(int(round(ideal_bx0)),
                      ln_col_right + max(LN_COL_GAP_MIN // 2, int(gap / 2)))
        else:
            bx0 = max(int(round(ideal_bx0)),
                      max(ln_col_right + 4, int(body_text_left) - 4))
        bx0 = max(0, bx0)

    # FINAL refinement using column-ink projection over the (now-trimmed)
    # body Y-band. This is the most direct test: scan left→right within the
    # final by0..by1 window and find the first narrow ink column followed
    # by a clear horizontal whitespace gap. The body crop should start AT
    # or just before that gap → body-text edge.
    proj_result = _find_left_column_edges_by_projection(
        ink, gray, by0, by1, body_text_left
    )
    proj_used = False
    if proj_result is not None:
        proj_ln_right, proj_body_left = proj_result
        gap = proj_body_left - proj_ln_right
        # Place bx0 inside the gap, biased toward the body so we keep the
        # first character of every line.
        if gap >= 2 * LN_COL_PREFERRED_MARGIN:
            proj_bx0 = proj_ln_right + max(LN_COL_PREFERRED_MARGIN, int(gap / 2))
        elif gap >= LN_COL_GAP_MIN:
            proj_bx0 = proj_ln_right + max(LN_COL_GAP_MIN // 2, int(gap / 2))
        else:
            # Hug body to avoid line numbers
            proj_bx0 = max(proj_ln_right + 4, proj_body_left - 4)
        # The projection result is authoritative (it's measured directly on
        # the trimmed body band), so override any earlier estimate.
        bx0 = max(0, proj_bx0)
        proj_used = True

    p.body_bbox.write_text(json.dumps({
        "page_size": [W, H],
        "bbox": {"x0": bx0, "y0": by0, "x1": bx1, "y1": by1},
        "crop_method": (
            "projection_left_column" if proj_used
            else ("line_number_column+rule_lines"
                  if ln_col_extent is not None
                  else "rule_lines+step_regularity")
        ),
        "n_body_candidates": len(cand),
        "n_body_lines": len(body_lines),
        "body_run_lengths": body_run_lengths,
        "body_line_step": dominant_step,
        "body_text_start_min": min(text_starts),
        "body_text_start_q25": pct(text_starts, 0.25),
        "body_text_start_median": body_text_start_median,
        "body_text_end_q95": pct(text_ends, 0.95),
        "rules_detected": [
            {"y_mid": r["y_mid"], "width_frac": round(r["width_frac"], 3)}
            for r in rules
        ],
        "band_top": band_top,
        "band_bottom": band_bottom,
        "ln_col_extent": (
            {"y_top": ln_col_extent[0], "y_bot": ln_col_extent[1],
             "x_left": ln_col_extent[2], "x_right": ln_col_extent[3]}
            if ln_col_extent is not None else None
        ),
        "footnote_top_detected": footnote_top,
    }, indent=2), encoding="utf-8")

    crop = img[by0:by1, bx0:bx1]
    cv2.imwrite(str(p.body_jpg), crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
    viz = img.copy()
    cv2.rectangle(viz, (bx0, by0), (bx1, by1), (0, 0, 255), 3)
    # Draw rule lines in green for verification
    for r in rules:
        cv2.line(viz, (r["x_left"], int(r["y_mid"])), (r["x_right"], int(r["y_mid"])), (0, 200, 0), 2)
    cv2.imwrite(str(p.body_preview), viz)


# ============================================================ stage: clean baselines
def stage_clean(p: Paths) -> None:
    img = cv2.imread(str(p.body_jpg))
    H, W = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binimg = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    ink = binimg > 0

    seg = json.loads(p.kraken_body.read_text(encoding="utf-8"))
    lines = seg.get("lines", [])

    per_line_slopes = []
    for L in lines:
        bl = L.get("baseline") or []
        if len(bl) >= 2:
            xs = np.array([pt[0] for pt in bl], dtype=float)
            ys = np.array([pt[1] for pt in bl], dtype=float)
            if xs.std() > 1.0:
                m, _ = np.polyfit(xs, ys, 1)
                per_line_slopes.append(m)
    global_m = float(np.median(per_line_slopes)) if per_line_slopes else 0.0

    cx = W / 2.0
    anchors = []
    for i, L in enumerate(lines):
        bl = L.get("baseline") or []
        if not bl:
            continue
        mx = float(np.mean([pt[0] for pt in bl]))
        my = float(np.mean([pt[1] for pt in bl]))
        anchor = my + global_m * (cx - mx)
        anchors.append({"anchor": anchor, "src_idx": i})
    anchors.sort(key=lambda a: a["anchor"])

    deduped = []
    for a in anchors:
        if deduped and abs(a["anchor"] - deduped[-1]["anchor"]) < 12:
            continue
        deduped.append(a)
    diffs = np.diff([a["anchor"] for a in deduped])
    line_step = float(np.median(diffs)) if len(diffs) else 41.0

    filled = [deduped[0]]
    for i in range(1, len(deduped)):
        prev = filled[-1]["anchor"]
        cur = deduped[i]["anchor"]
        gap = cur - prev
        n_missing = int(round(gap / line_step)) - 1
        if n_missing >= 1:
            for k in range(1, n_missing + 1):
                filled.append({
                    "anchor": prev + k * line_step,
                    "src_idx": -1,
                    "synthetic": True,
                })
        filled.append(deduped[i])

    h_top = line_step * 0.65
    h_bot = line_step * 0.35

    refined = []
    col_xs = np.arange(W)
    for i, A in enumerate(filled):
        baseline_ys = A["anchor"] + global_m * (col_xs - cx)
        has_ink = np.zeros(W, dtype=bool)
        for x in col_xs:
            y0 = int(max(0, baseline_ys[x] - h_top))
            y1 = int(min(H, baseline_ys[x] + h_bot))
            if y1 > y0 and int(ink[y0:y1, x].sum()) >= INK_MIN_PIXELS:
                has_ink[x] = True
        if not has_ink.any():
            continue
        ink_idx = np.where(has_ink)[0]
        xmin = max(0, int(ink_idx[0]) - MARGIN_X)
        xmax = min(W - 1, int(ink_idx[-1]) + MARGIN_X)

        def by(x: float) -> float:
            return A["anchor"] + global_m * (x - cx)

        tl = (xmin, max(0.0, by(xmin) - h_top - MARGIN_Y))
        tr = (xmax, max(0.0, by(xmax) - h_top - MARGIN_Y))
        br = (xmax, min(H - 1.0, by(xmax) + h_bot + MARGIN_Y))
        bl_pt = (xmin, min(H - 1.0, by(xmin) + h_bot + MARGIN_Y))

        refined.append({
            "index": i,
            "anchor_y_at_center": float(A["anchor"]),
            "global_slope": global_m,
            "synthetic": A.get("synthetic", False),
            "src_kraken_idx": A.get("src_idx"),
            "ink_xmin": int(ink_idx[0]),
            "ink_xmax": int(ink_idx[-1]),
            "quad": [[float(tl[0]), float(tl[1])],
                     [float(tr[0]), float(tr[1])],
                     [float(br[0]), float(br[1])],
                     [float(bl_pt[0]), float(bl_pt[1])]],
            "baseline": [[0.0, float(by(0))], [float(W - 1), float(by(W - 1))]],
        })

    p.clean.write_text(json.dumps({
        "image_size": [W, H],
        "global_slope": global_m,
        "line_step": line_step,
        "h_top": h_top,
        "h_bot": h_bot,
        "lines": refined,
    }, indent=2), encoding="utf-8")

    viz = img.copy()
    for r in refined:
        color = (0, 165, 255) if r["synthetic"] else (0, 200, 0)
        pts = np.array(r["quad"], dtype=np.int32).reshape(-1, 1, 2)
        cv2.polylines(viz, [pts], True, color, 1)
    cv2.imwrite(str(p.clean_visual), viz)


# ============================================================ stage: base_split
def sauvola(gray: np.ndarray, w: int, k: float, r: float) -> np.ndarray:
    g = gray.astype(np.float32)
    ksize = 2 * w + 1
    mean = cv2.boxFilter(g, ddepth=cv2.CV_32F, ksize=(ksize, ksize),
                         normalize=True, borderType=cv2.BORDER_REFLECT)
    sqmean = cv2.boxFilter(g * g, ddepth=cv2.CV_32F, ksize=(ksize, ksize),
                           normalize=True, borderType=cv2.BORDER_REFLECT)
    std = np.sqrt(np.maximum(sqmean - mean * mean, 0.0))
    threshold = mean * (1.0 + k * (std / r - 1.0))
    return (g < threshold).astype(np.uint8)


def warp_quad_to_rect(img, quad, h_target):
    tl, tr, br, bl = quad
    width = int(round(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl))))
    src = quad.astype(np.float32)
    dst = np.array([[0, 0], [width - 1, 0],
                    [width - 1, h_target - 1], [0, h_target - 1]],
                   dtype=np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    Minv = cv2.getPerspectiveTransform(dst, src)
    warped = cv2.warpPerspective(img, M, (width, h_target),
                                 flags=cv2.INTER_LINEAR, borderValue=255)
    return warped, Minv, width


def stage_base_split(p: Paths) -> None:
    img = cv2.imread(str(p.body_jpg))
    H, W = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    seg = json.loads(p.clean.read_text(encoding="utf-8"))
    h_top = seg["h_top"]
    h_bot = seg["h_bot"]
    line_step = h_top + h_bot
    baseline_y = int(round(h_top / line_step * WARP_HEIGHT))

    out_lines = []
    viz = img.copy()
    for r in seg["lines"]:
        quad = np.array(r["quad"], dtype=np.float32)
        warped_gray, Minv, w = warp_quad_to_rect(gray, quad, WARP_HEIGHT)
        ink = sauvola(warped_gray, SAUVOLA_W, SAUVOLA_K, SAUVOLA_R)

        n_lab, _, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
        blobs = []
        for lab in range(1, n_lab):
            x, y, bw, bh, area = stats[lab]
            if area < NOISE_AREA_FRAC * WARP_HEIGHT * WARP_HEIGHT:
                continue
            top, bot = int(y), int(y + bh - 1)
            if bot <= BLEED_BOTTOM_MAX_Y:
                continue
            touches = (top <= baseline_y + BASELINE_TOL
                       and bot >= baseline_y - BASELINE_TOL)
            kind = "base" if touches else "other"
            blobs.append({
                "id": int(lab),
                "kind": kind,
                "warped_bbox": [int(x), int(y), int(x + bw - 1), int(y + bh - 1)],
                "area": int(area),
            })
        blobs.sort(key=lambda b: b["warped_bbox"][0])

        for b in blobs:
            x0, y0, x1, y1 = b["warped_bbox"]
            corners_w = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]],
                                 dtype=np.float32).reshape(-1, 1, 2)
            corners_img = cv2.perspectiveTransform(corners_w, Minv).reshape(-1, 2)
            b["img_quad"] = corners_img.tolist()

        bl_w = np.array([[0, baseline_y], [w - 1, baseline_y]],
                        dtype=np.float32).reshape(-1, 1, 2)
        bl_img = cv2.perspectiveTransform(bl_w, Minv).reshape(-1, 2).tolist()

        out_lines.append({
            "line_index": r["index"],
            "synthetic": r.get("synthetic", False),
            "warped_size": [w, WARP_HEIGHT],
            "baseline_y_warped": baseline_y,
            "blobs": blobs,
        })

        line_color = (0, 165, 255) if r.get("synthetic") else (0, 200, 0)
        cv2.polylines(viz, [np.array(r["quad"], dtype=np.int32).reshape(-1, 1, 2)],
                      True, line_color, 1)
        cv2.line(viz,
                 (int(round(bl_img[0][0])), int(round(bl_img[0][1]))),
                 (int(round(bl_img[1][0])), int(round(bl_img[1][1]))),
                 (255, 255, 0), 1, cv2.LINE_AA)
        for b in blobs:
            color = COLOR_BASE if b["kind"] == "base" else COLOR_OTHER
            cpts = np.array(b["img_quad"], dtype=np.int32).reshape(-1, 1, 2)
            cv2.polylines(viz, [cpts], True, color, 1)

    p.split_json.write_text(json.dumps({
        "page": p.page,
        "image_size": [W, H],
        "warp_height": WARP_HEIGHT,
        "baseline_y_warped": baseline_y,
        "baseline_tol": BASELINE_TOL,
        "lines": out_lines,
    }, indent=2), encoding="utf-8")
    cv2.imwrite(str(p.split_visual), viz)


# ============================================================ driver
def run_page(page: str, force: bool = False) -> dict:
    """Run all stages for one page. Returns {'page', 'ok', 'msg', 'stages'}."""
    p = Paths(page)
    stages_done = []
    if not p.src.exists():
        return {"page": page, "ok": False, "msg": f"missing source: {p.src.name}",
                "stages": stages_done}
    try:
        if force or not p.kraken_full.exists():
            run_kraken(p.src, p.kraken_full); stages_done.append("kraken_full")
        if force or not p.body_jpg.exists() or not p.body_bbox.exists():
            stage_crop_body(p); stages_done.append("crop_body")
        if force or not p.kraken_body.exists():
            run_kraken(p.body_jpg, p.kraken_body); stages_done.append("kraken_body")
        if force or not p.clean.exists():
            stage_clean(p); stages_done.append("clean")
        if force or not p.split_json.exists():
            stage_base_split(p); stages_done.append("base_split")
        return {"page": page, "ok": True, "msg": "ok", "stages": stages_done}
    except Exception as e:
        return {"page": page, "ok": False,
                "msg": f"{type(e).__name__}: {e}",
                "stages": stages_done,
                "trace": traceback.format_exc()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", help="single zero-padded page id, e.g. 050")
    ap.add_argument("--pages", nargs="+", help="multiple pages")
    ap.add_argument("--all", action="store_true",
                    help="process every page found in IMAGES_DIR")
    ap.add_argument("--force", action="store_true",
                    help="rerun even if outputs exist")
    ap.add_argument("-j", "--max-concurrency", type=int, default=8)
    args = ap.parse_args()

    pages: list[str] = []
    if args.page:
        pages.append(args.page)
    if args.pages:
        pages.extend(args.pages)
    if args.all:
        for f in sorted(IMAGES_DIR.glob("keph_p*.jpg")):
            pages.append(f.stem.replace("keph_p", ""))
    pages = list(dict.fromkeys(pages))  # preserve order, dedup
    if not pages:
        ap.error("provide --page, --pages, or --all")

    n_workers = max(1, args.max_concurrency)
    print(f"running {len(pages)} pages with {n_workers} workers")

    failures: list[dict] = []
    with ThreadPoolExecutor(max_workers=n_workers) as ex:
        futs = {ex.submit(run_page, pg, args.force): pg for pg in pages}
        with tqdm(total=len(futs), unit="page") as pbar:
            for fut in as_completed(futs):
                res = fut.result()
                if not res["ok"]:
                    failures.append(res)
                    tqdm.write(f"FAIL p{res['page']}: {res['msg']}")
                pbar.set_postfix(failed=len(failures))
                pbar.update(1)

    print(f"\ndone: {len(pages) - len(failures)}/{len(pages)} ok")
    if failures:
        log = PAGES_DIR.parent / "_pipeline_failures.json"
        log.write_text(json.dumps(failures, indent=2), encoding="utf-8")
        print(f"failures logged to {log}")


if __name__ == "__main__":
    main()
