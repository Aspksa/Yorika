"""Continue training Yorika's one native Transformer from a trusted checkpoint.

Produces a *new* immutable checkpoint. The active brain is never switched.
"""
import hashlib
from pathlib import Path
from backend.neural_inference import validate_checkpoint
from backend.training_engine import train


def resume_training(examples, source, output, *, additional_steps=10, trainer=train):
    if type(additional_steps) is not int or not 1 <= additional_steps <= 10000:
        raise ValueError("additional_steps must be 1..10000")
    source, output = Path(source), Path(output)
    if not source.is_file() or not 0 < source.stat().st_size <= 100 * 1024 * 1024:
        raise ValueError("Trusted checkpoint missing or oversized")
    if output.exists() or source.resolve() == output.resolve():
        raise FileExistsError("Resume never overwrites source or existing checkpoints")
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("Optional PyTorch required") from exc
    data = torch.load(source, map_location="cpu", weights_only=True)
    config, vocab = validate_checkpoint(data)
    # Current trainer starts from random weights; it cannot resume safely.
    # Refuse rather than misrepresent a fresh run as continuation.
    raise NotImplementedError("Exact model and optimizer state restoration required for genuine resume")
