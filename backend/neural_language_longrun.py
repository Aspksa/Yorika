"""Bounded resumable training of one BPE dialogue model; no auto-promotion."""
import hashlib
import json
import time
from pathlib import Path
from backend.neural_bpe_v1 import OFFSET, train as fit_bpe, encode as bpe_encode, validate as check_bpe
from backend.neural_language_bpe_v2 import make_model


def digest(pairs):
    return hashlib.sha256(json.dumps(pairs, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def run(train, validation, output, *, total_steps, checkpoint_every=20,
        width=320, heads=8, layers=4, context=256, max_merges=128, seed=42,
        max_run_seconds=None, device='cpu'):
    import torch
    from torch.nn import functional as F
    if max_run_seconds is not None and (type(max_run_seconds) not in (int, float) or
            not 0 < max_run_seconds <= 86400):
        raise ValueError("Invalid run time budget")
    if device not in ("cpu", "cuda"):
        raise ValueError("Unsupported training device")
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA required but unavailable; no CPU fallback")
    train_device = torch.device(device)
    started_at = time.monotonic()
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
        if state.get("training_device", "cpu") != device:
            raise ValueError("Checkpoint device transition requires a new experiment; exact resume denied")
        if state.get("vocab_size") != vocab:
            raise ValueError("Vocab mismatch")
        model.load_state_dict(state["weights"], strict=True)
        opt.load_state_dict(state["optimizer"])
        torch.set_rng_state(state["rng"])
        if device == "cuda":
            if "cuda_rng" not in state:
                raise ValueError("CUDA resume requires saved CUDA RNG; CPU checkpoint is incompatible")
            torch.cuda.set_rng_state(state["cuda_rng"], device=train_device)
        start = state["step"]
        best_nll = float(state.get('best_validation_nll', float('inf')))
        best_step = state.get('best_step', 0)
        if best_step and (not best_path.exists() or best_step > start):
            raise ValueError('Best checkpoint missing or inconsistent')
        if best_nll != best_nll or best_nll == float('-inf'):
            raise ValueError('Invalid best score')
        if type(start) is not int or start < 0 or start > total_steps:
            raise ValueError("Invalid checkpoint step")
    model.to(train_device)
    if device == "cuda":
        for group in opt.state.values():
            for key, value in group.items():
                if isinstance(value, torch.Tensor) and key != "step":
                    group[key] = value.to(train_device)
    def loss(pair):
        p, a = pair
        prefix = [1, 3] + bpe_encode(p, tokenizer) + [4]
        ids = prefix + bpe_encode(a, tokenizer) + [2]
        if len(ids) > context + 1:
            raise ValueError("Sequence exceeds configured context")
        x = torch.tensor([ids[:-1]], dtype=torch.long, device=train_device)
        y = torch.tensor([ids[1:]], dtype=torch.long, device=train_device)
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
    actual_steps = start
    stopped_for_budget = False
    for i in range(start, total_steps):
        if max_run_seconds is not None and i > start and time.monotonic() - started_at >= max_run_seconds:
            stopped_for_budget = True
            break
        model.train()
        opt.zero_grad(set_to_none=True)
        l = loss(train[i % len(train)])
        l.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
        opt.step()
        actual_steps = i + 1
        if (i + 1) % checkpoint_every == 0 or i + 1 == total_steps or (max_run_seconds is not None and time.monotonic() - started_at >= max_run_seconds):
            final_score = evaluate()
            improved = final_score < best_nll
            if improved:
                best_nll, best_step = final_score, i + 1
            payload = {"schema": "yorika-language-longrun-v1", "weights": model.state_dict(),
                       "optimizer": opt.state_dict(), "rng": torch.get_rng_state(),
                       "step": i + 1, "tokenizer": tokenizer, "vocab_size": vocab,
                       "train_sha256": fingerprint, "validation_sha256": digest(validation),
                       "best_validation_nll": best_nll, "best_step": best_step,
                       "config": [width, heads, layers, context, max_merges, seed],
                       "training_device": device}
            if device == "cuda":
                payload["cuda_rng"] = torch.cuda.get_rng_state(train_device)
            temp = path.with_name(path.name + ".incomplete")
            if temp.exists():
                temp.unlink()
            try:
                if device == "cuda":
                    torch.cuda.synchronize(train_device)
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
    elapsed = time.monotonic() - started_at
    return {"steps": actual_steps, "requested_steps": total_steps,
            "stopped_for_budget": stopped_for_budget or actual_steps < total_steps,
            "elapsed_seconds": elapsed,
            "steps_per_second": (actual_steps - start) / elapsed if elapsed > 0 else 0.0,
            "parameters": count, "validation_nll": final_score,
            "train_sha256": fingerprint, "tokenizer_sha256": tokenizer["sha256"],
            "checkpoint": str(path), "best_checkpoint": str(best_path),
            "best_validation_nll": best_nll, "best_step": best_step,
            "resumed_from": start, "device": str(train_device),
            "peak_cuda_allocated_bytes": (torch.cuda.max_memory_allocated(train_device) if device == "cuda" else None)}
