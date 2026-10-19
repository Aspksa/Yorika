"""Self-learning loop: consented chat collection, owner ratings, export and version proposals."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import self_learning as sl
from backend import training_center as tc
from backend.storage import Store


def chat(pairs):
    history, ts = [], 1000
    for prompt, answer in pairs:
        history += [{"from": "me", "text": prompt, "ts": ts}, {"from": "bot", "text": answer, "ts": ts + 1}]
        ts += 2
    return history


class SelfLearningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = os.environ.get("YORIKA_HOME")
        os.environ["YORIKA_HOME"] = self.temp.name
        self.chat_dir = Path(self.temp.name) / "data"

    def tearDown(self):
        if self.old is None:
            os.environ.pop("YORIKA_HOME", None)
        else:
            os.environ["YORIKA_HOME"] = self.old
        self.temp.cleanup()

    def put_chat(self, history):
        with Store(self.chat_dir) as store:
            store.connection.execute(
                "INSERT INTO records(namespace,record_id,payload,updated_at) VALUES('chat','default',?,'t') "
                "ON CONFLICT(namespace,record_id) DO UPDATE SET payload=excluded.payload",
                (json.dumps({"history": history, "revision": 1}, ensure_ascii=False),))
            store.connection.commit()

    def test_collection_requires_consent(self):
        with self.assertRaises(ValueError):
            sl.collect(self.chat_dir)

    def test_filters_errors_secrets_and_duplicates(self):
        self.put_chat(chat([("Привет", "Привет! Рада тебя видеть."),
                            ("Как дела?", "Cloud.ru: превышено время ожидания ответа"),
                            ("Мой пароль: 12345", "Запомнила."),
                            ("Почта?", "Пиши на me@example.com")]))
        sl.set_collect(True)
        self.assertEqual(sl.collect(self.chat_dir)["added"], 1)
        self.assertEqual(sl.collect(self.chat_dir)["added"], 0)

    def test_only_rated_examples_are_exported_as_reviewed(self):
        self.put_chat(chat([("Вопрос %d" % i, "Ответ %d" % i) for i in range(14)]))
        sl.set_collect(True)
        sl.collect(self.chat_dir)
        items = sl.list_items("unrated", 0, 50)["items"]
        self.assertEqual(len(items), 14)
        with self.assertRaises(ValueError):
            sl.export()
        for item in items[:9]:
            sl.rate(item["id"], "up")
        sl.rate(items[9]["id"], "down", "Правильный ответ")
        sl.rate(items[10]["id"], "down")
        sl.delete(items[11]["id"])
        counts = sl.counts()
        self.assertEqual((counts["up"], counts["fixed"], counts["down"], counts["total"]), (9, 1, 1, 13))
        result = sl.export()
        records = json.loads((tc.folder() / "data" / result["name"]).read_text(encoding="utf-8"))
        self.assertEqual(len(records), 10)
        self.assertIn("Правильный ответ", [r["answer"] for r in records])
        self.assertTrue(all(r["quality_reviewed"] is True and r["consent"] is True for r in records))
        self.assertTrue(tc.check_data(result["name"])["ok"])
        # A deleted example never comes back on the next collection.
        self.assertEqual(sl.collect(self.chat_dir)["added"], 0)

    def test_finished_long_run_is_proposed_until_dismissed(self):
        run = tc.folder() / "runs" / "20260101-000000-long"
        run.mkdir(parents=True)
        tc._write(run / "run.json", {"id": run.name, "mode": "long"})
        tc._write(run / "progress.json", {"state": "finished", "steps": 50, "best_nll": 1.5})
        (run / "language-longrun.pt.best.pt").write_bytes(b"x")
        self.assertEqual(sl.proposal()["candidate"]["id"], run.name)
        sl.dismiss(run.name)
        self.assertIsNone(sl.proposal())

    def test_emergency_stop_requests_stop_for_running_jobs(self):
        run = tc.folder() / "runs" / "20260101-000000-long"
        run.mkdir(parents=True)
        tc._write(run / "run.json", {"id": run.name, "mode": "long"})
        tc._write(run / "progress.json", {"state": "running", "t": __import__("time").time()})
        self.assertEqual(tc.stop_all()["stopped"], [run.name])
        self.assertEqual(tc._read(run / "control.json")["request"], "stop")


if __name__ == "__main__":
    unittest.main()
