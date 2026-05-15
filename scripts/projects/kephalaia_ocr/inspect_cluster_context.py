#!/usr/bin/env python3
"""Print textual and cluster-neighbor contexts for one OCR cluster."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ASSIGNMENTS = REPO / "output" / "projects" / "kephalaia_ocr" / "clusters" / "_assignments.json"
CHAR_MAP = REPO / "output" / "projects" / "kephalaia_ocr" / "clusters" / "_char_assignments.json"
PAGES_V2 = REPO / "output" / "projects" / "kephalaia_v2" / "pages"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def page_line_text(page: str, line_index: int) -> str:
    if "_" in page:
        return "<continuation page>"
    path = PAGES_V2 / f"p_{page}.json"
    if not path.exists():
        return "<no page json>"
    data = load_json(path)
    match = next((line for line in data.get("lines", []) if int(line.get("i", -1)) == line_index), None)
    return match.get("coptic", "<line not found>") if match else "<line not found>"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cluster", type=int)
    parser.add_argument("--samples", type=int, default=12)
    parser.add_argument("--window", type=int, default=5)
    args = parser.parse_args()

    assignments = load_json(ASSIGNMENTS)
    char_map = load_json(CHAR_MAP)
    reverse = {cid: char for char, ids in char_map.items() for cid in ids}
    by_line: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for item in assignments:
        by_line[(item["page"], int(item["line_index"]))].append(item)

    items = [item for item in assignments if int(item["cluster"]) == args.cluster]
    print(f"cluster {args.cluster:02d}: {len(items)} instances")
    if not items:
        return

    # Spread samples through the corpus, with no duplicate page unless needed.
    picked = []
    seen_pages = set()
    step = max(1, len(items) // (args.samples * 3))
    for item in items[::step]:
        if item["page"] in seen_pages and len(seen_pages) < args.samples:
            continue
        picked.append(item)
        seen_pages.add(item["page"])
        if len(picked) >= args.samples:
            break

    for sample in picked:
        page = sample["page"]
        line_index = int(sample["line_index"])
        line_items = sorted(by_line[(page, line_index)], key=lambda z: z["warped_bbox"][0])
        pos = next(i for i, item in enumerate(line_items) if int(item["blob_id"]) == int(sample["blob_id"]))
        window = line_items[max(0, pos - args.window):pos + args.window + 1]
        seq = []
        for item in window:
            cid = f"{int(item['cluster']):02d}"
            label = reverse.get(cid, "?")
            left = "[" if int(item["blob_id"]) == int(sample["blob_id"]) else ""
            right = "]" if int(item["blob_id"]) == int(sample["blob_id"]) else ""
            seq.append(f"{left}c{cid}:{label}{right}")
        print("\n---")
        print(
            f"p{page} line_index={line_index} blob={sample['blob_id']} "
            f"x={sample['warped_bbox'][0]}-{sample['warped_bbox'][2]}"
        )
        print(page_line_text(page, line_index))
        print(" ".join(seq))


if __name__ == "__main__":
    main()
