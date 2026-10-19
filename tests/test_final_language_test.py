import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class FinalHeldoutAuditTests(unittest.TestCase):
    def test_sealed_test_once_and_lineage(self):
        try:
            import torch
        except ImportError:
            self.skipTest("PyTorch optional")
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            records = home / "records.json"
            entries = [{"prompt": "Привет номер " + str(i), "answer": "Ответ номер " + str(i),
                        "license": "synthetic", "source": "local-test", "consent": True}
                       for i in range(20)]
            records.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
            output = home / "run"
            train_cmd = [sys.executable, "scripts/run-language-experiment.py", "--records", str(records),
                         "--output", str(output), "--steps", "1", "--checkpoint-every", "1",
                         "--width", "32", "--heads", "4", "--layers", "1",
                         "--context", "128", "--max-merges", "8"]
            result = subprocess.run(train_cmd, cwd=root, text=True, capture_output=True, timeout=160)
            self.assertEqual(result.returncode, 0, result.stderr)
            from importlib.machinery import SourceFileLoader
            from importlib.util import spec_from_loader, module_from_spec
            loader = SourceFileLoader("final_language_test", str(root / "scripts/finalize-language-test.py"))
            spec = spec_from_loader(loader.name, loader)
            module = module_from_spec(spec)
            loader.exec_module(module)
            scored = module.finalize(records, output)
            self.assertGreater(scored["test"]["tokens"], 0)
            self.assertFalse(scored["auto_promoted"])
            with self.assertRaises(FileExistsError):
                module.finalize(records, output)
            rows = json.loads(records.read_text(encoding="utf-8"))
            rows[0]["answer"] += " изменён"
            records.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            (output / "final-test.json").unlink()
            with self.assertRaises(ValueError):
                module.finalize(records, output)


if __name__ == "__main__":
    unittest.main()
