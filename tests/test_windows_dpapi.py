"""Cloud.ru real DPAPI smoke checks (Windows only, never uses a real key)."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from backend.cloud_ru_vault import (credential_path, delete_credentials,
                                    public_status, read_credentials, save_credentials)


@unittest.skipUnless(sys.platform == "win32", "Windows CurrentUser DPAPI test")
class WindowsDPAPITests(unittest.TestCase):
    def test_encrypt_rotate_reload_delete_across_processes(self):
        with tempfile.TemporaryDirectory() as folder:
            env = dict(os.environ, LOCALAPPDATA=folder)
            previous = os.environ.get("LOCALAPPDATA")
            os.environ["LOCALAPPDATA"] = folder
            try:
                save_credentials("fake-test-secret-123", "ai-sage/test")
                path = credential_path()
                self.assertTrue(path.exists())
                self.assertNotIn(b"fake-test-secret-123", path.read_bytes())
                self.assertEqual(read_credentials()["key"], "fake-test-secret-123")
                save_credentials("fake-rotated-secret-456", "ai-sage/test-v2")
                self.assertEqual(read_credentials()["key"], "fake-rotated-secret-456")
                code = ("import json; from backend.cloud_ru_vault import public_status; "
                        "print(json.dumps(public_status()))")
                result = subprocess.run([sys.executable, "-c", code],
                                        cwd=str(Path(__file__).resolve().parents[1]),
                                        env=env, capture_output=True, text=True, check=True)
                self.assertIn("ai-sage/test-v2", result.stdout)
                self.assertNotIn("fake-rotated-secret-456", result.stdout)
                self.assertNotIn("fake-rotated-secret-456", result.stderr)
                delete_credentials()
                self.assertFalse(public_status()["configured"])
                self.assertFalse(path.exists())
            finally:
                if previous is None:
                    os.environ.pop("LOCALAPPDATA", None)
                else:
                    os.environ["LOCALAPPDATA"] = previous
