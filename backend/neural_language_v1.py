"""From-scratch UTF-8 autoregressive dialogue Transformer, separate from legacy v0.

Training masks the user's prompt: loss measures assistant tokens only.
"""
import hashlib
import json
from pathlib import Path
from backend.neural_tokenizer_v1 import SPECIAL, VOCAB_SIZE, encode, decode, encode_dialogue, fingerprint


def make_model(torch, *, width=64, heads=4, context=128):
    from torch import nn
    if (any(type(x) is not int for x in (width, heads, context)) or
            not 16 <= width <= 256 or not 1 <= heads <= 8 or width % heads or
            not 32 <= context <= 512):
        raise ValueError("Invalid model configuration")
    class LanguageBrain(nn.Module):
        def __init__(self):
            super().__init__()
            self.embedding = nn.Embedding(VOCAB_SIZE, width)
            self.position = nn.Embedding(context, width)
            layer = nn.TransformerEncoderLayer(
                d_model=width, nhead=heads, dim_feedforward=width*4,
                dropout=0.0, batch_first=True)
            self.encoder = nn.TransformerEncoder(layer, num_layers=2)
            self.output = nn.Linear(width, VOCAB_SIZE)
        def forward(self, ids):
            length = ids.shape[1]
            if length > context:
                raise ValueError("Context overflow")
            p = torch.arange(length, device=ids.device)
            mask = torch.triu(torch.ones(length, length, dtype=torch.bool, device=ids.device), diagonal=1)
            return self.output(self.encoder(self.embedding(ids)+self.position(p), mask=mask))
    return LanguageBrain()


def train_language(pairs, output, *, steps=10, seed=42, width=64, heads=4, context=128):
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
    torch.manual_seed(seed)
    model = make_model(torch, width=width, heads=heads, context=context)
    optim = torch.optim.AdamW(model.parameters(), lr=0.001)
    losses = []
    for step in range(steps):
        prompt, answer = pairs[step % len(pairs)]
        ids = encode_dialogue(prompt, answer)
        prefix = 2 + len(encode(prompt)) + 1
        if len(ids) > context + 1:
            raise ValueError("Dialogue exceeds context; shorten or increase context")
        x = torch.tensor([ids[:-1]], dtype=torch.long)
        y = torch.tensor([ids[1:]], dtype=torch.long)
        # First answer token has target index prefix-1.
        y[:, :prefix-1] = -100
        optim.zero_grad()
        logits = model(x)
        loss = F.cross_entropy(logits.reshape(-1, VOCAB_SIZE), y.reshape(-1), ignore_index=-100)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
        optim.step()
        losses.append(float(loss.detach()))
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"schema": "yorika-language-v1", "weights": model.state_dict(),
                "width": width, "heads": heads, "context": context,
                "tokenizer_sha256": fingerprint(), "steps": steps}, output)
    return {"steps": steps, "train_initial_loss": losses[0], "train_final_loss": losses[-1],
            "parameters": sum(p.numel() for p in model.parameters())}


def load_language(checkpoint):
    import torch
    path = Path(checkpoint)
    if not path.is_file() or not 0 < path.stat().st_size <= 100_000_000:
        raise ValueError("Missing or oversized checkpoint")
    data = torch.load(path, weights_only=True, map_location="cpu")
    if (not isinstance(data, dict) or data.get("schema") != "yorika-language-v1" or
            data.get("tokenizer_sha256") != fingerprint()):
        raise ValueError("Unsupported language checkpoint")
    model = make_model(torch, width=data["width"], heads=data["heads"], context=data["context"])
    model.load_state_dict(data["weights"], strict=True)
    model.eval()
    return model, data


def heldout_loss(checkpoint, pairs):
    import torch
    from torch.nn import functional as F
    model, cfg = load_language(checkpoint)
    scores = []
    with torch.inference_mode():
        for prompt, answer in pairs:
            ids = encode_dialogue(prompt, answer)
            prefix = 3 + len(encode(prompt))
            if len(ids) > cfg["context"] + 1:
                raise ValueError("Heldout sequence exceeds model context")
            x = torch.tensor([ids[:-1]])
            labels = torch.tensor([ids[1:]])
            labels[:, :prefix-1] = -100
            logits = model(x)
            scores.append(float(F.cross_entropy(logits.reshape(-1, VOCAB_SIZE),
                                                labels.reshape(-1), ignore_index=-100)))
    return sum(scores)/len(scores)


def generate_language(checkpoint, prompt, *, max_tokens=32):
    import torch
    if not isinstance(prompt, str) or not prompt or len(prompt) > 2000:
        raise ValueError("Invalid prompt")
    if type(max_tokens) is not int or not 1 <= max_tokens <= 256:
        raise ValueError("Invalid token count")
    model, cfg = load_language(checkpoint)
    ids = [1, 3] + encode(prompt) + [4]
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
    return {"answer": bytes(t-len(SPECIAL) for t in generated).decode("utf-8", errors="replace"),
            "generated_tokens": len(generated), "engine": "yorika-language-v1"}
