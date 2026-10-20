"""Power self-learning: speed, exam, pretraining, Cloud.ru teacher, smart order and the night cycle."""
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import night_cycle as night
from backend import self_learning as sl
from backend import teacher
from backend import training_center as tc

try:
    import torch  # noqa: F401
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

TINY = {"width": 32, "heads": 2, "layers": 1, "context": 64, "max_merges": 16, "seed": 1, "checkpoint_every": 20,
        "batch_size": 4, "accumulate": 2, "precision": "auto"}


class FakeCloud:
    """Answers like Cloud.ru: JSON pairs for generation, a verdict for review; records every request."""
    def __init__(self):
        self.requests = []

    def __call__(self, request, timeout):
        body = json.loads(request.data.decode("utf-8"))
        self.requests.append(body)
        ask = body["messages"][-1]["content"]
        if ask.startswith("Оцени"):
            content = '{"score": 2, "why": "неточно", "better": "Лучше так."}'
        else:
            n = len(self.requests)
            content = "Вот: " + json.dumps([{"prompt": "Вопрос %d-%d?" % (n, k), "answer": "Ответ %d." % k}
                                           for k in range(5)], ensure_ascii=False)
        data = {"choices": [{"message": {"content": content}}], "usage": {"total_tokens": 500}}
        stream = io.BytesIO(json.dumps(data, ensure_ascii=False).encode("utf-8"))
        stream.__enter__ = lambda *a: stream
        stream.__exit__ = lambda *a: None
        return stream


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.saved = {k: os.environ.get(k) for k in ("YORIKA_HOME", "YORIKA_CLOUD_RU_API_KEY")}
        os.environ["YORIKA_HOME"] = self.temp.name
        os.environ.pop("YORIKA_CLOUD_RU_API_KEY", None)
        (tc.folder() / "data").mkdir(parents=True)

    def tearDown(self):
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.temp.cleanup()

    def items(self, n, rating=None):
        store = sl._load()
        for i in range(n):
            store["items"].append({"id": "i%d" % i, "prompt": "Сколько будет %d?" % i, "answer": "Будет %d." % i,
                                   "ts": i, "rating": rating, "correction": None, "source": "yorika-chat"})
        sl._save(store)


class TeacherTests(Base):
    def test_needs_confirmation_key_and_fits_limits(self):
        with self.assertRaisesRegex(ValueError, "Подтвердите"):
            teacher.start("generate", 10)
        with self.assertRaisesRegex(ValueError, "Ключ"):
            teacher.start("generate", 10, confirm=True, launch=False)
        os.environ["YORIKA_CLOUD_RU_API_KEY"] = "k"
        plan = teacher.estimate("generate", 10)
        self.assertEqual(plan["requests"], 2)
        self.assertTrue(plan["fits"])
        teacher.set_limits(2000, 3000)
        with self.assertRaisesRegex(ValueError, "лимит"):
            teacher.start("generate", 50, confirm=True, launch=False)
        with self.assertRaises(ValueError):
            teacher.set_limits(5000, 3000)

    def test_generate_adds_unrated_examples_and_counts_tokens(self):
        os.environ["YORIKA_CLOUD_RU_API_KEY"] = "k"
        cloud = FakeCloud()
        teacher.start("generate", 10, confirm=True, launch=False, topics=["погода"])
        state = teacher.run_job(opener=cloud)
        self.assertEqual(state["state"], "finished")
        self.assertEqual(state["added"], 10)
        self.assertEqual(teacher.used_this_month(), 1000)
        self.assertIn("погода", cloud.requests[0]["messages"][-1]["content"])
        items = sl._load()["items"]
        self.assertTrue(all(i["rating"] is None and i["source"] == "teacher" for i in items))
        self.assertEqual(sl.counts()["teacher"], 10)

    def test_stops_at_budget_and_on_request(self):
        os.environ["YORIKA_CLOUD_RU_API_KEY"] = "k"
        teacher.start("generate", 50, confirm=True, launch=False, budget=2000)
        state = teacher.run_job(opener=FakeCloud())
        self.assertEqual(state["state"], "limit")
        self.assertLessEqual(state["tokens"], 2000)
        teacher.start("generate", 50, confirm=True, launch=False)
        teacher.stop()
        state = teacher.run_job(opener=FakeCloud())
        self.assertEqual(state["state"], "stopped")

    def test_review_then_owner_confirms_verdicts_and_export_marks_them(self):
        os.environ["YORIKA_CLOUD_RU_API_KEY"] = "k"
        self.items(12)
        teacher.start("review", 12, confirm=True, launch=False)
        teacher.run_job(opener=FakeCloud())
        self.assertEqual(sl.counts()["verdicts"], 12)
        self.assertEqual(sl.list_items("teacher")["matching"], 12)
        self.assertEqual(sl.counts()["ready"], 0)  # a verdict alone is not a review by the owner
        result = teacher.accept_verdicts()
        self.assertEqual(result["fixed"], 12)
        exported = sl.export()
        rows = json.loads((tc.folder() / "data" / exported["name"]).read_text(encoding="utf-8"))
        self.assertTrue(all(r["teacher_reviewed"] and r["answer"] == "Лучше так." for r in rows))

    def test_selfplay_starts_from_rejected_answers(self):
        os.environ["YORIKA_CLOUD_RU_API_KEY"] = "k"
        with self.assertRaisesRegex(ValueError, "слабых"):
            teacher.estimate("selfplay", 5)
        self.items(5, rating="down")
        cloud = FakeCloud()
        teacher.start("selfplay", 5, confirm=True, launch=False)
        state = teacher.run_job(opener=cloud)
        self.assertEqual(state["added"], 5)
        self.assertIn("ошиблась", cloud.requests[0]["messages"][-1]["content"])
        self.assertTrue(any(i["source"] == "selfplay" for i in sl._load()["items"]))
        rows = [r for r in sl._load()["items"] if r["source"] == "selfplay"]
        for row in rows:
            sl.rate(row["id"], "up")
        self.items(0)
        store = sl._load()
        for row in store["items"]:
            if row["rating"] == "down":
                row["correction"] = "Правильно."
        sl._save(store)
        exported = sl.export()
        data = json.loads((tc.folder() / "data" / exported["name"]).read_text(encoding="utf-8"))
        self.assertEqual({r["license"] for r in data}, {"synthetic", "user-consent"})

    def test_parsers_drop_bad_rows(self):
        self.assertEqual(teacher.parse_pairs("нет json"), [])
        self.assertEqual(teacher.parse_pairs('[{"prompt": "a@b.ru", "answer": "x"}, {"prompt": "Да?", "answer": "Да."}]'),
                         [("Да?", "Да.")])
        self.assertIsNone(teacher.parse_review('{"score": 9}'))
        self.assertIsNone(teacher.parse_review('{"score": 5, "better": "x"}')["better"])


@unittest.skipUnless(HAS_TORCH, "PyTorch optional")
class TrainingPowerTests(Base):
    def test_pretrain_then_dialogue_from_it_with_exam(self):
        texts = tc.folder() / "data" / "тексты"
        texts.mkdir(parents=True)
        paragraphs = ["Абзац номер %d. Лиса бежала по лесу и думала о снеге и о звёздах." % i for i in range(1200)]
        (texts / "сказки.txt").write_text("\n\n".join(paragraphs), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Отметьте"):
            tc.pretrain_corpus()
        with self.assertRaisesRegex(ValueError, "права"):
            tc.approve_text("сказки.txt", "unknown")
        tc.approve_text("сказки.txt", "public-domain")
        self.assertTrue(tc.texts()["files"][0]["approved"])
        run = tc.start("pretrain", device="cpu", total_steps=100, hours=0.1, config=TINY, launch=False)["id"]
        tc.worker(run)
        done = tc._summary(tc._run_dir(run))
        self.assertEqual(done["state"], "finished")
        self.assertIsNotNone(done["exam_nll"])
        with self.assertRaisesRegex(ValueError, "Предобучение"):
            tc.activate(run)
        rows = [{"prompt": "Вопрос %d?" % i, "answer": "Ответ %d." % i, "source": "t", "license": "synthetic",
                 "consent": True, "rights_reviewed_by": "т", "quality_reviewed": True} for i in range(tc.MIN_LONG_RECORDS)]
        (tc.folder() / "data" / "big.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        long_run = tc.start("long", dataset="big.json", device="cpu", total_steps=100, hours=0.1, config=TINY,
                            launch=False, base=run)["id"]
        tc.worker(long_run)
        item = tc._summary(tc._run_dir(long_run))
        self.assertEqual(item["state"], "finished")
        self.assertEqual(item["base"], run)
        self.assertGreater(item["exam_count"], 0)
        # Editing an approved text withdraws the approval.
        (texts / "сказки.txt").write_text("другое", encoding="utf-8")
        self.assertFalse(tc.texts()["files"][0]["approved"])

    def test_batched_steps_count_examples_and_smart_order_needs_a_model(self):
        self.items(5)
        with self.assertRaisesRegex(ValueError, "обучите"):
            sl.list_items("uncertain")
        run = tc.start("pilot", device="cpu", config=TINY, launch=False)["id"]
        old = tc.CHUNK_SECONDS
        tc.CHUNK_SECONDS = 1
        try:
            tc._write(tc._run_dir(run) / "control.json", {"request": "stop"})
            tc.worker(run)
            progress = tc._read(tc._run_dir(run) / "progress.json")
            progress["state"] = "starting"
            tc._write(tc._run_dir(run) / "progress.json", progress)
            run_info = tc._read(tc._run_dir(run) / "run.json")
            run_info["time_limit"] = 3
            tc._write(tc._run_dir(run) / "run.json", run_info)
            tc.worker(run)
        finally:
            tc.CHUNK_SECONDS = old
        item = tc._summary(tc._run_dir(run))
        self.assertEqual(item["batch_size"], 4)
        self.assertEqual(item["precision"], "fp32")
        self.assertGreater(item["examples_speed"], item["speed"])
        listing = sl.list_items("uncertain")
        doubts = [i["doubt"] for i in listing["items"]]
        self.assertEqual(doubts, sorted(doubts, reverse=True))


class NightTests(Base):
    def test_schedule_command_and_bounds(self):
        self.assertEqual(night.schedule_command(False, "02:00")[:2], ["schtasks", "/Delete"])
        create = night.schedule_command(True, "03:30")
        self.assertIn("03:30", create)
        self.assertTrue(create[-1].endswith('night-run.cmd"'))
        self.assertLessEqual(len(create[-1]), 261)
        with self.assertRaises(ValueError):
            night.set_settings(True, "25:00", apply=False)
        with self.assertRaises(ValueError):
            night.set_settings(True, "02:00", teacher_tokens=10 ** 9, apply=False)
        saved = night.set_settings(True, "02:30", hours=2, teacher_tokens=5000, apply=False)
        self.assertTrue(saved["enabled"])

    @unittest.skipUnless(HAS_TORCH, "starting a run needs PyTorch")
    def test_night_run_collects_teaches_exports_and_starts_training(self):
        os.environ["YORIKA_CLOUD_RU_API_KEY"] = "k"
        self.assertEqual(night.run(launch=False)["steps"][0]["result"], "выключен")
        night.set_settings(True, "02:00", hours=1, teacher_tokens=3000, selfplay=10, apply=False)
        store = sl._load()
        for i in range(tc.MIN_LONG_RECORDS + 1):
            store["items"].append({"id": "n%d" % i, "prompt": "Ночной вопрос %d?" % i, "answer": "Ответ %d." % i,
                                   "ts": i, "rating": "up" if i else "down", "correction": None,
                                   "source": "yorika-chat"})
        sl._save(store)
        entry = night.run(launch=False, opener=FakeCloud())
        steps = {s["step"]: s["result"] for s in entry["steps"]}
        self.assertIn("сбор выключен", steps["collect"])
        self.assertIn("самоигра", steps["teacher"])
        self.assertIn("опыт-", steps["export"])
        self.assertIn("запущено обучение", steps["train"])
        self.assertLessEqual(teacher.used_this_month(), 3000)
        self.assertEqual(tc.runs()[0]["mode"], "long")
        self.assertEqual(len(night.log()), 2)


if __name__ == "__main__":
    unittest.main()
