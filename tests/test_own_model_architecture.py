"""Reject accidental reintroduction of third-party local model servers."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class OwnModelArchitectureTests(unittest.TestCase):
    def test_responder_never_calls_third_party_local_model_api(self):
        source = (ROOT / "scripts" / "local-model.py").read_text(encoding="utf-8").casefold()
        self.assertNotIn("ollama", source)
        self.assertNotIn("11434", source)
        self.assertNotIn("urllib.request", source)
        self.assertIn("experimental_answer", source)
        self.assertIn("yorika_neural_checkpoint", source)

    def test_project_instructions_exclude_external_local_model_server(self):
        instructions = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("does **not** use Ollama", instructions)


if __name__ == "__main__":
    unittest.main()
