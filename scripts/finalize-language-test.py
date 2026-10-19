"""One-time, independently audited test scoring; no training or auto-promotion."""
import argparse
import hashlib
import json
from pathlib import Path

from backend.neural_corpus_v2 import prepare
from backend.neural_language_benchmark import fingerprint, load_candidate, score
from backend.neural_language_longrun import digest


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def finalize(records_path, experiment_dir, *, report_name="final-test.json"):
    source = Path(records_path)
    if not source.is_file() or not 0 < source.stat().st_size <= 30_000_000:
        raise ValueError("Missing or oversized consent dataset")
    root = Path(experiment_dir)
    if not root.is_dir() or not (root / "experiment.json").is_file():
        raise ValueError("Prior experiment report required")
    if report_name != "final-test.json":
        raise ValueError("Final report name is fixed")
    report_path = root / report_name
    if report_path.exists():
        raise FileExistsError("Independent test already recorded; never overwrite")
    experiment = json.loads((root / "experiment.json").read_text(encoding="utf-8"))
    if experiment.get("schema") != "yorika-experiment-v1" or experiment.get("test_evaluated") is not False:
        raise ValueError("Invalid prior experiment")
    dataset = prepare(json.loads(source.read_text(encoding="utf-8")))
    if dataset["manifest"] != experiment.get("data"):
        raise ValueError("Dataset changed since training")
    best = root / "language-longrun.pt.best.pt"
    model, state = load_candidate(best)
    if state.get("train_sha256") != digest(dataset["train"]):
        raise ValueError("Checkpoint training corpus hash mismatch")
    if state.get("validation_sha256") != digest(dataset["validation"]):
        raise ValueError("Checkpoint validation corpus hash mismatch")
    train_keys = {prompt.casefold().strip() for prompt, _ in dataset["train"]}
    val_keys = {prompt.casefold().strip() for prompt, _ in dataset["validation"]}
    test_keys = {prompt.casefold().strip() for prompt, _ in dataset["test"]}
    if test_keys & (train_keys | val_keys):
        raise ValueError("Independent test prompt contamination")
    result = score(model, state, dataset["test"])
    report = {"schema": "yorika-final-test-v1",
              "test_sha256": fingerprint(dataset["test"]),
              "test_count": len(dataset["test"]),
              "checkpoint_sha256": sha256_file(best),
              "checkpoint_step": state["step"],
              "tokenizer_sha256": state["tokenizer"]["sha256"],
              "test": result, "auto_promoted": False,
              "limitation": "Held-out NLL is not human dialogue-quality evidence"}
    with report_path.open("x", encoding="utf-8") as out:
        json.dump(report, out, ensure_ascii=False, sort_keys=True, indent=2)
        out.write("\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", required=True)
    parser.add_argument("--experiment-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.records, args.experiment_dir), ensure_ascii=False))


if __name__ == "__main__":
    main()
