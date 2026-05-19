#!/usr/bin/env python3
"""Build the Manual Reviewer editorial fingerprint layer from scratch.

This script deliberately does not read the old editorial marker override file.
It performs the three operations the reviewer layer needs:

1. Inventory unique German editorial phrases from the LLM witness text.
2. Record a few manuscript-side page/line samples for each phrase.
3. Build exact per-character fingerprints from the pre-overlay webapp ingest
   token stream. A fingerprint is one cluster/blob assignment per non-space
   Latin letter in the full phrase.

No fuzzy matching, vocabulary matching, line-level spreading, or phrase display
overlay happens here.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[3]
WITNESS_PATH = (
    REPO
    / "output"
    / "projects"
    / "kephalaia_ocr"
    / "llm_witness"
    / "clusters_shape_padded_split_bodycrop_corrected_k240"
    / "composite_line_sequences.jsonl"
)
BASELINE_DIR = REPO / "manual_reviewer" / "data" / "ingest" / "initial_baseline"
OUT_DIR = REPO / "manual_reviewer" / "data" / "ingest" / "editorial_fingerprints"
INVENTORY_PATH = OUT_DIR / "editorial_phrase_inventory.json"
SAMPLES_MD_PATH = OUT_DIR / "editorial_phrase_samples.md"
INDEX_PATH = OUT_DIR / "editorial_fingerprint_index.json"

EDITORIAL_KEYWORDS = {
    "abgerieben",
    "beschadigt",
    "einstweilen",
    "gelesen",
    "lesbar",
    "lesen",
    "leer",
    "nicht",
    "rest",
    "reste",
    "spuren",
    "undeutlich",
    "unlesbar",
    "unleserlich",
    "verwischt",
    "vollig",
    "zerstort",
}

COPTIC_RE = re.compile(r"[\u2C80-\u2CFF]")


def relative(path: Path) -> str:
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def ascii_fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def is_latin_letter(ch: str) -> bool:
    if not ch.isalpha():
        return False
    return unicodedata.name(ch, "").startswith("LATIN")


def is_coptic_letter(ch: str) -> bool:
    return bool(COPTIC_RE.match(ch))


def phrase_chars(text: str) -> list[str]:
    return [ch for ch in text if is_latin_letter(ch)]


def normalize_phrase(text: str) -> str:
    text = re.sub(r"[(),;:]+", " ", text)
    return " ".join(text.strip().split())


def phrase_key(text: str) -> str:
    return ascii_fold(normalize_phrase(text))


def latin_phrase_spans(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    start: int | None = None
    end = 0
    saw_letter = False

    def close(until: int) -> None:
        nonlocal start, end, saw_letter
        if start is None or not saw_letter:
            start = None
            end = 0
            saw_letter = False
            return
        raw = text[start:until]
        stripped = normalize_phrase(raw)
        if stripped:
            leading = len(raw) - len(raw.lstrip())
            trailing = len(raw.rstrip())
            spans.append((start + leading, start + trailing, stripped))
        start = None
        end = 0
        saw_letter = False

    for idx, ch in enumerate(text):
        if is_latin_letter(ch):
            if start is None:
                start = idx
            saw_letter = True
            end = idx + 1
        elif (ch.isspace() or ch in "(),;:") and start is not None:
            end = idx + 1
        else:
            close(idx)
    close(len(text) if start is not None else end)
    return spans


def is_editorial_candidate(phrase: str) -> bool:
    normalized = phrase_key(phrase)
    words = normalized.split()
    if not words:
        return False
    if normalized.startswith("wohl ") or " wohl " in f" {normalized} ":
        return False
    if normalized == "und":
        return False
    if len(phrase_chars(phrase)) < 4:
        return False
    return any(keyword in words or keyword in normalized for keyword in EDITORIAL_KEYWORDS)


def phrase_kind(phrase: str) -> str:
    return "vacat" if phrase_key(phrase) == "leer" else "editorial"


def has_substantive_letters(text: str) -> bool:
    return any(is_latin_letter(ch) or is_coptic_letter(ch) for ch in text)


def token_center_x(token: dict[str, Any]) -> float:
    aabb = (((token.get("geometry") or {}).get("aabb")) or [0, 0, 0, 0])
    return (float(aabb[0]) + float(aabb[2])) / 2.0


def load_witness_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if raw:
                rows.append(json.loads(raw))
    return rows


def build_inventory(rows: Iterable[dict[str, Any]], sample_limit: int) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    display_counts: dict[str, Counter[str]] = defaultdict(Counter)
    samples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    first_seen: dict[str, tuple[str, int]] = {}

    for row in rows:
        text = row.get("llm_text")
        if not isinstance(text, str):
            continue
        for start, end, phrase in latin_phrase_spans(text):
            if not is_editorial_candidate(phrase):
                continue
            key = phrase_key(phrase)
            counts[key] += 1
            display_counts[key][phrase] += 1
            first_seen.setdefault(key, (str(row.get("page")), int(row.get("line_index", -1))))
            if len(samples[key]) < sample_limit:
                samples[key].append(
                    {
                        "page": str(row.get("page")),
                        "line_index": int(row.get("line_index", -1)),
                        "text": text,
                        "phrase_start": start,
                        "phrase_end": end,
                    }
                )

    phrases: list[dict[str, Any]] = []
    for key in sorted(counts, key=lambda item: (phrase_kind(item), item)):
        phrase = display_counts[key].most_common(1)[0][0]
        chars = phrase_chars(phrase)
        page, line_index = first_seen[key]
        phrases.append(
            {
                "key": key,
                "phrase": phrase,
                "kind": phrase_kind(phrase),
                "char_count_no_spaces": len(chars),
                "chars_no_spaces": chars,
                "witness_count": counts[key],
                "first_seen": {"page": page, "line_index": line_index},
                "witness_samples": samples[key],
            }
        )

    return {
        "source": relative(WITNESS_PATH),
        "rule": "Latin editorial phrases extracted from llm_text; full phrases kept, words are not split.",
        "phrase_count": len(phrases),
        "phrases": phrases,
    }


def load_baseline_tokens(path: Path) -> dict[tuple[str, int], list[dict[str, Any]]]:
    by_page_v1: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for page_path in sorted(path.glob("p*.json")):
        page_data = load_json(page_path)
        page = str(page_data.get("page") or page_path.stem.removeprefix("p"))
        for line in page_data.get("lines", []):
            v2_line_index = int(line.get("line_index", -1))
            for token in line.get("tokens", []):
                enriched = dict(token)
                enriched["page"] = page
                enriched["line_index"] = v2_line_index
                enriched["v1_line_index"] = int(token.get("v1_line_index", line.get("v1_line_index", -1)))
                by_page_v1[(page, enriched["v1_line_index"])].append(enriched)

    for tokens in by_page_v1.values():
        tokens.sort(key=lambda item: (int(item.get("line_index", -1)), token_center_x(item), int(item.get("blob_id", -1))))
    return by_page_v1


def choose_window(
    tokens: list[dict[str, Any]],
    count: int,
    text: str,
    start: int,
    end: int,
) -> tuple[str | None, list[dict[str, Any]]]:
    before = text[:start]
    after = text[end:]
    at_start = not has_substantive_letters(before)
    at_end = not has_substantive_letters(after)
    if len(tokens) < count:
        return "not_enough_tokens", []
    if at_start and not at_end:
        return "leading", tokens[:count]
    if at_end and not at_start:
        return "trailing", tokens[-count:]
    if at_start and at_end:
        return "whole_line", tokens[:count]
    return "phrase_not_at_resolvable_edge", []


def build_fingerprint_index(
    rows: Iterable[dict[str, Any]],
    inventory: dict[str, Any],
    baseline_tokens: dict[tuple[str, int], list[dict[str, Any]]],
    *,
    include_vacat: bool,
) -> dict[str, Any]:
    phrase_info = {item["key"]: item for item in inventory["phrases"]}
    fingerprints: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, int, int, str]] = set()

    for row in rows:
        text = row.get("llm_text")
        if not isinstance(text, str):
            continue
        page = str(row.get("page"))
        v1_line_index = int(row.get("line_index", -1))
        tokens = baseline_tokens.get((page, v1_line_index), [])
        for start, end, phrase in latin_phrase_spans(text):
            info = phrase_info.get(phrase_key(phrase))
            if not info:
                continue
            kind = str(info["kind"])
            chars = phrase_chars(phrase)
            canonical_phrase = str(info["phrase"])
            if kind == "vacat" and not include_vacat:
                skipped.append(
                    {
                        "page": page,
                        "v1_line_index": v1_line_index,
                        "phrase": canonical_phrase,
                        "witness_phrase": phrase,
                        "kind": kind,
                        "reason": "vacat_not_editorial_overlay",
                        "text": text,
                    }
                )
                continue
            window_source, window = choose_window(tokens, len(chars), text, start, end)
            if len(window) != len(chars):
                skipped.append(
                    {
                        "page": page,
                        "v1_line_index": v1_line_index,
                        "phrase": canonical_phrase,
                        "witness_phrase": phrase,
                        "kind": kind,
                        "reason": window_source or "no_window",
                        "needed_chars": len(chars),
                        "available_tokens": len(tokens),
                        "text": text,
                    }
                )
                continue
            occurrence_key = (page, v1_line_index, int(window[0].get("blob_id", -1)), canonical_phrase)
            if occurrence_key in seen_keys:
                continue
            seen_keys.add(occurrence_key)
            assignments = []
            for position, (char, token) in enumerate(zip(chars, window)):
                assignments.append(
                    {
                        "position": position,
                        "char": char,
                        "page": page,
                        "line_index": int(token.get("line_index", -1)),
                        "v1_line_index": int(token.get("v1_line_index", v1_line_index)),
                        "blob_id": int(token.get("blob_id")),
                        "cluster": str(token.get("cluster") or "unclustered"),
                    }
                )
            fingerprints.append(
                {
                    "page": page,
                    "v1_line_index": v1_line_index,
                    "line_indices": sorted({item["line_index"] for item in assignments}),
                    "phrase": canonical_phrase,
                    "witness_phrase": phrase,
                    "kind": kind,
                    "window_source": window_source,
                    "char_count_no_spaces": len(chars),
                    "chars_no_spaces": chars,
                    "cluster_fingerprint": [item["cluster"] for item in assignments],
                    "blob_fingerprint": [item["blob_id"] for item in assignments],
                    "char_assignments": assignments,
                    "evidence": text,
                }
            )

    fingerprints.sort(key=lambda item: (item["page"], item["v1_line_index"], item["phrase"]))
    skipped.sort(key=lambda item: (item["page"], item["v1_line_index"], item["phrase"]))
    return {
        "source": {
            "witness": relative(WITNESS_PATH),
            "pre_overlay_baseline": relative(BASELINE_DIR),
        },
        "rule": "Each fingerprint contains exactly one pre-overlay app token per non-space Latin letter in the full phrase.",
        "include_vacat": include_vacat,
        "fingerprint_count": len(fingerprints),
        "skipped_count": len(skipped),
        "fingerprints": fingerprints,
        "skipped_occurrences": skipped,
    }


def write_samples_markdown(inventory: dict[str, Any], index_data: dict[str, Any]) -> None:
    indexed_counts: Counter[str] = Counter(item["phrase"] for item in index_data["fingerprints"])
    lines = [
        "# Editorial Phrase Inventory",
        "",
        "Source: `" + inventory["source"] + "`",
        "",
        "This file lists the full German editorial phrases found in the manuscript-side LLM witness. It does not use the old editorial marker index.",
        "",
    ]
    for item in inventory["phrases"]:
        phrase = item["phrase"]
        lines.extend(
            [
                f"## {phrase}",
                "",
                f"- kind: `{item['kind']}`",
                f"- key: `{item['key']}`",
                f"- characters without spaces: `{item['char_count_no_spaces']}`",
                f"- witness occurrences: `{item['witness_count']}`",
                f"- indexed fingerprints: `{indexed_counts[phrase]}`",
                "- samples:",
            ]
        )
        for sample in item["witness_samples"]:
            text = sample["text"].replace("`", "'")
            lines.append(f"  - p{sample['page']} line {sample['line_index']}: `{text}`")
        lines.append("")
    SAMPLES_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    SAMPLES_MD_PATH.write_text("\n".join(lines), encoding="utf-8")


def apply_index_to_baseline(index_data: dict[str, Any], baseline_dir: Path) -> int:
    by_page: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fingerprint in index_data.get("fingerprints", []):
        if fingerprint.get("kind") != "editorial":
            continue
        by_page[str(fingerprint["page"])].append(fingerprint)

    pages_written = 0
    for page, fingerprints in by_page.items():
        page_path = baseline_dir / f"p{page}.json"
        if not page_path.exists():
            continue
        page_data = load_json(page_path)
        token_by_key: dict[tuple[int, int, int], dict[str, Any]] = {}
        for line in page_data.get("lines", []):
            line_index = int(line.get("line_index", -1))
            for token in line.get("tokens", []):
                key = (
                    line_index,
                    int(token.get("v1_line_index", line.get("v1_line_index", -1))),
                    int(token.get("blob_id")),
                )
                token_by_key[key] = token

        changed = False
        for fingerprint in fingerprints:
            span_count = int(fingerprint["char_count_no_spaces"])
            phrase = str(fingerprint["phrase"])
            for assignment in fingerprint.get("char_assignments", []):
                key = (
                    int(assignment["line_index"]),
                    int(assignment["v1_line_index"]),
                    int(assignment["blob_id"]),
                )
                token = token_by_key.get(key)
                if token is None:
                    continue
                token["label"] = assignment["char"]
                token["review_sheet_source"] = "editorial_fingerprint_index"
                token["review_sheet_raw_label"] = assignment["char"]
                token["editorial_override"] = {
                    "marker_type": phrase,
                    "marker_text": phrase,
                    "span_position": int(assignment["position"]),
                    "span_count": span_count,
                    "confidence": "exact_pre_overlay_fingerprint",
                }
                changed = True
        if changed:
            page_path.write_text(json.dumps(page_data, ensure_ascii=False), encoding="utf-8")
            pages_written += 1
    return pages_written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-limit", type=int, default=5)
    parser.add_argument("--include-vacat", action="store_true", help="Also fingerprint standalone 'leer' vacat labels.")
    parser.add_argument("--apply", action="store_true", help="Apply editorial fingerprints as per-token labels in initial_baseline.")
    args = parser.parse_args()

    rows = load_witness_rows(WITNESS_PATH)
    inventory = build_inventory(rows, sample_limit=args.sample_limit)
    baseline_tokens = load_baseline_tokens(BASELINE_DIR)
    index_data = build_fingerprint_index(
        rows,
        inventory,
        baseline_tokens,
        include_vacat=args.include_vacat,
    )

    write_json(INVENTORY_PATH, inventory)
    write_json(INDEX_PATH, index_data)
    write_samples_markdown(inventory, index_data)

    print(f"[editorial] phrases: {inventory['phrase_count']}")
    print(f"[editorial] fingerprints: {index_data['fingerprint_count']}")
    print(f"[editorial] skipped: {index_data['skipped_count']}")
    print(f"[editorial] wrote {relative(INVENTORY_PATH)}")
    print(f"[editorial] wrote {relative(INDEX_PATH)}")
    print(f"[editorial] wrote {relative(SAMPLES_MD_PATH)}")
    if args.apply:
        pages_written = apply_index_to_baseline(index_data, BASELINE_DIR)
        print(f"[editorial] applied fingerprints to {pages_written} page files")


if __name__ == "__main__":
    main()