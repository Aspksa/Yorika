"""Beyond the brain: introspection, programs as skills, the game world, the study schedule,
copies merged back, branches in time, learning from the slower self, autopilot."""
import os
import random
import sys
import time
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import autopilot
from backend import continual
from backend import logic
from backend import night_cycle as night
from backend import plans
from backend import programs
from backend import schedule
from backend import self_learning as sl
from backend import simworld
from backend import tools
from backend import training_center as tc
from tests.test_learning_lab import LabBase, dataset
from tests.test_living_brain import LAB

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


class ProgramTests(LabBase):
    def test_search_finds_verified_programs_and_tools_run_them(self):
        found = programs.learn(seed=3)
        self.assertEqual(set(found), set(programs.FAMILIES))
        self.assertEqual(programs.evaluate(programs.library()["периметр"]["expr"], [3, 4]), 14)
        text, calls = tools.run_tools("Ответ: [[skill:день_через: суббота, 2]].")
        self.assertEqual(text, "Ответ: понедельник.")
        self.assertEqual(calls[0]["tool"], "skill")
        self.assertIn("(", tools.run_tools("[[skill:нет_такого: 1]]")[0])
        lessons = programs.lessons(per_skill=10)
        self.assertTrue(lessons)
        exam = {q for q, _ in programs.exam_tasks()} | logic._exam_questions() | simworld._banned()
        self.assertFalse({q for q, _ in lessons} & exam)
        self.assertEqual(programs.describe()[0]["pretty"], "((день + n) % 7)")

    def test_interpreter_runs_only_arithmetic(self):
        for bad in ("__import__('os')", "x0.real", "(lambda: 1)()", "[1][0]", "x9", "2 ** 10", "'a'"):
            with self.assertRaises(ValueError):
                programs.evaluate(bad, [1])
        self.assertEqual(programs.evaluate("(x0 + x1) % 7", [5, 4]), 2)
        self.assertIsNone(programs.synthesize([([1], 1), ([2], 4), ([3], 27)], 1, max_size=3))


class WorldTests(unittest.TestCase):
    def test_every_environment_checks_its_answers(self):
        rng = random.Random(4)
        for env in simworld.ENVS:
            for level in (1, 2, 3):
                t = simworld.task(rng, env, level)
                self.assertTrue(logic.correct(t["solution"], t["answer"]), t)
        nim = [simworld.task(rng, "nim") for _ in range(30)]
        for t in nim:
            stones = int(t["q"].split()[2])
            self.assertEqual(t["answer"], str(stones % 4) if stones % 4 else "никак")
        exam = simworld._banned()
        self.assertFalse({t["q"] for t in simworld.fresh(random.Random(1), 200)} & exam)
        self.assertFalse({q for q, _ in simworld.lessons(200)} & exam)


class ScheduleTests(LabBase):
    def test_painted_week_drives_tasks_and_lessons(self):
        grid = schedule.set_grid("night")["grid"]
        self.assertTrue(schedule.allowed(datetime(2026, 10, 19, 3), grid))
        self.assertFalse(schedule.allowed(datetime(2026, 10, 19, 12), grid))
        self.assertEqual(schedule.hours_left(datetime(2026, 10, 19, 5, 30), grid), 1.5)
        self.assertEqual(schedule.tasks(grid), [{"time": "01:00", "hours": 6.0, "days": schedule.DAYS}])
        week = schedule.set_grid(["0" * 23 + "1"] + ["1" + "0" * 23] + ["0" * 24] * 5)["grid"]
        self.assertEqual(schedule.blocks(week), [(0, 23, 2)])  # crosses midnight
        with self.assertRaises(ValueError):
            schedule.set_grid(["1" * 24] * 6)
        # Outside study hours quick lessons wait, even with enough new examples.
        schedule.set_grid(["0" * 24] * 7)
        continual.set_settings(True, min_new=10)
        tc._write(tc.folder() / "active-brain.json", {"run": "x", "checkpoint": "brains/x.pt"})
        self.assertIsNone(continual.maybe_start(launch=False))

    def test_week_plan_and_autopilot(self):
        with self.assertRaises(ValueError):
            night.set_settings(True, apply=False, week=["sleep"] * 6)
        plan = night.set_settings(True, apply=False, week=["sleep", "distill", "search", "swarm", "evolution", "fresh", "rest"])
        self.assertEqual(plan["week"][6], "rest")
        self.assertEqual(night.activity(plan, datetime(2026, 10, 25)), "rest")  # a Sunday
        state = autopilot.set_enabled(True, apply=False)
        self.assertTrue(state["on"], state)
        self.assertTrue(sl._settings()["collect"])
        self.assertFalse(continual.settings()["auto_activate"])  # never switched on by the autopilot
        self.assertFalse(autopilot.set_enabled(False, apply=False)["on"])
        self.assertFalse(continual.settings()["enabled"])


@unittest.skipUnless(HAS_TORCH, "PyTorch optional")
class MachineLearningTests(LabBase):
    def setUp(self):
        super().setUp()
        schedule.set_grid("always")

    def train(self, name, config=LAB):
        run = tc.start("long", dataset=name, device="cpu", total_steps=100, hours=0.1, config=config, launch=False)["id"]
        tc.worker(run)
        time.sleep(1.1)
        return tc._summary(tc._run_dir(run))

    def shorten_and_run(self, plan_kind, **kw):
        plan = plans.start(plan_kind, minutes=1, device="cpu", launch=False, **kw)
        self.assertEqual(plan["state"], "preparing")
        plans.worker()
        seen = set()
        for _ in range(10):
            plan = plans.current()
            pending = [r for r in plan.get("round_runs", []) if r not in seen]
            if plan["state"] != "running" or not pending:
                break
            run = pending[0]
            seen.add(run)
            info = tc._read(tc._run_dir(run) / "run.json")
            info["time_limit"] = 3
            tc._write(tc._run_dir(run) / "run.json", info)
            tc.worker(run)
            time.sleep(1.1)
        return plans.current()

    def test_introspection_copies_branches_and_future_self(self):
        name = dataset()
        base = self.train(name)
        report = base["introspection"]
        self.assertEqual(len(report["blocks"]), LAB["layers"])
        self.assertIsNotNone(report["blocks"][0]["contribution"])
        self.assertEqual(len(report["experts"]), 2)
        self.assertEqual(report["memory"]["slots"], 64)
        self.assertTrue(report["advice"])
        tc.activate(base["id"])
        store = sl._load()
        for i in range(30):
            store["items"].append({"id": "e%d" % i, "prompt": "Как прошёл день %d?" % i, "answer": "Хорошо, спасибо %d." % i,
                                   "ts": time.time(), "rating": "up", "correction": None, "source": "yorika-chat"})
        sl._save(store)
        # Copies: each learns one skill; only improved ones would be merged.
        swarm = self.shorten_and_run("swarm", copies=["tools", "experience"])
        self.assertEqual(swarm["state"], "finished", swarm.get("result"))
        self.assertEqual(len(swarm["runs"]), 2)
        self.assertEqual(len(swarm["copies_report"]), 2)
        merged = plans.merge_skills(tc.active()["checkpoint"], [r["id"] for r in swarm["runs"]])
        self.assertEqual(tc._summary(tc._run_dir(merged))["kind"], "swarm")
        time.sleep(1.1)
        # Branches: two paths from the same moment, the best one is kept or none.
        search = self.shorten_and_run("search", branches=2, rounds=1)
        self.assertEqual(search["state"], "finished", search.get("result"))
        self.assertEqual(len(search["rounds_report"][0]["branches"]), 2)
        self.assertEqual({tc._summary(tc._run_dir(r["id"]))["lr"] for r in search["runs"]}, {0.0001, 0.0003})
        # Future self: a tiny untrained model is too weak to teach; the plan says so honestly.
        records, made = plans.distill_set(tc.folder() / tc.active()["checkpoint"], prompts=20)
        self.assertEqual(made["asked"], 20)
        self.assertTrue(all(r["source"] in ("distill", "yorika-chat") for r in records))
        with self.assertRaises(ValueError):
            plans.start("swarm", copies=["logic"], launch=False)


if __name__ == "__main__":
    unittest.main()
