"""Growing brain: new layers are added so the network computes exactly what it did before.

A new block's attention and feed-forward outputs start at zero, so with pre-norm residual
blocks it passes its input through unchanged. Training then decides what the new layers learn;
nothing already learned is thrown away. Only the "lab" architecture grows this way: the
original post-norm network cannot take a new layer without changing its answers.
"""
import hashlib
from pathlib import Path

from backend.neural_language_longrun import SCHEMA


def grow(source, target, add_layers=2):
    import torch
    from backend.neural_language_bpe_v2 import make_model
    if type(add_layers) is not int or not 1 <= add_layers <= 8:
        raise ValueError("Добавить можно от 1 до 8 слоёв")
    state = torch.load(Path(source), map_location="cpu", weights_only=True)
    if state.get("schema") != SCHEMA:
        raise ValueError("Неизвестный формат версии")
    arch = state.get("arch") or {}
    if not arch:
        raise ValueError("Расти умеет только мозг нового устройства: обучите версию с «новым устройством»")
    width, heads, layers, context, merges, seed = state["config"]
    if layers + add_layers > 16:
        raise ValueError("Больше 16 слоёв не поддерживается")
    old = make_model(torch, vocab_size=state["vocab_size"], width=width, heads=heads, layers=layers,
                     context=context, arch=arch)
    old.load_state_dict(state["weights"], strict=True)
    new = make_model(torch, vocab_size=state["vocab_size"], width=width, heads=heads,
                     layers=layers + add_layers, context=context, arch=arch)
    weights = new.state_dict()
    for name, value in old.state_dict().items():
        weights[name] = value
    # Fresh blocks keep their zeroed output projections from make_model: an exact identity.
    new.load_state_dict(weights, strict=True)
    payload = {"schema": SCHEMA, "weights": new.state_dict(), "tokenizer": state["tokenizer"],
               "vocab_size": state["vocab_size"], "config": [width, heads, layers + add_layers, context, merges, seed],
               "objective": state.get("objective", "dialogue"), "arch": arch, "grown_from": hashlib.sha256(
                   Path(source).read_bytes()).hexdigest(), "step": 0}
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + ".tmp")
    torch.save(payload, temp)
    temp.replace(target)
    return {"layers": layers + add_layers, "parameters": sum(p.numel() for p in new.parameters())}


def reshape_experts(source, target, usage=None, change=2):
    """More experts where the router is crowded, fewer where experts sit idle.

    change=+2 splits the two busiest experts: each gets a twin with the same weights and a
    slightly perturbed router row, so the twins share the load and can then specialise.
    change=-2 removes the two least used. Unlike growing layers this is not an exact identity;
    the exam after the next lesson says what it cost.
    """
    import torch
    from backend.neural_language_bpe_v2 import check_arch
    if change not in (2, -2):
        raise ValueError("Экспертов можно добавить или убрать по два")
    state = torch.load(Path(source), map_location="cpu", weights_only=True)
    arch = dict(state.get("arch") or {})
    count = arch.get("experts", 0)
    if not count:
        raise ValueError("У этой версии нет роя экспертов")
    new_count = count + change
    try:
        arch = check_arch(dict(arch, experts=new_count))
    except ValueError:
        raise ValueError("Экспертов может быть 2, 4, 6 или 8") from None
    share = list(usage) if usage and len(usage) == count else [1.0 / count] * count
    order = sorted(range(count), key=lambda e: -share[e])
    keep = list(range(count)) if change > 0 else sorted(order[:new_count])
    twins = order[:change] if change > 0 else []
    generator = torch.Generator().manual_seed(7)
    weights = {}
    for name, value in state["weights"].items():
        if ".ffn.router.weight" in name:
            rows = [value[e] for e in keep] + [value[e] + torch.randn(value.shape[1], generator=generator) * value.std() * 0.01
                                               for e in twins]
            weights[name] = torch.stack(rows)
        elif name.endswith(".ffn.up") or name.endswith(".ffn.down"):
            weights[name] = torch.stack([value[e] for e in keep] + [value[e].clone() for e in twins])
        else:
            weights[name] = value
    payload = dict(state, weights=weights, arch=arch, step=0)
    payload.pop("optimizer", None)
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + ".tmp")
    torch.save(payload, temp)
    temp.replace(target)
    return {"experts": new_count, "split" if change > 0 else "removed": twins if change > 0 else
            sorted(set(range(count)) - set(keep))}
