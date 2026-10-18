#!/usr/bin/env python3
"""Tiny, optional JSON-over-stdin bridge to the stable SQLite store.

Never executes code from chat text; never talks to external services.
"""
import json
import sys
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

def main():
    action = sys.argv[1] if len(sys.argv) == 2 else ""
    if action not in ("get", "put", "clear"):
        raise ValueError("Unknown action")
    payload = json.load(sys.stdin) if action == "put" else None
    history = valid_history(payload) if action == "put" else None
    with Store() as store:
        if action == "get":
            item = store.get("chat", "default")
            result = {"history": valid_history(item["history"]) if item else None}
        else:
            store.put("chat", "default", {"history": history if action == "put" else []})
            result = {"ok": True}
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        sys.exit(1)
