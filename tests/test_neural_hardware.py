"""Read-only CUDA diagnostics never allocate GPU memory."""
import unittest
from unittest.mock import Mock
from backend.neural_hardware import hardware_report


class HardwareReportTests(unittest.TestCase):
    def test_cpu_fallback(self):
        torch = Mock()
        torch.cuda.is_available.return_value = False
        result = hardware_report(torch)
        self.assertEqual(result["device"], "cpu")
        self.assertIsNone(result["gpu_memory_bytes"])

    def test_cuda_properties_are_reported_not_guessed(self):
        torch = Mock()
        torch.cuda.is_available.return_value = True
        torch.cuda.get_device_properties.return_value = Mock(name="Fake GPU", total_memory=4 * 1024 ** 3)
        report = hardware_report(torch)
        self.assertEqual(report["device"], "cuda")
        self.assertEqual(report["gpu_memory_bytes"], 4 * 1024 ** 3)
        torch.cuda.get_device_properties.assert_called_once_with(0)


if __name__ == "__main__":
    unittest.main()
