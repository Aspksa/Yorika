"""Bounded Cloud.ru conversation turns persisted outside the application directory."""
import json
import re

from backend.storage import utc_now

NAMESPACE = "cloud_ru_history"
RECORD_ID = "current.v1"
THREAD_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def record_id(conversation_id=None):
    if conversation_id is None:
        return RECORD_ID
    if not isinstance(conversation_id, str) or not THREAD_ID.fullmatch(conversation_id):
        raise ValueError("Invalid conversation ID")
    return "thread." + conversation_id
MAX_TURNS = 8
MAX_TEXT = 4000


def load_history(store, conversation_id=None):
    row = store.connection.execute(
        "SELECT payload FROM records WHERE namespace=? AND record_id=?",
        (NAMESPACE, record_id(conversation_id)),
    ).fetchone()
    if not row:
        return []
    try:
        messages = json.loads(row[0])
    except (ValueError, TypeError):
        return []
    if not isinstance(messages, list):
        return []
    clean = []
    for message in messages[-MAX_TURNS * 2:]:
        if (isinstance(message, dict)
                and message.get("role") in ("user", "assistant")
                and isinstance(message.get("content"), str)
                and 0 < len(message["content"]) <= MAX_TEXT):
            clean.append({"role": message["role"], "content": message["content"]})
    return clean


def save_turn(store, question, answer, conversation_id=None):
    if not isinstance(question, str) or not isinstance(answer, str):
        raise ValueError("Invalid dialogue turn")
    messages = load_history(store, conversation_id)
    messages.extend([
        {"role": "user", "content": question[:MAX_TEXT]},
        {"role": "assistant", "content": answer[:MAX_TEXT]},
    ])
    messages = messages[-MAX_TURNS * 2:]
    with store.connection:
        store.connection.execute(
            "INSERT INTO records(namespace,record_id,payload,updated_at) VALUES(?,?,?,?) "
            "ON CONFLICT(namespace,record_id) DO UPDATE SET "
            "payload=excluded.payload, updated_at=excluded.updated_at",
            (NAMESPACE, record_id(conversation_id), json.dumps(messages, ensure_ascii=False), utc_now()),
        )
