"""Looking inside: what each part of Yorika's network does, measured on her own exam.

Every block is switched off in turn and the exam loss is measured again: a block whose absence
barely changes the loss does little (a candidate to drop or retrain), and a network where every
block matters is a candidate to grow. Experts and memory slots report how often they are used;
the feed-forward layers report neurons that never fire. The advice that comes out is a reading
of these numbers, nothing more.
"""
USELESS = 0.002    # under 0.2 % worse without the block: it barely contributes
CROWDED = 0.03     # every block costs more than 3 % when removed: there is no slack, grow
SAMPLE = 48


def _loss(model, state, examples):
    import torch
    from torch.nn import functional as F
    from backend.neural_bpe_v1 import encode
    tokenizer, context = state["tokenizer"], state["config"][3]
    nats, chars = 0.0, 0
    with torch.inference_mode():
        for prompt, answer in examples:
            prefix = [1, 3] + encode(prompt, tokenizer) + [4]
            ids = prefix + encode(answer, tokenizer) + [2]
            if len(ids) > context + 1:
                continue
            y = torch.tensor([ids[1:]])
            y[:, :len(prefix) - 1] = -100
            logits = model(torch.tensor([ids[:-1]]))
            nats += float(F.cross_entropy(logits.reshape(-1, logits.shape[-1]), y.reshape(-1),
                                          ignore_index=-100, reduction="sum"))
            chars += len(answer) + 1
    if not chars:
        raise ValueError("Нет примеров, которые помещаются в контекст")
    return nats / chars


def _dead_neurons(model, state, examples):
    """Share of feed-forward neurons that stay at or below zero on every example."""
    import torch
    from backend.neural_bpe_v1 import encode
    seen, hooks = {}, []
    for k, block in enumerate(getattr(model, "blocks", [])):
        ffn = getattr(block, "ffn", None)
        if isinstance(ffn, torch.nn.Sequential):
            def hook(_m, _i, out, k=k):
                fired = (out.reshape(-1, out.shape[-1]) > 0).any(0)
                seen[k] = fired if k not in seen else seen[k] | fired
            hooks.append(ffn[0].register_forward_hook(hook))
    try:
        with torch.inference_mode():
            for prompt, answer in examples:
                ids = ([1, 3] + encode(prompt, state["tokenizer"]) + [4] + encode(answer, state["tokenizer"]))
                model(torch.tensor([ids[:state["config"][3]]]))
    finally:
        for h in hooks:
            h.remove()
    return {k: round(1 - float(v.float().mean()), 3) for k, v in seen.items()}


def inspect(loaded, examples):
    """Report for one version: per-block contribution, experts, memory, dead neurons, advice."""
    import torch
    model, state = loaded
    examples = [e for e in examples if isinstance(e, (list, tuple)) and len(e) == 2][:SAMPLE]
    if not examples:
        raise ValueError("Нужны экзаменационные примеры")
    lab = hasattr(model, "skip")
    base = _loss(model, state, examples)
    blocks = []
    for k, block in enumerate(getattr(model, "blocks", [])):
        norm = float(sum(p.detach().float().pow(2).sum() for p in block.parameters()) ** 0.5)
        entry = {"layer": k + 1, "norm": round(norm, 2), "contribution": None}
        if lab:
            model.skip = {k}
            try:
                entry["contribution"] = round(_loss(model, state, examples) / base - 1, 4)
            finally:
                model.skip = set()
        blocks.append(entry)
    report = {"loss": round(base, 4), "blocks": blocks, "experts": None, "memory": None,
              "dead": _dead_neurons(model, state, examples), "arch": state.get("arch") or {}}
    traced = []
    for block in getattr(model, "blocks", []):
        if hasattr(block.ffn, "router"):
            block.ffn.trace = torch.zeros(block.ffn.up.shape[0])
            traced.append(block.ffn)
    memory = getattr(model, "memory", None)
    if memory is not None:
        memory.trace = torch.zeros(memory.keys.shape[0])
        traced.append(memory)
    if traced:
        try:
            _loss(model, state, examples)
            if memory is not None:
                use = memory.trace / memory.trace.sum().clamp_min(1e-9)
                top = use.sort(descending=True).values
                report["memory"] = {"slots": int(use.numel()),
                                    "used": int((use > 0.5 / use.numel()).sum()),
                                    "top_share": round(float(top[:max(1, use.numel() // 10)].sum()), 3)}
            experts = [m for m in traced if m is not memory]
            if experts:
                total = sum(m.trace for m in experts)
                share = (total / total.sum().clamp_min(1e-9)).tolist()
                report["experts"] = [round(v, 3) for v in share]
        finally:
            for m in traced:
                m.trace = None
    report["advice"] = advice(report)
    return report


def advice(report):
    """Plain-language readings of the numbers; each names the measurement it comes from."""
    out = []
    contributions = [b["contribution"] for b in report["blocks"] if b["contribution"] is not None]
    if contributions:
        weak = [b["layer"] for b in report["blocks"] if b["contribution"] is not None and b["contribution"] < USELESS]
        if weak:
            out.append({"kind": "weak", "text": "Слой %s почти ничего не делает: без него экзамен хуже меньше чем на 0,2%%. "
                        "Расти сейчас рано, сначала стоит доучить." % ", ".join(map(str, weak))})
        elif min(contributions) > CROWDED:
            out.append({"kind": "grow", "text": "Каждый слой нужен: без любого экзамен хуже больше чем на 3%%. "
                        "Места мало, ей пора расти (+2 слоя)."})
        else:
            out.append({"kind": "ok", "text": "Слои загружены ровно: самый слабый даёт %.1f%%, самый сильный %.1f%%." % (
                min(contributions) * 100, max(contributions) * 100)})
    else:
        out.append({"kind": "old", "text": "Старое устройство: слои нельзя выключить по одному. Новое устройство это умеет."})
    if report["experts"]:
        idle = [i + 1 for i, v in enumerate(report["experts"]) if v < 0.25 / len(report["experts"])]
        if idle:
            out.append({"kind": "experts", "text": "Эксперт %s почти не работает: роутер его не выбирает." % ", ".join(map(str, idle))})
        k, busiest = len(report["experts"]), max(report["experts"])
        if busiest > 1.6 / k and k < 8:
            out.append({"kind": "experts-grow", "text": "Эксперт %d берёт %.0f%% работы при ровной доле %.0f%%: он перегружен, "
                        "стоит разделить самых занятых (+2 эксперта)." % (report["experts"].index(busiest) + 1, busiest * 100, 100 / k)})
    if report["memory"] and report["memory"]["used"] < report["memory"]["slots"] // 4:
        out.append({"kind": "memory", "text": "Из %d ячеек памяти заметно используются %d: памяти больше, чем нужно сейчас." % (
            report["memory"]["slots"], report["memory"]["used"])})
    dead = [k + 1 for k, v in report["dead"].items() if v > 0.5]
    if dead:
        out.append({"kind": "dead", "text": "В слое %s больше половины нейронов ни разу не включились." % ", ".join(map(str, dead))})
    return out
