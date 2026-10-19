"""Standalone quality gates for Yorika's own model experiments.

The gate never promotes or deploys a checkpoint; it only produces a report.
"""
import math


def compare_evaluations(baseline, candidate, *, min_examples=5, max_regression=0.0):
    if type(min_examples) is not int or not 1 <= min_examples <= 100000:
        raise ValueError("Invalid minimum sample count")
    if type(max_regression) not in (int, float) or not math.isfinite(max_regression) or not 0 <= max_regression <= 1:
        raise ValueError("Invalid regression tolerance")
    for label, report in (("baseline", baseline), ("candidate", candidate)):
        if not isinstance(report, dict) or report.get("metric") != "heldout_exact_match_only":
            raise ValueError(f"Invalid {label} evaluation")
        count, score = report.get("examples"), report.get("exact_match_rate")
        if type(count) is not int or count < min_examples:
            raise ValueError(f"Insufficient {label} held-out examples")
        if type(score) not in (float, int) or not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError(f"Invalid {label} quality score")
        matches = report.get("exact_matches")
        if type(matches) is not int or not 0 <= matches <= count or abs(matches / count - score) > 1e-9:
            raise ValueError(f"Inconsistent {label} metrics")
    if baseline["examples"] != candidate["examples"]:
        raise ValueError("Evaluations require identical sample counts")
    if (not isinstance(baseline.get("dataset_sha256"), str)
            or baseline["dataset_sha256"] != candidate.get("dataset_sha256")
            or len(baseline["dataset_sha256"]) != 64):
        raise ValueError("Evaluations must use identical held-out dataset")
    delta = candidate["exact_match_rate"] - baseline["exact_match_rate"]
    return {"passed": delta >= -max_regression, "score_delta": round(delta, 8),
            "baseline_score": baseline["exact_match_rate"],
            "candidate_score": candidate["exact_match_rate"],
            "samples": baseline["examples"], "auto_promoted": False}
