"""Global KMeans cluster of base blobs across all Kephalaia pages.

Reads every temp/keph_pNNN_lines_base_split.json, extracts each "base" blob
from the corresponding warped binarized strip (Sauvola, same params as the
pipeline), embeds it as a 32x32 binarized patch, L2-normalizes, runs a
single KMeans across the whole corpus.

Outputs:
  temp/base_clusters_global/
    _overview.png        centroid grid (annotated id/size, sorted)
    _summary.json        cluster sizes + per-cluster page coverage
    _assignments.parquet|.json   one row per blob (page,line,blob_id,cluster)
    c_NN_nNNN.png        per-cluster sample montage

Usage:
  python cluster_base_global.py
  python cluster_base_global.py --n-clusters 60 --montage 96
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import cv2
import numpy as np
from sklearn.cluster import MiniBatchKMeans

REPO = Path(__file__).resolve().parents[3]
PAGES_DIR = REPO / "output" / "projects" / "kephalaia_ocr" / "pages"
OUT = REPO / "output" / "projects" / "kephalaia_ocr" / "clusters"
OUT.mkdir(parents=True, exist_ok=True)

# Must match pipeline_kephalaia.py
WARP_HEIGHT = 60
SAUVOLA_W = 12
SAUVOLA_K = 0.2
SAUVOLA_R = 128.0

PATCH = 32
SEED = 42

SPLIT_RE = re.compile(r"^keph_p([0-9]+(?:_cont)?)_lines_base_split\.json$")


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
    quad = np.asarray(quad, dtype=np.float32)
    tl, tr, br, bl = quad
    width = int(round(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl))))
    src = quad
    dst = np.array([[0, 0], [width - 1, 0],
                    [width - 1, h_target - 1], [0, h_target - 1]],
                   dtype=np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(img, M, (width, h_target),
                                 flags=cv2.INTER_LINEAR, borderValue=255)
    return warped


def patch_from_blob(ink: np.ndarray, bbox) -> np.ndarray | None:
    x0, y0, x1, y1 = bbox
    crop = ink[y0:y1 + 1, x0:x1 + 1]
    if crop.size == 0:
        return None
    crop = (crop * 255).astype(np.uint8)
    resized = cv2.resize(crop, (PATCH, PATCH), interpolation=cv2.INTER_AREA)
    binp = (resized.astype(np.float32) / 255.0 > 0.4).astype(np.float32)
    if binp.sum() < 1:
        return None
    return binp


def collect() -> tuple[np.ndarray, list[dict]]:
    feats = []
    meta = []
    files = sorted(PAGES_DIR.glob("keph_p*_lines_base_split.json"))
    print(f"found {len(files)} per-page split files")
    for f in files:
        m = SPLIT_RE.match(f.name)
        if not m:
            continue
        page = m.group(1)
        body_jpg = PAGES_DIR / f"keph_p{page}_body.jpg"
        clean_json = PAGES_DIR / f"kraken_p{page}_body_clean.json"
        if not body_jpg.exists() or not clean_json.exists():
            print(f"  skip p{page}: missing body/clean")
            continue

        img = cv2.imread(str(body_jpg))
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clean = json.loads(clean_json.read_text(encoding="utf-8"))
        # map line index -> quad (from clean)
        quad_by_idx = {L["index"]: L["quad"] for L in clean["lines"]}

        split = json.loads(f.read_text(encoding="utf-8"))
        n_blobs = 0
        for L in split["lines"]:
            li = L["line_index"]
            quad = quad_by_idx.get(li)
            if quad is None:
                continue
            warped_gray = warp_quad_to_rect(gray, quad, WARP_HEIGHT)
            ink = sauvola(warped_gray, SAUVOLA_W, SAUVOLA_K, SAUVOLA_R)
            for b in L["blobs"]:
                if b["kind"] != "base":
                    continue
                p = patch_from_blob(ink, b["warped_bbox"])
                if p is None:
                    continue
                v = p.flatten().astype(np.float32)
                n = float(np.linalg.norm(v))
                if n < 1e-6:
                    continue
                feats.append(v / n)
                meta.append({
                    "page": page,
                    "line_index": li,
                    "blob_id": b["id"],
                    "warped_bbox": b["warped_bbox"],
                    "area": b["area"],
                })
                n_blobs += 1
        print(f"  p{page}: {n_blobs} base blobs")

    if not feats:
        raise SystemExit("no features collected")
    X = np.stack(feats).astype(np.float32)
    return X, meta


def make_overview(centers: np.ndarray, sizes: np.ndarray) -> np.ndarray:
    n = len(centers)
    cols = 8
    rows = int(np.ceil(n / cols))
    cell_pad = 4
    label_h = 18
    cell_w = PATCH * 3 + cell_pad * 2
    cell_h = PATCH * 3 + cell_pad * 2 + label_h
    canvas = np.full((rows * cell_h, cols * cell_w, 3), 255, dtype=np.uint8)

    order = np.argsort(-sizes)
    for r, ci in enumerate(order):
        row = r // cols
        col = r % cols
        cen = centers[ci]
        m = float(np.ptp(cen))
        if m < 1e-6:
            cen_img = np.zeros_like(cen, dtype=np.float32)
        else:
            cen_img = (cen - cen.min()) / m
        img = (cen_img * 255).astype(np.uint8).reshape(PATCH, PATCH)
        img3 = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        big = cv2.resize(img3, (PATCH * 3, PATCH * 3), interpolation=cv2.INTER_NEAREST)
        y0 = row * cell_h + cell_pad
        x0 = col * cell_w + cell_pad
        canvas[y0:y0 + PATCH * 3, x0:x0 + PATCH * 3] = big
        label = f"c{ci:02d} n={int(sizes[ci])}"
        cv2.putText(canvas, label,
                    (x0, y0 + PATCH * 3 + label_h - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
    return canvas


def make_cluster_montage(X: np.ndarray, idxs: np.ndarray, n_max: int) -> np.ndarray:
    sel = idxs[:n_max]
    cols = 16
    rows = int(np.ceil(len(sel) / cols))
    pad = 2
    cell = PATCH * 2 + pad * 2
    canvas = np.full((rows * cell, cols * cell, 3), 255, dtype=np.uint8)
    for k, i in enumerate(sel):
        row = k // cols
        col = k % cols
        v = X[i]
        img = (v.reshape(PATCH, PATCH) * 255).astype(np.uint8)
        img = 255 - img  # invert: black ink on white
        img3 = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        big = cv2.resize(img3, (PATCH * 2, PATCH * 2), interpolation=cv2.INTER_NEAREST)
        y0 = row * cell + pad
        x0 = col * cell + pad
        canvas[y0:y0 + PATCH * 2, x0:x0 + PATCH * 2] = big
    return canvas


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-clusters", type=int, default=60)
    ap.add_argument("--montage", type=int, default=96,
                    help="max samples per cluster montage")
    ap.add_argument("--batch-size", type=int, default=4096)
    args = ap.parse_args()

    X, meta = collect()
    print(f"\nFEATURE MATRIX: {X.shape}  (n={len(meta)} blobs)")

    print(f"\nKMeans n_clusters={args.n_clusters}")
    km = MiniBatchKMeans(n_clusters=args.n_clusters, random_state=SEED,
                        batch_size=args.batch_size, n_init=10, max_iter=300)
    labels = km.fit_predict(X)
    centers = km.cluster_centers_

    # Stats.
    sizes = np.bincount(labels, minlength=args.n_clusters)
    print("cluster sizes (sorted desc):",
          sorted(sizes.tolist(), reverse=True))

    # Overview.
    overview = make_overview(centers, sizes)
    cv2.imwrite(str(OUT / "_overview.png"), overview)

    # Per-cluster montages (samples nearest to centroid first).
    dists = np.linalg.norm(X - centers[labels], axis=1)
    for ci in range(args.n_clusters):
        sel = np.where(labels == ci)[0]
        if len(sel) == 0:
            continue
        sel_sorted = sel[np.argsort(dists[sel])]
        montage = make_cluster_montage(X, sel_sorted, args.montage)
        cv2.imwrite(str(OUT / f"c_{ci:02d}_n{len(sel):04d}.png"), montage)

    # Per-cluster page coverage.
    coverage = []
    for ci in range(args.n_clusters):
        sel = np.where(labels == ci)[0]
        pages = sorted({meta[i]["page"] for i in sel})
        coverage.append({"cluster": int(ci), "size": int(len(sel)),
                          "n_pages": len(pages),
                          "pages_sample": pages[:10]})
    coverage.sort(key=lambda d: -d["size"])

    summary = {
        "n_blobs": int(len(meta)),
        "n_clusters": int(args.n_clusters),
        "patch": PATCH,
        "warp_height": WARP_HEIGHT,
        "sauvola": {"w": SAUVOLA_W, "k": SAUVOLA_K, "r": SAUVOLA_R},
        "cluster_sizes_desc": sorted(sizes.tolist(), reverse=True),
        "coverage": coverage,
    }
    (OUT / "_summary.json").write_text(json.dumps(summary, indent=2),
                                       encoding="utf-8")

    # Assignments JSON (light: only labels + page/line/blob).
    assigns = []
    for i, m in enumerate(meta):
        assigns.append({
            "page": m["page"],
            "line_index": m["line_index"],
            "blob_id": m["blob_id"],
            "warped_bbox": m["warped_bbox"],
            "cluster": int(labels[i]),
        })
    (OUT / "_assignments.json").write_text(
        json.dumps(assigns, separators=(",", ":")), encoding="utf-8")

    print(f"\nwrote outputs to {OUT}")


if __name__ == "__main__":
    main()
