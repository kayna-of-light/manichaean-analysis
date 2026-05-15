# Artifact Storage

Generated artifacts belong in Google Drive, not Git history.

The repository mirrors `output/` to:

```text
My Drive/.git-data/manichaean-analysis/output/
```

Run the mirror from the repository root:

```powershell
conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py
```

The script reuses the working Google Drive OAuth client and token from `literary-compilation/secrets/`. It creates missing Drive folders, uploads missing or changed files, skips files that already match by checksum, and never deletes remote files.

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
# Preview without uploading
conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --dry-run --limit 10

# Retry harder on flaky network connections
conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --retries 12
```

Git should keep source code, scripts, findings, and documentation. Large generated output should be restored from Drive when needed.

Large source artifacts that exceed GitHub's warning threshold should also be stored in Drive rather than committed directly. Use `--archive` for one-off preservation when a source OCR dump is too large for normal Git history.