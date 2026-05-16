#!/usr/bin/env python3
"""Mirror repository artifacts to Google Drive.

This is intended for large generated folders and source-data mirrors that need
Drive preservation in addition to Git. By default it mirrors this repository's
``output/`` and ``data/`` trees into:

    My Drive/.git-data/manichaean-analysis/output/
    My Drive/.git-data/manichaean-analysis/data/

The script only creates folders and uploads or updates files. It never deletes
remote files.
"""

from __future__ import annotations

import argparse
import hashlib
import mimetypes
import time
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_SOURCES = (REPO_ROOT / "output", REPO_ROOT / "data")
DEFAULT_REPO_FOLDER_NAME = "manichaean-analysis"

# Reuse the known-good OAuth app and token from literary-compilation.
LIT_COMP_SECRETS = Path(r"C:\Users\mlf\source\github\literary-compilation\secrets")
DEFAULT_OAUTH_CLIENT = LIT_COMP_SECRETS / "google_drive_oauth_client.json"
DEFAULT_OAUTH_TOKEN = LIT_COMP_SECRETS / "google_drive_token.json"

FOLDER_MIME = "application/vnd.google-apps.folder"
DEFAULT_CHUNK_SIZE = 16 * 1024 * 1024
T = TypeVar("T")


def _safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _md5_file(path: Path) -> str:
    h = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _with_retries(label: str, func: Callable[[], T], retries: int) -> T:
    attempt = 0
    while True:
        try:
            return func()
        except Exception:
            attempt += 1
            if attempt > retries:
                raise
            delay = min(60, 2**attempt)
            print(f"retry {attempt}/{retries}: {label}; sleeping {delay}s", flush=True)
            time.sleep(delay)


def _drive_service(oauth_client: Path, oauth_token: Path):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    scopes = ["https://www.googleapis.com/auth/drive"]
    creds: Any = None
    if oauth_token.exists():
        creds = Credentials.from_authorized_user_file(str(oauth_token), scopes=scopes)

    if creds and getattr(creds, "expired", False) and getattr(creds, "refresh_token", None):
        creds.refresh(Request())
    elif not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(oauth_client), scopes=scopes)
        creds = flow.run_local_server(port=0)

    if not creds:
        raise SystemExit("OAuth credentials could not be created")

    _safe_mkdir(oauth_token.parent)
    oauth_token.write_text(creds.to_json(), encoding="utf-8")
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _describe_http_error(exc: Exception) -> Optional[str]:
    try:
        from googleapiclient.errors import HttpError

        if not isinstance(exc, HttpError):
            return None
        content = getattr(exc, "content", b"")
        if isinstance(content, (bytes, bytearray)):
            text = content.decode("utf-8", errors="replace")
        else:
            text = str(content)
        if "accessNotConfigured" in text or ("drive.googleapis.com" in text and "disabled" in text):
            return "Google Drive API is not enabled for the OAuth project. Enable it, then retry."
        return text
    except Exception:
        return None


class DriveMirror:
    def __init__(self, service, dry_run: bool, retries: int) -> None:
        self.service = service
        self.dry_run = dry_run
        self.retries = retries
        self.children_cache: dict[str, list[dict[str, Any]]] = {}

    def list_children(self, parent_id: str) -> list[dict[str, Any]]:
        if parent_id in self.children_cache:
            return self.children_cache[parent_id]

        items: list[dict[str, Any]] = []
        page_token: Optional[str] = None
        while True:
            request = self.service.files().list(
                q=f"'{parent_id}' in parents and trashed=false",
                fields="nextPageToken, files(id, name, mimeType, size, md5Checksum)",
                pageToken=page_token,
                pageSize=1000,
            )
            resp = _with_retries(f"list children for {parent_id}", request.execute, self.retries)
            items.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        self.children_cache[parent_id] = items
        return items

    def find_child(
        self,
        parent_id: str,
        name: str,
        mime_type: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        for item in self.list_children(parent_id):
            if item.get("name") != name:
                continue
            if mime_type and item.get("mimeType") != mime_type:
                continue
            return item
        return None

    def ensure_folder(self, parent_id: str, folder_name: str) -> str:
        if self.dry_run:
            digest = hashlib.sha256(f"{parent_id}/{folder_name}".encode("utf-8")).hexdigest()[:12]
            return f"DRY_RUN_FOLDER_{digest}"

        found = self.find_child(parent_id, folder_name, mime_type=FOLDER_MIME)
        if found:
            return found["id"]

        metadata = {"name": folder_name, "mimeType": FOLDER_MIME, "parents": [parent_id]}
        request = self.service.files().create(body=metadata, fields="id, name, mimeType")
        created = _with_retries(f"create folder {folder_name}", request.execute, self.retries)
        self.children_cache.setdefault(parent_id, []).append(created)
        return created["id"]

    def upload_file(self, parent_id: str, local_file: Path, remote_name: str) -> str:
        from googleapiclient.http import MediaFileUpload

        local_size = local_file.stat().st_size
        if self.dry_run:
            return "create"

        local_md5 = _md5_file(local_file)
        existing = self.find_child(parent_id, remote_name)

        if existing and existing.get("md5Checksum") == local_md5 and int(existing.get("size", -1)) == local_size:
            return "skip"

        mime_type = mimetypes.guess_type(local_file.name)[0] or "application/octet-stream"
        media = MediaFileUpload(
            str(local_file),
            mimetype=mime_type,
            resumable=True,
            chunksize=DEFAULT_CHUNK_SIZE,
        )

        if existing:
            request = self.service.files().update(
                fileId=existing["id"],
                media_body=media,
                fields="id, name, mimeType, size, md5Checksum",
            )
            action = "update"
        else:
            body = {"name": remote_name, "parents": [parent_id]}
            request = self.service.files().create(
                body=body,
                media_body=media,
                fields="id, name, mimeType, size, md5Checksum",
            )
            action = "create"

        response = None
        last_progress = -1
        while response is None:
            status, response = _with_retries(
                f"upload {local_file.relative_to(local_file.parents[0])}",
                request.next_chunk,
                self.retries,
            )
            if status and local_size >= 100 * 1024 * 1024:
                progress = int(status.progress() * 100)
                if progress >= last_progress + 5:
                    last_progress = progress
                    print(f"upload progress {local_file.name}: {progress}%", flush=True)

        if existing:
            for idx, item in enumerate(self.children_cache.get(parent_id, [])):
                if item.get("id") == existing.get("id"):
                    self.children_cache[parent_id][idx] = response
                    break
        else:
            self.children_cache.setdefault(parent_id, []).append(response)

        return action


def iter_files(source_root: Path) -> list[Path]:
    return sorted(path for path in source_root.rglob("*") if path.is_file())


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} GB"


def mirror_artifacts(
    *,
    source_root: Path,
    drive_root_id: str,
    drive_root_name: str,
    repo_folder_name: str,
    remote_subfolder: str,
    oauth_client: Path,
    oauth_token: Path,
    dry_run: bool,
    limit: Optional[int],
    retries: int,
    progress_every: int,
) -> None:
    if not source_root.exists():
        raise SystemExit(f"Source folder not found: {source_root}")
    if not oauth_client.exists():
        raise SystemExit(f"OAuth client JSON not found: {oauth_client}")

    files = iter_files(source_root)
    if limit is not None:
        files = files[:limit]

    total_bytes = sum(path.stat().st_size for path in files)
    print(f"Source: {source_root}")
    print(f"Files: {len(files)}")
    print(f"Bytes: {human_size(total_bytes)}")
    print(f"Drive path: {drive_root_name}/{repo_folder_name}/{remote_subfolder}")
    print(f"Mode: {'dry-run' if dry_run else 'upload'}")

    service = _drive_service(oauth_client, oauth_token)
    mirror = DriveMirror(service, dry_run=dry_run, retries=retries)

    root_id = mirror.ensure_folder(drive_root_id, drive_root_name)
    repo_id = mirror.ensure_folder(root_id, repo_folder_name)
    source_id = mirror.ensure_folder(repo_id, remote_subfolder)

    folder_cache: dict[tuple[str, ...], str] = {(): source_id}
    counts = {"create": 0, "update": 0, "skip": 0, "failed": 0}

    for index, local_file in enumerate(files, 1):
        rel = local_file.relative_to(source_root)
        parent_parts = rel.parts[:-1]
        parent_id = source_id
        current_parts: list[str] = []
        for part in parent_parts:
            current_parts.append(part)
            key = tuple(current_parts)
            if key in folder_cache:
                parent_id = folder_cache[key]
                continue
            parent_id = mirror.ensure_folder(parent_id, part)
            folder_cache[key] = parent_id

        try:
            action = mirror.upload_file(parent_id, local_file, rel.name)
            counts[action] += 1
            should_print = action != "skip" or progress_every <= 1 or index % progress_every == 0
            if should_print:
                print(f"[{index}/{len(files)}] {action:6} {human_size(local_file.stat().st_size):>10} {rel.as_posix()}", flush=True)
        except Exception as exc:
            counts["failed"] += 1
            print(f"[{index}/{len(files)}] failed {human_size(local_file.stat().st_size):>10} {rel.as_posix()}: {exc}", flush=True)
            continue

    print("\nDone")
    print(f"Created: {counts['create']}")
    print(f"Updated: {counts['update']}")
    print(f"Skipped: {counts['skip']}")
    print(f"Failed: {counts['failed']}")
    if counts["failed"]:
        raise SystemExit(1)


def upload_single_artifact(
    *,
    local_file: Path,
    drive_root_id: str,
    drive_root_name: str,
    repo_folder_name: str,
    remote_subfolder: str,
    oauth_client: Path,
    oauth_token: Path,
    dry_run: bool,
    retries: int,
) -> None:
    if not local_file.exists() or not local_file.is_file():
        raise SystemExit(f"Archive file not found: {local_file}")
    if not oauth_client.exists():
        raise SystemExit(f"OAuth client JSON not found: {oauth_client}")

    print(f"File: {local_file}")
    print(f"Bytes: {human_size(local_file.stat().st_size)}")
    print(f"Drive path: {drive_root_name}/{repo_folder_name}/{remote_subfolder}/{local_file.name}")
    print(f"Mode: {'dry-run' if dry_run else 'upload'}")

    service = _drive_service(oauth_client, oauth_token)
    mirror = DriveMirror(service, dry_run=dry_run, retries=retries)
    root_id = mirror.ensure_folder(drive_root_id, drive_root_name)
    repo_id = mirror.ensure_folder(root_id, repo_folder_name)
    folder_id = mirror.ensure_folder(repo_id, remote_subfolder)
    action = mirror.upload_file(folder_id, local_file, local_file.name)
    print(f"{action}: {local_file.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Mirror repository artifacts to Google Drive")
    parser.add_argument(
        "--source",
        action="append",
        default=None,
        help="Local folder to mirror. Can be repeated. Defaults to output/ and data/.",
    )
    parser.add_argument("--archive", default=None, help="Upload a single archive file instead of mirroring a folder")
    parser.add_argument("--drive-root-id", default="root", help="Parent Drive folder id; default is My Drive root")
    parser.add_argument("--drive-root-name", default=".git-data", help="Top-level artifact folder name")
    parser.add_argument("--repo-folder-name", default=DEFAULT_REPO_FOLDER_NAME, help="Repository folder name under drive-root-name")
    parser.add_argument("--remote-subfolder", default=None, help="Remote subfolder name; default is source folder name")
    parser.add_argument("--oauth-client", default=str(DEFAULT_OAUTH_CLIENT), help="OAuth client JSON path")
    parser.add_argument("--oauth-token", default=str(DEFAULT_OAUTH_TOKEN), help="OAuth token cache path")
    parser.add_argument("--dry-run", action="store_true", help="Preview without creating folders or uploading files")
    parser.add_argument("--limit", type=int, default=None, help="Process only first N files")
    parser.add_argument("--retries", type=int, default=8, help="Retries per Drive operation")
    parser.add_argument(
        "--progress-every",
        type=int,
        default=100,
        help="Print every N skipped files; creates/updates/failures are always printed",
    )
    args = parser.parse_args()

    if args.source:
        source_roots = [Path(source).resolve() for source in args.source]
    else:
        missing_defaults = [path for path in DEFAULT_SOURCES if not path.exists()]
        for missing in missing_defaults:
            print(f"Skipping missing default source: {missing}")
        source_roots = [path.resolve() for path in DEFAULT_SOURCES if path.exists()]
        if not source_roots:
            default_list = ", ".join(str(path) for path in DEFAULT_SOURCES)
            raise SystemExit(f"No default source folders found: {default_list}")
    if args.remote_subfolder and len(source_roots) != 1 and not args.archive:
        raise SystemExit("--remote-subfolder can only be used when mirroring one --source folder")

    try:
        if args.archive:
            upload_single_artifact(
                local_file=Path(args.archive).resolve(),
                drive_root_id=args.drive_root_id,
                drive_root_name=args.drive_root_name,
                repo_folder_name=args.repo_folder_name,
                remote_subfolder=args.remote_subfolder or "archives",
                oauth_client=Path(args.oauth_client),
                oauth_token=Path(args.oauth_token),
                dry_run=args.dry_run,
                retries=args.retries,
            )
        else:
            for index, source_root in enumerate(source_roots, 1):
                if len(source_roots) > 1:
                    print(f"\n=== Source {index}/{len(source_roots)}: {source_root.name} ===")
                mirror_artifacts(
                    source_root=source_root,
                    drive_root_id=args.drive_root_id,
                    drive_root_name=args.drive_root_name,
                    repo_folder_name=args.repo_folder_name,
                    remote_subfolder=args.remote_subfolder or source_root.name,
                    oauth_client=Path(args.oauth_client),
                    oauth_token=Path(args.oauth_token),
                    dry_run=args.dry_run,
                    limit=args.limit,
                    retries=args.retries,
                    progress_every=max(1, args.progress_every),
                )
    except Exception as exc:
        friendly = _describe_http_error(exc)
        if friendly:
            raise SystemExit(friendly) from exc
        raise


if __name__ == "__main__":
    main()