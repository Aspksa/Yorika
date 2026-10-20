"""4-bit compression of a trained version for answering (not for training).

Each weight matrix is split into groups of 64 numbers; a group keeps one scale and 4 bits per
number. The copy is about a quarter of fp16 size. It is checked on the same exam as the
original, so the page shows what compression cost.
"""
from pathlib import Path

from backend.neural_language_longrun import MAX_WEIGHTS_BYTES, SCHEMA

Q4 = "yorika-q4-v1"
GROUP = 64


def _pack(tensor):
    import torch
    flat = tensor.float().flatten()
    pad = (-flat.numel()) % GROUP
    groups = torch.cat([flat, flat.new_zeros(pad)]).view(-1, GROUP)
    scale = groups.abs().amax(1, keepdim=True).clamp_min(1e-8) / 7
    q = (groups / scale).round().clamp(-8, 7).to(torch.int16) + 8
    q = q.flatten().to(torch.uint8)
    packed = q[0::2] | (q[1::2] << 4)
    return {"packed": packed, "scale": scale.squeeze(1).half(), "shape": list(tensor.shape), "n": tensor.numel()}


def _unpack(item):
    import torch
    packed = item["packed"]
    q = torch.empty(packed.numel() * 2, dtype=torch.int16)
    q[0::2] = (packed & 15).to(torch.int16)
    q[1::2] = (packed >> 4).to(torch.int16)
    values = (q - 8).float().view(-1, GROUP) * item["scale"].float().unsqueeze(1)
    return values.flatten()[:item["n"]].view(item["shape"])


def quantize(source, target):
    import torch
    state = torch.load(Path(source), map_location="cpu", weights_only=True)
    if state.get("schema") != SCHEMA:
        raise ValueError("Неизвестный формат версии")
    q, raw = {}, {}
    for name, value in state["weights"].items():
        if value.is_floating_point() and value.dim() >= 2 and value.numel() >= 1024:
            q[name] = _pack(value)
        else:
            raw[name] = value.half() if value.is_floating_point() else value
    keep = {k: state[k] for k in ("tokenizer", "vocab_size", "config", "objective", "arch", "best_step", "step")
            if k in state}
    target = Path(target)
    temp = target.with_name(target.name + ".tmp")
    torch.save({"schema": Q4, "state": keep, "q": q, "raw": raw}, temp)
    temp.replace(target)
    return {"bytes": target.stat().st_size, "original_bytes": sum(v.numel() * 4 for v in state["weights"].values())}


def load_quantized(path):
    import torch
    from backend.neural_bpe_v1 import OFFSET, validate
    from backend.neural_language_bpe_v2 import make_model
    path = Path(path)
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_WEIGHTS_BYTES:
        raise ValueError("Missing or oversized checkpoint")
    data = torch.load(path, map_location="cpu", weights_only=True)
    if data.get("schema") != Q4:
        raise ValueError("Wrong compressed checkpoint format")
    state = dict(data["state"])
    validate(state["tokenizer"])
    if state["vocab_size"] != OFFSET + 256 + len(state["tokenizer"]["merges"]):
        raise ValueError("Vocabulary mismatch")
    width, heads, layers, context, _, _ = state["config"]
    model = make_model(torch, vocab_size=state["vocab_size"], width=width, heads=heads, layers=layers,
                       context=context, arch=state.get("arch"))
    weights = {name: _unpack(item) for name, item in data["q"].items()}
    weights.update({name: value.float() if value.is_floating_point() else value for name, value in data["raw"].items()})
    model.load_state_dict(weights, strict=True)
    model.eval()
    state["weights"] = None
    return model, state
