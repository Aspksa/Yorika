"""«Обучение» page backend: data gate, chunked training, pause/resume, explicit activation."""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import training_center as tc

try:
    import torch  # noqa: F401
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

TINY = {"width": 32, "heads": 2, "layers": 1, "context": 64, "max_merges": 16, "seed": 1, "checkpoint_every": 20}


def records(n, reviewed=True):
    rows = [{"prompt": "Вопрос номер %d?" % i, "answer": "Ответ %d." % i, "source": "test",
             "license": "synthetic", "consent": True} for i in range(n)]
    if reviewed:
        for row in rows:
            row.update(rights_reviewed_by="Тест", quality_reviewed=True)
    return rows


class TrainingCenterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = os.environ.get("YORIKA_HOME")
        os.environ["YORIKA_HOME"] = self.temp.name
        self.data = tc.folder() / "data"
        self.data.mkdir(parents=True)

    def tearDown(self):
        if self.old is None:
            os.environ.pop("YORIKA_HOME", None)
        else:
            os.environ["YORIKA_HOME"] = self.old
        self.temp.cleanup()

    def put(self, name, rows):
        (self.data / name).write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    def test_data_check_explains_problems_in_russian(self):
        self.put("dup.json", records(20) + records(1))
        self.put("small.json", records(50))
        self.assertIn("повторяющиеся", tc.check_data("dup.json")["reason"])
        small = tc.check_data("small.json")
        self.assertTrue(small["ok"])
        self.assertFalse(small["long_ready"])
        self.assertIn("10000", small["long_blocker"])
        with self.assertRaises(ValueError):
            tc.check_data("..\\secret.json")

    def test_long_training_requires_reviewed_corpus(self):
        self.put("small.json", records(50))
        with self.assertRaises(ValueError):
            tc.start("long", dataset="small.json", device="cpu", total_steps=200, hours=0.1, launch=False)
        self.assertEqual(tc.runs(), [])

    def test_folder_must_be_absolute_and_flags_onedrive(self):
        with self.assertRaises(ValueError):
            tc.set_folder("relative/path")
        target = Path(self.temp.name) / "OneDrive" / "train"
        tc.set_folder(str(target))
        self.assertTrue(tc.status()["onedrive"])

    def test_stale_worker_is_reported_as_interrupted(self):
        run = tc.folder() / "runs" / "20260101-000000-long"
        run.mkdir(parents=True)
        tc._write(run / "run.json", {"id": run.name, "mode": "long"})
        tc._write(run / "progress.json", {"state": "running", "t": time.time() - 3600})
        item = tc.runs()[0]
        self.assertEqual(item["state"], "interrupted")
        self.assertTrue(item["resumable"])

    @unittest.skipUnless(HAS_TORCH, "PyTorch not installed")
    def test_pilot_trains_and_cannot_become_active(self):
        old = tc.PILOT_SECONDS, tc.CHUNK_SECONDS
        tc.PILOT_SECONDS, tc.CHUNK_SECONDS = 4, 2
        try:
            run = tc.start("pilot", device="cpu", config=TINY, launch=False)["id"]
            self.assertEqual(tc.worker(run), 0)
        finally:
            tc.PILOT_SECONDS, tc.CHUNK_SECONDS = old
        item = tc.runs()[0]
        self.assertEqual(item["state"], "finished")
        self.assertGreater(item["steps"], 0)
        self.assertTrue(item["history"])
        with self.assertRaises(ValueError):
            tc.activate(run)
        answer = tc.compare([run], ["Сколько будет 2 плюс 3?"])
        self.assertEqual(len(answer["versions"][0]["answers"]), 1)

    @unittest.skipUnless(HAS_TORCH, "PyTorch not installed")
    def test_long_run_pauses_resumes_activates_and_rolls_back(self):
        from backend.active_brain import active_brain
        self.put("big.json", records(tc.MIN_LONG_RECORDS))
        old = tc.CHUNK_SECONDS
        tc.CHUNK_SECONDS = 1
        try:
            run = tc.start("long", dataset="big.json", device="cpu", total_steps=200, hours=0.1,
                           config=TINY, launch=False)["id"]
            tc._write(tc._run_dir(run) / "control.json", {"request": "pause"})
            tc.worker(run)
            paused = tc.runs()[0]
            self.assertEqual(paused["state"], "paused")
            self.assertTrue(paused["resumable"])
            progress = tc._read(tc._run_dir(run) / "progress.json")
            progress["state"] = "starting"
            tc._write(tc._run_dir(run) / "progress.json", progress)
            tc.worker(run)
        finally:
            tc.CHUNK_SECONDS = old
        done = tc.runs()[0]
        self.assertEqual(done["state"], "finished")
        self.assertEqual(done["steps"], 200)
        chosen = tc.activate(run)
        self.assertEqual(chosen["run"], run)
        self.assertTrue(active_brain(tc.folder()).name.startswith(run))
        self.assertIsNone(tc.rollback())
        self.assertFalse((tc.folder() / "active-brain.json").exists())


if __name__ == "__main__":
    unittest.main()
