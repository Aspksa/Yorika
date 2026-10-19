"""Consent-only language corpus with provenance and immutable train/heldout hashes."""
import hashlib
import json
from backend.neural_evaluation import split_examples


def prepare_corpus(records):
    if not isinstance(records, (list, tuple)):
        raise ValueError("Explicit consent records required")
    examples = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Invalid record")
        if record.get("consent") is not True:
            continue
        if not isinstance(record.get("prompt"), str) or not isinstance(record.get("answer"), str):
            raise ValueError("Invalid consented dialogue")
        if not record["prompt"].strip() or not record["answer"].strip():
            raise ValueError("Empty consented dialogue")
        if not isinstance(record.get("source"), str) or not record["source"].strip():
            raise ValueError("Missing dataset provenance")
        if record.get("license") not in ("user-consent", "synthetic", "public-domain"):
            raise ValueError("Unknown data authorization")
        examples.append((record["prompt"].strip(), record["answer"].strip()))
    train, holdout = split_examples(examples)
    def digest(rows):
        return hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return {"train": train, "holdout": holdout,
            "manifest": {"schema": 1, "train_count": len(train),
                         "holdout_count": len(holdout),
                         "train_sha256": digest(train), "holdout_sha256": digest(holdout),
                         "provenance_checked": True}}
