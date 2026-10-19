import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import continual_learning as cl
from backend import self_learning as sl
from backend import training_center as tc


class ContinualTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"YORIKA_HOME": self.temp.name})
        self.env.start()
        sl.set_collect(True)

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_gate_rejects_any_regression_nan_infinity_and_ties(self):
        base = {"validation": 2., "retention": 3.}
        self.assertTrue(cl.gate(base, {"validation": 1., "retention": 3.}))
        for candidate in (base, {"validation": 1., "retention": 3.01},
                          {"validation": float("nan"), "retention": 1.},
                          {"validation": 1., "retention": float("inf")}):
            self.assertFalse(cl.gate(base, candidate))

    def rows(self):
        items = [{"id": str(i), "prompt": "Question %d" % i, "answer": "Yes",
                  "rating": "up", "source": "yorika-chat"} for i in range(80)]
        sl._save({"items": items, "removed": []})
        return items

    def test_review_and_consent_and_secret_filter(self):
        items = self.rows()
        items += [dict(items[0], id="latest", rating="down", correction="Corrected"),
                  dict(items[1], id="secret", answer="password=secret", prompt="Private"),
                  dict(items[2], id="unrated", rating=None, prompt="Unrated")]
        sl._save({"items": items, "removed": []})
        rows = cl.reviewed()
        self.assertEqual(rows[0]["pair"], ("Question 0", "Corrected"))
        self.assertFalse(any(r["pair"][0] in ("Private", "Unrated") for r in rows))
        sl.set_collect(False)
        with self.assertRaises(ValueError):
            cl.reviewed()

    def test_stable_disjoint_buckets_and_interleaved_replay(self):
        self.rows()
        groups = cl.partition(cl.reviewed())
        keys = [{cl._key(r["pair"][0]) for r in rows} for rows in groups.values()]
        self.assertFalse(keys[0] & keys[1] or keys[1] & keys[2] or keys[0] & keys[2])
        old = groups["train"][-1]
        batch, new = cl.make_batch(groups, [old["id"]], new_limit=2)
        self.assertEqual(batch[1], old["pair"])
        self.assertEqual(len(new), 2)
        consumed = [row["id"] for row in groups["train"]]
        self.assertEqual(cl.make_batch(groups, consumed), ([], []))
        batch, new = cl.make_batch(groups, consumed, rehearsal=True)
        self.assertTrue(batch)
        self.assertEqual(new, [])

    def test_lock_and_defaults_and_limits(self):
        self.assertFalse(cl.settings()["enabled"])
        with cl.lock():
            with self.assertRaises(ValueError):
                with cl.lock():
                    pass
        self.assertFalse(cl.busy())
        for step in (True, 0, 65):
            with self.assertRaises(ValueError):
                cl.configure(True, steps=step)

    def test_rejection_and_exception_leave_active_and_head_unchanged(self):
        self.rows()
        cl.configure(True, device="cpu")
        active = tc.folder() / "active.pt"
        active.parent.mkdir(parents=True, exist_ok=True)
        active.write_bytes(b"original")
        groups = cl.partition(cl.reviewed())

        def fake_train(train, validation, output, **kwargs):
            Path(output).write_bytes(b"candidate")
            return {"steps": 8}

        for scores in (({"validation": 2., "retention": 2.}, {"validation": 1., "retention": 3.}),
                       RuntimeError("fixture failure")):
            with patch.object(cl, "_source", return_value=active), \
                 patch.object(cl, "with_original_skills", return_value=(groups, [], "origin")), \
                 patch.object(cl, "_scores", side_effect=scores), \
                 patch("backend.neural_language_benchmark.load_candidate", return_value=(None, {"config": [32, 2, 1, 64, 0, 1]})), \
                 patch("backend.neural_language_longrun.run", side_effect=fake_train):
                report = cl.run()
            self.assertIn(report["state"], ("rejected", "failed"))
            self.assertEqual(active.read_bytes(), b"original")
            self.assertFalse((cl.root() / "head.json").exists())
            self.assertFalse(cl.busy())

    def test_real_weight_continuation_preserves_tokenizer_and_source(self):
        try:
            import torch
        except ImportError:
            self.skipTest("Optional PyTorch required")
        from backend.neural_language_longrun import run
        from backend.neural_language_benchmark import load_candidate
        torch.set_num_threads(1)
        base, candidate = Path(self.temp.name) / "base.pt", Path(self.temp.name) / "next.pt"
        run([("a", "b")], [("c", "d")], base, total_steps=1, checkpoint_every=1,
            width=16, heads=2, layers=1, context=32, max_merges=0)
        before = base.read_bytes()
        _, initial = load_candidate(base)
        run([("e", "f")], [("g", "h")], candidate, total_steps=1, checkpoint_every=1,
            width=16, heads=2, layers=1, context=32, max_merges=0,
            init_from=base, continue_dialogue=True)
        _, updated = load_candidate(candidate)
        self.assertEqual(base.read_bytes(), before)
        self.assertEqual(initial["tokenizer"], updated["tokenizer"])
        self.assertTrue(any(not torch.equal(v, updated["weights"][k]) for k, v in initial["weights"].items()))
        self.assertEqual(updated["init_sha256"], tc._sha256(base))

    def test_real_cycle_and_manual_activation_with_rollback(self):
        try:
            import torch
        except ImportError:
            self.skipTest("Optional PyTorch required")
        from backend.neural_language_longrun import run
        torch.set_num_threads(1)
        self.rows()
        groups = cl.partition(cl.reviewed())
        source = tc.folder() / "source.pt"
        run([("base", "yes")], [("heldout", "no")], source, total_steps=1,
            checkpoint_every=1, width=16, heads=2, layers=1, context=64, max_merges=0)
        tc._point_to("source.pt", {"run": None})
        cl.configure(True, device="cpu", steps=4)
        with patch.object(cl, "with_original_skills", return_value=(groups, [], "origin")), \
             patch.object(cl, "_scores", side_effect=[{"validation": 2., "retention": 2.},
                                                      {"validation": 1., "retention": 2.}]):
            report = cl.run()
        self.assertEqual(report["state"], "proposed")
        self.assertEqual(tc.active()["checkpoint"], "source.pt")
        head = tc._read(cl.root() / "head.json")
        self.assertEqual(len(head["consumed"]), 4)
        with self.assertRaises(ValueError):
            cl.activate("stale")
        cl.activate(report["id"])
        self.assertNotEqual(tc.active()["checkpoint"], "source.pt")
        tc.rollback()
        self.assertEqual(tc.active()["checkpoint"], "source.pt")

    def test_original_skills_replay_is_disjoint_and_requires_unchanged_manifest(self):
        records = [{"prompt": "Original %d" % i, "answer": "ok", "source": "fixture",
                    "license": "synthetic", "consent": True} for i in range(20)]
        name, run_id = "original.json", "20261019-010101-long"
        tc._write(tc.folder() / "data" / name, records)
        original = tc._prepare(records)
        tc._write(tc.folder() / "runs" / run_id / "run.json",
                  {"dataset": name, "manifest": original["manifest"]})
        tc._write(tc.folder() / "active-meta.json", {"run": run_id})
        self.rows()
        groups, replay_ids, origin = cl.with_original_skills(cl.partition(cl.reviewed()))
        self.assertEqual(origin, run_id)
        self.assertEqual(len(replay_ids), len(original["train"]))
        train_keys = {cl._key(r["pair"][0]) for r in groups["train"]}
        exam_keys = {cl._key(r["pair"][0]) for k in ("validation", "retention") for r in groups[k]}
        self.assertFalse(train_keys & exam_keys)
        records[0]["answer"] = "changed"
        tc._write(tc.folder() / "data" / name, records)
        with self.assertRaises(ValueError):
            cl.with_original_skills(cl.partition(cl.reviewed()))

    def test_start_and_activation_cannot_race_consolidation(self):
        with cl.lock():
            with self.assertRaises(ValueError):
                tc.start("pilot", device="cpu", launch=False)
            with self.assertRaises(ValueError):
                tc.rollback()

    def test_stop_disables_new_work_and_enable_clears_stop(self):
        cl.configure(True)
        cl.stop()
        self.assertFalse(cl.settings()["enabled"])
        self.assertTrue((cl.root() / "stop").exists())
        cl.configure(True)
        self.assertFalse((cl.root() / "stop").exists())


if __name__ == "__main__":
    unittest.main()
