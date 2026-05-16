---
name: gdrive-management
description: "Manage Google Drive storage for manichaean-analysis artifacts. Use when asked to sync, mirror, archive, back up, restore, or inspect generated output, large OCR files, .git-data, Google Drive, gdrive, Drive artifacts, or scripts/sync_artifacts_to_drive.py."
---

# Google Drive Artifact Management

## When To Use

Use this skill for `manichaean-analysis` tasks involving Google Drive storage, especially:

- Backing up or mirroring generated `output/` artifacts and repository `data/` sources.
- Uploading large OCR dumps or other files that should not enter Git history.
- Restoring generated artifacts from Drive archives.
- Verifying whether Drive holds a safety copy before cleanup.
- Keeping Git history free of generated files and blobs `>= 50 MB`.

This skill is about artifact storage. It is not for syncing the source text library as styled PDFs.

## Storage Policy

Generated artifacts belong in Google Drive, not Git history. The `data/` folder is mirrored to Drive as a safety copy, while normal-sized source data can still remain in Git.

Primary Drive location:

```text
My Drive/.git-data/manichaean-analysis/
```

Standard subfolders:

```text
.git-data/manichaean-analysis/output/
.git-data/manichaean-analysis/data/
.git-data/manichaean-analysis/archives/
```

Git should keep source code, scripts, findings, documentation, and reasonably sized source data. Do not commit generated `output/` trees. Avoid adding new blobs `>= 50 MB`; upload oversized source OCR dumps with archive mode instead.

## Script

Use the repository script:

```powershell
conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py
```

The script reuses the Google Drive OAuth client and token from:

```text
C:\Users\mlf\source\github\literary-compilation\secrets\google_drive_oauth_client.json
C:\Users\mlf\source\github\literary-compilation\secrets\google_drive_token.json
```

It creates missing Drive folders, uploads missing or changed files, skips files that match by checksum, and never deletes remote files.

## Standard Workflow

1. Check Git status before touching storage:

   ```powershell
   git status --short --branch
   ```

2. Preview small syncs before doing a large operation:

   ```powershell
   conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --dry-run --limit 10
   ```

3. For the default per-file mirror of `output/` and `data/`:

   ```powershell
   conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --retries 12
   ```

   By default this mirrors both `output/` and `data/` when present. A clean checkout without `output/` skips that missing default source. The limit in `--limit N` applies per source folder.

   To mirror only one folder:

   ```powershell
   conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --source output --retries 12
   conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --source data --retries 12
   ```

4. Prefer archive mode for immediate complete backups of large output trees:

   ```powershell
   New-Item -ItemType Directory -Force temp/gdrive_archives
   tar -czf temp/gdrive_archives/manichaean-analysis-output-YYYYMMDD.tar.gz output
   conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --archive temp/gdrive_archives/manichaean-analysis-output-YYYYMMDD.tar.gz --retries 12
   ```

5. Upload one oversized source artifact with archive mode:

   ```powershell
   conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --archive "path/to/large-source-file.json" --retries 12
   ```

6. Restore an archive from a local copy into the repository root:

   ```powershell
   tar -xzf temp/gdrive_archives/manichaean-analysis-output-YYYYMMDD.tar.gz
   ```

## Safety Checks

Before cleanup or promotion work, confirm preservation:

- There is a Drive archive under `.git-data/manichaean-analysis/archives/` when a full safety backup is needed.
- The default Drive mirror includes `.git-data/manichaean-analysis/output/` and `.git-data/manichaean-analysis/data/`.
- Large generated files are not staged.
- `output/` is ignored or locally excluded.
- New Git objects do not include blobs `>= 50 MB`.

Large blob check for new commits against upstream:

```powershell
$objects = git rev-list --objects '@{u}..HEAD'
foreach ($line in $objects) {
  $idx = $line.IndexOf(' ')
  if ($idx -lt 0) { continue }
  $hash = $line.Substring(0, $idx)
  $path = $line.Substring($idx + 1)
  if ((git cat-file -t $hash) -ne 'blob') { continue }
  $size = [int64](git cat-file -s $hash)
  if ($size -ge 50MB) { "{0:n2} MB`t{1}" -f ($size / 1MB), $path }
}
```

## Standing Rules

- Do not delete local artifacts as part of Drive sync unless the user explicitly asks.
- Do not use `git reset --hard` or destructive checkout to clean artifacts.
- Do not use Drive as proof of safety unless upload completion is visible.
- Do not use `--delete` behavior. The artifact sync script is intentionally non-deleting.
- Preserve old branch refs before promoting cleaned Git history.
- Record any important Drive location in `docs/artifact_storage.md` when the storage policy changes.
