#!/usr/bin/env python3
"""Generate exact non-Coptic overrides for printed German editorial markers.

This is a bootstrap step: it reads the current LLM witness once to locate known
German apparatus words, extracts the corresponding blob ids and cluster arrays,
and writes a stable override file consumed by build_contextual_review.py.
After that, normal review builds use only page/line/blob identity and no longer
need the LLM text to keep these printed words out of the Coptic stream.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
OCR_ROOT = REPO / "output" / "projects" / "kephalaia_ocr"
DEFAULT_CLUSTER_NAME = "clusters_shape_padded_k120"
DEFAULT_WITNESS = OCR_ROOT / "llm_witness" / DEFAULT_CLUSTER_NAME / "composite_line_sequences.jsonl"
DEFAULT_CLUSTERS_DIR = OCR_ROOT / DEFAULT_CLUSTER_NAME
EDITORIAL_LABEL = "_editorial_marker"

NON_WORD_LABELS = {
    "_lacuna_dot",
    "_middle_dot",
}

MARKER_PATTERNS = [
    # Multi-word phrases (longest first for priority)
    ("Überschrift ganz verwischt", r"\b[Üü]berschrift\s+ganz\s+verwischt\b"),
    ("bis auf ganz geringe Spuren zerstört", r"\bbis\s+auf\s+ganz\s+geringe\s+Spuren\s+zerst[öo]rt\b"),
    ("bis auf geringe Spuren zerstört", r"\bbis\s+auf\s+geringe\s+Spuren\s+zerst[öo]rt\b"),
    ("zerstört und abgerieben", r"\bzerst[öo]rt\s+und\s+abgerieben\b"),
    ("verwischt und abgerieben", r"\bverwischt\s+und\s+abgerieben\b"),
    ("fast völlig zerstört", r"\bfast\s+v[öo]llig\s+zerst[öo]rt\b"),
    ("sehr stark zerstört", r"\bsehr\s+stark\s+zerst[öo]rt\b"),
    ("vollständig zerstört", r"\bvollst[äa]ndig\s+zerst[öo]rt\b"),
    ("fast ganz zerstört", r"\bfast\s+ganz\s+zerst[öo]rt\b"),
    ("einstweilen unlesbar", r"\beinstweilen\s+unlesbar\b"),
    ("ganz geringe Spuren", r"\bganz\s+geringe\s+Spuren\b"),
    ("Rest nicht zu lesen", r"\bRest\s+nicht\s+zu\s+lesen\b"),
    ("zu stark abgerieben", r"\bzu\s+stark\s+abgerieben\b"),
    ("stark abgerieben", r"\bstark\s+abgerieben\b"),
    ("Rest abgerieben", r"\bRest\s+abgerieben\b"),
    ("Rest zerstört", r"\bRest\s+zerst[öo]rt\b"),
    ("geringe Spuren", r"\bgeringe\s+Spuren\b"),
    ("nicht zu lesen", r"\bnicht\s+zu\s+lesen\b"),
    ("nicht gelesen", r"\bnicht\s+gelesen\b"),
    ("nicht lesbar", r"\bnicht\s+lesbar\b"),
    ("teils unlesbar", r"\bteils\s+unlesbar\b"),
    ("leer abgerieben", r"\bleer\s+abgerieben\b"),
    ("wohl leer", r"\bwohl\s+leer\b"),
    ("ff. zerstört", r"\bff\.\s*zerst[öo]rt\b"),
    # Single words
    ("abgerieben", r"\babgerieben\b"),
    ("verwischt", r"\bverwischt\b"),
    ("zerstört", r"\bzerst[öo]rt\b"),
    ("unleserlich", r"\bunleserlich\b"),
    ("undeutlich", r"\bundeutlich\b"),
    ("unlesbar", r"\bunlesbar\b"),
    ("leer", r"\bleer\b"),
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if raw:
                rows.append(json.loads(raw))
    return rows


def dump_json(path: Path, data: Any) -> None:
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


def bbox(unit: dict[str, Any]) -> list[int]:
    values = (unit.get("geometry") or {}).get("warped_bbox") or [0, 0, 0, 0]
    return [int(value) for value in values]


def x0(unit: dict[str, Any]) -> int:
    return bbox(unit)[0]


def x1(unit: dict[str, Any]) -> int:
    return bbox(unit)[2]


def gap(left: dict[str, Any], right: dict[str, Any]) -> int:
    return x0(right) - x1(left) - 1


def is_dot_like(unit: dict[str, Any]) -> bool:
    geometry = unit.get("geometry") or {}
    width = float(geometry.get("width", 999))
    height = float(geometry.get("height", 999))
    area = float(geometry.get("area", 999))
    return width <= 7 and height <= 8 and area <= 35


def is_word_candidate(unit: dict[str, Any]) -> bool:
    label = unit.get("label")
    if label in NON_WORD_LABELS:
        return False
    if is_dot_like(unit):
        return False
    return True


def is_unaligned(unit: dict[str, Any]) -> bool:
    status = (unit.get("llm_alignment") or {}).get("status")
    return status in {"llm_unaligned", "llm_unavailable"}


def word_runs(
    units: list[dict[str, Any]], max_letter_gap: int, *, require_unaligned: bool
) -> list[list[dict[str, Any]]]:
    runs: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for unit in units:
        if (not require_unaligned or is_unaligned(unit)) and is_word_candidate(unit):
            if current and gap(current[-1], unit) > max_letter_gap:
                runs.append(current)
                current = []
            current.append(unit)
            continue
        if current:
            runs.append(current)
            current = []
    if current:
        runs.append(current)
    return runs


def marker_words(text: str) -> list[str]:
    return re.findall(r"[A-Za-zÄÖÜäöüß]+", text)


def display_chars(text: str) -> list[str]:
    return [char for word in marker_words(text) for char in word]


def find_marker_matches(text: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    claimed: list[tuple[int, int]] = []
    for marker_type, pattern in MARKER_PATTERNS:
        regex = re.compile(pattern, re.IGNORECASE)
        for match in regex.finditer(text):
            span = match.span()
            if any(max(span[0], old[0]) < min(span[1], old[1]) for old in claimed):
                continue
            claimed.append(span)
            matches.append({
                "marker_type": marker_type,
                "marker_text": match.group(0),
                "text_start": span[0],
                "text_end": span[1],
            })
    return sorted(matches, key=lambda item: int(item["text_start"]))


def inter_run_gap(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> int:
    return gap(left[-1], right[0])


def matching_run_groups(
    runs: list[list[dict[str, Any]]], marker_text: str, max_word_gap: int
) -> list[list[list[dict[str, Any]]]]:
    lengths = [len(word) for word in marker_words(marker_text)]
    if not lengths:
        return []
    groups: list[list[list[dict[str, Any]]]] = []
    count = len(lengths)
    for start in range(0, len(runs) - count + 1):
        group = runs[start:start + count]
        if [len(run) for run in group] != lengths:
            continue
        if all(inter_run_gap(group[index], group[index + 1]) <= max_word_gap for index in range(count - 1)):
            groups.append(group)
    return groups


def matching_elastic_run_groups(
    runs: list[list[dict[str, Any]]], marker_text: str, max_word_gap: int, max_total_extra: int = 2
) -> list[list[list[dict[str, Any]]]]:
    lengths = [len(word) for word in marker_words(marker_text)]
    if not lengths:
        return []
    groups: list[list[list[dict[str, Any]]]] = []
    count = len(lengths)
    for start in range(0, len(runs) - count + 1):
        group = runs[start:start + count]
        run_lengths = [len(run) for run in group]
        differences = [run_lengths[index] - lengths[index] for index in range(count)]
        if any(difference < 0 or difference > max_total_extra for difference in differences):
            continue
        if sum(differences) == 0 or sum(differences) > max_total_extra:
            continue
        if all(inter_run_gap(group[index], group[index + 1]) <= max_word_gap for index in range(count - 1)):
            groups.append(group)
    return groups


def flatten(group: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [unit for run in group for unit in run]


def display_chars_for_group(marker_text: str, group: list[list[dict[str, Any]]]) -> list[str]:
    """Distribute marker text characters across blob positions.

    When a run has more blobs than the word has letters (elastic match),
    spread the letters proportionally — each blob gets the nearest letter
    from the word so nothing shows as unassigned.
    """
    output: list[str] = []
    for word, run in zip(marker_words(marker_text), group):
        chars = list(word)
        run_length = len(run)
        if run_length == len(chars):
            output.extend(chars)
        elif run_length > len(chars) and chars:
            # Distribute letters proportionally across blob positions
            for i in range(run_length):
                char_idx = min(int(i * len(chars) / run_length), len(chars) - 1)
                output.append(chars[char_idx])
        elif run_length > 0:
            output.extend(chars[:max(0, run_length - 1)])
            output.append("".join(chars[max(0, run_length - 1):]))
    return output


def group_center_x(group: list[list[dict[str, Any]]]) -> float:
    units = flatten(group)
    if not units:
        return 0.0
    return (x0(units[0]) + x1(units[-1])) / 2.0


def line_width(units: list[dict[str, Any]]) -> float:
    boxes = [bbox(unit) for unit in units if bbox(unit) != [0, 0, 0, 0]]
    if not boxes:
        return 1.0
    return max(1.0, float(max(box[2] for box in boxes) - min(box[0] for box in boxes)))


def select_bootstrap_group(
    row: dict[str, Any], match: dict[str, Any], groups: list[list[list[dict[str, Any]]]]
) -> list[list[dict[str, Any]]] | None:
    if not groups:
        return None
    if len(groups) == 1:
        return groups[0]

    text = str(row.get("llm_text") or "")
    units = row.get("units", [])
    width = line_width(units)
    line_min_x = min((x0(unit) for unit in units if bbox(unit) != [0, 0, 0, 0]), default=0)
    text_ratio = (float(match["text_start"]) + float(match["text_end"])) / 2.0 / max(1.0, float(len(text)))

    def score(group: list[list[dict[str, Any]]]) -> float:
        x_ratio = (group_center_x(group) - line_min_x) / width
        return abs(x_ratio - text_ratio)

    scored = sorted((score(group), group) for group in groups)
    if len(scored) > 1 and scored[1][0] - scored[0][0] < 0.08:
        return None
    return scored[0][1]


def make_override(
    row: dict[str, Any],
    match: dict[str, Any],
    group: list[list[dict[str, Any]]],
    witness_path: Path,
    confidence: str = "generated_cluster_span",
) -> dict[str, Any]:
    units = flatten(group)
    clusters = [str(unit.get("cluster")) for unit in units]
    return {
        "page": str(row["page"]),
        "line_index": int(row["line_index"]),
        "blob_ids": [int(unit["blob_id"]) for unit in units],
        "label": EDITORIAL_LABEL,
        "marker_type": match["marker_type"],
        "marker_text": match["marker_text"],
        "display_chars": display_chars_for_group(str(match["marker_text"]), group),
        "confidence": confidence,
        "source": relative(witness_path),
        "evidence": str(row.get("llm_text") or ""),
        "clusters": clusters,
        "cluster_signature": " ".join(clusters),
        "word_cluster_runs": [[str(unit.get("cluster")) for unit in run] for run in group],
        "gaps": [gap(units[index], units[index + 1]) for index in range(len(units) - 1)],
    }


def build_outputs(
    rows: list[dict[str, Any]], witness_path: Path, max_letter_gap: int, max_word_gap: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Counter[str]]]:
    overrides: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    signature_counts: dict[str, Counter[str]] = defaultdict(Counter)
    claimed_keys: set[tuple[str, int, int]] = set()

    for row in rows:
        text = str(row.get("llm_text") or "")
        matches = find_marker_matches(text)
        if not matches:
            continue
        strict_runs = word_runs(row.get("units", []), max_letter_gap, require_unaligned=True)
        bootstrap_runs = word_runs(row.get("units", []), max_letter_gap, require_unaligned=False)
        for match in matches:
            confidence = "generated_cluster_span"
            groups = matching_run_groups(strict_runs, str(match["marker_text"]), max_word_gap)
            if len(groups) != 1:
                bootstrap_groups = matching_run_groups(
                    bootstrap_runs,
                    str(match["marker_text"]),
                    max_word_gap,
                )
                selected = select_bootstrap_group(row, match, bootstrap_groups)
                if selected is not None:
                    groups = [selected]
                    confidence = "generated_llm_bootstrap_cluster_span"
            if len(groups) != 1:
                elastic_groups = matching_elastic_run_groups(
                    strict_runs,
                    str(match["marker_text"]),
                    max_word_gap,
                )
                selected = select_bootstrap_group(row, match, elastic_groups)
                if selected is not None:
                    groups = [selected]
                    confidence = "generated_elastic_cluster_span"
            if len(groups) != 1:
                elastic_bootstrap_groups = matching_elastic_run_groups(
                    bootstrap_runs,
                    str(match["marker_text"]),
                    max_word_gap,
                )
                selected = select_bootstrap_group(row, match, elastic_bootstrap_groups)
                if selected is not None:
                    groups = [selected]
                    confidence = "generated_llm_bootstrap_elastic_span"
            if len(groups) != 1:
                target = ambiguous if groups else unmatched
                target.append({
                    "page": str(row["page"]),
                    "line_index": int(row["line_index"]),
                    **match,
                    "candidate_count": len(groups),
                    "candidate_cluster_runs": [
                        [[str(unit.get("cluster")) for unit in run] for run in group]
                        for group in groups[:8]
                    ],
                    "bootstrap_candidate_count": len(matching_run_groups(
                        bootstrap_runs,
                        str(match["marker_text"]),
                        max_word_gap,
                    )),
                    "elastic_candidate_count": len(matching_elastic_run_groups(
                        bootstrap_runs,
                        str(match["marker_text"]),
                        max_word_gap,
                    )),
                    "evidence": text,
                })
                continue

            override = make_override(row, match, groups[0], witness_path, confidence)
            keys = {
                (str(override["page"]), int(override["line_index"]), int(blob_id))
                for blob_id in override["blob_ids"]
            }
            if claimed_keys & keys:
                ambiguous.append({
                    "page": str(row["page"]),
                    "line_index": int(row["line_index"]),
                    **match,
                    "candidate_count": 1,
                    "reason": "overlaps_existing_override",
                    "blob_ids": override["blob_ids"],
                    "evidence": text,
                })
                continue
            claimed_keys.update(keys)
            overrides.append(override)
            signature_counts[str(match["marker_type"])][str(override["cluster_signature"])] += 1

    overrides.sort(key=lambda item: (str(item["page"]), int(item["line_index"]), item["blob_ids"]))
    return overrides, ambiguous, unmatched, signature_counts


# ---------------------------------------------------------------------------
# Phase 2: cluster-vocabulary fuzzy matching
# ---------------------------------------------------------------------------

def build_cluster_vocab(overrides: list[dict[str, Any]]) -> dict[str, Counter[str]]:
    """Build cluster_id → {letter: count} from confirmed Phase 1 overrides."""
    vocab: dict[str, Counter[str]] = defaultdict(Counter)
    for ov in overrides:
        clusters = ov.get("clusters", [])
        chars = ov.get("display_chars", [])
        for cl, ch in zip(clusters, chars):
            if ch and ch != "\u200b":
                vocab[str(cl)][ch.lower()] += 1
    return dict(vocab)


def decode_run_vocab(
    run: list[dict[str, Any]], vocab: dict[str, Counter[str]]
) -> tuple[str, int]:
    """Decode a blob run using cluster vocabulary.

    Returns (decoded_string, hit_count).
    """
    decoded: list[str] = []
    hits = 0
    for unit in run:
        cl = str(unit.get("cluster"))
        if cl in vocab:
            best = vocab[cl].most_common(1)[0][0]
            decoded.append(best)
            hits += 1
        else:
            decoded.append("?")
    return "".join(decoded), hits


def fuzzy_phrase_match(
    decoded_parts: list[str],
    target_phrase: str,
    vocab_ratio: float,
) -> bool:
    """Check if the concatenated decoded blobs match *target_phrase*.

    Tolerance scales with phrase length:
    - Short phrases (≤5 chars, e.g. "leer"): must match ≥60% of chars
    - Medium phrases (6-15 chars): must match ≥50% of chars
    - Long phrases (16+ chars): must match ≥40% of chars

    The vocab_ratio (fraction of blobs with known cluster mappings) is
    also factored in: if few blobs have vocab hits, even a lucky char
    match is unreliable.
    """
    decoded_flat = "".join(decoded_parts)
    target_flat = target_phrase.replace(" ", "").lower()
    if not target_flat:
        return False

    # Require minimum vocab coverage (at least 40% of blobs map to
    # known letters; otherwise the decoding is mostly guesswork)
    if vocab_ratio < 0.4:
        return False

    tlen = len(target_flat)
    dlen = len(decoded_flat)

    # Reject if decoded is shorter than target
    if dlen < tlen:
        return False

    # Sliding window over decoded to find best alignment with target
    best_match = 0
    for offset in range(dlen - tlen + 1):
        window = decoded_flat[offset : offset + tlen]
        matches = sum(1 for a, b in zip(window, target_flat) if a == b)
        best_match = max(best_match, matches)

    match_ratio = best_match / tlen

    # Context-dependent threshold
    if tlen <= 5:
        threshold = 0.60
    elif tlen <= 15:
        threshold = 0.50
    else:
        threshold = 0.40

    return match_ratio >= threshold


def vocabulary_scan(
    rows: list[dict[str, Any]],
    phase1_overrides: list[dict[str, Any]],
    witness_path: Path,
    max_letter_gap: int,
    max_word_gap: int,
) -> tuple[list[dict[str, Any]], dict[str, Counter[str]]]:
    """Scan ALL lines for editorial markers using the cluster vocabulary
    learned from Phase 1 overrides.

    This catches lines where the LLM witness did not produce German text
    but the underlying blobs match known editorial marker shapes.
    """
    vocab = build_cluster_vocab(phase1_overrides)
    if not vocab:
        return [], defaultdict(Counter)

    # Already-claimed blob keys from Phase 1
    claimed: set[tuple[str, int, int]] = set()
    for ov in phase1_overrides:
        page = str(ov["page"])
        li = int(ov["line_index"])
        for bid in ov["blob_ids"]:
            claimed.add((page, li, int(bid)))

    new_overrides: list[dict[str, Any]] = []
    sig_counts: dict[str, Counter[str]] = defaultdict(Counter)

    for row in rows:
        page = str(row["page"])
        line_idx = int(row["line_index"])
        units = row.get("units", [])
        if not units:
            continue

        # Use bootstrap runs (don't require LLM alignment)
        runs = word_runs(units, max_letter_gap, require_unaligned=False)
        if not runs:
            continue

        for marker_type, _pattern in MARKER_PATTERNS:
            words = marker_words(marker_type)
            if not words:
                continue

            # Guard: short single-word markers (e.g. "leer") produce massive
            # false positives on Coptic-dense lines.  True "leer" lines are
            # empty — they should have very few Coptic characters.
            # (Lines with mixed Coptic + German are handled by Phase 1.)
            if len(words) == 1 and len(words[0]) <= 6:
                coptic_on_line = sum(
                    1 for u in units
                    if u.get("final_label")
                    and not str(u.get("final_label")).startswith("_")
                    and str(u.get("final_label")) != "None"
                )
                if coptic_on_line > 5:
                    continue

            # Structural match: run lengths must match word lengths
            groups = matching_run_groups(runs, marker_type, max_word_gap)
            if not groups:
                groups = matching_elastic_run_groups(
                    runs, marker_type, max_word_gap, max_total_extra=2,
                )

            for group in groups:
                flat = flatten(group)
                keys = {(page, line_idx, int(u["blob_id"])) for u in flat}
                if keys & claimed:
                    continue

                # Decode all runs and check whole-phrase fuzzy match
                total_hits = 0
                total_blobs = 0
                decoded_parts: list[str] = []
                for run in group:
                    decoded, hits = decode_run_vocab(run, vocab)
                    decoded_parts.append(decoded)
                    total_hits += hits
                    total_blobs += len(run)

                vocab_ratio = total_hits / max(1, total_blobs)

                if not fuzzy_phrase_match(
                    decoded_parts, marker_type, vocab_ratio
                ):
                    continue

                match_info = {
                    "marker_type": marker_type,
                    "marker_text": marker_type,
                    "text_start": 0,
                    "text_end": 0,
                }
                override = make_override(
                    row, match_info, group, witness_path,
                    confidence="generated_vocab_fuzzy_match",
                )
                override["evidence"] = (
                    f"vocab_scan: decoded={decoded_parts} "
                    f"vocab_ratio={vocab_ratio:.2f}"
                )
                claimed.update(keys)
                new_overrides.append(override)
                sig = str(override.get("cluster_signature", ""))
                sig_counts[marker_type][sig] += 1
                break  # one marker type per group position

    new_overrides.sort(
        key=lambda item: (str(item["page"]), int(item["line_index"]), item["blob_ids"])
    )
    return new_overrides, sig_counts


# ---------------------------------------------------------------------------
# Phase 3: line-level fallback for German lines with unclaimed blobs
# ---------------------------------------------------------------------------

def _is_assigned_coptic(unit: dict[str, Any]) -> bool:
    """Return True if unit has a confirmed Coptic label."""
    label = unit.get("final_label")
    if not label or str(label) == "None":
        return False
    source = str(unit.get("final_label_source") or "")
    if str(label).startswith("_"):
        return False
    # Must have a confident assignment
    return source in {"assigned", "candidate", "assigned_multi"}


def line_level_fallback(
    rows: list[dict[str, Any]],
    prior_overrides: list[dict[str, Any]],
    witness_path: Path,
) -> list[dict[str, Any]]:
    """Claim all unclaimed blobs on lines where the LLM text matches German
    editorial patterns but Phase 1/2 could not align blobs individually.

    This handles cases where German words are printed as connected multi-char
    blobs or scattered dot remnants that don't match expected character counts.
    """
    # Build set of already-claimed blob keys
    claimed: set[tuple[str, int, int]] = set()
    for ov in prior_overrides:
        page = str(ov["page"])
        li = int(ov["line_index"])
        for bid in ov["blob_ids"]:
            claimed.add((page, li, int(bid)))

    new_overrides: list[dict[str, Any]] = []

    for row in rows:
        page = str(row["page"])
        line_idx = int(row["line_index"])
        text = str(row.get("llm_text") or "")
        if not text:
            continue

        # Check if this line matches any German pattern
        matches = find_marker_matches(text)
        if not matches:
            continue

        # Check if this line already has editorial overrides
        units = row.get("units", [])
        any_overridden = any(
            (page, line_idx, int(u["blob_id"])) in claimed
            for u in units
        )
        if any_overridden:
            continue

        # Collect unclaimed, non-Coptic-assigned blobs on this line
        unclaimed_units = []
        for u in units:
            bid = int(u["blob_id"])
            if (page, line_idx, bid) in claimed:
                continue
            if _is_assigned_coptic(u):
                continue
            unclaimed_units.append(u)

        if not unclaimed_units:
            continue

        # Use the longest/first match as the marker
        match = matches[0]
        blob_ids = [int(u["blob_id"]) for u in unclaimed_units]
        clusters = [str(u.get("cluster")) for u in unclaimed_units]

        # Distribute the marker text characters across unclaimed blobs
        marker_chars = display_chars(str(match["marker_text"]))
        if len(marker_chars) >= len(unclaimed_units):
            # More chars than blobs: bundle chars into blobs
            chars_per: list[str] = []
            for i in range(len(unclaimed_units)):
                idx_start = int(i * len(marker_chars) / len(unclaimed_units))
                idx_end = int((i + 1) * len(marker_chars) / len(unclaimed_units))
                chars_per.append("".join(marker_chars[idx_start:idx_end]))
        else:
            # More blobs than chars: spread chars, pad with zero-width space
            chars_per = []
            for i in range(len(unclaimed_units)):
                ci = int(i * len(marker_chars) / len(unclaimed_units))
                chars_per.append(marker_chars[ci] if ci < len(marker_chars) else "\u200b")

        override = {
            "page": page,
            "line_index": line_idx,
            "blob_ids": blob_ids,
            "label": EDITORIAL_LABEL,
            "marker_type": match["marker_type"],
            "marker_text": match["marker_text"],
            "display_chars": chars_per,
            "confidence": "generated_line_level_fallback",
            "source": relative(witness_path),
            "evidence": text,
            "clusters": clusters,
            "cluster_signature": " ".join(clusters),
            "word_cluster_runs": [clusters],
            "gaps": [
                gap(unclaimed_units[i], unclaimed_units[i + 1])
                for i in range(len(unclaimed_units) - 1)
            ],
        }
        for bid in blob_ids:
            claimed.add((page, line_idx, bid))
        new_overrides.append(override)

    new_overrides.sort(
        key=lambda item: (str(item["page"]), int(item["line_index"]), item["blob_ids"])
    )
    return new_overrides


def write_markdown_report(
    path: Path,
    overrides: list[dict[str, Any]],
    ambiguous: list[dict[str, Any]],
    unmatched: list[dict[str, Any]],
    signature_counts: dict[str, Counter[str]],
) -> None:
    lines = [
        "# Kephalaia OCR Editorial Marker Detection",
        "",
        f"Exact override spans: {len(overrides)}",
        f"Ambiguous marker matches: {len(ambiguous)}",
        f"Unmatched marker matches: {len(unmatched)}",
        "",
        "## Signature Summary",
        "",
    ]
    for marker_type in sorted(signature_counts):
        lines.append(f"### {marker_type}")
        lines.append("")
        for signature, count in signature_counts[marker_type].most_common(12):
            lines.append(f"- {count} x `{signature}`")
        lines.append("")

    lines.extend(["## Ambiguous Examples", ""])
    for item in ambiguous[:50]:
        lines.append(
            f"- p{item['page']} l{item['line_index']}: {item['marker_text']} "
            f"({item.get('candidate_count')} candidates)"
        )
    lines.extend(["", "## Unmatched Examples", ""])
    for item in unmatched[:50]:
        lines.append(f"- p{item['page']} l{item['line_index']}: {item['marker_text']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> None:
    witness_path = resolve_repo_path(args.witness, DEFAULT_WITNESS)
    clusters_dir = resolve_repo_path(args.clusters_dir, DEFAULT_CLUSTERS_DIR)
    report_dir = resolve_repo_path(
        args.report_dir,
        OCR_ROOT / "editorial_markers" / clusters_dir.name,
    )
    override_path = resolve_repo_path(args.override_path, clusters_dir / "_editorial_word_overrides.json")
    rows = load_jsonl(witness_path)
    overrides, ambiguous, unmatched, signature_counts = build_outputs(
        rows,
        witness_path,
        args.max_letter_gap,
        args.max_word_gap,
    )
    print(f"Phase 1 (LLM-bootstrapped): {len(overrides)} overrides")

    # Phase 2: vocabulary-based fuzzy matching on uncovered lines
    phase2_overrides, phase2_sigs = vocabulary_scan(
        rows, overrides, witness_path, args.max_letter_gap, args.max_word_gap,
    )
    if phase2_overrides:
        overrides.extend(phase2_overrides)
        overrides.sort(
            key=lambda item: (str(item["page"]), int(item["line_index"]), item["blob_ids"])
        )
        for marker_type, counter in phase2_sigs.items():
            signature_counts[marker_type] += counter
        print(f"Phase 2 (vocab fuzzy):      {len(phase2_overrides)} additional overrides")
    else:
        print("Phase 2 (vocab fuzzy):      0 additional overrides")

    # Phase 3: line-level fallback — claim all unclaimed blobs on German lines
    phase3_overrides = line_level_fallback(rows, overrides, witness_path)
    if phase3_overrides:
        overrides.extend(phase3_overrides)
        overrides.sort(
            key=lambda item: (str(item["page"]), int(item["line_index"]), item["blob_ids"])
        )
        print(f"Phase 3 (line fallback):    {len(phase3_overrides)} additional overrides")
    else:
        print("Phase 3 (line fallback):    0 additional overrides")

    output = {
        "description": "Generated exact non-Coptic spans for printed German editorial markers.",
        "label": EDITORIAL_LABEL,
        "generated_from": relative(witness_path),
        "parameters": {
            "max_letter_gap": args.max_letter_gap,
            "max_word_gap": args.max_word_gap,
        },
        "overrides": overrides,
    }
    candidates = {
        **output,
        "ambiguous": ambiguous,
        "unmatched": unmatched,
        "signature_counts": {
            marker_type: dict(counter.most_common())
            for marker_type, counter in sorted(signature_counts.items())
        },
    }

    dump_json(override_path, output)
    dump_json(report_dir / "editorial_marker_candidates.json", candidates)
    write_markdown_report(
        report_dir / "editorial_marker_report.md",
        overrides,
        ambiguous,
        unmatched,
        signature_counts,
    )
    print(f"wrote {len(overrides)} overrides to {relative(override_path)}")
    print(f"wrote report to {relative(report_dir / 'editorial_marker_report.md')}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--witness", default=None)
    parser.add_argument("--clusters-dir", default=None)
    parser.add_argument("--override-path", default=None)
    parser.add_argument("--report-dir", default=None)
    parser.add_argument("--max-letter-gap", type=int, default=12)
    parser.add_argument("--max-word-gap", type=int, default=45)
    return parser.parse_args()


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()