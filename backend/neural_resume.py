"""Continue from saved weights into a new checkpoint, without changing active brain.

This is weight continuation, not exact optimizer-state resume: AdamW moments reset.
"""
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
        raise FileExistsError("Never overwrite weights on continuation")
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("Optional PyTorch required") from exc
    loaded = torch.load(source, map_location="cpu", weights_only=True)
    config, vocab = validate_checkpoint(loaded)
    return trainer(examples, output, steps=additional_steps, seed=config["seed"],
                   width=config["width"], heads=config["heads"], context=config["context"],
                   source_checkpoint=source)
