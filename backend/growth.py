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


def rebirth(source, target, examples, threshold=0.0):
    """Neurogenesis inside a version: feed-forward neurons that never fired are born again.

    A neuron is dead when its input to the activation stays at or below zero on every example.
    It gets new random input weights, and its output weights are zeroed, so at birth it changes
    almost nothing (a dead neuron's GELU output is near zero anyway); training then gives it a
    job. Works for plain feed-forward layers and for experts. Returns how many were reborn.
    """
    import torch
    from backend.neural_bpe_v1 import encode
    from backend.neural_language_bpe_v2 import make_model
    state = torch.load(Path(source), map_location="cpu", weights_only=True)
    if state.get("schema") != SCHEMA:
        raise ValueError("Неизвестный формат версии")
    width, heads, layers, context, merges, seed = state["config"]
    arch = state.get("arch") or {}
    model = make_model(torch, vocab_size=state["vocab_size"], width=width, heads=heads, layers=layers,
                       context=context, arch=arch)
    model.load_state_dict(state["weights"], strict=True)
    model.eval()
    fired, hooks = {}, []
    for k, block in enumerate(getattr(model, "blocks", [])):
        ffn = getattr(block, "ffn", None)
        if isinstance(ffn, torch.nn.Sequential):
            def hook(_m, _i, out, k=k):
                hit = (out.reshape(-1, out.shape[-1]) > 0).any(0)
                fired[k] = hit if k not in fired else fired[k] | hit
            hooks.append(ffn[0].register_forward_hook(hook))
        elif hasattr(ffn, "up"):
            def hook(module, inputs, k=k):
                x = inputs[0].reshape(-1, inputs[0].shape[-1])
                hit = (torch.einsum("nw,ewh->enh", x, module.up) > 0).any(1)
                fired[k] = hit if k not in fired else fired[k] | hit
            hooks.append(ffn.register_forward_pre_hook(hook))
    if not hooks:
        raise ValueError("В этой версии нет слоёв, где нейроны могут родиться заново")
    used = 0
    try:
        with torch.no_grad():
            for prompt, answer in examples:
                ids = [1, 3] + encode(prompt, state["tokenizer"]) + [4] + encode(answer, state["tokenizer"])
                model(torch.tensor([ids[:context]]))
                used += 1
    finally:
        for h in hooks:
            h.remove()
    if not used:
        raise ValueError("Нужны примеры, чтобы увидеть, какие нейроны молчат")
    reborn, generator = {}, torch.Generator().manual_seed(seed + 99)
    with torch.no_grad():
        for k, hit in fired.items():
            dead = ~hit
            if float(dead.float().mean()) <= threshold or not dead.any():
                continue
            ffn = model.blocks[k].ffn
            if isinstance(ffn, torch.nn.Sequential):
                idx = dead.nonzero().flatten()
                bound = width ** -0.5
                ffn[0].weight[idx] = (torch.rand(len(idx), width, generator=generator) * 2 - 1) * bound
                ffn[0].bias[idx] = 0.0
                ffn[2].weight[:, idx] = 0.0
            else:
                for e in range(dead.shape[0]):
                    idx = dead[e].nonzero().flatten()
                    if len(idx):
                        ffn.up[e][:, idx] = torch.randn(width, len(idx), generator=generator) * width ** -0.5
                        ffn.down[e][idx, :] = 0.0
            reborn[k + 1] = int(dead.sum())
    payload = dict(state, weights=model.state_dict(), step=0, reborn=reborn)
    payload.pop("optimizer", None)
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + ".tmp")
    torch.save(payload, temp)
    temp.replace(target)
    return {"reborn": reborn, "total": sum(reborn.values())}


def engulf(host, guest, target):
    """Endosymbiosis: a whole smaller version (a specialist) moves inside the host.

    Both must share the word pieces. The guest keeps all its weights and reads the same text;
    its last hidden state reaches the host through a bridge that starts at zero, so at first the
    host answers exactly as before. Training then decides how much of the guest to listen to.
    """
    import torch
    from backend.neural_language_bpe_v2 import check_arch, make_model
    h = torch.load(Path(host), map_location="cpu", weights_only=True)
    g = torch.load(Path(guest), map_location="cpu", weights_only=True)
    if h.get("schema") != SCHEMA or g.get("schema") != SCHEMA:
        raise ValueError("Неизвестный формат версии")
    if h["tokenizer"]["sha256"] != g["tokenizer"]["sha256"]:
        raise ValueError("Встроить можно только версию с тем же словарём")
    h_arch, g_arch = h.get("arch") or {}, g.get("arch") or {}
    if not h_arch or not g_arch:
        raise ValueError("Оба должны быть нового устройства")
    if h_arch.get("guest") or g_arch.get("guest"):
        raise ValueError("Внутри уже живёт специалист")
    width, heads, layers, context, merges, seed = h["config"]
    g_width, g_heads, g_layers, g_context = g["config"][:4]
    if g_context != context:
        raise ValueError("У специалиста другой контекст")
    arch = check_arch(dict(h_arch, guest={"width": g_width, "heads": g_heads, "layers": g_layers, "arch": g_arch}))
    model = make_model(torch, vocab_size=h["vocab_size"], width=width, heads=heads, layers=layers, context=context, arch=arch)
    weights = model.state_dict()
    for name, value in h["weights"].items():
        weights[name] = value
    for name, value in g["weights"].items():
        weights["guest." + name] = value
    model.load_state_dict(weights, strict=True)
    payload = {"schema": SCHEMA, "weights": model.state_dict(), "tokenizer": h["tokenizer"], "vocab_size": h["vocab_size"],
               "config": [width, heads, layers, context, merges, seed], "objective": h.get("objective", "dialogue"),
               "arch": arch, "step": 0}
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + ".tmp")
    torch.save(payload, temp)
    temp.replace(target)
    return {"parameters": sum(p.numel() for p in model.parameters()), "guest_parameters": sum(v.numel() for v in g["weights"].values())}
