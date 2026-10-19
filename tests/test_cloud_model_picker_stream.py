"""Cloud.ru UI and stream errors must remain actionable and secret-safe."""
import subprocess
import shutil
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
        self.assertIn('id="cloud-ru-models-refresh"', html)
        self.assertIn('id="cloud-ru-model-select"', html)
        js = (ROOT / "www/settings.js").read_text(encoding="utf-8")
        self.assertIn('el("cloud-ru-model").value=result.model', js)
        self.assertIn('api("/api/cloud-ru/models")', js)
        self.assertIn('el("cloud-ru-model-select").onchange', js)
        self.assertIn('picker.disabled=result.models.length===0', js)
        gateway = (ROOT / "scripts/yorika-tray.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("(status|models|save|check|delete|diagnostics", gateway)
        server = (ROOT / "scripts/cloud-ru-settings.py").read_text(encoding="utf-8")
        self.assertIn("if action == \"models\"", server)
        self.assertIn("foundation-models.api.cloud.ru/v1/models", server)

    def test_errors_are_not_hidden_in_chat(self):
        source = (ROOT / "www/avatar.js").read_text(encoding="utf-8")
        self.assertIn("evt.message||'Cloud.ru не завершил поток'", source)
        self.assertIn("Fallback to non-streaming", source)
        if shutil.which("node"):
            process = subprocess.run(["node", "--check", str(ROOT / "www/avatar.js")],
                                     capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)

    def test_error_classifier_never_echoes_arbitrary_exception(self):
        source = (ROOT / "scripts/cloud-ru-stream.py").read_text(encoding="utf-8")
        self.assertIn('if "HTTP 401" in detail:', source)
        self.assertIn('elif "HTTP 404" in detail:', source)
        self.assertIn('"Invalid Cloud.ru stream event" in detail', source)
        self.assertNotIn('{"type": "error", "message": detail}', source)


if __name__ == "__main__":
    unittest.main()
