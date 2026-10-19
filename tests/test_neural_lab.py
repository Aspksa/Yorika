"""Persistent neural laboratory verification with isolated toy trainers."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from backend.neural_lab import run_lab
from backend.neural_experiment import corpus_fingerprint

CONFIGS = [
    {"name": "small", "steps": 2, "seed": 42, "width": 32, "heads": 4, "context": 32},
    {"name": "wide", "steps": 3, "seed": 42, "width": 64, "heads": 4, "context": 32},
]


class NeuralLabTests(unittest.TestCase):
    def examples(self):
        return [(f"Вопрос {i}", f"Ответ {i}") for i in range(30)]

    def trainer(self, pairs, path, **kwargs):
        Path(path).write_bytes(str(kwargs).encode("ascii"))
        return {"steps": kwargs["steps"], "initial_loss": 3., "final_loss": 2.}

    def evaluator(self, path, pairs):
        return {"metric": "heldout_exact_match_only",
                "examples": len(pairs), "exact_matches": 0,
                "exact_match_rate": 0.,
                "dataset_sha256": corpus_fingerprint(pairs),
                "checkpoint_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}

    def test_keep_checkpoints_with_verified_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "lab"
            report = run_lab(self.examples(), root, CONFIGS,
                             trainer=self.trainer, evaluator=self.evaluator)
            self.assertEqual(len(report["models"]), 2)
            self.assertFalse(report["auto_promoted"])
            self.assertTrue((root / "report.json").exists())
            self.assertTrue((root / "small.pt").exists())
            self.assertTrue((root / "wide.pt").exists())
            with self.assertRaises(FileExistsError):
                run_lab(self.examples(), root, CONFIGS, trainer=self.trainer, evaluator=self.evaluator)

    def test_failure_removes_incomplete_run(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "lab"
            with self.assertRaises(ValueError):
                run_lab(self.examples(), root, CONFIGS, trainer=self.trainer,
                        evaluator=lambda *args: {"metric": "heldout_exact_match_only"})
            self.assertFalse(root.exists())

    def test_invalid_config_does_not_create_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "lab"
            with self.assertRaises(ValueError):
                run_lab(self.examples(), root,
                        [CONFIGS[0], {**CONFIGS[1], "width": 33}],
                        trainer=self.trainer, evaluator=self.evaluator)
            self.assertFalse(root.exists())


if __name__ == "__main__":
    unittest.main()
