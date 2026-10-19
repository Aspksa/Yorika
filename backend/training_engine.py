"""Reproducible, opt-in tiny causal Transformer experiment.

PyTorch is an optional training dependency, not required by Yorika's base CI.
Only explicitly consented learning_examples are exported. No model promotion.
"""
import argparse
import json
import random
from pathlib import Path

from backend.storage import Store


def dataset(store, *, limit=5000):
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("Invalid dataset limit")
    records = store.list_records("learning_examples", limit=limit)
    examples = []
    for record in records:
        value = record["value"]
        if (value.get("consent") is True and isinstance(value.get("prompt"), str)
                and isinstance(value.get("answer"), str)
                and value["prompt"].strip() and value["answer"].strip()):
            examples.append((value["prompt"].strip(), value["answer"].strip()))
    return sorted(set(examples))


def train(examples, output, *, steps=10, seed=42, context=64, width=64, heads=4):
    if not examples:
        raise ValueError("No consented examples available")
    if any(type(x) is not int for x in (steps, seed, context, width, heads)):
        raise ValueError("Parameters must be integers")
    if not 1 <= steps <= 10000 or not 16 <= context <= 256 or not 16 <= width <= 256 or not 1 <= heads <= 8 or width % heads:
        raise ValueError("Invalid bounded training configuration")
    try:
        import torch
        from torch import nn
    except ImportError as exc:
        raise RuntimeError("Install optional PyTorch to train") from exc
    random.seed(seed)
    torch.manual_seed(seed)
    alphabet = sorted(set("".join(q + "\n" + a for q, a in examples)))
    vocab = ["<pad>", "<unk>"] + alphabet
    to_id = {symbol: i for i, symbol in enumerate(vocab)}
    sequences = []
    for prompt, answer in examples:
        text = prompt + "\n" + answer
        ids = [to_id[ch] for ch in text][:context + 1]
        if len(ids) >= 2:
            sequences.append(ids)
    if not sequences:
        raise ValueError("Training corpus contains no usable tokens")
    class TinyTransformer(nn.Module):
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
    model = TinyTransformer()
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001)
    losses = []
    for step in range(steps):
        ids = sequences[step % len(sequences)]
        inputs = torch.tensor([ids[:-1]])
        targets = torch.tensor([ids[1:]])
        optimizer.zero_grad()
        logits = model(inputs)
        loss = nn.functional.cross_entropy(logits.reshape(-1, len(vocab)), targets.reshape(-1))
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        losses.append(round(float(loss.detach()), 6))
    output = Path(output)
    if output.exists():
        raise FileExistsError("Never overwrite a training checkpoint")
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "vocab": vocab,
                "config": {"width": width, "heads": heads, "context": context, "seed": seed},
                "steps": steps, "examples": len(examples)}, output)
    return {"checkpoint": str(output), "examples": len(examples),
            "steps": steps, "initial_loss": losses[0], "final_loss": losses[-1]}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Yorika experimental Transformer trainer")
    parser.add_argument("--data-directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    with Store(args.data_directory) as store:
        samples = dataset(store)
    result = train(samples, args.output, steps=args.steps, seed=args.seed)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
