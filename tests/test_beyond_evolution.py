"""Beyond evolution: the archive of different strong versions, tournaments between generations,
evolving study recipes, the task ladder, smart width growth, shrinking after growth, health,
tidying, the self-planned night and the morning report."""
import random
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import archive
from backend import autopilot
from backend import health
from backend import logic
from backend import night_cycle as night
from backend import planner
from backend import plans
from backend import recipes
from backend import schedule
from backend import self_learning as sl
from backend import simworld
from backend import training_center as tc
from tests.test_learning_lab import LabBase, dataset
from tests.test_living_brain import LAB

try:
    import torch  # noqa: F401
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


class ArchiveRulesTests(unittest.TestCase):
    def test_niches_and_fitness(self):
        self.assertEqual(archive.family_of({}), "классика")
        self.assertEqual(archive.family_of({"lab": True}), "новое")
        self.assertEqual(archive.family_of({"lab": True, "experts": 4}), "эксперты")
        self.assertEqual(archive.family_of({"lab": True, "loops": 2, "memory": 64}), "всё сразу")
        self.assertEqual(archive.size_of(1_000_000), 0)
        self.assertEqual(archive.size_of(30_000_000), 3)
        self.assertEqual(archive.size_of(500_000_000), 4)
        self.assertIsNone(archive.fitness({"exam_per_char": None}))
        weak = archive.fitness({"exam_per_char": 2.0})
        strong = archive.fitness({"exam_per_char": 2.0, "logic": {"levels": {"1": 1.0}}, "sim": {"nim": 0.5},
                                  "honesty": {"honest": 3, "total": 4}})
        self.assertGreater(strong, weak)
        tasks = archive.tournament_tasks(5)
        self.assertEqual(len(tasks), archive.TOURNAMENT)
        self.assertEqual(tasks, archive.tournament_tasks(5))  # both sides get the same tasks
        exam = logic._exam_questions() | simworld._banned()
        self.assertFalse({q for q, _ in tasks} & exam)


class LadderTests(LabBase):
    def test_ladder_climbs_and_old_exams_stay_the_same(self):
        rng = random.Random(2)
        for level in range(1, simworld.MAX_LEVEL + 1):
            for env in simworld.ENVS:
                t = simworld.task(rng, env, level)
                self.assertTrue(logic.correct(t["solution"], t["answer"]), t)
        # The chain environment is new; the five older ones keep their exam questions.
        old = ["count", "grid", "nim", "shop", "sort"]
        for env in old:
            before = random.Random(700_000 + old.index(env))
            first = simworld.task(before, env, 1)["q"]
            self.assertEqual(simworld.exam_tasks(env)[0]["q"], first)
        moves = simworld.climb({"nim": {"lives": 20, "wins": 19}, "grid": {"lives": 5, "wins": 5},
                                "sort": {"lives": 20, "wins": 1}})
        self.assertEqual([(m["env"], m["to"]) for m in moves], [("nim", 2)])
        self.assertEqual(simworld.ladder()["levels"]["nim"], 2)
        self.assertEqual(simworld.ladder()["levels"]["sort"], 1)  # never below the first step
        tasks = simworld.fresh(random.Random(3), 30, level={"nim": 7}, envs=["nim"])
        self.assertTrue(all(t["level"] == 7 for t in tasks))


class RecipeTests(LabBase):
    def test_recipes_mutate_score_and_remember(self):
        self.assertTrue(recipes.valid(recipes.DEFAULT))
        found = recipes.candidates(4, seed=1)
        self.assertEqual(len(found), 4)
        self.assertEqual(len({recipes.describe(r) for r in found}), 4)
        self.assertTrue(all(recipes.valid(r) for r in found))
        lessons = recipes.records(found[1], seed=2)
        self.assertTrue(lessons)
        exam = logic._exam_questions() | simworld._banned()
        self.assertFalse({r["prompt"] for r in lessons} & exam)
        before = {"dialogue": -2.0, "logic": 0.1, "sim": 0.0}
        better = {"dialogue": -1.9, "logic": 0.2, "sim": 0.1}
        self.assertGreater(recipes.gain(before, better, 0.5)[0], recipes.gain(before, better, 1.0)[0])
        outcome = recipes.remember([{"recipe": found[1], "run": "a", "gain_per_hour": 0.2, "gain": 0.1, "hours": 0.5},
                                    {"recipe": found[2], "run": "b", "gain_per_hour": -0.1, "gain": -0.05, "hours": 0.5}])
        self.assertEqual(outcome["winner"]["run"], "a")
        self.assertEqual(recipes.best(), found[1])
        self.assertEqual(recipes.learning_rate(), found[1]["lr"])
        # A round where nothing improved keeps the previous winner.
        recipes.remember([{"recipe": found[3], "run": "c", "gain_per_hour": -0.3, "gain": -0.1, "hours": 0.5}])
        self.assertEqual(recipes.best(), found[1])
        self.assertEqual(recipes.status()["generations"], 2)


class AutomationTests(LabBase):
    def test_planner_health_and_autopilot_options(self):
        self.assertEqual(planner.today()["activity"], "fresh")
        self.assertEqual(planner.expert_change({"introspection": {"experts": [0.7, 0.1, 0.1, 0.1]}}), 2)
        self.assertEqual(planner.expert_change({"introspection": {"experts": [0.24, 0.24, 0.24, 0.24, 0.02, 0.02]}}), -2)
        self.assertEqual(planner.expert_change({"introspection": {"experts": [0.5, 0.5]}}), 0)
        report = health.check()
        self.assertIn(report["state"], ("ok", "warn", "bad"))
        self.assertTrue(report["items"])
        self.assertEqual(health.tidy()["removed"], [])
        self.assertFalse(autopilot.settings()["auto_week"])
        state = autopilot.set_enabled(True, apply=False)
        self.assertTrue(autopilot.settings()["auto_week"])
        self.assertIn("auto_week", {p["key"] for p in state["parts"]})
        autopilot.set_enabled(False, apply=False)
        self.assertFalse(autopilot.settings()["auto_week"])
        self.assertTrue(planner.morning()["empty"])
        with self.assertRaises(ValueError):
            autopilot.set_options(auto_week="да")


@unittest.skipUnless(HAS_TORCH, "PyTorch optional")
class EvolutionMachineTests(LabBase):
    def setUp(self):
        super().setUp()
        schedule.set_grid("always")

    def train(self, name, config=LAB, **kw):
        run = tc.start("long", dataset=name, device="cpu", total_steps=100, hours=0.1, config=config, launch=False, **kw)["id"]
        tc.worker(run)
        time.sleep(1.1)
        return tc._summary(tc._run_dir(run))

    def test_archive_tournament_growth_tidy_and_recipes(self):
        name = dataset()
        base = self.train(name)
        self.assertIsNotNone(base["sim"])
        self.assertIn("chain", base["sim"])
        cell = archive.load()["cells"][archive.niche(base)]
        self.assertEqual(cell["run"], base["id"])
        self.assertEqual(archive.pick_parent(random.Random(1)), base["id"])
        # A child of the base plays a tournament against it before it may enter the archive.
        child = self.train(name, init="runs/%s/language-longrun.pt.best.pt" % base["id"])
        self.assertEqual(child["parent"], base["id"])
        self.assertEqual(child["tournament"]["parent"], base["id"])
        self.assertEqual(child["tournament"]["tasks"], archive.TOURNAMENT)
        self.assertTrue(any(e["run"] == child["id"] for e in archive.load()["log"]))
        # Evolution starts from an elite of the archive.
        series = tc.start_evolution(name, 3, device="cpu", total_steps=100, hours_each=0.1, launch=False, seed=4)
        first = tc._read(tc._run_dir(series["first"]) / "run.json")
        self.assertIn(first["parent"], archive.elites())
        tc.stop_all()
        progress = tc._read(tc._run_dir(series["first"]) / "progress.json")
        progress["state"] = "stopped"
        tc._write(tc._run_dir(series["first"]) / "progress.json", progress)
        time.sleep(1.1)
        # Wider: the two busiest experts split into four.
        tc.activate(base["id"])
        grown = tc.start("long", device="cpu", total_steps=100, hours=0.1, grow={"from": base["id"], "experts": 2},
                         records=tc._load_records(name), launch=False)
        info = tc._read(tc._run_dir(grown["id"]) / "run.json")
        self.assertEqual(info["config"]["arch"]["experts"], 4)
        self.assertEqual(info["grown_from"], base["id"])
        tc.worker(grown["id"])
        time.sleep(1.1)
        self.assertEqual(len(tc._summary(tc._run_dir(grown["id"]))["introspection"]["experts"]), 4)
        with self.assertRaisesRegex(ValueError, "2, 4, 6 или 8"):
            tc.start("long", device="cpu", grow={"from": base["id"], "experts": 8}, records=tc._load_records(name),
                     launch=False)
        # Shrink after growth: the grown version is found as a teacher of its smaller ancestor.
        self.assertEqual(plans.shrink_teacher(), grown["id"])
        self.assertEqual(plans._root(grown["id"]), base["id"])
        self.assertEqual(planner.today("sleep")["activity"], "shrink")
        # Tidying removes stale resume copies, never a version or the active one.
        child_dir = tc._run_dir(child["id"])
        progress = tc._read(child_dir / "progress.json")
        progress["t"] = time.time() - 3 * 86400
        tc._write(child_dir / "progress.json", progress)
        protected = health._protected()
        done = health.tidy()
        if child["id"] not in protected:
            self.assertIn("%s/language-longrun.pt" % child["id"], done["removed"])
        self.assertTrue((child_dir / "language-longrun.pt.best.pt").is_file())
        self.assertTrue((tc._run_dir(base["id"]) / "language-longrun.pt").is_file())

    def test_recipes_plan_and_self_planned_night(self):
        name = dataset()
        base = self.train(name, dict(LAB, context=256))
        tc.activate(base["id"])
        store = sl._load()
        for i in range(30):
            store["items"].append({"id": "e%d" % i, "prompt": "Как прошёл день %d?" % i, "answer": "Хорошо, спасибо %d." % i,
                                   "ts": time.time(), "rating": "up", "correction": None, "source": "yorika-chat"})
        sl._save(store)
        plan = plans.start("recipes", branches=2, minutes=1, device="cpu", launch=False)
        plans.worker()
        for _ in range(4):
            plan = plans.current()
            pending = [r for r in plan.get("round_runs", []) if tc._summary(tc._run_dir(r))["state"] == "starting"]
            if plan["state"] != "running" or not pending:
                break
            info = tc._read(tc._run_dir(pending[0]) / "run.json")
            info["time_limit"] = 3
            tc._write(tc._run_dir(pending[0]) / "run.json", info)
            tc.worker(pending[0])
            time.sleep(1.1)
        plan = plans.current()
        self.assertEqual(plan["state"], "finished", plan.get("result"))
        self.assertEqual(len(plan["recipes_report"]), 2)
        self.assertEqual(recipes.status()["generations"], 1)
        with self.assertRaisesRegex(ValueError, "выросшей"):
            plans.start("shrink", launch=False)
        # The self-planned night: she picks an activity from measurements and says why.
        autopilot.set_options(auto_week=True)
        choice = planner.today("sleep")
        self.assertIn(choice["activity"], night.ACTIVITIES)
        self.assertTrue(choice["why"])



class LongLessonTests(unittest.TestCase):
    def test_long_lessons_are_cut_from_the_question_not_the_answer(self):
        from backend.neural_language_longrun import _LazyRows
        rows = _LazyRows([("q", "a"), ("q2", "a2")], lambda e: (list(range(20)), 15) if e[0] == "q" else (list(range(20)), 3), 9)
        ids, masked = rows[0]
        self.assertEqual(len(ids), 10)
        self.assertEqual(ids[-1], 19)  # the end of the answer stays
        self.assertEqual(masked, 5)
        ids, masked = rows[1]
        self.assertEqual(len(ids), 10)
        self.assertEqual(masked, 2)  # answer longer than the context: its start stays


if __name__ == "__main__":
    unittest.main()
