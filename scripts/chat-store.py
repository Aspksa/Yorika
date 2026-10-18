#!/usr/bin/env python3
"""Versioned SQLite chat snapshots. Only exact-revision writes are accepted."""
import json
import hashlib
import math
import re
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
        if not isinstance(ts, (int, float)) or isinstance(ts, bool) or not 0 <= ts < 10**16 or not math.isfinite(ts):
            raise ValueError("Invalid timestamp")
        result.append({"from": m["from"], "text": m["text"], "ts": ts})
    return result


# Only explicit user instructions are captured. Never mine arbitrary private chat.
REMEMBER_PATTERN = re.compile(r"^\s*(?:запомни\s*[:：,]?|remember\s*[:：,]?)\s*(.+?)\s*$", re.I | re.S)

def capture_explicit_memories(db, old_history, new_history):
    """Add source-linked memories from new explicit user requests only."""
    seen = {(m["from"], m["text"], m["ts"]) for m in old_history}
    count = 0
    for message in new_history:
        key = (message["from"], message["text"], message["ts"])
        if key in seen:
            continue
        seen.add(key)
        if message["from"] != "me":
            continue
        match = REMEMBER_PATTERN.fullmatch(message["text"])
        if not match or not match.group(1).strip():
            continue
        content = match.group(1).strip()
        if len(content) > 3000:
            continue
        digest = hashlib.sha256(
            json.dumps(key, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        source_id = "chat:" + digest
        value = {"text": content, "source": "explicit-chat-request",
                 "source_id": source_id,
                 "created_at": datetime.now(timezone.utc).isoformat()}
        db.execute(
            "INSERT OR IGNORE INTO records(namespace,record_id,payload,updated_at) "
            "VALUES(?,?,?,?)",
            ("memories", source_id, json.dumps(value, ensure_ascii=False),
             value["created_at"]),
        )
        count += 1
    return count

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
            if action == "put":
                capture_explicit_memories(db, current["history"] or [], history)
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
