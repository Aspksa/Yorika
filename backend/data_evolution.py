"""Evolving the lessons themselves: helpful examples survive and multiply, harmful ones die.

Each lesson example is scored by how well a step on it agrees with a step on held-out practice
examples (never exam questions): the cosine between the two gradients of the output layer
(a cheap form of TracIn influence). An example whose step points away from the practice set
would make her worse there; it dies. The places freed, plus a tenth more, are refilled with
fresh examples from the sources whose examples scored best (each question may appear only
once in a lesson, so the helpful multiply through their source), and the next generation of
lessons leans toward what helped.

The score is measured on the output layer only and on a handful of practice examples: a guide
for choosing lessons, not proof that an example helps. The exam after the lesson decides.
"""
import random
from datetime import datetime, timezone

PRACTICE = 24
TOP = 0.1


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _path():
    from backend import training_center as tc
    return tc.folder() / "data-evolution.json"


def load():
    from backend import training_center as tc
    data = tc._read(_path(), {}) or {}
    return {"generation": int(data.get("generation", 0)), "sources": data.get("sources", {}), "log": data.get("log", [])[-20:]}


def _hidden_and_target(torch, model, state, record):
    from backend.neural_bpe_v1 import encode
    tokenizer, context = state["tokenizer"], state["config"][3]
    prefix = [1, 3] + encode(record["prompt"], tokenizer) + [4]
    ids = prefix + encode(record["answer"], tokenizer) + [2]
    if len(ids) > context + 1:
        return None
    seen = {}
    hook = model.output.register_forward_hook(lambda _m, inputs, _o: seen.setdefault("h", inputs[0].detach()))
    try:
        with torch.no_grad():
            model(torch.tensor([ids[:-1]]))
    finally:
        hook.remove()
    y = torch.tensor(ids[1:])
    y[:len(prefix) - 1] = -100
    return seen["h"][0], y


def _gradient(torch, model, pairs):
    """Gradient of the output layer for one or several examples, flattened."""
    from torch.nn import functional as F
    weight = model.output.weight.detach().clone().requires_grad_(True)
    bias = model.output.bias.detach().clone().requires_grad_(True)
    loss = 0.0
    for h, y in pairs:
        loss = loss + F.cross_entropy(F.linear(h, weight, bias), y, ignore_index=-100)
    grad_w, grad_b = torch.autograd.grad(loss / len(pairs), (weight, bias))
    return torch.cat([grad_w.flatten(), grad_b])


def scores(loaded, records, practice):
    """Cosine of each example's step with the practice step; None for examples that do not fit."""
    import torch
    model, state = loaded
    model.eval()
    probe = [p for p in (_hidden_and_target(torch, model, state, r) for r in practice) if p is not None]
    if not probe:
        raise ValueError("Нет примеров для сравнения")
    target = _gradient(torch, model, probe)
    out = []
    for r in records:
        pair = _hidden_and_target(torch, model, state, r)
        if pair is None:
            out.append(None)
            continue
        g = _gradient(torch, model, [pair])
        out.append(round(float(torch.nn.functional.cosine_similarity(g, target, dim=0)), 4))
    return out


def evolve(loaded, records, refill, seed=0):
    """records: this generation's lessons (each with "source"); refill(source, n, seed) makes
    fresh lessons of one source. Returns the next generation and a report."""
    rng = random.Random(seed)
    records = list(records)
    rng.shuffle(records)
    practice, pool = records[:PRACTICE], records[PRACTICE:]
    if len(pool) < 20:
        raise ValueError("Для эволюции уроков мало примеров: %d" % len(pool))
    found = scores(loaded, pool, practice)
    scored = [(s, r) for s, r in zip(found, pool) if s is not None]
    scored.sort(key=lambda p: -p[0])
    alive = [r for s, r in scored if s >= 0]
    by_source = {}
    for s, r in scored:
        by_source.setdefault(r.get("source") or "?", []).append(s)
    means = {k: round(sum(v) / len(v), 4) for k, v in by_source.items()}
    dead = len(scored) - len(alive)
    fresh = []
    good = sorted((k for k, v in means.items() if v > 0 and k != "?"), key=lambda k: -means[k])
    born = dead + int(len(scored) * TOP)
    if born and good:
        weights = [max(1e-3, means[k]) for k in good]
        for k, source in enumerate(good):
            n = max(1, round(born * weights[k] / sum(weights)))
            fresh += refill(source, n, seed + 1000 * (data_generation() + 1) + k)
    keys, out = set(), []
    for r in practice + alive + fresh:
        key = r["prompt"].casefold().strip()
        if key in keys:
            continue
        keys.add(key)
        out.append(r)
    fresh_kept = len(out) - len(practice) - len(alive)
    data = load()
    data["generation"] += 1
    for source, mean in means.items():
        data["sources"][source] = mean
    entry = {"at": _now(), "generation": data["generation"], "kept": len(alive), "died": dead,
             "fresh": fresh_kept, "sources": means}
    data["log"].append(entry)
    from backend import training_center as tc
    data["log"] = data["log"][-20:]
    tc._write(_path(), data)
    return out, entry


def data_generation():
    return load()["generation"]


def status():
    data = load()
    return {"generation": data["generation"], "sources": data["sources"], "last": data["log"][-1] if data["log"] else None}
