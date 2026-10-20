"""Novelty search and species: diversity is rewarded and young kinds are protected.

Every version answers the same 24 probe tasks (logic and the game world, never exam tasks, and
never in a lesson). Which ones it solves is its behaviour, a row of 24 ones and zeros. Novelty
is the mean distance to its three nearest neighbours: a version that solves different things
than the others is new, even if its score is no higher.

Versions whose behaviours differ in at most a fifth of the probes form one species. A version
that behaves unlike any species founds a new one, and the new species is protected for six
archive updates: even if it lost its tournament or its cell, evolution may choose it as a parent
(three times in ten), so a new idea has time to mature, as in NEAT. Nothing is activated or
deleted here; extinction never touches a protected species.
"""
import random
from datetime import datetime, timezone

PROBES = 24
SAME = 0.2
PROTECT = 6
NEAREST = 3
NOVEL_PARENT = 0.3

_PROBE_TASKS = None


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def probes():
    """Fixed probe tasks: half logic (levels 1–3), half the game world (levels 1–2)."""
    global _PROBE_TASKS
    if _PROBE_TASKS is None:
        from backend import logic, simworld
        rng = random.Random(555_000)
        banned = logic._exam_questions() | simworld._banned()
        tasks, seen = [], set()
        while len(tasks) < PROBES // 2:
            t = logic.task(rng, 1 + len(tasks) % 3)
            if t["q"] not in banned and t["q"] not in seen:
                seen.add(t["q"])
                tasks.append((t["q"], t["answer"]))
        for t in simworld.fresh(rng, PROBES * 4, level=1):
            if len(tasks) >= PROBES:
                break
            if t["q"] not in seen and len(t["q"]) <= 300:
                seen.add(t["q"])
                tasks.append((t["q"], t["answer"]))
        _PROBE_TASKS = tasks
    return _PROBE_TASKS


def probe_questions():
    return {q.casefold().strip() for q, _ in probes()}


def behaviour(loaded, max_tokens=96):
    from backend.brain import generate
    from backend.logic import correct
    model, state = loaded
    return "".join("1" if correct(generate(model, state, q, max_tokens)["text"], a) else "0" for q, a in probes())


def distance(a, b):
    if len(a) != len(b) or not a:
        return 1.0
    return sum(x != y for x, y in zip(a, b)) / len(a)


def novelty(bits, others):
    near = sorted(distance(bits, o) for o in others)[:NEAREST]
    return round(sum(near) / len(near), 3) if near else 1.0


def _path():
    from backend import training_center as tc
    return tc.folder() / "species.json"


def load():
    from backend import training_center as tc
    data = tc._read(_path(), {}) or {}
    return {"behaviours": data.get("behaviours", {}), "species": data.get("species", []), "updates": int(data.get("updates", 0))}


def _save(data):
    from backend import training_center as tc
    tc._write(_path(), data)


def observe(run_id, loaded, fitness):
    """Records a version's behaviour and its species. Returns {"species", "novelty", "founded", "protected"}."""
    data = load()
    bits = behaviour(loaded)
    others = [b for r, b in data["behaviours"].items() if r != run_id]
    score = novelty(bits, others)
    data["behaviours"][run_id] = bits
    data["updates"] += 1
    best, gap = None, 1.0
    for s in data["species"]:
        d = distance(bits, s["bits"])
        if d < gap:
            best, gap = s, d
    founded = best is None or gap > SAME
    if founded:
        best = {"id": max([s["id"] for s in data["species"]] or [0]) + 1, "bits": bits, "founder": run_id, "members": [],
                "born": data["updates"], "protected_until": data["updates"] + PROTECT, "best": run_id,
                "best_fitness": fitness, "at": _now()}
        data["species"].append(best)
    if run_id not in best["members"]:
        best["members"] = (best["members"] + [run_id])[-30:]
    if fitness is not None and (best.get("best_fitness") is None or fitness > best["best_fitness"]):
        best["best"], best["best_fitness"] = run_id, fitness
    _save(data)
    return {"species": best["id"], "novelty": score, "founded": founded, "protected": best["protected_until"] > data["updates"]}


def protected_runs():
    """Members of young species: extinction never removes them."""
    data = load()
    return {r for s in data["species"] if s["protected_until"] > data["updates"] for r in s["members"]}


def novel_parent(rng=None, exists=None):
    """Three times in ten: the best of a young protected species, so new kinds get to have children."""
    rng = rng or random
    data = load()
    young = [s for s in data["species"] if s["protected_until"] > data["updates"] and (exists is None or exists(s["best"]))]
    if young and rng.random() < NOVEL_PARENT:
        return rng.choice(sorted(young, key=lambda s: s["id"]))["best"]
    return None


def forget(run_ids):
    """After an extinction: deleted versions leave the behaviour list and their species."""
    data = load()
    gone = set(run_ids)
    data["behaviours"] = {r: b for r, b in data["behaviours"].items() if r not in gone}
    alive = []
    for s in data["species"]:
        s["members"] = [r for r in s["members"] if r not in gone]
        if s["members"]:
            if s["best"] in gone:
                s["best"], s["best_fitness"] = s["members"][-1], None
            alive.append(s)
    data["species"] = alive
    _save(data)


def status():
    data = load()
    rows = []
    for s in sorted(data["species"], key=lambda s: s["id"]):
        rows.append({"id": s["id"], "size": len(s["members"]), "best": s["best"], "fitness": s.get("best_fitness"),
                     "solved": s["bits"].count("1"), "bits": s["bits"],
                     "protected": s["protected_until"] > data["updates"],
                     "left": max(0, s["protected_until"] - data["updates"])})
    scores = []
    for run, bits in data["behaviours"].items():
        scores.append({"run": run, "novelty": novelty(bits, [b for r, b in data["behaviours"].items() if r != run])})
    scores.sort(key=lambda x: -x["novelty"])
    return {"species": rows, "probes": PROBES, "novel": scores[:5], "versions": len(data["behaviours"])}
