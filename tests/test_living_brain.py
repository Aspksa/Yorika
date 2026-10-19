"""Living brain: big vocabulary, loops/experts/memory, growth, logic, thinking, quick lessons,
sleep with replay, forgetting, curiosity, evolution, crossbreeding, 4-bit compression, own chat."""
import io
import json
import os
import random
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import brain
from backend import continual
from backend import curiosity
from backend import logic
from backend import night_cycle as night
from backend import self_learning as sl
from backend import training_center as tc
from backend.neural_bpe_v1 import OFFSET, _bytes, _merge, decode, encode, train_words, validate
from tests.test_learning_lab import LabBase, dataset

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

LAB = {"width": 32, "heads": 2, "layers": 1, "context": 128, "max_merges": 300, "seed": 1, "checkpoint_every": 20,
       "batch_size": 4, "accumulate": 1, "precision": "auto", "arch": {"lab": True, "loops": 2, "experts": 2, "memory": 64}}


class TokenizerTests(unittest.TestCase):
    def test_word_bpe_is_valid_and_encode_matches_merge_order(self):
        texts = ["Привет, лиса %d! Снег идёт над лесом, а звёзды горят." % i for i in range(400)]
        manifest = train_words(texts, max_merges=600)
        validate(manifest)
        self.assertGreater(len(manifest["merges"]), 50)
        for text in texts[:30] + ["новое слово", "x"]:
            row = list(_bytes(text))
            for i, pair in enumerate(manifest["merges"]):
                row = _merge(row, pair, OFFSET + 256 + i)
            self.assertEqual(encode(text, manifest), row)
            self.assertEqual(decode(encode(text, manifest), manifest), text)
        self.assertLess(len(encode(texts[0], manifest)), len(texts[0].encode()) / 4)


@unittest.skipUnless(HAS_TORCH, "PyTorch optional")
class ArchitectureTests(unittest.TestCase):
    def test_classic_stays_identical_and_lab_features_work(self):
        from backend.neural_language_bpe_v2 import check_arch, make_model
        classic = make_model(torch, vocab_size=300, width=32, heads=2, layers=1, context=32)
        self.assertEqual(type(classic).__name__, "LanguageBrain")
        self.assertEqual(check_arch({}), {})
        with self.assertRaises(ValueError):
            check_arch({"loops": 9})
        model = make_model(torch, vocab_size=300, width=32, heads=2, layers=2, context=32,
                           arch={"loops": 3, "experts": 4, "memory": 64})
        x = torch.randint(0, 300, (2, 9))
        model.eval()
        fast, deep = model(x, passes=1), model(x, passes=3)
        self.assertEqual(fast.shape, (2, 9, 300))
        model.train()
        out = model(x)
        (out.sum() + model.aux_loss).backward()
        self.assertIsNotNone(model.aux_loss)
        del deep

    def test_growth_keeps_answers_and_compression_is_small(self):
        from backend import growth, quantize
        from backend.neural_language_bpe_v2 import make_model
        manifest = train_words(["привет мир и лес"] * 5, max_merges=20)
        vocab = OFFSET + 256 + len(manifest["merges"])
        arch = {"lab": True, "loops": 2, "experts": 2, "memory": 64}
        model = make_model(torch, vocab_size=vocab, width=64, heads=4, layers=2, context=64, arch=arch)
        for p in model.parameters():
            p.data.normal_(0, 0.05)
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "a.pt"
            torch.save({"schema": "yorika-language-longrun-v1", "weights": model.state_dict(), "tokenizer": manifest,
                        "vocab_size": vocab, "config": [64, 4, 2, 64, 20, 1], "arch": arch, "objective": "dialogue"}, src)
            info = growth.grow(src, Path(d) / "b.pt", 2)
            self.assertEqual(info["layers"], 4)
            grown = make_model(torch, vocab_size=vocab, width=64, heads=4, layers=4, context=64, arch=arch)
            grown.load_state_dict(torch.load(Path(d) / "b.pt", weights_only=True)["weights"])
            model.eval(), grown.eval()
            x = torch.randint(0, vocab, (1, 12))
            self.assertTrue(torch.allclose(model(x), grown(x), atol=1e-5))
            sizes = quantize.quantize(src, Path(d) / "a.q4.pt")
            self.assertLess(sizes["bytes"], sizes["original_bytes"] / 3)
            small, _ = quantize.load_quantized(Path(d) / "a.q4.pt")
            self.assertLess(float((small(x) - model(x)).abs().max()), 0.1)
            torch.save({"schema": "yorika-language-longrun-v1", "weights": {}, "config": [64, 4, 2, 64, 20, 1]}, src)
            with self.assertRaisesRegex(ValueError, "нового устройства"):
                growth.grow(src, Path(d) / "c.pt")


class LogicTests(unittest.TestCase):
    def test_tasks_are_verified_and_exam_never_leaks(self):
        rng = random.Random(3)
        for level in logic.LEVELS:
            for _ in range(20):
                t = logic.task(rng, level)
                self.assertTrue(logic.correct(t["solution"], t["answer"]), t)
                self.assertEqual(t["solution"].count("Шаг"), len(t["solution"].split("Шаг")) - 1)
        exam = {t["q"] for level in logic.LEVELS for t in logic.exam_tasks(level)}
        self.assertEqual(len(exam), len(logic.LEVELS) * logic.EXAM_PER_LEVEL)
        self.assertFalse(exam & {q for q, _ in logic.lessons(5, per_level=80)})
        self.assertFalse(logic.correct("Ответ: 6.", "7"))
        self.assertTrue(logic.correct("Шаг 1: [[calc:3+4]]. Ответ: [[calc:3+4]].", "7"))
        self.assertEqual(logic.frontier({"1": 0.9, "2": 0.5}), 2)
        self.assertEqual(logic.frontier(None), 1)

    def test_wrong_claims_are_found(self):
        self.assertEqual(brain.wrong_claims("Шаг 1: 7 + 5 = 12. Шаг 2: 12 * 2 = 25."), 1)
        self.assertEqual(brain.wrong_claims("Без чисел"), 0)


class ForgettingTests(LabBase):
    def test_strength_grows_with_repetition_and_fades_with_time(self):
        now = time.time()
        items = [{"id": "a", "prompt": "Как дела?", "ts": now, "rating": "up"},
                 {"id": "b", "prompt": "как дела?", "ts": now, "rating": "up"},
                 {"id": "c", "prompt": "Редкое", "ts": now - 300 * 86400, "rating": "up"}]
        power = continual.strengths(items, now)
        self.assertGreater(power["a"], 1.5)
        self.assertLess(power["c"], continual.FADED)

    def test_settings_and_curiosity_without_models(self):
        with self.assertRaises(ValueError):
            continual.set_settings(True, min_new=1)
        self.assertTrue(continual.set_settings(True, auto_activate=False, min_new=10)["enabled"])
        self.assertIsNone(continual.maybe_start(launch=False))  # no active version yet
        self.assertIn("обучите", curiosity.wishes()[0]["what"])
        self.assertIn("добавлено", curiosity.night_step())
        self.assertTrue(all(i["rating"] == "up" and i["verified"] for i in sl._load()["items"]))
        self.assertGreater(sl.pack_preview("logic")["count"], 0)

    def test_chat_engine_needs_an_active_version(self):
        self.assertEqual(brain.engine()["engine"], "cloud")
        self.assertFalse(brain.own_engine_selected())
        with self.assertRaisesRegex(ValueError, "активной"):
            brain.set_engine("own")

    def test_evolution_queues_mutants_of_the_parent(self):
        name = dataset()
        plan = tc.start_evolution(name, 4, device="cpu", total_steps=100, hours_each=0.1, launch=False, seed=2)
        self.assertEqual(len(plan["queue"]), 3)
        self.assertTrue(all(isinstance(q, str) for q in tc.series()["queue"]))
        rng = random.Random(1)
        from backend.neural_language_bpe_v2 import check_arch
        for _ in range(30):
            child = tc.mutate(tc.config_for("s"), rng)
            self.assertEqual(check_arch(child["arch"]), child["arch"])
            self.assertEqual(child["width"] % child["heads"], 0)


@unittest.skipUnless(HAS_TORCH, "PyTorch optional")
class LivingTrainingTests(LabBase):
    def train(self, name, config=LAB, **kw):
        run = tc.start("long", dataset=name, device="cpu", total_steps=100, hours=0.1, config=config, launch=False, **kw)["id"]
        tc.worker(run)
        time.sleep(1.1)  # run ids are per second
        return tc._summary(tc._run_dir(run))

    def test_lab_brain_trains_grows_merges_compresses_and_chats(self):
        name = dataset()
        first = self.train(name)
        self.assertEqual(first["state"], "finished", first.get("error"))
        self.assertEqual(first["arch"]["loops"], 2)
        self.assertIn("levels", first["logic"])
        second = self.train(name)
        merged = tc.merge(first["id"], second["id"], launch=False)
        self.assertEqual(merged["kind"], "merge")
        tc.exam_worker(merged["id"])
        self.assertIsNotNone(tc._summary(tc._run_dir(merged["id"]))["exam_per_char"])
        time.sleep(1.1)
        grown = tc.start("long", dataset=name, device="cpu", total_steps=100, hours=0.1, launch=False,
                         grow={"from": first["id"], "layers": 1})["id"]
        tc.worker(grown)
        item = tc._summary(tc._run_dir(grown))
        self.assertEqual((item["state"], item["layers"], item["kind"]), ("finished", 2, "grow"))
        packed = tc.compress(first["id"])
        self.assertLess(packed["bytes"], packed["original_bytes"])
        loaded = brain.load(tc._run_dir(first["id"]) / "language-longrun.pt.best.q4.pt")
        thought = brain.think(*loaded, "Сколько будет 2 плюс 2?", drafts=3)
        self.assertEqual(thought["drafts"], 3)
        tc.activate(first["id"])
        brain.set_engine("own", 1)
        self.assertTrue(brain.own_engine_selected())
        try:
            self.assertIn("answer", brain.chat("Привет!"))
        except RuntimeError as error:
            self.assertIn("Своя модель", str(error))  # a tiny model may say nothing; it never falls back

    def test_quick_lesson_sleep_and_rollback(self):
        name = dataset()
        first = self.train(name)
        tc.activate(first["id"])
        continual.set_settings(True, auto_activate=True, min_new=10, minutes=1)
        store = sl._load()
        for i in range(15):
            store["items"].append({"id": "q%d" % i, "prompt": "Новый вопрос %d?" % i, "answer": "Новый ответ %d." % i,
                                   "ts": time.time(), "rating": "up", "correction": None, "source": "yorika-chat"})
        sl._save(store)
        records, mix = continual.build_set(sl._load()["items"][-15:], 0.5, seed=1)
        banned = tc.protected_prompts()
        self.assertTrue(banned)
        self.assertFalse({r["prompt"].casefold() for r in records} & banned)
        run = continual.maybe_start(launch=False)
        self.assertIsNotNone(run)
        info = tc._read(tc._run_dir(run) / "run.json")
        info["time_limit"] = 4  # a short lesson is minutes long; the test needs seconds
        tc._write(tc._run_dir(run) / "run.json", info)
        tc.worker(run)
        item = tc._summary(tc._run_dir(run))
        self.assertEqual(item["kind"], "quick")
        self.assertIn(item["verdict"]["result"], ("activated", "rolled_back"))
        events = [e["event"] for e in continual.log()]
        self.assertEqual(events[0], "start")
        if item["verdict"]["result"] == "activated":
            self.assertEqual(tc.active()["run"], run)
        else:
            self.assertIn(run, sl._settings()["dismissed"])
        self.assertIsNone(continual.maybe_start(launch=False))  # nothing new since
        # Night: sleep continues the active version on today's experience plus replay.
        time.sleep(1.1)
        night.set_settings(True, "02:00", hours=1, apply=False, curiosity=True)
        exported = sl.export()
        self.assertTrue(exported["name"].startswith("опыт-"))
        entry = night.run(launch=False)
        steps = {s["step"]: s["result"] for s in entry["steps"]}
        self.assertIn("сон", steps["train"])
        self.assertIn("уровень", steps["curiosity"])


class ChatRouteTests(LabBase):
    def test_stream_answers_with_own_model_when_chosen(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("stream_under_test", Path(__file__).resolve().parents[1] / "scripts" / "cloud-ru-stream.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertFalse(module.own_model("Привет", None))
        tc._write(tc.folder() / "chat-engine.json", {"engine": "own", "drafts": 3})
        saved = brain.chat
        brain.chat = lambda q, c=None: {"answer": "Я тут!", "run": "r"}
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertTrue(module.own_model("Привет", None))
        finally:
            brain.chat = saved
        lines = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual(lines[-1], {"type": "done", "answer": "Я тут!"})


if __name__ == "__main__":
    unittest.main()
