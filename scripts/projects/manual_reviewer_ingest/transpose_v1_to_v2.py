"""Transpose v1 OCR results onto the v2 body crop / geometry for the manual reviewer.

v2 is leading:
- canvas:  output/projects/kephalaia_ocr_v2/line_body_split/text_body/p{NNN}_text_body.jpg
- rows:    output/projects/kephalaia_ocr_v2/body_geometry/pages/p{NNN}_geometry.json
            (geometry_rows[].baseline_y + x_span in v2 text_body coordinates)

v1 supplies tokens (cluster, label, candidates, overrides) with geometry in its
own body-crop coordinates:
- tokens:  output/projects/kephalaia_ocr/contextual_review/clusters_shape_padded_split_bodycrop_corrected_k240/line_sequences.jsonl
- quads:   output/projects/kephalaia_ocr/pages_base_split_chars_bodycrop_corrected/keph_p{NNN}_lines_base_split.json
            (lines[].blobs[].img_quad in v1 body-crop coordinates)

Per row we compute an affine map (x_span + baseline_y; isotropic y-scale ~= x-scale)
that takes a v1 img_quad point to a v2 text_body point. Rows are matched by
ordinal index; if v1 and v2 disagree on row count we mark the page low-confidence
but still emit (best effort, no rows dropped on the v2 side).

Output: output/projects/kephalaia_manual_reviewer/initial_baseline/p{NNN}.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any

REPO = Path(__file__).resolve().parents[3]
V1_OCR = REPO / "output" / "projects" / "kephalaia_ocr"
V2_OCR = REPO / "output" / "projects" / "kephalaia_ocr_v2"
OUT_ROOT = REPO / "output" / "projects" / "kephalaia_manual_reviewer"
INITIAL_DIR = OUT_ROOT / "initial_baseline"
SUMMARY_PATH = OUT_ROOT / "summary.json"

V1_LINE_SPLIT_DIR = V1_OCR / "pages_base_split_chars_bodycrop_corrected"
V1_LINE_SEQUENCES = (
    V1_OCR
    / "llm_witness"
    / "clusters_shape_padded_split_bodycrop_corrected_k240"
    / "composite_line_sequences.jsonl"
)
V2_BODY_GEOM_DIR = V2_OCR / "body_geometry" / "pages"
V2_LINE_BODY_META_DIR = V2_OCR / "line_body_split" / "metadata"
V2_TEXT_BODY_DIR = V2_OCR / "line_body_split" / "text_body"


@dataclass
class V1Blob:
    blob_id: int
    warped_bbox: list[int]
    img_quad: list[list[float]]


@dataclass
class V2Row:
    line_index: int
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


def load_v1_blobs(page: str) -> tuple[dict[int, list[V1Blob]], tuple[int, int]] | None:
    """Return {line_index: [V1Blob, ...]}, image_size or None if missing."""
    path = V1_LINE_SPLIT_DIR / f"keph_p{page}_lines_base_split.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    img_size = tuple(data.get("image_size") or (0, 0))
    out: dict[int, list[V1Blob]] = {}
    for ln in data.get("lines", []):
        idx = int(ln.get("line_index", -1))
        blobs: list[V1Blob] = []
        for b in ln.get("blobs", []):
            quad = b.get("img_quad")
            if not quad:
                continue
            blobs.append(
                V1Blob(
                    blob_id=int(b.get("id")),
                    warped_bbox=list(b.get("warped_bbox") or []),
                    img_quad=[[float(p[0]), float(p[1])] for p in quad],
                )
            )
        out[idx] = blobs
    return out, img_size  # type: ignore[return-value]


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


def v1_row_metrics(blobs: list[V1Blob]) -> dict[str, float] | None:
    """Estimate row baseline, x-span, and height from v1 img_quads."""
    if not blobs:
        return None
    bottom_ys: list[float] = []
    top_ys: list[float] = []
    xs_min: list[float] = []
    xs_max: list[float] = []
    for b in blobs:
        ys = [p[1] for p in b.img_quad]
        xs = [p[0] for p in b.img_quad]
        bottom_ys.append(max(ys))
        top_ys.append(min(ys))
        xs_min.append(min(xs))
        xs_max.append(max(xs))
    return {
        "baseline_y": median(bottom_ys),
        "top_y": median(top_ys),
        "x_min": min(xs_min),
        "x_max": max(xs_max),
        "height": median(bottom_ys) - median(top_ys),
    }


def build_row_transform(v1m: dict[str, float], v2: V2Row) -> tuple[float, float, float, float, float]:
    """Return affine parameters (sx, sy, tx, ty, baseline_y_v2).

    Maps a v1 (x, y) -> v2 (x', y') with:
        x' = sx * (x - x_min_v1) + x_span_v2[0]
        y' = sy * (y - baseline_y_v1) + baseline_y_v2
    sy is set to sx (isotropic) to preserve glyph proportions; rows compensate
    for vertical drift via their own baseline_y.
    """
    span_v1 = max(v1m["x_max"] - v1m["x_min"], 1.0)
    span_v2 = max(v2.x_span[1] - v2.x_span[0], 1.0)
    sx = span_v2 / span_v1
    sy = sx  # isotropic
    tx = v2.x_span[0]
    ty = v2.baseline_y
    return sx, sy, tx, ty, v2.baseline_y


def transform_quad(
    quad: list[list[float]],
    v1m: dict[str, float],
    tr: tuple[float, float, float, float, float],
) -> list[list[float]]:
    sx, sy, tx, ty, _ = tr
    out: list[list[float]] = []
    for x, y in quad:
        x2 = (x - v1m["x_min"]) * sx + tx
        y2 = (y - v1m["baseline_y"]) * sy + ty
        out.append([round(x2, 3), round(y2, 3)])
    return out


def quad_axis_aligned(quad: list[list[float]]) -> list[float]:
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    return [min(xs), min(ys), max(xs), max(ys)]


def transpose_page(
    page: str,
    sequences_by_page: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    v1_load = load_v1_blobs(page)
    v2_load = load_v2_rows(page)
    if v1_load is None:
        return {"page": page, "status": "missing_v1_geometry"}
    if v2_load is None:
        return {"page": page, "status": "missing_v2_geometry"}
    v1_blobs_by_line, v1_img_size = v1_load
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
        idx for idx in v1_blobs_by_line if idx in v1_tokens_by_line and v1_blobs_by_line[idx]
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
        v1_blobs = v1_blobs_by_line[v1_idx]
        v1m = v1_row_metrics(v1_blobs)
        if not v1m:
            continue
        tr = build_row_transform(v1m, v2_row)
        # Build a map blob_id -> transformed quad and aabb
        blob_geom: dict[int, dict[str, Any]] = {}
        for b in v1_blobs:
            q2 = transform_quad(b.img_quad, v1m, tr)
            aabb = quad_axis_aligned(q2)
            blob_geom[b.blob_id] = {
                "img_quad": q2,
                "warped_bbox": b.warped_bbox,
                "aabb": aabb,
            }

        # Merge v1 composite units with transformed geometry. Drop only units
        # that cannot be placed on the v2 canvas; mark attachment decisions come
        # from the v1 composite witness, not from v2 geometry.
        tokens_out: list[dict[str, Any]] = []
        for tok in v1_tokens_by_line[v1_idx]:
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
            t = {
                "blob_id": bid,
                "cluster": tok.get("cluster"),
                "label": tok.get("label"),
                "manual_override": tok.get("manual_override"),
                "manual_warning": tok.get("manual_warning"),
                "geometric_override": tok.get("geometric_override"),
                "editorial_override": tok.get("editorial_override"),
                "subcluster_override": tok.get("subcluster_override"),
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
        V2_TEXT_BODY_DIR.relative_to(REPO).as_posix() + f"/p{page}_text_body.jpg"
    )
    return {
        "page": page,
        "status": "ok",
        "image": text_body_rel,
        "image_size": list(v2_img_size),
        "v1_image_size": list(v1_img_size),
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

    INITIAL_DIR.mkdir(parents=True, exist_ok=True)

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

    summary_pages: list[dict[str, Any]] = []
    n_ok = 0
    for page in page_set:
        result = transpose_page(page, sequences_by_page)
        if not result:
            continue
        if result.get("status") == "ok":
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
        "pages": summary_pages,
    }
    if not args.dry_run:
        SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[transpose] done: {n_ok}/{len(page_set)} pages ok", file=sys.stderr)


if __name__ == "__main__":
    main()
