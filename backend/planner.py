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
9. Evolutionary activities in turn, each when its time has come: the two hemispheres, the
   language of thought, gene exchange, coevolution of tasks, the Red Queen, starting points (the
   Baldwin effect), evolution of genes, of lessons and of weights, endosymbiosis, breeding by an
   evolved recipe, learning from the majority of her drafts, and the school of reasoning
   (reasoning.py: Piaget's stages until passed, the logic engine, prover and checker, concepts,
   analogies, knowing her limits, steps moved inside, the insight experiment). Their rhythm adapts: an activity
   whose versions never helped in the last month (three tries or more) comes half as often, one
   that helped at least every second time comes twice as often, but not more than every three days.
10. Otherwise the week plan's activity for today (sleep, copies, branches, future self...).

Every activity is a lesson that ends in the usual exams and the tournament; nothing here
activates a version or spends money.
"""
import time
from datetime import datetime, timezone

RECIPES_EVERY = WEEK = 7 * 24 * 3600
DAY = 24 * 3600
MONTH = 30 * DAY
# How often each evolutionary activity comes when nothing is known about it yet.
EVERY = {"hemispheres": WEEK, "thoughts": WEEK, "ecosystem": WEEK, "coevolve": WEEK, "redqueen": WEEK,
         "baldwin": 2 * WEEK, "evolution": WEEK, "dataevo": WEEK, "es": 2 * WEEK, "symbiosis": 2 * WEEK,
         "breed": WEEK, "evolrl": WEEK, "development": 3 * DAY, "solver": WEEK, "prover": WEEK, "concepts": WEEK,
         "analogy": WEEK, "metacog": WEEK, "latent": WEEK, "grok": 2 * WEEK}


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
    from backend import breeding, mind
    rows = []

    def due(activity):
        # The rhythm adapts: an activity that never helped comes half as often, one that usually
        # helps comes twice as often (not more often than every three days).
        if not rows:
            rows.append(_tried())
        return _since(state, activity) > period(activity, rows[0])
    if mind.partner(item["id"]) and due("hemispheres"):
        return {"activity": "hemispheres", "why": "давно не было спора двух полушарий"}
    if due("thoughts"):
        return {"activity": "thoughts", "why": "давно не тренировала язык мыслей"}
    if due("ecosystem") and len(tc.runs()) > 2:
        return {"activity": "ecosystem", "why": "давно не было обмена генами между версиями одной линии"}
    if due("coevolve"):
        return {"activity": "coevolve", "why": "давно не искала свои слабые места"}
    if mind.partner(item["id"]) and due("redqueen"):
        return {"activity": "redqueen", "why": "давно не было матча Красной Королевы"}
    if due("baldwin"):
        return {"activity": "baldwin", "why": "давно не испытывала врождённые стартовые точки"}
    if due("evolution"):
        return {"activity": "evolution", "why": "давно не пробовала новые гены устройства мозга"}
    if due("dataevo"):
        return {"activity": "dataevo", "why": "давно не отбирала уроки по пользе"}
    if due("es"):
        return {"activity": "es", "why": "давно не пробовала эволюцию весов без градиентов"}
    if due("symbiosis") and plans.symbiont(item["id"]):
        return {"activity": "symbiosis", "why": "есть меньшая версия-специалист с тем же словарём, её можно встроить"}
    if due("breed") and breeding.ready(item["id"]):
        return {"activity": "breed", "why": "есть версии с тем же устройством: можно вывести рецепт скрещивания"}
    if due("evolrl"):
        return {"activity": "evolrl", "why": "давно не училась на ответах, в которых согласно большинство черновиков"}
    from backend import development, reasoning
    for kind in ("development",) + reasoning.KINDS[1:] + ("grok",):
        if kind == "development" and development.finished():
            continue
        if due(kind):
            return {"activity": kind, "why": reasoning.WHY[kind]}
    what = week_activity or "sleep"
    return {"activity": what, "why": "по плану недели"}


def _tried():
    from backend import summary
    try:
        return {r["kind"]: r for r in summary.tried(window=MONTH)}
    except Exception:  # noqa: BLE001 - without a summary the rhythm stays the default one
        return {}


def period(activity, rows):
    """Seconds between two nights of this activity, from what it gave in the last month."""
    base = EVERY[activity]
    row = rows.get(activity)
    if row and row["tried"] >= 3 and not row["helped"]:
        return 2 * base
    if row and row["tried"] >= 2 and 2 * row["helped"] >= row["tried"]:
        return max(3 * DAY, base // 2)
    return base


def rhythm():
    """Every evolutionary activity: how often it comes now, how often by default, and why."""
    from backend import summary
    rows = _tried()
    out = []
    for activity, base in EVERY.items():
        row = rows.get(activity) or {"tried": 0, "helped": 0}
        every = period(activity, rows)
        out.append({"activity": activity, "title": summary.NAMES.get(activity, activity), "tried": row["tried"],
                    "helped": row["helped"], "days": round(every / DAY, 1), "base_days": round(base / DAY, 1),
                    "change": "чаще" if every < base else "реже" if every > base else None})
    return out


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
