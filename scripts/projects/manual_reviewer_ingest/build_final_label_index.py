#!/usr/bin/env python3
"""Build a compact display_label index for the manual reviewer webapp.

Reads composite_line_sequences.jsonl (the same source the review sheet uses)
and resolves a display label for EVERY token using the same fallback chain as
build_page_review_sheet.py's choose_display_label(). This ensures the webapp
shows exactly what the review sheet shows.

Fallback chain (mirrors review sheet):
  1. final_label (with combining marks from geometry)
  2. manual_override.label
  3. geometric_override.label
  4. subcluster_override.label
  5. raw label
  6. candidates[0] (first displayable)
  7. llm_alignment.llm_bases / llm_text
  8. "?" (unresolved)
"""
import json
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CLUSTER = "clusters_shape_padded_split_bodycrop_corrected_k240"
COMPOSITE = (
    REPO / "output" / "projects" / "kephalaia_ocr" / "llm_witness"
    / CLUSTER / "composite_line_sequences.jsonl"
)
OUT = REPO / "output" / "projects" / "kephalaia_manual_reviewer" / "final_label_index.json"

SPECIAL_DISPLAY = {
    "_lacuna_dot": ".",
    "_middle_dot": "\u00b7",
    "_unknown": "?",
    "_left_square_bracket": "[",
    "_right_square_bracket": "]",
    "_connected_needs_literal_reading": "?",
    "_literal_connected_reference": "?",
    "_editorial_marker": "E",
}

COMBINING_MARKS = {
    "overline": "\u0304",
    "horizontal_mark": "\u0304",
    "above_dot": "\u0307",
    "dot": "\u0307",
    "diaeresis": "\u0308",
    "below_dot": "\u0323",
}
MARK_ORDER = ("overline", "horizontal_mark", "diaeresis", "above_dot", "dot", "below_dot")
OVERLINE_MARK_KINDS = {"overline", "horizontal_mark"}
OVERLINE_CODEPOINTS = {"\u0304", "\u0305", "\ufe24", "\ufe25", "\ufe26"}
GROUP_BLOCKED_ABOVE_CODEPOINTS = OVERLINE_CODEPOINTS | {"\u0307", "\u0308"}
CONJOINING_MACRON_LEFT = "\ufe24"
CONJOINING_MACRON_RIGHT = "\ufe25"
CONJOINING_MACRON_MIDDLE = "\ufe26"


def is_coptic_text(s: str) -> bool:
    if not s:
        return False
    for ch in s:
        if unicodedata.combining(ch):
            continue
        cp = ord(ch)
        # Coptic letters in Greek block (0x03E2-0x03EF) or Coptic block (0x2C80-0x2CFF)
        if 0x03E2 <= cp <= 0x03EF:
            continue
        if 0x2C80 <= cp <= 0x2CFF:
            continue
        return False
    return True


def label_to_text(label: str | None) -> str | None:
    if label is None:
        return None
    if is_coptic_text(label):
        return label
    return SPECIAL_DISPLAY.get(label)


def strip_combining_marks(text: str) -> str:
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def add_combining_marks(text: str, mark_kinds: list[str]) -> str:
    from collections import Counter
    counts = Counter(mark_kinds)
    marks: list[str] = []
    for kind in MARK_ORDER:
        if counts[kind] <= 0:
            continue
        if kind == "above_dot" and counts[kind] >= 2:
            marks.append(COMBINING_MARKS["diaeresis"])
            continue
        mark = COMBINING_MARKS.get(kind)
        if mark:
            marks.append(mark)
    if not marks or not is_coptic_text(text):
        return text
    # Strip existing marks first, then re-apply (same as review sheet)
    base = strip_combining_marks(text)
    return base + "".join(marks)


def resolve_display_label(u: dict) -> str:
    """Resolve display label using the same fallback chain as the review sheet."""
    text: str | None = None
    is_llm_rescue = False

    # 1. final_label
    final_label = u.get("final_label")
    if final_label and is_coptic_text(str(final_label)):
        text = str(final_label)

    # 2. manual_override
    if text is None:
        manual = u.get("manual_override") or {}
        ml = manual.get("label")
        text = label_to_text(ml)

    # 3. geometric_override
    if text is None:
        geo = u.get("geometric_override") or {}
        gl = geo.get("label")
        text = label_to_text(gl)

    # 4. subcluster_override
    if text is None:
        sub = u.get("subcluster_override") or {}
        sl = sub.get("label")
        text = label_to_text(sl)

    # 5. raw label
    if text is None:
        raw = u.get("label")
        text = label_to_text(raw)

    # 6. candidates[0]
    if text is None:
        candidates = u.get("candidates", [])
        for c in candidates:
            t = label_to_text(str(c))
            if t is not None:
                text = t
                break

    # 7. llm_alignment rescue
    if text is None:
        alignment = u.get("llm_alignment") or {}
        llm_bases = alignment.get("llm_bases")
        llm_text = alignment.get("llm_text")
        if llm_text and is_coptic_text(str(llm_text)):
            text = str(llm_text)
            is_llm_rescue = True
        elif llm_bases and is_coptic_text(str(llm_bases)):
            text = str(llm_bases)
            is_llm_rescue = True

    # 8. unresolved
    if text is None:
        text = "?"

    # Apply combining marks at the end (same as review sheet):
    # marks apply to ALL paths except llm_rescue, and only if text is Coptic
    mark_kinds = [str(m.get("kind")) for m in (u.get("attached_marks") or []) if m.get("kind")]
    if mark_kinds and not is_llm_rescue and is_coptic_text(text):
        text = add_combining_marks(text, mark_kinds)

    return text


def primary_overline_mark_id(u: dict) -> int | None:
    """Return the mark ID of the primary overline/horizontal_mark, or None."""
    for mark in u.get("attached_marks") or []:
        if mark.get("kind") in ("overline", "horizontal_mark") and mark.get("id") is not None:
            return int(mark["id"])
    return None


def conjoining_macron_for(position: int, count: int) -> str:
    """Return the appropriate conjoining macron for position in a group."""
    if count <= 1:
        return COMBINING_MARKS["overline"]  # plain U+0304
    if position == 0:
        return CONJOINING_MACRON_LEFT
    if position == count - 1:
        return CONJOINING_MACRON_RIGHT
    return CONJOINING_MACRON_MIDDLE


def strip_overline_codepoints(text: str) -> str:
    """Remove all overline-related combining chars from text."""
    return "".join(ch for ch in text if ch not in OVERLINE_CODEPOINTS)


def strip_group_blocked_above_codepoints(text: str) -> str:
    """Remove above marks that cannot coexist with an overline group."""
    return "".join(ch for ch in text if ch not in GROUP_BLOCKED_ABOVE_CODEPOINTS)


def apply_conjoining_overline(text: str, position: int, count: int) -> str:
    """Replace any overline mark in text with the appropriate conjoining macron."""
    if not is_coptic_text(strip_overline_codepoints(text)):
        return text
    # Strip overline codepoints, then append the correct conjoining variant
    base = strip_overline_codepoints(text)
    # Preserve non-overline combining marks
    non_overline_marks = "".join(ch for ch in text if unicodedata.combining(ch) and ch not in OVERLINE_CODEPOINTS)
    return base + conjoining_macron_for(position, count) + non_overline_marks


def main() -> None:
    if not COMPOSITE.exists():
        print(f"ERROR: {COMPOSITE} not found")
        return

    # Structure: { "page": { "line_index": { "blob_id": "label" | [label, overline_mark_id] } } }
    index: dict[str, dict[str, dict[str, str | list]]] = {}
    total = 0
    indexed = 0

    with open(COMPOSITE, "r", encoding="utf-8") as f:
        for raw in f:
            if not raw.strip():
                continue
            line = json.loads(raw)
            page = str(line.get("page", ""))
            line_idx = str(line.get("line_index", ""))
            units = line.get("units", [])

            # First pass: resolve labels and collect overline mark IDs
            resolved: list[tuple[str, str, int | None]] = []  # (blob_id, display, ovl_id)
            for u in units:
                total += 1
                display = resolve_display_label(u)
                blob_id = str(u.get("blob_id", ""))
                ovl_id = primary_overline_mark_id(u)
                resolved.append((blob_id, display, ovl_id))

            # Second pass: detect overline groups and apply conjoining macrons
            i = 0
            while i < len(resolved):
                blob_id, display, ovl_id = resolved[i]
                if ovl_id is not None:
                    # Find extent of group sharing this mark ID
                    j = i + 1
                    while j < len(resolved) and resolved[j][2] == ovl_id:
                        j += 1
                    group_size = j - i
                    if group_size > 1:
                        # Multi-char group: store base label with mark ID; UI renders conjoining macrons.
                        for pos in range(group_size):
                            g_blob_id, g_display, g_ovl_id = resolved[i + pos]
                            g_display = strip_group_blocked_above_codepoints(g_display)
                            if page not in index:
                                index[page] = {}
                            if line_idx not in index[page]:
                                index[page][line_idx] = {}
                            index[page][line_idx][g_blob_id] = [g_display, g_ovl_id]
                            indexed += 1
                    else:
                        # Single-char overline: store as plain string (U+0304 already in display)
                        if page not in index:
                            index[page] = {}
                        if line_idx not in index[page]:
                            index[page][line_idx] = {}
                        index[page][line_idx][blob_id] = display
                        indexed += 1
                    i = j
                else:
                    if page not in index:
                        index[page] = {}
                    if line_idx not in index[page]:
                        index[page][line_idx] = {}
                    index[page][line_idx][blob_id] = display
                    indexed += 1
                    i += 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    size_kb = OUT.stat().st_size / 1024
    print(f"Done: {indexed}/{total} tokens indexed ({size_kb:.0f} KB)")
    print(f"Output: {OUT}")


if __name__ == "__main__":
    main()
