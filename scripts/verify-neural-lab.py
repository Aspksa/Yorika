"""Real CPU PyTorch acceptance of persisted architecture candidates."""
import json
import tempfile
from pathlib import Path
from backend.neural_lab import run_lab


def main():
    pairs = [(f"Вопрос {i}", f"Ответ {i}") for i in range(30)]
    configs = [
        {"name": "width32", "steps": 2, "seed": 42, "width": 32, "heads": 4, "context": 32},
        {"name": "width48", "steps": 2, "seed": 42, "width": 48, "heads": 4, "context": 32},
    ]
    with tempfile.TemporaryDirectory(prefix="yorika-real-lab-") as temp:
        root = Path(temp) / "candidates"
        report = run_lab(pairs, root, configs)
        assert len(report["models"]) == 2
        assert all((root / (c["name"] + ".pt")).is_file() for c in configs)
        print(json.dumps({"models": [
            {"name": m["name"], "checkpoint_bytes": m["checkpoint_bytes"],
             "exact_match_rate": m["evaluation"]["exact_match_rate"],
             "training_seconds": m["training_seconds"],
             "evaluation_seconds": m["evaluation_seconds"]} for m in report["models"]],
             "auto_promoted": report["auto_promoted"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
