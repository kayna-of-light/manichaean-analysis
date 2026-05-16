# Artifact Storage

Generated artifacts belong in Google Drive, not Git history. Source data also gets a Drive mirror so oversized OCR dumps and recovered source material have an external safety copy.

The default repository sync mirrors `output/` and `data/` to:

```text
My Drive/.git-data/manichaean-analysis/output/
My Drive/.git-data/manichaean-analysis/data/
```

Run the mirror from the repository root:

```powershell
conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py
```

The script reuses the working Google Drive OAuth client and token from `literary-compilation/secrets/`. It creates missing Drive folders, uploads missing or changed files, skips files that already match by checksum, and never deletes remote files. The default sync includes both `output/` and `data/` when present; a clean checkout without `output/` skips that missing default source. Use `--source output` or `--source data` for a targeted single-folder sync.

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

To restore an archive into the repository root:

```powershell
tar -xzf temp/gdrive_archives/manichaean-analysis-output-YYYYMMDD.tar.gz
```

Useful options:

```powershell
# Preview without uploading. The limit applies per source folder.
conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --dry-run --limit 10

# Sync only one source folder
conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --source data --retries 12

# Retry harder on flaky network connections
conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --retries 12
```

Git should keep source code, scripts, findings, documentation, and normal-sized source data. Large generated output should be restored from Drive when needed.

Large source artifacts that exceed GitHub's warning threshold should also be stored in Drive rather than committed directly. Use `--archive` for one-off preservation when a source OCR dump is too large for normal Git history.
