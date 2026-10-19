"""Blind comparison: two versions answer the same unseen questions, the owner picks without names.

Which side is which version stays in the round file on disk; the page only ever sees A and B
until every question is voted. Questions come from the newer version's exam split, so
neither version trained on them.
"""
import json
import random
import secrets
import time

from backend import training_center as tc

FALLBACK = ["Привет! Как тебя зовут?", "Что ты умеешь?", "Как прошёл твой день?", "Посоветуй, чем заняться вечером",
            "Расскажи что-нибудь интересное"]


def _dir():
    return tc.folder() / "blind"


def _questions(run_ids, count):
    for run_id in sorted(run_ids, reverse=True):
        item = tc._summary(tc._run_dir(run_id))
        if item["mode"] == "long" and item.get("dataset"):
            try:
                test = tc._prepare(tc._load_records(item["dataset"]))["test"]
            except ValueError:
                continue
            prompts = [p for p, _ in test]
            random.SystemRandom().shuffle(prompts)
            return prompts[:count]
    return FALLBACK[:count]


def start(run_ids, count=5):
    if not isinstance(run_ids, list) or len(run_ids) != 2 or len(set(run_ids)) != 2:
        raise ValueError("Выберите две разные версии")
    if type(count) is not int or not 1 <= count <= 10:
        raise ValueError("От 1 до 10 вопросов")
    from backend.neural_language_benchmark import load_candidate
    models = {}
    for run_id in run_ids:
        best = tc._run_dir(run_id) / "language-longrun.pt.best.pt"
        if not best.is_file():
            raise ValueError("У одной из версий нет сохранённой лучшей точки")
        models[run_id] = load_candidate(best)
    flip = random.SystemRandom()
    rows = []
    for question in _questions(run_ids, count):
        answers = {r: tc._with_tools(tc._answer(*models[r], question, 64)) for r in run_ids}
        a, b = (run_ids[0], run_ids[1]) if flip.random() < .5 else (run_ids[1], run_ids[0])
        rows.append({"q": question, "a": answers[a] or "(пустой ответ)", "b": answers[b] or "(пустой ответ)",
                     "a_run": a, "b_run": b, "vote": None})
    round_id = secrets.token_hex(8)
    tc._write(_dir() / (round_id + ".json"), {"id": round_id, "runs": sorted(run_ids), "t": time.time(), "rows": rows})
    return {"round": round_id, "questions": [{"q": r["q"], "a": r["a"], "b": r["b"]} for r in rows]}


def _round(round_id):
    if not isinstance(round_id, str) or not round_id.isalnum() or len(round_id) != 16:
        raise ValueError("Неизвестный раунд")
    data = tc._read(_dir() / (round_id + ".json"))
    if not data:
        raise ValueError("Неизвестный раунд")
    return data


def vote(round_id, index, choice):
    data = _round(round_id)
    if type(index) is not int or not 0 <= index < len(data["rows"]):
        raise ValueError("Неизвестный вопрос")
    if choice not in ("a", "b", "same"):
        raise ValueError("Выберите A, B или «одинаково»")
    data["rows"][index]["vote"] = choice
    tc._write(_dir() / (round_id + ".json"), data)
    done = all(r["vote"] for r in data["rows"])
    # Names are revealed only after the whole round is voted.
    return {"done": done, "reveal": _tally(data) if done else None}


def _tally(data):
    wins = {r: 0 for r in data["runs"]}
    same = 0
    for row in data["rows"]:
        if row["vote"] == "same":
            same += 1
        elif row["vote"] in ("a", "b"):
            wins[row[row["vote"] + "_run"]] += 1
    return {"runs": data["runs"], "wins": wins, "same": same, "votes": sum(1 for r in data["rows"] if r["vote"])}


def results():
    """All finished rounds, summed per pair of versions."""
    totals = {}
    if _dir().is_dir():
        for path in sorted(_dir().glob("*.json"))[-200:]:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            tally = _tally(data)
            key = "|".join(tally["runs"])
            entry = totals.setdefault(key, {"runs": tally["runs"], "wins": {r: 0 for r in tally["runs"]}, "same": 0, "votes": 0})
            for run_id, n in tally["wins"].items():
                entry["wins"][run_id] += n
            entry["same"] += tally["same"]
            entry["votes"] += tally["votes"]
    return [e for e in totals.values() if e["votes"]]
