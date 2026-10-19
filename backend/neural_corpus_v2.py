"""Fail-closed preparation of explicitly authorized Russian dialogue records.

A manifest proves filtering/splitting, not linguistic quality or a license audit.
"""
import hashlib
import json
import re

EMAIL = re.compile(r"(?<![\w.])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
SECRET = re.compile(r"(?i)(?:api[_ -]?key|password|token|пароль)\s*[:=]\s*\S+")
ALLOWED = {"user-consent", "public-domain", "synthetic"}


def _sha(data):
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def prepare(records):
    if not isinstance(records, (list, tuple)) or not 10 <= len(records) <= 100000:
        raise ValueError("At least 10 explicitly authorized records required")
    clean, seen = [], set()
    for record in records:
        if not isinstance(record, dict) or record.get("consent") is not True:
            raise ValueError("Every supplied record must have explicit consent")
        if record.get("license") not in ALLOWED or not isinstance(record.get("source"), str) or not record["source"].strip():
            raise ValueError("Source and supported license required")
        prompt, answer = record.get("prompt"), record.get("answer")
        if (not isinstance(prompt, str) or not isinstance(answer, str) or
                not 1 <= len(prompt.strip()) <= 2000 or not 1 <= len(answer.strip()) <= 2000):
            raise ValueError("Invalid dialogue text")
        if any(EMAIL.search(s) or SECRET.search(s) for s in (prompt, answer)):
            raise ValueError("Potential secret/PII: manual review required")
        key = prompt.strip().casefold()
        if key in seen:
            raise ValueError("Duplicate prompt can leak across splits")
        seen.add(key)
        clean.append({"prompt": prompt.strip(), "answer": answer.strip(),
                      "source": record["source"].strip(), "license": record["license"]})
    clean.sort(key=lambda row: _sha(row))
    # Disjoint by normalized prompt; no tokenizer fit on validation or test.
    n = len(clean)
    n_test = max(1, n // 10)
    n_val = max(1, n // 10)
    train, val, test = clean[:n-n_test-n_val], clean[n-n_test-n_val:n-n_test], clean[n-n_test:]
    def pairs(rows):
        return [(r["prompt"], r["answer"]) for r in rows]
    return {"train": pairs(train), "validation": pairs(val), "test": pairs(test),
            "manifest": {"schema": 1, "count": n, "train_sha256": _sha(train),
                         "validation_sha256": _sha(val), "test_sha256": _sha(test),
                         "split": "deterministic-hash-v1", "license_checked": "metadata-only",
                         "personal_data_checked": "regex-only; manual review required"}}
