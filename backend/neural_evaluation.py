"""Held-out neural evaluation with deterministic, non-training fixtures.

Evaluation never modifies checkpoints or the user memory database.
"""
import hashlib
import json
from pathlib import Path


def split_examples(examples, *, holdout_percent=20):
    if type(holdout_percent) is not int or not 1 <= holdout_percent <= 50:
        raise ValueError("holdout_percent must be 1..50")
    if not isinstance(examples, (list, tuple)):
        raise ValueError("expected example pairs")
    unique = {}
    for item in examples:
        if (not isinstance(item, (tuple, list)) or len(item) != 2 or
                not all(isinstance(x, str) and 0 < len(x) <= 4000 for x in item)):
            raise ValueError("invalid example")
        prompt, answer = item
        if prompt in unique and unique[prompt] != answer:
            raise ValueError("conflicting answers for the same prompt")
        unique[prompt] = answer
    if len(unique) < 5:
        raise ValueError("at least five unique prompts needed")
    ordered = sorted(unique.items(), key=lambda pair: hashlib.sha256(pair[0].encode("utf-8")).hexdigest())
    count = max(1, len(ordered) * holdout_percent // 100)
    return ordered[count:], ordered[:count]


def evaluate_heldout(examples, predict, *, max_tokens=64):
    if not callable(predict):
        raise ValueError("predict must be callable")
    if type(max_tokens) is not int or not 1 <= max_tokens <= 256:
        raise ValueError("max_tokens must be 1..256")
    if not isinstance(examples, (list, tuple)) or not examples:
        raise ValueError("nonempty evaluation set required")
    correct, count, length_sum = 0, 0, 0
    for prompt, expected in examples:
        if not isinstance(prompt, str) or not isinstance(expected, str):
            raise ValueError("invalid held-out record")
        response = predict(prompt, max_tokens=max_tokens)
        answer = response["answer"] if isinstance(response, dict) else response
        if not isinstance(answer, str):
            raise ValueError("predictor must return text")
        correct += answer.strip() == expected.strip()
        count += 1
        length_sum += len(answer)
    return {"examples": count, "exact_matches": correct,
            "exact_match_rate": correct / count, "average_output_chars": length_sum / count,
            "metric": "heldout_exact_match_only"}


def evaluate_checkpoint(checkpoint, train_pairs, *, holdout_percent=20, max_tokens=64):
    from backend.neural_inference import generate
    _, test_pairs = split_examples(train_pairs, holdout_percent=holdout_percent)
    result = evaluate_heldout(test_pairs, lambda prompt, **kw: generate(checkpoint, prompt, **kw),
                              max_tokens=max_tokens)
    result["checkpoint_sha256"] = hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest()
    return result


def write_report(path, report):
    target = Path(path)
    if target.exists():
        raise FileExistsError("Evaluation reports are immutable")
    if not isinstance(report, dict) or report.get("metric") != "heldout_exact_match_only":
        raise ValueError("invalid evaluation report")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    return target
