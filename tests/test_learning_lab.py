"""Model sizes, sandbox series, not forgetting, honesty, tools, blind checks, lesson packs and several teachers."""
import json
import os
import sys
import tempfile
import time
import unittest
from unittest import mock
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import blind
from backend import honesty
from backend import night_cycle as night
from backend import self_learning as sl
from backend import teacher
from backend import tools
from backend import training_center as tc
from tests.test_power_learning import TINY, Base, FakeCloud

try:
    import torch  # noqa: F401
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


def dataset(name="big.json", n=None):
    rows = [{"prompt": "Вопрос %d?" % i, "answer": "Ответ %d." % i, "source": "t", "license": "synthetic",
             "consent": True, "rights_reviewed_by": "т", "quality_reviewed": True}
            for i in range(n or tc.MIN_LONG_RECORDS)]
    (tc.folder() / "data" / name).write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return name


class LabBase(Base):
    def setUp(self):
        super().setUp()
        self.saved_local = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = self.temp.name

    def tearDown(self):
        if self.saved_local is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = self.saved_local
        super().tearDown()


class SizeAndSeriesTests(LabBase):
    def test_sizes_have_growing_width_and_layers(self):
        widths = [tc.config_for(s)["width"] for s in ("s", "m", "l")]
        self.assertEqual(widths, sorted(widths))
        self.assertLess(tc.config_for("s")["layers"], tc.config_for("l")["layers"])
        with self.assertRaises(ValueError):
            tc.config_for("xl")

    def test_series_runs_sizes_one_after_another(self):
        name = dataset()
        with self.assertRaisesRegex(ValueError, "двух до трёх"):
            tc.start_series(name, ["s"], device="cpu", launch=False)
        with self.assertRaisesRegex(ValueError, "двух до трёх"):
            tc.start_series(name, ["s", "s"], device="cpu", launch=False)
        plan = tc.start_series(name, ["s", "m"], device="cpu", total_steps=100, hours_each=0.1, launch=False)
        self.assertEqual(plan["queue"], ["m"])
        first = tc._summary(tc._run_dir(plan["first"]))
        self.assertEqual((first["size"], first["series"]), ("s", plan["series"]))
        # A finished run starts the next size; the last one leaves the queue empty.
        progress = tc._read(tc._run_dir(plan["first"]) / "progress.json") or {}
        progress["state"] = "finished"
        tc._write(tc._run_dir(plan["first"]) / "progress.json", progress)
        time.sleep(1.1)  # run ids are per second
        second = tc._continue_series(plan["first"])
        self.assertIsNotNone(second)
        self.assertEqual(tc._summary(tc._run_dir(second))["size"], "m")
        self.assertEqual(tc.series()["queue"], [])
        self.assertIsNone(tc._continue_series(second))

    def test_stop_all_clears_the_queue(self):
        name = dataset()
        tc.start_series(name, ["s", "m", "l"], device="cpu", total_steps=100, hours_each=0.1, launch=False)
        tc.stop_all()
        self.assertEqual(tc.series()["queue"], [])

    def test_night_can_run_a_sandbox(self):
        with self.assertRaises(ValueError):
            night.set_settings(True, "02:00", sizes=["s", "xl"], apply=False)
        saved = night.set_settings(True, "02:00", hours=4, sizes=["s", "m"], apply=False)
        self.assertEqual(saved["sizes"], ["s", "m"])
        store = sl._load()
        for i in range(tc.MIN_LONG_RECORDS):
            store["items"].append({"id": "n%d" % i, "prompt": "Ночь %d?" % i, "answer": "Да %d." % i, "ts": i,
                                   "rating": "up", "correction": None, "source": "yorika-chat"})
        sl._save(store)
        # Outside the study grid the night uses its own 4 hours; inside it, the hours left would depend on the clock.
        with mock.patch("backend.schedule.hours_left", lambda *a, **k: 0):
            steps = {s["step"]: s["result"] for s in night.run(launch=False)["steps"]}
        self.assertIn("песочница", steps["train"])
        self.assertEqual(tc.series()["hours_each"], 2.0)


class HonestyAndToolsTests(LabBase):
    def test_exam_and_lessons_never_share_questions(self):
        self.assertFalse(set(honesty.EXAM) & {q for q, _ in honesty.lessons()})
        self.assertTrue(all(honesty.is_honest(a) for _, a in honesty.lessons()))
        self.assertTrue(honesty.is_honest("Честно, я не знаю."))
        self.assertFalse(honesty.is_honest("Выиграет номер 42."))

    def test_calculator_is_exact_and_refuses_code(self):
        self.assertEqual(tools.calc("2+2*2"), "6")
        self.assertEqual(tools.calc("7/2"), "3,5")
        self.assertEqual(tools.calc("12×3"), "36")
        for bad in ("__import__('os')", "2**99999", "1/0", "", "a+1"):
            with self.assertRaises(ValueError):
                tools.calc(bad)

    def test_run_tools_replaces_calls(self):
        moment = datetime(2026, 10, 19, 14, 5)
        text, calls = tools.run_tools("Считаю: [[calc:15*4]]. Сейчас [[time:]].", moment=moment)
        self.assertEqual(text, "Считаю: 60. Сейчас 19.10.2026, 14:05, понедельник.")
        self.assertEqual([c["tool"] for c in calls], ["calc", "time"])
        text, _ = tools.run_tools("[[calc:1/0]]")
        self.assertIn("посчитать", text)

    def test_memory_tool_reads_memory(self):
        from backend.storage import Store
        with Store() as db:
            db.remember("m1", "У пользователя собака по имени Рыжик", "test")
        text, calls = tools.run_tools("Помню: [[memory:собака]]")
        self.assertIn("Рыжик", text)
        self.assertEqual(calls[0]["tool"], "memory")

    def test_tool_lessons_are_well_formed(self):
        pairs = tools.lessons(120)
        self.assertEqual(len(pairs), 120)
        self.assertEqual(len({p for p, _ in pairs}), 120)
        for _, answer in pairs:
            self.assertRegex(answer, tools.CALL)
            self.assertNotIn("(", tools.run_tools(answer)[0].replace("[[", ""))

    def test_packs_need_confirmation_and_are_ready_for_export(self):
        preview = sl.pack_preview("honesty")
        self.assertEqual(preview["count"], len(honesty.LESSONS))
        with self.assertRaisesRegex(ValueError, "Подтвердите"):
            sl.add_pack("tools")
        self.assertEqual(sl.add_pack("tools", True)["added"], 120)
        self.assertEqual(sl.add_pack("tools", True)["added"], 0)
        with self.assertRaises(ValueError):
            sl.pack_preview("всё")
        self.assertEqual(sl.counts()["ready"], 120)


class TeacherLabTests(LabBase):
    def test_several_teachers_learn_which_one_the_owner_prefers(self):
        with self.assertRaises(ValueError):
            teacher.set_models(["плохо имя"])
        teacher.set_models(["a/one", "b/two"])
        self.assertEqual(teacher.models(), ["a/one", "b/two"])
        self.assertEqual({teacher.pick_model("погода", n) for n in range(2)}, {"a/one", "b/two"})
        store = sl._load()
        for i in range(teacher.MIN_RATED):
            for model, rating in (("a/one", "down"), ("b/two", "up")):
                store["items"].append({"id": "%s%d" % (model, i), "prompt": "%s %d" % (model, i), "answer": "x",
                                       "ts": i, "rating": rating, "correction": "y" if rating == "down" else None,
                                       "source": "teacher", "teacher_model": model, "topic": "погода"})
        sl._save(store)
        self.assertEqual(teacher.model_stats()["b/two"]["погода"], [teacher.MIN_RATED, teacher.MIN_RATED])
        self.assertEqual(teacher.pick_model("погода", 0), "b/two")
        self.assertEqual(teacher.pick_model("погода", 1), "b/two")
        teacher.set_limits(5000, 50000)
        self.assertEqual(teacher.settings()["models"], ["a/one", "b/two"])

    def test_teacher_choice_reaches_the_request(self):
        os.environ["YORIKA_CLOUD_RU_API_KEY"] = "k"
        teacher.set_models(["a/one", "b/two"])
        cloud = FakeCloud()
        teacher.start("generate", 10, confirm=True, launch=False, topics=["погода"])
        teacher.run_job(opener=cloud)
        self.assertEqual([r["model"] for r in cloud.requests], ["a/one", "b/two"])
        self.assertEqual({i["teacher_model"] for i in sl._load()["items"]}, {"a/one", "b/two"})

    def test_honesty_and_memory_tasks(self):
        os.environ["YORIKA_CLOUD_RU_API_KEY"] = "k"
        teacher.start("honesty", 5, confirm=True, launch=False)
        cloud = FakeCloud()
        teacher.run_job(opener=cloud)
        self.assertIn("не знаю", cloud.requests[0]["messages"][-1]["content"])
        self.assertEqual(sl.counts()["teacher"], 5)
        with self.assertRaisesRegex(ValueError, "памяти"):
            teacher.estimate("memory", 3)
        from backend.storage import Store
        with Store() as db:
            db.remember("m1", "Пользователь любит чай с мятой", "test")
        plan = teacher.estimate("memory", 3)
        self.assertTrue(plan["sends_memory"])
        self.assertEqual(plan["count"], 1)
        teacher.start("memory", 3, confirm=True, launch=False)
        state = teacher.run_job(opener=cloud)
        self.assertEqual(state["state"], "finished")
        self.assertIn("чай с мятой", cloud.requests[-1]["messages"][-1]["content"])
        self.assertTrue(any(i["source"] == "memory" and i["rating"] is None for i in sl._load()["items"]))

    def test_selfcheck_needs_a_trained_version(self):
        self.items(3)
        with self.assertRaisesRegex(ValueError, "обученная"):
            teacher.estimate("selfcheck", 3)


@unittest.skipUnless(HAS_TORCH, "PyTorch optional")
class ExamLabTests(LabBase):
    def train(self, name, size="s"):
        run = tc.start("long", dataset=name, device="cpu", total_steps=100, hours=0.1, config=TINY, launch=False,
                       size=size)["id"]
        tc.worker(run)
        return tc._summary(tc._run_dir(run))

    def test_new_versions_retake_old_exams_and_honesty_and_blind_check(self):
        first = self.train(dataset("one.json"))
        self.assertEqual(first["state"], "finished")
        self.assertIsNotNone(first["exam_per_char"])
        self.assertEqual(first["honesty"]["total"], len(honesty.EXAM))
        time.sleep(1.1)
        second = self.train(dataset("two.json", tc.MIN_LONG_RECORDS + 7))
        self.assertEqual([o["run"] for o in second["old_exams"]], [first["id"]])
        self.assertIn("mine", second["old_exams"][0])
        proposal = sl.proposal()
        if proposal:
            self.assertIn("forgets", proposal)
        # Blind check: names stay hidden until the round is voted.
        with self.assertRaises(ValueError):
            blind.start([first["id"]])
        started = blind.start([first["id"], second["id"]], 2)
        self.assertNotIn(first["id"], json.dumps(started))
        self.assertFalse(blind.vote(started["round"], 0, "a")["done"])
        reveal = blind.vote(started["round"], 1, "same")["reveal"]
        self.assertEqual(reveal["votes"], 2)
        self.assertEqual(reveal["same"], 1)
        self.assertEqual(sum(reveal["wins"].values()), 1)
        self.assertEqual(blind.results()[0]["votes"], 2)
        with self.assertRaises(ValueError):
            blind.vote("../../etc", 0, "a")


if __name__ == "__main__":
    unittest.main()
