"""Selection of weights, lessons and genes: evolution strategies, Pareto selection, lessons that
evolve, epigenetic gates, endosymbiosis and the memory of failures."""
import random
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import archive
from backend import planner
from backend import plans
from backend import recipes
from backend import schedule
from backend import self_learning as sl
from backend import tabu
from backend import training_center as tc
from backend.neural_language_bpe_v2 import check_arch
from tests.test_learning_lab import LabBase, dataset
from tests.test_living_brain import LAB

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

GUEST = {"width": 16, "heads": 2, "layers": 1, "arch": {"lab": True}}


class RulesTests(LabBase):
    def test_failed_changes_become_tabu_for_a_while(self):
        parent = {"layers": 4, "arch": {"lab": True}, "label": "x"}
        child = {"layers": 6, "arch": {"lab": True, "mixer": "liquid"}, "label": "y"}
        changes = tabu.diff(parent, child)
        self.assertEqual(changes, ["arch.mixer: None → liquid", "layers: 4 → 6"])
        tabu.record("архитектура", changes, False)
        self.assertFalse(tabu.banned("архитектура", changes))
        tabu.record("архитектура", changes, False)
        self.assertTrue(tabu.banned("архитектура", ["layers: 4 → 6"]))
        self.assertFalse(tabu.banned("рецепты", ["layers: 4 → 6"]))
        self.assertEqual(tabu.status()["count"], 2)
        for _ in range(tabu.TERM):
            tabu.record("архитектура", ["other"], False)
        self.assertFalse(tabu.banned("архитектура", changes))  # its term is over
        # A change that once helped never becomes tabu.
        tabu.record("рецепты", ["lr: 0.0003 → 0.0006"], True)
        for _ in range(4):
            tabu.record("рецепты", ["lr: 0.0003 → 0.0006"], False)
        self.assertFalse(tabu.banned("рецепты", ["lr: 0.0003 → 0.0006"]))
        self.assertTrue(all(recipes.valid(r) for r in recipes.candidates(4, seed=1)))

    def test_evolution_skips_tabu_changes(self):
        rng = random.Random(2)
        parent = tc.config_for("s")
        for _ in range(3):
            child = tc.mutate(parent, rng)
            tabu.record("архитектура", tabu.diff(parent, child), False)
            tabu.record("архитектура", tabu.diff(parent, child), False)
        with mock.patch.object(tc, "start_series", lambda *a, **kw: kw["configs"]):
            configs = tc.start_evolution("d.json", 6, seed=3, launch=False)
        for child in configs[1:]:
            self.assertTrue(child["changes"])
            self.assertFalse(tabu.banned("архитектура", child["changes"]))

    def test_pareto_front_keeps_small_versions_with_a_worse_exam(self):
        runs = [{"id": "a", "mode": "long", "has_best": True, "exam_per_char": 1.0, "parameters": 9e6, "logic": None},
                {"id": "b", "mode": "long", "has_best": True, "exam_per_char": 1.2, "parameters": 2e6, "logic": None},
                {"id": "c", "mode": "long", "has_best": True, "exam_per_char": 1.3, "parameters": 9e6, "logic": None},
                {"id": "d", "mode": "long", "has_best": True, "exam_per_char": 1.4, "parameters": 9e6,
                 "logic": {"levels": {"1": 1.0}}}]
        with mock.patch.object(tc, "runs", lambda: runs):
            ranks = {p["run"]: p["rank"] for p in archive.pareto()}
            self.assertEqual(ranks, {"a": 0, "b": 0, "c": 1, "d": 0})
            self.assertEqual([p["run"] for p in archive.pareto_status()["front"]], ["b", "a", "d"])

    def test_new_genes_and_planner(self):
        self.assertEqual(check_arch({"epigenetic": True}), {"lab": True, "epigenetic": True})
        self.assertEqual(check_arch({"guest": GUEST})["guest"], GUEST)
        for bad in ({"guest": dict(GUEST, layers=0)}, {"guest": dict(GUEST, arch={"guest": GUEST})},
                    {"guest": {"width": 16}}, {"epigenetic": 1}):
            with self.assertRaises(ValueError, msg=bad):
                check_arch(bad)
        rng, seen = random.Random(5), False
        config = tc.config_for("s")
        for _ in range(200):
            config = tc.mutate(config, rng)
            seen |= bool(config["arch"].get("epigenetic"))
        self.assertTrue(seen)
        state = planner._state()
        state["history"] = {k: time.time() for k in ("rebirth", "hemispheres", "thoughts", "ecosystem", "redqueen",
                                                     "baldwin", "coevolve", "evolution", "evolrl")}
        planner._save_state(state)
        item = {"id": "x", "introspection": None, "layers": 4}
        recipes.remember([{"recipe": recipes.DEFAULT, "run": "x", "gain_per_hour": 0.1, "gain": 0.1, "hours": 1}])
        with mock.patch.object(planner, "_active_item", lambda: item), \
                mock.patch.object(archive, "cells", lambda: {"filled": 3}), \
                mock.patch.object(plans, "shrink_teacher", lambda: None), \
                mock.patch.object(plans, "symbiont", lambda run: "g"):
            order = []
            for _ in range(4):
                choice = planner.today("sleep")["activity"]
                order.append(choice)
                state["history"][choice] = time.time()
                planner._save_state(state)
        self.assertEqual(order, ["dataevo", "es", "symbiosis", "sleep"])


@unittest.skipUnless(HAS_TORCH, "PyTorch optional")
class PartsTests(unittest.TestCase):
    def model(self, arch):
        from backend.neural_language_bpe_v2 import make_model
        torch.manual_seed(0)
        return make_model(torch, vocab_size=300, width=32, heads=4, context=64, layers=2, arch=arch)

    def test_epigenome_and_guest_start_as_identity(self):
        ids = torch.randint(0, 300, (2, 30))
        base = self.model({"lab": True}).eval()
        for arch in ({"epigenetic": True}, {"guest": GUEST}):
            m = self.model(arch).eval()
            weights = m.state_dict()
            weights.update(base.state_dict())
            m.load_state_dict(weights)
            self.assertTrue(torch.allclose(base(ids), m(ids), atol=1e-6), arch)
            later = ids.clone()
            later[:, 20:] = 5
            self.assertTrue(torch.allclose(m(ids)[:, :20], m(later)[:, :20], atol=1e-5), arch)

    def test_es_moves_weights_without_gradients(self):
        from backend import es
        m = self.model({"lab": True})
        state = {"tokenizer": None, "config": [32, 4, 2, 64, 0, 1]}
        with mock.patch.object(es, "_rows", lambda st, rec: [([1, 3, 10 + i % 7, 4, 20 + i % 5, 2], 3) for i in range(40)]):
            before = [p.detach().clone() for p in m.parameters()]
            weights, made = es.evolve((m, state), [None] * 40, seconds=2, seed=1)
        self.assertGreater(made["generations"], 0)
        self.assertLessEqual(made["loss_after"], made["loss_before"])
        self.assertTrue(all(p.grad is None for p in m.parameters()))
        self.assertFalse(all(torch.equal(a, b) for a, b in zip(before, m.parameters())))
        self.assertEqual(set(weights), set(m.state_dict()))


@unittest.skipUnless(HAS_TORCH, "PyTorch optional")
class SelectionMachineTests(LabBase):
    def setUp(self):
        super().setUp()
        schedule.set_grid("always")

    def train(self, name, config):
        run = tc.start("long", dataset=name, device="cpu", total_steps=100, hours=0.1, config=config, launch=False)["id"]
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

    def test_es_dataevo_and_symbiosis_plans(self):
        from backend import data_evolution, es
        name = dataset()
        host_cfg = dict(LAB, arch={"lab": True}, context=256, width=48, heads=4)
        host = self.train(name, host_cfg)
        tc.activate(host["id"])
        store = sl._load()
        for i in range(40):
            store["items"].append({"id": "k%d" % i, "prompt": "Как дела %d?" % i, "answer": "Хорошо %d." % i,
                                   "ts": time.time(), "rating": "up", "correction": None, "source": "yorika-chat"})
        sl._save(store)

        real = es.evolve
        with mock.patch.object(es, "evolve", lambda *a, **kw: real(*a, **dict(kw, seconds=3))):
            plan = self.run_plan("es")
        self.assertEqual(plan["state"], "finished", plan.get("result"))
        self.assertGreater(plan["made"]["generations"], 0)
        self.assertEqual(es.status()["runs"], 1)
        if plan.get("result_run"):
            item = tc._summary(tc._run_dir(plan["result_run"]))
            self.assertEqual(item["kind"], "es")
            self.assertIsNotNone(item["exam_per_char"])

        plan = self.run_plan("dataevo")
        self.assertEqual(plan["state"], "finished", plan.get("result"))
        last = data_evolution.status()["last"]
        self.assertEqual(last["generation"], 1)
        self.assertGreater(last["kept"], 0)
        self.assertTrue(last["sources"])

        # A smaller version trained on the same data has the same word pieces: a specialist to engulf.
        small = self.train(name, dict(host_cfg, width=32, heads=2, seed=3))
        self.assertEqual(plans.symbiont(host["id"]), small["id"])
        self.assertIsNone(plans.symbiont(small["id"]))  # never a bigger guest
        from backend import growth
        host_best = tc._run_dir(host["id"]) / "language-longrun.pt.best.pt"
        made = growth.engulf(host_best, tc._run_dir(small["id"]) / "language-longrun.pt.best.pt", tc.folder() / "plan" / "g.pt")
        self.assertGreater(made["parameters"], made["guest_parameters"])
        plan = self.run_plan("symbiosis")
        self.assertEqual(plan["state"], "finished", plan.get("result"))
        self.assertEqual(plan["guest"], small["id"])
        lesson = tc._read(tc._run_dir(plan["round_runs"][-1]) / "run.json")["config"]
        self.assertIn("guest", lesson["arch"])


if __name__ == "__main__":
    unittest.main()
