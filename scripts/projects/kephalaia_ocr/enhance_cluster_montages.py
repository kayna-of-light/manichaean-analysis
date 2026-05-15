#!/usr/bin/env python3
"""Create high-contrast diagnostic copies of cluster montage PNGs."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[3]
CLUSTERS_DIR = REPO / "output" / "projects" / "kephalaia_ocr" / "clusters"


def enhance_cluster(cluster_id: int, out_dir: Path, threshold: int) -> Path:
    matches = sorted(CLUSTERS_DIR.glob(f"c_{cluster_id:02d}_n*.png"))
    if not matches:
        raise FileNotFoundError(f"No montage found for cluster {cluster_id:02d}")
    src = matches[0]
    img = cv2.imread(str(src), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise RuntimeError(f"Could not read {src}")
    mask = img < threshold
    enhanced = np.full_like(img, 255)
    enhanced[mask] = 0
    rgb = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / src.name
    cv2.imwrite(str(out), rgb)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("clusters", nargs="+", type=int)
    parser.add_argument("--threshold", type=int, default=252)
    args = parser.parse_args()

    name = f"enhanced_clusters_{args.clusters[0]:02d}_{args.clusters[-1]:02d}"
    out_dir = CLUSTERS_DIR / "context_sheets" / name
    for cluster_id in args.clusters:
        enhance_cluster(cluster_id, out_dir, args.threshold)
    print(out_dir)


if __name__ == "__main__":
    main()
