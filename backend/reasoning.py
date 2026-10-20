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
- emergent: her own language born in a signalling game over generations, then put into Russian (emergent.py)
- grounded: words tied to actions in a small world, checked by executing them (grounded.py)
- scientist: conjectures tested on thousands of cases, laws and counterexamples (scientist.py)
- counterfactual: «а если бы…» with one fact changed, the answer derived by the solver (counterfactual.py)
- teaching: her explanations count only when a younger one then solves the task (teaching.py)

Laboratory kinds (LAB) measure without creating a version:
- grok: an experiment on insight with a small network of her kind (grokking.py)
- observer: a probe on her hidden state predicts her errors; chat uses it when it is better (observer.py)
- budget: accuracy per unit of thinking, thresholds for how many drafts (budget.py)

The autopilot (planner.py) takes them in this order when their time comes; their rhythm adapts to
what helped, like every other evolutionary activity.
"""
import time

KINDS = ("development", "solver", "prover", "concepts", "analogy", "metacog", "latent",
         "emergent", "grounded", "scientist", "counterfactual", "teaching")
LAB = ("grok", "observer", "budget")
TITLES = {"development": "Развитие по этапам", "solver": "Язык и решатель", "prover": "Доказывающая и проверяющая",
          "concepts": "Свои понятия", "analogy": "Аналогии", "metacog": "Знает, чего не знает",
          "latent": "Мышление без слов", "grok": "Озарение", "emergent": "Свой язык", "grounded": "Язык через действия",
          "scientist": "Учёный внутри", "counterfactual": "Что было бы, если", "teaching": "Учит младшую",
          "observer": "Внутренний наблюдатель", "budget": "Цена мысли"}
WHY = {"development": "ещё не пройдены ранние этапы мышления (по Пиаже)",
       "solver": "давно не училась переводить задачу в факты для решателя",
       "prover": "давно не тренировала понятные решения и поиск ошибок",
       "concepts": "давно не собирала свои понятия из решений",
       "analogy": "давно не училась переносить решение на задачи в другом обличье",
       "metacog": "давно не проверяла, насколько знает свои силы",
       "latent": "давно не переносила шаги решения внутрь",
       "grok": "давно не ставила опыт с озарением",
       "emergent": "давно не рождался новый поколением её язык знаков",
       "grounded": "давно не учила слова через действия в мире задач",
       "scientist": "давно не проверяла гипотезы на тысячах примеров",
       "counterfactual": "давно не представляла, что было бы, если изменить одно условие",
       "teaching": "давно не объясняла младшей так, чтобы та решила",
       "observer": "давно не проверяла, видно ли ошибку по её внутреннему состоянию",
       "budget": "давно не мерила, сколько думать выгодно"}


def make(kind, loaded, seed=0, run_id=None):
    from backend import (analogy, concepts, counterfactual, development, emergent, grounded, latent, metacog, prover,
                         scientist, solver, teaching)
    if kind in ("metacog", "teaching"):
        return {"metacog": metacog, "teaching": teaching}[kind].lessons(loaded, seed, run_id=run_id)
    module = {"development": development, "solver": solver, "prover": prover, "concepts": concepts,
              "analogy": analogy, "latent": latent, "emergent": emergent, "grounded": grounded,
              "scientist": scientist, "counterfactual": counterfactual}[kind]
    return module.lessons(loaded, seed)


def lab(kind, loaded, run_id, seed=0, seconds=600, device="cpu", should_stop=None):
    """A laboratory kind: its measurement, with a «verdict» line. No version is made."""
    if kind == "grok":
        from backend import grokking
        made = grokking.experiment(seconds=seconds, seed=seed, device=device, should_stop=should_stop)
        grokking.remember(made)
        return {k: made[k] for k in ("p", "verdict")}
    from backend import budget, observer
    return {"observer": observer, "budget": budget}[kind].experiment(loaded, run_id, seed)


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
    if kind == "emergent":
        return "поколение %d, понимают друг друга на %d%%, составность %s (было %s), незнакомых сигналов поняла %d из %d" % (
            m.get("generation", 0), round(100 * (m.get("accuracy") or 0)), m.get("topsim"), m.get("topsim_start"),
            m.get("unseen_right", 0), m.get("unseen", 0))
    if kind == "grounded":
        return "с незнакомым предметом верно %d из %d" % (m.get("transfer", 0), m.get("asked", 0))
    if kind == "scientist":
        return "законов %d, опровергнуто %d, угадала исход %d из %d новых гипотез" % (
            m.get("laws", 0), m.get("refuted", 0), m.get("predicted", 0), m.get("asked", 0))
    if kind == "counterfactual":
        return "до урока верно %d из %d" % (m.get("right", 0), m.get("asked", 0))
    if kind == "teaching":
        return "младшая сама решила %d из %d, после её объяснения ещё %d, после объяснения кодом %d" % (
            m.get("alone", 0), m.get("asked", 0), m.get("her_helped", 0), m.get("code_helped", 0))
    if kind in LAB:
        return m.get("verdict") or ""
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
    from backend import budget, concepts, development, emergent, grokking, latent, metacog, observer, scientist
    from backend import training_center as tc
    data = tc._read(_path(), {}) or {}
    out = {"titles": TITLES, "last": {k: (data.get(k) or [None])[-1] for k in KINDS + LAB}}
    dev = development.load()
    out["development"] = {"stage": dev["stage"], "stages": list(development.STAGES), "scores": dev.get("scores", {})}
    out["concepts"] = [c["name"] for c in concepts.load().get("library", [])][:6]
    lat = latent.load()
    out["latent"] = {"stage": lat["stage"], "max": latent.MAX_STAGE}
    mc = metacog.load()
    out["metacog"] = {k: mc.get(k) for k in ("brier", "base", "useful", "run")}
    out["grok"] = grokking.status()
    lang = emergent.status()
    out["emergent"] = {"generation": lang["generation"], "words": lang["words"][:6],
                       "topsim": [r["topsim"] for r in lang["history"]]}
    out["scientist"] = scientist.status()
    out["observer"] = observer.status()
    out["budget"] = budget.status()
    for kind, entry in out["last"].items():
        if entry:
            entry["text"] = describe(kind, entry.get("made"))
    return out
