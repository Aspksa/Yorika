"""The CLI preserves its production default and has explicit experimental opt-in."""
import importlib.util
import io
import json
import os
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("yorika_local_model_cli", ROOT / "scripts" / "local-model.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class NeuralChatCliTests(TestCase):
    def test_default_stays_on_existing_provider(self):
        with patch.object(MODULE.sys, "stdin", io.StringIO("Привет")), patch.object(
            MODULE, "answer", return_value={"answer": "основной", "provider": "local-ollama"}
        ) as original, patch.dict(os.environ, {"YORIKA_EXPERIMENTAL_NEURAL": "0"}, clear=False), patch(
            "sys.stdout", new_callable=io.StringIO
        ) as output:
            MODULE.main()
        self.assertEqual(json.loads(output.getvalue())["provider"], "local-ollama")
        original.assert_called_once_with("Привет")

    def test_experimental_mode_requires_checkpoint(self):
        with patch.object(MODULE.sys, "stdin", io.StringIO("Привет")), patch.dict(
            os.environ, {"YORIKA_EXPERIMENTAL_NEURAL": "1", "YORIKA_EXPERIMENTAL_CHECKPOINT": ""}
        ):
            with self.assertRaises(RuntimeError):
                MODULE.main()

    def test_experimental_mode_routes_explicitly(self):
        expected = {"answer": "проба", "provider": "experimental-local-transformer"}
        with patch.object(MODULE.sys, "stdin", io.StringIO("Привет")), patch.dict(
            os.environ, {"YORIKA_EXPERIMENTAL_NEURAL": "1", "YORIKA_EXPERIMENTAL_CHECKPOINT": "model.pt"}
        ), patch.object(MODULE, "route_answer", return_value=expected) as route, patch(
            "sys.stdout", new_callable=io.StringIO
        ) as output:
            MODULE.main()
        self.assertEqual(json.loads(output.getvalue()), expected)
        self.assertTrue(route.call_args.kwargs["experimental"])
        self.assertEqual(route.call_args.kwargs["checkpoint"], "model.pt")


if __name__ == "__main__":
    import unittest
    unittest.main()
