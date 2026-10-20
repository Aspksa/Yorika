"""Insight (grokking): a small network of her own kind first memorizes, then suddenly understands.

Power et al. (2022) saw it on modular arithmetic: trained long with strong weight decay, a network
reaches 100 % on its training examples early, stays at chance on unseen ones for a long time, and
then jumps to full accuracy on them as the memorized table is replaced by a real rule.

Here a fresh small network built from Yorika's own blocks learns «(a + b) по модулю p», the same
sum that days of the week use (p = 7 is too small to see anything, so p is larger). It sees part
of the table; the rest is the test. Two copies train side by side for the same time: one with
strong weight decay, one almost without. The curves show whether and when the jump happens and
whether regularization is what makes it. It is a laboratory experiment: it never touches the
active version and never creates one.
"""
import random
import time

P = 23
TRAIN_SHARE = 0.4
POINTS = 60


def data(p=P, share=TRAIN_SHARE, seed=0):
    pairs = [(a, b) for a in range(p) for b in range(p)]
    random.Random(seed).shuffle(pairs)
    cut = int(len(pairs) * share)
    return pairs[:cut], pairs[cut:]


def _tensors(torch, pairs, p):
    x = torch.tensor([[a, b, p] for a, b in pairs])
    y = torch.tensor([(a + b) % p for a, b in pairs])
    return x, y


def _accuracy(torch, model, x, y):
    with torch.no_grad():
        return float((model(x)[:, -1].argmax(-1) == y).float().mean())


def train(*, decay, seconds, p=P, seed=0, device="cpu", should_stop=None, width=64, layers=2):
    import torch
    from torch.nn import functional as F
    from backend.neural_language_bpe_v2 import make_model
    torch.manual_seed(seed)
    # The smallest vocabulary and context her network allows; only p + 1 tokens and 3 places are used.
    model = make_model(torch, vocab_size=261, width=width, heads=4, context=32, layers=layers, arch={"lab": True}).to(device)
    train_pairs, test_pairs = data(p, seed=seed)
    xt, yt = [t.to(device) for t in _tensors(torch, train_pairs, p)]
    xv, yv = [t.to(device) for t in _tensors(torch, test_pairs, p)]
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=decay, betas=(0.9, 0.98))
    curve, step, start = [], 0, time.monotonic()
    memorized = grokked = None
    while time.monotonic() - start < seconds and not (should_stop and should_stop()):
        model.train()
        loss = F.cross_entropy(model(xt)[:, -1], yt)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        step += 1
        if step % 25 == 0:
            model.eval()
            tr, te = _accuracy(torch, model, xt, yt), _accuracy(torch, model, xv, yv)
            curve.append({"step": step, "train": round(tr, 3), "test": round(te, 3)})
            if memorized is None and tr >= 0.99:
                memorized = step
            if grokked is None and te >= 0.95:
                grokked = step
                break
    while len(curve) > POINTS:
        curve = curve[::2]
    return {"decay": decay, "steps": step, "memorized": memorized, "grokked": grokked,
            "test": curve[-1]["test"] if curve else None,
            "gap": grokked - memorized if grokked and memorized else None, "curve": curve,
            "seconds": round(time.monotonic() - start, 1)}


def experiment(seconds=600, seed=0, device="cpu", should_stop=None):
    strong = train(decay=1.0, seconds=seconds / 2, seed=seed, device=device, should_stop=should_stop)
    weak = train(decay=0.01, seconds=seconds / 2, seed=seed, device=device, should_stop=should_stop)
    if strong["grokked"] and not weak["grokked"]:
        verdict = "озарение пришло только с сильной регуляризацией"
    elif strong["grokked"] and weak["grokked"]:
        verdict = "озарение пришло в обоих случаях; с сильной регуляризацией через %d шагов, без неё через %d" % (
            strong["grokked"], weak["grokked"])
    elif strong["memorized"]:
        verdict = "таблицу выучила, на новых примерах пока %d%% с регуляризацией и %d%% без: озарения ещё не было" % (
            round(100 * (strong["test"] or 0)), round(100 * (weak["test"] or 0)))
    else:
        verdict = "за это время не выучила даже таблицу"
    return {"p": P, "strong": strong, "weak": weak, "verdict": verdict}


def _path():
    from backend import training_center as tc
    return tc.folder() / "grokking.json"


def remember(made):
    from backend import training_center as tc
    log = (tc._read(_path(), []) or [])[-9:]
    log.append(dict(made, at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
    tc._write(_path(), log)


def status():
    from backend import training_center as tc
    log = tc._read(_path(), []) or []
    return {"runs": len(log), "last": log[-1] if log else None}
