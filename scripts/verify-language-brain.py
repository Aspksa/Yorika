"""CPU PyTorch actual train -> heldout loss -> generate acceptance."""
import json
import tempfile
from pathlib import Path
from backend.neural_language_v1 import train_language, heldout_loss, generate_language
from backend.neural_evaluation import split_examples


def main():
    examples = [(f"Приветствие номер {i}", f"Здравствуйте номер {i}") for i in range(30)]
    training, holdout = split_examples(examples)
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "language-v1.pt"
        report = train_language(training, path, steps=3, width=32, context=128)
        score = heldout_loss(path, holdout)
        result = generate_language(path, "Приветствие номер 99", max_tokens=4)
        assert score > 0 and score < 100 and path.exists()
        assert result["engine"] == "yorika-language-v1"
        print(json.dumps({"train": report, "heldout_nll": score,
                          "generated_bytes": result["generated_tokens"],
                          "holdout_count": len(holdout)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
