# Artifact Storage

Generated artifacts belong in Google Drive, not Git history. Source data also gets a Drive mirror so oversized OCR dumps and recovered source material have an external safety copy.

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

Git should keep source code, scripts, findings, documentation, and normal-sized source data. Large generated output should be restored from Drive when needed.

Large source artifacts that exceed GitHub's warning threshold should also be stored in Drive rather than committed directly. Use `--archive` for one-off preservation when a source OCR dump is too large for normal Git history.
