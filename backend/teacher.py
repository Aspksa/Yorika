"""Cloud.ru teacher for Yorika's own model: writes examples, reviews answers, plays against weak spots.

Every paid run is started by the owner after seeing its token estimate, stays inside a
per-run and a monthly token limit counted here, and can be stopped between requests.
The local limit is Yorika's own counter, not a billing cap on the Cloud.ru side.
Teacher output is never training data on its own: it enters the experience list unrated,
and only the owner's 👍 (or confirmation of the teacher's verdict) makes it a record.
"""
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from backend import self_learning as sl
from backend import training_center as tc

ENDPOINT = "https://foundation-models.api.cloud.ru/v1/chat/completions"
DEFAULT_MODEL = "ai-sage/GigaChat3-10B-A1.8B"
KINDS = ("generate", "review", "selfplay")
PAIRS_PER_REQUEST = 5
# Rough per-request cost used only for the estimate the owner confirms; real usage is counted.
ESTIMATE = {"generate": 1800, "review": 700, "selfplay": 1800}
DEFAULT_SETTINGS = {"per_run_tokens": 30000, "monthly_tokens": 300000}
DEFAULT_TOPICS = ["приветствие и как прошёл день", "помощь с учёбой", "планы на выходные", "погода и настроение",
                  "советы по компьютеру", "книги и фильмы", "готовка", "спорт и здоровье",
                  "когда грустно", "работа и дела", "путешествия", "музыка", "домашние животные",
                  "время и напоминания", "кто такая Yorika", "благодарность и похвала"]
TEACHER_RULES = ("Ты учитель для маленькой нейросети Yorika. Пиши по-русски, коротко и естественно, "
                 "в характере Yorika: взрослая заботливая лиса-кицунэ, честная, без выдуманных фактов, "
                 "без утверждений о настоящих чувствах. Никаких личных данных, почты, паролей и ключей.")


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dir():
    return tc.folder() / "teacher"


def settings():
    saved = tc._read(_dir() / "settings.json", {}) or {}
    return {k: int(saved.get(k, v)) for k, v in DEFAULT_SETTINGS.items()}


def set_limits(per_run_tokens, monthly_tokens):
    for value in (per_run_tokens, monthly_tokens):
        if type(value) is not int or not 1000 <= value <= 50_000_000:
            raise ValueError("Лимит от 1 000 до 50 000 000 токенов")
    if per_run_tokens > monthly_tokens:
        raise ValueError("Лимит на запуск не может быть больше месячного")
    tc._write(_dir() / "settings.json", {"per_run_tokens": per_run_tokens, "monthly_tokens": monthly_tokens})
    return settings()


def _month():
    return datetime.now(timezone.utc).strftime("%Y-%m")


def used_this_month():
    return int((tc._read(_dir() / "usage.json", {}) or {}).get(_month(), 0))


def _add_usage(tokens):
    usage = tc._read(_dir() / "usage.json", {}) or {}
    usage[_month()] = int(usage.get(_month(), 0)) + int(tokens)
    tc._write(_dir() / "usage.json", dict(sorted(usage.items())[-24:]))


def credentials():
    """Same source as the chat: DPAPI vault on Windows, environment key only off Windows."""
    if sys.platform == "win32":
        from backend.cloud_ru_vault import read_credentials
        stored = read_credentials() if os.environ.get("LOCALAPPDATA") else None
        return (stored["key"], stored["model"]) if stored else (None, None)
    key = os.environ.get("YORIKA_CLOUD_RU_API_KEY") or None
    return key, os.environ.get("YORIKA_CLOUD_RU_MODEL", DEFAULT_MODEL)


def chat(messages, *, max_tokens=1500, opener=None, key=None, model=None):
    """One bounded non-streaming request; returns (text, tokens counted)."""
    if key is None:
        key, model = credentials()
    if not key:
        raise ValueError("Ключ Cloud.ru не настроен: добавьте его в Настройках")
    payload = json.dumps({"model": model or DEFAULT_MODEL, "messages": messages, "stream": False,
                          "max_completion_tokens": max_tokens, "temperature": 0.8},
                         ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(ENDPOINT, data=payload, method="POST",
                                     headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with (opener or urllib.request.urlopen)(request, timeout=90) as response:
            raw = response.read(512 * 1024 + 1)
    except urllib.error.HTTPError as error:
        # Never surface response bodies: they can echo request details.
        known = {401: "неверный или отозванный ключ", 403: "нет доступа к модели", 429: "превышен лимит запросов"}
        raise RuntimeError("Cloud.ru HTTP %d: %s" % (error.code, known.get(error.code, "запрос отклонён"))) from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError("Cloud.ru недоступен") from None
    if len(raw) > 512 * 1024:
        raise RuntimeError("Слишком большой ответ Cloud.ru")
    try:
        data = json.loads(raw.decode("utf-8"))
        text = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        raise RuntimeError("Непонятный ответ Cloud.ru") from None
    if not isinstance(text, str):
        raise RuntimeError("Непонятный ответ Cloud.ru")
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    tokens = usage.get("total_tokens")
    if type(tokens) is not int or tokens <= 0:
        tokens = (len(json.dumps(messages, ensure_ascii=False)) + len(text)) // 3 + 1
    return text, tokens


def parse_pairs(text):
    """Pulls [{"prompt","answer"}] out of the teacher's reply, dropping anything unusable."""
    match = re.search(r"\[.*\]", text, re.S)
    if not match:
        return []
    try:
        rows = json.loads(match.group(0))
    except ValueError:
        return []
    pairs = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        prompt, answer = str(row.get("prompt", "")).strip(), str(row.get("answer", "")).strip()
        if (1 <= len(prompt) <= sl.MAX_TEXT and 1 <= len(answer) <= sl.MAX_TEXT and
                not any(sl.EMAIL.search(s) or sl.SECRET.search(s) for s in (prompt, answer))):
            pairs.append((prompt, answer))
    return pairs


def parse_review(text):
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    try:
        row = json.loads(match.group(0))
        score = int(row.get("score"))
    except (ValueError, TypeError, AttributeError):
        return None
    if not 1 <= score <= 5:
        return None
    better = row.get("better")
    better = better.strip()[:sl.MAX_TEXT] if isinstance(better, str) and better.strip() else None
    if better and (sl.EMAIL.search(better) or sl.SECRET.search(better)):
        better = None
    return {"score": score, "better": better if score <= 3 else None,
            "why": str(row.get("why", "")).strip()[:300]}


def _requests(kind, count):
    return max(1, -(-count // PAIRS_PER_REQUEST)) if kind in ("generate", "selfplay") else count


def estimate(kind, count):
    if kind not in KINDS:
        raise ValueError("Неизвестная задача учителя")
    if type(count) is not int or not 1 <= count <= 2000:
        raise ValueError("Количество от 1 до 2000")
    if kind == "review":
        count = min(count, len(_review_queue(count)))
        if not count:
            raise ValueError("Нет примеров без оценки для проверки")
    if kind == "selfplay" and not weak_prompts():
        raise ValueError("Пока нет слабых мест: поставьте 👎 хотя бы одному ответу")
    tokens = _requests(kind, count) * ESTIMATE[kind]
    limits, used = settings(), used_this_month()
    return {"kind": kind, "count": count, "requests": _requests(kind, count), "tokens": tokens,
            "per_run_limit": limits["per_run_tokens"], "monthly_limit": limits["monthly_tokens"],
            "used_this_month": used,
            "fits": tokens <= limits["per_run_tokens"] and used + tokens <= limits["monthly_tokens"]}


def weak_prompts(limit=40):
    """Where the model is weakest: answers the owner rejected, newest first."""
    items = sl._load()["items"]
    return [i["prompt"] for i in reversed(items) if i["rating"] == "down"][:limit]


def _review_queue(limit):
    return [i for i in reversed(sl._load()["items"]) if i["rating"] is None and not i.get("teacher")][:limit]


def job():
    state = tc._read(_dir() / "job.json", {}) or {}
    if state.get("state") == "running" and time.time() - state.get("t", 0) > 300:
        state["state"] = "interrupted"
    return state or None


def start(kind, count, *, confirm=False, topics=None, launch=True, budget=None):
    if confirm is not True:
        raise ValueError("Подтвердите запуск: он тратит токены Cloud.ru")
    plan = estimate(kind, count)
    if not plan["fits"]:
        raise ValueError("Не помещается в лимит токенов: уменьшите количество или поднимите лимит")
    current = job()
    if current and current.get("state") == "running":
        raise ValueError("Учитель уже работает")
    if credentials()[0] is None:
        raise ValueError("Ключ Cloud.ru не настроен: добавьте его в Настройках")
    if topics is not None and (not isinstance(topics, list) or len(topics) > 50 or
                               any(not isinstance(t, str) or not 1 <= len(t.strip()) <= 100 for t in topics)):
        raise ValueError("До 50 тем, каждая до 100 символов")
    state = {"kind": kind, "count": plan["count"], "topics": [t.strip() for t in topics or []] or None,
             "state": "running", "t": time.time(), "started": _now(), "done": 0, "added": 0,
             "tokens": 0, "budget": plan["tokens"] + plan["tokens"] // 2, "error": None}
    state["budget"] = min(state["budget"], settings()["per_run_tokens"], budget or 10 ** 12)
    (_dir() / "stop.json").unlink(missing_ok=True)
    tc._write(_dir() / "job.json", state)
    if launch:
        tc._spawn([sys.executable, str(tc.CLI), "teacher-worker"], _dir() / "worker.log")
    return state


def stop():
    current = job()
    if not current or current.get("state") != "running":
        raise ValueError("Учитель сейчас не работает")
    tc._write(_dir() / "stop.json", {"t": _now()})
    return {"requested": "stop"}


def _add_items(pairs, source):
    store = sl._load()
    known = {i["prompt"].casefold() for i in store["items"]}
    added = 0
    for prompt, answer in pairs:
        if prompt.casefold() in known:
            continue
        known.add(prompt.casefold())
        store["items"].append({"id": sl._id(prompt, _now() + source), "prompt": prompt, "answer": answer,
                               "ts": _now(), "rating": None, "correction": None, "source": source})
        added += 1
    sl._save(store)
    return added


def run_job(opener=None):
    """Worker body: one request at a time, stops on limit, stop request or error."""
    path = _dir() / "job.json"
    state = tc._read(path, {}) or {}
    key, model = credentials() if opener is None else ("test", DEFAULT_MODEL)
    monthly = settings()["monthly_tokens"]

    def save(**fields):
        state.update(fields, t=time.time())
        tc._write(path, state)
        return state

    try:
        kind, count = state["kind"], state["count"]
        topics = state.get("topics") or DEFAULT_TOPICS
        weak = weak_prompts()
        queue = _review_queue(count) if kind == "review" else None
        for n in range(_requests(kind, count)):
            if (_dir() / "stop.json").exists():
                (_dir() / "stop.json").unlink(missing_ok=True)
                return save(state="stopped")
            if state["tokens"] + ESTIMATE[kind] > state["budget"] or used_this_month() + ESTIMATE[kind] > monthly:
                return save(state="limit")
            if kind == "review":
                item = queue[n]
                messages = [{"role": "system", "content": TEACHER_RULES},
                            {"role": "user", "content":
                             "Оцени ответ Yorika от 1 до 5. Если 3 или ниже, напиши лучший ответ. "
                             "Верни только JSON {\"score\": n, \"why\": \"коротко\", \"better\": \"...\"}.\n"
                             "Вопрос: " + item["prompt"] + "\nОтвет Yorika: " + item["answer"]}]
            else:
                want = min(PAIRS_PER_REQUEST, count - n * PAIRS_PER_REQUEST)
                if kind == "generate":
                    task = "на тему «%s»" % topics[n % len(topics)]
                else:
                    seeds = [weak[(n * 3 + k) % len(weak)] for k in range(min(3, len(weak)))]
                    task = ("похожие на вопросы, где маленькая модель ошиблась (не повторяй их дословно): " +
                            "; ".join("«%s»" % s[:200] for s in seeds))
                messages = [{"role": "system", "content": TEACHER_RULES},
                            {"role": "user", "content":
                             "Придумай %d разных вопросов пользователя %s и ответь на каждый как Yorika. "
                             "Верни только JSON-массив [{\"prompt\": \"...\", \"answer\": \"...\"}]." % (want, task)}]
            text, tokens = chat(messages, opener=opener, key=key, model=model)
            _add_usage(tokens)
            state["tokens"] += tokens
            if kind == "review":
                verdict = parse_review(text)
                if verdict:
                    store = sl._load()
                    for row in store["items"]:
                        if row["id"] == item["id"]:
                            row["teacher"] = dict(verdict, model=model, at=_now())
                    sl._save(store)
                    state["added"] += 1
            else:
                state["added"] += _add_items(parse_pairs(text), "teacher" if kind == "generate" else "selfplay")
            save(done=n + 1)
        return save(state="finished")
    except Exception as error:  # the page must see why the teacher stopped
        message = str(error) if re.search("[а-яА-Я]", str(error)) else "Учитель остановился с ошибкой"
        save(state="failed", error=message[:200])
        return state


def worker():
    stop_beat = threading.Event()

    def beat():
        while not stop_beat.wait(20):
            state = tc._read(_dir() / "job.json", {}) or {}
            if state.get("state") == "running":
                state["t"] = time.time()
                tc._write(_dir() / "job.json", state)
    threading.Thread(target=beat, daemon=True).start()
    try:
        state = run_job()
    finally:
        stop_beat.set()
    return 0 if state.get("state") != "failed" else 1


def accept_verdicts():
    """Owner confirms the teacher's verdicts in bulk: 4–5 becomes 👍, 1–3 with a better answer becomes a fix."""
    store = sl._load()
    up = fixed = 0
    for item in store["items"]:
        verdict = item.get("teacher")
        if item["rating"] is not None or not verdict:
            continue
        if verdict["score"] >= 4:
            item["rating"], up = "up", up + 1
        elif verdict.get("better"):
            item["rating"], item["correction"], fixed = "down", verdict["better"], fixed + 1
        else:
            continue
        item["confirmed_teacher"] = True
    sl._save(store)
    return {"up": up, "fixed": fixed, "counts": sl.counts(store)}


def status():
    key, model = credentials()
    return {"configured": key is not None, "model": model, "settings": settings(),
            "used_this_month": used_this_month(), "job": job(), "weak": len(weak_prompts()),
            "verdicts": sum(1 for i in sl._load()["items"] if i["rating"] is None and i.get("teacher")),
            "note": "Лимит считает Yorika у себя, это не ограничение счёта на стороне Cloud.ru"}
