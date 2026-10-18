#!/usr/bin/env python3
"""Versioned SQLite chat snapshots. Only exact-revision writes are accepted."""
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.storage import Store

MAX_MESSAGES = 5000
MAX_TEXT = 4000


def valid_history(obj):
    if not isinstance(obj, list) or len(obj) > MAX_MESSAGES:
        raise ValueError("Invalid message history length")
    result = []
    for m in obj:
        if not isinstance(m, dict) or m.get("from") not in ("me", "bot") or not isinstance(m.get("text"), str):
            raise ValueError("Invalid message")
        if len(m["text"]) > MAX_TEXT:
            raise ValueError("Message too long")
        ts = m.get("ts")
        if not isinstance(ts, (int, float)) or isinstance(ts, bool) or not 0 <= ts < 10**16:
            raise ValueError("Invalid timestamp")
        result.append({"from": m["from"], "text": m["text"], "ts": ts})
    return result


def read_record(db):
    row = db.execute("SELECT payload FROM records WHERE namespace=? AND record_id=?",
                     ("chat", "default")).fetchone()
    value = json.loads(row[0]) if row else None
    return {"history": valid_history(value["history"]) if value else None,
            "revision": value.get("revision", 0) if value else 0}


def run(action, payload=None, directory=None):
    if action not in ("get", "put", "clear"):
        raise ValueError("Unknown action")
    if action in ("put", "clear"):
        if not isinstance(payload, dict):
            raise ValueError("Expected revision and history")
        expected = payload.get("revision")
        if type(expected) is not int or expected < 0:
            raise ValueError("Expected nonnegative integer revision")
        history = valid_history(payload.get("history")) if action == "put" else []
    with Store(directory) as store:
        db = store.connection
        if action == "get":
            return read_record(db)
        db.execute("BEGIN IMMEDIATE")
        try:
            current = read_record(db)
            if expected != current["revision"]:
                db.rollback()
                return dict(current, conflict=True)
            new_revision = expected + 1
            json_value = json.dumps({"history": history, "revision": new_revision},
                                    ensure_ascii=False, allow_nan=False)
            timestamp = datetime.now(timezone.utc).isoformat()
            db.execute(
                "INSERT INTO records(namespace,record_id,payload,updated_at) VALUES(?,?,?,?) "
                "ON CONFLICT(namespace,record_id) DO UPDATE SET "
                "payload=excluded.payload,updated_at=excluded.updated_at",
                ("chat", "default", json_value, timestamp))
            db.commit()
        except BaseException:
            db.rollback()
            raise
        return {"ok": True, "revision": new_revision}


def main():
    action = sys.argv[1] if len(sys.argv) == 2 else ""
    payload = json.load(sys.stdin) if action in ("put", "clear") else None
    print(json.dumps(run(action, payload), ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, sqlite3.DatabaseError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        sys.exit(1)
