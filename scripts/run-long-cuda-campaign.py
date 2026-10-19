"""Resume-aware single-brain GPU campaign with gated local corpora and session receipts.

No downloads, no automatic model activation. Local evidence is not third-party
proof of licensing or GPU duration. Use CUDA explicitly on the actual GPU host.
"""
import argparse
import json
import math
import time
from pathlib import Path

from backend.neural_corpus_v2 import prepare
from backend.neural_language_longrun import run


def campaign(records_path, output_dir, *, total_steps=100000, session_seconds=3600,
             max_sessions=48, min_records=10000, device="cuda",
             width=320, heads=8, layers=4, context=256, max_merges=128,
             checkpoint_every=100, seed=42):
    if device not in ("cpu", "cuda"):
        raise ValueError("Explicit cpu/cuda device required")
    if (type(total_steps) is not int or not 1 <= total_steps <= 1000000 or
            type(max_sessions) is not int or not 1 <= max_sessions <= 500 or
            type(min_records) is not int or not 10 <= min_records <= 100000 or
            type(session_seconds) not in (int, float) or
            not math.isfinite(session_seconds) or not 0 < session_seconds <= 86400):
        raise ValueError("Invalid campaign budget")
    source = Path(records_path)
    if not source.is_file() or not 0 < source.stat().st_size <= 30_000_000:
        raise ValueError("Missing or oversized local corpus")
    records = json.loads(source.read_text(encoding="utf-8"))
    data = prepare(records)
    if len(records) < min_records:
        raise ValueError("Corpus smaller than approved campaign threshold")
    if any(not isinstance(r.get("rights_reviewed_by"), str) or
           not r["rights_reviewed_by"].strip() or
           r.get("quality_reviewed") is not True for r in records):
        raise ValueError("All corpus records require recorded rights/quality review")
    import torch
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable: campaign cannot silently fall back to CPU")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    checkpoint = out / "language-longrun.pt"
    summary = {"schema": "yorika-campaign-v1", "device": device,
               "gpu_name": torch.cuda.get_device_name(0) if device == "cuda" else None,
               "corpus": data["manifest"], "target_steps": total_steps}
    manifest = out / "campaign-manifest.json"
    if manifest.exists():
        if json.loads(manifest.read_text(encoding="utf-8")) != summary:
            raise ValueError("Campaign config or corpus changed")
    else:
        with manifest.open("x", encoding="utf-8") as stream:
            json.dump(summary, stream, ensure_ascii=False, sort_keys=True, indent=2)
    sessions = []
    for index in range(max_sessions):
        # Preexisting checkpoint is validated by the trainer before any updates.
        elapsed_start = time.monotonic()
        status = run(data["train"], data["validation"], checkpoint,
                     total_steps=total_steps, checkpoint_every=checkpoint_every,
                     width=width, heads=heads, layers=layers, context=context,
                     max_merges=max_merges, seed=seed,
                     max_run_seconds=session_seconds, device=device)
        receipt = {"schema": "yorika-campaign-session-v1", "session": index,
                   "device": device, "gpu_name": summary["gpu_name"],
                   "steps": status["steps"], "resumed_from": status["resumed_from"],
                   "wall_seconds": time.monotonic() - elapsed_start,
                   "peak_cuda_allocated_bytes": status["peak_cuda_allocated_bytes"],
                   "validation_nll": status["validation_nll"],
                   "best_step": status["best_step"],
                   "train_sha256": status["train_sha256"]}
        path = out / ("session-%04d-%d.json" % (index, status["steps"]))
        with path.open("x", encoding="utf-8") as stream:
            json.dump(receipt, stream, ensure_ascii=False, sort_keys=True, indent=2)
        sessions.append(receipt)
        if status["steps"] >= total_steps:
            break
        if status["steps"] <= status["resumed_from"]:
            raise RuntimeError("Campaign made no training progress")
    return {"completed": bool(sessions and sessions[-1]["steps"] >= total_steps),
            "sessions": len(sessions), "last_step": sessions[-1]["steps"],
            "device": device, "evidence_is_self_reported": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--total-steps", type=int, default=100000)
    parser.add_argument("--session-seconds", type=float, default=3600)
    parser.add_argument("--max-sessions", type=int, default=48)
    parser.add_argument("--min-records", type=int, default=10000)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--heads", type=int, default=8)
    parser.add_argument("--layers", type=int, default=4)
    parser.add_argument("--context", type=int, default=256)
    parser.add_argument("--max-merges", type=int, default=128)
    parser.add_argument("--checkpoint-every", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    result = campaign(args.records, args.output, total_steps=args.total_steps,
                      session_seconds=args.session_seconds, max_sessions=args.max_sessions,
                      min_records=args.min_records, device=args.device,
                      width=args.width, heads=args.heads, layers=args.layers,
                      context=args.context, max_merges=args.max_merges,
                      checkpoint_every=args.checkpoint_every, seed=args.seed)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
