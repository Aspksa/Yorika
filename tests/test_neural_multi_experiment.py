"""Native neural multi-candidate evaluation: matched datasets and safe reports."""
import tempfile
import unittest
from pathlib import Path
from backend.neural_multi_experiment import compare_candidates, save_comparison


class MultiCandidateTests(unittest.TestCase):
    def report(self, examples, *, steps, seed):
        quality = 0.8 if steps > 2 else 0.7
        return {
            "auto_promoted": False, "train_sha256": "a" * 64, "heldout_sha256": "b" * 64,
            "evaluation": {"metric": "heldout_exact_match_only", "examples": 10,
                           "exact_matches": int(quality * 10), "exact_match_rate": quality,
                           "dataset_sha256": "b" * 64},
        }

    def test_two_versions_have_comparable_quality_and_measurements(self):
        report = compare_candidates([], [{"name": "baseline", "steps": 2, "seed": 4},
                                         {"name": "candidate", "steps": 3, "seed": 4}],
                                    runner=self.report)
        self.assertEqual(report["baseline"], "baseline")
        self.assertEqual(len(report["candidates"]), 2)
        self.assertTrue(report["comparisons"][0]["passed"])
        self.assertFalse(report["auto_promoted"])
        self.assertGreaterEqual(report["candidates"][0]["python_peak_bytes"], 0)

    def test_dataset_mismatch_rejected(self):
        def runner(examples, *, steps, seed):
            result = self.report(examples, steps=steps, seed=seed)
            result["heldout_sha256"] = str(steps)
            return result
        with self.assertRaises(ValueError):
            compare_candidates([], [{"name": "baseline", "steps": 2, "seed": 4},
                                    {"name": "other", "steps": 3, "seed": 4}], runner=runner)

    def test_bad_config_and_immutable_report(self):
        with self.assertRaises(ValueError):
            compare_candidates([], [{"name": "only", "steps": 1, "seed": 2}])
        with self.assertRaises(ValueError):
            compare_candidates([], [{"name": "same", "steps": 1, "seed": 2},
                                    {"name": "same", "steps": 2, "seed": 2}])
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "report.json"
            save_comparison(target, {"auto_promoted": False})
            with self.assertRaises(FileExistsError):
                save_comparison(target, {"auto_promoted": False})


if __name__ == "__main__":
    unittest.main()
