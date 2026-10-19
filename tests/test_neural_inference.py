"""Inference validation without optional PyTorch or private model data."""
import tempfile
import unittest
from pathlib import Path

from backend.neural_inference import generate, validate_checkpoint


class NeuralInferenceTests(unittest.TestCase):
    def test_checkpoint_dimensions_and_vocabulary(self):
        base = {"state_dict": {}, "vocab": ["<pad>", "<unk>", "а"],
                "config": {"width": 64, "heads": 4, "context": 64, "seed": 42},
                "steps": 10, "examples": 1}
        self.assertEqual(validate_checkpoint(base)[1][-1], "а")
        with self.assertRaises(ValueError):
            validate_checkpoint({**base, "vocab": ["<pad>", "<unk>", "а", "а"]})
        with self.assertRaises(ValueError):
            validate_checkpoint({**base, "config": {**base["config"], "width": 65}})
        with self.assertRaises(ValueError):
            validate_checkpoint({**base, "steps": 0})

    def test_bad_generation_parameters_fail_before_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.pt"
            with self.assertRaises(ValueError):
                generate(missing, "", max_tokens=5)
            with self.assertRaises(ValueError):
                generate(missing, "Привет", max_tokens=0)
            with self.assertRaises(ValueError):
                generate(missing, "Привет", max_tokens=True)
            with self.assertRaises(ValueError):
                generate(missing, "Привет")
            oversized = Path(directory) / "oversized.pt"
            with oversized.open("wb") as output:
                output.truncate(101 * 1024 * 1024)
            with self.assertRaises(ValueError):
                generate(oversized, "Привет")


if __name__ == "__main__":
    unittest.main()
