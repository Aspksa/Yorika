import tempfile
import unittest
from pathlib import Path


class BoundedTrainingTests(unittest.TestCase):
    def test_budget_validation(self):
        try:
            import torch
        except ImportError:
            self.skipTest("PyTorch optional")
        from backend.neural_language_longrun import run
        pairs = [("Привет", "Здравствуйте")]
        valid = [("Другой", "Ответ")]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "model.pt"
            kwargs = dict(total_steps=3, checkpoint_every=1, width=32, heads=4,
                          layers=1, context=128, max_merges=8)
            with self.assertRaises(ValueError):
                run(pairs, valid, path, max_run_seconds=-1, **kwargs)
            report = run(pairs, valid, path, max_run_seconds=0.001, **kwargs)
            self.assertGreaterEqual(report["steps"], 1)
            self.assertLessEqual(report["steps"], 3)
            self.assertGreater(report["elapsed_seconds"], 0)
            self.assertGreater(report["steps_per_second"], 0)
            self.assertTrue(path.exists())
            resumed = run(pairs, valid, path, max_run_seconds=30, **kwargs)
            self.assertEqual(resumed["steps"], 3)
            self.assertEqual(resumed["resumed_from"], report["steps"])


if __name__ == "__main__":
    unittest.main()
