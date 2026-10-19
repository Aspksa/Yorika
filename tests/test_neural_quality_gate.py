"""Reject untrusted quality claims and cross-dataset comparisons."""
import unittest
from backend.neural_quality_gate import compare_evaluations


class NeuralQualityGateTests(unittest.TestCase):
    def report(self, matches, digest="a" * 64):
        return {"metric": "heldout_exact_match_only", "examples": 10,
                "exact_matches": matches, "exact_match_rate": matches / 10,
                "dataset_sha256": digest}

    def test_equal_or_better_quality_can_pass_without_promotion(self):
        result = compare_evaluations(self.report(7), self.report(8))
        self.assertTrue(result["passed"])
        self.assertFalse(result["auto_promoted"])

    def test_regression_is_blocked(self):
        self.assertFalse(compare_evaluations(self.report(8), self.report(7))["passed"])

    def test_wrong_dataset_and_inconsistent_score_rejected(self):
        with self.assertRaises(ValueError):
            compare_evaluations(self.report(8), self.report(8, digest="b" * 64))
        invalid = {**self.report(7), "exact_match_rate": 0.95}
        with self.assertRaises(ValueError):
            compare_evaluations(self.report(8), invalid)
        with self.assertRaises(ValueError):
            compare_evaluations(self.report(8), self.report(9), min_examples=True)


if __name__ == "__main__":
    unittest.main()
