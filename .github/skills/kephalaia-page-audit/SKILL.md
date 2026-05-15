---
name: kephalaia-page-audit
description: Per-page visual audit of Kephalaia v2 page JSON files against the manuscript image and Gardner translation. Use when asked to audit, fix, verify, or correct page JSON files in output/projects/kephalaia_v2/pages/. Keywords: kephalaia, page audit, leiden, brackets, lacuna, restoration, uncertain, leer, scriptio continua, Polotsky, Böhlig.
---

# Kephalaia Page Audit Skill

## When to use

Whenever you are asked to audit, verify, correct, or fix entries in `output/projects/kephalaia_v2/pages/p_NNN.json` — especially in the context of working through `temp/page_audit_chores.md`.

This is a **manual, visual** workflow. Do NOT call Azure / Anthropic to re-translate. The current chore set exists precisely because rerunning stage 1 is too expensive.

## Background

Stage 1 (`scripts/projects/kephalaia_v2/stage_1_translate.py`) was updated to capture page-image conventions correctly. Existing files in `output/projects/kephalaia_v2/pages/` were produced under earlier rules. The mechanical migrations have already been done in a prior pass (`leer` → `break_after`, German destruction markers → `partial` field on lacunae). The audit pass is the residue: things only the human eye on the printed page can verify.

## Sources

For each page `N`, four sources must be consulted:

| Source | Path | Use |
|---|---|---|
| Page image | `output/projects/kephalaia_v2/coptic/images/keph_pNNN.jpg` | Authoritative — the manuscript photo with Polotsky/Böhlig print conventions |
| Pass 2 OCR | `output/projects/kephalaia_v2/coptic/transcriptions/keph_pNNN_pass2.txt` | Auxiliary; can be wrong, the image rules |
| Existing JSON | `output/projects/kephalaia_v2/pages/p_NNN.json` | The file you edit in place |
| Gardner English | `output/texts/Kephalaia_of_the_Teacher.md` | Second witness — section between inline markers `(N)` and `(N+1)` |

How to read Gardner for page `N` (from `scripts/transcribe_coptic_v2.py`):

```python
import re, pathlib
text = pathlib.Path("output/texts/Kephalaia_of_the_Teacher.md").read_text(encoding="utf-8")
start = re.search(rf"\({N}\)", text)
end = re.search(rf"\({N+1}\)", text[start.end():])
section = text[start.start():(start.end() + end.start()) if end else (start.start()+3000)]
```

## What the schema says now

Apparatus item is `{id, segment, type ("lacuna" | "restoration"), ...}`.

For `lacuna`:
- `est_chars: integer | null`. `null` = "extent unknown"; never `0`.
- `partial: string` (optional). Either visible letter traces OR the verbatim German editor marker (`abgerieben`, `zerstört`, `verwischt`, `geringe Spuren`, `unlesbar`, `nicht zu lesen`, `fast völlig zerstört`, or compounds like `verwischt und abgerieben`).

For `restoration`:
- `coptic, english, basis: string`.
- `uncertain: bool` (optional, default false). True when the editor printed the letters with subscript dots OR followed them with `(?)`. The text is on the page, but the editor is doubtful.

`leer` is **not** a lacuna. It is a deliberate scribal blank space (vacat) that marks a section boundary. It is captured at the segment level via `break_after: true`, never in apparatus. Mid-line `leer` splits the segment into two entries with the same `n` and sequential `i`; the first gets `break_after: true`.

Coptic is **scriptio continua** — no spaces. Any whitespace inside a Coptic line in the OCR is editorial print artifact; collapse it. (English keeps its spaces.)

## Per-page workflow

Do these in order. Do not skip steps.

### Step 1 — Read the page sources

Read in parallel:
1. `read_file` on the existing JSON (full).
2. `read_file` on `keph_pNNN_pass2.txt`.
3. `view_image` on `keph_pNNN.jpg`.
4. Read the Gardner section for page `N` with the regex above (or use `grep_search` for `\(N\)`).

### Step 2 — Walk every apparatus entry against the image

For each entry in `apparatus`:

**If `type == "lacuna"`:**
- Locate the gap on the printed page.
- If the print shows dots: `est_chars` should be the dot count. Correct it if wrong.
- If the print shows empty brackets `[ ]` with no dots: `est_chars` must be `null`.
- If the print shows a German marker (`abgerieben`, `zerstört`, etc.): `est_chars: null`, and `partial` should hold the verbatim German marker. If `partial` is missing, add it.
- If two adjacent same-kind apparatus entries exist with no certain text between them in the segment (a margin-bracket artifact): MERGE into one entry, sum the `est_chars`, update placeholders.
- If the entry was a hidden `leer` (rare; mostly migrated already): remove it, set `break_after: true` on the segment, renumber.

**If `type == "restoration"`:**
- Verify the `coptic` field matches the bracketed letters on the page.
- If the bracket on the page contains MIXED content (letters + dots): the entry must be **decomposed**. Split into separate entries by run-of-same-kind. Worked example for `[ⲣⲟ . . ⲃ]ⲣⲏⲧⲉ`:
  - `restoration` `"ⲣⲟ"`
  - `lacuna` `est_chars=2`
  - `restoration` `"ⲃ"`
  - plain text `ⲣⲏⲧⲉ` in the segment (no apparatus)
- If the editor printed the letters with subscript dots OR followed them with `(?)`: set `uncertain: true`. Otherwise omit (default false).

### Step 3 — Coptic scriptio continua

Walk every `coptic` string in `header` and each `lines[i]`. Collapse any internal whitespace runs in the Coptic. Keep placeholders intact. Do NOT touch English fields.

Quick check: if a `coptic` string contains a regular space character that is not part of a `{N}` placeholder boundary, it is wrong unless it falls between text and a placeholder.

### Step 4 — Renumber if anything changed

After decomposition or merging, the apparatus IDs and `{N}` placeholders may have drifted. Apparatus IDs MUST be `0..len(apparatus)-1` sequential. Every `{N}` that appears in any `coptic` or `english` string MUST have a matching apparatus entry with `id: N`. The same `{N}` must appear at the same logical position in both `coptic` and `english`.

If you renumbered, do a final scan: count distinct `{N}` placeholders in lines+header, count apparatus entries — they must match.

### Step 5 — Save and check off

Write the updated JSON. Run `get_errors` if Python tooling is involved (it isn't here, but the file should remain valid JSON — verify by reading it back if any complex edit was made). Mark the page as `[x]` in `temp/page_audit_chores.md`.

## Stub pages

`p_149.json` and `p_161.json` are 152/154-byte stubs (page mostly destroyed, no body content). Verify they are syntactically valid and consistent with the schema, then check off without further work.

## Standing rules

- **No scripts that bulk-rewrite `output/`.** Use `multi_replace_string_in_file` for edits.
- **Image rules; pass2 is auxiliary.** When the OCR disagrees with the page, the page wins.
- **Gardner is a SECOND witness, not authority.** It informs what the line means; it does not authorize changes that the image does not support.
- **No re-translation.** This audit fixes structural fidelity to the print conventions. The Coptic and English content stays as it is unless the image proves it wrong at a small character level.
- **Mark progress.** Every saved page gets checked off in `temp/page_audit_chores.md`.

## Context budget reality

Each page costs roughly: 1 image view + 3 file reads + 1 file write. A single conversation will not finish 282 pages. Work in stride from where the chore list is currently incomplete; resume in the next conversation from the next unchecked page.
