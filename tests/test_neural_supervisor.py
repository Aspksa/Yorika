"""Supervisor retry policy prevents infinite loops and keeps brain unchanged."""
import tempfile
import unittest
from backend.neural_supervisor import supervise


class SupervisorTests(unittest.TestCase):
    def test_retry_once_and_complete(self):
        calls = []
        def runner(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("simulated transient failure")
            return {"finished": True, "completed_steps": 4}
        with tempfile.TemporaryDirectory() as folder:
            result = supervise([], folder, total_steps=4, runner=runner, sleep=lambda _: None)
        self.assertTrue(result["finished"])
        self.assertEqual(result["restarts"], 1)
        self.assertFalse(result["active_brain_changed"])

    def test_permanent_failure_is_bounded(self):
        def broken(*args, **kwargs):
            raise OSError("failure")
        with tempfile.TemporaryDirectory() as folder:
            result = supervise([], folder, total_steps=2, max_restarts=2,
                               runner=broken, sleep=lambda _: None)
        self.assertFalse(result["finished"])
        self.assertEqual(len(result["failures"]), 3)

    def test_invalid_limits(self):
        with self.assertRaises(ValueError):
            supervise([], ".", total_steps=2, max_restarts=True)


if __name__ == "__main__":
    unittest.main()
