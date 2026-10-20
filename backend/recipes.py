"""Evolution of how she studies, not only of what she is: recipes of a lesson.

A recipe is a learning rate, a share of each kind of lessons (your conversations, logic, the game
world, programs, tools), a logic level and a lesson length. A plan of kind «recipes» runs the
best known recipe and its mutants from the same active version; each lesson is scored on the
same exams (the active version's dialogue exam, logic and the game world) by how much it
improved them per hour of study. The winner becomes the recipe quick lessons and sleep use.

The recipe also carries a learning rule (weight decay, gradient clip, warm-up and plasticity
across depth: which blocks change faster). So evolution changes the law by which her neurons
change, not only the neurons: the winning rule passes to every later lesson.

Gains are measured on one laptop, from one starting version, on short lessons: they guide the
next choice, they are not a law. Nothing is activated without the usual check (continual.judge).
"""
import json
import random
from datetime import datetime, timezone

SOURCES = ("experience", "logic", "sim", "programs", "tools")
LRS = (0.0001, 0.0002, 0.0003, 0.0004, 0.0006, 0.0008)
TIME = (0.5, 1.0, 1.5)
DEFAULT = {"lr": 0.0003, "mix": {"experience": 4, "logic": 2, "sim": 2, "programs": 1, "tools": 1}, "level": 0, "time": 1.0}
LESSONS = 400
RULE_VALUES = {"wd": (0.0, 0.01, 0.05, 0.1), "clip": (0.5, 1.0, 2.0), "warmup": (0, 20, 100), "plasticity": (0.5, 1.0, 2.0)}


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _path():
    from backend import training_center as tc
    return tc.folder() / "recipes.json"


def load():
    from backend import training_center as tc
    data = tc._read(_path(), {}) or {}
    best = data.get("best") if valid(data.get("best")) else None
    return {"best": best, "tried": data.get("tried", []), "generations": data.get("generations", 0)}


def _valid_rule(rule):
    from backend.neural_language_longrun import check_rule
    try:
        return rule is None or check_rule(rule) == rule
    except ValueError:
        return False


def valid(recipe):
    return (isinstance(recipe, dict) and _valid_rule(recipe.get("rule")) and recipe.get("lr") in LRS and recipe.get("time") in TIME and
            recipe.get("level") in (0, 1) and isinstance(recipe.get("mix"), dict) and set(recipe["mix"]) == set(SOURCES) and
            all(type(v) is int and 0 <= v <= 4 for v in recipe["mix"].values()) and sum(recipe["mix"].values()) > 0)


def best():
    return load()["best"] or json.loads(json.dumps(DEFAULT))


def learning_rate():
    """The learning rate quick lessons and sleep use: the winner's, or the usual 0.0003."""
    return best()["lr"]


def learning_rule():
    return best().get("rule")


def mutate(recipe, rng):
    child = json.loads(json.dumps(recipe))
    gene = rng.choice(["lr", "mix", "mix", "level", "time", "rule", "rule"])
    if gene == "rule":
        rule = dict(child.get("rule") or {"wd": 0.01, "clip": 1.0, "warmup": 0, "plasticity": 1.0})
        key = rng.choice(sorted(RULE_VALUES))
        rule[key] = rng.choice([v for v in RULE_VALUES[key] if v != rule.get(key)])
        child["rule"] = dict(sorted(rule.items()))
    elif gene == "lr":
        child["lr"] = rng.choice([v for v in LRS if v != recipe["lr"]])
    elif gene == "level":
        child["level"] = 1 - recipe["level"]
    elif gene == "time":
        child["time"] = rng.choice([v for v in TIME if v != recipe["time"]])
    else:
        source = rng.choice(SOURCES)
        child["mix"][source] = max(0, min(4, child["mix"][source] + rng.choice([-1, 1, 2])))
        if not sum(child["mix"].values()):
            child["mix"]["experience"] = 1
    return child


def candidates(count, seed=None):
    """The best recipe and `count - 1` different mutants of it."""
    rng = random.Random(seed)
    parent = best()
    out, seen = [parent], {describe(parent)}
    for _ in range(count * 20):
        if len(out) >= count:
            break
        child = mutate(parent, rng)
        if describe(child) not in seen:
            seen.add(describe(child))
            out.append(child)
    return out


def describe(recipe):
    names = {"experience": "разговоры", "logic": "логика", "sim": "мир", "programs": "программы", "tools": "инструменты"}
    total = sum(recipe["mix"].values())
    mix = ", ".join("%s %d%%" % (names[k], round(100 * v / total)) for k, v in recipe["mix"].items() if v)
    rule = recipe.get("rule")
    law = (" · закон: распад %g, срез %g, разгон %d, пластичность ×%g" % (rule["wd"], rule["clip"], rule["warmup"], rule["plasticity"])
           if rule else "")
    return "шаг %g · %s%s · время ×%g%s" % (recipe["lr"], mix, " · логика выше" if recipe["level"] else "", recipe["time"], law)


def records(recipe, seed=0, total=LESSONS):
    """Lessons in the recipe's proportions; every source keeps its exam questions out."""
    from backend import curiosity, logic, plans, programs, simworld, tools
    weights = recipe["mix"]
    share = {k: int(total * v / sum(weights.values())) for k, v in weights.items()}
    out = []
    if share["experience"]:
        out += plans._experience(share["experience"], seed)
    if share["logic"]:
        level = min(5, curiosity.logic_frontier() + recipe["level"])
        out += plans._synthetic(logic.lessons(level, max(1, share["logic"] // level), seed=seed + 7), "logic")[:share["logic"]]
    if share["sim"]:
        out += plans._synthetic(simworld.lessons(share["sim"], seed=seed + 11), "sim")
    if share["programs"]:
        if not programs.library():
            programs.learn(seed)
        per = max(1, share["programs"] // max(1, len(programs.library())))
        out += plans._synthetic(programs.lessons(per_skill=per, seed=seed + 5), "programs")[:share["programs"]]
    if share["tools"]:
        out += plans._synthetic(tools.lessons(share["tools"], seed=seed + 3), "tools")[:share["tools"]]
    seen, unique = set(), []
    for r in out:
        key = r["prompt"].casefold().strip()
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def scores(loaded, test):
    """The three numbers every recipe is judged on, higher is better."""
    from backend import logic, simworld
    from backend.neural_language_longrun import score_checkpoint
    levels = logic.exam(loaded)["levels"]
    sim = simworld.exam(loaded)
    return {"dialogue": -score_checkpoint(None, test, loaded=loaded)["per_char"],
            "logic": sum(levels.values()) / len(levels), "sim": sum(sim.values()) / len(sim)}


def gain(before, after, hours):
    """Exam improvement per hour of study (dialogue counts most, then logic and the world)."""
    delta = ((after["dialogue"] - before["dialogue"]) + 0.5 * (after["logic"] - before["logic"]) +
             0.3 * (after["sim"] - before["sim"]))
    return round(delta / max(hours, 1e-6), 4), round(delta, 4)


def remember(results):
    """results: [{"recipe", "run", "gain_per_hour", "gain", "hours"}]; the best one with a real gain wins."""
    from backend import training_center as tc
    data = load()
    for r in results:
        data["tried"].append({"recipe": r["recipe"], "label": describe(r["recipe"]), "run": r["run"],
                              "gain_per_hour": r["gain_per_hour"], "gain": r["gain"], "at": _now()})
    data["tried"] = data["tried"][-40:]
    data["generations"] += 1
    winner = max(results, key=lambda r: r["gain_per_hour"]) if results else None
    changed = False
    if winner and winner["gain"] > 0:
        changed = describe(winner["recipe"]) != describe(best())
        data["best"] = winner["recipe"]
    tc._write(_path(), data)
    return {"winner": winner, "changed": changed}


def status():
    data = load()
    current = best()
    return {"best": current, "label": describe(current), "default": data["best"] is None,
            "generations": data["generations"],
            "tried": sorted(data["tried"][-12:], key=lambda r: -r["gain_per_hour"])}
