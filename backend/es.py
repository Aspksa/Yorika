"""Evolving the weights themselves, without gradients (evolution strategies).

OpenAI-style ES: from the current weights, pairs of copies are made with the same random noise
added and subtracted (antithetic pairs). Each copy answers a fixed handful of lessons and its
loss is measured. The weights then move toward the noise directions of the copies that did
better, weighted by rank. Nothing is differentiated: only forward passes, like natural
selection acting on whole networks.

It is much slower per step than ordinary training and is not expected to beat it; it explores
in a different way (it can cross flat areas where gradients say nothing), and the exam decides
whether the result is kept. The noise of every copy comes from its own seed, so memory holds
only the weights and one noise tensor at a time.
"""
import random
import time

SIGMA = 0.002   # size of the noise, relative to each tensor's own scale
LR = 0.3        # step, in units of sigma
PAIRS = 4
BATCH = 16


def _rows(state, records):
    from backend.neural_bpe_v1 import encode
    tokenizer, context = state["tokenizer"], state["config"][3]
    rows = []
    for r in records:
        prefix = [1, 3] + encode(r["prompt"], tokenizer) + [4]
        ids = prefix + encode(r["answer"], tokenizer) + [2]
        if len(ids) <= context + 1:
            rows.append((ids, len(prefix) - 1))
    return rows


def _loss(torch, model, rows):
    from torch.nn import functional as F
    total = 0.0
    with torch.inference_mode():
        for ids, masked in rows:
            y = torch.tensor([ids[1:]])
            y[:, :masked] = -100
            logits = model(torch.tensor([ids[:-1]]))
            total += float(F.cross_entropy(logits.reshape(-1, logits.shape[-1]), y.reshape(-1), ignore_index=-100))
    return total / max(1, len(rows))


def _noise(torch, params, seed):
    generator = torch.Generator().manual_seed(seed)
    return [torch.randn(p.shape, generator=generator) * (p.detach().float().std() if p.numel() > 1 else 1.0).clamp(min=1e-3)
            for p in params]


def evolve(loaded, records, *, seconds=600, seed=0, should_stop=None):
    """Runs ES within `seconds`. Returns the weights (a state dict) and a report. The lessons are
    split: one part chooses the direction, the other part says which generation was best, so the
    result is not just fitted to the noise of one batch."""
    import torch
    model, state = loaded
    rows = _rows(state, records)
    if len(rows) < 2 * BATCH:
        raise ValueError("Для эволюции весов нужно хотя бы %d уроков, сейчас %d" % (2 * BATCH, len(rows)))
    rng = random.Random(seed)
    rng.shuffle(rows)
    check, pool = rows[:BATCH], rows[BATCH:]
    params = [p for p in model.parameters() if p.is_floating_point()]
    model.eval()
    start = time.monotonic()
    best = _loss(torch, model, check)
    first = best
    best_weights = {k: v.detach().clone() for k, v in model.state_dict().items()}
    generation, history = 0, [round(best, 4)]
    while time.monotonic() - start < seconds and not (should_stop and should_stop()):
        batch = [pool[(generation * BATCH + k) % len(pool)] for k in range(BATCH)]
        base = [p.detach().clone() for p in params]
        scored = []
        for pair in range(PAIRS):
            noise_seed = seed * 100003 + generation * PAIRS + pair
            noise = _noise(torch, params, noise_seed)
            for sign in (1, -1):
                with torch.no_grad():
                    for p, b, n in zip(params, base, noise):
                        p.copy_(b + sign * SIGMA * n.to(p.dtype))
                scored.append((_loss(torch, model, batch), noise_seed, sign))
        # Rank-based weights: robust to a few huge losses.
        order = sorted(range(len(scored)), key=lambda k: scored[k][0])
        ranks = {k: 1 - 2 * r / (len(scored) - 1) for r, k in enumerate(order)}  # best +1 … worst -1
        with torch.no_grad():
            for p, b in zip(params, base):
                p.copy_(b)
            step = [torch.zeros_like(p, dtype=torch.float32) for p in params]
            for k, (_, noise_seed, sign) in enumerate(scored):
                for s, n in zip(step, _noise(torch, params, noise_seed)):
                    s += ranks[k] * sign * n
            for p, s in zip(params, step):
                p += (LR * SIGMA / len(scored) * s).to(p.dtype)
        generation += 1
        now = _loss(torch, model, check)
        history.append(round(now, 4))
        if now < best:
            best = now
            best_weights = {k: v.detach().clone() for k, v in model.state_dict().items()}
    return best_weights, {"generations": generation, "copies": generation * PAIRS * 2, "loss_before": round(first, 4),
                          "loss_after": round(best, 4), "history": history[-30:], "seconds": round(time.monotonic() - start, 1)}


def _path():
    from backend import training_center as tc
    return tc.folder() / "es.json"


def remember(made, run_id, verdict=None):
    from backend import training_center as tc
    log = (tc._read(_path(), []) or [])[-19:]
    log.append(dict(made, run=run_id, verdict=verdict, at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
    tc._write(_path(), log)


def status():
    from backend import training_center as tc
    log = tc._read(_path(), []) or []
    return {"runs": len(log), "last": log[-1] if log else None}
