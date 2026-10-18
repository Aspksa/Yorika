"""Local SQLite storage foundation. Does not expose any HTTP endpoints yet.

User data lives outside versioned application directories by default.
No untrusted input is interpreted as SQL identifiers.
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

SCHEMA_VERSION = 1

def data_directory() -> Path:
    """Use the current Windows user's local application data, never the repo/release directory."""
    root = os.environ.get("LOCALAPPDATA")
    if root:
        return Path(root) / "Yorika" / "data"
    # Non-Windows development fallback; never silently put real data in git checkout.
    return Path.home() / ".local" / "share" / "Yorika" / "data"

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

class Store:
    def __init__(self, directory: Path | None = None):
        self.directory = (directory or data_directory()).expanduser().resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "yorika.sqlite3"
        self.connection = sqlite3.connect(str(self.path), timeout=15)
        try:
            self.connection.execute("PRAGMA busy_timeout=15000")
            self.connection.execute("PRAGMA foreign_keys=ON")
            result = self.connection.execute("PRAGMA quick_check").fetchone()[0]
            if result != "ok":
                raise RuntimeError("SQLite integrity check failed: " + str(result))
            self.connection.execute("PRAGMA journal_mode=WAL")
            self._migrate()
        except BaseException:
            self.connection.close()
            raise

    def _migrate(self) -> None:
        current = int(self.connection.execute("PRAGMA user_version").fetchone()[0])
        if current > SCHEMA_VERSION:
            raise RuntimeError("Database was created by a newer Yorika; refusing downgrade")
        if current == 0:
            # Unversioned databases containing user tables are not blank.
            # Refuse to claim schema v1 without an explicit migration.
            existing = {row[0] for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            if existing:
                raise RuntimeError("Unversioned database contains tables; refusing automatic migration")
            with self.connection:
                self.connection.execute(
                    "CREATE TABLE IF NOT EXISTS records ("
                    "namespace TEXT NOT NULL, record_id TEXT NOT NULL, "
                    "payload TEXT NOT NULL, updated_at TEXT NOT NULL, "
                    "PRIMARY KEY(namespace, record_id))"
                )
                self.connection.execute(
                    "CREATE TABLE IF NOT EXISTS events ("
                    "event_id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "event_type TEXT NOT NULL, payload TEXT NOT NULL, recorded_at TEXT NOT NULL)"
                )
                self.connection.execute("PRAGMA user_version=1")

        if current == SCHEMA_VERSION:
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
                info = self.connection.execute("PRAGMA table_info(" + table + ")").fetchall()
                actual = {row[1]: (row[2].upper(), row[3], row[5]) for row in info}
                if any(actual.get(name) != spec for name, spec in columns.items()):
                    raise RuntimeError("Yorika database schema mismatch: " + table)

    def put(self, namespace: str, record_id: str, value: dict) -> None:
        if not namespace or not record_id or not isinstance(value, dict):
            raise ValueError("namespace/record_id must be non-empty and value must be an object")
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
        with self.connection:
            self.connection.execute(
                "INSERT INTO records(namespace,record_id,payload,updated_at) VALUES(?,?,?,?) "
                "ON CONFLICT(namespace,record_id) DO UPDATE SET "
                "payload=excluded.payload,updated_at=excluded.updated_at",
                (namespace, record_id, encoded, utc_now()),
            )

    def get(self, namespace: str, record_id: str) -> dict | None:
        row = self.connection.execute(
            "SELECT payload FROM records WHERE namespace=? AND record_id=?",
            (namespace, record_id),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def append_event(self, event_type: str, value: dict) -> int:
        if not event_type or not isinstance(value, dict):
            raise ValueError("event_type must be non-empty and value must be an object")
        with self.connection:
            cursor = self.connection.execute(
                "INSERT INTO events(event_type,payload,recorded_at) VALUES(?,?,?)",
                (event_type, json.dumps(value, ensure_ascii=False, allow_nan=False), utc_now()),
            )
            return int(cursor.lastrowid)

    def backup(self, destination: Path) -> Path:
        """Create a consistent SQLite snapshot (including WAL contents)."""
        # Use the verified exclusive snapshot utility; never overwrite a user backup.
        from scripts.sqlite_backup import create_verified_backup
        if self.connection.in_transaction:
            raise RuntimeError("Commit or rollback the current transaction before backup")
        report = create_verified_backup(self.path, destination)
        return Path(report["path"])

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
