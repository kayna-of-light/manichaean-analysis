#!/usr/bin/env python3
"""Apply reviewed subcluster labels to character-cluster refinements.

This turns `_character_cluster_refinements.json` into a conservative labeled
overlay. Coarse cluster labels stay coarse; mixed clusters get blob-level labels
only where the visual subcluster label is strong.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CLUSTERS_DIR = REPO / "output" / "projects" / "kephalaia_ocr" / "clusters"
REFINEMENT_PATH = CLUSTERS_DIR / "_character_cluster_refinements.json"
OUT_PATH = CLUSTERS_DIR / "_character_cluster_refinements_labeled.json"
SUBCLUSTER_DIR = CLUSTERS_DIR / "subclusters" / "c32_tall_k06"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def blob_key(item: dict) -> tuple[str, int, int]:
    return (str(item["page"]), int(item["line_index"]), int(item["blob_id"]))


def load_c32_tall_labels() -> dict[tuple[str, int, int], dict]:
    subassignments = load_json(SUBCLUSTER_DIR / "_subassignments.json")
    label_map = load_json(SUBCLUSTER_DIR / "_subcluster_labels.json")
    labels = label_map["labels"]
    resolved = {}
    for item in subassignments:
        subcluster = str(item["subcluster"]).zfill(2)
        metadata = labels.get(subcluster, {
            "label": "_unlabeled_subcluster",
            "confidence": "needs_review",
            "notes": "No manual label assigned.",
        })
        resolved[blob_key(item)] = {
            "subcluster": subcluster,
            "label": metadata["label"],
            "confidence": metadata.get("confidence", "needs_review"),
            "candidate_labels": metadata.get("candidate_labels", []),
            "notes": metadata.get("notes", ""),
        }
    return resolved


def apply_labels() -> dict:
    refinement = load_json(REFINEMENT_PATH)
    c32_tall = load_c32_tall_labels()
    overrides = []
    label_counts: Counter = Counter()
    confidence_counts: Counter = Counter()
    bucket_counts: Counter = Counter()

    for item in refinement["overrides"]:
        labeled = dict(item)
        bucket = item.get("bucket")
        if item.get("cluster") == "32" and bucket == "tall_mixed_candidate":
            metadata = c32_tall.get(blob_key(item), {
                "subcluster": None,
                "label": "_unresolved_tall_mixed",
                "confidence": "needs_review",
                "candidate_labels": [],
                "notes": "Tall mixed form missing from subcluster assignments.",
            })
            labeled.update({
                "subcluster": metadata["subcluster"],
                "label": metadata["label"],
                "confidence": metadata["confidence"],
                "candidate_labels": metadata["candidate_labels"],
                "notes": metadata["notes"],
            })
        else:
            labeled["confidence"] = "strong" if labeled.get("label") in {"ⲑ", "_multi_char_connected"} else "needs_review"
            labeled.setdefault("candidate_labels", [])
            labeled.setdefault("notes", "")
        overrides.append(labeled)
        label_counts[labeled["label"]] += 1
        confidence_counts[labeled["confidence"]] += 1
        bucket_counts[bucket] += 1

    return {
        "description": "Conservative blob-level labels after applying reviewed subcluster labels.",
        "source_refinement": str(REFINEMENT_PATH.relative_to(REPO)),
        "subcluster_label_sources": [str((SUBCLUSTER_DIR / "_subcluster_labels.json").relative_to(REPO))],
        "summary": {
            "labels": dict(label_counts),
            "confidence": dict(confidence_counts),
            "buckets": dict(bucket_counts),
        },
        "overrides": overrides,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    args = parser.parse_args()
    result = apply_labels()
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(args.out)
    print(json.dumps(result["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()