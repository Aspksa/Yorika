"""Exact CPU continuation for trusted Yorika checkpoints.

Versioned training state is separate from inference checkpoints; no auto-promotion.
"""
import hashlib
import json
from pathlib import Path
from backend.training_engine import train


def data_hash(examples):
    encoded = json.dumps(examples, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def exact_resume(examples, source, output, *, additional_steps):
    if type(additional_steps) is not int or not 1 <= additional_steps <= 10000:
        raise ValueError("Invalid additional steps")
    import torch
    file = Path(source)
    if not file.is_file() or file.stat().st_size > 100 * 1024 * 1024:
        raise ValueError("Trusted checkpoint missing or oversized")
    saved = torch.load(file, map_location="cpu", weights_only=True)
    from backend.neural_inference import validate_checkpoint
    config, _ = validate_checkpoint({key: saved[key] for key in ("state_dict", "vocab", "config", "steps", "examples")})
    return train(examples, output, steps=additional_steps,
                 seed=config["seed"], width=config["width"], heads=config["heads"],
                 context=config["context"], source_checkpoint=source, exact_resume=True)
