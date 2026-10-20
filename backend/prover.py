"""Prover and checker: solutions written so that a weak checker can follow them (prover-verifier
games, OpenAI 2024).

Two roles of one Yorika:
- the prover solves fresh tasks in several drafts; a solution is kept as her own lesson only when
  it is right AND every step can be checked by the small checker (arithmetic and days of the week
  recomputed): legible, not just lucky;
- the checker learns to find the one wrong step in a solution. Wrong solutions come from a
  «sneaky» role played by code: a correct solution with one step quietly broken.

Before the lesson the checker's skill is measured on fresh pairs of right and broken solutions.
"""
import random
import re

from backend import logic, solver

STEP = re.compile(r"Шаг \d+:\s*")


def steps_of(solution):
    body = (solution or "").split("Ответ:")[0]
    return [s.strip().rstrip(".").strip() for s in STEP.split(body)[1:] if s.strip().rstrip(".").strip()]


def checkable(step):
    """True when the small checker can recompute this step."""
    from backend.brain import CLAIM
    return bool(CLAIM.search(step) or solver.DAY_STEP.search(step))


def step_wrong(step):
    from backend.brain import wrong_claims
    return wrong_claims(step) + solver.wrong_steps(step) > 0


def legible(text, answer):
    """Right answer, at least one step, and every checkable step is right."""
    steps = steps_of(text)
    return (logic.correct(text, answer) and bool(steps) and any(checkable(s) for s in steps)
            and not any(step_wrong(s) for s in steps))


def sneaky(task, rng):
    """The task's correct solution with one checkable step broken, or None."""
    steps = steps_of(task["solution"])
    spots = [k for k, s in enumerate(steps) if checkable(s)]
    if not spots:
        return None
    k = rng.choice(spots)
    numbers = list(re.finditer(r"-?\d+", steps[k]))
    if solver.DAY_STEP.search(steps[k]):
        day = solver.DAY_STEP.search(steps[k]).group(3)
        wrong = logic.DAYS[(logic.DAYS.index(day) + rng.randint(1, 6)) % 7]
        broken = steps[k][:steps[k].rindex(day)] + wrong
        right = day
    else:
        last = numbers[-1]
        right = last.group(0)
        broken = steps[k][:last.start()] + str(int(right) + rng.choice([-2, -1, 1, 2, 10]))
    bad = list(steps)
    bad[k] = broken
    text = " ".join("Шаг %d: %s." % (j + 1, s) for j, s in enumerate(bad))
    return {"text": text, "step": k + 1, "broken": broken, "right": right}


def check_prompt(task, text):
    return "Проверь решение. Задача: %s Решение: %s" % (task["q"], text)


def check_answer(found):
    if found is None:
        return "Решение верное."
    return "Ошибка в шаге %d: %s — неверно, должно быть %s." % (found["step"], found["broken"], found["right"])


def checker_right(reply, found):
    reply = (reply or "").casefold()
    if found is None:
        return "верное" in reply and "ошибка" not in reply
    return ("шаге %d" % found["step"]) in reply


def lessons(loaded, seed=0, count=60):
    from backend import brain
    model, state = loaded
    rng = random.Random(seed)
    tasks = [t for t in solver.fresh_tasks(count * 2, seed, 3) if steps_of(t["solution"])]
    pairs, made = [], {"asked": 0, "right": 0, "legible": 0, "checks": 0, "checker_right": 0}
    # The checker before its lesson: half broken, half correct, never shown in lessons.
    for t in tasks[:12]:
        found = sneaky(t, rng) if rng.random() < 0.5 else None
        text = found["text"] if found else t["solution"][:t["solution"].rindex("Ответ:")].strip()
        reply = brain.generate(model, state, check_prompt(t, text), 64)["text"]
        made["checks"] += 1
        made["checker_right"] += checker_right(reply, found)
    for t in tasks[12:12 + count]:
        thought = brain.think(model, state, t["q"], drafts=3, seed=rng.randrange(10 ** 6))
        made["asked"] += 1
        good = [x for x in thought["texts"] if legible(x, t["answer"])]
        made["right"] += any(logic.correct(x, t["answer"]) for x in thought["texts"])
        if good:
            made["legible"] += 1
            pairs.append((t["q"], min(good, key=len).strip()))   # the clearest: shortest legible one
        else:
            pairs.append((t["q"], t["solution"]))
        found = sneaky(t, rng)
        if found:
            pairs.append((check_prompt(t, found["text"]), check_answer(found)))
        plain = t["solution"][:t["solution"].rindex("Ответ:")].strip()
        if rng.random() < 0.5:
            pairs.append((check_prompt(t, plain), check_answer(None)))
    return pairs, made
