import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "scripts" / "yorika-tray.ps1"
SCRIPT = ROOT / "scripts" / "cloud-ru-settings.py"
spec = importlib.util.spec_from_file_location("yorika_cloud_settings", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CloudSettingsRegression(unittest.TestCase):
    def test_server_routes_and_guardrails_are_not_corrupted(self):
        content = SERVER.read_text(encoding="utf-8-sig")
        self.assertIn(
            "^/api/cloud-ru/(status|save|check|delete|diagnostics)\\z", content
        )
        self.assertIn("}elseif($path -eq '/api/chat/respond'){", content)
        self.assertIn("$action=$Matches[1]", content)
        self.assertIn("scripts\\cloud-ru-settings.py", content)
        self.assertIn("scripts\\cloud-ru-model.py", content)
        self.assertIn("$origin -ne", content)

    def test_cloud_subprocess_timeout_precedes_blocking_stdout_read(self):
        content = SERVER.read_text(encoding="utf-8-sig")
        settings = content.split("}elseif($path -match '^/api/cloud-ru/", 1)[1].split(
            "}elseif($path -eq '/api/chat/respond')", 1
        )[0]
        chat = content.split("}elseif($path -eq '/api/chat/respond')", 1)[1].split(
            "}elseif($path -eq '/api/memory/recall')", 1
        )[0]
        for block, timeout in ((settings, "28000"), (chat, "25000")):
            with self.subTest(timeout=timeout):
                self.assertLess(
                    block.index("WaitForExit(" + timeout + ")"),
                    block.index("StandardOutput.ReadToEnd()"),
                )
                self.assertLess(
                    block.index("WaitForExit(" + timeout + ")"),
                    block.index("StandardError.ReadToEnd()"),
                )

    def test_status_diagnostics_and_model_rotation_do_not_return_key(self):
        from backend import cloud_ru_vault as vault
        state = {"key": "test-key", "model": "ai-sage/old"}
        def read():
            return dict(state)
        def save(key, model):
            state.update(key=key, model=model)
        def status():
            return {"configured": True, "model": state["model"],
                    "storage": "windows-dpapi-current-user"}
        with patch.object(module, "read_credentials", side_effect=read), \
             patch.object(module, "save_credentials", side_effect=save), \
             patch.object(module, "public_status", side_effect=status):
            rotated = module.run("save", {"key": None, "model": "ai-sage/new"})
            self.assertEqual(rotated["model"], "ai-sage/new")
            self.assertEqual(state["key"], "test-key")
            self.assertNotIn("key", rotated)
            info = module.run("diagnostics")
            self.assertTrue(info["key_accessible"])
            self.assertTrue(info["live_check_required"])
            self.assertNotIn("key", info)

    def test_connection_probe_explicit_and_source_stays_masked(self):
        secret = {"key": "test-key", "model": "ai-sage/test"}
        calls = []
        def fake(question, **kwargs):
            calls.append(kwargs)
            return {"answer": "готово"}
        with patch.object(module, "read_credentials", return_value=secret):
            result = module.run("check", test_call=fake)
        self.assertTrue(result["connected"])
        self.assertEqual(calls[0]["api_key"], "test-key")
        self.assertIs(calls[0]["include_memory"], False)
        self.assertNotIn("key", result)


if __name__ == "__main__":
    unittest.main()
