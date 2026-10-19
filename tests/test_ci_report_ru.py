"""Checks Russian CI reporting against missing, failed and passing input."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / "scripts/ci-report-ru.py"
SPEC = importlib.util.spec_from_file_location("ci_report_ru", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RussianReportTests(unittest.TestCase):
    def test_missing_report_is_failure(self):
        text, passed = MODULE.build_report("/nonexistent/yorika-report.json")
        self.assertFalse(passed)
        self.assertIn("СБОЙ", text)

    def test_real_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "results.json"
            file.write_text(json.dumps({"passed": True, "results": [
                {"name": "plan", "status": "passed"}]}), encoding="utf-8")
            text, passed = MODULE.build_report(file)
            self.assertTrue(passed)
            self.assertIn("План задач", text)
            text, passed = MODULE.build_report(file, extra=[("Windows", "skipped")])
            self.assertFalse(passed)
            self.assertIn("ПРОПУЩЕНО", text)

    def test_overall_failure_not_hidden_by_green_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "mismatch.json"
            file.write_text(json.dumps({"passed": False, "results": [
                {"name": "plan", "status": "passed"}]}), encoding="utf-8")
            text, passed = MODULE.build_report(file)
            self.assertFalse(passed)
            self.assertIn("Общий итог", text)

    def test_bad_status_is_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "bad.json"
            file.write_text('{"results":[{"name":"bad","status":"unknown"}]}', encoding="utf-8")
            _, passed = MODULE.build_report(file)
            self.assertFalse(passed)


if __name__ == "__main__":
    unittest.main()
