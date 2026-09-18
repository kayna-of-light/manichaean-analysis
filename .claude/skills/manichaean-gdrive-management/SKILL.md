---
name: manichaean-gdrive-management
description: "Mirror or restore manichaean-analysis ignored/additional repo files with scripts/sync_artifacts_to_drive.py and Google Drive .git-data/manichaean-analysis."
---

# Google Drive Mirror

Use this skill when the user asks to sync, mirror, back up, restore, inspect, or repair the Google Drive mirror for `manichaean-analysis` artifacts.

## Contract

The script mirrors additional repo files that are not safely represented by Git, so a fresh clone can be restored into a working state.

Default local sources:

```text
output/
data/
manual_reviewer/data/
```

Default Drive target:

```text
My Drive/.git-data/manichaean-analysis/
```

This is a true local-to-Drive mirror. Local files are ground truth during upload mirror mode: changed/missing Drive files are created or updated, unchanged files are skipped by checksum/size, and remote extras are deleted only after the `DELETE_REMOTE` prompt unless `--yes` is explicitly used.

The script keeps a local Drive metadata cache at `temp/gdrive_mirror_cache/drive_cache.json`. That cache and `temp/gdrive_archives/` are excluded from mirror file discovery and must not be mirrored.

## Commands

Run commands from the repository root:

```powershell
cd C:\Users\mlf\source\github\manichaean-analysis
```

Full mirror with live progress:

```powershell
conda run --no-capture-output -n literary-compilation python scripts/sync_artifacts_to_drive.py --retries 12
```

Tune parallel file work when needed:

```powershell
conda run --no-capture-output -n literary-compilation python scripts/sync_artifacts_to_drive.py --workers 2 --retries 12
conda run --no-capture-output -n literary-compilation python scripts/sync_artifacts_to_drive.py --workers 6 --retries 12
```

Mirror only one source:

```powershell
conda run --no-capture-output -n literary-compilation python scripts/sync_artifacts_to_drive.py --source output --retries 12
conda run --no-capture-output -n literary-compilation python scripts/sync_artifacts_to_drive.py --source data --retries 12
conda run --no-capture-output -n literary-compilation python scripts/sync_artifacts_to_drive.py --source manual_reviewer/data --retries 12
```

Inspect or preview:

```powershell
conda run --no-capture-output -n literary-compilation python scripts/sync_artifacts_to_drive.py --status --source manual_reviewer/data --retries 12
conda run --no-capture-output -n literary-compilation python scripts/sync_artifacts_to_drive.py --dry-run --limit 10 --retries 12
```

Upload/update without deleting Drive extras:

```powershell
conda run --no-capture-output -n literary-compilation python scripts/sync_artifacts_to_drive.py --no-delete --retries 12
```

Restore the Drive mirror into a fresh clone:

```powershell
conda run --no-capture-output -n literary-compilation python scripts/sync_artifacts_to_drive.py --restore --retries 12
```

Only prune local extras during restore when explicitly requested:

```powershell
conda run --no-capture-output -n literary-compilation python scripts/sync_artifacts_to_drive.py --restore --prune-local --retries 12
```

Optional frequent Manual Reviewer state backup. This is not a replacement for the full mirror:

```powershell
conda run --no-capture-output -n literary-compilation python scripts/sync_artifacts_to_drive.py --manual-reviewer-db --retries 12
```

## Notes

- Use `--no-capture-output` so progress, prompts, and failures are visible.
- Do not mirror the cache; the script excludes it automatically.
- Do not bypass deletion prompts unless the user has clearly confirmed local ground truth or asked for non-interactive cleanup.
- The OAuth client and token are reused from `literary-compilation/secrets/` by default.
