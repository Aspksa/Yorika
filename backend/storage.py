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
            self._migrate()
            self.connection.execute("PRAGMA journal_mode=WAL")
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

    def get_record(self, namespace: str, record_id: str) -> dict | None:
        """Return one memory with its ID, value and update timestamp for editing."""
        if not isinstance(namespace, str) or not namespace:
            raise ValueError("namespace must be non-empty")
        if not isinstance(record_id, str) or not record_id:
            raise ValueError("record_id must be non-empty")
        row = self.connection.execute(
            "SELECT payload, updated_at FROM records WHERE namespace=? AND record_id=?",
            (namespace, record_id),
        ).fetchone()
        if row is None:
            return None
        return {"record_id": record_id, "value": json.loads(row[0]),
                "updated_at": row[1]}

    def update_record_if_unchanged(
        self, namespace: str, record_id: str, expected_value: dict, new_value: dict
    ) -> bool:
        """Conditionally edit an existing memory without overwriting concurrent changes."""
        if not isinstance(namespace, str) or not namespace:
            raise ValueError("namespace must be non-empty")
        if not isinstance(record_id, str) or not record_id:
            raise ValueError("record_id must be non-empty")
        if not isinstance(expected_value, dict) or not isinstance(new_value, dict):
            raise ValueError("expected_value and new_value must be objects")
        encoded = json.dumps(new_value, ensure_ascii=False, allow_nan=False)
        with self.connection:
            row = self.connection.execute(
                "SELECT payload FROM records WHERE namespace=? AND record_id=?",
                (namespace, record_id),
            ).fetchone()
            if row is None or json.loads(row[0]) != expected_value:
                return False
            cursor = self.connection.execute(
                "UPDATE records SET payload=?, updated_at=? "
                "WHERE namespace=? AND record_id=? AND payload=?",
                (encoded, utc_now(), namespace, record_id, row[0]),
            )
            return cursor.rowcount == 1

    def delete_record_if_unchanged(
        self, namespace: str, record_id: str, expected_value: dict
    ) -> bool:
        """Delete only an unchanged record, avoiding stale editor deletions."""
        if not isinstance(namespace, str) or not namespace:
            raise ValueError("namespace must be non-empty")
        if not isinstance(record_id, str) or not record_id:
            raise ValueError("record_id must be non-empty")
        if not isinstance(expected_value, dict):
            raise ValueError("expected_value must be an object")
        with self.connection:
            row = self.connection.execute(
                "SELECT payload FROM records WHERE namespace=? AND record_id=?",
                (namespace, record_id),
            ).fetchone()
            if row is None or json.loads(row[0]) != expected_value:
                return False
            cursor = self.connection.execute(
                "DELETE FROM records WHERE namespace=? AND record_id=? AND payload=?",
                (namespace, record_id, row[0]),
            )
            return cursor.rowcount == 1

    def delete_record(self, namespace: str, record_id: str) -> bool:
        """Delete one local record by exact namespace and ID; return whether it existed."""
        if not isinstance(namespace, str) or not namespace:
            raise ValueError("namespace must be non-empty")
        if not isinstance(record_id, str) or not record_id:
            raise ValueError("record_id must be non-empty")
        with self.connection:
            cursor = self.connection.execute(
                "DELETE FROM records WHERE namespace=? AND record_id=?",
                (namespace, record_id),
            )
            return cursor.rowcount == 1

    def list_records(self, namespace: str, limit: int = 100) -> list[dict]:
        """Enumerate saved records in stable newest-first order."""
        if not isinstance(namespace, str) or not namespace:
            raise ValueError("namespace must be non-empty")
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        rows = self.connection.execute(
            "SELECT record_id, payload, updated_at FROM records "
            "WHERE namespace=? ORDER BY updated_at DESC, record_id ASC LIMIT ?",
            (namespace, limit),
        ).fetchall()
        return [{"record_id": record_id, "value": json.loads(payload),
                 "updated_at": updated_at} for record_id, payload, updated_at in rows]

    def search_records(self, namespace: str, query: str, limit: int = 20) -> list[dict]:
        """Case-insensitive literal search in local JSON memories, including Cyrillic."""
        if not isinstance(namespace, str) or not namespace:
            raise ValueError("namespace must be non-empty")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        term = query.strip().casefold()
        # SQLite LIKE is ASCII-only case-insensitive by default; Python casefold
        # also matches Cyrillic. This is a simple scan, not an indexed FTS search.
        rows = self.connection.execute(
            "SELECT record_id, payload, updated_at FROM records "
            "WHERE namespace=? ORDER BY updated_at DESC, record_id ASC",
            (namespace,),
        )
        matches = []
        for record_id, payload, updated_at in rows:
            value = json.loads(payload)
            # Search user-facing text values, not JSON field names or syntax.
            def texts(obj):
                if isinstance(obj, str):
                    yield obj
                elif isinstance(obj, dict):
                    for child in obj.values():
                        yield from texts(child)
                elif isinstance(obj, list):
                    for child in obj:
                        yield from texts(child)

            if any(term in text.casefold() for text in texts(value)):
                matches.append({"record_id": record_id, "value": value,
                                "updated_at": updated_at})
                if len(matches) == limit:
                    break
        return matches

    def search_records_fts(self, namespace: str, query: str, limit: int = 20) -> list[dict]:
        """Rank words from local JSON text using a temporary FTS5 index.

        Index is rebuilt from the selected namespace, never persisted or sent away.
        """
        if not isinstance(namespace, str) or not namespace:
            raise ValueError("namespace must be non-empty")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        import re
        words = re.findall(r"[^\\W_]+", query.casefold(), flags=re.UNICODE)
        if not words:
            return []
        if len(words) > 20 or any(len(word) > 100 for word in words):
            raise ValueError("FTS query too large")
        # Escape input into literal FTS5 tokens, never accept query operators.
        expression = " AND ".join('"' + token.replace('"', '""') + '"' for token in words)
        def flatten(obj):
            if isinstance(obj, str):
                yield obj
            elif isinstance(obj, dict):
                for child in obj.values():
                    yield from flatten(child)
            elif isinstance(obj, list):
                for child in obj:
                    yield from flatten(child)
        with sqlite3.connect(":memory:") as fts:
            try:
                fts.execute("CREATE VIRTUAL TABLE docs USING fts5(record_id UNINDEXED, body, tokenize='unicode61')")
            except sqlite3.OperationalError as exc:
                raise RuntimeError("SQLite build lacks FTS5 support") from exc
            rows = self.connection.execute(
                "SELECT record_id,payload,updated_at FROM records WHERE namespace=?",
                (namespace,),
            )
            metadata = {}
            for record_id, payload, updated_at in rows:
                value = json.loads(payload)
                metadata[record_id] = (value, updated_at)
                fts.execute(
                    "INSERT INTO docs(record_id,body) VALUES(?,?)",
                    (record_id, " ".join(flatten(value))),
                )
            ranked = fts.execute(
                "SELECT record_id,bm25(docs) AS rank FROM docs WHERE docs MATCH ? "
                "ORDER BY rank ASC, record_id ASC LIMIT ?", (expression, limit),
            ).fetchall()
            return [
                {"record_id": rid, "value": metadata[rid][0],
                 "updated_at": metadata[rid][1], "rank": score}
                for rid, score in ranked
            ]

    def export_records(self, namespace: str) -> dict:
        """Export all records from one namespace, including stable IDs and timestamps."""
        if not isinstance(namespace, str) or not namespace:
            raise ValueError("namespace must be non-empty")
        rows = self.connection.execute(
            "SELECT record_id, payload, updated_at FROM records "
            "WHERE namespace=? ORDER BY record_id ASC",
            (namespace,),
        )
        return {"format": "yorika-records-v1", "namespace": namespace,
                "records": [{"record_id": record_id, "value": json.loads(payload),
                             "updated_at": updated_at}
                            for record_id, payload, updated_at in rows]}

    def import_records(
        self, bundle: dict, *, dry_run: bool = True, on_conflict: str = "reject"
    ) -> dict:
        """Strict, atomic import of one untrusted namespace export.

        No overwrites. Dry run by default. All validation precedes any write.
        """
        if not isinstance(bundle, dict) or set(bundle) != {"format", "namespace", "records"}:
            raise ValueError("Invalid memory export fields")
        if bundle["format"] != "yorika-records-v1":
            raise ValueError("Unsupported memory export format")
        namespace = bundle["namespace"]
        if not isinstance(namespace, str) or not namespace or len(namespace) > 256:
            raise ValueError("Invalid export namespace")
        if any(ord(c) < 32 for c in namespace):
            raise ValueError("Control character in namespace")
        entries = bundle["records"]
        if not isinstance(entries, list) or len(entries) > 100000:
            raise ValueError("Export records must be an array of at most 100000 entries")
        if type(dry_run) is not bool:
            raise ValueError("dry_run must be a boolean")
        if type(on_conflict) is not str or on_conflict not in ("reject", "skip"):
            raise ValueError("on_conflict must be reject or skip")
        prepared = []
        seen = set()
        total_bytes = 0
        for item in entries:
            if not isinstance(item, dict) or set(item) != {"record_id", "value", "updated_at"}:
                raise ValueError("Invalid memory record fields")
            record_id, value, updated_at = item["record_id"], item["value"], item["updated_at"]
            if not isinstance(record_id, str) or not record_id or len(record_id) > 512:
                raise ValueError("Invalid memory record ID")
            if any(ord(c) < 32 for c in record_id):
                raise ValueError("Control character in memory record ID")
            if record_id in seen:
                raise ValueError("Duplicate memory record ID")
            if not isinstance(value, dict):
                raise ValueError("Memory record value must be an object")
            if not isinstance(updated_at, str) or len(updated_at) > 64:
                raise ValueError("Invalid memory record timestamp")
            try:
                moment = datetime.fromisoformat(updated_at)
            except ValueError as error:
                raise ValueError("Invalid ISO8601 memory timestamp") from error
            if moment.tzinfo is None or moment.utcoffset() is None:
                raise ValueError("Memory timestamp must include timezone")
            try:
                encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
            except (TypeError, ValueError, UnicodeError, RecursionError) as error:
                raise ValueError("Memory value must contain finite JSON data") from error
            try:
                byte_size = len(encoded.encode("utf-8"))
            except UnicodeError as error:
                raise ValueError("Memory value contains invalid Unicode") from error
            if byte_size > 1024 * 1024:
                raise ValueError("Memory record exceeds 1 MiB")
            total_bytes += byte_size
            if total_bytes > 32 * 1024 * 1024:
                raise ValueError("Memory import exceeds 32 MiB")
            seen.add(record_id)
            prepared.append((namespace, record_id, encoded, updated_at))
        existing = {
            row[0] for row in self.connection.execute(
                "SELECT record_id FROM records WHERE namespace=?", (namespace,)
            )
        }
        conflicts = sum(row[1] in existing for row in prepared)
        if conflicts and on_conflict == "reject":
            raise ValueError("Memory import conflicts with existing record IDs")
        pending = [row for row in prepared if row[1] not in existing]
        applied = 0
        if not dry_run and pending:
            # Unique-key races raise IntegrityError and roll back the entire batch.
            with self.connection:
                self.connection.executemany(
                    "INSERT INTO records(namespace,record_id,payload,updated_at) "
                    "VALUES(?,?,?,?)", pending
                )
            applied = len(pending)
        return {"namespace": namespace, "dry_run": dry_run,
                "requested": len(prepared), "conflicts": conflicts,
                "eligible": len(pending), "applied": applied,
                "bytes": total_bytes}

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
