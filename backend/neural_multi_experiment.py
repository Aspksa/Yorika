"""Bounded multi-candidate native neural experiment; no model is deployed."""
import json
import math
import time
import tracemalloc
from pathlib import Path
from backend.neural_experiment import run_experiment, compare_runs
from backend.neural_evaluation import write_report


def compare_candidates(examples, configurations, *, runner=run_experiment, clock=time.perf_counter):
    if not isinstance(configurations, (list, tuple)) or not 2 <= len(configurations) <= 5:
        raise ValueError("Use 2..5 candidate configurations")
    names = set()
    runs = []
    for config in configurations:
        if not isinstance(config, dict) or set(config) != {"name", "steps", "seed"}:
            raise ValueError("Expected name, steps and seed")
        name, steps, seed = config["name"], config["steps"], config["seed"]
        if not isinstance(name, str) or not name.isidentifier() or len(name) > 40 or name in names:
            raise ValueError("Invalid or duplicate candidate name")
        if type(steps) is not int or not 1 <= steps <= 10000:
            raise ValueError("Invalid steps")
        if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
            raise ValueError("Invalid seed")
        names.add(name)
        started = clock()
        tracemalloc.start()
        try:
            result = runner(examples, steps=steps, seed=seed)
            _, peak_bytes = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        elapsed = clock() - started
        if (not isinstance(result, dict) or
                result.get("auto_promoted") is not False or
                not isinstance(result.get("evaluation"), dict)):
            raise ValueError("Runner did not return a safe evaluated experiment")
        runs.append({"name": name, "steps": steps, "seed": seed,
                     "wall_seconds": round(elapsed, 4),
                     "python_peak_bytes": peak_bytes, "result": result})
    baseline = runs[0]
    for run in runs[1:]:
        if (run["result"].get("train_sha256") != baseline["result"].get("train_sha256")
                or run["result"].get("heldout_sha256") != baseline["result"].get("heldout_sha256")):
            raise ValueError("Candidate training or held-out datasets differ")
    comparisons = [{"candidate": run["name"],
                    **compare_runs(baseline["result"], run["result"])} for run in runs[1:]]
    return {"baseline": baseline["name"], "candidates": runs,
            "comparisons": comparisons, "auto_promoted": False,
            "measurement_note": "Python tracemalloc is not total RSS, PyTorch native memory or CUDA VRAM."}


def save_comparison(path, report):
    target = Path(path)
    if not isinstance(report, dict) or report.get("auto_promoted") is not False:
        raise ValueError("Unsafe experiment report")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    return target
