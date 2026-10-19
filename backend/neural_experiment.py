"""Reproducible, isolated native-model experiments without third-party inference.

The runner uses synthetic examples unless an explicitly consented dataset is
passed by its caller. Held-out prompts never enter train().
"""
import hashlib
import json
import tempfile
from pathlib import Path

from backend.neural_evaluation import split_examples, evaluate_checkpoint
from backend.neural_quality_gate import compare_evaluations
from backend.training_engine import train


def corpus_fingerprint(pairs):
    data = json.dumps(sorted([list(p) for p in pairs]), ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def run_experiment(examples, *, steps=2, seed=42, holdout_percent=20,
                   trainer=train, evaluator=evaluate_checkpoint):
    if type(steps) is not int or not 1 <= steps <= 10000:
        raise ValueError("Invalid step count")
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ValueError("Invalid seed")
    train_pairs, heldout_pairs = split_examples(examples, holdout_percent=holdout_percent)
    if set(map(tuple, train_pairs)) & set(map(tuple, heldout_pairs)):
        raise RuntimeError("Training and held-out overlap")
    with tempfile.TemporaryDirectory(prefix="yorika-experiment-") as root:
        checkpoint = Path(root) / "candidate.pt"
        trained = trainer(train_pairs, checkpoint, steps=steps, seed=seed)
        if not checkpoint.is_file():
            raise RuntimeError("Training produced no checkpoint")
        measured = evaluator(checkpoint, heldout_pairs)
        if measured.get("metric") != "heldout_exact_match_only":
            raise ValueError("Unexpected quality metric")
        digest = corpus_fingerprint(heldout_pairs)
        if measured.get("dataset_sha256") != digest:
            raise ValueError("Evaluation dataset fingerprint mismatch")
        return {"training": {"steps": trained["steps"], "examples": len(train_pairs),
                             "initial_loss": trained["initial_loss"],
                             "final_loss": trained["final_loss"]},
                "evaluation": measured, "train_sha256": corpus_fingerprint(train_pairs),
                "heldout_sha256": digest, "checkpoint_retained": False,
                "auto_promoted": False}


def compare_runs(baseline, candidate):
    return compare_evaluations(baseline["evaluation"], candidate["evaluation"])
