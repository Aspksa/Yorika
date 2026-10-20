"""Breeding by an evolved recipe (DARE + TIES per layer, kinship of parents, skills taking turns as
in CycleQD), learning from the majority of her own drafts (EVOL-RL) and the autopilot's rhythm."""
import random
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import breeding
from backend import planner
from backend import plans
from backend import schedule
from backend import selfevolve
from backend import self_learning as sl
from backend import training_center as tc
from tests.test_learning_lab import LabBase, dataset
from tests.test_living_brain import LAB

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

DAY = 24 * 3600


@unittest.skipUnless(HAS_TORCH, "PyTorch optional")
class RecipeTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(0)
        self.base = {"embedding.weight": torch.randn(6, 4), "blocks.0.w": torch.randn(4, 4), "blocks.1.w": torch.randn(4, 4),
                     "output.weight": torch.randn(6, 4), "steps": torch.tensor([3])}
        self.names = breeding.groups(self.base)

    def shifted(self, delta):
        return {k: (v + delta[k] if v.is_floating_point() else v) for k, v in self.base.items()}

    def test_groups_are_input_every_block_and_output(self):
        self.assertEqual(self.names, ["in", "block 0", "block 1", "out"])
        self.assertEqual([breeding.group_of(k) for k in self.base], ["in", "block 0", "block 1", "out", "out"])

    def test_one_parent_weight_per_layer(self):
        delta = {k: torch.ones_like(v, dtype=torch.float32) for k, v in self.base.items()}
        parent = self.shifted(delta)
        genome = {"w": [[1.0, 0.0, 0.5, 1.0]], "density": 1.0, "seed": 1}
        child = breeding.materialize(self.base, [parent], genome, self.names)
        self.assertTrue(torch.allclose(child["embedding.weight"], parent["embedding.weight"]))
        self.assertTrue(torch.allclose(child["blocks.0.w"], self.base["blocks.0.w"]))
        self.assertTrue(torch.allclose(child["blocks.1.w"], self.base["blocks.1.w"] + 0.5))
        self.assertTrue(torch.equal(child["steps"], self.base["steps"]))

    def test_ties_keeps_only_changes_with_the_agreed_sign(self):
        up = self.shifted({k: torch.full_like(v, 1.0, dtype=torch.float32) for k, v in self.base.items()})
        down = self.shifted({k: torch.full_like(v, -0.4, dtype=torch.float32) for k, v in self.base.items()})
        genome = {"w": [[1.0] * 4, [1.0] * 4], "density": 1.0, "seed": 1}
        child = breeding.materialize(self.base, [up, down], genome, self.names)
        # The sum is positive, so only the parent that moved up is added; the other is not averaged in.
        self.assertTrue(torch.allclose(child["blocks.0.w"], self.base["blocks.0.w"] + 1.0))

    def test_dare_drops_and_rescales_with_its_own_seed(self):
        parent = self.shifted({k: torch.ones_like(v, dtype=torch.float32) for k, v in self.base.items()})
        genome = {"w": [[1.0] * 4], "density": 0.5, "seed": 7}
        a = breeding.materialize(self.base, [parent], genome, self.names)
        b = breeding.materialize(self.base, [parent], genome, self.names)
        moved = a["output.weight"] - self.base["output.weight"]
        self.assertTrue(torch.equal(a["output.weight"], b["output.weight"]))
        self.assertTrue(set(torch.round(moved, decimals=4).unique().tolist()) <= {0.0, 2.0})

    def test_kinship_and_change(self):
        d = {k: torch.randn(v.shape) if v.is_floating_point() else v for k, v in self.base.items()}
        a, twin = self.shifted(d), self.shifted({k: 1.01 * v if v.is_floating_point() else v for k, v in d.items()})
        opposite = self.shifted({k: -v if v.is_floating_point() else v for k, v in d.items()})
        self.assertGreater(breeding.kinship(a, twin, self.base), breeding.KIN_MAX)
        self.assertAlmostEqual(breeding.kinship(a, opposite, self.base), -1.0, places=3)
        self.assertIsNone(breeding.kinship(self.base, a, self.base))
        self.assertEqual(breeding.change(self.base, self.base), 0.0)
        self.assertGreater(breeding.change(a, self.base), breeding.MIN_CHANGE)

    def test_genomes_stay_in_bounds(self):
        rng = random.Random(3)
        g = breeding.random_genome(rng, 2, 4)
        for _ in range(200):
            g = breeding.mutate(breeding.crossover(g, breeding.random_genome(rng, 2, 4), rng), rng, sigma=0.8)
            self.assertTrue(all(breeding.W_LOW <= x <= breeding.W_HIGH for row in g["w"] for x in row))
            self.assertTrue(0.2 <= g["density"] <= 1.0)
        self.assertEqual(breeding.random_genome(rng, 2, 3, plain=True)["w"], [[0.5] * 3, [0.5] * 3])

    def test_cycleqd_cell_is_the_other_skills(self):
        gains = {"logic": 0.1, "honesty": -0.06, "dialogue": 0.01}
        self.assertEqual(breeding._cell(gains, "logic"), (2, 0))   # dialogue in [0, 0.05), honesty below -0.05
        self.assertEqual(breeding._cell(gains, "dialogue"), (0, 3))


class MajorityTests(unittest.TestCase):
    def test_majority_selects_and_novelty_varies(self):
        texts = ["Шаг 1: 2+3. Ответ: 5.", "Сложим два и три. Ответ: 5.", "Шаг 1: 2+3. Ответ: 5.", "Ответ: 6.", ""]
        text, key, votes, novel = selfevolve.pick(texts, True)
        self.assertEqual((key, votes), ("5", 3))
        self.assertEqual(text, "Сложим два и три. Ответ: 5.")   # the agreed answer by the least common path
        self.assertGreater(novel, 0)
        self.assertIsNone(selfevolve.pick(["Ответ: 1.", "Ответ: 2.", "Ответ: 1.", "Ответ: 3.", "нет"], True))
        chat = ["Привет! Рада тебя видеть.", "привет!  рада тебя видеть.", "Привет! Рада тебя видеть.", "Здравствуй", "Ой"]
        self.assertEqual(selfevolve.pick(chat, False)[2], 3)


class RhythmTests(LabBase):
    def test_period_adapts_to_what_helped(self):
        self.assertEqual(planner.period("es", {}), 2 * planner.WEEK)
        self.assertEqual(planner.period("es", {"es": {"tried": 3, "helped": 0}}), 4 * planner.WEEK)
        self.assertEqual(planner.period("es", {"es": {"tried": 4, "helped": 2}}), planner.WEEK)
        self.assertEqual(planner.period("coevolve", {"coevolve": {"tried": 2, "helped": 2}}), 3.5 * DAY)
        self.assertEqual(planner.period("breed", {"breed": {"tried": 6, "helped": 6}}), 3.5 * DAY)
        self.assertEqual(planner.period("thoughts", {"thoughts": {"tried": 1, "helped": 0}}), planner.WEEK)
        with mock.patch.object(planner, "_tried", lambda: {"es": {"tried": 3, "helped": 0}}):
            rows = {r["activity"]: r for r in planner.rhythm()}
        self.assertEqual((rows["es"]["days"], rows["es"]["change"]), (28.0, "реже"))
        self.assertIsNone(rows["breed"]["change"])

    def test_planner_reaches_breeding_and_the_majority(self):
        state = planner._state()
        state["history"] = {k: time.time() for k in planner.EVERY if k not in ("breed", "evolrl")}
        from backend import development
        development_done = mock.patch.object(development, "finished", lambda: True)
        development_done.start()
        self.addCleanup(development_done.stop)
        planner._save_state(state)
        from backend import archive, recipes
        recipes.remember([{"recipe": recipes.DEFAULT, "run": "x", "gain_per_hour": 0.1, "gain": 0.1, "hours": 1}])
        with mock.patch.object(planner, "_active_item", lambda: {"id": "x", "introspection": None, "layers": 4}), \
                mock.patch.object(archive, "cells", lambda: {"filled": 3}), \
                mock.patch.object(plans, "shrink_teacher", lambda: None), \
                mock.patch.object(breeding, "ready", lambda run: True):
            first = planner.today("sleep")
            planner.done(first)
            second = planner.today("sleep")
            planner.done(second)
            self.assertEqual([first["activity"], second["activity"], planner.today("sleep")["activity"]],
                             ["breed", "evolrl", "sleep"])
        # A month in which breeding never helped: it waits twice as long.
        with mock.patch.object(planner, "_tried", lambda: {"breed": {"tried": 3, "helped": 0}}):
            self.assertEqual(planner.period("breed", planner._tried()), 2 * planner.WEEK)


@unittest.skipUnless(HAS_TORCH, "PyTorch optional")
class BreedingMachineTests(LabBase):
    def setUp(self):
        super().setUp()
        schedule.set_grid("always")

    def train(self, name, config):
        run = tc.start("long", dataset=name, device="cpu", total_steps=100, hours=0.1, config=config, launch=False)["id"]
        tc.worker(run)
        time.sleep(1.1)
        return tc._summary(tc._run_dir(run))

    def child(self, anchor, seed, scale=0.02):
        ckpt = "runs/%s/language-longrun.pt.best.pt" % anchor
        state = torch.load(tc.folder() / ckpt, map_location="cpu", weights_only=True)
        g = torch.Generator().manual_seed(seed)
        weights = {k: (v + scale * v.float().std().clamp(min=1e-3) * torch.randn(v.shape, generator=g)).to(v.dtype)
                   if v.is_floating_point() and v.numel() > 1 else v for k, v in state["weights"].items()}
        run_id = plans.new_version(ckpt, weights, "branch", "(тест)", anchor)
        tc.exam_worker(run_id)
        time.sleep(1.1)
        return run_id

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

    def test_breeding_plan_merge_guard_and_majority_plan(self):
        name = dataset()
        anchor = self.train(name, dict(LAB, arch={"lab": True}))
        tc.activate(anchor["id"])
        self.assertFalse(breeding.ready(anchor["id"]))
        a, b = self.child(anchor["id"], 1), self.child(anchor["id"], 2)
        self.assertTrue(breeding.ready(anchor["id"]))
        self.assertEqual(breeding.lineage(a)[:2], [a, anchor["id"]])

        real = breeding.breed
        with mock.patch.object(breeding, "breed", lambda *x, **kw: real(*x, **dict(kw, seconds=2))):
            plan = self.run_plan("breed")
        self.assertEqual(plan["state"], "finished", plan.get("result"))
        self.assertEqual(sorted(p["run"] for p in plan["made"]["parents"]), sorted([a, b]))
        self.assertGreater(plan["made"]["children"], 0)
        self.assertEqual(breeding.status()["runs"], 1)
        if plan.get("result_run"):
            item = tc._summary(tc._run_dir(plan["result_run"]))
            self.assertEqual(item["kind"], "breed")
            self.assertIsNotNone(item["exam_per_char"])
            self.assertEqual(item["origin"]["how"], "merged")

        # Two versions that learned the same thing from one ancestor are near-clones: not bred.
        ckpt = tc._run_dir(a) / "language-longrun.pt.best.pt"
        state = torch.load(ckpt, map_location="cpu", weights_only=True)
        base = torch.load(tc._run_dir(anchor["id"]) / "language-longrun.pt.best.pt", map_location="cpu", weights_only=True)
        twin_weights = {k: (base["weights"][k] + 1.001 * (v - base["weights"][k])) if v.is_floating_point() else v
                        for k, v in state["weights"].items()}
        twin = plans.new_version("runs/%s/language-longrun.pt.best.pt" % anchor["id"], twin_weights, "branch", "(близнец)", anchor["id"])
        time.sleep(1.1)
        with self.assertRaisesRegex(ValueError, "почти клоны"):
            tc.merge(a, twin, launch=False)
        merged = tc.merge(a, b, launch=False)   # siblings that went different ways are fine
        self.assertEqual(merged["kind"], "merge")

        store = sl._load()
        for i in range(30):
            store["items"].append({"id": "k%d" % i, "prompt": "Как дела %d?" % i, "answer": "Хорошо %d." % i,
                                   "ts": time.time(), "rating": "up", "correction": None, "source": "yorika-chat"})
        sl._save(store)

        def think(model, state, question, drafts=5, seed=0, **kw):
            agreed = "Ответ: 7." if "Как дела" not in question else "Хорошо, спасибо."
            return {"texts": [agreed, "Думаю так. " + agreed, agreed, "Ответ: 1.", "не знаю"], "answer": agreed}
        time.sleep(1.1)
        with mock.patch("backend.brain.think", think):
            plan = self.run_plan("evolrl", prompts=40)
        self.assertEqual(plan["state"], "finished", plan.get("result"))
        made = plan["made"]
        self.assertGreaterEqual(made["kept"], 10)
        self.assertLessEqual(made["right"], made["tasks"])
        self.assertEqual(selfevolve.status()["runs"], 1)
        lesson = tc._read(tc.folder() / "plan" / "r1-0.json")
        self.assertTrue(any(r["source"] == "evolrl" and r["answer"].startswith("Думаю так") for r in lesson))


class PageTests(unittest.TestCase):
    def test_cards_and_names(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / "www" / "training.html").read_text(encoding="utf-8")
        js = (root / "www" / "training.js").read_text(encoding="utf-8")
        for node in ('data-evo-plan="breed"', 'data-evo-plan="evolrl"', 'id="breed-list"', 'id="evolrl-list"', 'id="rhythm-list"',
                     'data-icon="merge"', 'data-icon="vote"'):
            self.assertIn(node, html)
        self.assertEqual(js.count('breed:"Скрещивание по рецепту"'), 2)
        for icon in ("merge:[", "vote:["):
            self.assertIn(icon, js)
        from backend import night_cycle, summary
        for kind in ("breed", "evolrl"):
            self.assertIn(kind, plans.KINDS)
            self.assertIn(kind, night_cycle.ACTIVITIES)
            self.assertIn(kind, summary.NAMES)


if __name__ == "__main__":
    unittest.main()
