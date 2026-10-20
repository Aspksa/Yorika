"""The inner observer: a probe reads her hidden state and predicts whether she is about to be wrong.

Self-knowledge from the outside (metacog.py) uses two numbers: how unsure the first word is and how
confident the answer was. The observer looks inside instead: the vector her last layer holds at
the end of the question, before she writes anything (probing, as in work on whether language
models «know what they know», Kadavath et al. 2022). A small logistic probe learns from fresh
checked tasks; its quality is the Brier score on tasks it did not learn from, against always
guessing the average and against metacog on the same tasks.

It is a laboratory measurement: no version is created. When the probe beats both for the active
version, chat uses it to decide how long she thinks (metacog.sure prefers it).
"""
import time

from backend import logic, metacog, solver


def hidden(model, state, question):
    """Her last hidden vector at the end of the question (the input of her output layer)."""
    import torch
    from backend.neural_bpe_v1 import encode
    ids = ([1, 3] + encode(question, state["tokenizer"]) + [4])[-state["config"][3]:]
    seen = []
    handle = model.output.register_forward_pre_hook(lambda module, args: seen.append(args[0][0, -1].detach().float()))
    try:
        with torch.inference_mode():
            model(torch.tensor([ids], dtype=torch.long))
    finally:
        handle.remove()
    return seen[-1]


def fit(xs, ys, decay=1e-2, steps=300):
    """Logistic probe with weight decay on standardized vectors. Returns (w, b, mean, std)."""
    import torch
    x = torch.stack(xs)
    y = torch.tensor(ys, dtype=torch.float32)
    mean, std = x.mean(0), x.std(0).clamp_min(1e-4)
    z = (x - mean) / std
    w = torch.zeros(z.shape[1], requires_grad=True)
    b = torch.tensor(float(torch.logit(y.mean().clamp(0.02, 0.98))), requires_grad=True)
    optimizer = torch.optim.LBFGS([w, b], max_iter=steps)

    def closure():
        optimizer.zero_grad()
        loss = torch.nn.functional.binary_cross_entropy_with_logits(z @ w + b, y) + decay * (w * w).sum()
        loss.backward()
        return loss
    optimizer.step(closure)
    return w.detach(), float(b.detach()), mean, std


def predict(probe, x):
    import torch
    w, b, mean, std = probe
    return float(torch.sigmoid(((x - mean) / std) @ w + b))


def brier(ps, ys):
    return round(sum((p - y) ** 2 for p, y in zip(ps, ys)) / max(1, len(ys)), 4)


def observe(loaded, tasks):
    from backend.brain import generate
    model, state = loaded
    rows = []
    for t in tasks:
        draft = generate(model, state, t["q"], 96)
        rows.append({"h": hidden(model, state, t["q"]), "right": int(logic.correct(draft["text"], t["answer"])),
                     "meta": metacog.features(model, state, t["q"], draft["confidence"])})
    return rows


def _path():
    from backend import training_center as tc
    return tc.folder() / "observer.json"


def load():
    from backend import training_center as tc
    return tc._read(_path(), {}) or {}


def experiment(loaded, run_id, seed=0, count=120):
    from backend import training_center as tc
    rows = observe(loaded, solver.fresh_tasks(count, 2100 + seed, 5))
    half = len(rows) // 2
    learn, held = rows[:half], rows[half:]
    ys = [r["right"] for r in held]
    report = {"run": run_id, "asked": len(rows), "right": sum(r["right"] for r in rows),
              "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    base = sum(r["right"] for r in learn) / max(1, len(learn))
    report["base"] = brier([base] * len(held), ys)
    meta_w = metacog.fit([(r["meta"], r["right"]) for r in learn])
    report["metacog"] = brier([metacog._p(meta_w, r["meta"]) for r in held], ys)
    if 0 < sum(r["right"] for r in learn) < len(learn):
        probe = fit([r["h"] for r in learn], [r["right"] for r in learn])
        report["brier"] = brier([predict(probe, r["h"]) for r in held], ys)
        report["probe"] = {"w": [round(v, 5) for v in probe[0].tolist()], "b": probe[1],
                           "mean": [round(v, 5) for v in probe[2].tolist()], "std": [round(v, 5) for v in probe[3].tolist()]}
    else:
        report["brier"] = None   # all right or all wrong: nothing to tell apart yet
    report["useful"] = report["brier"] is not None and report["brier"] < min(report["base"], report["metacog"])
    if report["useful"]:
        verdict = "наблюдатель внутри точнее: ошибка %s против %s у самооценки и %s у угадывания"
    elif report["brier"] is None:
        verdict = "все ответы %s: наблюдателю пока нечего различать"
    else:
        verdict = "наблюдатель пока не лучше: ошибка %s против %s у самооценки и %s у угадывания"
    report["verdict"] = (verdict % ("верны" if report["right"] else "неверны") if report["brier"] is None
                         else verdict % (report["brier"], report["metacog"], report["base"]))
    data = load()
    data.update(report)
    data["history"] = (data.get("history", []) + [{k: report[k] for k in ("at", "brier", "metacog", "base", "right", "asked")}])[-20:]
    tc._write(_path(), data)
    return {k: report[k] for k in ("asked", "right", "brier", "metacog", "base", "useful", "verdict")}


def sure(model, state, question, run_id=None):
    """Probability of being right from the observer, or None when it is not worth using."""
    import torch
    data = load()
    if not data.get("useful") or not data.get("probe") or (run_id and data.get("run") != run_id):
        return None
    p = data["probe"]
    x = hidden(model, state, question)
    if x.shape[0] != len(p["w"]):
        return None
    probe = (torch.tensor(p["w"]), p["b"], torch.tensor(p["mean"]), torch.tensor(p["std"]))
    return round(predict(probe, x), 3)


def status():
    data = load()
    return {k: data.get(k) for k in ("run", "brier", "metacog", "base", "useful", "verdict", "at")}
