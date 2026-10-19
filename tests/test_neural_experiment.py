"""Experiment runner isolation and fingerprint regression checks."""
import tempfile
import unittest
from pathlib import Path
from backend.neural_experiment import run_experiment, corpus_fingerprint, compare_runs


class NeuralExperimentTests(unittest.TestCase):
    def setUp(self):
        self.examples = [(f"Вопрос {i}", f"Ответ {i}") for i in range(10)]

    def test_only_train_split_reaches_trainer(self):
        observed = {}
        def trainer(pairs, checkpoint, **kwargs):
            observed["train"] = set(map(tuple, pairs))
            Path(checkpoint).write_bytes(b"temporary weights")
            return {"steps": kwargs["steps"], "initial_loss": 2.0, "final_loss": 1.5}
        def evaluator(checkpoint, heldout):
            observed["heldout"] = set(map(tuple, heldout))
            return {"metric": "heldout_exact_match_only", "examples": len(heldout),
                    "exact_matches": 0, "exact_match_rate": 0.0,
                    "dataset_sha256": corpus_fingerprint(heldout)}
        result = run_experiment(self.examples, trainer=trainer, evaluator=evaluator)
        self.assertFalse(observed["train"] & observed["heldout"])
        self.assertFalse(result["auto_promoted"])
        self.assertFalse(result["checkpoint_retained"])
        self.assertEqual(result["training"]["examples"], 8)

    def test_forged_evaluation_fingerprint_fails(self):
        def trainer(pairs, checkpoint, **kwargs):
            Path(checkpoint).write_bytes(b"fixture")
            return {"steps": 2, "initial_loss": 1., "final_loss": 1.}
        def evaluator(*args):
            return {"metric": "heldout_exact_match_only", "dataset_sha256": "0" * 64}
        with self.assertRaises(ValueError):
            run_experiment(self.examples, trainer=trainer, evaluator=evaluator)

    def test_reject_invalid_arguments_without_training(self):
        for kwargs in ({"steps": 0}, {"seed": True}, {"holdout_percent": 99}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                run_experiment(self.examples, **kwargs)


if __name__ == "__main__":
    unittest.main()
