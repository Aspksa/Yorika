"""The school of reasoning: Piaget's stages, the logic engine, prover and checker, concepts,
analogies, self-knowledge, steps moved inside and the insight experiment, joined to the autopilot."""
import random
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import analogy, concepts, development, latent, logic, metacog, planner, plans, prover, reasoning, schedule, solver
from backend import self_learning as sl
from backend import training_center as tc
from tests.test_learning_lab import LabBase, dataset
from tests.test_living_brain import LAB

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


class SolverTests(unittest.TestCase):
    def test_engine_solves_every_task_from_its_facts(self):
        rng = random.Random(4)
        for _ in range(2000):
            t = logic.task(rng, rng.randint(1, 5))
            found = solver.derive(solver.facts_of(t["q"]))
            self.assertEqual(found["answer"].casefold(), str(t["answer"]).casefold(), t["q"])

    def test_engine_never_guesses(self):
        self.assertIsNone(solver.derive(["ряд 1 5 2 9"]))
        self.assertIsNone(solver.derive(["Аня > Боря", "Вика > Гена"]))      # two at the top: unknown
        self.assertIsNone(solver.derive(["число пять"]))
        self.assertEqual(solver.derive(["Аня есть лисы", "все лисы есть звери", "вопрос Аня есть птицы"])["answer"], "неизвестно")
        self.assertEqual(solver.apply("просто текст"), ("просто текст", False))

    def test_engine_answer_beats_the_guess_in_think(self):
        from backend import brain
        drafts = iter([{"text": "Ответ: 9.", "confidence": -0.1}, {"text": "Факты: число 5; плюс 3. Ответ: 9.", "confidence": -2.0},
                       {"text": "Шаг 1: среда + 5 дн. = суббота. Ответ: суббота.", "confidence": -0.2}])
        with mock.patch.object(brain, "generate", lambda *a, **kw: next(drafts)), \
                mock.patch.object(brain, "difficulty", lambda *a: 0.0):
            out = brain.think(None, {"arch": {}}, "У Лисы было 5 орехов. Она нашла ещё 3. Сколько у неё теперь?", drafts=3)
        self.assertEqual(out["answer"], "Факты: число 5; плюс 3. Ответ: 8.")
        self.assertTrue(out["solver"])
        self.assertEqual(solver.wrong_steps("среда + 5 дн. = суббота"), 1)
        self.assertEqual(solver.wrong_steps("среда + 5 дн. = понедельник"), 0)


class ProverConceptAnalogyTests(unittest.TestCase):
    def test_sneaky_breaks_one_step_the_checker_can_see(self):
        rng = random.Random(1)
        for t in solver.fresh_tasks(60, 2, 3):
            found = prover.sneaky(t, rng)
            if not found:
                continue
            steps = prover.steps_of(found["text"])
            self.assertEqual(sum(prover.step_wrong(s) for s in steps), 1, found)
            self.assertTrue(prover.step_wrong(steps[found["step"] - 1]))
            self.assertTrue(prover.checker_right(prover.check_answer(found), found))
            self.assertFalse(prover.checker_right("Решение верное.", found))
            self.assertTrue(prover.legible(t["solution"], t["answer"]) or not any(prover.checkable(s) for s in prover.steps_of(t["solution"])))

    def test_concepts_compress_solutions(self):
        tasks = solver.fresh_tasks(200, 1, 4)
        library = concepts.mine([t["solution"] for t in tasks])
        names = [c["name"] for c in library]
        self.assertIn("сдвинуть день, потом сдвинуть день", names)
        self.assertEqual(concepts.pattern("среда + 5 дн. = суббота"), "ДЕНЬ + N дн. = ДЕНЬ")
        long = next(t for t in tasks if len(prover.steps_of(t["solution"])) >= 3 and t["solution"].count("дн.") >= 2)
        text, used = concepts.rewrite(long["solution"], library)
        self.assertGreater(used, 0)
        self.assertLess(len(prover.steps_of(text)), len(prover.steps_of(long["solution"])))
        self.assertTrue(logic.correct(text, long["answer"]))

    def test_analogy_never_teaches_the_held_out_guise(self):
        with mock.patch.object(analogy, "transfer", lambda loaded, tasks: 3):
            pairs, made = analogy.lessons(None, seed=1, count=60)
        text = " ".join(q + a for q, a in pairs)
        self.assertNotIn("складе", text)
        self.assertNotIn("пришёл раньше", text)
        self.assertEqual(made["transfer"], 3)
        held = analogy.transfer_tasks()
        self.assertTrue(all(t["guise"] in analogy.HELD_OUT.values() for t in held))
        for t in held:
            self.assertTrue(logic.correct(analogy.solution(t), t["answer"]))


class DevelopmentMetacogLatentTests(LabBase):
    def test_stages_exams_and_lessons_are_disjoint(self):
        exam = development._banned()
        self.assertEqual(len(exam), development.EXAM * len(development.STAGES))
        with mock.patch.object(development, "exam", lambda loaded: {"0": 0.9, "1": 0.5, "2": 0.0, "3": 0.0}):
            pairs, made = development.lessons(None, seed=3, count=80)
        self.assertEqual(made["stage"], 1)
        self.assertEqual(development.load()["stage"], 1)
        self.assertFalse({q for q, _ in pairs} & exam)
        self.assertTrue(all(logic.answer_of(a) for _, a in pairs))
        self.assertEqual(development.stage_of({"0": 1, "1": 1, "2": 0.8, "3": 0.85}), 4)

    def test_calibration_beats_guessing_only_when_signals_predict(self):
        rng = random.Random(0)
        rows = [([e, -e / 2], int(e < 1.5)) for e in (rng.uniform(0, 3) for _ in range(200))]
        w = metacog.fit(rows[:100])
        self.assertLess(metacog.brier(rows[100:], w), metacog.brier(rows[100:]) / 2)
        self.assertEqual([metacog.drafts_for(p, 3) for p in (0.9, 0.6, 0.2, None)], [1, 3, 5, 3])
        tc._write(metacog._path(), {"w": w, "useful": True, "run": "a"})
        with mock.patch.object(metacog, "features", lambda *a: [0.1, -0.05]):
            self.assertGreater(metacog.sure(None, None, "q", 0, "a"), 0.8)
            self.assertIsNone(metacog.sure(None, None, "q", 0, "b"))   # made for another version

    def test_latent_stages_move_inside_one_step_at_a_time(self):
        solution = "Шаг 1: 5 + 3 = 8. Шаг 2: 8 - 2 = 6. Ответ: 6."
        self.assertEqual(latent.internalized(solution, 0), solution)
        self.assertEqual(latent.internalized(solution, 1), "Шаг 1: …. Шаг 2: 8 - 2 = 6. Ответ: 6.")
        self.assertEqual(latent.internalized(solution, 4), "Ответ: 6.")
        latent.after({}, "waiting")
        self.assertEqual(latent.load()["stage"], 1)
        latent.after({}, "rolled_back")
        latent.after({}, "rolled_back")
        self.assertEqual(latent.load()["stage"], 0)


class PlannerTests(LabBase):
    def test_school_of_reasoning_in_order_and_stages_first(self):
        state = planner._state()
        state["history"] = {k: time.time() for k in planner.EVERY if k not in reasoning.KINDS + reasoning.LAB}
        planner._save_state(state)
        from backend import archive, recipes
        recipes.remember([{"recipe": recipes.DEFAULT, "run": "x", "gain_per_hour": 0.1, "gain": 0.1, "hours": 1}])
        with mock.patch.object(planner, "_active_item", lambda: {"id": "x", "introspection": None, "layers": 4}), \
                mock.patch.object(archive, "cells", lambda: {"filled": 3}), \
                mock.patch.object(plans, "shrink_teacher", lambda: None):
            order = []
            for _ in range(len(reasoning.KINDS + reasoning.LAB) + 2):
                choice = planner.today("sleep")
                order.append(choice["activity"])
                planner.done(choice)
        self.assertEqual(order, ["development", "solver", "prover", "concepts", "analogy", "metacog", "latent", "emergent",
                                 "grounded", "scientist", "counterfactual", "teaching", "grok", "observer", "budget",
                                 "sleep", "sleep"])
        state = planner._state()
        state["history"]["development"] = 0
        planner._save_state(state)
        with mock.patch.object(planner, "_active_item", lambda: {"id": "x", "introspection": None, "layers": 4}), \
                mock.patch.object(archive, "cells", lambda: {"filled": 3}), \
                mock.patch.object(plans, "shrink_teacher", lambda: None), \
                mock.patch.object(development, "finished", lambda: True):
            self.assertEqual(planner.today("sleep")["activity"], "sleep")


@unittest.skipUnless(HAS_TORCH, "PyTorch optional")
class SchoolMachineTests(LabBase):
    def setUp(self):
        super().setUp()
        schedule.set_grid("always")

    def run_plan(self, kind, **kw):
        plans.start(kind, minutes=1, device="cpu", launch=False, **kw)
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
        return plans.current()

    def test_every_kind_runs_as_a_plan_and_the_page_shows_it(self):
        name = dataset()
        run = tc.start("long", dataset=name, device="cpu", total_steps=100, hours=0.1, config=dict(LAB, arch={"lab": True}),
                       launch=False)["id"]
        tc.worker(run)
        time.sleep(1.1)
        tc.activate(run)
        store = sl._load()
        for i in range(30):
            store["items"].append({"id": "k%d" % i, "prompt": "Как дела %d?" % i, "answer": "Хорошо %d." % i,
                                   "ts": time.time(), "rating": "up", "correction": None, "source": "yorika-chat"})
        sl._save(store)
        small = {"solver": 40, "concepts": 80, "analogy": 30, "development": 60, "latent": 40, "grounded": 60,
                 "counterfactual": 40}
        from backend import teaching
        for kind in reasoning.KINDS:
            # The tiny test model never solves anything; here the younger one solves whenever it gets a hint.
            with mock.patch.object(reasoning, "make", lambda k, loaded, seed=0, run_id=None: _small(k, loaded, seed, run_id, small)), \
                    mock.patch.object(teaching, "_solves", lambda student, q, answer: q.startswith("Подсказка")):
                plan = self.run_plan(kind)
            self.assertEqual(plan["state"], "finished", (kind, plan.get("result")))
            self.assertTrue(reasoning.describe(kind, plan["made"]), kind)
            time.sleep(1.1)
        status = reasoning.status()
        self.assertTrue(all(status["last"][k] for k in reasoning.KINDS))
        from backend import grokking
        real = grokking.experiment
        with mock.patch.object(grokking, "experiment", lambda **kw: real(**dict(kw, seconds=2))):
            plan = self.run_plan("grok")
        self.assertEqual(plan["state"], "finished", plan.get("result"))
        self.assertIn("Озарение", plan["result"])
        self.assertTrue(grokking.status()["last"]["strong"]["curve"])
        from backend import budget, observer
        for kind, module, count in (("observer", observer, 16), ("budget", budget, 4)):
            real_lab = module.experiment
            time.sleep(1.1)
            with mock.patch.object(module, "experiment", lambda loaded, run_id, seed=0, real_lab=real_lab, count=count:
                                   real_lab(loaded, run_id, seed, count=count)):
                plan = self.run_plan(kind)
            self.assertEqual(plan["state"], "finished", (kind, plan.get("result")))
            self.assertIn(reasoning.TITLES[kind], plan["result"])
            self.assertTrue(reasoning.status()["last"][kind]["text"])
        self.assertEqual(reasoning.status()["observer"]["run"], run)


def _small(kind, loaded, seed, run_id, small):
    """The same lessons with fewer tasks, so the test stays short."""
    from backend import analogy as an, concepts as co, development as de, latent as la, metacog as me, prover as pr, solver as so
    if kind == "metacog":
        return me.lessons(loaded, seed, count=20, run_id=run_id)
    if kind == "prover":
        return pr.lessons(loaded, seed, count=12)
    from backend import counterfactual as cf, emergent as em, grounded as gr, scientist as sc, teaching as te
    if kind == "emergent":
        return em.lessons(loaded, seed, generations=2)
    if kind == "scientist":
        return sc.lessons(loaded, seed)
    if kind == "teaching":
        return te.lessons(loaded, seed, count=24, run_id=run_id)
    module = {"solver": so, "concepts": co, "analogy": an, "development": de, "latent": la, "grounded": gr,
              "counterfactual": cf}[kind]
    return module.lessons(loaded, seed, count=small[kind])


class PageTests(unittest.TestCase):
    def test_eight_cards_with_buttons(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / "www" / "training.html").read_text(encoding="utf-8")
        js = (root / "www" / "training.js").read_text(encoding="utf-8")
        self.assertIn('id="reason-title"', html)
        from backend import night_cycle, summary
        self.assertIn('id="beyond-title"', html)
        for kind in reasoning.KINDS + reasoning.LAB:
            self.assertIn('data-evo-plan="%s"' % kind, html)
            self.assertIn('id="rs-%s"' % kind, html)
            self.assertIn(kind, plans.KINDS)
            self.assertIn(kind, night_cycle.ACTIVITIES)
            self.assertIn(kind, summary.NAMES)
            self.assertIn(kind, planner.EVERY)
        self.assertIn("function renderReasoning", js)


if __name__ == "__main__":
    unittest.main()
