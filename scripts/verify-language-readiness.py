"""Evidence-based gates for three unfinished Yorika milestones.

No downloading, training, billable operations, or promotion occurs here.
This validator deliberately fails closed when proof is missing.
"""
import argparse
import hashlib
import json
from pathlib import Path

from backend.neural_corpus_v2 import prepare


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect(records_path, gpu_evidence_path=None, dialogue_evidence_path=None,
            *, min_examples=10000, min_gpu_hours=24):
    records = json.loads(Path(records_path).read_text(encoding="utf-8"))
    # Provenance tags and regex detection are not sufficient to establish legal rights.
    data = prepare(records)
    corpus = data["manifest"]
    corpus_ready = len(records) >= min_examples and all(
        isinstance(r.get("rights_reviewed_by"), str) and r["rights_reviewed_by"].strip()
        and r.get("quality_reviewed") is True for r in records
    )
    gpu_ready = False
    gpu = None
    if gpu_evidence_path is not None:
        gpu = json.loads(Path(gpu_evidence_path).read_text(encoding="utf-8"))
        gpu_ready = (
            gpu.get("schema") == "yorika-gpu-evidence-v1"
            and gpu.get("device_type") == "cuda"
            and isinstance(gpu.get("gpu_name"), str) and bool(gpu["gpu_name"].strip())
            and type(gpu.get("elapsed_hours")) in (int, float)
            and gpu["elapsed_hours"] >= min_gpu_hours
            and type(gpu.get("completed_steps")) is int and gpu["completed_steps"] > 0
            and isinstance(gpu.get("checkpoint_sha256"), str)
            and len(gpu["checkpoint_sha256"]) == 64
            and gpu.get("train_sha256") == corpus["train_sha256"]
            and gpu.get("operator_verified") is True
        )
    dialogue_ready = False
    if dialogue_evidence_path is not None:
        d = json.loads(Path(dialogue_evidence_path).read_text(encoding="utf-8"))
        dialogue_ready = (
            d.get("schema") == "yorika-dialogue-evidence-v1"
            and d.get("blind_human_review") is True
            and type(d.get("independent_prompts")) is int and d["independent_prompts"] >= 100
            and type(d.get("baseline_wins")) is int
            and type(d.get("candidate_wins")) is int
            and 0 <= d["baseline_wins"] < d["candidate_wins"]
            and d["baseline_wins"] + d["candidate_wins"] <= d["independent_prompts"]
            and d.get("reviewer_signoff") is True
            and gpu_ready and corpus_ready
        )
    return {
        "schema": "yorika-milestone-gates-v1",
        "corpus": {"ready": corpus_ready, "records": len(records),
                   "target": min_examples, "manifest": corpus},
        "gpu_training": {"ready": gpu_ready, "target_hours": min_gpu_hours,
                         "evidence_supplied": gpu is not None},
        "dialogue_improvement": {"ready": dialogue_ready},
        "all_ready": corpus_ready and gpu_ready and dialogue_ready,
        "warning": "User-supplied attestations require external human verification; never treat this output alone as proof.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", required=True)
    parser.add_argument("--gpu-evidence")
    parser.add_argument("--dialogue-evidence")
    parser.add_argument("--min-examples", type=int, default=10000)
    parser.add_argument("--min-gpu-hours", type=float, default=24)
    args = parser.parse_args()
    if not 1000 <= args.min_examples <= 100000 or not 1 <= args.min_gpu_hours <= 10000:
        parser.error("Invalid acceptance thresholds")
    result = inspect(args.records, args.gpu_evidence, args.dialogue_evidence,
                     min_examples=args.min_examples, min_gpu_hours=args.min_gpu_hours)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["all_ready"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
