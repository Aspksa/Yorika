"""From-scratch UTF-8 autoregressive dialogue Transformer, separate from legacy v0.

Training masks the user's prompt: loss measures assistant tokens only.
"""
import hashlib
import json
from pathlib import Path
from backend.neural_bpe_v1 import SPECIAL, OFFSET, train as train_bpe, encode as encode_bpe, decode as decode_bpe, validate as validate_bpe


ARCH_KEYS = ("lab", "loops", "experts", "memory")


def check_arch(arch):
    """Optional brain features; an empty dict is the original architecture, bit for bit.

    "lab" alone is the newer pre-norm network (it can grow); loops, experts and memory imply it.
    """
    arch = dict(arch or {})
    if set(arch) - set(ARCH_KEYS):
        raise ValueError("Unknown architecture option")
    loops, experts, memory = arch.get("loops", 1), arch.get("experts", 0), arch.get("memory", 0)
    if (type(loops) is not int or not 1 <= loops <= 4 or type(experts) is not int or experts not in (0, 2, 4, 6, 8)
            or type(memory) is not int or memory not in (0, 64, 128, 256, 512, 1024)
            or arch.get("lab", True) is not True):
        raise ValueError("Invalid architecture options")
    out = {k: v for k, v in (("loops", loops), ("experts", experts), ("memory", memory))
           if v != {"loops": 1, "experts": 0, "memory": 0}[k]}
    return dict(lab=True, **out) if out or arch.get("lab") else {}


def make_model(torch, *, vocab_size, width=64, heads=4, context=128, layers=2, arch=None):
    if type(vocab_size) is not int or not 261 <= vocab_size <= 4357:
        raise ValueError("Invalid BPE vocabulary size")
    from torch import nn
    if (any(type(x) is not int for x in (width, heads, context)) or
            not 16 <= width <= 1024 or not 1 <= heads <= 16 or width % heads or
            type(layers) is not int or not 1 <= layers <= 16 or
            not 32 <= context <= 512):
        raise ValueError("Invalid model configuration")
    arch = check_arch(arch)
    if arch:
        return _lab_model(torch, nn, vocab_size, width, heads, context, layers, arch)
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


def _lab_model(torch, nn, vocab_size, width, heads, context, layers, arch):
    """Pre-norm blocks with three optional brain features.

    loops: the block stack runs several times (shared weights); training samples 1..loops passes,
    so the same model can answer fast or think longer. experts: each block's feed-forward is a
    mixture of experts and every token uses the two its router picks. memory: a learned slot
    memory read by attention after the first block.
    Zero-initialised output projections make a new block an exact identity, which is what lets
    the brain grow deeper without losing what it learned (backend/growth.py).
    """
    from torch.nn import functional as F
    loops, experts, slots = arch.get("loops", 1), arch.get("experts", 0), arch.get("memory", 0)

    class Experts(nn.Module):
        def __init__(self):
            super().__init__()
            self.router = nn.Linear(width, experts, bias=False)
            self.up = nn.Parameter(torch.randn(experts, width, width * 2) * width ** -0.5)
            self.down = nn.Parameter(torch.zeros(experts, width * 2, width))

        def forward(self, x):
            logits = self.router(x)
            weights, chosen = logits.topk(2, dim=-1)
            weights = weights.softmax(-1)
            # Balance term (Switch Transformer): keeps every expert in use instead of two winners.
            share = F.one_hot(chosen[..., 0], experts).float().reshape(-1, experts).mean(0)
            self.aux = experts * (share * logits.softmax(-1).reshape(-1, experts).mean(0)).sum()
            if getattr(self, "trace", None) is not None:
                # Introspection: how often each expert is picked.
                self.trace += F.one_hot(chosen, experts).float().reshape(-1, experts).sum(0).detach().cpu()
            out = torch.zeros_like(x)
            for slot in range(2):
                for e in range(experts):
                    hit = chosen[..., slot] == e
                    if hit.any():
                        h = F.gelu(x[hit] @ self.up[e]) @ self.down[e]
                        out[hit] += weights[..., slot][hit].unsqueeze(-1) * h
            return out

    class Block(nn.Module):
        def __init__(self):
            super().__init__()
            self.norm1, self.norm2 = nn.LayerNorm(width), nn.LayerNorm(width)
            self.attn = nn.MultiheadAttention(width, heads, batch_first=True, bias=False)
            nn.init.zeros_(self.attn.out_proj.weight)
            if experts:
                self.ffn = Experts()
            else:
                self.ffn = nn.Sequential(nn.Linear(width, width * 4), nn.GELU(), nn.Linear(width * 4, width))
                nn.init.zeros_(self.ffn[2].weight)
                nn.init.zeros_(self.ffn[2].bias)

        def forward(self, x, mask):
            h = self.norm1(x)
            x = x + self.attn(h, h, h, attn_mask=mask, need_weights=False)[0]
            return x + self.ffn(self.norm2(x))

    class Memory(nn.Module):
        def __init__(self):
            super().__init__()
            self.norm = nn.LayerNorm(width)
            self.keys = nn.Parameter(torch.randn(slots, width) * width ** -0.5)
            self.values = nn.Parameter(torch.zeros(slots, width))

        def forward(self, x):
            scores = (self.norm(x) @ self.keys.t() * width ** -0.5).softmax(-1)
            if getattr(self, "trace", None) is not None:
                # Introspection: how much attention each memory slot receives.
                self.trace += scores.reshape(-1, slots).sum(0).detach().cpu()
            return x + scores @ self.values

    class LabBrain(nn.Module):
        def __init__(self):
            super().__init__()
            self.embedding = nn.Embedding(vocab_size, width)
            self.position = nn.Embedding(context, width)
            self.blocks = nn.ModuleList(Block() for _ in range(layers))
            if loops > 1:
                self.loop = nn.Embedding(loops, width)
                nn.init.zeros_(self.loop.weight)
            if slots:
                self.memory = Memory()
            self.norm = nn.LayerNorm(width)
            self.output = nn.Linear(width, vocab_size)
            self.passes = loops
            # Introspection switches blocks off one at a time to measure what each one does.
            self.skip = set()

        def forward(self, ids, passes=None):
            length = ids.shape[1]
            if length > context:
                raise ValueError("Context overflow")
            if passes is None:
                passes = int(torch.randint(1, loops + 1, ()).item()) if self.training and loops > 1 else self.passes
            p = torch.arange(length, device=ids.device)
            mask = torch.triu(torch.ones(length, length, dtype=torch.bool, device=ids.device), diagonal=1)
            x = self.embedding(ids) + self.position(p)
            for n in range(max(1, min(passes, loops))):
                if loops > 1:
                    x = x + self.loop.weight[n]
                for k, block in enumerate(self.blocks):
                    if k not in self.skip:
                        x = block(x, mask)
                    # Memory is read right after the first block, so growing deeper never moves it.
                    if slots and k == 0:
                        x = self.memory(x)
            self.aux_loss = sum(b.ffn.aux for b in self.blocks) / len(self.blocks) if experts else None
            return self.output(self.norm(x))

    return LabBrain()


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
