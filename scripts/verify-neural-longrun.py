"""Real PyTorch test: restart a bounded run from periodic checkpoints."""
import tempfile
from pathlib import Path
from backend.neural_longrun import run_long_training
from backend.neural_inference import generate


def main():
    examples = [("Привет", "Здравствуйте"), ("Как дела", "Нормально")]
    with tempfile.TemporaryDirectory(prefix="yorika-recovery-") as folder:
        root = Path(folder)
        ticks = iter([0., 0.1, 2.])
        first = run_long_training(examples, root, total_steps=4, interval=2,
                                  max_seconds=1, clock=lambda: next(ticks))
        assert first["completed_steps"] == 2
        second = run_long_training(examples, root, total_steps=4, interval=2)
        assert second["finished"] and second["completed_steps"] == 4
        assert (root / "step-000002.pt").is_file()
        assert (root / "step-000004.pt").is_file()
        result = generate(root / "step-000004.pt", "Привет", max_tokens=2)
        assert result["generated_tokens"] == 2
        print({"recovered": True, "steps": 4, "old_checkpoint_preserved": True})


if __name__ == "__main__":
    main()
