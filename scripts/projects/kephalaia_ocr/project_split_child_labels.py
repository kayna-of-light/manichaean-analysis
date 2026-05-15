#!/usr/bin/env python3
"""Project labels onto a split-derived cluster set.

The split cluster run changes cluster ids, so labels must be re-derived from
unchanged blob identities. For each new cluster, this script counts labels from
unchanged original blobs whose old clusters already had a projected single-glyph
label. Split children are then classified by their new cluster label and compared
against `split_expected_base` only as a witness check.
"""

from __future__ import annotations

import argparse
import json
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
OCR_ROOT = REPO / "output" / "projects" / "kephalaia_ocr"
DEFAULT_OLD_CLUSTERS = OCR_ROOT / "clusters_shape_padded_k120"
DEFAULT_NEW_CLUSTERS = OCR_ROOT / "clusters_shape_padded_split_k120"

EXCLUDED_SOURCE_LABELS = {"?", "_mixed_character", "_multi_char_connected", "_connected_needs_literal_reading"}
SPECIAL_PROJECTABLE_LABELS = {
    "_lacuna_dot",
    "_middle_dot",
    "_unknown",
    "_left_square_bracket",
    "_right_square_bracket",
    "_editorial_marker",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
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


def is_coptic_base(char: str) -> bool:
    code = ord(char)
    return 0x2C80 <= code <= 0x2CFF or 0x03E2 <= code <= 0x03EF


def coptic_base_len(value: str | None) -> int:
    if not value or not isinstance(value, str) or value.startswith("_"):
        return 0
    return sum(1 for char in unicodedata.normalize("NFD", value) if is_coptic_base(char))


def coptic_bases(value: str | None) -> list[str]:
    if not value or not isinstance(value, str) or value.startswith("_"):
        return []
    return [char for char in unicodedata.normalize("NFD", value) if is_coptic_base(char)]


def is_projectable_cluster_label(label: str | None) -> bool:
    if not label or not isinstance(label, str) or label in EXCLUDED_SOURCE_LABELS:
        return False
    if label in SPECIAL_PROJECTABLE_LABELS:
        return True
    return coptic_base_len(label) == 1


def is_exact_blob_label(label: str | None) -> bool:
    if not label or not isinstance(label, str) or label in {"?", "_mixed_character"}:
        return False
    return bool(label.startswith("_") or coptic_bases(label))


def stable_key(item: dict[str, Any]) -> tuple[str, int, int]:
    return (str(item["page"]), int(item["line_index"]), int(item["blob_id"]))


def load_old_cluster_labels(old_dir: Path) -> dict[str, str]:
    data = load_json(old_dir / "_char_assignments_projected.json")
    assignments = data.get("assignments", data)
    reverse: dict[str, str] = {}
    for label, clusters in assignments.items():
        if not is_projectable_cluster_label(str(label)):
            continue
        for cluster in clusters:
            reverse[cluster_key(cluster)] = str(label)
    return reverse


def load_old_review_clusters(old_dir: Path) -> dict[str, dict[str, Any]]:
    data = load_json(old_dir / "_char_assignments_projected.json")
    return {cluster_key(row["cluster"]): row for row in data.get("review_clusters", [])}


def load_old_blob_clusters(old_dir: Path) -> dict[tuple[str, int, int], str]:
    return {stable_key(item): cluster_key(item["cluster"]) for item in load_json(old_dir / "_assignments.json")}


def scaled_review_counts(review_item: dict[str, Any], scale: int = 1000) -> Counter[str]:
    total = max(1, int(review_item.get("total") or sum(int(count) for _label, count in review_item.get("top", []))))
    counts: Counter[str] = Counter()
    for label, count in review_item.get("top", []):
        if not is_exact_blob_label(str(label)) and str(label) not in {"_connected_needs_literal_reading", "_multi_char_connected"}:
            continue
        counts[str(label)] += max(1, int(round((int(count) / total) * scale)))
    return counts


def old_blob_labels(old_dir: Path, old_cluster_labels: dict[str, str]) -> dict[tuple[str, int, int], dict[str, Any]]:
    labels: dict[tuple[str, int, int], dict[str, Any]] = {}
    for item in load_json(old_dir / "_assignments.json"):
        label = old_cluster_labels.get(cluster_key(item["cluster"]))
        if label:
            labels[stable_key(item)] = {
                "label": label,
                "confidence": "old_projected_cluster",
                "source": relative(old_dir / "_char_assignments_projected.json"),
                "old_cluster": cluster_key(item["cluster"]),
            }
    return labels


def overlay_manual_blob_labels(old_dir: Path, labels: dict[tuple[str, int, int], dict[str, Any]]) -> None:
    path = old_dir / "_manual_glyph_overrides.json"
    if not path.exists():
        return
    for row in load_json(path).get("overrides", []):
        label = row.get("label")
        if not is_exact_blob_label(label):
            continue
        key = (str(row["page"]), int(row["line_index"]), int(row["blob_id"]))
        labels[key] = dict(row, source=row.get("source") or relative(path))


def overlay_subcluster_blob_labels(old_dir: Path, labels: dict[tuple[str, int, int], dict[str, Any]]) -> None:
    subcluster_root = old_dir / "subclusters"
    if not subcluster_root.exists():
        return
    for label_path in sorted(subcluster_root.glob("*/_subcluster_labels.json")):
        assignment_path = label_path.parent / "_subassignments.json"
        if not assignment_path.exists():
            continue
        label_data = load_json(label_path)
        subcluster_labels = label_data.get("labels", {})
        for item in load_json(assignment_path):
            subcluster = str(item["subcluster"]).zfill(2)
            metadata = subcluster_labels.get(subcluster)
            if not metadata or not is_exact_blob_label(metadata.get("label")):
                continue
            key = stable_key(item)
            labels[key] = {
                "label": str(metadata["label"]),
                "confidence": metadata.get("confidence", "needs_review"),
                "evidence": metadata.get("evidence", ""),
                "source": relative(label_path),
                "old_cluster": cluster_key(item.get("cluster", 0)),
                "old_subcluster": subcluster,
            }


def overlay_editorial_blob_labels(old_dir: Path, labels: dict[tuple[str, int, int], dict[str, Any]]) -> None:
    path = old_dir / "_editorial_word_overrides.json"
    if not path.exists():
        return
    for row in load_json(path).get("overrides", []):
        page = str(row["page"])
        line_index = int(row["line_index"])
        blob_ids = [int(blob_id) for blob_id in row.get("blob_ids", [])]
        display_chars = [str(char) for char in row.get("display_chars", [])]
        for position, blob_id in enumerate(blob_ids):
            metadata = dict(row)
            metadata["label"] = row.get("label") or "_editorial_marker"
            metadata["source"] = row.get("source") or relative(path)
            metadata["span_position"] = position
            metadata["span_count"] = len(blob_ids)
            if position < len(display_chars):
                metadata["display_text"] = display_chars[position]
            labels[(page, line_index, blob_id)] = metadata


def load_old_blob_label_metadata(old_dir: Path, old_cluster_labels: dict[str, str]) -> dict[tuple[str, int, int], dict[str, Any]]:
    labels = old_blob_labels(old_dir, old_cluster_labels)
    overlay_manual_blob_labels(old_dir, labels)
    overlay_subcluster_blob_labels(old_dir, labels)
    overlay_editorial_blob_labels(old_dir, labels)
    return labels


def expected_base_from_parent(item: dict[str, Any], old_labels_by_blob: dict[tuple[str, int, int], dict[str, Any]]) -> str | None:
    expected_base = item.get("split_expected_base")
    if expected_base and coptic_base_len(str(expected_base)) == 1:
        return str(expected_base)
    parent_id = item.get("parent_blob_id")
    if parent_id is None:
        return None
    parent_key = (str(item["page"]), int(item["line_index"]), int(parent_id))
    parent = old_labels_by_blob.get(parent_key)
    bases = coptic_bases((parent or {}).get("label"))
    child_index = int(item.get("split_child_index", -1))
    if 0 <= child_index < len(bases):
        return bases[child_index]
    return None


def split_child_override_row(item: dict[str, Any], label: str, source: str) -> dict[str, Any]:
    reason = str(item.get("split_reason") or "")
    confidence = "split_child_from_reviewed_parent" if reason == "already_multi_char_label" else "split_child_from_expected_text"
    return {
        "page": str(item["page"]),
        "line_index": int(item["line_index"]),
        "blob_id": int(item["blob_id"]),
        "label": label,
        "confidence": confidence,
        "evidence": f"Split child {item.get('split_child_index')} of parent blob {item.get('parent_blob_id')} from {item.get('split_expected_text')!r}.",
        "source": source,
        "parent_blob_id": int(item["parent_blob_id"]),
        "split_child_index": int(item.get("split_child_index", 0)),
        "split_child_count": int(item.get("split_child_count", 1)),
        "split_expected_text": item.get("split_expected_text"),
        "split_reason": item.get("split_reason"),
        "split_confidence": item.get("split_confidence"),
    }


def carried_blob_override_row(item: dict[str, Any], metadata: dict[str, Any], assigned_cluster_label: str | None) -> dict[str, Any]:
    return {
        "page": str(item["page"]),
        "line_index": int(item["line_index"]),
        "blob_id": int(item["blob_id"]),
        "label": str(metadata["label"]),
        "confidence": metadata.get("confidence", "carried_from_old_stable_blob"),
        "evidence": metadata.get("evidence", "Carried by stable page/line/blob identity from preserved parent body-crop cluster stack."),
        "source": metadata.get("source"),
        "migration": "old_stable_blob_label_carried_into_split_stack",
        "old_cluster": metadata.get("old_cluster"),
        "old_subcluster": metadata.get("old_subcluster"),
        "new_cluster": cluster_key(item["cluster"]),
        "new_cluster_label": assigned_cluster_label,
    }


def review_cluster_rows(
    cluster_labels: dict[str, dict[str, Any]],
    carried_review_evidence_by_cluster: dict[str, Counter[str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cluster, metadata in sorted(cluster_labels.items(), key=lambda item: int(item[0])):
        if metadata.get("label"):
            continue
        counts = Counter(dict(metadata.get("top") or metadata.get("unchanged_top") or metadata.get("reviewed_connected_top") or []))
        counts.update(carried_review_evidence_by_cluster.get(cluster, Counter()))
        if not counts:
            continue
        top = counts.most_common(10)
        count_total = sum(int(count) for count in counts.values())
        rows.append({
            "cluster": cluster,
            "total": count_total,
            "top": top,
            "source": "split_projection_mixed_or_low_purity_evidence",
            "confidence": metadata.get("confidence"),
            "unchanged_evidence_total": int(metadata.get("unchanged_evidence_total") or 0),
            "reviewed_connected_total": int(metadata.get("reviewed_connected_total") or 0),
            "purity": metadata.get("purity"),
        })
    return rows


def load_split_subcluster_labels(new_dir: Path) -> dict[tuple[str, int, int], dict[str, Any]]:
    labels_by_blob: dict[tuple[str, int, int], dict[str, Any]] = {}
    subcluster_root = new_dir / "subclusters"
    if not subcluster_root.exists():
        return labels_by_blob
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
            labels_by_blob[stable_key(item)] = {
                "label": str(metadata["label"]),
                "confidence": metadata.get("confidence", "needs_review"),
                "evidence": metadata.get("evidence", ""),
                "source": relative(label_path),
                "cluster": cluster_key(item.get("cluster", 0)),
                "subcluster": subcluster,
            }
    return labels_by_blob


def project(args: argparse.Namespace) -> dict[str, Any]:
    old_dir = resolve_repo_path(args.old_clusters, DEFAULT_OLD_CLUSTERS)
    new_dir = resolve_repo_path(args.new_clusters, DEFAULT_NEW_CLUSTERS)
    old_cluster_labels = load_old_cluster_labels(old_dir)
    old_review_clusters = load_old_review_clusters(old_dir)
    old_blob_clusters = load_old_blob_clusters(old_dir)
    old_labels_by_blob = load_old_blob_label_metadata(old_dir, old_cluster_labels)
    new_assignments = load_json(new_dir / "_assignments.json")
    split_subcluster_labels = load_split_subcluster_labels(new_dir) if args.use_subcluster_labels else {}

    unchanged_evidence_by_cluster: dict[str, Counter[str]] = defaultdict(Counter)
    reviewed_child_evidence_by_cluster: dict[str, Counter[str]] = defaultdict(Counter)
    carried_review_evidence_by_cluster: dict[str, Counter[str]] = defaultdict(Counter)
    split_children: list[dict[str, Any]] = []
    unchanged_items: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for item in new_assignments:
        new_cluster = cluster_key(item["cluster"])
        if "parent_blob_id" in item:
            split_children.append(item)
            expected_base = expected_base_from_parent(item, old_labels_by_blob)
            if expected_base and coptic_base_len(expected_base) == 1:
                if args.use_split_expected_evidence:
                    reviewed_child_evidence_by_cluster[new_cluster][expected_base] += 1
            continue
        old_label = old_labels_by_blob.get(stable_key(item))
        label = (old_label or {}).get("label")
        if old_label and is_exact_blob_label(label):
            unchanged_items.append((item, old_label))
        if is_projectable_cluster_label(label):
            unchanged_evidence_by_cluster[new_cluster][label] += 1
        else:
            old_cluster = old_blob_clusters.get(stable_key(item))
            review_item = old_review_clusters.get(old_cluster or "")
            if review_item:
                carried_review_evidence_by_cluster[new_cluster].update(scaled_review_counts(review_item))

    cluster_labels: dict[str, dict[str, Any]] = {}
    label_assignments: dict[str, list[str]] = defaultdict(list)
    for cluster in sorted({cluster_key(item["cluster"]) for item in new_assignments}):
        unchanged_counts = unchanged_evidence_by_cluster.get(cluster, Counter())
        reviewed_counts = reviewed_child_evidence_by_cluster.get(cluster, Counter())
        unchanged_total = sum(unchanged_counts.values())
        unchanged_top = unchanged_counts.most_common(1)[0] if unchanged_counts else (None, 0)
        unchanged_purity = unchanged_top[1] / max(unchanged_total, 1)
        reviewed_total = sum(reviewed_counts.values())
        reviewed_top = reviewed_counts.most_common(1)[0] if reviewed_counts else (None, 0)
        reviewed_purity = reviewed_top[1] / max(reviewed_total, 1)
        counts = Counter(unchanged_counts)
        for label, count in reviewed_counts.items():
            counts[label] += int(count * args.reviewed_weight)
        total = sum(counts.values())
        if not unchanged_counts and not reviewed_counts:
            cluster_labels[cluster] = {
                "label": None,
                "confidence": "no_unchanged_single_char_evidence",
                "evidence_total": 0,
                "unchanged_top": [],
                "reviewed_connected_top": [],
                "top": [],
            }
            continue
        if unchanged_total >= args.min_evidence and unchanged_purity >= args.purity:
            assigned = str(unchanged_top[0])
            confidence = "strong_projected"
            if reviewed_total >= args.min_evidence and reviewed_top[0] != unchanged_top[0]:
                confidence = "strong_projected_connected_expected_conflict"
            label_assignments[assigned].append(cluster)
            cluster_labels[cluster] = {
                "label": assigned,
                "confidence": confidence,
                "evidence_total": total,
                "unchanged_evidence_total": unchanged_total,
                "reviewed_connected_total": reviewed_total,
                "purity": round(unchanged_purity, 4),
                "unchanged_purity": round(unchanged_purity, 4),
                "reviewed_connected_purity": round(reviewed_purity, 4),
                "unchanged_top": unchanged_counts.most_common(8),
                "reviewed_connected_top": reviewed_counts.most_common(8),
                "top": counts.most_common(8),
            }
            continue
        if unchanged_total >= max(3, args.min_evidence // 2) and unchanged_purity >= args.weak_purity:
            assigned = str(unchanged_top[0]) if args.include_weak else None
            confidence = "weak_projected_review"
            if assigned:
                label_assignments[assigned].append(cluster)
            cluster_labels[cluster] = {
                "label": assigned,
                "confidence": confidence,
                "evidence_total": total,
                "unchanged_evidence_total": unchanged_total,
                "reviewed_connected_total": reviewed_total,
                "purity": round(unchanged_purity, 4),
                "unchanged_purity": round(unchanged_purity, 4),
                "reviewed_connected_purity": round(reviewed_purity, 4),
                "unchanged_top": unchanged_counts.most_common(8),
                "reviewed_connected_top": reviewed_counts.most_common(8),
                "top": counts.most_common(8),
            }
            continue
        if reviewed_total >= args.min_evidence and reviewed_purity >= args.reviewed_purity:
            assigned = str(reviewed_top[0])
            confidence = "strong_reviewed_connected_child"
            label_assignments[assigned].append(cluster)
            purity = reviewed_purity
            label = assigned
            count = int(reviewed_top[1])
        else:
            confidence = "mixed_needs_review"
            assigned = None
            label, count = counts.most_common(1)[0]
            purity = count / max(total, 1)
        cluster_labels[cluster] = {
            "label": assigned,
            "confidence": confidence,
            "evidence_total": total,
            "unchanged_evidence_total": unchanged_total,
            "reviewed_connected_total": reviewed_total,
            "purity": round(purity, 4),
            "unchanged_purity": round(unchanged_purity, 4),
            "reviewed_connected_purity": round(reviewed_purity, 4),
            "unchanged_top": unchanged_counts.most_common(8),
            "reviewed_connected_top": reviewed_counts.most_common(8),
            "top": counts.most_common(8),
        }

    child_rows: list[dict[str, Any]] = []
    child_counts = Counter()
    child_match_counts = Counter()
    subcluster_label_counts = Counter()
    split_child_overrides: list[dict[str, Any]] = []
    skipped_expected_overrides = Counter()
    for item in split_children:
        cluster = cluster_key(item["cluster"])
        subcluster_label = split_subcluster_labels.get(stable_key(item))
        projected = (subcluster_label or {}).get("label") or cluster_labels.get(cluster, {}).get("label")
        expected = expected_base_from_parent(item, old_labels_by_blob)
        if subcluster_label:
            subcluster_label_counts["with_subcluster_label"] += 1
        child_counts["total"] += 1
        if projected:
            child_counts["with_projected_label"] += 1
        if expected:
            child_counts["with_expected_base"] += 1
        if projected and expected:
            if projected == expected:
                child_match_counts["match"] += 1
            else:
                child_match_counts["mismatch"] += 1
        if expected and coptic_base_len(expected) == 1:
            if not projected:
                split_child_overrides.append(split_child_override_row(item, expected, relative(new_dir / "_char_assignments_projected.json")))
            elif projected == expected:
                split_child_overrides.append(split_child_override_row(item, expected, relative(new_dir / "_char_assignments_projected.json")))
            else:
                skipped_expected_overrides["projected_label_conflict"] += 1
        child_rows.append({
            "page": str(item["page"]),
            "line_index": int(item["line_index"]),
            "blob_id": int(item["blob_id"]),
            "parent_blob_id": int(item["parent_blob_id"]),
            "split_child_index": int(item.get("split_child_index", 0)),
            "split_child_count": int(item.get("split_child_count", 1)),
            "cluster": cluster,
            "projected_label": projected,
            "projection_source": "split_subcluster_label" if subcluster_label else "split_cluster_label",
            "cluster_label_confidence": cluster_labels.get(cluster, {}).get("confidence"),
            "split_subcluster": (subcluster_label or {}).get("subcluster"),
            "split_subcluster_confidence": (subcluster_label or {}).get("confidence"),
            "split_subcluster_source": (subcluster_label or {}).get("source"),
            "split_expected_base": expected,
            "split_expected_text": item.get("split_expected_text"),
            "split_reason": item.get("split_reason"),
            "split_confidence": item.get("split_confidence"),
            "warped_bbox": item.get("warped_bbox"),
            "parent_warped_bbox": item.get("parent_warped_bbox"),
        })

    carried_blob_overrides: list[dict[str, Any]] = []
    for item, metadata in unchanged_items:
        cluster = cluster_key(item["cluster"])
        assigned = cluster_labels.get(cluster, {}).get("label")
        label = str(metadata.get("label"))
        if metadata.get("confidence") == "old_projected_cluster" and coptic_base_len(label) == 1:
            continue
        if assigned == label and metadata.get("confidence") == "old_projected_cluster":
            continue
        carried_blob_overrides.append(carried_blob_override_row(item, metadata, assigned))

    sorted_assignments = {label: sorted(clusters, key=int) for label, clusters in sorted(label_assignments.items())}
    review_clusters = review_cluster_rows(cluster_labels, carried_review_evidence_by_cluster)
    return {
        "description": "Labels projected onto split-derived clusters from unchanged single-character blob evidence.",
        "old_clusters": relative(old_dir),
        "new_clusters": relative(new_dir),
        "parameters": {
            "purity": args.purity,
            "weak_purity": args.weak_purity,
            "min_evidence": args.min_evidence,
            "include_weak": args.include_weak,
            "use_reviewed_connected_evidence": args.use_reviewed_connected_evidence,
            "use_split_expected_evidence": args.use_split_expected_evidence,
            "reviewed_weight": args.reviewed_weight,
            "reviewed_purity": args.reviewed_purity,
            "use_subcluster_labels": args.use_subcluster_labels,
        },
        "summary": {
            "new_cluster_count": len(cluster_labels),
            "assigned_cluster_count": sum(1 for row in cluster_labels.values() if row.get("label")),
            "split_child_counts": dict(child_counts),
            "split_child_expected_agreement": dict(child_match_counts),
            "split_child_subcluster_labels": dict(subcluster_label_counts),
            "split_child_expected_overrides_skipped": dict(skipped_expected_overrides),
            "old_blob_label_sources": dict(Counter(str(value.get("confidence")) for value in old_labels_by_blob.values())),
            "split_child_override_count": len(split_child_overrides),
            "carried_blob_override_count": len(carried_blob_overrides),
            "review_cluster_count": len(review_clusters),
            "carried_review_cluster_count": len(carried_review_evidence_by_cluster),
        },
        "assignments": sorted_assignments,
        "review_clusters": review_clusters,
        "cluster_labels": cluster_labels,
        "split_child_assignments": child_rows,
        "split_child_glyph_overrides": {
            "description": "Exact child labels produced from split parent expected text so reviewed connected readings survive root splitting.",
            "generated_from": relative(new_dir / "_char_assignments_projected.json"),
            "overrides": split_child_overrides,
        },
        "carried_blob_glyph_overrides": {
            "description": "Exact unchanged blob labels carried by stable page/line/blob identity when split reclustering cannot safely assign the whole new cluster.",
            "generated_from": relative(new_dir / "_char_assignments_projected.json"),
            "overrides": carried_blob_overrides,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-clusters", default=None)
    parser.add_argument("--new-clusters", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--purity", type=float, default=0.90)
    parser.add_argument("--weak-purity", type=float, default=0.75)
    parser.add_argument("--min-evidence", type=int, default=25)
    parser.add_argument("--include-weak", action="store_true")
    parser.add_argument("--use-reviewed-connected-evidence", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--use-split-expected-evidence", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--reviewed-weight", type=float, default=3.0)
    parser.add_argument("--reviewed-purity", type=float, default=0.90)
    parser.add_argument("--use-subcluster-labels", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--split-child-overrides-out", default=None)
    parser.add_argument("--carried-blob-overrides-out", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    new_dir = resolve_repo_path(args.new_clusters, DEFAULT_NEW_CLUSTERS)
    out_path = resolve_repo_path(args.out, new_dir / "_char_assignments_projected.json")
    split_child_out = resolve_repo_path(args.split_child_overrides_out, new_dir / "_split_child_glyph_overrides.json")
    carried_blob_out = resolve_repo_path(args.carried_blob_overrides_out, new_dir / "_carried_blob_glyph_overrides.json")
    result = project(args)
    write_json(out_path, result)
    write_json(split_child_out, result["split_child_glyph_overrides"])
    write_json(carried_blob_out, result["carried_blob_glyph_overrides"])
    print(out_path)
    print(split_child_out)
    print(carried_blob_out)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()