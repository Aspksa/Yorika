"""Tasks that evolve together with her, and the Red Queen game between two versions.

Coevolution of tasks: a population of task genomes (a kind of task and its level: «лабиринт,
уровень 3», «счёт по шагам, уровень 4»). Each generation the active version tries a few fresh
tasks of every genome. A genome is fit when she fails its tasks: those are her weak spots.
Tasks she always solves die out; tasks she can never solve count less, unless they are the only
hard ones; a genome whose failures dropped after a lesson gets a bonus (she can learn it). The
fit half survives and mutates (level up or down, another kind, another world), and the lessons
of the night come from the surviving genomes. Every task and every solution is written and
checked by a program, and no exam task is ever used.

Red Queen: two versions, each acting as a quiz master. A quiz master may ask only questions it
answers correctly itself; it scores a point for each one its rival fails. Then each one studies
the tasks it failed (with the program's solution) plus fresh tasks of the same genomes. Both
have to keep running to stay in place. Ratings follow the Elo formula.

Fail rates are measured on a handful of tasks: a guide for choosing lessons, not a precise score.
"""
import random
from datetime import datetime, timezone

LOGIC = ("arith", "order", "days", "sequence", "syllogism")
LOGIC_MAX = {"arith": 6, "order": 5, "days": 6, "sequence": 2, "syllogism": 4}  # longer ones do not fit a lesson
SIM_MAX = 10
SIZE = 12
PER = 6
LESSONS = 240
K = 24  # Elo step


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _path(name):
    from backend import training_center as tc
    return tc.folder() / name


def _logic_fn(kind):
    from backend import logic
    return {"arith": logic._arith, "order": logic._order, "days": logic._days, "sequence": logic._sequence,
            "syllogism": logic._syllogism}[kind]


def key(genome):
    return "%s:%s:%d" % (genome["domain"], genome["kind"], genome["level"])


def valid(genome):
    from backend import simworld
    if not isinstance(genome, dict) or type(genome.get("level")) is not int:
        return False
    if genome.get("domain") == "logic":
        return genome.get("kind") in LOGIC and 1 <= genome["level"] <= LOGIC_MAX[genome["kind"]]
    return genome.get("domain") == "sim" and genome.get("kind") in simworld.ENVS and 1 <= genome["level"] <= SIM_MAX


def describe(genome):
    from backend import simworld
    names = {"arith": "счёт по шагам", "order": "кто старше", "days": "дни недели", "sequence": "ряды чисел",
             "syllogism": "выводы"}
    name = names.get(genome["kind"]) if genome["domain"] == "logic" else simworld.ENVS[genome["kind"]][0].lower()
    return "%s, уровень %d" % (name, genome["level"])


def seeds():
    from backend import simworld
    return ([{"domain": "logic", "kind": k, "level": 1} for k in LOGIC] +
            [{"domain": "sim", "kind": e, "level": 1} for e in simworld.ORDER])


def _banned():
    from backend import logic, simworld
    return logic._exam_questions() | simworld._banned()


def make(genome, rng, count, max_chars=None):
    """`count` fresh tasks of one genome: {"q", "solution", "answer"}; never an exam task, never too long."""
    from backend import plans, simworld
    limit, banned = max_chars or plans.MAX_CHARS, _banned()
    out, seen = [], set()
    for _ in range(count * 15):
        if len(out) >= count:
            break
        if genome["domain"] == "logic":
            q, steps, answer = _logic_fn(genome["kind"])(rng, genome["level"])
            solution = " ".join("Шаг %d: %s." % (k + 1, s) for k, s in enumerate(steps)) + " Ответ: %s." % answer
        else:
            t = simworld.task(rng, genome["kind"], genome["level"])
            q, solution, answer = t["q"], t["solution"], t["answer"]
        if q in banned or q in seen or len(q) + len(solution) > limit:
            continue
        seen.add(q)
        out.append({"q": q, "solution": solution, "answer": answer})
    return out


def mutate(genome, rng):
    from backend import simworld
    child = dict(genome)
    move = rng.choice(["level", "level", "level", "kind", "domain"])
    if move == "level":
        top = LOGIC_MAX[child["kind"]] if child["domain"] == "logic" else SIM_MAX
        child["level"] = max(1, min(top, child["level"] + rng.choice([-1, 1, 1, 2])))
    elif move == "kind" and child["domain"] == "logic":
        child["kind"] = rng.choice([k for k in LOGIC if k != child["kind"]])
    elif move == "kind":
        child["kind"] = rng.choice([e for e in simworld.ORDER if e != child["kind"]])
    else:
        child["domain"] = "sim" if child["domain"] == "logic" else "logic"
        child["kind"] = rng.choice(LOGIC if child["domain"] == "logic" else simworld.ORDER)
    top = LOGIC_MAX[child["kind"]] if child["domain"] == "logic" else SIM_MAX
    child["level"] = max(1, min(top, child["level"]))
    return child


def _solves(loaded, task, max_tokens=96):
    from backend.brain import generate
    from backend.logic import correct
    model, state = loaded
    return bool(correct(generate(model, state, task["q"], max_tokens)["text"], task["answer"]))


def fitness(entry):
    """Higher means a better teacher: tasks she fails but can learn."""
    fail, history = entry.get("fail"), entry.get("history") or []
    if fail is None or entry.get("tried", 0) == 0:
        return 0.0
    learned = max(0.0, history[-2] - history[-1]) if len(history) >= 2 else 0.0
    # Sometimes failed, sometimes solved: the edge of what she can do, the best place to learn.
    edge = fail + 0.3 if 0 < fail < 1 else (0.6 if fail >= 1 else 0.0)
    return round(edge + 0.5 * learned, 4)


def load():
    from backend import training_center as tc
    data = tc._read(_path("coevolution.json"), {}) or {}
    population = [e for e in data.get("population", []) if valid(e.get("genome"))]
    return {"population": population, "generation": int(data.get("generation", 0)), "log": data.get("log", [])[-30:]}


def _save(data):
    from backend import training_center as tc
    data["log"] = data["log"][-30:]
    tc._write(_path("coevolution.json"), data)


def evolve(loaded, seed=0, size=SIZE, per=PER, lessons=LESSONS):
    """One generation: test every genome on her, keep the fit half, mutate it. Returns lesson pairs
    (question, checked solution) from the survivors and a report."""
    from backend import mutation
    rng = random.Random(seed)
    data = load()
    population = data["population"] or [{"genome": g, "born": data["generation"]} for g in seeds()]
    for entry in population:
        tasks = make(entry["genome"], rng, per)
        if not tasks:
            entry.update(fail=None, tried=0)
            continue
        failed = sum(not _solves(loaded, t) for t in tasks)
        entry["tried"], entry["fail"] = len(tasks), round(failed / len(tasks), 3)
        entry["history"] = (entry.get("history", []) + [entry["fail"]])[-6:]
        entry["fitness"] = fitness(entry)
    population.sort(key=lambda e: -e.get("fitness", 0))
    survivors = [e for e in population if e.get("tried")][:max(3, size // 2)]
    children, seen = [], {key(e["genome"]) for e in survivors}
    for _ in range(size * 20):
        if len(survivors) + len(children) >= size or not survivors:
            break
        parent = rng.choice(survivors[:max(1, len(survivors))])
        child = mutation.apply(mutate, parent["genome"], rng)
        if valid(child) and key(child) not in seen:
            seen.add(key(child))
            children.append({"genome": child, "born": data["generation"] + 1, "parent": key(parent["genome"])})
    teaching = [e for e in survivors if e.get("fitness", 0) > 0] or survivors
    total = sum(max(0.05, e.get("fitness", 0)) for e in teaching) or 1
    pairs = []
    for e in teaching:
        share = max(4, int(lessons * max(0.05, e.get("fitness", 0)) / total))
        pairs += [(t["q"], t["solution"]) for t in make(e["genome"], rng, share)]
    data["population"] = survivors + children
    data["generation"] += 1
    weak = [{"genome": key(e["genome"]), "label": describe(e["genome"]), "fail": e["fail"]} for e in survivors[:4]]
    data["log"].append({"at": _now(), "generation": data["generation"], "weak": weak, "lessons": len(pairs)})
    _save(data)
    return pairs, {"generation": data["generation"], "weak": weak, "lessons": len(pairs), "population": len(data["population"])}


def status():
    data = load()
    rows = sorted(data["population"], key=lambda e: -e.get("fitness", 0))
    return {"generation": data["generation"],
            "top": [{"label": describe(e["genome"]), "fail": e.get("fail"), "fitness": e.get("fitness", 0),
                     "trend": (e.get("history") or [None])[-2:]} for e in rows[:6]],
            "size": len(rows), "log": data["log"][-6:], "redqueen": redqueen_status()}


# ---- the Red Queen ----------------------------------------------------------------------

def _ratings():
    from backend import training_center as tc
    data = tc._read(_path("redqueen.json"), {}) or {}
    return {"ratings": data.get("ratings", {}), "matches": data.get("matches", [])[-20:]}


def elo(a, b, score_a):
    """New ratings after a match; score_a is 1 for a win of a, 0.5 for a draw, 0 for a loss."""
    expected = 1 / (1 + 10 ** ((b - a) / 400))
    change = K * (score_a - expected)
    return round(a + change, 1), round(b - change, 1)


def match(left, right, seed=0, questions=20):
    """left/right: (run id, loaded). Each asks `questions` tasks it can answer itself; a point for
    every one the rival fails. Returns the lesson pairs for each side and the match report."""
    rng = random.Random(seed)
    data = load()
    genomes = [e["genome"] for e in sorted(data["population"], key=lambda e: -e.get("fitness", 0))] or seeds()
    sides = {"left": left, "right": right}
    lessons = {"left": [], "right": []}
    report = {}
    for asker, rival in (("left", "right"), ("right", "left")):
        asked, points, wasted = 0, 0, 0
        for k in range(questions):
            genome = genomes[k % len(genomes)]
            tasks = make(genome, rng, 1)
            if not tasks:
                continue
            task = tasks[0]
            if not _solves(sides[asker][1], task):
                wasted += 1
                lessons[asker].append((genome, task))
                continue
            asked += 1
            if not _solves(sides[rival][1], task):
                points += 1
                lessons[rival].append((genome, task))
        report[asker] = {"asked": asked, "points": points, "wasted": wasted}
    total = report["left"]["points"] + report["right"]["points"]
    score = 0.5 if total == 0 else report["left"]["points"] / total
    store = _ratings()
    a, b = store["ratings"].get(left[0], 1000.0), store["ratings"].get(right[0], 1000.0)
    store["ratings"][left[0]], store["ratings"][right[0]] = elo(a, b, score)
    entry = {"at": _now(), "left": left[0], "right": right[0], "score": [report["left"]["points"], report["right"]["points"]],
             "asked": [report["left"]["asked"], report["right"]["asked"]],
             "ratings": [store["ratings"][left[0]], store["ratings"][right[0]]]}
    store["matches"].append(entry)
    from backend import training_center as tc
    tc._write(_path("redqueen.json"), {"ratings": store["ratings"], "matches": store["matches"][-20:]})
    out = {}
    for side, failed in lessons.items():
        pairs = []
        for genome, task in failed:
            pairs.append((task["q"], task["solution"]))
            pairs += [(t["q"], t["solution"]) for t in make(genome, rng, 3)]
        out[side] = pairs
    return out["left"], out["right"], dict(entry, report=report)


def redqueen_status():
    store = _ratings()
    last = store["matches"][-1] if store["matches"] else None
    return {"last": last, "matches": len(store["matches"]),
            "ratings": sorted(({"run": r, "rating": v} for r, v in store["ratings"].items()), key=lambda x: -x["rating"])[:5]}
