"""Curiosity: Yorika looks at her own exams and asks for lessons where she is weakest.

Wishes come from measurements only: the first logic level she has not passed, a low honesty
score, answers she is least sure of, and your phrases that surprised her most. Free wishes
(logic self-play) can run by themselves at night; paid ones (the teacher) stay suggestions.
"""
import time

from backend import self_learning as sl
from backend import training_center as tc


def _reference():
    """The version whose exams describe Yorika now: the active one, else the newest trained."""
    current = tc.active()
    runs = [r for r in tc.runs() if r["mode"] == "long" and r["has_best"]]
    if current:
        for r in runs:
            if r["id"] == current["run"]:
                return r
    return runs[0] if runs else None


def logic_frontier():
    from backend import logic
    ref = _reference()
    return logic.frontier(((ref or {}).get("logic") or {}).get("levels"))


def wishes():
    from backend import honesty, logic
    ref = _reference()
    out = []
    if ref is None:
        return [{"what": "Сначала обучите версию: без экзаменов мне не видно, что у меня слабое", "action": None}]
    levels = (ref.get("logic") or {}).get("levels") or {}
    level = logic.frontier(levels)
    out.append({"what": "Логика, уровень %d: решаю %d%% задач, хочу хотя бы %d%%" % (
        level, round(levels.get(str(level), 0) * 100), round(logic.PASS * 100)),
        "action": "logic", "level": level, "free": True, "weight": 1 - levels.get(str(level), 0)})
    h = ref.get("honesty") or {}
    if h and h.get("honest", 0) < h.get("total", len(honesty.EXAM)) * 0.75:
        out.append({"what": "Честность: говорю «не знаю» в %d случаях из %d, хочу чаще не выдумывать" % (
            h["honest"], h["total"]), "action": "honesty", "free": True,
            "weight": 1 - h["honest"] / max(1, h["total"])})
    counts = sl.counts()
    if counts["unrated"]:
        out.append({"what": "Оцени, пожалуйста, мои самые неуверенные ответы: их %d" % counts["unrated"],
                    "action": "rate", "free": True, "weight": 0.3})
    table = sl.surprises()
    if table:
        items = {i["id"]: i for i in sl._load()["items"]}
        top = sorted((v, k) for k, v in table.items() if k in items)[-3:]
        if top:
            out.append({"what": "Меня удивили твои фразы: " + "; ".join("«%s»" % items[k]["prompt"][:60] for _, k in reversed(top)),
                        "action": "teacher", "free": False, "topics": [items[k]["prompt"][:100] for _, k in reversed(top)],
                        "weight": 0.2})
    return sorted(out, key=lambda w: -w.get("weight", 0))


def night_step(loaded=None, count=40, seed=None):
    """The free part of curiosity: logic self-play at the frontier, verified by the program."""
    from backend import logic
    from backend.neural_language_benchmark import load_candidate
    checkpoint = sl._scoring_checkpoint()
    level = logic_frontier()
    if loaded is None:
        if checkpoint is None:
            pairs = logic.lessons(level)
            added = _add(pairs, "logic")
            return "уровень %d: моделей нет, добавлено %d решений от программы" % (level, added)
        loaded = load_candidate(checkpoint)
    result = logic.selfplay(loaded, level, count, seed=seed)
    added = _add(result["own"] + result["hints"], "logic")
    return "уровень %d: решила сама %d из %d, добавлено %d проверенных решений" % (
        level, result["solved"], result["count"], added)


def start(launch=True):
    """Free curiosity now, in a detached worker: self-play can take minutes."""
    state = tc._read(tc.folder() / "curiosity.json", {}) or {}
    if state.get("state") == "running" and time.time() - state.get("t", 0) < 1800:
        raise ValueError("Любопытство уже работает")
    tc._write(tc.folder() / "curiosity.json", {"state": "running", "t": time.time(), "result": None})
    if launch:
        import sys
        tc._spawn([sys.executable, str(tc.CLI), "curiosity-worker"], tc.folder() / "curiosity.log")
    return {"state": "running"}


def worker():
    try:
        result, state = night_step(), "finished"
    except Exception as error:  # noqa: BLE001 - the page shows why it stopped
        result, state = str(error)[:200], "failed"
    tc._write(tc.folder() / "curiosity.json", {"state": state, "t": time.time(), "result": result})
    return 0 if state == "finished" else 1


def last():
    return tc._read(tc.folder() / "curiosity.json")


def _add(pairs, source):
    """Verified by the program, so they enter experience already approved."""
    store = sl._load()
    known = {i["prompt"].casefold() for i in store["items"]}
    added = 0
    for prompt, answer in pairs:
        if prompt.casefold() in known:
            continue
        known.add(prompt.casefold())
        store["items"].append({"id": sl._id(prompt, source), "prompt": prompt, "answer": answer, "ts": None,
                               "rating": "up", "correction": None, "source": source, "verified": True})
        added += 1
    sl._save(store)
    return added
