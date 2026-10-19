"""Bounded resumable training of one BPE dialogue model; no auto-promotion."""
import hashlib
import json
from pathlib import Path
from backend.neural_bpe_v1 import OFFSET, train as fit_bpe, encode as bpe_encode, validate as check_bpe
from backend.neural_language_bpe_v2 import make_model


def digest(pairs):
    return hashlib.sha256(json.dumps(pairs, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def run(train, validation, output, *, total_steps, checkpoint_every=20,
        width=320, heads=8, layers=4, context=256, max_merges=128, seed=42):
    import torch
    from torch.nn import functional as F
    if (not isinstance(train, (list, tuple)) or not train or
            not isinstance(validation, (list, tuple)) or not validation):
        raise ValueError("Disjoint train and validation splits required")
    if set(p.casefold().strip() for p, _ in train) & set(p.casefold().strip() for p, _ in validation):
        raise ValueError("Train/validation prompt leakage")
    if (type(total_steps) is not int or not 1 <= total_steps <= 1000000 or
            type(checkpoint_every) is not int or not 1 <= checkpoint_every <= 10000):
        raise ValueError("Invalid bounded training schedule")
    if any(not isinstance(p, str) or not isinstance(a, str) or not p or not a for p, a in train + validation):
        raise ValueError("Invalid examples")
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    fingerprint = digest(train)
    if path.exists():
        if not 0 < path.stat().st_size <= 200_000_000:
            raise ValueError("Invalid checkpoint size")
        state = torch.load(path, map_location="cpu", weights_only=True)
        if (state.get("schema") != "yorika-language-longrun-v1" or
                state.get('validation_sha256', digest(validation)) != digest(validation) or
                state.get("train_sha256") != fingerprint or state.get("config") !=
                [width, heads, layers, context, max_merges, seed]):
            raise ValueError("Checkpoint incompatible with current experiment")
        tokenizer = state["tokenizer"]
        check_bpe(tokenizer)
    else:
        tokenizer = fit_bpe([s for pair in train for s in pair], max_merges=max_merges)
        state = None
    vocab = OFFSET + 256 + len(tokenizer["merges"])
    torch.manual_seed(seed)
    model = make_model(torch, vocab_size=vocab, width=width, heads=heads, layers=layers, context=context)
    count = sum(p.numel() for p in model.parameters())
    opt = torch.optim.AdamW(model.parameters(), lr=0.0003)
    start = 0
    best_nll = float('inf')
    best_step = 0
    best_path = path.with_name(path.name + '.best.pt')
    if state:
        if state.get("vocab_size") != vocab:
            raise ValueError("Vocab mismatch")
        model.load_state_dict(state["weights"], strict=True)
        opt.load_state_dict(state["optimizer"])
        torch.set_rng_state(state["rng"])
        start = state["step"]
        best_nll = float(state.get('best_validation_nll', float('inf')))
        best_step = state.get('best_step', 0)
        if best_step and (not best_path.exists() or best_step > start):
            raise ValueError('Best checkpoint missing or inconsistent')
        if best_nll != best_nll or best_nll == float('-inf'):
            raise ValueError('Invalid best score')
        if type(start) is not int or start < 0 or start > total_steps:
            raise ValueError("Invalid checkpoint step")
    def loss(pair):
        p, a = pair
        prefix = [1, 3] + bpe_encode(p, tokenizer) + [4]
        ids = prefix + bpe_encode(a, tokenizer) + [2]
        if len(ids) > context + 1:
            raise ValueError("Sequence exceeds configured context")
        x = torch.tensor([ids[:-1]], dtype=torch.long)
        y = torch.tensor([ids[1:]], dtype=torch.long)
        y[:, :len(prefix)-1] = -100
        logits = model(x)
        return F.cross_entropy(logits.reshape(-1, vocab), y.reshape(-1), ignore_index=-100)
    def evaluate():
        model.eval()
        with torch.inference_mode():
            score = sum(float(loss(pair)) for pair in validation) / len(validation)
        model.train()
        return score
    final_score = None
    for i in range(start, total_steps):
        model.train()
        opt.zero_grad(set_to_none=True)
        l = loss(train[i % len(train)])
        l.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
        opt.step()
        if (i + 1) % checkpoint_every == 0 or i + 1 == total_steps:
            final_score = evaluate()
            improved = final_score < best_nll
            if improved:
                best_nll, best_step = final_score, i + 1
            payload = {"schema": "yorika-language-longrun-v1", "weights": model.state_dict(),
                       "optimizer": opt.state_dict(), "rng": torch.get_rng_state(),
                       "step": i + 1, "tokenizer": tokenizer, "vocab_size": vocab,
                       "train_sha256": fingerprint, "validation_sha256": digest(validation),
                       "best_validation_nll": best_nll, "best_step": best_step,
                       "config": [width, heads, layers, context, max_merges, seed]}
            temp = path.with_name(path.name + ".incomplete")
            if temp.exists():
                temp.unlink()
            try:
                torch.save(payload, temp)
                if improved:
                    best_temp = best_path.with_name(best_path.name + '.incomplete')
                    try:
                        torch.save(payload, best_temp)
                        best_temp.replace(best_path)
                    finally:
                        if best_temp.exists():
                            best_temp.unlink()
                temp.replace(path)
            finally:
                if temp.exists():
                    temp.unlink()
    return {"steps": total_steps, "parameters": count, "validation_nll": final_score,
            "train_sha256": fingerprint, "tokenizer_sha256": tokenizer["sha256"],
            "checkpoint": str(path), "best_checkpoint": str(best_path),
            "best_validation_nll": best_nll, "best_step": best_step,
            "resumed_from": start}
