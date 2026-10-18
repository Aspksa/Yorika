#!/usr/bin/env python3
"""Same-origin server helper for Cloud.ru key management; never prints secrets."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.cloud_ru_vault import (read_credentials, save_credentials,
                                   delete_credentials, public_status)
from backend.storage import Store
from backend.memory_controls import (set_preference, list_preferences, list_memories,
                                     delete_record, update_memory)
from backend.persona_growth import stats, list_replies, remove_reply, set_enabled
from backend.persona_vocabulary import vocabulary_stats


def run(action, data=None, *, test_call=None):
    if action in ("memory-status", "memory-set", "memory-delete", "memory-edit"):
        with Store() as store:
            if action == "memory-status":
                return {"memories": list_memories(store), "preferences": list_preferences(store)}
            if not isinstance(data, dict):
                raise ValueError("Missing memory data")
            if action == "memory-set":
                return set_preference(store, data.get("key"), data.get("text"))
            if action == "memory-delete":
                return delete_record(store, data.get("namespace"), data.get("id"))
            return update_memory(store, data.get("id"), data.get("text"))
    if action == "persona-status":
        with Store() as store:
            return {**stats(store), "replies": list_replies(store, 20),
                    "vocabulary": vocabulary_stats(store, limit=10)}
    if action == "persona-config":
        if not isinstance(data, dict):
            raise ValueError("Missing settings")
        with Store() as store:
            return set_enabled(store, data.get("enabled"))
    if action == "persona-delete":
        if not isinstance(data, dict):
            raise ValueError("Missing reply ID")
        with Store() as store:
            return remove_reply(store, data.get("id"))
    if action == "status":
        return public_status()
    if action == "save":
        if not isinstance(data, dict):
            raise ValueError("Missing settings")
        key = data.get("key")
        model = data.get("model")
        if key is None:
            old = read_credentials()
            if old is None:
                raise ValueError("Key required")
            key = old["key"]
        save_credentials(key, model)
        return public_status()
    if action == "delete":
        delete_credentials()
        return public_status()
    if action == "diagnostics":
        value = public_status()
        value["python_ok"] = True
        value["key_accessible"] = value["configured"]
        value["live_check_required"] = True
        return value
    if action == "check":
        credential = read_credentials()
        if credential is None:
            raise ValueError("Cloud.ru key not configured")
        if test_call is None:
            import importlib.util
            target = Path(__file__).with_name("cloud-ru-model.py")
            spec = importlib.util.spec_from_file_location("yorika_cloud_model", target)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            test_call = module.answer
        # Explicit check: never attach SQLite memories to a diagnostic request.
        response = test_call("Ответь одним словом: готово", model=credential["model"],
                             api_key=credential["key"], include_memory=False)
        return {"connected": bool(response.get("answer")), "model": credential["model"]}
    raise ValueError("Unknown action")


def main():
    action = sys.argv[1] if len(sys.argv) == 2 else ""
    data = json.load(sys.stdin) if action in ("save", "persona-config", "persona-delete", "memory-set", "memory-delete", "memory-edit") else None
    result = run(action, data)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, TypeError, KeyError) as exc:
        # Provider errors are classified without echoing responses, credentials, or URLs.
        message = str(exc)
        if isinstance(exc, ValueError):
            safe = message if len(message) < 160 else "Invalid configuration"
        elif "HTTP 401" in message:
            safe = "Cloud.ru отклонил API-ключ (401). Проверьте ключ."
        elif "HTTP 403" in message:
            safe = "Недостаточно разрешений Cloud.ru (403)."
        elif "HTTP 429" in message:
            safe = "Cloud.ru ограничил частоту запросов (429)."
        elif "unavailable" in message.lower():
            safe = "Cloud.ru недоступен. Проверьте сеть и модель."
        else:
            safe = "Операция Cloud.ru не выполнена"
        print(json.dumps({"error": safe}, ensure_ascii=False))
        sys.exit(1)
