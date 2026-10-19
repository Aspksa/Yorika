import tempfile
import unittest
from pathlib import Path


class BestCheckpointTests(unittest.TestCase):
    def test_resume_retains_best_and_rejects_changed_validation(self):
        try:
            import torch
        except ImportError:
            self.skipTest("PyTorch optional")
        from backend.neural_language_longrun import run
        from backend.neural_language_benchmark import load_candidate
        train = [("Привет " + str(i), "Ответ " + str(i)) for i in range(3)]
        valid = [("Новый запрос", "Новый ответ")]
        kwargs = dict(width=32, heads=4, layers=1, context=128,
                      max_merges=8, checkpoint_every=1)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "state.pt"
            first = run(train, valid, path, total_steps=1, **kwargs)
            best = Path(first["best_checkpoint"])
            self.assertTrue(best.exists())
            _, state = load_candidate(best)
            self.assertEqual(state["step"], 1)
            second = run(train, valid, path, total_steps=2, **kwargs)
            self.assertEqual(second["resumed_from"], 1)
            self.assertGreaterEqual(second["best_step"], 1)
            self.assertLessEqual(second["best_step"], 2)
            _, latest = load_candidate(path)
            self.assertEqual(latest["best_step"], second["best_step"])
            with self.assertRaises(ValueError):
                run(train, [("Совсем новый запрос", "Новый ответ")],
                    path, total_steps=3, **kwargs)
            best.unlink()
            with self.assertRaises(ValueError):
                run(train, valid, path, total_steps=3, **kwargs)


if __name__ == "__main__":
    unittest.main()
