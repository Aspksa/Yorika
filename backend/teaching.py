"""She teaches a younger one: an explanation counts only if the younger one then solves the task.

Learning by teaching (the protégé effect; explanation games like Prover–Verifier) made checkable:
she writes «Объясни, как решать: …», the younger one gets the task with that explanation and
without it. An explanation is useful only when the younger one solves the task with it and not
without it; nobody judges explanations by how they sound. The useful ones become her lessons,
together with explanations written by code from the checked solution that also helped the younger
one (when hers did not), so she learns what kind of explanation actually works.

The younger one is a smaller trained version of the same line (the one endosymbiosis would choose)
when there is one; otherwise it is she herself answering at once, with one greedy draft,
which is weaker but honest about what it is.
"""
import random

from backend import logic, solver

ASK = "Объясни, как решать: %s"


def hinted(question, explanation):
    return "Подсказка: %s Задача: %s" % (explanation.strip()[:200], question)


def code_explanation(t):
    facts = solver.facts_of(t["q"])
    steps = t["solution"].split("Ответ:")[0].strip()
    head = "Выпиши факты: %s. " % "; ".join(facts) if facts else ""
    return head + steps


def younger(run_id):
    """(loaded, who) of a smaller version, or (None, None) when there is none."""
    from backend import plans
    from backend import training_center as tc
    try:
        guest = plans.symbiont(run_id) if run_id else None
        if guest:
            from backend.neural_language_benchmark import load_candidate
            return load_candidate(tc._run_dir(guest) / "language-longrun.pt.best.pt"), guest
    except Exception:  # noqa: BLE001 - without a smaller version she teaches her quick self
        pass
    return None, None


def _solves(student, question, answer):
    from backend.brain import generate
    model, state = student
    return logic.correct(generate(model, state, question, 96)["text"], answer)


def lessons(loaded, seed=0, count=60, run_id=None):
    from backend import curiosity
    from backend.brain import think
    model, state = loaded
    student, who = younger(run_id)
    student = student or loaded
    level = min(5, curiosity.logic_frontier() + 1)
    tasks = solver.fresh_tasks(count, 5000 + seed, level)
    rng = random.Random(seed)
    made = {"younger": who or "она же, сразу и без раздумий", "asked": len(tasks), "alone": 0, "her_helped": 0,
            "code_helped": 0}
    pairs = []
    for t in tasks:
        if _solves(student, t["q"], t["answer"]):
            made["alone"] += 1
            continue   # nothing to explain: the younger one solves it alone
        own = think(model, state, ASK % t["q"], drafts=2, seed=rng.randrange(1000))["answer"]
        if own.strip() and _solves(student, hinted(t["q"], own), t["answer"]):
            made["her_helped"] += 1
            pairs.append((ASK % t["q"], own.strip()))
            continue
        written = code_explanation(t)
        if _solves(student, hinted(t["q"], written), t["answer"]):
            made["code_helped"] += 1
            pairs.append((ASK % t["q"], written))
    made["lessons"] = len(pairs)
    return pairs, made
