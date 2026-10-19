"""Check that acceptance reporting fails closed and preserves check failures."""
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run-acceptance.py"
spec = importlib.util.spec_from_file_location("yorika_acceptance_runner", SCRIPT)
runner_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner_module)


class AcceptanceRunnerTests(unittest.TestCase):
    def test_all_checks_pass(self):
        calls = []
        def good(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, "ok", "")
        with tempfile.TemporaryDirectory() as folder:
            result = runner_module.execute(Path(folder), runner=good)
        self.assertTrue(result["passed"])
        self.assertEqual(len(calls), len(runner_module.COMMANDS))
        self.assertTrue(all(x["status"] == "passed" for x in result["results"]))

    def test_failure_does_not_skip_remaining_checks(self):
        calls = []
        def failed(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 1 if len(calls) == 2 else 0, "", "failed")
        with tempfile.TemporaryDirectory() as folder:
            result = runner_module.execute(Path(folder), runner=failed)
        self.assertFalse(result["passed"])
        self.assertEqual(len(calls), len(runner_module.COMMANDS))
        self.assertEqual(result["results"][1]["status"], "failed")

    def test_timeout_fails_closed(self):
        def timeout(command, **kwargs):
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        with tempfile.TemporaryDirectory() as folder:
            result = runner_module.execute(Path(folder), runner=timeout)
        self.assertFalse(result["passed"])
        self.assertTrue(all(x["status"] == "error" for x in result["results"]))


    def test_compact_log_preserves_both_failure_boundaries(self):
        original = "BEGIN: error context\\n" + ("x" * 30000) + "\\nEND: final traceback"
        rendered = runner_module.compact_log(original, limit=2000)
        self.assertIn("BEGIN: error context", rendered)
        self.assertIn("END: final traceback", rendered)
        self.assertIn("middle of output omitted", rendered)
        self.assertLess(len(rendered), len(original))

    def test_compact_log_does_not_modify_short_output(self):
        report = "OK\\nТест памяти прошёл\\n"
        self.assertEqual(runner_module.compact_log(report, limit=2000), report)


if __name__ == "__main__":
    unittest.main()
