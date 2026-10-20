"""Newer brain parts: Mamba-style scan, liquid time constants, active dendrites, Hopfield memory,
fast weights and the Forward-Forward warm-up. Each one is causal, starts as an exact identity,
trains, and is a gene that evolution can switch."""
import random
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import archive
from backend import schedule
from backend import training_center as tc
from backend.neural_language_bpe_v2 import check_arch
from backend.neural_language_longrun import check_rule
from tests.test_learning_lab import LabBase, dataset
from tests.test_living_brain import LAB

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

NEW = [{"mixer": "ssm"}, {"mixer": "liquid"}, {"mixer": "hybrid"}, {"dendrites": 4}, {"hopfield": 64}, {"fast": True}]


class GeneTests(unittest.TestCase):
    def test_options_are_checked_and_defaults_dropped(self):
        self.assertEqual(check_arch({}), {})
        self.assertEqual(check_arch({"lab": True, "loops": 2, "experts": 2, "memory": 64}),
                         {"lab": True, "loops": 2, "experts": 2, "memory": 64})  # older versions read the same
        self.assertEqual(check_arch({"mixer": "attn", "fast": False, "hopfield": 0}), {})
        self.assertEqual(check_arch({"mixer": "liquid", "fast": True}), {"lab": True, "mixer": "liquid", "fast": True})
        for bad in ({"mixer": "rnn"}, {"dendrites": 3}, {"hopfield": 100}, {"fast": 1}, {"experts": 4, "dendrites": 4},
                    {"mixer": "ssm", "lab": False}, {"glia": True}):
            with self.assertRaises(ValueError, msg=bad):
                check_arch(bad)
        self.assertEqual(check_rule({"ff": 200}), {"ff": 200})
        with self.assertRaises(ValueError):
            check_rule({"ff": 2.5})
        self.assertEqual(tc.config_for("s", ff=True)["rule"], {"ff": tc.FF_STEPS})
        self.assertNotIn("rule", tc.config_for("s"))

    def test_evolution_switches_every_new_part(self):
        rng, seen = random.Random(3), set()
        config = tc.config_for("s")
        for _ in range(400):
            config = tc.mutate(config, rng)
            arch = check_arch(config["arch"])
            self.assertEqual(arch, config["arch"])
            self.assertFalse(arch.get("experts") and arch.get("dendrites"))
            check_rule(config.get("rule"))
            seen |= {k for k in arch if k != "lab"} | ({"ff"} if (config.get("rule") or {}).get("ff") else set())
            seen.add(arch.get("mixer", "attn"))
        self.assertTrue({"mixer", "dendrites", "hopfield", "fast", "ff", "ssm", "liquid", "hybrid"} <= seen, seen)
        label = tc._describe(dict(config_for_label(), rule={"ff": 200}))
        self.assertIn("жидкие нейроны", label)
        self.assertIn("Forward-Forward", label)
        self.assertEqual(archive.family_of({"lab": True, "mixer": "liquid"}), "без внимания")
        self.assertEqual(archive.family_of({"lab": True, "hopfield": 64, "dendrites": 4}), "всё сразу")


def config_for_label():
    return tc.config_for("s", {"mixer": "liquid", "hopfield": 128})


@unittest.skipUnless(HAS_TORCH, "PyTorch optional")
class PartsTests(unittest.TestCase):
    def model(self, arch, layers=2):
        from backend.neural_language_bpe_v2 import make_model
        torch.manual_seed(0)
        return make_model(torch, vocab_size=300, width=32, heads=4, context=64, layers=layers, arch=arch)

    def test_every_part_is_causal_learns_and_grows_as_identity(self):
        for arch in NEW:
            m = self.model(arch).eval()
            ids = torch.randint(0, 300, (2, 40))
            later = ids.clone()
            later[:, 30:] = torch.randint(0, 300, (2, 10))
            # A token never sees the future.
            self.assertTrue(torch.allclose(m(ids)[:, :30], m(later)[:, :30], atol=1e-5), arch)
            m.train()
            m(ids).sum().backward()
            self.assertFalse([n for n, p in m.named_parameters() if p.grad is None], arch)
            # Growing deeper with the same parts changes nothing until training.
            small, big = self.model(arch, 2).eval(), self.model(arch, 4).eval()
            weights = big.state_dict()
            weights.update(small.state_dict())
            big.load_state_dict(weights)
            self.assertTrue(torch.allclose(small(ids), big(ids), atol=1e-5), arch)

    def test_scan_matches_the_step_by_step_recurrence(self):
        from backend import brain_blocks
        decay, inputs = -torch.rand(2, 21, 3), torch.randn(2, 21, 3)
        h, expected = torch.zeros(2, 3), []
        for t in range(21):
            h = torch.exp(decay[:, t]) * h + inputs[:, t]
            expected.append(h)
        self.assertTrue(torch.allclose(brain_blocks.scan(torch, decay, inputs), torch.stack(expected, 1), atol=1e-5))

    def test_forward_forward_trains_each_block_locally(self):
        from backend import forward_forward
        m = self.model({"lab": True}, 2)
        rows = [([1, 3, 10 + i, 4] + [20 + (i + k) % 50 for k in range(8)] + [2], 3) for i in range(30)]
        before = {n: p.detach().clone() for n, p in m.named_parameters()}
        report = forward_forward.warmup(torch, m, rows, torch.device("cpu"), steps=30)
        self.assertEqual(len(report["separation"]), 2)
        self.assertTrue(all(0 <= s <= 1 for s in report["separation"]))
        changed = {n for n, p in m.named_parameters() if not torch.equal(p, before[n])}
        self.assertTrue(any(n.startswith("blocks.1") for n in changed))
        self.assertFalse(any(n.startswith("output") for n in changed))  # the output layer waits for backprop
        with self.assertRaises(ValueError):
            forward_forward.warmup(torch, m, [([1, 3, 4, 5, 2], 3)], torch.device("cpu"), steps=2)


@unittest.skipUnless(HAS_TORCH, "PyTorch optional")
class TrainingWithPartsTests(LabBase):
    def setUp(self):
        super().setUp()
        schedule.set_grid("always")

    def test_a_version_with_new_parts_trains_passes_the_exam_and_is_inspected(self):
        config = dict(LAB, arch={"lab": True, "mixer": "hybrid", "hopfield": 64, "fast": True, "dendrites": 4},
                      layers=2, rule={"ff": 20})
        run = tc.start("long", dataset=dataset(), device="cpu", total_steps=100, hours=0.1, config=config, launch=False)["id"]
        tc.worker(run)
        time.sleep(1.1)
        item = tc._summary(tc._run_dir(run))
        self.assertEqual(item["state"], "finished", item.get("error"))
        self.assertIsNotNone(item["exam_per_char"])
        self.assertEqual(len(item["forward_forward"]["separation"]), 2)
        report = tc._read(tc._run_dir(run) / "progress.json")["introspection"]
        self.assertEqual({p["name"] for p in report["parts"]}, {"hopfield", "fast"})
        best = torch.load(tc._run_dir(run) / "language-longrun.pt.best.pt", map_location="cpu", weights_only=True)
        self.assertEqual(best["ff_report"], item["forward_forward"])


if __name__ == "__main__":
    unittest.main()
