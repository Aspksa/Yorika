import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import cloud_ru_vault as vault


class CloudRuVaultTests(unittest.TestCase):
    def test_save_rotate_delete_and_never_expose_key_in_status(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "cloud.dpapi"
            def mock_crypt(data, *, decrypt):
                return data[::-1]
            with patch.object(vault, "credential_path", return_value=path), \
                 patch.object(vault, "_crypt", side_effect=mock_crypt):
                vault.save_credentials("secret-one", "ai-sage/test")
                self.assertNotIn(b"secret-one", path.read_bytes())
                self.assertEqual(vault.read_credentials()["key"], "secret-one")
                self.assertEqual(vault.public_status()["model"], "ai-sage/test")
                self.assertNotIn("key", vault.public_status())
                vault.save_credentials("secret-two", "ai-sage/other")
                self.assertEqual(vault.read_credentials()["key"], "secret-two")
                vault.delete_credentials()
                self.assertFalse(path.exists())
                self.assertFalse(vault.public_status()["configured"])

    def test_invalid_input_rejected_without_file(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "cloud.dpapi"
            with patch.object(vault, "credential_path", return_value=path), \
                 patch.object(vault, "_crypt", return_value=b"ignored"):
                for key, model in [("", "a"), ("bad\nkey", "a"), ("test", "bad model")]:
                    with self.assertRaises(ValueError):
                        vault.save_credentials(key, model)
                self.assertFalse(path.exists())

    def test_non_windows_refuses_unprotected_vault(self):
        with patch.object(vault.sys, "platform", "linux"):
            with self.assertRaises(RuntimeError):
                vault.credential_path()


if __name__ == "__main__":
    unittest.main()
