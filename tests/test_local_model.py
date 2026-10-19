"""The local responder must rely only on Yorika's own checkpoint."""
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "local-model.py"
spec = importlib.util.spec_from_file_location("yorika_local_model", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class LocalModelTests(unittest.TestCase):
    def test_own_checkpoint_only(self):
        calls = []
        def fake(path, query, **kwargs):
            calls.append((path, query, kwargs))
            return {"answer": "Локальный тест", "provider": "experimental-local-transformer"}
        result = module.answer("Привет", checkpoint="trusted.pt", generator=fake)
        self.assertEqual(result["answer"], "Локальный тест")
        self.assertEqual(calls[0][0], "trusted.pt")
        self.assertEqual(result["provider"], "experimental-local-transformer")

    def test_missing_checkpoint_is_explicit_error(self):
        with patch.dict(module.os.environ, {"YORIKA_NEURAL_CHECKPOINT": ""}):
            with self.assertRaises(RuntimeError):
                module.answer("Привет")
        with self.assertRaises(ValueError):
            module.answer("", checkpoint="trusted.pt")

    def test_empty_neural_output_is_not_disguised(self):
        with self.assertRaises(RuntimeError):
            module.answer("Привет", checkpoint="trusted.pt",
                          generator=lambda *a, **kw: {"answer": "  "})


if __name__ == "__main__":
    unittest.main()
