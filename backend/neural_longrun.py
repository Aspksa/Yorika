"""Crash-recoverable bounded CPU training for Yorika's single brain.

Checkpoints are immutable, and the active-brain pointer is never changed.
"""
import hashlib
import json
import os
import time
from pathlib import Path

from backend.neural_exact_resume import exact_resume
from backend.training_engine import train


def run_long_training(examples, directory, *, total_steps, interval=10, max_seconds=3600,
                      max_checkpoint_bytes=100_000_000, seed=42, context=32, width=32,
                      heads=4, trainer=train, resumer=exact_resume, clock=time.monotonic):
    if type(total_steps) is not int or not 1 <= total_steps <= 10000:
        raise ValueError("Invalid total_steps")
    if type(interval) is not int or not 1 <= interval <= total_steps:
        raise ValueError("Invalid interval")
    if type(max_seconds) not in (int, float) or not 1 <= max_seconds <= 86400:
        raise ValueError("Invalid runtime budget")
    if type(max_checkpoint_bytes) is not int or not 1024 <= max_checkpoint_bytes <= 100_000_000:
        raise ValueError("Invalid checkpoint budget")
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    manifest = root / "training-progress.json"
    if manifest.exists():
        info = json.loads(manifest.read_text(encoding="utf-8"))
        if info.get("schema") != 1 or info.get("total_steps") != total_steps or info.get("interval") != interval:
            raise ValueError("Progress configuration changed")
        completed = info["completed_steps"]
        source = root / info["checkpoint"]
        if (type(completed) is not int or not 1 <= completed <= total_steps or not source.is_file()
                or hashlib.sha256(source.read_bytes()).hexdigest() != info["checkpoint_sha256"]):
            raise ValueError("Untrusted or damaged checkpoint")
    else:
        completed, source = 0, None
    started = clock()
    while completed < total_steps:
        if clock() - started >= max_seconds:
            break
        advance = min(interval, total_steps - completed)
        next_step = completed + advance
        output = root / f"step-{next_step:06d}.pt"
        if output.exists():
            raise FileExistsError("Untracked checkpoint already exists")
        if source is None:
            result = trainer(examples, output, steps=advance, seed=seed,
                             context=context, width=width, heads=heads)
        else:
            result = resumer(examples, source, output, additional_steps=advance)
        if result["steps"] != next_step or not output.is_file():
            raise RuntimeError("Training did not reach expected step")
        if output.stat().st_size > max_checkpoint_bytes:
            output.unlink()
            raise RuntimeError("Checkpoint exceeded disk budget")
        info = {"schema": 1, "total_steps": total_steps, "interval": interval,
                "completed_steps": next_step, "checkpoint": output.name,
                "checkpoint_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "automatic_promotion": False}
        temporary = root / "training-progress.json.tmp"
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(info, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, manifest)
        completed, source = next_step, output
    return {"completed_steps": completed, "total_steps": total_steps,
            "finished": completed == total_steps, "active_brain_changed": False}
