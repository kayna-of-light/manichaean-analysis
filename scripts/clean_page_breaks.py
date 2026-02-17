#!/usr/bin/env python3
"""
Clean page-break markers from core extraction JSON files.

The scholarly edition uses `[ ... / ... ]` to indicate a lacuna that spans
a page break. The `/` is NOT content — it's just a column/page separator.
This script normalizes all such brackets to plain `[...]` so the AI never
sees the `/` and never mimics it.

Also cleans OCR slash artifacts in surviving text (e.g., "to/ward" → "toward").
"""
import json
import re
from pathlib import Path

CORE_DIR = Path("output/core/chapters")

# Pattern: bracket containing " / " (page break marker)
# Examples: [ ... / ... ], [e ... / ... ], [ ... / fr], [text (?) ... / ... ]
PAGE_BREAK_BRACKET = re.compile(
    r"\["          # opening bracket
    r"([^\]]*?)"   # group 1: content before /
    r"\s*/\s*"     # the page-break /
    r"([^\]]*?)"   # group 2: content after /
    r"\]"          # closing bracket
)

# OCR slash artifacts in non-bracket text: word/word where both halves
# join into a real word (e.g., "to/ward", "im/measurable")
OCR_SLASH = re.compile(r"(\w{2,})/(\w{2,})")


def clean_page_break_bracket(m: re.Match) -> str:
    """Merge the two halves of a page-break bracket into one bracket."""
    before = m.group(1).strip()
    after = m.group(2).strip()
    
    # Merge: keep text from both halves
    parts = []
    if before and before != "...":
        parts.append(before)
    if after and after != "...":
        parts.append(after)
    
    if not parts:
        return "[...]"
    
    # If either side had "...", keep it
    has_dots_before = "..." in (m.group(1) or "")
    has_dots_after = "..." in (m.group(2) or "")
    
    combined = " ".join(parts)
    
    # If there was partial text on one side and dots on the other,
    # keep the text + dots pattern
    if has_dots_before and has_dots_after:
        if combined.strip() == "":
            return "[...]"
        return f"[{combined}]"
    elif has_dots_before:
        return f"[... {combined}]" if combined else "[...]"
    elif has_dots_after:
        return f"[{combined} ...]" if combined else "[...]"
    else:
        return f"[{combined}]" if combined else "[...]"


def clean_core_text(text: str) -> str:
    """Clean page-break markers and OCR artifacts from core text."""
    # First pass: clean page-break brackets
    cleaned = PAGE_BREAK_BRACKET.sub(clean_page_break_bracket, text)
    
    # Second pass: clean OCR slash artifacts in non-bracket text
    # Only outside brackets — find bracket spans first
    def fix_ocr_slashes(text: str) -> str:
        # Split on brackets, only process non-bracket segments
        parts = re.split(r"(\[[^\]]*\])", text)
        result = []
        for i, part in enumerate(parts):
            if part.startswith("[") and part.endswith("]"):
                result.append(part)  # bracket — don't touch
            else:
                result.append(OCR_SLASH.sub(r"\1\2", part))
        return "".join(result)
    
    cleaned = fix_ocr_slashes(cleaned)
    return cleaned


def main():
    files = sorted(CORE_DIR.glob("ch_*.json"))
    print(f"Scanning {len(files)} core chapter files...")
    
    total_changes = 0
    files_changed = 0
    
    for f in files:
        data = json.load(open(f, encoding="utf-8"))
        changed = False
        
        for p in data.get("paragraphs", []):
            old_text = p.get("core_text")
            if not old_text:
                continue
            new_text = clean_core_text(old_text)
            if new_text != old_text:
                # Count changes
                old_slashes = len(PAGE_BREAK_BRACKET.findall(old_text))
                ocr_fixes = len(OCR_SLASH.findall(old_text)) - len(OCR_SLASH.findall(new_text))
                
                if old_slashes > 0 or ocr_fixes > 0:
                    pnum = p["paragraph_number"]
                    print(f"  {f.name} ¶{pnum}: {old_slashes} page-breaks, {ocr_fixes} OCR fixes")
                    total_changes += old_slashes + max(0, ocr_fixes)
                
                p["core_text"] = new_text
                changed = True
        
        if changed:
            files_changed += 1
            with open(f, "w", encoding="utf-8") as out:
                json.dump(data, out, indent=2, ensure_ascii=False)
    
    print(f"\nDone: {total_changes} changes in {files_changed} files")


if __name__ == "__main__":
    main()
