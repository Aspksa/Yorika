"""Neural experimental routing cannot silently replace the production provider."""
import unittest
from backend.neural_router import experimental_answer, route_answer


class NeuralRoutingTests(unittest.TestCase):
    def test_default_is_production(self):
        calls = []
        def fallback(query):
            calls.append(query)
            return {"answer": "стабильный", "provider": "existing"}
        self.assertEqual(route_answer("Привет", fallback=fallback),
                         {"answer": "стабильный", "provider": "existing"})
        self.assertEqual(calls, ["Привет"])

    def test_explicit_experiment_is_labeled(self):
        output = route_answer("Привет", experimental=True, checkpoint="trained.pt",
                              fallback=lambda q: {"answer": "fallback"},
                              generator=lambda path, prompt, **kw: {"answer": "тест"})
        self.assertEqual(output["provider"], "experimental-local-transformer")
        self.assertFalse(output["quality_verified"])
        self.assertEqual(output["checkpoint"], "trained.pt")

    def test_bad_checkpoint_falls_back(self):
        fallback = lambda q: {"answer": "исходный движок"}
        result = route_answer("Привет", experimental=True, checkpoint="missing.pt",
                              fallback=fallback,
                              generator=lambda *a, **k: (_ for _ in ()).throw(ValueError("invalid checkpoint")))
        self.assertEqual(result["answer"], "исходный движок")

    def test_no_implicit_opt_in(self):
        with self.assertRaises(PermissionError):
            experimental_answer("Привет", checkpoint="model.pt")
        with self.assertRaises(ValueError):
            route_answer("Привет", fallback=None)


if __name__ == "__main__":
    unittest.main()
