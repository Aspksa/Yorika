"""Bounded same-process supervisor for Yorika training.

This is not an OS daemon: it retries recoverable failures and never auto-promotes.
"""
import json
import time
from pathlib import Path
from backend.neural_longrun import run_long_training


def supervise(examples, directory, *, max_restarts=3, max_seconds=3600,
              runner=run_long_training, sleep=time.sleep, clock=time.monotonic, **training):
    if type(max_restarts) is not int or not 0 <= max_restarts <= 10:
        raise ValueError("Invalid restart limit")
    if type(max_seconds) not in (int, float) or not 1 <= max_seconds <= 86400:
        raise ValueError("Invalid supervisor deadline")
    if "total_steps" not in training:
        raise ValueError("total_steps is required")
    started = clock()
    failures = []
    for attempt in range(max_restarts + 1):
        remaining = max_seconds - (clock() - started)
        if remaining < 1:
            break
        try:
            result = runner(examples, directory, max_seconds=remaining, **training)
            if result["finished"]:
                return {"finished": True, "restarts": attempt, "result": result,
                        "failures": failures, "active_brain_changed": False}
            # An unfinished run with a clean time-budget exit must not spin.
            return {"finished": False, "restarts": attempt, "result": result,
                    "failures": failures, "active_brain_changed": False}
        except (OSError, RuntimeError) as error:
            failures.append(type(error).__name__)
            if attempt == max_restarts:
                break
            sleep(min(2 ** attempt, 8))
    return {"finished": False, "restarts": max(0, len(failures) - 1),
            "failures": failures, "active_brain_changed": False}
