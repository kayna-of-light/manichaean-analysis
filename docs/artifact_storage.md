# Artifact Storage

Storage follows provenance, not the directory name. An `output/` file may be an
expensive model response, a human correction, or a cheap deterministic derivative.
Git retains the first two and excludes known rebuildable products. The Drive mirror
is an additional safety copy of both retained and ignored data, not evidence that a
particular local file has already been backed up.

## What Git Keeps

- Final Ancient Word publication PDFs in `output/pdfs/`, including
	`The_Ancient_Word.pdf` and versioned `The_Ancient_Word_v*.pdf` editions. These are
	published deliverables even though the PDF generators can rebuild them.
	Temporary `*_tmp.pdf` builds remain ignored.
- Source OCR JSON and captured source text, including `data/*.pdf.json` and
	`output/texts/`. A new OCR service call or a new download need not reproduce them.
- Original Coptic model transcriptions, including both pass texts and two-pass JSON
	under `output/projects/kephalaia_v2/coptic/transcriptions/`.
- LLM-cleaned chapters, discovered corpus metadata, extractions, restorations,
	readings, proposed terms, reviews, corrected text, and model checkpoints.
- Manual and trusted corrections, editorial fingerprints, glyph overrides,
	subcluster labels, and the saved cluster assignments those labels address.
- Existing OCR geometry JSON, reviewer baseline snapshots, crop metadata, and
	provenance summaries. These retain the coordinates and identifiers used by
	reviewed decisions; do not replace them with a fresh clustering/segmentation run
	merely because a producer script exists.

The three `_assignments.json` cluster maps are currently about 66-71 MiB each.
They exceed GitHub's 50 MiB warning threshold but not its 100 MiB rejection limit.
They are retained deliberately: regenerating cluster IDs without migrating their
reviewed labels could silently misapply the labels. The smaller projected maps,
subassignments, and overrides are retained alongside them.

## What Git Excludes

The root `.gitignore` uses product-specific patterns, not a blanket `output/`,
`*.json`, or image exclusion. New or unclassified output remains eligible for Git
until its provenance is established.

| Rebuildable product | Retained inputs / producer |
|---|---|
| Other `output/pdfs/*.pdf` and temporary `*_tmp.pdf` builds | Saved text and JSON; PDF generators in `scripts/tools/`; final Ancient Word editions are explicitly retained |
| `kephalaia/analysis/chapters/*.json` | Cleaned chapters and corpus metadata; `scripts/projects/kephalaia/stage_3_score.py` |
| `kephalaia_v2/scores/*.json` | Saved chapters and corpus metadata; `scripts/projects/kephalaia_v2/stage_3b_score.py` |
| `kephalaia_v2/coptic/images/*.jpg` | Source PDFs restored from Drive; `scripts/projects/kephalaia_v2/stage_0_extract.py` |
| OCR PNG previews, cluster/context montages, and body-crop JPGs | Saved source/geometry/cluster data; OCR pipeline and sheet builders in `scripts/projects/kephalaia_ocr/` |
| Contextual-review streams and reports | Saved cluster mappings, overrides, split geometry; `build_contextual_review.py` |
| LLM-witness streams, derived review JSON, recommendations, and reports | Saved original transcriptions and contextual-review data; `build_llm_witness.py` |
| v2 deskewed JPGs | Saved Kraken geometry and source images; `deskew_and_crop.py` |
| v2 line/body split JPGs and review images | Deskewed pages; `split_line_numbers_body.py` |
| v2 body-geometry page JSON, masks, and review images | Body crops and retained settings; `polygonize_body_crops.py` |

Project-relative names in the table live under `output/projects/`. The last three
builders are in `scripts/projects/kephalaia_ocr_v2/`. Crop metadata and summaries
remain tracked even where their neighboring images are ignored.

Despite its name, `build_llm_witness.py` makes no model calls. It aligns the
already-saved transcriptions to reviewed OCR data. Its large
`composite_line_sequences.jsonl` and `review_llm_witness.json` can be rebuilt; the
original model transcriptions must stay in Git.

For example, rebuild a specific cluster's contextual and witness products from
the repository root, after restoring any required source PDFs and rebuilding
source/crop images:

```powershell
python scripts/projects/kephalaia_ocr/build_contextual_review.py --clusters-dir output/projects/kephalaia_ocr/clusters_shape_padded_k120
python scripts/projects/kephalaia_ocr/build_llm_witness.py --context-dir output/projects/kephalaia_ocr/contextual_review/clusters_shape_padded_k120 --out-dir output/projects/kephalaia_ocr/llm_witness/clusters_shape_padded_k120
```

Use the matching saved cluster name and split geometry for other cluster families.
Do not rerun LLM stages to rebuild these derivatives. Required Python dependencies,
source PDFs, and (for fresh Kraken segmentation) the WSL Kraken runtime are still
needed; a clean clone alone does not contain every source asset.

## Before Pushing

Check the entire unpublished history, not just the current working tree:

```powershell
python scripts/check_git_artifact_sizes.py
```

The default range is `origin/main..HEAD`. Use `--base <published-ref>` and
`--head <local-ref>` when checking another branch. The check exits nonzero for any
blob over 100 MiB, including a blob added in one commit and deleted in a later
one. Blobs over 50 MiB produce warnings. The total shown is uncompressed blob
size, not the pack size sent to GitHub. This is an explicit check, not an installed
Git hook; run it before each push.

Adding an ignore rule does not remove already-committed files. If unpublished
history contains an ignored generated file, rewrite the introducing commit (and
its local descendants) rather than adding a deletion-only commit. Preserve local
files, uncommitted work, and recovery refs before rewriting. Never rewrite
published history or push recovery refs as part of routine artifact cleanup.

## Drive Mirror and Recovery

The default repository sync mirrors `output/`, `data/`, and `manual_reviewer/data/` to:

```text
My Drive/.git-data/manichaean-analysis/output/
My Drive/.git-data/manichaean-analysis/data/
My Drive/.git-data/manichaean-analysis/manual_reviewer/data/
```

Run the mirror from the repository root:

```powershell
conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py
```

The script reuses the working Google Drive OAuth client and token from the sibling `literary-compilation/secrets/` folder. Set `LITERARY_COMPILATION_SECRETS` or pass `--oauth-client` / `--oauth-token` if the secrets live elsewhere. It creates missing Drive folders, uploads missing or changed files, skips files that already match by checksum, and deletes remote files that no longer exist locally after confirmation. The default sync includes `output/`, `data/`, and `manual_reviewer/data/` when present; a clean checkout without generated local folders skips those missing default sources. Use `--source output`, `--source data`, or `--source manual_reviewer/data` for a targeted single-folder sync.

Normal sync is a true local-to-Drive mirror. If the script finds remote files that are not present locally, it prints a warning and requires typing `DELETE_REMOTE` before deleting them. Use `--yes` for an already-reviewed non-interactive run, or `--no-delete` for upload/update-only behavior.

For a fast complete safety backup, create and upload a single archive:

```powershell
New-Item -ItemType Directory -Force temp/gdrive_archives
tar -czf temp/gdrive_archives/manichaean-analysis-output-YYYYMMDD.tar.gz output
conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --archive temp/gdrive_archives/manichaean-analysis-output-YYYYMMDD.tar.gz
```

Archive uploads go to:

```text
My Drive/.git-data/manichaean-analysis/archives/
```

For full `output/` disaster recovery, use the archive. The archive is the complete safety copy; the per-file `output/` mirror is useful for targeted restores, but it can lag if a full mirror pass did not finish.

Restore the latest Drive archive into the repository root:

```powershell
conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --restore-archive --retries 12
```

Restore a specific Drive archive by name:

```powershell
conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --restore-archive manichaean-analysis-output-YYYYMMDD.tar.gz --retries 12
```

If the archive was downloaded manually, extract it into the repository root:

```powershell
tar -xzf temp/gdrive_archives/manichaean-analysis-output-YYYYMMDD.tar.gz
```

Verify a local archive has been fully restored:

```powershell
conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --verify-archive temp/gdrive_archives/manichaean-analysis-output-YYYYMMDD.tar.gz
```

Useful options:

```powershell
# Compare local files to the Drive mirror without changing anything
conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --status --source output --retries 12

# Preview without uploading. The limit applies per source folder.
conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --dry-run --limit 10

# Sync only one source folder
conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --source data --retries 12
conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --source manual_reviewer/data --retries 12

# After reviewing the warning, confirm remote cleanup non-interactively
conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --yes --retries 12

# Upload/update only, without deleting remote extras
conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --no-delete --retries 12

# Retry harder on flaky network connections
conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --retries 12
```

To restore the Drive mirror into a fresh clone:

```powershell
conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --restore --retries 12
```

This restores the per-file mirrors (`output/`, `data/`, and `manual_reviewer/data/`). For complete generated `output/` recovery, prefer `--restore-archive` unless a verified full per-file mirror is known to exist.

Restore creates or updates local files from Drive. It does not delete local extras unless explicitly requested:

```powershell
conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --restore --prune-local --retries 12
```

When `--prune-local` finds local files missing from Drive, it requires typing `DELETE_LOCAL` before deleting them. Use `--dry-run` first to preview restore or cleanup actions.

Git keeps source code, scripts, findings, documentation, and the research data
listed above. Rebuild excluded deterministic products from retained inputs or
restore their saved copies from Drive when needed. Keep the complete Drive mirror
for source PDFs and live reviewer state that are not in Git.

Large source artifacts that exceed GitHub's warning threshold should also be stored in Drive rather than committed directly. Use `--archive` for one-off preservation when a source OCR dump is too large for normal Git history.
