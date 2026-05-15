#!/usr/bin/env python3
"""Create blob-level refinements for mixed dot-like clusters.

The cluster-level assignment file cannot represent internal mixing. This script
keeps the coarse cluster map intact and writes per-blob labels for clusters that
are mostly lacuna dots but contain strokes, wide marks, printed-text debris, or
other mixed residue.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CLUSTERS_DIR = REPO / "output" / "projects" / "kephalaia_ocr" / "clusters"
OUT_PATH = CLUSTERS_DIR / "_dot_cluster_refinements.json"

DEFAULT_CLUSTERS = [2, 34, 35, 46]

LABEL_BY_BUCKET = {
    "tiny_dot": "_lacuna_dot",
    "dot_like": "_lacuna_dot",
    "tall_stroke": "_dot_cluster_tall_stroke",
    "wide_mark": "_dot_cluster_wide_mark",
    "other_mixed": "_unknown",
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def bbox_shape(item: dict) -> tuple[int, int]:
    x0, y0, x1, y1 = item["warped_bbox"]
    return int(x1 - x0 + 1), int(y1 - y0 + 1)


def bucket_for(item: dict) -> str:
    width, height = bbox_shape(item)
    if width <= 4 and height <= 5:
        return "tiny_dot"
    if width <= 6 and height <= 8:
        return "dot_like"
    if width <= 8 and height >= 14:
        return "tall_stroke"
    if width >= 10 and height <= 10:
        return "wide_mark"
    return "other_mixed"


def refine(clusters: list[int]) -> dict:
    assignments = load_json(CLUSTERS_DIR / "_assignments.json")
    selected = {int(cluster) for cluster in clusters}
    summary: dict[str, dict] = {}
    overrides = []
    bucket_counts_by_cluster: dict[int, Counter] = defaultdict(Counter)
    label_counts_by_cluster: dict[int, Counter] = defaultdict(Counter)

    for item in assignments:
        cluster = int(item["cluster"])
        if cluster not in selected:
            continue
        bucket = bucket_for(item)
        label = LABEL_BY_BUCKET[bucket]
        bucket_counts_by_cluster[cluster][bucket] += 1
        label_counts_by_cluster[cluster][label] += 1
        width, height = bbox_shape(item)
        overrides.append({
            "page": str(item["page"]),
            "line_index": int(item["line_index"]),
            "blob_id": int(item["blob_id"]),
            "cluster": f"{cluster:02d}",
            "bucket": bucket,
            "label": label,
            "warped_bbox": item["warped_bbox"],
            "width": width,
            "height": height,
        })

    for cluster in sorted(selected):
        bucket_counts = bucket_counts_by_cluster[cluster]
        label_counts = label_counts_by_cluster[cluster]
        total = sum(bucket_counts.values())
        summary[f"{cluster:02d}"] = {
            "total": total,
            "buckets": dict(bucket_counts),
            "labels": dict(label_counts),
            "lacuna_dot_fraction": (label_counts.get("_lacuna_dot", 0) / total) if total else 0.0,
        }

    return {
        "description": "Blob-level refinements for internally mixed dot-like clusters.",
        "rules": {
            "tiny_dot": "width <= 4 and height <= 5",
            "dot_like": "width <= 6 and height <= 8",
            "tall_stroke": "width <= 8 and height >= 14",
            "wide_mark": "width >= 10 and height <= 10",
            "other_mixed": "fallback bucket",
        },
        "label_by_bucket": LABEL_BY_BUCKET,
        "summary": summary,
        "overrides": overrides,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("clusters", nargs="*", type=int, default=DEFAULT_CLUSTERS)
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    args = parser.parse_args()
    result = refine(args.clusters)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(args.out)
    for cluster, data in result["summary"].items():
        print(cluster, data)


if __name__ == "__main__":
    main()