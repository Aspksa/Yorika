"""Restore a verified Yorika snapshot into a NEW, empty destination.

Never replaces a live database. To switch over, stop Yorika and perform a
separately reviewed recovery procedure; this module intentionally cannot do it.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile

from scripts.sqlite_restore_preview import preview


def restore_copy(source: Path, destination: Path, sha256: str) -> dict:
    source = Path(source).expanduser().resolve(strict=True)
    destination = Path(destination).expanduser().resolve()
    if source == destination:
        raise ValueError("Source and destination must differ")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Destination already exists")
    if not sha256:
        raise ValueError("A trusted expected SHA256 is required")
    checked = preview(source, sha256)
    if not destination.parent.is_dir():
        raise FileNotFoundError("Destination parent directory must exist")
    fd, name = tempfile.mkstemp(prefix=".yorika-restore-", suffix=".sqlite3", dir=destination.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as output, source.open("rb") as original:
            shutil.copyfileobj(original, output)
            output.flush()
            os.fsync(output.fileno())
        preview(temporary, checked["sha256"])
        # Fail closed if another file appeared during copy.
        try:
            os.link(temporary, destination)
        except OSError:
            if destination.exists():
                raise FileExistsError("Destination created concurrently")
            raise
        return preview(destination, checked["sha256"])
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Restore checked Yorika backup into NEW file; never overwrite")
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(restore_copy(args.source, args.destination, args.sha256), indent=2))


if __name__ == "__main__":
    main()
