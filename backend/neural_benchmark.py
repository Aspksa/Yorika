"""Local neural runtime benchmark with no access to chat history or profile.

The benchmark is explicit and never promotes a checkpoint into production.
"""
import argparse
import json
import time
from pathlib import Path

from backend.neural_hardware import hardware_report
from backend.neural_inference import generate


def benchmark(checkpoint, *, prompt="Привет", repetitions=3, max_tokens=16,
              inference=generate, clock=time.perf_counter):
    if type(repetitions) is not int or not 1 <= repetitions <= 20:
        raise ValueError("repetitions must be 1..20")
    if type(max_tokens) is not int or not 1 <= max_tokens <= 64:
        raise ValueError("max_tokens must be 1..64")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 200:
        raise ValueError("Invalid prompt")
    file = Path(checkpoint)
    if not file.is_file() or file.stat().st_size > 100 * 1024 * 1024:
        raise ValueError("Missing or oversized checkpoint")
    durations = []
    for _ in range(repetitions):
        started = clock()
        result = inference(file, prompt, max_tokens=max_tokens)
        elapsed = clock() - started
        if not isinstance(result, dict) or not isinstance(result.get("answer"), str):
            raise RuntimeError("Invalid inference result")
        durations.append(round(elapsed, 6))
    return {"runs": repetitions, "seconds": durations,
            "average_seconds": sum(durations) / repetitions,
            "checkpoint_bytes": file.stat().st_size,
            "device_used": "cpu",
            "hardware": hardware_report(),
            "note": "This inference path runs on CPU; CUDA availability is diagnostic only."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=3)
    args = parser.parse_args()
    print(json.dumps(benchmark(args.checkpoint, repetitions=args.repetitions), ensure_ascii=False))


if __name__ == "__main__":
    main()
