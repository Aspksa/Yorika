"""The school of reasoning: eight ways to think beyond ordinary training, as one set of activities.

Each kind makes lessons from fresh, checked tasks (never exam questions), measured before the
lesson, and the lesson is then judged like any other against the active version:

- development: early ideas in Piaget's stages (development.py)
- solver: she writes the facts, a logic engine derives the answer (solver.py)
- prover: legible solutions and a checker that finds the wrong step (prover.py)
- concepts: recurring steps become named building blocks (concepts.py)
- analogy: one skeleton in different guises, tested on a guise never taught (analogy.py)
- metacog: predicting her own success, used to decide how long to think (metacog.py)
- latent: written steps move inside, one stage at a time (latent.py)
- grok: a laboratory experiment on insight with a small network of her kind (grokking.py)

The autopilot (planner.py) takes them in this order when their time comes; their rhythm adapts to
what helped, like every other evolutionary activity.
"""
import time

KINDS = ("development", "solver", "prover", "concepts", "analogy", "metacog", "latent")
TITLES = {"development": "Развитие по этапам", "solver": "Язык и решатель", "prover": "Доказывающая и проверяющая",
          "concepts": "Свои понятия", "analogy": "Аналогии", "metacog": "Знает, чего не знает",
          "latent": "Мышление без слов", "grok": "Озарение"}
WHY = {"development": "ещё не пройдены ранние этапы мышления (по Пиаже)",
       "solver": "давно не училась переводить задачу в факты для решателя",
       "prover": "давно не тренировала понятные решения и поиск ошибок",
       "concepts": "давно не собирала свои понятия из решений",
       "analogy": "давно не училась переносить решение на задачи в другом обличье",
       "metacog": "давно не проверяла, насколько знает свои силы",
       "latent": "давно не переносила шаги решения внутрь",
       "grok": "давно не ставила опыт с озарением"}


def make(kind, loaded, seed=0, run_id=None):
    from backend import analogy, concepts, development, latent, metacog, prover, solver
    if kind == "metacog":
        return metacog.lessons(loaded, seed, run_id=run_id)
    module = {"development": development, "solver": solver, "prover": prover, "concepts": concepts,
              "analogy": analogy, "latent": latent}[kind]
    return module.lessons(loaded, seed)


def describe(kind, made):
    m = made or {}
    if kind == "development":
        return "этап «%s», уроков %d" % (m.get("title"), m.get("lessons", 0))
    if kind == "solver":
        return "до урока её факты привели решатель к верному ответу в %d из %d" % (m.get("translated", 0), m.get("checked", 0))
    if kind == "prover":
        return "понятных верных решений %d из %d, проверяющая права в %d из %d" % (
            m.get("legible", 0), m.get("asked", 0), m.get("checker_right", 0), m.get("checks", 0))
    if kind == "concepts":
        return "понятий %d, решения короче на %d%%" % (m.get("concepts", 0), round(100 * (m.get("shorter") or 0)))
    if kind == "analogy":
        return "в незнакомом обличье верно %d из %d" % (m.get("transfer", 0), m.get("asked", 0))
    if kind == "metacog":
        return "ошибка самооценки %s против %s у угадывания" % (m.get("brier"), m.get("base"))
    if kind == "latent":
        return "этап %d, молча верно %d из %d" % (m.get("stage", 0), m.get("silent_right", 0), m.get("asked", 0))
    return ""


def after(kind, made, verdict):
    if kind == "latent":
        from backend import latent
        latent.after(made or {}, verdict)


def _path():
    from backend import training_center as tc
    return tc.folder() / "reasoning.json"


def remember(kind, made, run_id=None, verdict=None):
    from backend import training_center as tc
    data = tc._read(_path(), {}) or {}
    log = data.get(kind, [])[-9:]
    log.append({"made": made, "run": run_id, "verdict": verdict, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    data[kind] = log
    tc._write(_path(), data)


def status():
    from backend import concepts, development, grokking, latent, metacog
    from backend import training_center as tc
    data = tc._read(_path(), {}) or {}
    out = {"titles": TITLES, "last": {k: (data.get(k) or [None])[-1] for k in KINDS}}
    dev = development.load()
    out["development"] = {"stage": dev["stage"], "stages": list(development.STAGES), "scores": dev.get("scores", {})}
    out["concepts"] = [c["name"] for c in concepts.load().get("library", [])][:6]
    lat = latent.load()
    out["latent"] = {"stage": lat["stage"], "max": latent.MAX_STAGE}
    mc = metacog.load()
    out["metacog"] = {k: mc.get(k) for k in ("brier", "base", "useful", "run")}
    out["grok"] = grokking.status()
    for kind, entry in out["last"].items():
        if entry:
            entry["text"] = describe(kind, entry.get("made"))
    return out
