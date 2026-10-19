import tempfile
import unittest
from pathlib import Path


class CheckpointDeviceTests(unittest.TestCase):
    def test_cpu_resume_has_device_binding(self):
        try:
            import torch
        except ImportError:
            self.skipTest("PyTorch is optional")
        from backend.neural_language_longrun import run
        train = [("Привет " + str(i), "Ответ " + str(i)) for i in range(3)]
        val = [("Другой вопрос", "Другой ответ")]
        args = dict(width=32, heads=4, layers=1, context=128,
                    max_merges=8, checkpoint_every=1)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "checkpoint.pt"
            first = run(train, val, path, total_steps=1, device="cpu", **args)
            self.assertEqual(first["device"], "cpu")
            state = torch.load(path, weights_only=True, map_location="cpu")
            self.assertEqual(state["training_device"], "cpu")
            continued = run(train, val, path, total_steps=2, device="cpu", **args)
            self.assertEqual(continued["resumed_from"], 1)
            if torch.cuda.is_available():
                with self.assertRaisesRegex(ValueError, "device transition"):
                    run(train, val, path, total_steps=3, device="cuda", **args)

    def test_cpu_checkpoint_cannot_claim_cuda_rng(self):
        try:
            import torch
        except ImportError:
            self.skipTest("PyTorch is optional")
        from backend.neural_language_longrun import run
        train = [("Утро", "Доброе утро")]
        val = [("Вечер", "Добрый вечер")]
        kwargs = dict(width=32, heads=4, layers=1, context=128,
                      max_merges=8, checkpoint_every=1)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "checkpoint.pt"
            run(train, val, path, total_steps=1, **kwargs)
            checkpoint = torch.load(path, weights_only=True, map_location="cpu")
            checkpoint["training_device"] = "cuda"
            torch.save(checkpoint, path)
            if torch.cuda.is_available():
                with self.assertRaisesRegex(ValueError, "CUDA RNG"):
                    run(train, val, path, total_steps=2, device="cuda", **kwargs)
            else:
                with self.assertRaisesRegex(RuntimeError, "CUDA required"):
                    run(train, val, path, total_steps=2, device="cuda", **kwargs)


if __name__ == "__main__":
    unittest.main()
