"""Her own concepts: recurring pieces of solutions become named building blocks (library learning,
as in DreamCoder).

Checked solutions are read step by step; numbers, names and days are replaced by placeholders, so
«13 - 7 = 6» and «20 - 4 = 16» are the same pattern. Two steps that often follow each other are
one idea, and a pair that repeats enough becomes a concept with a name made from what it does
(«отнять, потом удвоить»). The library keeps the concepts that save the most steps (the
description gets shorter: minimum description length). Lessons teach what each concept means and
solutions that use it as one step, so a long chain of thought becomes shorter.
"""
import random
import re
import time
from collections import Counter

from backend import logic, prover

GROUPS = ["жители леса", "друзья снега", "любители зимы", "лисы", "звери", "существа", "птицы", "рыбы", "горожане", "соседи"]
MIN_USES = 6
LIBRARY = 12
WORDS = {"+": "прибавить", "-": "отнять", "*": "удвоить", "дн.": "сдвинуть день", "старше": "сравнить",
         "все": "вывести"}


def pattern(step):
    """A step with its particulars replaced: N for numbers, ДЕНЬ, ИМЯ."""
    s = re.sub(r"\b(%s)\b" % "|".join(logic.DAYS), "ДЕНЬ", step)
    s = re.sub(r"\b(%s)\b" % "|".join(logic.NAMES), "ИМЯ", s)
    s = re.sub(r"\b(%s)\b" % "|".join(GROUPS), "ГРУППА", s)
    s = re.sub(r"\* 2", "* ДВА", s)
    return re.sub(r"-?\d+", "N", s)


def verb(p):
    if "дн." in p:
        return WORDS["дн."]
    if "старше" in p:
        return WORDS["старше"]
    if "все" in p:
        return WORDS["все"]
    for op in ("*", "+", "-"):
        if " %s " % op in p:
            return WORDS[op]
    return None


def name_of(patterns):
    verbs = [verb(p) for p in patterns]
    return ", потом ".join(verbs) if all(verbs) else None


def mine(solutions):
    """Pairs of consecutive step patterns that repeat: candidate concepts, best first."""
    pairs = Counter()
    for text in solutions:
        pats = [pattern(s) for s in prover.steps_of(text)]
        for a, b in zip(pats, pats[1:]):
            pairs[(a, b)] += 1
    found = []
    for (a, b), uses in pairs.items():
        name = name_of((a, b))
        if uses >= MIN_USES and name:
            found.append({"name": name, "patterns": [a, b], "uses": uses, "saved": uses})
    return sorted(found, key=lambda c: -c["saved"])[:LIBRARY]


def rewrite(text, library):
    """The solution with every known pair of steps merged into one named step."""
    steps = prover.steps_of(text)
    if not steps:
        return text, 0
    out, k, used = [], 0, 0
    while k < len(steps):
        if k + 1 < len(steps):
            pair = [pattern(steps[k]), pattern(steps[k + 1])]
            concept = next((c for c in library if c["patterns"] == pair), None)
            if concept:
                out.append("приём «%s»: %s, %s" % (concept["name"], steps[k], steps[k + 1]))
                k, used = k + 2, used + 1
                continue
        out.append(steps[k])
        k += 1
    answer = text[text.index("Ответ:"):] if "Ответ:" in text else ""
    return " ".join("Шаг %d: %s." % (j + 1, s) for j, s in enumerate(out)) + (" " + answer if answer else ""), used


def example(concept, rng):
    for _ in range(400):
        t = logic.task(rng, rng.randint(2, 4))
        steps = prover.steps_of(t["solution"])
        for a, b in zip(steps, steps[1:]):
            if [pattern(a), pattern(b)] == concept["patterns"]:
                return "%s, %s" % (a, b)
    return None


def _path():
    from backend import training_center as tc
    return tc.folder() / "concepts.json"


def load():
    from backend import training_center as tc
    return tc._read(_path(), {}) or {"library": [], "history": []}


def lessons(loaded, seed=0, count=200):
    """Mines the library from checked solutions (the code's and her own correct ones), then lessons:
    what each concept means, and solutions written with it."""
    from backend import solver
    from backend import training_center as tc
    rng = random.Random(seed)
    tasks = solver.fresh_tasks(count, seed, 4)
    solutions = [t["solution"] for t in tasks]
    library = mine(solutions)
    before = sum(len(prover.steps_of(s)) for s in solutions)
    rewritten = [rewrite(s, library) for s in solutions]
    after = sum(len(prover.steps_of(s)) for s, _ in rewritten)
    pairs = []
    for concept in library:
        shown = example(concept, rng)
        if shown:
            pairs.append(("Что значит приём «%s»?" % concept["name"],
                          "Это два шага одним: %s. Например: %s." % (" и ".join(concept["patterns"]), shown)))
    for t, (text, used) in zip(tasks, rewritten):
        if used:
            pairs.append((t["q"], text))
    data = load()
    data["library"] = library
    data["history"] = (data.get("history", []) + [{"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                                    "concepts": len(library), "steps_before": before, "steps_after": after}])[-20:]
    tc._write(_path(), data)
    made = {"concepts": len(library), "steps_before": before, "steps_after": after,
            "shorter": round(1 - after / before, 3) if before else 0, "top": [c["name"] for c in library[:4]]}
    return pairs, made
