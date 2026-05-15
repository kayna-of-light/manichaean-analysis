# Kephalaia OCR Current Pipeline

Last verified: 2026-05-09

This note records the current authoritative Kephalaia OCR review stack after the
body-crop split correction work. The goal is to keep reviewed results in data
files, not in page-specific code paths.

## Authoritative Data Stack

- Base page segmentation and body crops:
  `output/projects/kephalaia_ocr/pages/`
- Body-crop provenance cluster layer used to derive split targets:
  `output/projects/kephalaia_ocr/clusters_shape_padded_k120_bodycrop_test/`
- Forced split target overlay for missed connected Coptic parents:
  `output/projects/kephalaia_ocr/split_corrections/forced_connected_targets.json`
- Corrected child split layer:
  `output/projects/kephalaia_ocr/pages_base_split_chars_bodycrop_corrected/`
- Current corrected child cluster and assignment layer:
  `output/projects/kephalaia_ocr/clusters_shape_padded_split_bodycrop_corrected_k240/`
- Current contextual review:
  `output/projects/kephalaia_ocr/contextual_review/clusters_shape_padded_split_bodycrop_corrected_k240/`
- Current constrained witness:
  `output/projects/kephalaia_ocr/llm_witness/clusters_shape_padded_split_bodycrop_corrected_k240/`
- Canonical visible review sheets:
  `output/projects/kephalaia_ocr/page_review_sheets/`
- Canonical sheet manifests and renderer HTML:
  `temp/projects/kephalaia_ocr/page_review_sheets/`

`output/projects/kephalaia_ocr/page_review_sheets/` should contain PNG files
only. JSON and HTML review artifacts belong under `temp/`.

## Current Rebuild Commands

From the repository root, using the `manichaean` conda environment:

```powershell
& "$env:USERPROFILE\.conda\envs\manichaean\python.exe" scripts/projects/kephalaia_ocr/build_contextual_review.py --clusters-dir output/projects/kephalaia_ocr/clusters_shape_padded_split_bodycrop_corrected_k240 --context-dir output/projects/kephalaia_ocr/contextual_review/clusters_shape_padded_split_bodycrop_corrected_k240 --split-dir output/projects/kephalaia_ocr/pages_base_split_chars_bodycrop_corrected
& "$env:USERPROFILE\.conda\envs\manichaean\python.exe" scripts/projects/kephalaia_ocr/build_llm_witness.py --context-dir output/projects/kephalaia_ocr/contextual_review/clusters_shape_padded_split_bodycrop_corrected_k240 --out-dir output/projects/kephalaia_ocr/llm_witness/clusters_shape_padded_split_bodycrop_corrected_k240 --split-dir output/projects/kephalaia_ocr/pages_base_split_chars_bodycrop_corrected
& "$env:USERPROFILE\.conda\envs\manichaean\python.exe" scripts/projects/kephalaia_ocr/build_page_review_sheet.py --page 010 --page 011 --page 012 --page 013 --context-dir output/projects/kephalaia_ocr/contextual_review/clusters_shape_padded_split_bodycrop_corrected_k240 --witness-dir output/projects/kephalaia_ocr/llm_witness/clusters_shape_padded_split_bodycrop_corrected_k240 --split-dir output/projects/kephalaia_ocr/pages_base_split_chars_bodycrop_corrected
```

The current review artifacts should be regenerated with explicit `--context-dir`,
`--witness-dir`, and `--split-dir` arguments so they do not silently fall back to
the older base cluster layer.

## Root Split Regeneration

The corrected split stack was produced from the body-crop provenance layer plus
the forced target overlay:

```powershell
& "$env:USERPROFILE\.conda\envs\manichaean\python.exe" scripts/projects/kephalaia_ocr/split_connected_base_blobs.py --witness output/projects/kephalaia_ocr/llm_witness/clusters_shape_padded_k120_bodycrop_test/composite_line_sequences.jsonl --clusters-dir output/projects/kephalaia_ocr/clusters_shape_padded_k120_bodycrop_test --force-targets output/projects/kephalaia_ocr/split_corrections/forced_connected_targets.json --out-dir output/projects/kephalaia_ocr/pages_base_split_chars_bodycrop_corrected
& "$env:USERPROFILE\.conda\envs\manichaean\python.exe" scripts/projects/kephalaia_ocr/cluster_base_global_shape.py --split-dir output/projects/kephalaia_ocr/pages_base_split_chars_bodycrop_corrected --output-name clusters_shape_padded_split_bodycrop_corrected_k240 --n-clusters 240 --max-workers 8 --montage 128
& "$env:USERPROFILE\.conda\envs\manichaean\python.exe" scripts/projects/kephalaia_ocr/project_split_child_labels.py --old-clusters output/projects/kephalaia_ocr/clusters_shape_padded_k120_bodycrop_test --new-clusters output/projects/kephalaia_ocr/clusters_shape_padded_split_bodycrop_corrected_k240
```

The forced target file does not assign glyph labels. It only forces root
segmentation for parent blobs that visual review showed were still connected.
Child labels then flow through the normal split-cluster assignment data.

The splitter also detects coherent wide single-label Coptic clusters before
review-sheet rendering. It reads the full body-crop cluster assignment layer,
supplements missing projected labels with strong witness-majority single-letter
labels, and selects whole cluster families whose width distribution is too wide
for the inferred single character. This catches fused parents that masquerade as
confident single glyphs. The current automatic wide-family pass selects old
cluster `086` (`ⲧⲧ` shapes previously inferred as single `ⲡ`) and leaves old
cluster `089` alone because it is a tall true single `ⲡ` family.

## Verified Invariants

- Current corrected split summary: 3,856 targets, 1,038 auto-wide targets,
  3 forced targets, 0 split failures.
- Current auto-wide target group: old cluster `086`, 1,038 members, all split;
  full-corpus coverage check found 0 unsplit old `086` parents.
- Current target reasons: 1,904 `already_multi_char_label`,
  1,007 `needs_literal_reading`, 915 `auto_wide_single_cluster`,
  27 `llm_suggests_connected_reading`, and 3 `manual_force_connected_split`.
- Current corrected split child count: 8,285 split children from
  `pages_base_split_chars_bodycrop_corrected/`.
- Current corrected cluster assignments are in
  `clusters_shape_padded_split_bodycrop_corrected_k240/_char_assignments_projected.json`.
- Current corrected cluster layer contains 336,736 blobs across 240 clusters.
- Current contextual review and witness read current corrected cluster data and
  split data through command arguments and cluster summary metadata.
- Current constrained witness invariant: zero multi-character Coptic
  `final_label`s and zero unsplit `llm_suggests_connected_reading` units.
- Example root auto-wide proof: p011 line 9 parent blob 36 now splits into child
  blob 55 = `ⲧ` and child blob 56 = `ⲧ`, rendered on the p011 sheet at display
  indices 367 and 368.
- Page review sheet indices are display indices only. Stable review identity is
  `page`, `line_index`, `blob_id`, and split provenance fields such as
  `parent_blob_id`, `split_child_index`, and `cut_positions`.
- The canonical page review output directory is `page_review_sheets`, not
  `page_review_sheets_split_bodycrop_k240` or any other alternate folder.