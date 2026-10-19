"""Deterministic neural evaluation, input isolation, and report safety."""
import tempfile
import unittest
from pathlib import Path
from backend.neural_evaluation import split_examples, evaluate_heldout, write_report


class NeuralEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.pairs = [(f"Вопрос {n}", f"Ответ {n}") for n in range(20)]

    def test_repeatable_disjoint_split(self):
        train, heldout = split_examples(self.pairs)
        self.assertEqual((len(train), len(heldout)), (16, 4))
        self.assertEqual((train, heldout), split_examples(list(reversed(self.pairs))))
        self.assertFalse(set(map(tuple, train)) & set(map(tuple, heldout)))
        self.assertEqual(set(map(tuple, train + heldout)), set(self.pairs))

    def test_reject_conflicting_or_insufficient_data(self):
        with self.assertRaises(ValueError):
            split_examples([("same", "yes"), ("same", "no")] + self.pairs)
        with self.assertRaises(ValueError):
            split_examples(self.pairs[:4])
        with self.assertRaises(ValueError):
            split_examples(self.pairs, holdout_percent=True)

    def test_exact_match_is_honest_metric(self):
        result = evaluate_heldout([("a", "yes"), ("b", "no")],
                                  lambda q, **kw: {"answer": "yes" if q == "a" else "maybe"})
        self.assertEqual(result["exact_matches"], 1)
        self.assertEqual(result["exact_match_rate"], 0.5)
        self.assertEqual(result["metric"], "heldout_exact_match_only")

    def test_immutable_report(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "eval.json"
            report = evaluate_heldout([("a", "yes")], lambda q, **kw: "yes")
            write_report(target, report)
            with self.assertRaises(FileExistsError):
                write_report(target, report)
            self.assertTrue(target.exists())


if __name__ == "__main__":
    unittest.main()
