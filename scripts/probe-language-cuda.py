"""Read-only CUDA readiness probe. Does not claim GPU model training.

Runs a real small CUDA matmul if CUDA is available; never fabricates results.
"""
import argparse
import json
import platform
import time
from pathlib import Path


def probe(*, require_cuda=False):
    try:
        import torch
    except ImportError as exc:
        if require_cuda:
            raise RuntimeError("PyTorch is not installed") from exc
        return {"schema": "yorika-cuda-probe-v1", "cuda_usable": False,
                "reason": "PyTorch unavailable", "real_training_completed": False}
    result = {"schema": "yorika-cuda-probe-v1", "torch_version": torch.__version__,
              "python_platform": platform.platform(), "cuda_usable": False,
              "real_training_completed": False}
    if not torch.cuda.is_available():
        result["reason"] = "CUDA unavailable in the current PyTorch environment"
        if require_cuda:
            raise RuntimeError(result["reason"])
        return result
    try:
        device = torch.device("cuda:0")
        name = torch.cuda.get_device_name(device)
        memory = torch.cuda.get_device_properties(device).total_memory
        begin = time.perf_counter()
        a = torch.ones((64, 64), device=device)
        b = torch.mm(a, a)
        torch.cuda.synchronize(device)
        if float(b[0, 0].item()) != 64.0:
            raise RuntimeError("GPU arithmetic self-test failed")
        result.update({"cuda_usable": True, "gpu_name": name, "vram_bytes": memory,
                       "probe_seconds": time.perf_counter() - begin,
                       "reason": "CUDA arithmetic passed; language training not run"})
    except Exception as exc:
        if require_cuda:
            raise
        result["reason"] = "CUDA probe failed: " + type(exc).__name__
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--require-cuda", action="store_true")
    args = parser.parse_args()
    output = Path(args.output)
    result = probe(require_cuda=args.require_cuda)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(result, ensure_ascii=False))
    if not result["cuda_usable"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
