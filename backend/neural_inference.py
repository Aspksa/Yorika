"""Experimental inference for trusted, locally generated tiny Transformer checkpoints.

Requires optional PyTorch. Checkpoints must come from the user's own trusted
training run; never load downloaded or untrusted model files.
"""
from pathlib import Path


def validate_checkpoint(data):
    if not isinstance(data, dict) or set(data) != {"state_dict", "vocab", "config", "steps", "examples"}:
        raise ValueError("Unexpected checkpoint structure")
    vocab, config = data["vocab"], data["config"]
    if (not isinstance(vocab, list) or not 2 <= len(vocab) <= 4096
            or any(not isinstance(x, str) or len(x) > 12 for x in vocab)
            or len(set(vocab)) != len(vocab) or vocab[:2] != ["<pad>", "<unk>"]):
        raise ValueError("Invalid checkpoint vocabulary")
    if not isinstance(config, dict) or set(config) != {"width", "heads", "context", "seed"}:
        raise ValueError("Invalid checkpoint config")
    width, heads, context = (config[key] for key in ("width", "heads", "context"))
    if (any(type(x) is not int for x in (width, heads, context, config["seed"]))
            or not 16 <= width <= 256 or not 1 <= heads <= 8
            or width % heads or not 16 <= context <= 256):
        raise ValueError("Invalid checkpoint dimensions")
    if type(data["steps"]) is not int or data["steps"] < 1:
        raise ValueError("Invalid training steps")
    return config, vocab


def generate(checkpoint, prompt, *, max_tokens=32):
    if not isinstance(prompt, str) or not prompt or len(prompt) > 2000:
        raise ValueError("Invalid prompt")
    if type(max_tokens) is not int or not 1 <= max_tokens <= 256:
        raise ValueError("Invalid generation limit")
    checkpoint = Path(checkpoint)
    if not checkpoint.is_file() or checkpoint.stat().st_size > 100 * 1024 * 1024:
        raise ValueError("Checkpoint missing or too large")
    try:
        import torch
        from torch import nn
    except ImportError as exc:
        raise RuntimeError("Optional PyTorch is required for inference") from exc
    try:
        data = torch.load(checkpoint, map_location="cpu", weights_only=True)
    except Exception as exc:
        raise ValueError("Cannot load safe checkpoint") from exc
    config, vocab = validate_checkpoint(data)
    width, heads, context = (config[key] for key in ("width", "heads", "context"))
    class Model(nn.Module):
        def __init__(self):
            super().__init__()
            self.embedding = nn.Embedding(len(vocab), width)
            self.position = nn.Embedding(context, width)
            layer = nn.TransformerEncoderLayer(d_model=width, nhead=heads,
                                               dim_feedforward=width * 2,
                                               batch_first=True, dropout=0.0)
            self.encoder = nn.TransformerEncoder(layer, num_layers=2)
            self.output = nn.Linear(width, len(vocab))
        def forward(self, tokens):
            length = tokens.size(1)
            positions = torch.arange(length, device=tokens.device)
            hidden = self.embedding(tokens) + self.position(positions)
            mask = torch.triu(torch.ones(length, length, dtype=torch.bool, device=tokens.device), diagonal=1)
            return self.output(self.encoder(hidden, mask=mask))
    model = Model()
    model.load_state_dict(data["state_dict"], strict=True)
    model.eval()
    mapping = {symbol: index for index, symbol in enumerate(vocab)}
    tokens = [mapping.get(ch, 1) for ch in prompt][-context:]
    output = []
    with torch.inference_mode():
        for _ in range(max_tokens):
            inputs = torch.tensor([tokens[-context:]], dtype=torch.long)
            predictions = model(inputs)[0, -1]
            next_id = int(predictions.argmax().item())
            tokens.append(next_id)
            if next_id >= 2:
                output.append(vocab[next_id])
    return {"answer": "".join(output), "generated_tokens": max_tokens,
            "engine": "experimental-tiny-transformer"}
