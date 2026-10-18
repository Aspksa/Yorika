"""Create and verify a consistent SQLite backup without modifying the source.

Uses only the Python standard library. A backup is never considered successful
unless an independently opened copy passes SQLite integrity_check.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_snapshot(path: Path) -> dict:
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    uri = path.as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        status = database.execute("PRAGMA integrity_check").fetchone()[0]
        version = database.execute("PRAGMA user_version").fetchone()[0]
        if status != "ok":
            raise ValueError("SQLite integrity check failed: " + str(status))
    return {"path": str(path), "sha256": sha256_file(path), "user_version": version, "integrity": status}


def create_verified_backup(source: Path, target: Path) -> dict:
    source, target = Path(source).resolve(), Path(target).expanduser().absolute()
    if source == target:
        raise ValueError("Backup cannot overwrite source database")
    if not source.is_file():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        raise FileExistsError("Backup destination already exists")
    fd, tmp_name = tempfile.mkstemp(prefix=".yorika-backup-", suffix=".sqlite3", dir=target.parent)
    os.close(fd)
    temporary = Path(tmp_name)
    try:
        source_uri = source.as_uri() + "?mode=ro"
        with closing(sqlite3.connect(source_uri, uri=True)) as active:
            with closing(sqlite3.connect(str(temporary))) as destination:
                active.backup(destination)
        report = verify_snapshot(temporary)
        # Exclusive creation: never replace another file created during backup.
        os.link(temporary, target)
        report["path"] = str(target)
        return report
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Non-destructive Yorika SQLite backup and verification")
    parser.add_argument("source", type=Path, help="Live SQLite file")
    parser.add_argument("destination", type=Path, help="New snapshot filename (must not exist)")
    args = parser.parse_args()
    report = create_verified_backup(args.source, args.destination)
    print("verified:", report["path"], "sha256:", report["sha256"], "schema:", report["user_version"])


if __name__ == "__main__":
    main()
