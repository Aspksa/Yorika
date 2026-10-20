"""Checkpoint files every size can read back, and an exam that fails never lets a version in."""
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import continual
from backend import schedule
from backend import training_center as tc
from tests.test_learning_lab import LabBase, dataset
from tests.test_living_brain import LAB

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


@unittest.skipUnless(HAS_TORCH, "PyTorch optional")
class CheckpointSafetyTests(LabBase):
    def setUp(self):
        super().setUp()
        schedule.set_grid("always")

    def train(self, name, config=LAB):
        run = tc.start("long", dataset=name, device="cpu", total_steps=100, hours=0.1, config=config, launch=False)["id"]
        tc.worker(run)
        time.sleep(1.1)
        return tc._summary(tc._run_dir(run))

    def test_sizes_fit_the_limits(self):
        from backend.neural_language_benchmark import MAX_WEIGHTS_BYTES as READ_LIMIT
        from backend.neural_language_bpe_v2 import make_model
        from backend.neural_language_longrun import MAX_TRAINING_BYTES, MAX_WEIGHTS_BYTES
        self.assertEqual(READ_LIMIT, MAX_WEIGHTS_BYTES)
        for size in ("m", "l"):
            c = tc.config_for(size)
            model = make_model(torch, vocab_size=261 + c["max_merges"], width=c["width"], heads=c["heads"],
                               layers=c["layers"], context=c["context"], arch=c.get("arch"))
            weights = sum(p.numel() for p in model.parameters()) * 4
            self.assertLess(weights * 1.2, MAX_WEIGHTS_BYTES, size)       # the answering copy
            self.assertLess(weights * 3 * 1.2, MAX_TRAINING_BYTES, size)  # weights + Adam's two moments

    def test_best_file_is_compact_and_the_training_file_resumes(self):
        from backend.neural_language_benchmark import load_candidate
        item = self.train(dataset())
        path = tc._run_dir(item["id"])
        full = torch.load(path / "language-longrun.pt", map_location="cpu", weights_only=True)
        best = torch.load(path / "language-longrun.pt.best.pt", map_location="cpu", weights_only=True)
        self.assertIn("optimizer", full)
        self.assertFalse({"optimizer", "rng", "scaler", "cuda_rng"} & set(best))
        self.assertLess((path / "language-longrun.pt.best.pt").stat().st_size, (path / "language-longrun.pt").stat().st_size / 2)
        load_candidate(path / "language-longrun.pt.best.pt")
        # The run continues from the training file after more time is allowed.
        info = tc._read(path / "run.json")
        info["time_limit"] += 3
        info["total_steps"] += 40
        tc._write(path / "run.json", info)
        progress = tc._read(path / "progress.json")
        progress["state"] = "paused"
        tc._write(path / "progress.json", progress)
        self.assertEqual(tc.worker(item["id"]), 0)
        self.assertGreater(tc._summary(path)["steps"], item["steps"])

    def test_failed_exam_blocks_automatic_replacement(self):
        name = dataset()
        base = self.train(name)
        tc.activate(base["id"])
        candidate = self.train(name, dict(LAB, seed=2))
        continual.set_settings(True, auto_activate=True)
        with mock.patch("backend.neural_language_longrun.score_checkpoint", side_effect=ValueError("Missing or oversized checkpoint")):
            verdict = continual.judge(candidate["id"])
        self.assertEqual(verdict["result"], "rolled_back")
        self.assertIn("экзамен не удался", verdict["why"])
        self.assertEqual(tc.active()["run"], base["id"])


if __name__ == "__main__":
    unittest.main()
