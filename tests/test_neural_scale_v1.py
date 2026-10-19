import tempfile
import unittest
from pathlib import Path
from backend.neural_corpus_v2 import prepare


class CorpusTests(unittest.TestCase):
    def records(self):
        return [{"prompt": "Вопрос " + str(i), "answer": "Ответ " + str(i),
                 "source": "author-reviewed", "license": "synthetic", "consent": True}
                for i in range(20)]

    def test_three_way_split_and_fingerprints(self):
        first = prepare(self.records())
        self.assertEqual(first, prepare(list(reversed(self.records()))))
        self.assertEqual(sum(len(first[k]) for k in ("train", "validation", "test")), 20)
        keys = [set(x for x, _ in first[k]) for k in ("train", "validation", "test")]
        self.assertFalse(keys[0] & keys[1] or keys[0] & keys[2] or keys[1] & keys[2])

    def test_fail_closed(self):
        rows = self.records()
        rows[0]["consent"] = False
        with self.assertRaises(ValueError):
            prepare(rows)
        rows = self.records()
        rows[0]["answer"] = "пароль: secretvalue"
        with self.assertRaises(ValueError):
            prepare(rows)
        rows = self.records()
        rows[1]["prompt"] = rows[0]["prompt"]
        with self.assertRaises(ValueError):
            prepare(rows)


class ScaleTests(unittest.TestCase):
    def test_scaled_parameter_budget(self):
        try:
            import torch
        except ImportError:
            self.skipTest("PyTorch optional")
        from backend.neural_language_bpe_v2 import make_model
        model = make_model(torch, vocab_size=261, width=320, heads=8, layers=4, context=256)
        count = sum(p.numel() for p in model.parameters())
        self.assertGreaterEqual(count, 5_000_000)
        self.assertLessEqual(count, 10_000_000)

    def test_checkpoint_resume_and_heldout(self):
        try:
            import torch
        except ImportError:
            self.skipTest("PyTorch optional")
        from backend.neural_language_longrun import run
        train = [("Привет " + str(i), "Ответ " + str(i)) for i in range(4)]
        val = [("Другой вопрос", "Другой ответ")]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "run.pt"
            kwargs = dict(width=32, heads=4, layers=1, context=128,
                          max_merges=8, checkpoint_every=1)
            first = run(train, val, path, total_steps=1, **kwargs)
            next_run = run(train, val, path, total_steps=2, **kwargs)
            self.assertEqual(first["steps"], 1)
            self.assertEqual(next_run["resumed_from"], 1)
            self.assertGreater(next_run["validation_nll"], 0)
            with self.assertRaises(ValueError):
                run(train[::-1], val, path, total_steps=3, **kwargs)


if __name__ == "__main__":
    unittest.main()
