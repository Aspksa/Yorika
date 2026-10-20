"""What if…: one fact of a solved task is changed, and the new answer is computed by the solver.

A task she can read («У Лисы было 5 орехов. Она нашла ещё 3…») is asked again with one change:
another number in one sentence, another day to start from, or a rule we no longer know («а если
бы мы не знали, что все лисы — звери?»). The changed task is translated into facts and the logic
engine derives its answer (solver.py), so every counterfactual answer is exact, including «не
изменится» and «неизвестно». This is the third rung of Pearl's ladder (seeing, doing, imagining)
on the smallest scale: reasoning about a world that differs from the given one in one place.
"""
import random
import re

from backend import logic, solver

DAY_IS = {"понедельник": "был понедельник", "вторник": "был вторник", "среда": "была среда", "четверг": "был четверг",
          "пятница": "была пятница", "суббота": "была суббота", "воскресенье": "было воскресенье"}


def _sentences(q):
    return re.split(r"(?<=[.?])\s+", q.strip())


def _solve(question):
    facts = solver.facts_of(question)
    return solver.derive(facts) if facts else None


def change(rng, t):
    """(clause, changed question) for a task, or None when this kind of task has no change here."""
    q, parts = t["q"], _sentences(t["q"])
    if q.startswith("У Лисы было"):
        options = [k for k, s in enumerate(parts[1:-1], 1) if re.search(r"\d+", s)]
        if not options:
            return None
        k = rng.choice(options)
        old = int(re.search(r"\d+", parts[k]).group(0))
        new = rng.choice([v for v in range(1, 16) if v != old])
        sentence = re.sub(r"\d+", str(new), parts[k], count=1)
        changed = " ".join(parts[:k] + [sentence] + parts[k + 1:])
        return "А если бы вместо «%s» было «%s»?" % (parts[k].rstrip("."), sentence.rstrip(".")), changed
    if q.startswith("Сегодня "):
        old = next(d for d in logic.DAYS if q.startswith("Сегодня %s." % d))
        new = rng.choice([d for d in logic.DAYS if d != old])
        return "А если бы сегодня %s?" % DAY_IS[new], q.replace("Сегодня %s." % old, "Сегодня %s." % new, 1)
    if "Верно ли, что" in q:
        rules = [s for s in parts if s.startswith("Все ")]
        if not rules:
            return None
        rule = rng.choice(rules)
        changed = " ".join(s for s in parts if s != rule)
        return "А если бы мы не знали, что %s?" % (rule[0].lower() + rule[1:].rstrip(".")), changed
    return None


def make(rng, t):
    found = change(rng, t)
    if not found:
        return None
    clause, changed = found
    before, after = _solve(t["q"]), _solve(changed)
    if not before or not after or any("= -" in s for s in after["steps"]):
        return None   # a count below zero is not a world worth imagining
    same = before["answer"] == after["answer"]
    steps = ["было: ответ %s" % before["answer"], "меняю одно условие"] + after["steps"]
    if same:
        steps.append("ответ не изменится")
    text = " ".join("Шаг %d: %s." % (k + 1, s) for k, s in enumerate(steps)) + " Ответ: %s." % after["answer"]
    return {"q": "%s %s" % (t["q"], clause), "solution": text, "answer": after["answer"], "same": same}


def tasks(count, seed=0, max_level=3):
    rng, out = random.Random(seed), []
    for t in solver.fresh_tasks(count * 4, 4000 + seed, max_level):
        made = make(rng, t)
        if made:
            out.append(made)
        if len(out) >= count:
            break
    return out


def measure(loaded, items):
    from backend.brain import generate
    model, state = loaded
    return sum(logic.correct(generate(model, state, t["q"], 96)["text"], t["answer"]) for t in items)


def lessons(loaded, seed=0, count=140):
    from backend import curiosity
    level = min(5, curiosity.logic_frontier() + 1)
    items = tasks(count + 20, seed, level)
    check, teach = items[:20], items[20:]
    made = {"right": measure(loaded, check), "asked": len(check), "same": sum(t["same"] for t in teach)}
    pairs = [(t["q"], t["solution"]) for t in teach]
    made["lessons"] = len(pairs)
    return pairs, made
