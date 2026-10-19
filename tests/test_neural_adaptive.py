import unittest
try:
    import torch
except ImportError:
    torch = None
from backend.neural_adaptive import make_adaptive, weight_budget


@unittest.skipIf(torch is None, "Optional PyTorch required")
class AdaptiveTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        torch.manual_seed(3)
        self.model = make_adaptive(torch)
        self.ids = torch.tensor([[1, 8, 9, 10]])

    def test_growth_preserves_logits_and_original_parameters(self):
        before, _ = self.model(self.ids, passes=2)
        grown = self.model.grown_copy()
        after, _ = grown(self.ids, passes=2)
        self.assertTrue(torch.equal(before, after))
        self.assertEqual(len(self.model.growth), 0)
        loss = grown(self.ids)[0].square().mean()
        loss.backward()
        self.assertGreater(grown.growth[0].down.weight.grad.abs().sum(), 0)

    def test_shared_parameters_do_not_grow_with_pass_count(self):
        count = sum(p.numel() for p in self.model.parameters())
        one, _ = self.model(self.ids)
        four, _ = self.model(self.ids, passes=4)
        self.assertEqual(count, sum(p.numel() for p in self.model.parameters()))
        self.assertFalse(torch.equal(one, four))
        with self.assertRaises(ValueError):
            self.model(self.ids, passes=9)

    def test_causal_attention_and_differentiable_memory(self):
        changed = self.ids.clone()
        changed[0, -1] = 20
        first, _ = self.model(self.ids, passes=2)
        second, _ = self.model(changed, passes=2)
        torch.testing.assert_close(first[:, :-1], second[:, :-1], atol=1e-6, rtol=1e-6)
        memory = torch.randn(1, 3, 32, requires_grad=True)
        logits, auxiliary = self.model(self.ids, memory=memory)
        (logits.square().mean() + .01 * auxiliary).backward()
        self.assertGreater(memory.grad.abs().sum(), 0)
        self.assertTrue(torch.isfinite(auxiliary))

    def test_exactly_two_experts_receive_each_token(self):
        dispatched = []
        hooks = [expert.register_forward_pre_hook(lambda m, args: dispatched.append(args[0].shape[0]))
                 for expert in self.model.shared.experts]
        self.model(self.ids)
        for hook in hooks:
            hook.remove()
        self.assertEqual(sum(dispatched), 2 * self.ids.numel())

    def test_memory_estimate_does_not_claim_training_fits(self):
        budget = weight_budget(200_000_000)
        self.assertEqual(budget["int4_weight_bytes_lower_bound"], 100_000_000)
        self.assertEqual(budget["fp32_adam_training_bytes_lower_bound"], 3_200_000_000)


if __name__ == "__main__":
    unittest.main()
