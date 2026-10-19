"""Bounded resumable training of one BPE dialogue model; no auto-promotion.

Speed knobs (batch_size, accumulate, precision) change how many examples one optimizer
step sees, not the model. objective="lm" pretrains on plain texts; init_from starts a
dialogue run from such a pretrained checkpoint with its tokenizer.
"""
import hashlib
import json
import time
from pathlib import Path
from backend.neural_bpe_v1 import OFFSET, train as fit_bpe, encode as bpe_encode, validate as check_bpe
from backend.neural_language_bpe_v2 import make_model

SCHEMA = "yorika-language-longrun-v1"
PRECISIONS = ("fp32", "bf16", "fp16")
BPE_SAMPLE_CHARS = 2_000_000


_ENCODED = {}


class _LazyRows:
    """Dialogue examples encoded on first use, so a short chunk does not re-encode the corpus."""
    def __init__(self, examples, encode, context):
        self.examples, self.encode, self.context, self.rows = list(examples), encode, context, {}

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[k] for k in range(*index.indices(len(self)))]
        if index not in self.rows:
            ids, masked = self.encode(self.examples[index])
            if len(ids) > self.context + 1:
                raise ValueError("Sequence exceeds configured context")
            self.rows[index] = (ids, masked)
        return self.rows[index]


def digest(pairs):
    return hashlib.sha256(json.dumps(pairs, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def run(train, validation, output, *, total_steps, checkpoint_every=20,
        width=320, heads=8, layers=4, context=256, max_merges=128, seed=42,
        max_run_seconds=None, device='cpu', batch_size=1, accumulate=1, precision="fp32",
        objective="dialogue", init_from=None):
    import torch
    from torch.nn import functional as F
    if max_run_seconds is not None and (type(max_run_seconds) not in (int, float) or
            not 0 < max_run_seconds <= 86400):
        raise ValueError("Invalid run time budget")
    if device not in ("cpu", "cuda"):
        raise ValueError("Unsupported training device")
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA required but unavailable; no CPU fallback")
    if (type(batch_size) is not int or not 1 <= batch_size <= 256 or
            type(accumulate) is not int or not 1 <= accumulate <= 64):
        raise ValueError("Invalid batch configuration")
    if precision not in PRECISIONS or (precision != "fp32" and device != "cuda"):
        raise ValueError("Half precision requires CUDA")
    if objective not in ("dialogue", "lm"):
        raise ValueError("Unknown training objective")
    train_device = torch.device(device)
    started_at = time.monotonic()
    if (not isinstance(train, (list, tuple)) or not train or
            not isinstance(validation, (list, tuple)) or not validation):
        raise ValueError("Disjoint train and validation splits required")
    lm = objective == "lm"
    if lm:
        if any(not isinstance(t, str) or not t.strip() for t in list(train) + list(validation)):
            raise ValueError("Invalid texts")
        if set(t.strip() for t in train) & set(t.strip() for t in validation):
            raise ValueError("Train/validation text leakage")
    elif set(p.casefold().strip() for p, _ in train) & set(p.casefold().strip() for p, _ in validation):
        raise ValueError("Train/validation prompt leakage")
    if (type(total_steps) is not int or not 1 <= total_steps <= 1000000 or
            type(checkpoint_every) is not int or not 1 <= checkpoint_every <= 10000):
        raise ValueError("Invalid bounded training schedule")
    if not lm and any(not isinstance(p, str) or not isinstance(a, str) or not p or not a
                      for p, a in list(train) + list(validation)):
        raise ValueError("Invalid examples")
    speed = [batch_size, accumulate, precision]
    base = None
    if init_from is not None:
        base_path = Path(init_from)
        if not base_path.is_file() or not 0 < base_path.stat().st_size <= 200_000_000:
            raise ValueError("Missing pretrained checkpoint")
        base = torch.load(base_path, map_location="cpu", weights_only=True)
        if (base.get("schema") != SCHEMA or base.get("objective") != "lm" or
                base.get("config", [None]*6)[:4] != [width, heads, layers, context]):
            raise ValueError("Pretrained checkpoint does not match this model")
        check_bpe(base["tokenizer"])
        base_sha = hashlib.sha256(base_path.read_bytes()).hexdigest()
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    fingerprint = digest(train)
    if path.exists():
        if not 0 < path.stat().st_size <= 200_000_000:
            raise ValueError("Invalid checkpoint size")
        state = torch.load(path, map_location="cpu", weights_only=True)
        if (state.get("schema") != SCHEMA or
                state.get('validation_sha256', digest(validation)) != digest(validation) or
                state.get("train_sha256") != fingerprint or state.get("config") !=
                [width, heads, layers, context, max_merges, seed] or
                state.get("speed", [1, 1, "fp32"]) != speed or
                state.get("objective", "dialogue") != objective or
                state.get("init_sha256") != (base_sha if base else None)):
            raise ValueError("Checkpoint incompatible with current experiment")
        tokenizer = state["tokenizer"]
        check_bpe(tokenizer)
    elif base:
        tokenizer = base["tokenizer"]
        state = None
    else:
        texts = list(train) if lm else [s for pair in train for s in pair]
        sample, size = [], 0
        for text in texts:
            # Pure-Python BPE is slow on big corpora; a bounded sample keeps fitting to minutes.
            if size >= BPE_SAMPLE_CHARS or len(sample) >= 100000:
                break
            sample.append(text[:20000])
            size += len(sample[-1])
        tokenizer = fit_bpe(sample, max_merges=max_merges)
        state = None
    vocab = OFFSET + 256 + len(tokenizer["merges"])
    torch.manual_seed(seed)
    model = make_model(torch, vocab_size=vocab, width=width, heads=heads, layers=layers, context=context)
    count = sum(p.numel() for p in model.parameters())
    if base and not state:
        if base.get("vocab_size") != vocab:
            raise ValueError("Vocab mismatch")
        model.load_state_dict(base["weights"], strict=True)
    opt = torch.optim.AdamW(model.parameters(), lr=0.0003)
    half = {"bf16": torch.bfloat16, "fp16": torch.float16}.get(precision)
    scaler = torch.amp.GradScaler("cuda") if precision == "fp16" else None
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
        if scaler is not None and state.get("scaler"):
            scaler.load_state_dict(state["scaler"])
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
    def encode(example):
        if lm:
            return [1] + bpe_encode(example, tokenizer) + [2], 0
        p, a = example
        prefix = [1, 3] + bpe_encode(p, tokenizer) + [4]
        return prefix + bpe_encode(a, tokenizer) + [2], len(prefix) - 1
    def prepare(examples, name):
        # The worker resumes in short chunks inside one process; encoding is kept between them.
        key = (name, digest(examples) if not lm else digest(list(examples)), tokenizer["sha256"], objective, context)
        if key in _ENCODED:
            return _ENCODED[key]
        if not lm:
            rows = _LazyRows(examples, encode, context)
        else:
            rows = []
            for example in examples:
                ids, _ = encode(example)
                # Plain texts are cut into context-sized windows that overlap by one token.
                for begin in range(0, max(1, len(ids) - 1), context):
                    window = ids[begin:begin + context + 1]
                    if len(window) >= 2:
                        rows.append((window, 0))
            if not rows:
                raise ValueError("No trainable sequences")
        _ENCODED.clear() if len(_ENCODED) > 8 else None
        _ENCODED[key] = rows
        return rows
    train_rows, valid_rows = prepare(train, "train"), prepare(validation, "validation")
    def batch_loss(rows):
        # Pads go after each sequence, so the causal mask keeps them invisible; they carry no loss.
        width_ = max(len(ids) for ids, _ in rows) - 1
        x = torch.zeros((len(rows), width_), dtype=torch.long)
        y = torch.full((len(rows), width_), -100, dtype=torch.long)
        for k, (ids, masked) in enumerate(rows):
            n = len(ids) - 1
            x[k, :n] = torch.tensor(ids[:-1])
            y[k, :n] = torch.tensor(ids[1:])
            y[k, :masked] = -100
        x, y = x.to(train_device), y.to(train_device)
        with torch.autocast(device_type="cuda", dtype=half, enabled=half is not None):
            logits = model(x)
        per_token = F.cross_entropy(logits.float().reshape(-1, vocab), y.reshape(-1),
                                    ignore_index=-100, reduction="none").reshape(y.shape)
        counted = (y != -100).sum(1).clamp(min=1)
        # Mean per example, then over the batch: same metric as one example at a time.
        return (per_token.sum(1) / counted).mean()
    def evaluate():
        model.eval()
        with torch.inference_mode():
            total = 0.0
            for k in range(0, len(valid_rows), max(batch_size, 8)):
                part = valid_rows[k:k + max(batch_size, 8)]
                total += float(batch_loss(part)) * len(part)
            score = total / len(valid_rows)
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
        for part in range(accumulate):
            first = (i * accumulate + part) * batch_size
            rows = [train_rows[(first + k) % len(train_rows)] for k in range(batch_size)]
            l = batch_loss(rows) / accumulate
            (scaler.scale(l) if scaler else l).backward()
        if scaler:
            scaler.unscale_(opt)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
        if scaler:
            scaler.step(opt)
            scaler.update()
        else:
            opt.step()
        actual_steps = i + 1
        if (i + 1) % checkpoint_every == 0 or i + 1 == total_steps or (max_run_seconds is not None and time.monotonic() - started_at >= max_run_seconds):
            final_score = evaluate()
            improved = final_score < best_nll
            if improved:
                best_nll, best_step = final_score, i + 1
            payload = {"schema": SCHEMA, "weights": model.state_dict(),
                       "optimizer": opt.state_dict(), "rng": torch.get_rng_state(),
                       "step": i + 1, "tokenizer": tokenizer, "vocab_size": vocab,
                       "train_sha256": fingerprint, "validation_sha256": digest(validation),
                       "best_validation_nll": best_nll, "best_step": best_step,
                       "config": [width, heads, layers, context, max_merges, seed],
                       "training_device": device, "speed": speed, "objective": objective,
                       "init_sha256": base_sha if base else None}
            if scaler is not None:
                payload["scaler"] = scaler.state_dict()
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
            "examples_per_second": (actual_steps - start) * batch_size * accumulate / elapsed if elapsed > 0 else 0.0,
            "parameters": count, "validation_nll": final_score,
            "train_sha256": fingerprint, "tokenizer_sha256": tokenizer["sha256"],
            "checkpoint": str(path), "best_checkpoint": str(best_path),
            "best_validation_nll": best_nll, "best_step": best_step,
            "resumed_from": start, "device": str(train_device),
            "peak_cuda_allocated_bytes": (torch.cuda.max_memory_allocated(train_device) if device == "cuda" else None)}


def score_checkpoint(checkpoint, examples, *, objective="dialogue", limit=2000):
    """Mean per-example loss of a saved checkpoint on examples it never trained on (the exam)."""
    import torch
    from torch.nn import functional as F
    from backend.neural_language_benchmark import load_candidate
    model, state = load_candidate(checkpoint)
    tokenizer, context = state["tokenizer"], state["config"][3]
    scores = []
    with torch.inference_mode():
        for example in list(examples)[:limit]:
            if objective == "lm":
                ids, masked = [1] + bpe_encode(example, tokenizer)[:context] + [2], 0
            else:
                prefix = [1, 3] + bpe_encode(example[0], tokenizer) + [4]
                ids, masked = prefix + bpe_encode(example[1], tokenizer) + [2], len(prefix) - 1
            ids = ids[:context + 1]
            if len(ids) - 1 <= masked:
                continue
            y = torch.tensor([ids[1:]])
            y[:, :masked] = -100
            logits = model(torch.tensor([ids[:-1]]))
            scores.append(float(F.cross_entropy(logits.reshape(-1, logits.shape[-1]), y.reshape(-1),
                                                ignore_index=-100)))
    if not scores:
        raise ValueError("No exam examples fit the model context")
    return sum(scores) / len(scores), len(scores)
