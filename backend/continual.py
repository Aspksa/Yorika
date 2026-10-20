"""Living learning: short lessons after conversations, sleep with replay, and forgetting.

Quick learning continues the active version on examples you approved since the last lesson,
mixed with older ones so the old is not overwritten. The result takes the active version's
exam: if it is worse, it is discarded (rolled back); if not, it waits for you, or replaces the
active version by itself only when you turned on «включать сама, если не хуже».

Forgetting: every approved example has a strength that grows with how often the same question
comes up and halves every HALF_LIFE days. Replay picks strong examples more often; examples
whose strength fell below FADED are not replayed any more.
"""
import math
import random
import time
from datetime import datetime, timezone

from backend import self_learning as sl
from backend import training_center as tc

DEFAULTS = {"enabled": False, "auto_activate": False, "min_new": 20, "minutes": 5, "replay": 0.5}
HALF_LIFE = 30.0
FADED = 0.05
MAX_SET = 4000


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def settings():
    saved = tc._read(tc.folder() / "continual.json", {}) or {}
    return {k: saved.get(k, v) for k, v in DEFAULTS.items()}


def set_settings(enabled, auto_activate=False, min_new=20, minutes=5):
    if not isinstance(enabled, bool) or not isinstance(auto_activate, bool):
        raise ValueError("Неверное значение")
    if type(min_new) is not int or not 10 <= min_new <= 1000 or type(minutes) not in (int, float) or not 1 <= minutes <= 60:
        raise ValueError("Новых примеров от 10 до 1000, урок от 1 до 60 минут")
    saved = tc._read(tc.folder() / "continual.json", {}) or {}
    saved.update(enabled=enabled, auto_activate=auto_activate, min_new=min_new, minutes=minutes,
                 changed=_now())
    tc._write(tc.folder() / "continual.json", saved)
    return settings()


def log():
    return (tc._read(tc.folder() / "continual-log.json", []) or [])[-20:]


def _log(entry):
    tc._write(tc.folder() / "continual-log.json", (log() + [dict(entry, at=_now())])[-20:])


# ---- forgetting --------------------------------------------------------------

def _age_days(item, now):
    ts = item.get("ts")
    if isinstance(ts, (int, float)) and ts > 1e9:
        return max(0.0, (now - ts) / 86400)
    if isinstance(ts, str):
        try:
            return max(0.0, (now - datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()) / 86400)
        except ValueError:
            pass
    return 0.0


def strengths(items, now=None):
    """Strength of each reviewed example: repetition makes it stronger, time makes it fade."""
    now = now or time.time()
    uses = {}
    for item in items:
        key = item["prompt"].casefold().strip()
        uses[key] = uses.get(key, 0) + 1 + int(item.get("asked", 0))
    return {item["id"]: (1 + math.log(uses[item["prompt"].casefold().strip()])) *
            0.5 ** (_age_days(item, now) / HALF_LIFE) for item in items}


def _ready(items):
    return [i for i in items if i["rating"] == "up" or (i["rating"] == "down" and i.get("correction"))]


def _record(item):
    answer = item["correction"] if item["rating"] == "down" else item["answer"]
    return {"prompt": item["prompt"], "answer": answer, "source": item.get("source") or "yorika-chat",
            "license": sl.SOURCES.get(item.get("source") or "yorika-chat", "user-consent"), "consent": True,
            "rights_reviewed_by": "owner", "quality_reviewed": True}


def memory_state(now=None):
    items = _ready(sl._load()["items"])
    power = strengths(items, now)
    faded = sum(1 for v in power.values() if v < FADED)
    return {"ready": len(items), "faded": faded, "strong": sum(1 for v in power.values() if v >= 1),
            "half_life_days": HALF_LIFE}


def build_set(new_items, replay_share=0.5, seed=None, now=None):
    """New approved examples plus replayed older ones, weighted by strength; never exam prompts."""
    banned = tc.protected_prompts()
    store = sl._load()["items"]
    ready = [i for i in _ready(store) if i["prompt"].casefold().strip() not in banned]
    new_ids = {i["id"] for i in new_items}
    fresh = [i for i in ready if i["id"] in new_ids]
    old = [i for i in ready if i["id"] not in new_ids]
    power = strengths(ready, now)
    old = [i for i in old if power[i["id"]] >= FADED]
    rng = random.Random(seed)
    want = min(len(old), int(len(fresh) * replay_share / max(1e-9, 1 - replay_share)) + 1, MAX_SET - len(fresh))
    replay = []
    if want > 0 and old:
        # Weighted sampling without replacement (Efraimidis–Spirakis keys).
        keyed = sorted(old, key=lambda i: rng.random() ** (1 / max(power[i["id"]], 1e-6)), reverse=True)
        replay = keyed[:want]
    records, seen = [], set()
    for item in fresh + replay:
        key = item["prompt"].casefold().strip()
        if key not in seen:
            seen.add(key)
            records.append(_record(item))
    return records, {"new": len(fresh), "replay": len(replay)}


# ---- quick learning after conversations -------------------------------------

def _since_last():
    state = tc._read(tc.folder() / "continual-state.json", {}) or {}
    done = set(state.get("learned", []))
    return [i for i in _ready(sl._load()["items"]) if i["id"] not in done]


def maybe_start(launch=True, force=False):
    """Starts a short lesson when enough new approved examples piled up. Returns the run id or None."""
    plan = settings()
    if not force and not plan["enabled"]:
        return None
    current = tc.active()
    if not current or tc._active_job():
        return None
    new = _since_last()
    if not force and len(new) < plan["min_new"]:
        return None
    from backend import schedule
    if not force and not schedule.allowed():
        # Lessons wait for study hours; the examples stay counted until then.
        return None
    if not new:
        raise ValueError("Новых одобренных примеров нет")
    records, mix = build_set(new, plan["replay"])
    if len(records) < 10:
        raise ValueError("Для урока нужно хотя бы 10 примеров")
    config = dict(tc._read(tc._run_dir(current["run"]) / "run.json")["config"])
    from backend import recipes
    config["lr"], config["rule"] = recipes.learning_rate(), recipes.learning_rule()  # the study recipe that won its last contest
    run = tc.start("long", device=_device(current["run"]), total_steps=1000000, hours=plan["minutes"] / 60,
                   config=config, kind="quick", init=current["checkpoint"], records=records, launch=launch,
                   scheduled=not force)
    state = tc._read(tc.folder() / "continual-state.json", {}) or {}
    state["learned"] = (state.get("learned", []) + [i["id"] for i in new])[-50000:]
    state["pending"] = run["id"]
    tc._write(tc.folder() / "continual-state.json", state)
    _log({"run": run["id"], "event": "start", "new": mix["new"], "replay": mix["replay"]})
    return run["id"]


def _device(run_id):
    return (tc._read(tc._run_dir(run_id) / "run.json") or {}).get("device", "cuda")


def judge(run_id):
    """Exam against the active version on the active version's own exam: keep, wait or roll back."""
    from backend.neural_language_benchmark import load_candidate
    from backend.neural_language_longrun import score_checkpoint
    current = tc.active()
    item = tc._summary(tc._run_dir(run_id))
    if not current or not item["has_best"]:
        verdict = {"result": "rolled_back", "why": "нет активной версии или сохранённой точки"}
    else:
        base = next((r for r in tc.runs() if r["id"] == current["run"]), None)
        try:
            info = tc._read(tc._run_dir(current["run"]) / "run.json")
            records = tc._read(tc._run_dir(current["run"]) / "dataset.json") if info.get("internal") else tc._load_records(info["dataset"])
            test = tc._prepare(records)["test"]
            mine = score_checkpoint(None, test, loaded=load_candidate(tc._run_dir(run_id) / "language-longrun.pt.best.pt"))["per_char"]
            theirs = score_checkpoint(None, test, loaded=load_candidate(tc.folder() / current["checkpoint"]))["per_char"]
        except (ValueError, TypeError, KeyError):
            mine = theirs = None
        honest_new = (item.get("honesty") or {}).get("honest")
        honest_old = ((base or {}).get("honesty") or {}).get("honest")
        worse = []
        if mine is not None and mine > theirs * 1.01:
            worse.append("экзамен %.3f хуже %.3f" % (mine, theirs))
        if honest_new is not None and honest_old is not None and honest_new < honest_old - 1:
            worse.append("честность %d против %d" % (honest_new, honest_old))
        logic_new = sum(((item.get("logic") or {}).get("levels") or {}).values())
        logic_old = sum((((base or {}).get("logic") or {}).get("levels") or {}).values())
        if base and base.get("logic") and logic_new < logic_old - 0.1:
            worse.append("логика стала слабее")
        if worse:
            verdict = {"result": "rolled_back", "why": "; ".join(worse), "mine": mine, "theirs": theirs}
        elif settings()["auto_activate"]:
            tc.activate(run_id, by="auto-policy")
            verdict = {"result": "activated", "why": "не хуже на экзаменах; вы разрешили включать самой",
                       "mine": mine, "theirs": theirs}
        else:
            verdict = {"result": "waiting", "why": "не хуже на экзаменах; ждёт вашего решения", "mine": mine,
                       "theirs": theirs}
    if verdict["result"] == "rolled_back":
        # Rolled back: the lesson stays on disk for inspection but is never proposed.
        sl_settings = sl._settings()
        if run_id not in sl_settings["dismissed"]:
            sl_settings["dismissed"].append(run_id)
            sl._save_settings(sl_settings)
    _log({"run": run_id, "event": verdict["result"], "why": verdict["why"]})
    return verdict


def sleep_set(newest_name, seed=None):
    """Night: today's experience file plus a replay of everything older, by strength."""
    records = tc._load_records(newest_name)
    prompts = {r["prompt"].casefold().strip() for r in records}
    new = [i for i in _ready(sl._load()["items"]) if i["prompt"].casefold().strip() in prompts]
    mixed, mix = build_set(new, 0.3, seed=seed)
    banned = tc.protected_prompts()
    extra = [r for r in records if r["prompt"].casefold().strip() not in banned and
             r["prompt"].casefold().strip() not in {m["prompt"].casefold().strip() for m in mixed}]
    return (mixed + extra)[:MAX_SET * 2], mix


def status():
    return {"settings": settings(), "log": log(), "pending": len(_since_last()), "memory": memory_state()}
