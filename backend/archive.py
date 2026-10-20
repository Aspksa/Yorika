"""An archive of different strong versions (MAP-Elites) and tournaments between generations.

Evolution that keeps only the single best version gets stuck: every child looks like its
parent. The archive keeps the best version of every kind instead: a grid of size (by number
of parameters) × build (classic, loops, experts, memory, everything at once). A version enters
its cell when it is better there than the one already in it, so the archive stays diverse,
and new evolution picks a parent from any cell.

Before that a new version plays a tournament against its parent: the same fresh tasks of the
game world and logic, never exam tasks, for both. If it solves fewer than the parent, it does
not enter. The score that orders a cell mixes the exam per character with logic, honesty and
the game world; across different datasets it is an approximate guide, not a precise measure.

Nothing here activates a version or deletes one.
"""
import random
import zlib
from datetime import datetime, timezone

SIZES = [(2_000_000, "до 2 млн"), (8_000_000, "2–8 млн"), (20_000_000, "8–20 млн"), (40_000_000, "20–40 млн"),
         (None, "от 40 млн")]
FAMILIES = ["классика", "новое", "петли", "эксперты", "память", "без внимания", "дендриты", "всё сразу"]
TOURNAMENT = 30


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _path():
    from backend import training_center as tc
    return tc.folder() / "archive.json"


def load():
    from backend import training_center as tc
    data = tc._read(_path(), {}) or {}
    return {"cells": data.get("cells", {}), "log": data.get("log", [])}


def _save(data):
    from backend import training_center as tc
    data["log"] = data["log"][-60:]
    tc._write(_path(), data)


def size_of(parameters):
    for k, (limit, _) in enumerate(SIZES):
        if limit is None or (parameters or 0) < limit:
            return k
    return len(SIZES) - 1


def family_of(arch):
    arch = arch or {}
    if not arch.get("lab"):
        return "классика"
    features = [name for name, on in (("петли", arch.get("loops", 1) > 1), ("эксперты", bool(arch.get("experts"))),
                                      ("память", bool(arch.get("memory") or arch.get("hopfield") or arch.get("fast"))),
                                      ("без внимания", arch.get("mixer", "attn") != "attn"),
                                      ("дендриты", bool(arch.get("dendrites")))) if on]
    if len(features) >= 2:
        return "всё сразу"
    return features[0] if features else "новое"


def niche(item):
    return "%d|%s" % (size_of(item.get("parameters")), family_of(item.get("arch")))


def _mean(values):
    values = [v for v in values if isinstance(v, (int, float))]
    return sum(values) / len(values) if values else 0.0


def fitness(item):
    """Higher is better. None while the version has no exam."""
    if item.get("exam_per_char") is None:
        return None
    honesty = item.get("honesty") or {}
    score = (-item["exam_per_char"] + 0.5 * _mean(((item.get("logic") or {}).get("levels") or {}).values()) +
             0.3 * (honesty.get("honest", 0) / honesty["total"] if honesty.get("total") else 0) +
             0.3 * _mean((item.get("sim") or {}).values()))
    return round(score, 4)


# ---- tournament -----------------------------------------------------------------

def tournament_tasks(seed, count=TOURNAMENT):
    """Fresh verified tasks, half from the game world and half logic; never exam questions."""
    from backend import logic, simworld
    rng = random.Random(seed)
    tasks = [(t["q"], t["answer"]) for t in simworld.fresh(rng, count // 2, level=2)]
    banned = logic._exam_questions() | {q for q, _ in tasks}
    for _ in range(count * 20):
        if len(tasks) >= count:
            break
        t = logic.task(rng, rng.choice((1, 2, 3)))
        if t["q"] not in banned:
            banned.add(t["q"])
            tasks.append((t["q"], t["answer"]))
    return tasks


def solved(loaded, tasks, max_tokens=96):
    from backend.brain import generate
    from backend.logic import correct
    model, state = loaded
    return sum(correct(generate(model, state, q, max_tokens)["text"], a) for q, a in tasks)


def tournament(new_run, parent_run, loaded=None, count=TOURNAMENT):
    """Both versions answer the same fresh tasks; the new one passes if it solves at least as many."""
    from backend import training_center as tc
    from backend.neural_language_benchmark import load_candidate
    parent_best = tc._run_dir(parent_run) / "language-longrun.pt.best.pt"
    if not parent_best.is_file():
        return {"parent": parent_run, "skipped": "у предка нет сохранённой точки"}
    tasks = tournament_tasks(zlib.crc32(new_run.encode()), count)
    loaded = loaded or load_candidate(tc._run_dir(new_run) / "language-longrun.pt.best.pt")
    mine, theirs = solved(loaded, tasks), solved(load_candidate(parent_best), tasks)
    return {"parent": parent_run, "tasks": len(tasks), "mine": mine, "theirs": theirs, "passed": mine >= theirs,
            "at": _now()}


# ---- the archive ------------------------------------------------------------------

def update(run_id, loaded=None, play=True):
    """After a version's exam: a tournament against its parent, then a place in its cell if it is
    the best of its kind. Returns what happened, also saved as the run's "tournament"."""
    from backend import training_center as tc
    path = tc._run_dir(run_id)
    item = tc._summary(path)
    score = fitness(item)
    if item["mode"] != "long" or score is None or not item["has_best"] or item.get("kind") == "selfcheck":
        return None
    match = None
    parent = item.get("parent")
    if play and parent and parent != run_id:
        try:
            match = tournament(run_id, parent, loaded)
        except (ValueError, OSError, RuntimeError) as error:
            match = {"parent": parent, "skipped": str(error)[:120]}
        progress = tc._read(path / "progress.json", {}) or {}
        progress["tournament"] = match
        tc._write(path / "progress.json", progress)
    data = load()
    key = niche(item)
    entry = {"run": run_id, "at": _now(), "cell": key, "fitness": score}
    if match and match.get("passed") is False:
        entry["result"] = "проиграла предку %d:%d, в архив не вошла" % (match["mine"], match["theirs"])
    else:
        incumbent = data["cells"].get(key)
        if incumbent and incumbent["run"] != run_id and incumbent["fitness"] >= score and _exists(incumbent["run"]):
            entry["result"] = "в своей клетке есть сильнее (%.3f ≥ %.3f)" % (incumbent["fitness"], score)
        else:
            data["cells"][key] = {"run": run_id, "fitness": score, "parameters": item.get("parameters"),
                                  "label": tc._describe(dict(layers=item.get("layers") or 0, width=_width(path),
                                                             arch=item.get("arch"))),
                                  "added": _now(), "replaced": incumbent["run"] if incumbent and incumbent["run"] != run_id else None}
            entry["result"] = "вошла в архив" + (" вместо %s" % incumbent["run"] if incumbent and incumbent["run"] != run_id else "")
    born = _species(run_id, path, loaded, score)
    if born:
        entry["species"] = born["species"]
        if born["founded"] and "вошла" not in entry["result"]:
            entry["result"] += "; но она основала новый вид №%d, он под защитой" % born["species"]
    if item.get("kind") == "evolution":
        from backend import mutation
        mutation.record("архитектура", entry["result"].startswith("вошла"))
    data["log"].append(entry)
    _save(data)
    return dict(entry, tournament=match)


def _species(run_id, path, loaded, score):
    """Behaviour on the probe tasks and a species; never stops the archive update."""
    from backend import species
    from backend.neural_language_benchmark import load_candidate
    try:
        return species.observe(run_id, loaded or load_candidate(path / "language-longrun.pt.best.pt"), score)
    except Exception as error:  # noqa: BLE001
        import sys
        print(repr(error), file=sys.stderr)
        return None


def _width(path):
    from backend import training_center as tc
    return ((tc._read(path / "run.json", {}) or {}).get("config") or {}).get("width", 0)


def _exists(run_id):
    from backend import training_center as tc
    try:
        return (tc._run_dir(run_id) / "language-longrun.pt.best.pt").is_file()
    except ValueError:
        return False


def elites():
    return [cell["run"] for cell in load()["cells"].values() if _exists(cell["run"])]


def pick_parent(rng=None):
    """Any elite, so evolution keeps exploring different kinds; sometimes the best of a young
    protected species (backend/species.py); None while both are empty."""
    from backend import species
    rng = rng or random
    novel = species.novel_parent(rng, _exists)
    if novel:
        return novel
    found = sorted(elites())
    return rng.choice(found) if found else None


def cells():
    """The grid for the page: sizes as rows, builds as columns."""
    data = load()
    grid = []
    for k, (_, title) in enumerate(SIZES):
        row = []
        for family in FAMILIES:
            cell = data["cells"].get("%d|%s" % (k, family))
            row.append(dict(cell, alive=_exists(cell["run"])) if cell else None)
        grid.append({"size": title, "cells": row})
    filled = sum(1 for row in grid for c in row["cells"] if c)
    return {"rows": grid, "families": FAMILIES, "filled": filled, "total": len(SIZES) * len(FAMILIES),
            "log": data["log"][-12:]}
