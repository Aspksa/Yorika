"""Cloud.ru UI and stream errors must remain actionable and secret-safe."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CloudStreamUiTests(unittest.TestCase):
    def test_picker_preserves_custom_model_ids(self):
        html = (ROOT / "www/settings.html").read_text(encoding="utf-8")
        self.assertIn('list="cloud-ru-model-suggestions"', html)
        self.assertIn('id="cloud-ru-model-suggestions"', html)
        self.assertIn("введите ID", html)
        js = (ROOT / "www/settings.js").read_text(encoding="utf-8")
        self.assertIn('el("cloud-ru-model").value=result.model', js)

    def test_errors_are_not_hidden_in_chat(self):
        source = (ROOT / "www/avatar.js").read_text(encoding="utf-8")
        self.assertIn("evt.message||'Cloud.ru не завершил поток'", source)
        self.assertIn("Fallback to non-streaming", source)
        process = subprocess.run(["node", "--check", str(ROOT / "www/avatar.js")],
                                 capture_output=True, text=True)
        if process.returncode and "not found" not in process.stderr.lower():
            self.fail(process.stderr)

    def test_error_classifier_never_echoes_arbitrary_exception(self):
        source = (ROOT / "scripts/cloud-ru-stream.py").read_text(encoding="utf-8")
        self.assertIn('if "HTTP 401" in detail:', source)
        self.assertIn('elif "HTTP 404" in detail:', source)
        self.assertNotIn('{"type": "error", "message": detail}', source)


if __name__ == "__main__":
    unittest.main()
