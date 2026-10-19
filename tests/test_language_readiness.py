import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("readiness", ROOT / "scripts/verify-language-readiness.py")
readiness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(readiness)


class ReadinessTests(unittest.TestCase):
    def make_records(self, path):
        rows = [{"prompt": "Вопрос номер " + str(i), "answer": "Ответ номер " + str(i),
                 "license": "synthetic", "source": "unit-test", "consent": True}
                for i in range(20)]
        path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        return rows

    def test_missing_real_world_evidence_stays_open(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "corpus.json"
            self.make_records(path)
            result = readiness.inspect(path)
            self.assertFalse(result["all_ready"])
            self.assertFalse(result["corpus"]["ready"])
            self.assertFalse(result["gpu_training"]["ready"])
            self.assertFalse(result["dialogue_improvement"]["ready"])

    def test_fake_gpu_and_fake_human_scores_cannot_close_milestones(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "corpus.json"
            self.make_records(path)
            gpu = root / "gpu.json"
            dialogue = root / "human.json"
            gpu.write_text(json.dumps({"schema": "yorika-gpu-evidence-v1",
                                      "device_type": "cpu", "elapsed_hours": 0,
                                      "completed_steps": 3, "operator_verified": False}),
                           encoding="utf-8")
            dialogue.write_text(json.dumps({"schema": "yorika-dialogue-evidence-v1",
                                           "blind_human_review": False,
                                           "independent_prompts": 0,
                                           "candidate_wins": 0, "baseline_wins": 0}),
                                encoding="utf-8")
            result = readiness.inspect(path, gpu, dialogue)
            self.assertFalse(result["all_ready"])

    def test_unconsented_records_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "corpus.json"
            rows = self.make_records(path)
            rows[0]["consent"] = False
            path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ValueError):
                readiness.inspect(path)


if __name__ == "__main__":
    unittest.main()
