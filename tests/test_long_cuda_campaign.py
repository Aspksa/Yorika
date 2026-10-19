import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cuda_campaign", ROOT / "scripts/run-long-cuda-campaign.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CampaignTests(unittest.TestCase):
    def records(self, path, reviewed=True):
        rows = [{"prompt": "Вопрос " + str(i), "answer": "Ответ " + str(i),
                 "source": "local synthetic test", "license": "synthetic", "consent": True,
                 "rights_reviewed_by": "fixture-author" if reviewed else "",
                 "quality_reviewed": reviewed} for i in range(12)]
        path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    def test_reject_unreviewed_and_missing_cuda(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "records.json"
            self.records(source, reviewed=False)
            with self.assertRaisesRegex(ValueError, "review"):
                module.campaign(source, root / "out", min_records=10, device="cpu",
                                total_steps=1)
            self.records(source)
            try:
                import torch
            except ImportError:
                self.skipTest("PyTorch optional")
            if not torch.cuda.is_available():
                with self.assertRaisesRegex(RuntimeError, "CUDA unavailable"):
                    module.campaign(source, root / "out", min_records=10, device="cuda",
                                    total_steps=1)

    def test_multi_session_cpu_smoke_and_receipt(self):
        try:
            import torch
        except ImportError:
            self.skipTest("PyTorch optional")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "records.json"
            self.records(source)
            output = root / "out"
            kwargs = dict(min_records=10, device="cpu", total_steps=2,
                          session_seconds=30, max_sessions=2, width=32,
                          heads=4, layers=1, context=128, max_merges=8,
                          checkpoint_every=1)
            result = module.campaign(source, output, **kwargs)
            self.assertTrue(result["completed"])
            self.assertEqual(result["last_step"], 2)
            receipts = list(output.glob("session-*.json"))
            self.assertEqual(len(receipts), 1)
            receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
            self.assertEqual(receipt["device"], "cpu")
            self.assertIsNone(receipt["peak_cuda_allocated_bytes"])
            with self.assertRaises(ValueError):
                module.campaign(source, output, width=64, **{k:v for k,v in kwargs.items() if k != "width"})


if __name__ == "__main__":
    unittest.main()
