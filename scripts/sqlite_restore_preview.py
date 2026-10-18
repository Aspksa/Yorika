"""Read-only SQLite restoration preview.

This tool never modifies the active Yorika database. It validates a backup,
checks expected schema tables, and optionally verifies a published SHA256.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

EXPECTED_TABLES = {"records", "events"}
SUPPORTED_SCHEMA = 1


def preview(path: Path, expected_sha256: str | None = None) -> dict:
    path = Path(path).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError("Expected a regular SQLite file")
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    if expected_sha256 is not None:
        if len(expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_sha256.lower()):
            raise ValueError("Invalid SHA256 digest")
        if digest != expected_sha256.lower():
            raise ValueError("Backup SHA256 mismatch")

    # immutable=1 prevents writes to the candidate, including WAL/shm files.
    # A backup produced by sqlite_backup.py is a self-contained checkpoint.
    uri = path.as_uri() + "?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        integrity_rows = [row[0] for row in db.execute("PRAGMA integrity_check")]
        if integrity_rows != ["ok"]:
            raise ValueError("SQLite integrity check failed")
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version != SUPPORTED_SCHEMA:
            raise ValueError("Unsupported Yorika schema version: " + str(version))
        tables = {row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        if not EXPECTED_TABLES.issubset(tables):
            raise ValueError("Backup does not contain Yorika data tables")
        # A matching table name alone does not make a backup restorable.
        expected = {
            "records": {
                "namespace": ("TEXT", 1, 1),
                "record_id": ("TEXT", 1, 2),
                "payload": ("TEXT", 1, 0),
                "updated_at": ("TEXT", 1, 0),
            },
            "events": {
                "event_id": ("INTEGER", 0, 1),
                "event_type": ("TEXT", 1, 0),
                "payload": ("TEXT", 1, 0),
                "recorded_at": ("TEXT", 1, 0),
            },
        }
        for table, columns in expected.items():
            info = db.execute("PRAGMA table_info(" + table + ")").fetchall()
            actual = {row[1]: (row[2].upper(), row[3], row[5]) for row in info}
            if any(actual.get(name) != spec for name, spec in columns.items()):
                raise ValueError("Backup schema mismatch: " + table)
        counts = {}
        for name in sorted(EXPECTED_TABLES):
            counts[name] = db.execute("SELECT COUNT(*) FROM " + name).fetchone()[0]
    return {"sha256": digest, "schema_version": version, "integrity": "ok",
            "counts": counts, "read_only": True}


def main():
    parser = argparse.ArgumentParser(description="Preview a Yorika SQLite backup without restoring it")
    parser.add_argument("backup", type=Path)
    parser.add_argument("--sha256", help="Expected SHA256 from the backup report")
    args = parser.parse_args()
    print(json.dumps(preview(args.backup, args.sha256), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
