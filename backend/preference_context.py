"""Render explicitly saved user preferences as bounded, untrusted Cloud.ru context.

Preferences are user-controlled data, not system/developer instructions.
"""
import json
from backend.memory_controls import list_preferences

MAX_ITEMS = 20
MAX_TOTAL = 1600
MAX_VALUE = 200


def preference_context(store):
    rows = list_preferences(store)
    parts = []
    for item in rows[:MAX_ITEMS]:
        key = item.get("key")
        value = item.get("text")
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        parts.append(json.dumps({"key": key, "value": value[:MAX_VALUE]}, ensure_ascii=False))
    return "\n".join(parts)[:MAX_TOTAL]
