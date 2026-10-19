"""Real CPU PyTorch comparison using synthetic prompts only."""
import json
from backend.neural_multi_experiment import compare_candidates


def main():
    examples = [(f"Вопрос {i}", f"Ответ {i}") for i in range(10)]
    report = compare_candidates(
        examples,
        [{"name": "base", "steps": 2, "seed": 42},
         {"name": "trial", "steps": 3, "seed": 42}],
    )
    print(json.dumps(report, ensure_ascii=False))
    return report


if __name__ == "__main__":
    main()
