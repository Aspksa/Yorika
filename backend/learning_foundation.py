"""Local supervised learning registry with explicit consent and manual release gates.

No model is trained, downloaded, or replaced by this module.
"""
import hashlib
import json
import math
import re
from backend.storage import utc_now


def add_example(store, *, prompt, answer, consent=False):
    if consent is not True:
        raise PermissionError("Explicit consent required")
    if not all(isinstance(s, str) and 1 <= len(s.strip()) <= 4000 for s in (prompt, answer)):
        raise ValueError("Example text must be bounded and nonempty")
    key = hashlib.sha256(json.dumps([prompt, answer], ensure_ascii=False).encode("utf-8")).hexdigest()
    store.put("learning_examples", key, {"prompt": prompt.strip(), "answer": answer.strip(),
              "consent": True, "created_at": utc_now()})
    return {"example_id": key}


def evaluate(store, candidate, *, quality, regressions, tests):
    if not isinstance(candidate, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", candidate):
        raise ValueError("Invalid candidate")
    if type(quality) not in (int, float) or not math.isfinite(quality) or not 0 <= quality <= 1:
        raise ValueError("Invalid quality")
    if type(regressions) is not int or regressions < 0 or type(tests) is not int or tests < 10:
        raise ValueError("Invalid evaluation counts")
    value = {"candidate": candidate, "quality": quality, "regressions": regressions,
             "tests": tests, "evaluated_at": utc_now()}
    store.put("learning_evaluations", candidate, value)
    return value


def promote(store, candidate, *, approved=False, min_quality=0.8):
    if approved is not True:
        raise PermissionError("Manual approval required")
    if type(min_quality) not in (float, int) or not math.isfinite(min_quality) or not 0 <= min_quality <= 1:
        raise ValueError("Invalid quality threshold")
    report = store.get("learning_evaluations", candidate)
    if report is None or report["quality"] < min_quality or report["regressions"] != 0:
        raise ValueError("Candidate has not passed evaluation")
    store.put("learning_settings", "active", {"candidate": candidate, "approved_at": utc_now()})
    return {"candidate": candidate}


def rollback(store, *, approved=False):
    if approved is not True:
        raise PermissionError("Manual approval required")
    return store.delete_record("learning_settings", "active")
