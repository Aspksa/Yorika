"""Neural smoke regression tests without mandatory PyTorch dependency."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import neural_smoke


class NeuralSmokeTests(unittest.TestCase):
    def test_bounded_configuration_fails_before_training(self):
        for steps in (0, 51, True, "2"):
            with self.subTest(steps=steps), self.assertRaises(ValueError):
                neural_smoke.smoke(steps=steps)
        with self.assertRaises(ValueError):
            neural_smoke.smoke(prompt="")

    def test_temporary_checkpoint_and_result_without_profile_access(self):
        def fake_train(examples, output, **kwargs):
            self.assertEqual(kwargs["context"], 32)
            Path(output).write_bytes(b"temporary placeholder")
            return {"steps": kwargs["steps"], "initial_loss": 2.0, "final_loss": 1.0}
        def fake_generate(checkpoint, prompt, **kwargs):
            self.assertTrue(Path(checkpoint).exists())
            self.assertEqual(kwargs["max_tokens"], 8)
            return {"generated_tokens": 8, "engine": "experimental-tiny-transformer"}
        with patch.object(neural_smoke, "train", side_effect=fake_train), patch.object(
            neural_smoke, "generate", side_effect=fake_generate
        ):
            result = neural_smoke.smoke(steps=3)
        self.assertTrue(result["trained"])
        self.assertEqual(result["final_loss"], 1.0)
        self.assertEqual(result["generated_tokens"], 8)


if __name__ == "__main__":
    unittest.main()
