"""From-scratch UTF-8 autoregressive dialogue Transformer, separate from legacy v0.

Training masks the user's prompt: loss measures assistant tokens only.
"""
import hashlib
import json
from pathlib import Path
from backend.neural_bpe_v1 import SPECIAL, OFFSET, train as train_bpe, encode as encode_bpe, decode as decode_bpe, validate as validate_bpe


def make_model(torch, *, vocab_size, width=64, heads=4, context=128, layers=2):
    if type(vocab_size) is not int or not 261 <= vocab_size <= 4357:
        raise ValueError("Invalid BPE vocabulary size")
    from torch import nn
    if (any(type(x) is not int for x in (width, heads, context)) or
            not 16 <= width <= 1024 or not 1 <= heads <= 16 or width % heads or
            type(layers) is not int or not 1 <= layers <= 16 or
            not 32 <= context <= 512):
        raise ValueError("Invalid model configuration")
    class LanguageBrain(nn.Module):
        def __init__(self):
            super().__init__()
            self.embedding = nn.Embedding(vocab_size, width)
            self.position = nn.Embedding(context, width)
            layer = nn.TransformerEncoderLayer(
                d_model=width, nhead=heads, dim_feedforward=width*4,
                dropout=0.0, batch_first=True)
            self.encoder = nn.TransformerEncoder(layer, num_layers=layers)
            self.output = nn.Linear(width, vocab_size)
        def forward(self, ids):
            length = ids.shape[1]
            if length > context:
                raise ValueError("Context overflow")
            p = torch.arange(length, device=ids.device)
            mask = torch.triu(torch.ones(length, length, dtype=torch.bool, device=ids.device), diagonal=1)
            return self.output(self.encoder(self.embedding(ids)+self.position(p), mask=mask))
    return LanguageBrain()


def train_language(pairs, output, *, steps=10, seed=42, width=64, heads=4, context=128, max_merges=64, layers=2):
    if type(steps) is not int or not 1 <= steps <= 10000 or type(seed) is not int:
        raise ValueError("Invalid training budget")
    if not isinstance(pairs, (list, tuple)) or not pairs:
        raise ValueError("Empty corpus")
    for prompt, answer in pairs:
        if (not isinstance(prompt, str) or not isinstance(answer, str) or
                not prompt.strip() or not answer.strip() or len(prompt) > 2000 or len(answer) > 2000):
            raise ValueError("Invalid consented dialogue")
    import torch
    from torch.nn import functional as F
    output = Path(output)
    if output.exists():
        raise FileExistsError("Checkpoint already exists")
    # Only supplied training examples are used to fit BPE; evaluation data must stay external.
    tokenizer = train_bpe([text for prompt, answer in pairs for text in (prompt, answer)], max_merges=max_merges)
    vocab_size = OFFSET + 256 + len(tokenizer["merges"])
    torch.manual_seed(seed)
    model = make_model(torch, vocab_size=vocab_size, width=width, heads=heads, context=context, layers=layers)
    optim = torch.optim.AdamW(model.parameters(), lr=0.001)
    losses = []
    for step in range(steps):
        prompt, answer = pairs[step % len(pairs)]
        ids = [1, 3] + encode_bpe(prompt, tokenizer) + [4] + encode_bpe(answer, tokenizer) + [2]
        prefix = 3 + len(encode_bpe(prompt, tokenizer))
        if len(ids) > context + 1:
            raise ValueError("Dialogue exceeds context; shorten or increase context")
        x = torch.tensor([ids[:-1]], dtype=torch.long)
        y = torch.tensor([ids[1:]], dtype=torch.long)
        # First answer token has target index prefix-1.
        y[:, :prefix-1] = -100
        optim.zero_grad()
        logits = model(x)
        loss = F.cross_entropy(logits.reshape(-1, vocab_size), y.reshape(-1), ignore_index=-100)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
        optim.step()
        losses.append(float(loss.detach()))
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"schema": "yorika-language-bpe-v2", "weights": model.state_dict(),
                "width": width, "heads": heads, "context": context, "layers": layers,
                "tokenizer": tokenizer, "vocab_size": vocab_size, "steps": steps}, output)
    return {"steps": steps, "train_initial_loss": losses[0], "train_final_loss": losses[-1],
            "parameters": sum(p.numel() for p in model.parameters())}


def load_language(checkpoint):
    import torch
    path = Path(checkpoint)
    if not path.is_file() or not 0 < path.stat().st_size <= 100_000_000:
        raise ValueError("Missing or oversized checkpoint")
    data = torch.load(path, weights_only=True, map_location="cpu")
    if (not isinstance(data, dict) or data.get("schema") != "yorika-language-bpe-v2"):
        raise ValueError("Unsupported language checkpoint")
    validate_bpe(data.get("tokenizer"))
    expected_vocab = OFFSET + 256 + len(data["tokenizer"]["merges"])
    if data.get("vocab_size") != expected_vocab:
        raise ValueError("Checkpoint/tokenizer vocabulary mismatch")
    model = make_model(torch, vocab_size=expected_vocab, width=data["width"], heads=data["heads"], context=data["context"], layers=data.get("layers", 2))
    model.load_state_dict(data["weights"], strict=True)
    model.eval()
    return model, data


def heldout_loss(checkpoint, pairs):
    import torch
    from torch.nn import functional as F
    model, cfg = load_language(checkpoint)
    if not pairs:
        raise ValueError("Heldout pairs required")
    vocab_size = cfg["vocab_size"]
    tokenizer = cfg["tokenizer"]
    scores = []
    with torch.inference_mode():
        for prompt, answer in pairs:
            ids = [1, 3] + encode_bpe(prompt, tokenizer) + [4] + encode_bpe(answer, tokenizer) + [2]
            prefix = 3 + len(encode_bpe(prompt, tokenizer))
            if len(ids) > cfg["context"] + 1:
                raise ValueError("Heldout sequence exceeds model context")
            x = torch.tensor([ids[:-1]])
            labels = torch.tensor([ids[1:]])
            labels[:, :prefix-1] = -100
            logits = model(x)
            scores.append(float(F.cross_entropy(logits.reshape(-1, vocab_size),
                                                labels.reshape(-1), ignore_index=-100)))
    return sum(scores)/len(scores)


def generate_language(checkpoint, prompt, *, max_tokens=32):
    import torch
    if not isinstance(prompt, str) or not prompt or len(prompt) > 2000:
        raise ValueError("Invalid prompt")
    if type(max_tokens) is not int or not 1 <= max_tokens <= 256:
        raise ValueError("Invalid token count")
    model, cfg = load_language(checkpoint)
    tokenizer = cfg["tokenizer"]
    ids = [1, 3] + encode_bpe(prompt, tokenizer) + [4]
    generated = []
    with torch.inference_mode():
        for _ in range(max_tokens):
            x = torch.tensor([ids[-cfg["context"]:]], dtype=torch.long)
            token = int(model(x)[0, -1].argmax())
            if token == 2:
                break
            ids.append(token)
            if token >= len(SPECIAL):
                generated.append(token)
    # Generated sequence may end mid UTF-8 codepoint; keep replacements visible.
    return {"answer": _decode_generated(generated, tokenizer),
            "generated_tokens": len(generated), "engine": "yorika-language-bpe-v2"}


def _decode_generated(tokens, tokenizer):
    # Full UTF-8 sequences are lossless; incomplete sampled fragments are replaced.
    expansions = [bytes([i]) for i in range(256)]
    for left, right in tokenizer["merges"]:
        expansions.append(expansions[left - OFFSET] + expansions[right - OFFSET])
    return b"".join(expansions[t - OFFSET] for t in tokens).decode("utf-8", errors="replace")
