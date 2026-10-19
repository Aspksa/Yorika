"""Self-learning loop for the «Обучение» page: experience from chat, owner ratings, decisions.

Chat pairs are collected only after the owner turns collection on. Only answers the owner
approved (👍) or corrected become training records, so every exported record is reviewed by
a person. New model versions are only ever proposed; switching stays an explicit click.
"""
import hashlib
import json
import re
from datetime import datetime, timezone

from backend import training_center as tc

EMAIL = re.compile(r"(?<![\w.])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
SECRET = re.compile(r"(?i)(?:api[_ -]?key|password|token|пароль|ключ)\s*[:=]\s*\S+")
# Fixed error texts the chat shows when no model answered; they are not Yorika's answers.
NOT_AN_ANSWER = re.compile(r"^(?:Cloud\.ru:|Python 3 не найден|Ошибка|Нет ответа)", re.I)
MAX_TEXT = 2000
MAX_ITEMS = 100000
RATINGS = (None, "up", "down")


def _store_path():
    return tc.folder() / "experience.json"


def _settings_path():
    return tc.folder() / "self-learning.json"


def _settings():
    data = tc._read(_settings_path(), {}) or {}
    return {"collect": data.get("collect") is True, "dismissed": list(data.get("dismissed", []))[-200:],
            "collected_at": data.get("collected_at")}


def _save_settings(settings):
    tc._write(_settings_path(), settings)


def _load():
    data = tc._read(_store_path(), {}) or {}
    return {"items": data.get("items", []), "removed": data.get("removed", [])}


def _save(store):
    tc._write(_store_path(), {"schema": "yorika-experience-v1", "items": store["items"][-MAX_ITEMS:],
                              "removed": store["removed"][-MAX_ITEMS:]})


def _id(prompt, ts):
    return hashlib.sha256(json.dumps([prompt, ts], ensure_ascii=False).encode("utf-8")).hexdigest()[:20]


def set_collect(enabled):
    if not isinstance(enabled, bool):
        raise ValueError("Неверное значение")
    settings = _settings()
    settings["collect"] = enabled
    _save_settings(settings)
    return {"collect": enabled}


def chat_pairs(history):
    """Each owner message followed directly by Yorika's reply, without errors, secrets or e-mail."""
    pairs = []
    for ask, reply in zip(history, history[1:]):
        if ask.get("from") != "me" or reply.get("from") != "bot":
            continue
        prompt, answer = ask.get("text", "").strip(), reply.get("text", "").strip()
        if not 1 <= len(prompt) <= MAX_TEXT or not 1 <= len(answer) <= MAX_TEXT:
            continue
        if NOT_AN_ANSWER.match(answer) or any(EMAIL.search(s) or SECRET.search(s) for s in (prompt, answer)):
            continue
        pairs.append({"id": _id(prompt, ask.get("ts")), "prompt": prompt, "answer": answer, "ts": ask.get("ts")})
    return pairs


def _chat_history(directory=None):
    from backend.storage import Store
    with Store(directory) as store:
        row = store.connection.execute("SELECT payload FROM records WHERE namespace=? AND record_id=?",
                                       ("chat", "default")).fetchone()
    if not row:
        return []
    history = json.loads(row[0]).get("history", [])
    return history if isinstance(history, list) else []


def collect(chat_directory=None):
    settings = _settings()
    if not settings["collect"]:
        raise ValueError("Сначала включите сбор опыта")
    store = _load()
    known = {item["id"] for item in store["items"]} | set(store["removed"])
    added = 0
    for pair in chat_pairs(_chat_history(chat_directory)):
        if pair["id"] in known:
            continue
        store["items"].append(dict(pair, rating=None, correction=None, source="yorika-chat"))
        known.add(pair["id"])
        added += 1
    _save(store)
    settings["collected_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _save_settings(settings)
    return {"added": added, "counts": counts(store)}


def counts(store=None):
    items = (store or _load())["items"]
    up = sum(1 for i in items if i["rating"] == "up")
    fixed = sum(1 for i in items if i["rating"] == "down" and i.get("correction"))
    down = sum(1 for i in items if i["rating"] == "down" and not i.get("correction"))
    return {"total": len(items), "up": up, "fixed": fixed, "down": down,
            "unrated": sum(1 for i in items if i["rating"] is None), "ready": up + fixed,
            "needed": tc.MIN_LONG_RECORDS}


def list_items(view="unrated", offset=0, limit=20):
    if view not in ("unrated", "up", "down", "all"):
        raise ValueError("Неизвестный фильтр")
    if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= 50:
        raise ValueError("Неверная страница")
    items = list(reversed(_load()["items"]))
    if view != "all":
        items = [i for i in items if i["rating"] == (None if view == "unrated" else view)]
    return {"items": items[offset:offset + limit], "matching": len(items), "counts": counts()}


def rate(item_id, rating, correction=None):
    if rating not in RATINGS:
        raise ValueError("Неизвестная оценка")
    if correction is not None:
        if not isinstance(correction, str) or len(correction.strip()) > MAX_TEXT:
            raise ValueError("Исправление до 2000 символов")
        correction = correction.strip() or None
        if correction and (EMAIL.search(correction) or SECRET.search(correction)):
            raise ValueError("В исправлении похоже на почту, пароль или ключ")
    store = _load()
    for item in store["items"]:
        if item["id"] == item_id:
            item["rating"] = rating
            item["correction"] = correction if rating == "down" else None
            _save(store)
            return {"item": item, "counts": counts(store)}
    raise ValueError("Пример не найден")


def delete(item_id):
    store = _load()
    before = len(store["items"])
    store["items"] = [i for i in store["items"] if i["id"] != item_id]
    if len(store["items"]) == before:
        raise ValueError("Пример не найден")
    store["removed"].append(item_id)
    _save(store)
    return {"counts": counts(store)}


def export():
    """Writes reviewed examples as a dated data file the training block can use."""
    records, seen = [], set()
    for item in reversed(_load()["items"]):
        answer = item["answer"] if item["rating"] == "up" else item.get("correction") if item["rating"] == "down" else None
        key = item["prompt"].casefold()
        if not answer or key in seen:
            continue
        seen.add(key)
        records.append({"prompt": item["prompt"], "answer": answer, "source": "yorika-chat",
                        "license": "user-consent", "consent": True,
                        "rights_reviewed_by": "владелец Yorika", "quality_reviewed": True})
    if len(records) < 10:
        raise ValueError("Нужно хотя бы 10 оценённых примеров (👍 или исправленных)")
    name = "опыт-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + ".json"
    path = tc.folder() / "data" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(records, stream, ensure_ascii=False, indent=1)
    return {"name": name, "count": len(records), "long_ready": len(records) >= tc.MIN_LONG_RECORDS}


def proposal():
    """The newest finished long run that is neither active nor dismissed, next to the active one."""
    settings, current = _settings(), tc.active()
    for item in tc.runs():
        if (item["mode"] == "long" and item["has_best"] and item["state"] in ("finished", "paused", "stopped")
                and item["id"] not in settings["dismissed"] and not (current and current["run"] == item["id"])):
            active_run = None
            if current:
                active_run = next((r for r in tc.runs() if r["id"] == current["run"]), None)
            pick = ("id", "created", "steps", "best_nll", "best_step", "dataset", "device", "gpu_name")
            return {"candidate": {k: item[k] for k in pick},
                    "active": {k: active_run[k] for k in pick} if active_run else None}
    return None


def dismiss(run_id):
    tc._run_dir(run_id)
    settings = _settings()
    if run_id not in settings["dismissed"]:
        settings["dismissed"].append(run_id)
    _save_settings(settings)
    return {"dismissed": run_id}


def status():
    settings = _settings()
    return {"collect": settings["collect"], "collected_at": settings["collected_at"],
            "counts": counts(), "proposal": proposal()}
