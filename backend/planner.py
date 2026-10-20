"""She plans her own study night from measurements, and writes a morning report.

When the autopilot's «сама выбирает занятие» is on, each study block asks today(): the first
rule that fits picks the activity, and its reason is written into the log and the report.

1. No active version: a fresh one.
2. A grown version waits to be compressed: shrink (the big one teaches the small one).
3. Looking inside the active version says experts are overloaded or idle: experts ±2.
4. It says more than half the neurons of a layer stay silent: neurogenesis (they are reborn).
5. It says every layer is needed: grow two layers deeper.
6. The study recipe was not tested for a week: a recipes contest.
7. The archive has fewer than three kinds: evolution from any elite.
8. Approved books and no pretrained base yet: reading.
9. A week without the two hemispheres, the language of thought or gene exchange: that one.
10. A week without coevolution of tasks or a Red Queen match, two weeks without a generation of
    starting points (the Baldwin effect): that one.
11. Otherwise the week plan's activity for today (sleep, copies, branches, future self...).

Every activity is a lesson that ends in the usual exams and the tournament; nothing here
activates a version or spends money.
"""
import time
from datetime import datetime, timezone

RECIPES_EVERY = WEEK = 7 * 24 * 3600


def _state():
    from backend import training_center as tc
    return tc._read(tc.folder() / "planner.json", {}) or {}


def _save_state(state):
    from backend import training_center as tc
    tc._write(tc.folder() / "planner.json", state)


def _active_item():
    from backend import training_center as tc
    current = tc.active()
    if not current:
        return None
    return next((r for r in tc.runs() if r["id"] == current.get("run")), None)


def expert_change(item):
    """+2 when one expert takes far more than its share, -2 when some are idle, else 0."""
    report = (item or {}).get("introspection") or {}
    shares = report.get("experts")
    if not shares:
        return 0
    k = len(shares)
    if max(shares) > 1.6 / k and k < 8:
        return 2
    if sum(1 for v in shares if v < 0.25 / k) >= 2 and k > 2:
        return -2
    return 0


def _grown_children(run_id):
    from backend import training_center as tc
    return [r for r in tc.runs() if r.get("grown_from") == run_id and r.get("kind") == "grow"]


def today(week_activity=None):
    """{"activity", "why", "grow": {...} for growth}; never starts anything itself."""
    from backend import archive, plans, recipes
    from backend import training_center as tc
    item = _active_item()
    state = _state()
    if not item:
        return {"activity": "fresh", "why": "активной версии нет: учу новую"}
    teacher = plans.shrink_teacher()
    if teacher and teacher not in state.get("shrunk", []) and teacher != item["id"]:
        return {"activity": "shrink", "why": "выросшая версия %s ещё не передала знания малой" % teacher, "teacher": teacher}
    grown = _grown_children(item["id"])
    change = expert_change(item)
    if change and not grown:
        why = "один эксперт перегружен" if change > 0 else "два эксперта почти не работают"
        return {"activity": "experts", "why": why + " (по взгляду внутрь)", "grow": {"from": item["id"], "experts": change}}
    advice = {a.get("kind") for a in ((item.get("introspection") or {}).get("advice") or [])}
    if "dead" in advice and _since(state, "rebirth") > WEEK:
        return {"activity": "rebirth", "why": "в слое больше половины нейронов молчат (по взгляду внутрь)"}
    if "grow" in advice and not grown and (item.get("layers") or 0) + 2 <= 16:
        return {"activity": "grow", "why": "каждый слой нужен, места мало (по взгляду внутрь)",
                "grow": {"from": item["id"], "layers": 2}}
    tried = recipes.load()["tried"]
    last = max((_ts(t["at"]) for t in tried), default=0)
    if time.time() - last > RECIPES_EVERY:
        return {"activity": "recipes", "why": "рецепт учёбы не проверялся неделю" if tried else "рецепт учёбы ещё не испытан"}
    if archive.cells()["filled"] < 3:
        return {"activity": "evolution", "why": "в архиве меньше трёх разных видов"}
    if _pretrain_waits():
        return {"activity": "pretrain", "why": "есть одобренные книги, а прочитанной основы ещё нет"}
    from backend import mind
    if mind.partner(item["id"]) and _since(state, "hemispheres") > WEEK:
        return {"activity": "hemispheres", "why": "неделю не было спора двух полушарий"}
    if _since(state, "thoughts") > WEEK:
        return {"activity": "thoughts", "why": "неделю не тренировала язык мыслей"}
    if _since(state, "ecosystem") > WEEK and len(tc.runs()) > 2:
        return {"activity": "ecosystem", "why": "неделю не было обмена генами между версиями одной линии"}
    if _since(state, "coevolve") > WEEK:
        return {"activity": "coevolve", "why": "неделю не искала свои слабые места"}
    if mind.partner(item["id"]) and _since(state, "redqueen") > WEEK:
        return {"activity": "redqueen", "why": "неделю не было матча Красной Королевы"}
    if _since(state, "baldwin") > 2 * WEEK:
        return {"activity": "baldwin", "why": "две недели не испытывала врождённые стартовые точки"}
    if _since(state, "dataevo") > WEEK:
        return {"activity": "dataevo", "why": "неделю не отбирала уроки по пользе"}
    if _since(state, "es") > 2 * WEEK:
        return {"activity": "es", "why": "две недели не пробовала эволюцию весов без градиентов"}
    if _since(state, "symbiosis") > 2 * WEEK and plans.symbiont(item["id"]):
        return {"activity": "symbiosis", "why": "есть меньшая версия-специалист с тем же словарём, её можно встроить"}
    what = week_activity or "sleep"
    return {"activity": what, "why": "по плану недели"}


def _since(state, activity):
    return time.time() - (state.get("history") or {}).get(activity, 0)


def _pretrain_waits():
    from backend import training_center as tc
    if not any(f["approved"] for f in tc.texts()["files"]):
        return False
    return not any(r["mode"] == "pretrain" and r["has_best"] for r in tc.runs())


def _ts(text):
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        return 0


def done(choice):
    """Remembers what was chosen so the same reason does not fire every night."""
    state = _state()
    if choice.get("activity") == "shrink":
        state["shrunk"] = (state.get("shrunk", []) + [choice["teacher"]])[-50:]
    state["last"] = dict(choice, at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    state.setdefault("history", {})[choice["activity"]] = time.time()
    _save_state(state)


def last():
    return _state().get("last")


# ---- the morning report ----------------------------------------------------------

def morning():
    """What happened since the last study block began, in plain sentences, and what waits for you."""
    from backend import archive, night_cycle, plans, simworld
    from backend import training_center as tc
    nights = night_cycle.log()
    entry = nights[-1] if nights else None
    since = _ts(entry["started"]) if entry else 0
    lines = []
    if entry:
        for step in entry["steps"]:
            if step["step"] in ("plan", "train", "sim", "programs", "tidy", "health", "dreams"):
                lines.append({"kind": step["step"], "text": step["result"]})
    new_runs = [r for r in tc.runs() if _ts(r.get("created")) >= since and r["mode"] == "long"]
    for r in new_runs[:6]:
        t = r.get("tournament") or {}
        text = "%s: %s" % (r["id"], r.get("dataset") or r.get("kind") or "урок")
        if t.get("tasks"):
            text += ", турнир с предком %d:%d" % (t["mine"], t["theirs"])
        lines.append({"kind": "run", "text": text})
    for a in archive.load()["log"]:
        if _ts(a.get("at")) >= since:
            lines.append({"kind": "archive", "text": "%s %s" % (a["run"], a.get("result", ""))})
    for m in simworld.ladder()["history"]:
        if _ts(m.get("at")) >= since:
            lines.append({"kind": "ladder", "text": "%s: уровень %d → %d" % (simworld.ENVS.get(m["env"], [m["env"]])[0], m["from"], m["to"])})
    for p in plans.history():
        if _ts(p.get("finished")) >= since:
            lines.append({"kind": "plan", "text": p.get("result") or ""})
    try:
        from backend import extinction
        stuck = extinction.plateau()
        if stuck["plateau"]:
            lines.append({"kind": "plateau", "text": "Эволюция на плато (%s): можно устроить вымирание, только вашей кнопкой" % stuck["why"]})
    except Exception:  # noqa: BLE001 - the report never fails because of one line
        pass
    waiting = [r["id"] for r in tc.runs() if (r.get("verdict") or {}).get("result") == "waiting" and _ts(r.get("created")) >= since]
    return {"since": entry["started"] if entry else None, "lines": lines[-16:], "waiting": waiting,
            "choice": last(), "empty": not lines}
