"""Thinking without words: written steps of a solution move inside, one step at a time.

Stepwise internalization (Deng et al., 2024: from explicit to implicit chain of thought). At stage
0 she writes every step. Each stage removes one more of the first steps from the lessons and puts
«…» in their place, so that step has to happen inside the network: in her layers and, for a
model with loops, in the extra passes, which a silent question always gets in full. At the last
stage only the answer is written.

A stage is kept only when the lesson was not rolled back; two rollbacks in a row go one stage
back. This is a data method on her own network, not continuous vector thoughts fed back as input
(Coconut needs a different training loop); it is measured by how often she answers a silent
question right.
"""
import time

from backend import logic, prover, solver

SILENT = "Подумай про себя."
MAX_STAGE = 4


def silent(question):
    return "%s %s" % (question, SILENT)


def internalized(solution, stage):
    steps = prover.steps_of(solution)
    answer = solution[solution.index("Ответ:"):]
    if stage >= len(steps):
        return answer
    kept = ["…"] * min(stage, len(steps)) + steps[stage:]
    return " ".join("Шаг %d: %s." % (k + 1, s) for k, s in enumerate(kept)) + " " + answer


def _path():
    from backend import training_center as tc
    return tc.folder() / "latent.json"


def load():
    from backend import training_center as tc
    return tc._read(_path(), {}) or {"stage": 0, "misses": 0, "history": []}


def measure(loaded, tasks):
    from backend.brain import think
    model, state = loaded
    return sum(logic.correct(think(model, state, silent(t["q"]), drafts=1)["answer"], t["answer"]) for t in tasks)


def lessons(loaded, seed=0, count=160):
    from backend import curiosity
    data = load()
    stage = data["stage"]
    level = min(5, curiosity.logic_frontier() + 1)
    tasks = solver.fresh_tasks(count + 20, 3000 + seed, level)
    check, teach = tasks[:20], tasks[20:]
    made = {"stage": stage, "silent_right": measure(loaded, check), "asked": len(check)}
    pairs = []
    for t in teach:
        pairs.append((silent(t["q"]), internalized(t["solution"], stage)))
        if stage < MAX_STAGE:
            pairs.append((silent(t["q"]), internalized(t["solution"], stage + 1)))   # a glimpse of the next stage
    made["lessons"] = len(pairs)
    return pairs, made


def after(made, verdict):
    """Moves the stage on after a lesson that was kept; back after two rollbacks in a row."""
    from backend import training_center as tc
    data = load()
    if verdict in ("waiting", "activated"):
        data.update(stage=min(MAX_STAGE, data["stage"] + 1), misses=0)
    else:
        data["misses"] = data.get("misses", 0) + 1
        if data["misses"] >= 2:
            data.update(stage=max(0, data["stage"] - 1), misses=0)
    data["history"] = (data.get("history", []) + [{"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                                    "stage": data["stage"], "silent_right": made.get("silent_right"),
                                                    "asked": made.get("asked"), "verdict": verdict}])[-20:]
    tc._write(_path(), data)
    return data
