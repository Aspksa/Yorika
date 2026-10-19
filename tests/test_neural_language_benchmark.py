import tempfile
import unittest
from pathlib import Path

from backend.neural_language_benchmark import compare, fingerprint


class IndependentEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.train = [("Привет " + str(i), "Ответ " + str(i)) for i in range(4)]
        self.validation = [("Другой вопрос", "Другой ответ")]
        self.test = [("Незнакомый вопрос", "Новый ответ")]
        self.hash = fingerprint(self.test)

    def test_reject_modified_test_without_loading_model(self):
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            compare("missing", "missing", self.test, expected_test_sha256="0" * 64)

    def test_train_resume_and_locked_comparison(self):
        try:
            import torch
        except ImportError:
            self.skipTest("PyTorch optional")
        from backend.neural_language_longrun import run
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder) / "baseline.pt"
            cand = Path(folder) / "candidate.pt"
            options = dict(width=32, heads=4, layers=1, context=128,
                           max_merges=8, checkpoint_every=1)
            run(self.train, self.validation, base, total_steps=1, **options)
            run(self.train, self.validation, cand, total_steps=2, **options)
            report_path = Path(folder) / "evaluation.json"
            result = compare(base, cand, self.test, expected_test_sha256=self.hash,
                             report_path=report_path)
            self.assertEqual(result["test_sha256"], self.hash)
            self.assertEqual(result["baseline"]["tokens"], result["candidate"]["tokens"])
            self.assertGreater(result["candidate"]["perplexity"], 0)
            with self.assertRaises(FileExistsError):
                compare(base, cand, self.test, expected_test_sha256=self.hash,
                        report_path=report_path)
            self.assertTrue(report_path.is_file())

    def test_invalid_test_values(self):
        with self.assertRaises(ValueError):
            compare("missing", "missing", [("", "a")], expected_test_sha256="x")


if __name__ == "__main__":
    unittest.main()
