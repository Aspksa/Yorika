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
