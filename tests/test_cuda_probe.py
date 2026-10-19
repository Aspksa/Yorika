import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "scripts/probe-language-cuda.py"
spec = importlib.util.spec_from_file_location("cuda_probe", PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ProbeTests(unittest.TestCase):
    def test_honest_probe(self):
        report = module.probe()
        self.assertEqual(report["schema"], "yorika-cuda-probe-v1")
        self.assertIs(report["real_training_completed"], False)
        self.assertIn("cuda_usable", report)
        if report["cuda_usable"]:
            self.assertGreater(report["vram_bytes"], 0)
            self.assertGreaterEqual(report["probe_seconds"], 0)

    def test_no_false_training_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "report.json"
            result = module.probe()
            path.write_text(json.dumps(result), encoding="utf-8")
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn("completed_steps", saved)
            self.assertNotIn("elapsed_hours", saved)
            self.assertFalse(saved["real_training_completed"])


if __name__ == "__main__":
    unittest.main()
