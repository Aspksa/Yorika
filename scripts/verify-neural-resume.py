"""Real PyTorch weight continuation acceptance on synthetic examples."""
import tempfile
from pathlib import Path
from backend.training_engine import train
from backend.neural_resume import resume_training
from backend.neural_inference import generate


def main():
    examples = [("Привет", "Здравствуйте"), ("Как дела", "Нормально")]
    with tempfile.TemporaryDirectory() as folder:
        first, second = Path(folder) / "first.pt", Path(folder) / "continued.pt"
        original = train(examples, first, steps=2, width=32, heads=4, context=32)
        result = resume_training(examples, first, second, additional_steps=2)
        assert first.is_file() and second.is_file()
        assert original["steps"] == 2 and result["steps"] == 4
        assert result["optimizer_reinitialized"] is True
        assert generate(second, "Привет", max_tokens=3)["generated_tokens"] == 3
        print({"original_steps": original["steps"], "continued_steps": result["steps"],
               "optimizer_reinitialized": True, "source_preserved": first.exists()})


if __name__ == "__main__":
    main()
