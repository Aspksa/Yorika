"""Benchmark measurements are deterministic under an injected clock."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend.neural_benchmark import benchmark


class NeuralBenchmarkTests(unittest.TestCase):
    def test_report_cpu_and_no_fake_gpu_measurements(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "trusted.pt"
            path.write_bytes(b"fixture")
            samples = iter([0., 0.2, 1., 1.4])
            with patch("backend.neural_benchmark.hardware_report", return_value={"device": "cpu"}):
                result = benchmark(path, repetitions=2,
                                   inference=lambda *a, **k: {"answer": "example"},
                                   clock=lambda: next(samples))
            self.assertEqual(result["runs"], 2)
            self.assertEqual(result["seconds"], [0.2, 0.4])
            self.assertEqual(result["device_used"], "cpu")

    def test_bounds_before_inference(self):
        with tempfile.TemporaryDirectory() as d:
            file = Path(d) / "fixture.pt"
            file.write_bytes(b"fixture")
            for kwargs in ({"repetitions": True}, {"repetitions": 21},
                           {"max_tokens": 0}, {"prompt": ""}):
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                    benchmark(file, **kwargs)


if __name__ == "__main__":
    unittest.main()
