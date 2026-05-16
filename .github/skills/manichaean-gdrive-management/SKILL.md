---
name: manichaean-gdrive-management
description: "Manage Google Drive storage for manichaean-analysis artifacts. Use when asked to sync, mirror, archive, back up, restore, or inspect Manichaean generated output, large OCR files, .git-data/manichaean-analysis, Google Drive, gdrive, Drive artifacts, or scripts/sync_artifacts_to_drive.py."
---

# Google Drive Artifact Management

## When To Use

Use this skill for `manichaean-analysis` tasks involving Google Drive storage, especially:

- Backing up or mirroring generated `output/` artifacts, repository `data/` sources, and `manual_reviewer/data/` local review data.
- Uploading large OCR dumps or other files that should not enter Git history.
- Pruning old Drive files when local mirror files were deleted.
- Restoring generated artifacts from Drive archives.
- Restoring the Drive mirror into a fresh clone or new machine.
- Verifying whether Drive holds a safety copy before cleanup.
- Keeping Git history free of generated files and blobs `>= 50 MB`.

This skill is about artifact storage. It is not for syncing the source text library as styled PDFs.

## Storage Policy

Generated artifacts belong in Google Drive, not Git history. The `data/` folder is mirrored to Drive as a safety copy, while normal-sized source data can still remain in Git. The manual reviewer local data folder is also mirrored because it is intentionally ignored from Git.

Primary Drive location:

```text
My Drive/.git-data/manichaean-analysis/
```

Standard subfolders:

```text
.git-data/manichaean-analysis/output/
.git-data/manichaean-analysis/data/
.git-data/manichaean-analysis/manual_reviewer/data/
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

It creates missing Drive folders, uploads missing or changed files, skips files that match by checksum, and deletes remote files that no longer exist locally after confirmation. Set `LITERARY_COMPILATION_SECRETS` or pass `--oauth-client` / `--oauth-token` when the sibling `literary-compilation/secrets/` folder is not available.

## Standard Workflow

1. Check Git status before touching storage:

   ```powershell
   git status --short --branch
   ```

2. Preview small syncs before doing a large operation:

   ```powershell
   conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --dry-run --limit 10
   ```

3. For the default per-file mirror of `output/`, `data/`, and `manual_reviewer/data/`:

   ```powershell
   conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --retries 12
   ```

   By default this mirrors `output/`, `data/`, and `manual_reviewer/data/` when present. A clean checkout without generated local folders skips those missing default sources. The limit in `--limit N` applies per source folder.

   This is a true local-to-Drive mirror. Remote files missing locally are deleted after a `DELETE_REMOTE` confirmation. Use `--dry-run` first to preview, `--yes` after reviewing, or `--no-delete` when an upload/update-only pass is required.

   To mirror only one folder:

   ```powershell
   conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --source output --retries 12
   conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --source data --retries 12
   conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --source manual_reviewer/data --retries 12
   ```

   Confirm reviewed deletions non-interactively:

   ```powershell
   conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --yes --retries 12
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

6. Restore the Drive mirror into a fresh clone:

   ```powershell
   conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --restore --retries 12
   ```

   Restore creates/updates local files but does not delete local extras unless explicitly requested:

   ```powershell
   conda run -n literary-compilation python scripts/sync_artifacts_to_drive.py --restore --prune-local --retries 12
   ```

   `--prune-local` requires typing `DELETE_LOCAL` before deleting local files that are missing from Drive. Use `--yes` only after reviewing a dry run.

7. Restore an archive from a local copy into the repository root:

   ```powershell
   tar -xzf temp/gdrive_archives/manichaean-analysis-output-YYYYMMDD.tar.gz
   ```

## Safety Checks

Before cleanup or promotion work, confirm preservation:

- There is a Drive archive under `.git-data/manichaean-analysis/archives/` when a full safety backup is needed.
- The default Drive mirror includes `.git-data/manichaean-analysis/output/`, `.git-data/manichaean-analysis/data/`, and `.git-data/manichaean-analysis/manual_reviewer/data/`.
- Run `--dry-run` before any sync expected to delete remote files.
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

- Do not delete local artifacts as part of Drive restore unless the user explicitly asks via `--prune-local`.
- Do not use `git reset --hard` or destructive checkout to clean artifacts.
- Do not use Drive as proof of safety unless upload completion is visible.
- Do not bypass destructive prompts unless a dry run has already been reviewed or the user explicitly asked for non-interactive cleanup.
- Preserve old branch refs before promoting cleaned Git history.
- Record any important Drive location in `docs/artifact_storage.md` when the storage policy changes.
