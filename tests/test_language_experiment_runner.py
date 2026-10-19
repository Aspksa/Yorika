"""Acceptance of the explicit consent-only experiment CLI."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ExperimentRunnerTests(unittest.TestCase):
    def test_run_resume_and_test_isolation(self):
        try:
            import torch
        except ImportError:
            self.skipTest("CPU PyTorch optional")
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            data = folder / "records.json"
            rows = [{"prompt": "Привет " + str(i), "answer": "Ответ " + str(i),
                     "source": "verified-synthetic-fixture", "license": "synthetic",
                     "consent": True} for i in range(20)]
            data.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            dest = folder / "experiment"
            command = [sys.executable, "scripts/run-language-experiment.py",
                       "--records", str(data), "--output", str(dest),
                       "--steps", "2", "--checkpoint-every", "1",
                       "--width", "32", "--heads", "4", "--layers", "1",
                       "--context", "128", "--max-merges", "8"]
            proc = subprocess.run(command, cwd=root, capture_output=True, text=True,
                                  timeout=150)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads((dest / "experiment.json").read_text(encoding="utf-8"))
            self.assertTrue(report["test_reserved"])
            self.assertFalse(report["test_evaluated"])
            self.assertEqual(report["training"]["steps"], 2)
            self.assertTrue((dest / "language-longrun.pt.best.pt").exists())
            repeat = subprocess.run(command, cwd=root, capture_output=True, text=True,
                                    timeout=150)
            self.assertNotEqual(repeat.returncode, 0)
            self.assertIn("already exists", repeat.stderr)

    def test_reject_unconsented_data(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            path = folder / "records.json"
            rows = [{"prompt": "Вопрос " + str(i), "answer": "Ответ",
                     "source": "synthetic", "license": "synthetic",
                     "consent": i != 0} for i in range(10)]
            path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run([sys.executable, "scripts/run-language-experiment.py",
                                     "--records", str(path), "--output", str(folder / "out"),
                                     "--steps", "1"], cwd=root, capture_output=True,
                                    text=True, timeout=40)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((folder / "out" / "language-longrun.pt").exists())


if __name__ == "__main__":
    unittest.main()
