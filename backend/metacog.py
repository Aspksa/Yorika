"""Knowing what she does not know: before answering she estimates whether she will get it right.

Two signals she already has: how unsure the first word is (entropy) and how confident her greedy
answer was. On fresh checked tasks a small logistic model learns how these predict being right.
The quality of that self-knowledge is measured as the Brier score against always guessing the
average (lower is better); only a calibration that beats the average is used.

Used in the chat with her own model: a question she is sure about gets one draft, a hard one five
drafts and every pass of her loops, and the reply carries how sure she was. Lessons «Сможешь ли
ты решить…?» teach her to say it in words, from what actually happened.
"""
import math
import random
import time

from backend import logic, solver


def features(model, state, question, answer_confidence):
    from backend.brain import difficulty
    return [difficulty(model, state, question), answer_confidence]


def _p(w, x):
    z = w[0] + w[1] * x[0] + w[2] * x[1]
    return 1 / (1 + math.exp(-max(-30, min(30, z))))


def fit(rows, steps=400, lr=0.3):
    """rows: (features, right). Plain logistic regression with gradient steps."""
    if not rows:
        return [0.0, 0.0, 0.0]
    mean = [sum(r[0][k] for r in rows) / len(rows) for k in range(2)]
    w = [math.log((sum(r[1] for r in rows) + 0.5) / (len(rows) - sum(r[1] for r in rows) + 0.5)), 0.0, 0.0]
    for _ in range(steps):
        grad = [0.0, 0.0, 0.0]
        for x, y in rows:
            xc = [x[0] - mean[0], x[1] - mean[1]]
            err = _p(w, xc) - y
            grad[0] += err
            grad[1] += err * xc[0]
            grad[2] += err * xc[1]
        w = [wi - lr * g / len(rows) for wi, g in zip(w, grad)]
    # Fold the centring into the intercept so predict() takes raw features.
    return [w[0] - w[1] * mean[0] - w[2] * mean[1], w[1], w[2]]


def brier(rows, w=None):
    base = sum(y for _, y in rows) / len(rows) if rows else 0
    return round(sum(((_p(w, x) if w else base) - y) ** 2 for x, y in rows) / max(1, len(rows)), 4)


def observe(loaded, tasks):
    from backend.brain import generate
    model, state = loaded
    rows = []
    for t in tasks:
        draft = generate(model, state, t["q"], 96)
        rows.append((features(model, state, t["q"], draft["confidence"]), int(logic.correct(draft["text"], t["answer"]))))
    return rows


def _path():
    from backend import training_center as tc
    return tc.folder() / "metacog.json"


def load():
    from backend import training_center as tc
    return tc._read(_path(), {}) or {}


def calibrate(loaded, run_id, seed=0, count=60):
    tasks = solver.fresh_tasks(count, 900 + seed, 5)
    rows = observe(loaded, tasks)
    half = len(rows) // 2
    w = fit(rows[:half])
    held = rows[half:]
    report = {"run": run_id, "w": w, "brier": brier(held, w), "base": brier(held), "right": sum(y for _, y in rows),
              "asked": len(rows), "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    report["useful"] = report["brier"] < report["base"]
    from backend import training_center as tc
    data = load()
    data.update(report)
    data["history"] = (data.get("history", []) + [{k: report[k] for k in ("at", "brier", "base", "right", "asked")}])[-20:]
    tc._write(_path(), data)
    return report, rows


def sure(model, state, question, confidence, run_id=None):
    """Probability of being right from her calibration, or None when there is none worth using
    (no calibration, one that is not better than the average, or one made for another version)."""
    try:
        # The inner observer reads her hidden state; when it beat this calibration, it decides.
        from backend import observer
        inner = observer.sure(model, state, question, run_id)
        if inner is not None:
            return inner
    except Exception:  # noqa: BLE001 - a broken probe leaves the calibration
        pass
    data = load()
    if not data.get("useful") or not data.get("w") or (run_id and data.get("run") != run_id):
        return None
    return round(_p(data["w"], features(model, state, question, confidence)), 3)


def drafts_for(p, default, run_id=None):
    """Drafts from the self-estimate; the thresholds are the ones the budget measured for this version."""
    if p is None:
        return default
    from backend import budget
    hi, lo = budget.thresholds(run_id)
    return 1 if p >= hi else 5 if p < lo else max(3, default)


def lessons(loaded, seed=0, count=80, run_id=None):
    report, rows = calibrate(loaded, run_id, seed)
    rng = random.Random(seed)
    tasks = solver.fresh_tasks(count, 1300 + seed, 5)
    outcome = observe(loaded, tasks)
    pairs = []
    for t, (_, right) in zip(tasks, outcome):
        pairs.append(("Сможешь ли ты решить: %s" % t["q"],
                      "Да, думаю, справлюсь." if right else "Скорее нет: для меня это пока трудно, подумаю дольше."))
        if not right and rng.random() < 0.5:
            pairs.append((t["q"], t["solution"]))
    return pairs, {k: report[k] for k in ("brier", "base", "right", "asked", "useful")}
