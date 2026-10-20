"""How strongly evolution mutates is itself tuned by evolution (Rechenberg's one-fifth rule).

Every mutant that turns out better than its parent makes the next mutations gentler; every
failure makes them a little bolder. With these factors the strength stays put when about one
mutant in five succeeds: on a plateau it grows (more genes change at once, so evolution jumps
farther), after successes it shrinks (small careful steps near a good solution). A mass
extinction gives a few generations of the boldest mutants.

The strength is the number of genes a child changes: 1 to 4. It applies to architecture
evolution, study recipes and the task population of coevolution.
"""
import random
from datetime import datetime, timezone

LOW, HIGH = 1.0, 4.0
START = 1.5
UP = 1.22 ** 0.25  # a failure: a little bolder
DOWN = 1 / 1.22     # a success: gentler; balance at a one-in-five success rate
PLATEAU = 6         # failures in a row that count as a plateau


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _path():
    from backend import training_center as tc
    return tc.folder() / "mutation.json"


def load():
    from backend import training_center as tc
    data = tc._read(_path(), {}) or {}
    strength = data.get("strength")
    return {"strength": strength if isinstance(strength, (int, float)) and LOW <= strength <= HIGH else START,
            "tries": int(data.get("tries", 0)), "wins": int(data.get("wins", 0)), "streak": int(data.get("streak", 0)),
            "boost": int(data.get("boost", 0)), "log": list(data.get("log", []))[-40:]}


def _save(data):
    from backend import training_center as tc
    data["log"] = data["log"][-40:]
    tc._write(_path(), data)


def genes(rng=None):
    """How many genes the next child changes: the strength, rounded at random so 1.5 means 1 or 2."""
    data = load()
    if data["boost"] > 0:
        return int(HIGH)
    rng = rng or random
    whole = int(data["strength"])
    return max(1, min(int(HIGH), whole + (rng.random() < data["strength"] - whole)))


def apply(mutate, parent, rng, count=None):
    """`mutate` applied `count` (or genes()) times in a row: one child with several changes."""
    child = parent
    for _ in range(count or genes(rng)):
        child = mutate(child, rng)
    return child


def record(source, improved):
    """One generation's outcome. Returns the new state."""
    data = load()
    data["tries"] += 1
    if improved:
        data["wins"] += 1
        data["streak"] = 0
        data["strength"] = max(LOW, data["strength"] * DOWN)
    else:
        data["streak"] += 1
        data["strength"] = min(HIGH, data["strength"] * UP)
    if data["boost"] > 0:
        data["boost"] -= 1
    data["log"].append({"at": _now(), "source": source, "improved": bool(improved), "strength": round(data["strength"], 3)})
    _save(data)
    return data


def boost(generations=3):
    """After an extinction: the next generations mutate at full strength."""
    data = load()
    data["boost"] = max(data["boost"], generations)
    data["log"].append({"at": _now(), "source": "вымирание", "improved": None, "strength": HIGH})
    _save(data)
    return data


def status():
    data = load()
    return {"strength": round(data["strength"], 2), "low": LOW, "high": HIGH, "tries": data["tries"], "wins": data["wins"],
            "rate": round(data["wins"] / data["tries"], 3) if data["tries"] else None, "streak": data["streak"],
            "plateau": data["streak"] >= PLATEAU, "boost": data["boost"], "log": data["log"][-12:]}
