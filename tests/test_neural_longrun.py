"""Long-run resume verifies progress and never activates weights."""
import tempfile
import unittest
from pathlib import Path
from backend.neural_longrun import run_long_training


class LongRunTests(unittest.TestCase):
    def test_recovery_from_time_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            calls = []
            def trainer(examples, output, **kwargs):
                Path(output).write_bytes(b"x" * 2048)
                calls.append(kwargs["steps"])
                return {"steps": kwargs["steps"]}
            def resumer(examples, source, output, **kwargs):
                Path(output).write_bytes(b"y" * 2048)
                calls.append(kwargs["additional_steps"])
                prior = int(Path(source).stem.split("-")[1])
                return {"steps": prior + kwargs["additional_steps"]}
            ticks = iter([0, 0.1, 2.0])
            first = run_long_training([("a", "b")], Path(folder), total_steps=4, interval=2,
                                      max_seconds=1, trainer=trainer, resumer=resumer,
                                      clock=lambda: next(ticks))
            self.assertEqual(first["completed_steps"], 2)
            self.assertFalse(first["finished"])
            second = run_long_training([("a", "b")], Path(folder), total_steps=4, interval=2,
                                       trainer=trainer, resumer=resumer)
            self.assertTrue(second["finished"])
            self.assertEqual(calls, [2, 2])
            self.assertFalse(second["active_brain_changed"])

    def test_bad_config(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                run_long_training([], folder, total_steps=5, interval=0)


if __name__ == "__main__":
    unittest.main()
