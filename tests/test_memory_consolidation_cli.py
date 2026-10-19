"""CLI safety regression: preview never deletes; confirmation required to apply."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from backend.storage import Store

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "consolidate-memory.py"


class ConsolidationCliTests(unittest.TestCase):
    def test_preview_requires_explicit_double_opt_in_to_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with Store(root) as db:
                db.remember("a", "Запомни план", "user", source_id="same")
                db.remember("b", "Запомни план", "user", source_id="same")
            def run(*args):
                return subprocess.run([sys.executable, str(SCRIPT), "--directory", str(root), *args],
                                      cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
            preview = run()
            self.assertEqual(preview.returncode, 0, preview.stderr)
            self.assertEqual(json.loads(preview.stdout)["duplicates"], 1)
            self.assertEqual(json.loads(preview.stdout)["removed"], 0)
            self.assertNotIn("Запомни", preview.stdout)
            with Store(root) as db:
                self.assertIsNotNone(db.get("memories", "b"))
            self.assertNotEqual(run("--apply").returncode, 0)
            self.assertNotEqual(run("--confirm").returncode, 0)
            applied = run("--apply", "--confirm")
            self.assertEqual(applied.returncode, 0, applied.stderr)
            self.assertEqual(json.loads(applied.stdout)["removed"], 1)
            with Store(root) as db:
                self.assertIsNone(db.get("memories", "b"))


if __name__ == "__main__":
    unittest.main()
