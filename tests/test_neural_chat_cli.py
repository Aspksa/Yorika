"""Yorika CLI uses only an explicitly configured own checkpoint."""
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
    def test_requires_checkpoint_without_network_fallback(self):
        with patch.object(MODULE.sys, "stdin", io.StringIO("Привет")), patch.dict(
            os.environ, {"YORIKA_NEURAL_CHECKPOINT": ""}
        ):
            with self.assertRaises(RuntimeError):
                MODULE.main()

    def test_routes_only_to_own_checkpoint(self):
        expected = {"answer": "проба", "provider": "experimental-local-transformer"}
        with patch.object(MODULE.sys, "stdin", io.StringIO("Привет")), patch.dict(
            os.environ, {"YORIKA_NEURAL_CHECKPOINT": "own-model.pt"}
        ), patch.object(MODULE, "answer", return_value=expected) as responder, patch(
            "sys.stdout", new_callable=io.StringIO
        ) as output:
            MODULE.main()
        self.assertEqual(json.loads(output.getvalue()), expected)
        responder.assert_called_once_with("Привет")


if __name__ == "__main__":
    import unittest
    unittest.main()
