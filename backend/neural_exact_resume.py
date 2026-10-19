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
    return train(examples, output, steps=additional_steps,
                 source_checkpoint=source, exact_resume=True)
