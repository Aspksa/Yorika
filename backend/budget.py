"""Thoughts cost energy: how much thinking is worth it, measured as accuracy per unit of work.

Each draft in think() costs the same work again, and a hard question also runs every pass of her
loops. On fresh checked tasks every task is answered with 1, 3 and 5 drafts; the work is drafts
times passes. Then the rule chat uses to choose drafts from her self-estimate (sure ≥ hi → one
draft, sure < lo → five, otherwise three) gets the thresholds that give the best accuracy minus
a price for the work (adaptive computation, Graves 2016, as a budget instead of a halting unit).

Only thresholds measured on the active version are used; without a self-estimate worth using
there is nothing to tune and the owner's setting stays. A laboratory measurement: no version is
created.
"""
import time

from backend import logic, solver

DRAFTS = (1, 3, 5)
PRICE = 0.05    # a fifth of a right answer for five drafts
GRID = (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.01)


def choose(p, hi, lo):
    return 1 if p >= hi else 5 if p < lo else 3


def score(rows, hi, lo):
    """(accuracy, mean work, value) of the threshold rule on measured rows."""
    right = work = 0.0
    for r in rows:
        d = choose(r["p"], hi, lo)
        right += r["right"][d]
        work += r["work"][d]
    n = max(1, len(rows))
    return right / n, work / n, right / n - PRICE * work / n


def tune(rows):
    best = None
    for hi in GRID:
        for lo in GRID:
            if lo > hi:
                continue
            accuracy, work, value = score(rows, hi, lo)
            if best is None or value > best["value"] + 1e-9:
                best = {"hi": hi, "lo": lo, "accuracy": round(accuracy, 3), "work": round(work, 2), "value": round(value, 4)}
    return best


def measure(loaded, tasks, run_id=None):
    from backend import metacog
    from backend.brain import generate, think
    model, state = loaded
    rows = []
    for t in tasks:
        first = generate(model, state, t["q"], 24)
        p = metacog.sure(model, state, t["q"], first["confidence"], run_id)
        row = {"p": p, "right": {}, "work": {}}
        for d in DRAFTS:
            result = think(model, state, t["q"], drafts=d)
            row["right"][d] = int(logic.correct(result["answer"], t["answer"]))
            row["work"][d] = d * result["passes"]
        rows.append(row)
    return rows


def _path():
    from backend import training_center as tc
    return tc.folder() / "budget.json"


def load():
    from backend import training_center as tc
    return tc._read(_path(), {}) or {}


def experiment(loaded, run_id, seed=0, count=40):
    from backend import training_center as tc
    rows = measure(loaded, solver.fresh_tasks(count, 2600 + seed, 5), run_id)
    fixed = {d: {"accuracy": round(sum(r["right"][d] for r in rows) / max(1, len(rows)), 3),
                 "work": round(sum(r["work"][d] for r in rows) / max(1, len(rows)), 2)} for d in DRAFTS}
    for d in DRAFTS:
        fixed[d]["per_work"] = round(fixed[d]["accuracy"] / max(fixed[d]["work"], 1e-9), 3)
    report = {"run": run_id, "asked": len(rows), "fixed": {str(d): v for d, v in fixed.items()},
              "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if all(r["p"] is not None for r in rows) and rows:
        report.update(rule=tune(rows))
        report["verdict"] = "по самооценке: уверена ≥ %s → 1 черновик, < %s → 5; верно %d%% при работе %s" % (
            report["rule"]["hi"], report["rule"]["lo"], round(100 * report["rule"]["accuracy"]), report["rule"]["work"])
    else:
        report["rule"] = None
        report["verdict"] = "самооценки, которой можно верить, нет: пороги не настроены; 1/3/5 черновиков дают %d%%/%d%%/%d%%" % tuple(
            round(100 * fixed[d]["accuracy"]) for d in DRAFTS)
    data = load()
    data.update(report)
    data["history"] = (data.get("history", []) + [{"at": report["at"], "fixed": report["fixed"], "rule": report["rule"]}])[-20:]
    tc._write(_path(), data)
    return {k: report[k] for k in ("asked", "fixed", "rule", "verdict")}


def thresholds(run_id=None):
    """(hi, lo) measured for this version, or the default (0.8, 0.4)."""
    data = load()
    rule = data.get("rule")
    if rule and (not run_id or data.get("run") == run_id):
        return rule["hi"], rule["lo"]
    return 0.8, 0.4


def status():
    data = load()
    return {k: data.get(k) for k in ("run", "fixed", "rule", "verdict", "at")}
