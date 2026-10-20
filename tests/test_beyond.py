"""Language, science and self-observation: her own language over generations, words through
actions, the scientist, counterfactuals, teaching a younger one, the inner observer and the price
of a thought."""
import random
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import budget, counterfactual, emergent, grounded, logic, metacog, observer, scientist, solver, teaching
from tests.test_learning_lab import LabBase

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


class EmergentTests(LabBase):
    def test_topsim_measures_compositionality(self):
        compositional = {o: (o[0], 4 + o[1]) for o in emergent.OBJECTS}
        self.assertEqual(emergent.topsim(compositional), 1.0)
        rng = random.Random(0)
        names = rng.sample([(a, b) for a in range(8) for b in range(8)], 16)
        holistic = dict(zip(emergent.OBJECTS, names))
        self.assertLess(emergent.topsim(holistic), 0.5)

    def test_generations_through_a_bottleneck_become_more_compositional(self):
        start, end = [], []
        for seed in range(4):
            _, rows = emergent.evolve(None, 5, seed)
            self.assertGreaterEqual(rows[-1]["accuracy"], 0.9)
            start.append(rows[0]["topsim"])
            end.append(rows[-1]["topsim"])
        self.assertGreater(sum(end) / 4, sum(start) / 4 + 0.15)

    def test_language_lives_on_and_is_grounded_in_russian(self):
        with mock.patch.object(emergent, "measure", lambda loaded, language, objects: 0):
            pairs, made = emergent.lessons(None, seed=1, generations=2)
            second, made2 = emergent.lessons(None, seed=2, generations=1)
        self.assertEqual(made2["generation"], 3)
        held = {emergent.name(o) for o in emergent.asked_only(0)}
        self.assertFalse(any("Ответ: %s." % h == a for h in held for _, a in pairs))
        self.assertTrue(all(logic.answer_of(a) for _, a in pairs))
        self.assertEqual(emergent.name((0, 3)), "красная звезда")
        self.assertEqual(len(emergent.status()["words"]), 16)


class GroundedTests(unittest.TestCase):
    def test_actions_are_executed_and_stop_at_the_edge(self):
        world = {"objects": {("синий", "квадрат"): (4, 2)}, "tree": (1, 1)}
        end, _ = grounded.execute(world, ("синий", "квадрат"), [("вправо", 3), ("вверх", 1)])
        self.assertEqual(end, (5, 1))

    def test_lessons_never_show_the_held_out_object_and_fit(self):
        rng = random.Random(3)
        for _ in range(300):
            t = grounded.task(rng)
            self.assertNotIn("Жёлтая звезда", t["q"])
            self.assertTrue(grounded.check(t, t["solution"]), t)
            self.assertLessEqual(len(t["q"]) + len(t["solution"]), 360)
        self.assertTrue(all("Жёлтая звезда" in t["q"] for t in grounded.transfer_tasks()))
        self.assertTrue(grounded.check({"answer": "(2,3)"}, "Ответ: (2, 3)."))


class ScientistTests(LabBase):
    def test_conjectures_are_refuted_by_the_smallest_counterexample(self):
        results = {r["text"]: r for r in scientist.research()}
        self.assertTrue(results["n³ − n делится на 6"]["holds"])
        self.assertEqual(results["n² + n + 41 — простое число"]["counterexample"], 40)
        self.assertEqual(results["если n делится на 2 и на 4, то n делится на 8"]["counterexample"], 4)
        self.assertTrue(results["сумма 5 чисел подряд, начиная с n, делится на 5"]["holds"])
        self.assertFalse(results["сумма 4 чисел подряд, начиная с n, делится на 4"]["holds"])
        self.assertTrue(results["через 14 дн. после любого дня недели наступит тот же день недели"]["holds"])

    def test_lessons_say_checked_not_proved_and_asked_ones_stay_out(self):
        with mock.patch.object(scientist, "predict", lambda loaded, results: 0):
            pairs, made = scientist.lessons(None, seed=0)
        _, asked = scientist.split(0)
        asked_texts = {scientist.question(c[0]) for c in asked}
        self.assertFalse(asked_texts & {q for q, _ in pairs})
        self.assertTrue(all(logic.answer_of(a) in ("да", "нет") for _, a in pairs))
        self.assertFalse(any("доказано" in a for _, a in pairs))
        self.assertGreater(made["laws"], 10)


class CounterfactualTests(unittest.TestCase):
    def test_every_counterfactual_answer_is_the_solvers(self):
        items = counterfactual.tasks(200, seed=1, max_level=3)
        self.assertGreater(len(items), 150)
        for t in items:
            self.assertTrue(logic.correct(t["solution"], t["answer"]))
        self.assertTrue(any(t["same"] for t in items))
        self.assertTrue(any(t["answer"] == "неизвестно" and "не знали" in t["q"] for t in items))

    def test_changed_number_is_recomputed(self):
        t = {"q": "У Лисы было 5 орехов. Она нашла ещё 3. Сколько у неё теперь?", "answer": "8"}
        rng = mock.Mock()
        rng.choice = lambda xs: 7 if 7 in xs else xs[0]
        made = counterfactual.make(rng, t)
        self.assertIn("«Она нашла ещё 7»", made["q"])
        self.assertEqual(made["answer"], "12")


class TeachingTests(LabBase):
    def test_only_explanations_that_make_the_younger_one_solve_count(self):
        tasks = solver.fresh_tasks(6, 1, 2)
        with mock.patch.object(solver, "fresh_tasks", lambda *a: tasks), \
                mock.patch("backend.brain.think", lambda *a, **kw: {"answer": "Подумай о фактах."}), \
                mock.patch.object(teaching, "younger", lambda run_id: (None, None)), \
                mock.patch.object(teaching, "_solves", lambda student, q, answer: "Выпиши факты" in q):
            pairs, made = teaching.lessons(("m", {}), seed=0, count=6)
        self.assertEqual((made["alone"], made["her_helped"], made["code_helped"]), (0, 0, 6))
        self.assertTrue(all(a.startswith("Выпиши факты") for _, a in pairs))
        with mock.patch.object(solver, "fresh_tasks", lambda *a: tasks), \
                mock.patch("backend.brain.think", lambda *a, **kw: {"answer": "Сложи по шагам."}), \
                mock.patch.object(teaching, "younger", lambda run_id: (None, None)), \
                mock.patch.object(teaching, "_solves", lambda student, q, answer: "Сложи" in q):
            pairs, made = teaching.lessons(("m", {}), seed=0, count=6)
        self.assertEqual(made["her_helped"], 6)
        self.assertEqual(made["younger"], "она же, сразу и без раздумий")


class BudgetTests(LabBase):
    def test_thresholds_trade_accuracy_for_work(self):
        # Sure ones are right with one draft; unsure ones need five.
        rows = [{"p": 0.9, "right": {1: 1, 3: 1, 5: 1}, "work": {1: 1, 3: 3, 5: 5}} for _ in range(10)]
        rows += [{"p": 0.1, "right": {1: 0, 3: 0, 5: 1}, "work": {1: 1, 3: 3, 5: 5}} for _ in range(10)]
        best = budget.tune(rows)
        self.assertEqual(budget.choose(0.9, best["hi"], best["lo"]), 1)
        self.assertEqual(budget.choose(0.1, best["hi"], best["lo"]), 5)
        self.assertEqual(best["accuracy"], 1.0)
        self.assertEqual(budget.thresholds("a"), (0.8, 0.4))
        from backend import training_center as tc
        tc._write(budget._path(), {"run": "a", "rule": {"hi": 0.6, "lo": 0.2}})
        self.assertEqual(budget.thresholds("a"), (0.6, 0.2))
        self.assertEqual(budget.thresholds("b"), (0.8, 0.4))
        self.assertEqual(metacog.drafts_for(0.7, 3, "a"), 1)
        self.assertEqual(metacog.drafts_for(0.7, 3, "b"), 3)


@unittest.skipUnless(HAS_TORCH, "PyTorch optional")
class ObserverTests(LabBase):
    def test_probe_reads_a_signal_hidden_in_the_state(self):
        g = torch.Generator().manual_seed(0)
        xs = [torch.randn(32, generator=g) for _ in range(200)]
        ys = [int(x[3] > 0) for x in xs]
        probe = observer.fit(xs[:100], ys[:100])
        ps = [observer.predict(probe, x) for x in xs[100:]]
        self.assertLess(observer.brier(ps, ys[100:]), 0.15)   # guessing the average gives about 0.25

    def test_hidden_state_and_chat_use_only_a_useful_probe(self):
        from backend.neural_language_bpe_v2 import make_model
        from backend.neural_bpe_v1 import OFFSET, train
        tokenizer = train(["привет мир " * 50], max_merges=8)
        model = make_model(torch, vocab_size=OFFSET + 256 + len(tokenizer["merges"]), width=16, heads=2, context=32, layers=1,
                           arch={"lab": True}).eval()
        state = {"tokenizer": tokenizer, "config": [0, 0, 0, 32]}
        h = observer.hidden(model, state, "привет")
        self.assertEqual(tuple(h.shape), (16,))
        self.assertIsNone(observer.sure(model, state, "привет", "a"))
        from backend import training_center as tc
        tc._write(observer._path(), {"run": "a", "useful": True, "probe": {"w": [0.0] * 16, "b": 2.0, "mean": [0.0] * 16,
                                                                           "std": [1.0] * 16}})
        self.assertAlmostEqual(observer.sure(model, state, "привет", "a"), 0.881, places=3)
        self.assertIsNone(observer.sure(model, state, "привет", "b"))
        self.assertAlmostEqual(metacog.sure(model, state, "привет", -1.0, "a"), 0.881, places=3)


if __name__ == "__main__":
    unittest.main()
