"""Independent, read-only language checkpoint evaluation (no model promotion).

Candidates must use the same tokenizer and identical locked test set. Reports
exclude the dialogue content and never overwrite previous evaluation evidence.
"""
import hashlib
import json
import math
from pathlib import Path

from backend.neural_bpe_v1 import OFFSET, encode as bpe_encode, validate as check_bpe
from backend.neural_language_bpe_v2 import make_model

SCHEMA = "yorika-independent-eval-v1"
CHECKPOINT_SCHEMA = "yorika-language-longrun-v1"


def fingerprint(pairs):
    payload = json.dumps(pairs, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_candidate(path):
    import torch
    path = Path(path)
    if not path.is_file() or not 0 < path.stat().st_size <= 200_000_000:
        raise ValueError("Missing or oversized checkpoint")
    state = torch.load(path, weights_only=True, map_location="cpu")
    if not isinstance(state, dict) or state.get("schema") != CHECKPOINT_SCHEMA:
        raise ValueError("Wrong checkpoint format")
    tokenizer = state.get("tokenizer")
    check_bpe(tokenizer)
    config = state.get("config")
    if not isinstance(config, list) or len(config) != 6:
        raise ValueError("Invalid architecture configuration")
    width, heads, layers, context, _, _ = config
    vocab = OFFSET + 256 + len(tokenizer["merges"])
    if state.get("vocab_size") != vocab:
        raise ValueError("Vocabulary mismatch")
    model = make_model(torch, vocab_size=vocab, width=width, heads=heads,
                       layers=layers, context=context)
    model.load_state_dict(state["weights"], strict=True)
    model.eval()
    return model, state


def score(model, state, pairs):
    import torch
    from torch.nn import functional as F
    config = state["config"]
    context = config[3]
    vocab = state["vocab_size"]
    tokenizer = state["tokenizer"]
    total_nll, total_tokens = 0.0, 0
    with torch.inference_mode():
        for prompt, answer in pairs:
            prefix = [1, 3] + bpe_encode(prompt, tokenizer) + [4]
            sequence = prefix + bpe_encode(answer, tokenizer) + [2]
            if len(sequence) > context + 1:
                raise ValueError("Test dialogue longer than context")
            x = torch.tensor([sequence[:-1]], dtype=torch.long)
            y = torch.tensor([sequence[1:]], dtype=torch.long)
            y[:, :len(prefix)-1] = -100
            count = int((y != -100).sum().item())
            logits = model(x)
            nll_sum = F.cross_entropy(logits.reshape(-1, vocab), y.reshape(-1),
                                      ignore_index=-100, reduction="sum")
            total_nll += float(nll_sum)
            total_tokens += count
    if total_tokens == 0 or not math.isfinite(total_nll):
        raise ValueError("Invalid evaluation score")
    nll = total_nll / total_tokens
    return {"tokens": total_tokens, "nll": nll, "perplexity": math.exp(min(nll, 100))}


def compare(baseline, candidate, test_pairs, *, expected_test_sha256, report_path=None):
    if (not isinstance(test_pairs, (list, tuple)) or not test_pairs or
            any(not isinstance(pair, (list, tuple)) or len(pair) != 2 or
                any(not isinstance(s, str) or not s.strip() for s in pair)
                for pair in test_pairs)):
        raise ValueError("Nonempty independent test pairs required")
    pairs = [tuple(pair) for pair in test_pairs]
    test_hash = fingerprint(pairs)
    if test_hash != expected_test_sha256:
        raise ValueError("Independent test set fingerprint mismatch")
    base_model, base_state = load_candidate(baseline)
    cand_model, cand_state = load_candidate(candidate)
    if (base_state["tokenizer"]["sha256"] != cand_state["tokenizer"]["sha256"]
            or base_state["vocab_size"] != cand_state["vocab_size"]):
        raise ValueError("Tokenizers differ: token NLL would not be comparable")
    if test_hash in {base_state.get("train_sha256"), cand_state.get("train_sha256")}:
        raise ValueError("Test corpus collides with training corpus")
    b = score(base_model, base_state, pairs)
    c = score(cand_model, cand_state, pairs)
    report = {"schema": SCHEMA, "test_sha256": test_hash, "test_count": len(pairs),
              "tokenizer_sha256": base_state["tokenizer"]["sha256"],
              "baseline": b, "candidate": c, "delta_nll": c["nll"] - b["nll"],
              "improved_test_nll": c["nll"] < b["nll"],
              "caveat": "One independent test score is not proof of general dialogue improvement"}
    if report_path is not None:
        dest = Path(report_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
    return report
