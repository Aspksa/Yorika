import tempfile
import unittest
from pathlib import Path


class CudaTrainingTests(unittest.TestCase):
    def test_explicit_device_and_cpu_resume(self):
        try:
            import torch
        except ImportError:
            self.skipTest("PyTorch optional")
        from backend.neural_language_longrun import run
        train = [("Привет " + str(i), "Ответ " + str(i)) for i in range(3)]
        val = [("Новый вопрос", "Новый ответ")]
        kwargs = dict(checkpoint_every=1, width=32, heads=4, layers=1,
                      context=128, max_merges=8)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.pt"
            with self.assertRaises(ValueError):
                run(train, val, path, total_steps=1, device="invalid", **kwargs)
            first = run(train, val, path, total_steps=1, device="cpu", **kwargs)
            self.assertEqual(first["device"], "cpu")
            self.assertIsNone(first["peak_cuda_allocated_bytes"])
            resumed = run(train, val, path, total_steps=2, device="cpu", **kwargs)
            self.assertEqual(resumed["resumed_from"], 1)
            if not torch.cuda.is_available():
                with self.assertRaisesRegex(RuntimeError, "CUDA required"):
                    run(train, val, path, total_steps=3, device="cuda", **kwargs)

    def test_real_cuda_if_available(self):
        try:
            import torch
        except ImportError:
            self.skipTest("PyTorch optional")
        if not torch.cuda.is_available():
            self.skipTest("No CUDA device on runner; hardware acceptance remains open")
        from backend.neural_language_longrun import run
        train = [("Добрый день " + str(i), "Здравствуйте " + str(i)) for i in range(3)]
        valid = [("Другой вопрос", "Другой ответ")]
        kwargs = dict(checkpoint_every=1, width=32, heads=4, layers=1,
                      context=128, max_merges=8, device="cuda")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.pt"
            first = run(train, valid, path, total_steps=1, **kwargs)
            self.assertEqual(first["device"], "cuda")
            self.assertGreater(first["peak_cuda_allocated_bytes"], 0)
            second = run(train, valid, path, total_steps=2, **kwargs)
            self.assertEqual(second["resumed_from"], 1)


if __name__ == "__main__":
    unittest.main()
