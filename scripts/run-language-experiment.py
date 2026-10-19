"""Explicit local experiment entrypoint for Yorika's single BPE language brain.

Input JSON array: prompt, answer, source, license, consent=true.
Never downloads data, uses the held-out test set for model selection, or promotes weights.
"""
import argparse
import hashlib
import json
from pathlib import Path

from backend.neural_corpus_v2 import prepare
from backend.neural_language_longrun import run


def execute(records_path, output_dir, *, steps=100, checkpoint_every=20,
            width=320, heads=8, layers=4, context=256, max_merges=128, seed=42):
    source = Path(records_path)
    if not source.is_file() or not 0 < source.stat().st_size <= 30_000_000:
        raise ValueError("Missing or oversized consent dataset JSON")
    records = json.loads(source.read_text(encoding="utf-8"))
    dataset = prepare(records)
    output = Path(output_dir)
    if output.exists() and not output.is_dir():
        raise ValueError("Output must be a directory")
    output.mkdir(parents=True, exist_ok=True)
    checkpoint = output / "language-longrun.pt"
    report_path = output / "experiment.json"
    if report_path.exists():
        raise FileExistsError("Immutable experiment report already exists")
    result = run(dataset["train"], dataset["validation"], checkpoint,
                 total_steps=steps, checkpoint_every=checkpoint_every,
                 width=width, heads=heads, layers=layers, context=context,
                 max_merges=max_merges, seed=seed)
    report = {"schema": "yorika-experiment-v1",
              "data": dataset["manifest"], "training": result,
              "test_reserved": True, "test_evaluated": False,
              "notes": "Metadata license checks and regex screening do not establish dataset quality; no automatic promotion"}
    with report_path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", required=True, help="Local explicitly authorized JSON dataset")
    parser.add_argument("--output", required=True, help="Directory for checkpoint and immutable report")
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--checkpoint-every", type=int, default=20)
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--heads", type=int, default=8)
    parser.add_argument("--layers", type=int, default=4)
    parser.add_argument("--context", type=int, default=256)
    parser.add_argument("--max-merges", type=int, default=128)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    report = execute(args.records, args.output, steps=args.steps,
                     checkpoint_every=args.checkpoint_every,
                     width=args.width, heads=args.heads, layers=args.layers,
                     context=args.context, max_merges=args.max_merges, seed=args.seed)
    print(json.dumps({"training": report["training"], "test_evaluated": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
