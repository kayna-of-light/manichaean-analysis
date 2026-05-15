#!/usr/bin/env python3
"""Project reviewed labels onto a body-crop recluster.

This is for the main base-blob cluster layer after body crop changes. Cluster ids
can change, but most reviewed knowledge can be carried forward from unchanged
(page, line_index, blob_id) evidence. Subcluster/geometric rules tied to old
cluster ids are preserved as exact reviewed override effects when they cannot be
safely re-bound to the new cluster ids.
"""

from __future__ import annotations

import argparse
import json
import math
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
OCR_ROOT = REPO / "output" / "projects" / "kephalaia_ocr"
DEFAULT_OLD_CLUSTERS = OCR_ROOT / "clusters_shape_padded_k120"
DEFAULT_NEW_CLUSTERS = OCR_ROOT / "clusters_shape_padded_k120_bodycrop_test"
EXCLUDED_SOURCE_LABELS = {"?", "_mixed_character"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_repo_path(value: str | None, default: Path) -> Path:
    if value is None:
        return default
    path = Path(value)
    return path if path.is_absolute() else REPO / path


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO)).replace("\\", "/")
    except ValueError:
        return str(path)


def cluster_key(value: str | int) -> str:
    return f"{int(value):03d}"


def stable_key(item: dict[str, Any]) -> tuple[str, int, int]:
    return (str(item["page"]), int(item["line_index"]), int(item["blob_id"]))


def bbox_center(bbox: list[int]) -> tuple[float, float]:
    return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)


def bbox_size(bbox: list[int]) -> tuple[int, int]:
    return (bbox[2] - bbox[0] + 1, bbox[3] - bbox[1] + 1)


def is_coptic_base(char: str) -> bool:
    code = ord(char)
    return 0x2C80 <= code <= 0x2CFF or 0x03E2 <= code <= 0x03EF


def coptic_base_len(value: str | None) -> int:
    if not value or not isinstance(value, str) or value.startswith("_"):
        return 0
    return sum(1 for char in unicodedata.normalize("NFD", value) if is_coptic_base(char))


def load_old_cluster_projection(old_dir: Path) -> tuple[dict[str, str], dict[str, dict[str, Any]], dict[str, Any]]:
    data = load_json(old_dir / "_char_assignments_projected.json")
    assignments = data.get("assignments", data)
    reverse: dict[str, str] = {}
    for label, clusters in assignments.items():
        if label in EXCLUDED_SOURCE_LABELS:
            continue
        for cluster in clusters:
            reverse[cluster_key(cluster)] = str(label)
    review = {cluster_key(row["cluster"]): row for row in data.get("review_clusters", [])}
    return reverse, review, data.get("_metadata", {})


def load_old_blob_labels(old_dir: Path, reverse: dict[str, str]) -> dict[tuple[str, int, int], str]:
    labels: dict[tuple[str, int, int], str] = {}
    for item in load_json(old_dir / "_assignments.json"):
        label = reverse.get(cluster_key(item["cluster"]))
        if label:
            labels[stable_key(item)] = label
    return labels


def load_old_review_evidence(old_dir: Path, old_review: dict[str, dict[str, Any]]) -> dict[tuple[str, int, int], list[list[Any]]]:
    evidence: dict[tuple[str, int, int], list[list[Any]]] = {}
    for item in load_json(old_dir / "_assignments.json"):
        cluster = cluster_key(item["cluster"])
        row = old_review.get(cluster)
        if row:
            evidence[stable_key(item)] = row.get("top", [])
    return evidence


def load_subcluster_override_effects(old_dir: Path) -> dict[tuple[str, int, int], dict[str, Any]]:
    effects: dict[tuple[str, int, int], dict[str, Any]] = {}
    subcluster_root = old_dir / "subclusters"
    if not subcluster_root.exists():
        return effects
    for label_path in sorted(subcluster_root.glob("*/_subcluster_labels.json")):
        assignment_path = label_path.parent / "_subassignments.json"
        if not assignment_path.exists():
            continue
        label_data = load_json(label_path)
        labels = label_data.get("labels", {})
        for item in load_json(assignment_path):
            subcluster = str(item["subcluster"]).zfill(2)
            metadata = labels.get(subcluster)
            if not metadata or not metadata.get("label"):
                continue
            key = stable_key(item)
            effects[key] = {
                "label": metadata["label"],
                "confidence": metadata.get("confidence", "reviewed_subcluster"),
                "evidence": metadata.get("evidence", ""),
                "source": relative(label_path),
                "old_cluster": cluster_key(item.get("cluster", 0)),
                "old_subcluster": subcluster,
                "migration": "old_subcluster_effect_preserved_by_stable_blob_key",
            }
    return effects


def range_contains(value: float, bounds: list[float] | None) -> bool:
    if not bounds:
        return True
    return float(bounds[0]) <= value <= float(bounds[1])


def load_geometric_override_effects(old_dir: Path) -> dict[tuple[str, int, int], dict[str, Any]]:
    path = old_dir / "_geometric_glyph_overrides.json"
    if not path.exists():
        return {}
    config = load_json(path)
    effects: dict[tuple[str, int, int], dict[str, Any]] = {}
    for rule in config.get("rules", []):
        label = rule.get("label")
        subassignments_value = rule.get("subassignments")
        if not label or not subassignments_value:
            continue
        subassignments_path = Path(str(subassignments_value))
        if not subassignments_path.is_absolute():
            subassignments_path = old_dir / subassignments_path
        if not subassignments_path.exists():
            continue
        cluster = cluster_key(rule.get("cluster", 0)) if rule.get("cluster") is not None else None
        subcluster = str(rule.get("subcluster", "")).zfill(2) if rule.get("subcluster") is not None else None
        geometry = rule.get("geometry", {}) or {}
        for item in load_json(subassignments_path):
            item_cluster = cluster_key(item.get("cluster", 0))
            item_subcluster = str(item.get("subcluster", "")).zfill(2)
            if cluster and item_cluster != cluster:
                continue
            if subcluster and item_subcluster != subcluster:
                continue
            bbox = [int(value) for value in item.get("warped_bbox", [])]
            if len(bbox) != 4:
                continue
            width = float(item.get("width", bbox[2] - bbox[0] + 1))
            height = float(item.get("height", bbox[3] - bbox[1] + 1))
            center_y = (bbox[1] + bbox[3]) / 2.0
            if not range_contains(width, geometry.get("width")):
                continue
            if not range_contains(height, geometry.get("height")):
                continue
            if not range_contains(center_y, geometry.get("center_y")):
                continue
            effects[stable_key(item)] = {
                "label": label,
                "confidence": rule.get("confidence", "geometric_reviewed"),
                "evidence": rule.get("evidence", ""),
                "source": relative(path),
                "old_rule_id": rule.get("id"),
                "old_cluster": item_cluster,
                "old_subcluster": item_subcluster,
                "migration": "old_geometric_rule_effect_preserved_by_stable_blob_key",
            }
    return effects


def copy_manual_overrides(old_dir: Path) -> list[dict[str, Any]]:
    path = old_dir / "_manual_glyph_overrides.json"
    if not path.exists():
        return []
    return list(load_json(path).get("overrides", []))


def copy_editorial_overrides(old_dir: Path) -> dict[str, Any]:
    path = old_dir / "_editorial_word_overrides.json"
    if not path.exists():
        return {"description": "No prior editorial overrides found.", "overrides": []}
    return load_json(path)


def effect_is_small_mark(effect: dict[str, Any]) -> bool:
    return str(effect.get("label") or "").startswith("_")


def closest_same_line_effect_target(
    effect: dict[str, Any],
    old_by_key: dict[tuple[str, int, int], dict[str, Any]],
    new_by_line: dict[tuple[str, int], list[dict[str, Any]]],
) -> tuple[tuple[str, int, int], dict[str, Any], float] | None:
    old_key = (str(effect["page"]), int(effect["line_index"]), int(effect["blob_id"]))
    old_item = old_by_key.get(old_key)
    if not old_item:
        return None
    old_bbox = [int(value) for value in old_item.get("warped_bbox", [])]
    if len(old_bbox) != 4:
        return None

    old_center = bbox_center(old_bbox)
    old_size = bbox_size(old_bbox)
    candidates: list[tuple[float, float, int, dict[str, Any]]] = []
    for new_item in new_by_line.get((old_key[0], old_key[1]), []):
        new_bbox = [int(value) for value in new_item.get("warped_bbox", [])]
        if len(new_bbox) != 4:
            continue
        new_center = bbox_center(new_bbox)
        new_size = bbox_size(new_bbox)
        distance = math.hypot(new_center[0] - old_center[0], new_center[1] - old_center[1])
        size_delta = abs(new_size[0] - old_size[0]) + abs(new_size[1] - old_size[1])
        score = distance + size_delta * 0.75
        candidates.append((score, distance, size_delta, new_item))
    if not candidates:
        return None
    score, distance, size_delta, new_item = min(candidates, key=lambda row: row[0])

    if effect_is_small_mark(effect):
        if score > 10.0 or distance > 10.0 or size_delta > 3:
            return None
    elif score > 12.0 or distance > 8.0 or size_delta > 4:
        return None

    new_key = stable_key(new_item)
    return new_key, new_item, score


def project(args: argparse.Namespace) -> dict[str, Any]:
    old_dir = resolve_repo_path(args.old_clusters, DEFAULT_OLD_CLUSTERS)
    new_dir = resolve_repo_path(args.new_clusters, DEFAULT_NEW_CLUSTERS)
    old_reverse, old_review, old_metadata = load_old_cluster_projection(old_dir)
    old_blob_labels = load_old_blob_labels(old_dir, old_reverse)
    old_review_evidence = load_old_review_evidence(old_dir, old_review)
    new_assignments = load_json(new_dir / "_assignments.json")

    assigned_evidence_by_cluster: dict[str, Counter[str]] = defaultdict(Counter)
    review_evidence_by_cluster: dict[str, Counter[str]] = defaultdict(Counter)
    key_matches = 0
    review_key_matches = 0
    for item in new_assignments:
        key = stable_key(item)
        new_cluster = cluster_key(item["cluster"])
        label = old_blob_labels.get(key)
        if label:
            assigned_evidence_by_cluster[new_cluster][label] += 1
            key_matches += 1
        for old_label, count in old_review_evidence.get(key, []):
            review_evidence_by_cluster[new_cluster][str(old_label)] += int(count)
            review_key_matches += 1

    label_assignments: dict[str, list[str]] = defaultdict(list)
    review_clusters: list[dict[str, Any]] = []
    cluster_labels: dict[str, dict[str, Any]] = {}
    all_clusters = sorted({cluster_key(item["cluster"]) for item in new_assignments}, key=int)
    for cluster in all_clusters:
        assigned_counts = assigned_evidence_by_cluster.get(cluster, Counter())
        review_counts = review_evidence_by_cluster.get(cluster, Counter())
        assigned_total = sum(assigned_counts.values())
        if assigned_counts:
            label, count = assigned_counts.most_common(1)[0]
            purity = count / max(assigned_total, 1)
            if assigned_total >= args.min_evidence and purity >= args.purity:
                label_assignments[label].append(cluster)
                cluster_labels[cluster] = {
                    "label": label,
                    "confidence": "strong_projected_from_prior_reviewed_clusters",
                    "evidence_total": assigned_total,
                    "purity": round(purity, 4),
                    "top": assigned_counts.most_common(8),
                }
                continue
            if assigned_total >= args.weak_min_evidence and purity >= args.weak_purity and args.include_weak:
                label_assignments[label].append(cluster)
                cluster_labels[cluster] = {
                    "label": label,
                    "confidence": "weak_projected_from_prior_reviewed_clusters",
                    "evidence_total": assigned_total,
                    "purity": round(purity, 4),
                    "top": assigned_counts.most_common(8),
                }
                continue
        merged_review = Counter(review_counts)
        for label, count in assigned_counts.items():
            merged_review[label] += count
        if merged_review:
            review_clusters.append({
                "cluster": cluster,
                "total": int(sum(merged_review.values())),
                "top": [[label, int(count)] for label, count in merged_review.most_common(12)],
                "source": "projected_from_prior_assigned_and_review_cluster_evidence",
            })
            cluster_labels[cluster] = {
                "label": None,
                "confidence": "projected_review_cluster",
                "assigned_evidence_total": assigned_total,
                "review_evidence_total": sum(review_counts.values()),
                "top": merged_review.most_common(8),
            }
        else:
            cluster_labels[cluster] = {
                "label": None,
                "confidence": "no_prior_stable_blob_evidence",
                "evidence_total": 0,
                "top": [],
            }

    subcluster_effects = load_subcluster_override_effects(old_dir)
    geometric_effects = load_geometric_override_effects(old_dir)
    new_keys = {stable_key(item) for item in new_assignments}
    old_by_key = {stable_key(item): item for item in load_json(old_dir / "_assignments.json")}
    new_by_line: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for item in new_assignments:
        new_by_line[(str(item["page"]), int(item["line_index"]))].append(item)
    preserved_manual_overrides = copy_manual_overrides(old_dir)
    migrated_effects: list[dict[str, Any]] = []
    missing_effects: list[dict[str, Any]] = []
    recovered_effects: list[dict[str, Any]] = []
    for key, metadata in {**subcluster_effects, **geometric_effects}.items():
        row = {
            "page": key[0],
            "line_index": key[1],
            "blob_id": key[2],
            "label": metadata["label"],
            "confidence": metadata.get("confidence", "reviewed_migrated"),
            "evidence": metadata.get("evidence", ""),
            "source": metadata.get("source", "prior_review"),
            "migration": metadata.get("migration", "prior_review_effect_preserved_by_stable_blob_key"),
            "old_cluster": metadata.get("old_cluster"),
            "old_subcluster": metadata.get("old_subcluster"),
            "old_rule_id": metadata.get("old_rule_id"),
        }
        if key in new_keys:
            migrated_effects.append(row)
            continue
        recovered = closest_same_line_effect_target(row, old_by_key, new_by_line)
        if recovered is None:
            missing_effects.append(row)
            continue
        recovered_key, recovered_item, recovered_score = recovered
        recovered_row = dict(row)
        recovered_row.update({
            "line_index": recovered_key[1],
            "blob_id": recovered_key[2],
            "migration": f"{row['migration']}; recovered_by_same_line_geometry",
            "old_blob_id": row["blob_id"],
            "new_cluster": cluster_key(recovered_item["cluster"]),
            "geometry_recovery_score": round(float(recovered_score), 4),
        })
        migrated_effects.append(recovered_row)
        recovered_effects.append(recovered_row)
    manual_output = {
        "description": "Manual and migrated exact reviewed glyph effects for the body-crop recluster. Cluster/subcluster rules from the prior cluster set are preserved here only when re-binding by cluster id would be unsafe.",
        "overrides": preserved_manual_overrides + migrated_effects,
        "migration_summary": {
            "manual_overrides_copied": len(preserved_manual_overrides),
            "review_effects_preserved": len(migrated_effects),
            "review_effects_recovered_by_geometry": len(recovered_effects),
            "review_effects_missing_stable_key": len(missing_effects),
            "missing_effects": missing_effects,
            "recovered_effects": recovered_effects,
        },
    }
    editorial_output = copy_editorial_overrides(old_dir)
    return {
        "projection": {
            "_metadata": {
                "source": "Projected from prior reviewed cluster labels after body-crop reclustering.",
                "old_clusters": relative(old_dir),
                "new_clusters": relative(new_dir),
                "old_metadata": old_metadata,
                "parameters": {
                    "purity": args.purity,
                    "min_evidence": args.min_evidence,
                    "weak_purity": args.weak_purity,
                    "weak_min_evidence": args.weak_min_evidence,
                    "include_weak": args.include_weak,
                },
                "stable_key_matches": key_matches,
                "stable_review_key_matches": review_key_matches,
                "n_review_clusters": len(review_clusters),
            },
            "assignments": {label: sorted(clusters, key=int) for label, clusters in sorted(label_assignments.items())},
            "review_clusters": sorted(review_clusters, key=lambda row: int(row["cluster"])),
            "cluster_labels": cluster_labels,
        },
        "manual_overrides": manual_output,
        "editorial_overrides": editorial_output,
        "summary": {
            "assigned_cluster_count": sum(len(value) for value in label_assignments.values()),
            "review_cluster_count": len(review_clusters),
            "stable_key_matches": key_matches,
            "stable_review_key_matches": review_key_matches,
            "migrated_review_effects": len(migrated_effects),
            "geometry_recovered_review_effects": len(recovered_effects),
            "missing_review_effects": len(missing_effects),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-clusters", default=None)
    parser.add_argument("--new-clusters", default=None)
    parser.add_argument("--purity", type=float, default=0.90)
    parser.add_argument("--min-evidence", type=int, default=20)
    parser.add_argument("--weak-purity", type=float, default=0.75)
    parser.add_argument("--weak-min-evidence", type=int, default=8)
    parser.add_argument("--include-weak", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    new_dir = resolve_repo_path(args.new_clusters, DEFAULT_NEW_CLUSTERS)
    result = project(args)
    write_json(new_dir / "_char_assignments_projected.json", result["projection"])
    write_json(new_dir / "_manual_glyph_overrides.json", result["manual_overrides"])
    write_json(new_dir / "_editorial_word_overrides.json", result["editorial_overrides"])
    print(new_dir / "_char_assignments_projected.json")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
