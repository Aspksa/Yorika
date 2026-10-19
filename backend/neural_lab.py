"""Persistent, reviewable native neural experiments; never auto-activate checkpoints."""
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

from backend.neural_evaluation import split_examples, evaluate_checkpoint
from backend.neural_experiment import corpus_fingerprint
from backend.training_engine import train


def run_lab(examples, directory, configurations, *, trainer=train, evaluator=evaluate_checkpoint):
    if not isinstance(configurations, (list, tuple)) or not 2 <= len(configurations) <= 5:
        raise ValueError("Two to five candidates required")
    train_pairs, heldout_pairs = split_examples(examples)
    root = Path(directory)
    if root.exists():
        raise FileExistsError("Lab directory must be new to avoid overwriting models")
    names = set()
    for config in configurations:
        if not isinstance(config, dict) or set(config) != {"name", "steps", "seed", "width", "heads", "context"}:
            raise ValueError("Expected explicit architecture and training configuration")
        name = config["name"]
        if not isinstance(name, str) or not name.isidentifier() or len(name) > 40 or name in names:
            raise ValueError("Invalid candidate name")
        names.add(name)
        width, heads, context, steps, seed = (config[k] for k in ("width", "heads", "context", "steps", "seed"))
        if any(type(v) is not int for v in (width, heads, context, steps, seed)):
            raise ValueError("Training configuration must be integers")
        if not 16 <= width <= 256 or not 1 <= heads <= 8 or width % heads or not 16 <= context <= 256 or not 1 <= steps <= 10000 or not 0 <= seed <= 2**32-1:
            raise ValueError("Training configuration exceeds limits")
    root.mkdir(parents=True)
    results = []
    try:
        for config in configurations:
            filename = root / (config["name"] + ".pt")
            started = time.perf_counter()
            training = trainer(train_pairs, filename, **{key: config[key] for key in ("steps", "seed", "width", "heads", "context")})
            train_seconds = time.perf_counter() - started
            if not filename.is_file() or filename.stat().st_size > 100 * 1024 * 1024:
                raise RuntimeError("Checkpoint missing or oversized")
            started = time.perf_counter()
            quality = evaluator(filename, heldout_pairs)
            eval_seconds = time.perf_counter() - started
            heldout_hash = corpus_fingerprint(heldout_pairs)
            if quality.get("dataset_sha256") != heldout_hash or quality.get("metric") != "heldout_exact_match_only":
                raise ValueError("Evaluation data does not match held-out corpus")
            digest = hashlib.sha256(filename.read_bytes()).hexdigest()
            if quality.get("checkpoint_sha256") != digest:
                raise ValueError("Checkpoint digest mismatch")
            results.append({"name": config["name"], "config": config,
                            "training": training, "evaluation": quality,
                            "training_seconds": round(train_seconds, 4),
                            "evaluation_seconds": round(eval_seconds, 4),
                            "checkpoint_bytes": filename.stat().st_size,
                            "checkpoint_sha256": digest})
        report = {"train_sha256": corpus_fingerprint(train_pairs),
                  "heldout_sha256": corpus_fingerprint(heldout_pairs),
                  "models": results, "auto_promoted": False,
                  "note": "Manual review required. CPU timing is not RTX 3050 acceptance."}
        with (root / "report.json").open("x", encoding="utf-8") as output:
            json.dump(report, output, ensure_ascii=False, indent=2)
        return report
    except Exception:
        # Never leave a partially accepted run that could be mistaken for a validated model.
        import shutil
        shutil.rmtree(root)
        raise
