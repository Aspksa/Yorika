"""Forward-Forward warm-up: a newborn network's blocks first learn each on their own.

Hinton's Forward-Forward idea: instead of one error sent backwards through the whole network,
every block gets a local goal. Here a block should be more active ("goodness": the mean square
of its output) on real dialogues than on corrupted ones, where the answer's tokens are shuffled.
The input of each block is detached, so no gradient ever crosses from one block into the block
below it. After the warm-up, ordinary training (backpropagation) continues as usual.

The goodness compares the two as a ratio, so a block cannot win by simply growing its outputs.
This runs only on a newborn of the newer architecture; whether it helps is decided by the
exam against a version born without it. It is known to be weaker than backpropagation on its
own, which is why it is only a warm-up here.
"""

STEPS = 200
BATCH = 4
LR = 0.0005


def _corrupt(torch, ids, masked, generator):
    """The same dialogue with the answer tokens shuffled; None when the answer is too short."""
    answer = ids[masked + 1:-1]
    if len(answer) < 2:
        return None
    order = torch.randperm(len(answer), generator=generator).tolist()
    if order == list(range(len(answer))):
        order = order[1:] + order[:1]
    return ids[:masked + 1] + [answer[k] for k in order] + ids[-1:]


def _goodness(torch, model, rows, device, detach=True):
    width_ = max(len(ids) for ids, _ in rows)
    x = torch.zeros((len(rows), width_), dtype=torch.long)
    keep = torch.zeros((len(rows), width_))
    for k, (ids, masked) in enumerate(rows):
        x[k, :len(ids)] = torch.tensor(ids)
        keep[k, masked + 1:len(ids)] = 1.0  # the answer: where real and shuffled differ
    x, keep = x.to(device), keep.to(device)
    n = x.shape[1]
    mask = torch.triu(torch.ones(n, n, dtype=torch.bool, device=device), diagonal=1)
    h = model.embedding(x) + model.position(torch.arange(n, device=device))
    out = []
    for k, block in enumerate(model.blocks):
        h = block(h.detach() if k and detach else h, mask)
        g = h.float().pow(2).mean(-1)
        out.append((g * keep).sum(1) / keep.sum(1).clamp(min=1))
    return out


def warmup(torch, model, rows, device, steps=STEPS, seed=0):
    """Trains the embeddings and blocks with local goals only. Returns how well each block tells
    a real answer from a shuffled one at the end (share of pairs, 0.5 is chance)."""
    if not hasattr(model, "blocks") or type(steps) is not int or steps < 1:
        raise ValueError("Forward-Forward работает только с новым устройством мозга")
    generator = torch.Generator().manual_seed(seed + 5)
    pairs = []
    context = model.position.num_embeddings
    for k in range(min(len(rows), 4000)):
        ids, masked = rows[k]
        ids = list(ids)[:context]
        bad = _corrupt(torch, ids, masked, generator)
        if bad is not None:
            pairs.append(((ids, masked), (bad, masked)))
    if not pairs:
        raise ValueError("Нет ответов, которые можно перемешать")
    params = [p for name, p in model.named_parameters() if name.split(".")[0] in ("embedding", "position", "blocks")]
    opt = torch.optim.Adam(params, lr=LR)
    model.train()
    for step in range(steps):
        batch = [pairs[(step * BATCH + k) % len(pairs)] for k in range(BATCH)]
        good = _goodness(torch, model, [p for p, _ in batch], device)
        bad = _goodness(torch, model, [b for _, b in batch], device)
        loss = 0.0
        for gp, gn in zip(good, bad):
            score = (gp - gn) / (gp + gn + 1e-6)
            loss = loss + torch.nn.functional.softplus(-4 * score).mean()
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(params, 1.0)
        opt.step()
    with torch.no_grad():
        sample = pairs[:64]
        good = _goodness(torch, model, [p for p, _ in sample], device)
        bad = _goodness(torch, model, [b for _, b in sample], device)
        separation = [round(float((gp > gn).float().mean()), 3) for gp, gn in zip(good, bad)]
    return {"steps": steps, "separation": separation, "pairs": len(pairs)}
