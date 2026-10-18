"""Explicit preference memory and user-directed memory management.

Never derive preferences from unrequested chat content.
"""
import json
import re
from backend.storage import utc_now

NAMESPACE = "user_preferences"
KEY = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _key(key):
    if not isinstance(key, str) or not KEY.fullmatch(key):
        raise ValueError("Invalid preference key")
    return key


def set_preference(store, key, value):
    _key(key)
    if not isinstance(value, str) or not value.strip() or len(value) > 500:
        raise ValueError("Invalid preference value")
    store.put(NAMESPACE, key, {"text": value.strip(), "source": "explicit-user-setting"})
    return {"key": key, "text": value.strip()}


def list_preferences(store):
    rows = store.connection.execute(
        "SELECT record_id,payload FROM records WHERE namespace=? ORDER BY record_id LIMIT 200",
        (NAMESPACE,)
    ).fetchall()
    return [{"key": rid, "text": json.loads(raw)["text"]} for rid, raw in rows]


def list_memories(store, limit=50):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Invalid limit")
    rows = store.connection.execute(
        "SELECT record_id,payload FROM records WHERE namespace='memories' "
        "ORDER BY updated_at DESC LIMIT ?", (limit,)
    ).fetchall()
    result = []
    for rid, raw in rows:
        value = json.loads(raw)
        if isinstance(value, dict) and isinstance(value.get("text"), str):
            result.append({"id": rid, "text": value["text"], "source": value.get("source", "")})
    return result


def delete_record(store, namespace, key):
    if namespace not in ("memories", NAMESPACE):
        raise ValueError("Invalid namespace")
    if not isinstance(key, str) or not key or len(key) > 512:
        raise ValueError("Invalid record ID")
    with store.connection:
        removed = store.connection.execute(
            "DELETE FROM records WHERE namespace=? AND record_id=?", (namespace, key)
        ).rowcount
    return {"deleted": bool(removed)}


def update_memory(store, record_id, text):
    if not isinstance(record_id, str) or not record_id or len(record_id) > 512:
        raise ValueError("Invalid memory ID")
    if not isinstance(text, str) or not text.strip() or len(text) > 3000:
        raise ValueError("Invalid memory text")
    with store.connection:
        row = store.connection.execute(
            "SELECT payload FROM records WHERE namespace='memories' AND record_id=?", (record_id,)
        ).fetchone()
        if not row:
            raise ValueError("Memory not found")
        value = json.loads(row[0])
        value["text"] = text.strip()
        value["source"] = "user-edited"
        store.connection.execute(
            "UPDATE records SET payload=?,updated_at=? WHERE namespace='memories' AND record_id=?",
            (json.dumps(value, ensure_ascii=False), utc_now(), record_id),
        )
    return {"updated": True}
