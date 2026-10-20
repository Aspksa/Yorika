"""Evolutionary know-how: coevolving tasks, the Red Queen, the Baldwin effect, self-adapting
mutation strength, novelty and species, and the mass extinction that only the owner can start."""
import random
import sys
import time
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import archive
from backend import baldwin
from backend import coevolution
from backend import extinction
from backend import logic
from backend import mutation
from backend import planner
from backend import plans
from backend import recipes
from backend import schedule
from backend import self_learning as sl
from backend import simworld
from backend import species
from backend import training_center as tc
from tests.test_learning_lab import LabBase, dataset
from tests.test_living_brain import LAB

try:
    import torch  # noqa: F401
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


class RulesTests(LabBase):
    def test_mutation_strength_follows_the_one_fifth_rule(self):
        self.assertEqual(mutation.status()["strength"], mutation.START)
        rng = random.Random(1)
        self.assertTrue(all(1 <= mutation.genes(rng) <= 2 for _ in range(50)))
        for _ in range(mutation.PLATEAU):
            mutation.record("тест", False)
        stuck = mutation.status()
        self.assertTrue(stuck["plateau"])
        self.assertGreater(stuck["strength"], mutation.START)
        mutation.record("тест", True)
        self.assertLess(mutation.status()["strength"], stuck["strength"])
        self.assertFalse(mutation.status()["plateau"])
        # Four failures balance one success: the strength stays put at one success in five.
        before = mutation.status()["strength"]
        for _ in range(4):
            mutation.record("тест", False)
        mutation.record("тест", True)
        self.assertAlmostEqual(mutation.status()["strength"], before, places=2)
        mutation.boost(2)
        self.assertEqual(mutation.genes(rng), 4)
        mutation.record("тест", False)
        mutation.record("тест", False)
        self.assertEqual(mutation.status()["boost"], 0)
        child = mutation.apply(lambda g, r: g + 1, 0, rng, count=3)
        self.assertEqual(child, 3)
        found = recipes.candidates(5, seed=2)
        self.assertTrue(all(recipes.valid(r) for r in found))

    def test_task_genomes_make_true_tasks_and_never_exam_ones(self):
        exam = logic._exam_questions() | simworld._banned()
        rng = random.Random(4)
        for genome in coevolution.seeds() + [{"domain": "logic", "kind": "order", "level": 5},
                                             {"domain": "sim", "kind": "nim", "level": 6}]:
            self.assertTrue(coevolution.valid(genome))
            tasks = coevolution.make(genome, rng, 5)
            self.assertTrue(tasks, genome)
            for t in tasks:
                self.assertNotIn(t["q"], exam)
                self.assertTrue(logic.correct(t["solution"], t["answer"]), t)
                self.assertLessEqual(len(t["q"]) + len(t["solution"]), plans.MAX_CHARS)
        genome = coevolution.seeds()[0]
        for _ in range(300):
            genome = coevolution.mutate(genome, rng)
            self.assertTrue(coevolution.valid(genome), genome)
        self.assertFalse(coevolution.valid({"domain": "logic", "kind": "sequence", "level": 3}))
        self.assertEqual(coevolution.fitness({"fail": 0.0, "tried": 6, "history": [0.0]}), 0.0)
        self.assertGreater(coevolution.fitness({"fail": 0.5, "tried": 6, "history": [0.5]}),
                           coevolution.fitness({"fail": 1.0, "tried": 6, "history": [1.0]}))
        # She learned it: the failure rate dropped, so the genome is a good teacher.
        self.assertGreater(coevolution.fitness({"fail": 0.5, "tried": 6, "history": [1.0, 0.5]}),
                           coevolution.fitness({"fail": 0.5, "tried": 6, "history": [0.5, 0.5]}))
        a, b = coevolution.elo(1000, 1000, 1.0)
        self.assertEqual((a, b), (1012.0, 988.0))
        self.assertEqual(coevolution.elo(1100, 900, 0.5)[0] + coevolution.elo(1100, 900, 0.5)[1], 2000)

    def test_species_probes_novelty_and_protection(self):
        probes = species.probes()
        self.assertEqual(len(probes), species.PROBES)
        self.assertFalse({q for q, _ in probes} & (logic._exam_questions() | simworld._banned()))
        lessons = plans._synthetic(probes + [("Новый вопрос?", "Ответ.")], "t")
        self.assertEqual([r["prompt"] for r in lessons], ["Новый вопрос?"])  # probes never become lessons
        self.assertEqual(species.distance("1100", "1000"), 0.25)
        self.assertEqual(species.novelty("1111", ["0000", "1111"]), 0.5)
        self.assertEqual(species.novelty("1111", []), 1.0)

    def test_extinction_needs_your_word_and_a_plateau_is_measured(self):
        with self.assertRaisesRegex(ValueError, "подтвержд"):
            extinction.run(False, 0)
        with self.assertRaisesRegex(ValueError, "некого"):
            extinction.run(True, 0)
        with self.assertRaisesRegex(ValueError, "изменился"):
            extinction.run(True, 3)
        self.assertFalse(extinction.plateau()["plateau"])
        data = archive.load()
        data["log"] = [{"run": "r%d" % i, "result": "в своей клетке есть сильнее"} for i in range(8)]
        archive._save(data)
        self.assertTrue(extinction.plateau()["plateau"])
        self.assertEqual(extinction.status()["count"], 0)


@unittest.skipUnless(HAS_TORCH, "PyTorch optional")
class KnowHowMachineTests(LabBase):
    def setUp(self):
        super().setUp()
        schedule.set_grid("always")

    def train(self, name, config=LAB, **kw):
        run = tc.start("long", dataset=name, device="cpu", total_steps=100, hours=0.1, config=config, launch=False, **kw)["id"]
        tc.worker(run)
        time.sleep(1.1)
        return tc._summary(tc._run_dir(run))

    def run_plan(self, kind, **kw):
        plans.start(kind, minutes=1, device="cpu", launch=False, **kw)
        plans.worker()
        for _ in range(6):
            plan = plans.current()
            pending = [r for r in plan.get("round_runs", []) if tc._summary(tc._run_dir(r))["state"] == "starting"]
            if plan["state"] != "running" or not pending:
                break
            info = tc._read(tc._run_dir(pending[0]) / "run.json")
            info["time_limit"] = 3
            tc._write(tc._run_dir(pending[0]) / "run.json", info)
            tc.worker(pending[0])
            time.sleep(1.1)
        return plans.current()

    def test_coevolution_red_queen_baldwin_species_and_extinction(self):
        name = dataset()
        dense = dict(LAB, arch={"lab": True}, context=256)
        base = self.train(name, dense)
        rival = self.train(name, dict(dense, seed=2))
        # Every exam gives the version a behaviour on the probes and a species.
        seen = species.load()
        self.assertIn(base["id"], seen["behaviours"])
        self.assertEqual(len(seen["behaviours"][base["id"]]), species.PROBES)
        self.assertTrue(species.status()["species"])
        tc.activate(base["id"])
        store = sl._load()
        for i in range(30):
            store["items"].append({"id": "k%d" % i, "prompt": "Как дела %d?" % i, "answer": "Хорошо %d." % i,
                                   "ts": time.time(), "rating": "up", "correction": None, "source": "yorika-chat"})
        sl._save(store)

        plan = self.run_plan("coevolve")
        self.assertEqual(plan["state"], "finished", plan.get("result"))
        self.assertEqual(plan["made"]["generation"], 1)
        co = coevolution.status()
        self.assertEqual(co["generation"], 1)
        self.assertTrue(all(t["fail"] is None or 0 <= t["fail"] <= 1 for t in co["top"]))

        plan = self.run_plan("redqueen", teacher=rival["id"], prompts=40)
        self.assertEqual(plan["state"], "finished", plan.get("result"))
        match = coevolution.redqueen_status()["last"]
        self.assertEqual((match["left"], match["right"]), (base["id"], rival["id"]))
        self.assertAlmostEqual(sum(match["ratings"]), 2000, places=0)
        sides = {r.get("side") for r in plan["runs"]}
        self.assertTrue(sides <= {"active", "partner"} and sides)

        plan = self.run_plan("baldwin", branches=2)
        self.assertEqual(plan["state"], "finished", plan.get("result"))
        self.assertTrue((tc.folder() / "baldwin" / "inherited.pt").is_file())
        self.assertEqual(baldwin.status()["generation"], 1)
        self.assertTrue(plan["genomes"][0]["control"])
        # The next generation starts one newborn from the inherited point, next to the control.
        genomes = baldwin.candidates(3, seed=5)
        self.assertTrue(genomes[0].get("control") and genomes[1].get("inherit"))
        target = tc.folder() / "baldwin" / "check.pt"
        baldwin.newborn(tc._run_dir(base["id"]) / "language-longrun.pt.best.pt", genomes[1], target)
        born = torch.load(target, map_location="cpu", weights_only=True)
        self.assertEqual(born["step"], 0)

        # Planner: after a week each new activity is chosen with its reason.
        state = planner._state()
        state["history"] = {k: time.time() for k in ("rebirth", "hemispheres", "thoughts", "ecosystem", "redqueen", "baldwin",
                                                       "dataevo", "es", "symbiosis")}
        planner._save_state(state)
        recipes.remember([{"recipe": recipes.DEFAULT, "run": base["id"], "gain_per_hour": 0.1, "gain": 0.1, "hours": 1}])
        quiet = dict(tc._summary(tc._run_dir(base["id"])), introspection=None)
        with mock.patch.object(planner, "_active_item", lambda: quiet), \
                mock.patch.object(archive, "cells", lambda: {"filled": 3}):
            self.assertEqual(planner.today("sleep")["activity"], "coevolve")
            state["history"]["coevolve"] = time.time()
            state["history"]["redqueen"] = 0
            planner._save_state(state)
            self.assertEqual(planner.today("sleep")["activity"], "redqueen")
            state["history"]["redqueen"] = time.time()
            state["history"]["baldwin"] = time.time() - 8 * 24 * 3600
            planner._save_state(state)
            self.assertEqual(planner.today("sleep")["activity"], "sleep")  # Baldwin waits two weeks

        # Extinction: the active version, its lineage and the archive's best are never on the list.
        found = {c["run"] for c in extinction.candidates()}
        self.assertNotIn(base["id"], found)
        self.assertFalse(found & {c["run"] for c in archive.load()["cells"].values()})
        preview = extinction.preview()
        if preview["count"]:
            done = extinction.run(True, preview["count"])
            self.assertEqual(sorted(done["removed"]), sorted(found))
            self.assertTrue(all(not (tc.folder() / "runs" / r).exists() for r in done["removed"]))
            self.assertEqual(mutation.status()["boost"], 3)
        self.assertTrue(tc._summary(tc._run_dir(base["id"]))["has_best"])


if __name__ == "__main__":
    unittest.main()
