#!/usr/bin/env python3
"""Mirror repository artifacts to and from Google Drive.

This is intended for large generated folders and source-data mirrors that need
Drive preservation in addition to Git. By default it mirrors this repository's
``output/``, ``data/``, and ``manual_reviewer/data/`` trees into:

    My Drive/.git-data/manichaean-analysis/output/
    My Drive/.git-data/manichaean-analysis/data/
    My Drive/.git-data/manichaean-analysis/manual_reviewer/data/

Normal sync is a true mirror: it creates and updates changed files, skips
unchanged files, and deletes remote files that no longer exist locally after an
explicit confirmation. Restore mode downloads the Drive mirror back into a fresh
clone. Archive restore mode downloads and extracts a full ``.tar.gz`` safety
archive from Drive; use it when the complete generated ``output/`` tree is needed.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import mimetypes
import tarfile
import time
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_SOURCE_SPECS = (
    (REPO_ROOT / "output", "output"),
    (REPO_ROOT / "data", "data"),
    (REPO_ROOT / "manual_reviewer" / "data", "manual_reviewer/data"),
)
DEFAULT_REPO_FOLDER_NAME = "manichaean-analysis"
ARCHIVE_CACHE_DIR = REPO_ROOT / "temp" / "gdrive_archives"

# Reuse the known-good OAuth app and token from literary-compilation.
LIT_COMP_SECRETS = Path(
    os.environ.get(
        "LITERARY_COMPILATION_SECRETS",
        str(REPO_ROOT.parent / "literary-compilation" / "secrets"),
    )
)
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
                fields="nextPageToken, files(id, name, mimeType, size, md5Checksum, modifiedTime)",
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
            if not parent_id.startswith("DRY_RUN_FOLDER_"):
                found = self.find_child(parent_id, folder_name, mime_type=FOLDER_MIME)
                if found:
                    return found["id"]
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

    def delete_item(self, file_id: str, label: str) -> None:
        if self.dry_run:
            return
        request = self.service.files().delete(fileId=file_id)
        _with_retries(f"delete {label}", request.execute, self.retries)

    def download_file(self, file_id: str, local_file: Path, total_size: Optional[int] = None) -> None:
        from googleapiclient.http import MediaIoBaseDownload

        if self.dry_run:
            return

        _safe_mkdir(local_file.parent)
        temp_file = local_file.with_name(f"{local_file.name}.download")
        request = self.service.files().get_media(fileId=file_id)
        with temp_file.open("wb") as handle:
            downloader = MediaIoBaseDownload(handle, request, chunksize=DEFAULT_CHUNK_SIZE)
            done = False
            last_progress = -1
            while not done:
                status, done = _with_retries(
                    f"download {local_file.name}",
                    downloader.next_chunk,
                    self.retries,
                )
                if status and total_size and total_size >= 100 * 1024 * 1024:
                    progress = int(status.progress() * 100)
                    if progress >= last_progress + 5:
                        last_progress = progress
                        print(f"download progress {local_file.name}: {progress}%", flush=True)
        temp_file.replace(local_file)


def iter_files(source_root: Path) -> list[Path]:
    return sorted(path for path in source_root.rglob("*") if path.is_file())


def relative_file_paths(source_root: Path) -> set[str]:
    if not source_root.exists():
        return set()
    return {path.relative_to(source_root).as_posix() for path in iter_files(source_root)}


def validate_archive_members(archive_path: Path, destination_root: Path) -> tuple[int, int]:
    root = destination_root.resolve()
    file_count = 0
    dir_count = 0
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers():
            if member.issym() or member.islnk():
                raise SystemExit(f"Archive links are not supported: {member.name}")
            target = (destination_root / member.name).resolve()
            if target != root and root not in target.parents:
                raise SystemExit(f"Unsafe archive member path: {member.name}")
            if member.isfile():
                file_count += 1
            elif member.isdir():
                dir_count += 1
    return file_count, dir_count


def verify_archive_contents(archive_path: Path, destination_root: Path, max_missing: int = 80) -> tuple[int, int]:
    missing: list[str] = []
    checked = 0
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            checked += 1
            local_file = destination_root / member.name
            if not local_file.is_file() or local_file.stat().st_size != member.size:
                if len(missing) < max_missing:
                    missing.append(member.name)

    print(f"Archive files checked: {checked}")
    print(f"Archive files missing or size-mismatched: {len(missing)}")
    for path in missing:
        print(f"missing {path}")
    return checked, len(missing)


def extract_archive(archive_path: Path, destination_root: Path, dry_run: bool) -> None:
    file_count, dir_count = validate_archive_members(archive_path, destination_root)
    print(f"Archive members: {file_count} files, {dir_count} folders")
    print(f"Extract target: {destination_root}")
    if dry_run:
        print("dry-run: archive extraction skipped")
        return
    with tarfile.open(archive_path, "r:gz") as archive:
        archive.extractall(destination_root)
    print("Archive extracted")


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} GB"


def default_remote_subfolder(source_root: Path) -> str:
    try:
        return source_root.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return source_root.name


def ensure_remote_folder_path(mirror: DriveMirror, parent_id: str, remote_subfolder: str) -> str:
    folder_id = parent_id
    parts = [part for part in remote_subfolder.replace("\\", "/").split("/") if part]
    for part in parts:
        folder_id = mirror.ensure_folder(folder_id, part)
    return folder_id


def find_remote_folder_path(mirror: DriveMirror, parent_id: str, remote_subfolder: str) -> Optional[str]:
    folder_id = parent_id
    parts = [part for part in remote_subfolder.replace("\\", "/").split("/") if part]
    for part in parts:
        found = mirror.find_child(folder_id, part, mime_type=FOLDER_MIME)
        if not found:
            return None
        folder_id = found["id"]
    return folder_id


def collect_remote_tree(
    mirror: DriveMirror,
    folder_id: str,
    rel_prefix: str = "",
    duplicate_files: Optional[list[tuple[str, dict[str, Any]]]] = None,
) -> tuple[dict[str, dict[str, Any]], list[tuple[str, dict[str, Any]]]]:
    files: dict[str, dict[str, Any]] = {}
    folders: list[tuple[str, dict[str, Any]]] = []
    for item in mirror.list_children(folder_id):
        name = item.get("name")
        item_id = item.get("id")
        mime_type = item.get("mimeType")
        if not name or not item_id or not mime_type:
            continue
        rel_path = f"{rel_prefix}/{name}" if rel_prefix else name
        if mime_type == FOLDER_MIME:
            folders.append((rel_path, item))
            child_files, child_folders = collect_remote_tree(mirror, item_id, rel_path, duplicate_files)
            for child_path, child_item in child_files.items():
                if child_path in files:
                    if duplicate_files is not None:
                        duplicate_files.append((child_path, child_item))
                    continue
                files[child_path] = child_item
            folders.extend(child_folders)
        else:
            if duplicate_files is not None and rel_path in files:
                duplicate_files.append((rel_path, item))
                continue
            files[rel_path] = item
    return files, folders


def desired_folder_paths(file_paths: set[str]) -> set[str]:
    folders: set[str] = set()
    for rel_path in file_paths:
        parts = Path(rel_path).parts[:-1]
        current: list[str] = []
        for part in parts:
            current.append(part)
            folders.add("/".join(current))
    return folders


def print_path_sample(paths: list[str], *, heading: str, limit: int = 25) -> None:
    if not paths:
        return
    print(heading)
    for path in paths[:limit]:
        print(f"  - {path}")
    if len(paths) > limit:
        print(f"  ... and {len(paths) - limit} more")


def print_prefix_status(local_paths: set[str], remote_paths: set[str], *, depth: int = 2) -> None:
    prefixes: set[str] = set()
    for path in local_paths | remote_paths:
        parts = path.split("/")
        if len(parts) >= depth:
            prefixes.add("/".join(parts[:depth]) + "/")

    if not prefixes:
        return
    print("\nPrefix status")
    for prefix in sorted(prefixes):
        local_count = sum(1 for path in local_paths if path.startswith(prefix))
        remote_count = sum(1 for path in remote_paths if path.startswith(prefix))
        if local_count != remote_count:
            print(f"  {prefix} local={local_count} remote={remote_count}")


def confirm_destructive_action(*, label: str, token: str, yes: bool, dry_run: bool) -> None:
    if dry_run or yes:
        return
    answer = input(f"Type {token} to {label}: ")
    if answer != token:
        raise SystemExit("Cancelled; no files were deleted.")


def delete_remote_extras(
    *,
    mirror: DriveMirror,
    source_id: str,
    desired_paths: set[str],
    dry_run: bool,
    yes: bool,
) -> tuple[int, int]:
    if dry_run and source_id.startswith("DRY_RUN_FOLDER_"):
        print("Remote cleanup: mirror folder does not exist yet; no remote extras to preview")
        return 0, 0

    duplicate_files: list[tuple[str, dict[str, Any]]] = []
    remote_files, remote_folders = collect_remote_tree(mirror, source_id, duplicate_files=duplicate_files)
    extra_files = sorted(set(remote_files) - desired_paths)
    desired_folders = desired_folder_paths(desired_paths)
    candidate_folders = sorted(rel for rel, _item in remote_folders if rel not in desired_folders)

    if not extra_files and not duplicate_files and not candidate_folders:
        print("Remote cleanup: no extras")
        return 0, 0

    print("\nRemote cleanup warning")
    print(f"Remote files not present locally: {len(extra_files)}")
    print(f"Duplicate remote files: {len(duplicate_files)}")
    print(f"Remote folders that may become empty: {len(candidate_folders)}")
    print_path_sample(extra_files, heading="Files to delete from Drive:")
    print_path_sample([rel_path for rel_path, _item in duplicate_files], heading="Duplicate files to delete from Drive:")
    print_path_sample(candidate_folders, heading="Folders to delete from Drive if empty:")

    confirm_destructive_action(
        label="delete remote files that are not present locally",
        token="DELETE_REMOTE",
        yes=yes,
        dry_run=dry_run,
    )

    deleted_files = 0
    deleted_folders = 0
    for rel_path in extra_files:
        mirror.delete_item(remote_files[rel_path]["id"], rel_path)
        deleted_files += 1
        print(f"delete remote file: {rel_path}")

    for rel_path, item in duplicate_files:
        mirror.delete_item(item["id"], rel_path)
        deleted_files += 1
        print(f"delete duplicate remote file: {rel_path}")

    if extra_files or duplicate_files or candidate_folders:
        mirror.children_cache.clear()

    for rel_path, item in sorted(remote_folders, key=lambda pair: pair[0].count("/"), reverse=True):
        if rel_path in desired_folders:
            continue
        if dry_run:
            print(f"delete remote folder if empty: {rel_path}")
            deleted_folders += 1
            continue
        children = mirror.list_children(item["id"])
        if children:
            continue
        mirror.delete_item(item["id"], rel_path)
        mirror.children_cache.clear()
        deleted_folders += 1
        print(f"delete remote folder: {rel_path}")

    return deleted_files, deleted_folders


def delete_local_extras(
    *,
    source_root: Path,
    remote_paths: set[str],
    dry_run: bool,
    yes: bool,
) -> tuple[int, int]:
    local_paths = relative_file_paths(source_root)
    extra_files = sorted(local_paths - remote_paths)
    if not extra_files:
        print("Local cleanup: no extras")
        return 0, 0

    print("\nLocal cleanup warning")
    print(f"Local files not present in Drive mirror: {len(extra_files)}")
    print_path_sample(extra_files, heading="Files to delete locally:")
    confirm_destructive_action(
        label="delete local files that are not present in Drive",
        token="DELETE_LOCAL",
        yes=yes,
        dry_run=dry_run,
    )

    deleted_files = 0
    for rel_path in extra_files:
        local_file = source_root / Path(rel_path)
        if dry_run:
            print(f"delete local file: {rel_path}")
        else:
            local_file.unlink(missing_ok=True)
            print(f"delete local file: {rel_path}")
        deleted_files += 1

    deleted_folders = 0
    if source_root.exists():
        for folder in sorted((path for path in source_root.rglob("*") if path.is_dir()), key=lambda path: len(path.parts), reverse=True):
            try:
                if dry_run:
                    if not any(folder.iterdir()):
                        print(f"delete local folder if empty: {folder.relative_to(source_root).as_posix()}")
                        deleted_folders += 1
                    continue
                folder.rmdir()
                print(f"delete local folder: {folder.relative_to(source_root).as_posix()}")
                deleted_folders += 1
            except OSError:
                continue

    return deleted_files, deleted_folders


def restore_artifacts(
    *,
    destination_root: Path,
    drive_root_id: str,
    drive_root_name: str,
    repo_folder_name: str,
    remote_subfolder: str,
    oauth_client: Path,
    oauth_token: Path,
    dry_run: bool,
    retries: int,
    progress_every: int,
    prune_local: bool,
    yes: bool,
    required_remote: bool,
) -> None:
    if not oauth_client.exists():
        raise SystemExit(f"OAuth client JSON not found: {oauth_client}")

    print(f"Destination: {destination_root}")
    print(f"Drive path: {drive_root_name}/{repo_folder_name}/{remote_subfolder}")
    print(f"Mode: {'dry-run restore' if dry_run else 'restore'}")
    print(f"Delete local extras: {'yes' if prune_local else 'no'}")

    service = _drive_service(oauth_client, oauth_token)
    mirror = DriveMirror(service, dry_run=dry_run, retries=retries)
    root = mirror.find_child(drive_root_id, drive_root_name, mime_type=FOLDER_MIME)
    if not root:
        raise SystemExit(f"Drive folder not found: {drive_root_name}")
    repo = mirror.find_child(root["id"], repo_folder_name, mime_type=FOLDER_MIME)
    if not repo:
        raise SystemExit(f"Drive repo folder not found: {drive_root_name}/{repo_folder_name}")
    source_id = find_remote_folder_path(mirror, repo["id"], remote_subfolder)
    if not source_id:
        message = f"Drive mirror folder not found: {drive_root_name}/{repo_folder_name}/{remote_subfolder}"
        if required_remote:
            raise SystemExit(message)
        print(f"Skipping missing remote source: {message}")
        return

    remote_files, _remote_folders = collect_remote_tree(mirror, source_id)
    remote_paths = set(remote_files)
    total_bytes = sum(int(item.get("size", 0)) for item in remote_files.values())
    print(f"Remote files: {len(remote_files)}")
    print(f"Remote bytes: {human_size(total_bytes)}")

    counts = {"create": 0, "update": 0, "skip": 0, "failed": 0}
    for index, rel_path in enumerate(sorted(remote_files), 1):
        item = remote_files[rel_path]
        local_file = destination_root / Path(rel_path)
        remote_size = int(item.get("size", -1))
        remote_md5 = item.get("md5Checksum")
        if local_file.exists() and remote_md5 and local_file.stat().st_size == remote_size and _md5_file(local_file) == remote_md5:
            action = "skip"
        else:
            action = "update" if local_file.exists() else "create"
            try:
                mirror.download_file(item["id"], local_file)
            except Exception as exc:
                counts["failed"] += 1
                print(f"[{index}/{len(remote_files)}] failed {human_size(max(remote_size, 0)):>10} {rel_path}: {exc}", flush=True)
                continue
        counts[action] += 1
        should_print = action != "skip" or progress_every <= 1 or index % progress_every == 0
        if should_print:
            print(f"[{index}/{len(remote_files)}] {action:6} {human_size(max(remote_size, 0)):>10} {rel_path}", flush=True)

    print("\nRestore done")
    print(f"Created: {counts['create']}")
    print(f"Updated: {counts['update']}")
    print(f"Skipped: {counts['skip']}")
    print(f"Failed: {counts['failed']}")
    if prune_local:
        deleted_files, deleted_folders = delete_local_extras(
            source_root=destination_root,
            remote_paths=remote_paths,
            dry_run=dry_run,
            yes=yes,
        )
        print(f"Deleted local files: {deleted_files}{' (dry-run)' if dry_run else ''}")
        print(f"Deleted local folders: {deleted_folders}{' (dry-run)' if dry_run else ''}")
    if counts["failed"]:
        raise SystemExit(1)


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
    delete_extras: bool,
    yes: bool,
) -> None:
    if not source_root.exists():
        raise SystemExit(f"Source folder not found: {source_root}")
    if not oauth_client.exists():
        raise SystemExit(f"OAuth client JSON not found: {oauth_client}")

    all_files = iter_files(source_root)
    desired_paths = {path.relative_to(source_root).as_posix() for path in all_files}
    files = all_files
    if limit is not None:
        files = files[:limit]

    total_bytes = sum(path.stat().st_size for path in all_files)
    print(f"Source: {source_root}")
    print(f"Files: {len(all_files)}")
    if limit is not None:
        print(f"Limited upload/check pass: first {len(files)} files")
    print(f"Bytes: {human_size(total_bytes)}")
    print(f"Drive path: {drive_root_name}/{repo_folder_name}/{remote_subfolder}")
    print(f"Mode: {'dry-run' if dry_run else 'mirror'}")
    print(f"Delete remote extras: {'yes' if delete_extras else 'no'}")

    service = _drive_service(oauth_client, oauth_token)
    mirror = DriveMirror(service, dry_run=dry_run, retries=retries)

    root_id = mirror.ensure_folder(drive_root_id, drive_root_name)
    repo_id = mirror.ensure_folder(root_id, repo_folder_name)
    source_id = ensure_remote_folder_path(mirror, repo_id, remote_subfolder)

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
    if delete_extras:
        deleted_files, deleted_folders = delete_remote_extras(
            mirror=mirror,
            source_id=source_id,
            desired_paths=desired_paths,
            dry_run=dry_run,
            yes=yes,
        )
        print(f"Deleted remote files: {deleted_files}{' (dry-run)' if dry_run else ''}")
        print(f"Deleted remote folders: {deleted_folders}{' (dry-run)' if dry_run else ''}")
    if counts["failed"]:
        raise SystemExit(1)


def status_artifacts(
    *,
    source_root: Path,
    drive_root_id: str,
    drive_root_name: str,
    repo_folder_name: str,
    remote_subfolder: str,
    oauth_client: Path,
    oauth_token: Path,
    retries: int,
) -> None:
    if not source_root.exists():
        raise SystemExit(f"Source folder not found: {source_root}")
    if not oauth_client.exists():
        raise SystemExit(f"OAuth client JSON not found: {oauth_client}")

    local_files = iter_files(source_root)
    local_paths = {path.relative_to(source_root).as_posix(): path for path in local_files}
    local_bytes = sum(path.stat().st_size for path in local_files)

    print(f"Source: {source_root}", flush=True)
    print(f"Local files: {len(local_files)}", flush=True)
    print(f"Local bytes: {human_size(local_bytes)}", flush=True)
    print(f"Drive path: {drive_root_name}/{repo_folder_name}/{remote_subfolder}", flush=True)
    print("Mode: status", flush=True)

    service = _drive_service(oauth_client, oauth_token)
    mirror = DriveMirror(service, dry_run=False, retries=retries)
    root = mirror.find_child(drive_root_id, drive_root_name, mime_type=FOLDER_MIME)
    repo = mirror.find_child(root["id"], repo_folder_name, mime_type=FOLDER_MIME) if root else None
    source_id = find_remote_folder_path(mirror, repo["id"], remote_subfolder) if repo else None

    if not source_id:
        print("Remote files: 0")
        print("Remote bytes: 0.00 B")
        print("File progress: 0.0%")
        print("Byte progress: 0.0%")
        print(f"Missing remotely: {len(local_paths)}")
        print("Remote extras: 0")
        return

    duplicate_files: list[tuple[str, dict[str, Any]]] = []
    remote_files, _remote_folders = collect_remote_tree(mirror, source_id, duplicate_files=duplicate_files)
    remote_paths = set(remote_files)
    remote_bytes = sum(int(item.get("size", 0) or 0) for item in remote_files.values())
    missing_remote = sorted(set(local_paths) - remote_paths)
    remote_extras = sorted(remote_paths - set(local_paths))

    file_progress = (len(remote_files) / len(local_files) * 100) if local_files else 100.0
    byte_progress = (remote_bytes / local_bytes * 100) if local_bytes else 100.0

    print(f"Remote files: {len(remote_files)}")
    print(f"Remote bytes: {human_size(remote_bytes)}")
    print(f"File progress: {len(remote_files)}/{len(local_files)} ({file_progress:.1f}%)")
    print(f"Byte progress: {remote_bytes}/{local_bytes} ({byte_progress:.1f}%)")
    print(f"Missing remotely: {len(missing_remote)}")
    print(f"Remote extras: {len(remote_extras)}")
    print(f"Remote duplicates: {len(duplicate_files)}")
    print_prefix_status(set(local_paths), remote_paths)
    print_path_sample(missing_remote, heading="\nMissing remote sample")
    print_path_sample(remote_extras, heading="\nRemote extra sample")
    print_path_sample([rel_path for rel_path, _item in duplicate_files], heading="\nRemote duplicate sample")


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
    folder_id = ensure_remote_folder_path(mirror, repo_id, remote_subfolder)
    action = mirror.upload_file(folder_id, local_file, local_file.name)
    print(f"{action}: {local_file.name}")


def restore_archive_from_drive(
    *,
    archive_name: str,
    drive_root_id: str,
    drive_root_name: str,
    repo_folder_name: str,
    remote_subfolder: str,
    oauth_client: Path,
    oauth_token: Path,
    dry_run: bool,
    retries: int,
) -> None:
    if not oauth_client.exists():
        raise SystemExit(f"OAuth client JSON not found: {oauth_client}")

    print(f"Drive path: {drive_root_name}/{repo_folder_name}/{remote_subfolder}")
    print(f"Archive selection: {archive_name}")
    print(f"Mode: {'dry-run archive restore' if dry_run else 'archive restore'}")

    service = _drive_service(oauth_client, oauth_token)
    mirror = DriveMirror(service, dry_run=dry_run, retries=retries)
    root = mirror.find_child(drive_root_id, drive_root_name, mime_type=FOLDER_MIME)
    if not root:
        raise SystemExit(f"Drive folder not found: {drive_root_name}")
    repo = mirror.find_child(root["id"], repo_folder_name, mime_type=FOLDER_MIME)
    if not repo:
        raise SystemExit(f"Drive repo folder not found: {drive_root_name}/{repo_folder_name}")
    archive_folder_id = find_remote_folder_path(mirror, repo["id"], remote_subfolder)
    if not archive_folder_id:
        raise SystemExit(f"Drive archive folder not found: {drive_root_name}/{repo_folder_name}/{remote_subfolder}")

    archives = [
        item
        for item in mirror.list_children(archive_folder_id)
        if item.get("mimeType") != FOLDER_MIME and str(item.get("name", "")).endswith(".tar.gz")
    ]
    if not archives:
        raise SystemExit(f"No .tar.gz archives found in {drive_root_name}/{repo_folder_name}/{remote_subfolder}")

    if archive_name in {"", "latest"}:
        selected = max(archives, key=lambda item: (str(item.get("modifiedTime", "")), str(item.get("name", ""))))
    else:
        matches = [item for item in archives if item.get("name") == archive_name]
        if not matches:
            available = ", ".join(sorted(str(item.get("name")) for item in archives))
            raise SystemExit(f"Archive not found: {archive_name}. Available archives: {available}")
        selected = matches[0]

    selected_name = str(selected["name"])
    remote_size = int(selected.get("size", 0))
    remote_md5 = selected.get("md5Checksum")
    local_archive = ARCHIVE_CACHE_DIR / selected_name
    print(f"Selected archive: {selected_name}")
    print(f"Remote bytes: {human_size(remote_size)}")
    print(f"Local cache: {local_archive}")

    need_download = True
    if local_archive.is_file() and remote_size and local_archive.stat().st_size == remote_size:
        if not remote_md5 or _md5_file(local_archive) == remote_md5:
            need_download = False

    if dry_run:
        print(f"dry-run: would {'download' if need_download else 'reuse'} archive")
        print("dry-run: archive extraction skipped")
        return

    if need_download:
        _safe_mkdir(local_archive.parent)
        mirror.download_file(selected["id"], local_archive, total_size=remote_size)
        print(f"downloaded: {local_archive}")
    else:
        print(f"reuse: {local_archive}")

    extract_archive(local_archive, REPO_ROOT, dry_run=False)
    _checked, missing = verify_archive_contents(local_archive, REPO_ROOT)
    if missing:
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mirror repository artifacts to Google Drive")
    parser.add_argument(
        "--source",
        action="append",
        default=None,
        help="Local folder to mirror. Can be repeated. Defaults to output/, data/, and manual_reviewer/data/.",
    )
    parser.add_argument("--archive", default=None, help="Upload a single archive file instead of mirroring a folder")
    parser.add_argument("--status", action="store_true", help="Compare local files to the Drive mirror without changing anything")
    parser.add_argument(
        "--restore-archive",
        nargs="?",
        const="latest",
        default=None,
        help="Download and extract an archive from the Drive archives folder. Use without a value for the latest archive.",
    )
    parser.add_argument("--verify-archive", default=None, help="Verify that all files in a local .tar.gz archive exist under the repo root")
    parser.add_argument("--restore", action="store_true", help="Restore mirrored Drive folders into local source folders")
    parser.add_argument("--drive-root-id", default="root", help="Parent Drive folder id; default is My Drive root")
    parser.add_argument("--drive-root-name", default=".git-data", help="Top-level artifact folder name")
    parser.add_argument("--repo-folder-name", default=DEFAULT_REPO_FOLDER_NAME, help="Repository folder name under drive-root-name")
    parser.add_argument("--remote-subfolder", default=None, help="Remote subfolder name; default is source folder name")
    parser.add_argument("--oauth-client", default=str(DEFAULT_OAUTH_CLIENT), help="OAuth client JSON path")
    parser.add_argument("--oauth-token", default=str(DEFAULT_OAUTH_TOKEN), help="OAuth token cache path")
    parser.add_argument("--dry-run", action="store_true", help="Preview without creating folders or uploading files")
    parser.add_argument("--limit", type=int, default=None, help="Process only first N files")
    parser.add_argument("--retries", type=int, default=8, help="Retries per Drive operation")
    parser.add_argument("--no-delete", action="store_true", help="Upload/update only; do not delete remote files missing locally")
    parser.add_argument("--prune-local", action="store_true", help="With --restore, delete local files missing from the Drive mirror")
    parser.add_argument("--yes", action="store_true", help="Skip destructive confirmation prompts")
    parser.add_argument(
        "--progress-every",
        type=int,
        default=100,
        help="Print every N skipped files; creates/updates/failures are always printed",
    )
    args = parser.parse_args()

    selected_modes = sum(
        bool(value)
        for value in (args.archive, args.status, args.restore, args.restore_archive, args.verify_archive)
    )
    if selected_modes > 1:
        raise SystemExit("Use only one of --archive, --status, --restore, --restore-archive, or --verify-archive")
    if args.limit is not None and (args.status or args.restore or args.restore_archive or args.verify_archive):
        raise SystemExit("--limit is only supported for upload/mirror sync")

    source_specs: list[tuple[Path, str]] = []
    if not args.archive and not args.restore_archive and not args.verify_archive:
        if args.source:
            source_specs = [
                (Path(source).resolve(), args.remote_subfolder or default_remote_subfolder(Path(source).resolve()))
                for source in args.source
            ]
        elif args.restore:
            source_specs = [(path.resolve(), remote_subfolder) for path, remote_subfolder in DEFAULT_SOURCE_SPECS]
        else:
            missing_defaults = [(path, remote_subfolder) for path, remote_subfolder in DEFAULT_SOURCE_SPECS if not path.exists()]
            for missing, remote_subfolder in missing_defaults:
                print(f"Skipping missing default source: {missing}")
            source_specs = [(path.resolve(), remote_subfolder) for path, remote_subfolder in DEFAULT_SOURCE_SPECS if path.exists()]
            if not source_specs:
                default_list = ", ".join(str(path) for path, _remote_subfolder in DEFAULT_SOURCE_SPECS)
                raise SystemExit(f"No default source folders found: {default_list}")
        if args.remote_subfolder and len(source_specs) != 1:
            raise SystemExit("--remote-subfolder can only be used when mirroring one --source folder")

    try:
        if args.verify_archive:
            archive_path = Path(args.verify_archive).resolve()
            if not archive_path.is_file():
                raise SystemExit(f"Archive file not found: {archive_path}")
            validate_archive_members(archive_path, REPO_ROOT)
            _checked, missing = verify_archive_contents(archive_path, REPO_ROOT)
            if missing:
                raise SystemExit(1)
        elif args.archive:
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
        elif args.restore_archive:
            restore_archive_from_drive(
                archive_name=args.restore_archive,
                drive_root_id=args.drive_root_id,
                drive_root_name=args.drive_root_name,
                repo_folder_name=args.repo_folder_name,
                remote_subfolder=args.remote_subfolder or "archives",
                oauth_client=Path(args.oauth_client),
                oauth_token=Path(args.oauth_token),
                dry_run=args.dry_run,
                retries=args.retries,
            )
        elif args.status:
            for index, (source_root, remote_subfolder) in enumerate(source_specs, 1):
                if len(source_specs) > 1:
                    print(f"\n=== Status {index}/{len(source_specs)}: {remote_subfolder} ===")
                status_artifacts(
                    source_root=source_root,
                    drive_root_id=args.drive_root_id,
                    drive_root_name=args.drive_root_name,
                    repo_folder_name=args.repo_folder_name,
                    remote_subfolder=remote_subfolder,
                    oauth_client=Path(args.oauth_client),
                    oauth_token=Path(args.oauth_token),
                    retries=args.retries,
                )
        elif args.restore:
            for index, (destination_root, remote_subfolder) in enumerate(source_specs, 1):
                if len(source_specs) > 1:
                    print(f"\n=== Restore {index}/{len(source_specs)}: {remote_subfolder} ===")
                restore_artifacts(
                    destination_root=destination_root,
                    drive_root_id=args.drive_root_id,
                    drive_root_name=args.drive_root_name,
                    repo_folder_name=args.repo_folder_name,
                    remote_subfolder=remote_subfolder,
                    oauth_client=Path(args.oauth_client),
                    oauth_token=Path(args.oauth_token),
                    dry_run=args.dry_run,
                    retries=args.retries,
                    progress_every=max(1, args.progress_every),
                    prune_local=args.prune_local,
                    yes=args.yes,
                    required_remote=bool(args.source),
                )
        else:
            for index, (source_root, remote_subfolder) in enumerate(source_specs, 1):
                if len(source_specs) > 1:
                    print(f"\n=== Source {index}/{len(source_specs)}: {remote_subfolder} ===")
                mirror_artifacts(
                    source_root=source_root,
                    drive_root_id=args.drive_root_id,
                    drive_root_name=args.drive_root_name,
                    repo_folder_name=args.repo_folder_name,
                    remote_subfolder=remote_subfolder,
                    oauth_client=Path(args.oauth_client),
                    oauth_token=Path(args.oauth_token),
                    dry_run=args.dry_run,
                    limit=args.limit,
                    retries=args.retries,
                    progress_every=max(1, args.progress_every),
                    delete_extras=not args.no_delete,
                    yes=args.yes,
                )
    except Exception as exc:
        friendly = _describe_http_error(exc)
        if friendly:
            raise SystemExit(friendly) from exc
        raise


if __name__ == "__main__":
    main()