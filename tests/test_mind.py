"""Ways of thinking from living brains: dreams from answer to cause, neurogenesis, two hemispheres,
evolving learning rules, the language of thought, gene exchange; plus more data, the diary,
screen help and the one-button self-check."""
import random
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import diary
from backend import dreams
from backend import harvest
from backend import logic
from backend import mind
from backend import plans
from backend import recipes
from backend import schedule
from backend import screen
from backend import selfcheck
from backend import self_learning as sl
from backend import simworld
from backend import training_center as tc
from tests.test_learning_lab import LabBase, dataset
from tests.test_living_brain import LAB

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


class ThoughtAndDreamTests(unittest.TestCase):
    def test_dreams_are_true_and_never_exam_questions(self):
        pairs = dreams.dream(120, seed=4)
        self.assertGreater(len(pairs), 100)
        exam = logic._exam_questions() | simworld._banned()
        self.assertFalse({q for q, _ in pairs} & exam)
        rng = random.Random(2)
        for make in dreams.INVERSE:
            for _ in range(30):
                q, solution, answer = make(rng)
                self.assertTrue(logic.correct(solution, answer), (q, solution))

    def test_hidden_thoughts(self):
        text = "⟦иду назад; 162 : 9 = 18⟧ Ответ: 18."
        self.assertEqual(mind.strip_thoughts(text), "Ответ: 18.")
        self.assertEqual(mind.thoughts_of(text), ["иду назад; 162 : 9 = 18"])
        self.assertEqual(mind.strip_thoughts("Привет ⟦не закрыто"), "Привет")
        converted = mind.as_thought("Шаг 1: 3 + 4 = 7. Ответ: 7.")
        self.assertEqual(converted, "⟦3 + 4 = 7⟧ Ответ: 7.")
        self.assertTrue(logic.correct(converted, "7"))
        lessons = mind.thought_lessons(60, seed=1)
        self.assertTrue(all(a.startswith("⟦") for _, a in lessons))

    def test_learning_rules(self):
        from backend.neural_language_longrun import _groups, check_rule
        self.assertIsNone(check_rule(None))
        self.assertEqual(check_rule({"wd": 0.05, "plasticity": 2}), {"plasticity": 2, "wd": 0.05})
        for bad in ({"wd": 1.0}, {"speed": 1}, {"clip": "1"}, [1]):
            with self.assertRaises(ValueError):
                check_rule(bad)
        if HAS_TORCH:
            from backend.neural_language_bpe_v2 import make_model
            model = make_model(torch, vocab_size=300, width=32, heads=2, layers=3, context=32, arch={"lab": True})
            groups = _groups(model, 0.001, {"plasticity": 4.0})
            self.assertAlmostEqual(groups[0]["lr"], 0.001)
            self.assertAlmostEqual(groups[2]["lr"], 0.004)
            self.assertEqual(sum(len(g["params"]) for g in groups), len(list(model.parameters())))
        rng = random.Random(3)
        children = [recipes.mutate(recipes.DEFAULT, rng) for _ in range(40)]
        self.assertTrue(all(recipes.valid(c) for c in children))
        self.assertTrue(any(c.get("rule") for c in children))
        self.assertIn("пластичность", recipes.describe(next(c for c in children if c.get("rule"))))


class HelperTests(LabBase):
    def test_harvest_mixes_your_examples_with_verified_practice(self):
        store = sl._load()
        for i in range(50):
            store["items"].append({"id": "h%d" % i, "prompt": "Как дела у лисы %d?" % i, "answer": "Хорошо %d." % i,
                                   "ts": time.time(), "rating": "up", "correction": None, "source": "yorika-chat"})
        sl._save(store)
        made = harvest.build(400, seed=1)
        self.assertEqual(made["count"], 400)
        self.assertEqual(made["mix"]["experience"], 50)
        self.assertFalse(made["long_ready"])  # 400 is below the 10 000 a long training needs
        records = tc._load_records(made["name"])
        exam = logic._exam_questions() | simworld._banned()
        self.assertFalse({r["prompt"] for r in records} & exam)
        self.assertIsNone(tc.long_gate(records) if len(records) >= tc.MIN_LONG_RECORDS else None)
        with self.assertRaises(ValueError):
            harvest.build(5)

    def test_screen_help_reads_only_on_request_and_saves_nothing(self):
        fake = lambda: '{"text": "Окно\\nError: файл не найден\\nОК", "lines": 3}'
        self.assertEqual(screen.read_text(fake).splitlines()[1], "Error: файл не найден")
        self.assertTrue(screen.focus("a\nError: x\nb").startswith("Error: x"))
        result = screen.help_with("Что не так?", runner=fake)
        self.assertIsNone(result["answer"])  # no trained version yet: only the text is shown
        self.assertIn("файл не найден", result["text"])
        with self.assertRaisesRegex(ValueError, "экран"):
            screen.help_with("?", runner=lambda: '{"error": "denied"}')
        self.assertFalse(list(tc.folder().glob("*screen*")))

    def test_diary_uses_only_measured_numbers(self):
        entry = diary.write({"steps": [{"step": "sim", "result": "прожито 10 жизней, побед 3"}]})
        self.assertIn("Чему училась: прожито 10 жизней, побед 3.", entry["lines"])
        self.assertIsNone(entry["numbers"]["logic"])
        self.assertEqual(len(diary.entries()), 1)
        entry = diary.write(None)
        self.assertTrue(any("не училась" in line for line in entry["lines"]))


@unittest.skipUnless(HAS_TORCH, "PyTorch optional")
class MindMachineTests(LabBase):
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

    def test_rebirth_rule_hemispheres_thoughts_and_gene_exchange(self):
        from backend.growth import rebirth
        name = dataset()
        dense = dict(LAB, arch={"lab": True}, context=256)
        base = self.train(name, dense)
        best = tc._run_dir(base["id"]) / "language-longrun.pt.best.pt"
        state = torch.load(best, map_location="cpu", weights_only=True)
        state["weights"]["blocks.0.ffn.0.bias"][:10] = -100.0  # ten neurons that never fire
        torch.save(state, best)
        born = rebirth(best, tc.folder() / "reborn.pt", tc._prepare(tc._load_records(name))["train"][:32])
        self.assertGreaterEqual(born["reborn"][1], 10)
        new = torch.load(tc.folder() / "reborn.pt", map_location="cpu", weights_only=True)["weights"]
        self.assertTrue(bool((new["blocks.0.ffn.2.weight"][:, :10] == 0).all()))
        self.assertTrue(bool((new["blocks.0.ffn.0.bias"][:10] == 0).all()))
        # A learning rule travels with the run and is checked on resume.
        ruled = self.train(name, dict(dense, rule={"warmup": 5, "plasticity": 2.0, "wd": 0.05}),
                           init="runs/%s/language-longrun.pt.best.pt" % base["id"])
        self.assertEqual(ruled["state"], "finished")
        tc.activate(base["id"])
        store = sl._load()
        for i in range(30):
            store["items"].append({"id": "m%d" % i, "prompt": "Что нового %d?" % i, "answer": "Всё хорошо %d." % i,
                                   "ts": time.time(), "rating": "up", "correction": None, "source": "yorika-chat"})
        sl._save(store)
        self.assertEqual(mind.partner(base["id"]), ruled["id"])
        plan = self.run_plan("hemispheres", prompts=20)
        self.assertEqual(plan["state"], "finished", plan.get("result"))
        self.assertEqual(plan["made"]["asked"], 20 + 5)
        self.assertTrue(mind.trust())
        plan = self.run_plan("thoughts")
        self.assertEqual(plan["state"], "finished", plan.get("result"))
        # Gene exchange: versions of one line trade blocks only when the exam sample improves.
        donors = mind.donors(base["id"])
        self.assertIn(ruled["id"], donors)
        run_id, made = mind.exchange(base["id"], donors, tc._prepare(tc._load_records(name))["validation"])
        if run_id:
            self.assertEqual(tc._summary(tc._run_dir(run_id))["kind"], "ecosystem")
            self.assertLess(made["end"], made["start"])
        else:
            self.assertEqual(made["taken"], [])

    def test_selfcheck_runs_every_step_and_cleans_up(self):
        report = selfcheck.run(device="cpu", seconds=3)
        steps = {s["step"]: s for s in report["steps"]}
        self.assertTrue(steps["train"]["ok"], steps["train"])
        self.assertTrue(steps["exams"]["ok"], steps["exams"])
        self.assertTrue(steps["tidy"]["ok"])
        self.assertIn("Самопроверка Yorika", report["text"])
        self.assertEqual(tc.runs(), [])  # the throwaway version is gone
        self.assertEqual(selfcheck.last()["state"], "finished")


if __name__ == "__main__":
    unittest.main()
