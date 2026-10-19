"""Optional end-to-end smoke check of the experimental neural engine.

Runs only with explicitly supplied examples; never reads the user's profile.
The generated text is an experiment, not a quality or AGI claim.
"""
import argparse
import json
import tempfile
from pathlib import Path

from backend.training_engine import train
from backend.neural_inference import generate


def smoke(*, steps=2, prompt="Привет", examples=None):
    if examples is None:
        examples = [("Привет", "Здравствуйте"), ("Как дела", "Хорошо")]
    if type(steps) is not int or not 1 <= steps <= 50:
        raise ValueError("Smoke steps must be 1..50")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 200:
        raise ValueError("Invalid smoke prompt")
    with tempfile.TemporaryDirectory(prefix="yorika-neural-smoke-") as folder:
        path = Path(folder) / "smoke.pt"
        result = train(examples, path, steps=steps, context=32, width=32, heads=4)
        inference = generate(path, prompt, max_tokens=8)
        return {"trained": path.exists(), "steps": result["steps"],
                "initial_loss": result["initial_loss"],
                "final_loss": result["final_loss"],
                "generated_tokens": inference["generated_tokens"],
                "engine": inference["engine"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=2)
    args = parser.parse_args()
    print(json.dumps(smoke(steps=args.steps), ensure_ascii=False))


if __name__ == "__main__":
    main()
