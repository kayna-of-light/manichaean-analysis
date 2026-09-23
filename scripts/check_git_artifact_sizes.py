"""Check blobs introduced by a commit range before pushing to GitHub."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
WARNING_BYTES = 50 * 1024 * 1024
LIMIT_BYTES = 100 * 1024 * 1024


def git(*arguments: str, input_text: str | None = None) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=REPO,
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="origin/main", help="Already-published base")
    parser.add_argument("--head", default="HEAD", help="Tip to check, including intermediate commits")
    args = parser.parse_args()
    base = git("rev-parse", "--verify", "--end-of-options", f"{args.base}^{{commit}}").strip()
    head = git("rev-parse", "--verify", "--end-of-options", f"{args.head}^{{commit}}").strip()
    objects = git("rev-list", "--objects", f"{base}..{head}")
    details = git(
        "cat-file",
        "--batch-check=%(objecttype) %(objectname) %(objectsize) %(rest)",
        input_text=objects,
    )
    blocked = 0
    warnings = 0
    blobs = 0
    total_bytes = 0
    for line in details.splitlines():
        object_type, object_id, size_text, *name = line.split(" ", 3)
        if object_type != "blob":
            continue
        size = int(size_text)
        blobs += 1
        total_bytes += size
        if size <= WARNING_BYTES:
            continue
        path = name[0] if name else object_id
        if size > LIMIT_BYTES:
            blocked += 1
            print(f"BLOCKED {size / 1024**2:.2f} MiB {path}")
        else:
            warnings += 1
            print(f"WARNING {size / 1024**2:.2f} MiB {path}")
    print(
        f"{blobs} new blobs, {total_bytes / 1024**2:.2f} MiB uncompressed; "
        f"{blocked} over 100 MiB, {warnings} over 50 MiB."
    )
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())