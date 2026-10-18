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

    def test_decrypted_vault_rejects_invalid_model_and_key(self):
        import json
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "cloud.dpapi"
            path.write_bytes(b"encrypted")
            values = [
                {"key": "test", "model": "../bad model"},
                {"key": "test"},
                {"key": "", "model": "ai-sage/valid"},
                {"key": "test", "model": 42},
            ]
            with patch.object(vault, "credential_path", return_value=path):
                for value in values:
                    with self.subTest(value=value), patch.object(
                        vault, "_crypt", return_value=json.dumps(value).encode()
                    ):
                        with self.assertRaisesRegex(RuntimeError, "Corrupt"):
                            vault.read_credentials()

    def test_oversized_ciphertext_rejected_before_decrypt(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "cloud.dpapi"
            path.write_bytes(b"x" * (vault.MAX_CREDENTIAL_FILE_BYTES + 1))
            with patch.object(vault, "credential_path", return_value=path), \
                 patch.object(vault, "_crypt", side_effect=AssertionError("Decryption attempted")):
                with self.assertRaisesRegex(RuntimeError, "too large"):
                    vault.read_credentials()

    def test_linked_secret_folder_blocks_read_and_delete(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "real").mkdir()
            linked = root / "linked"
            try:
                linked.symlink_to(root / "real", target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks unavailable")
            with patch.object(vault, "credential_path", return_value=linked / "cloud.dpapi"):
                with self.assertRaisesRegex(RuntimeError, "linked"):
                    vault.read_credentials()
                with self.assertRaisesRegex(RuntimeError, "linked"):
                    vault.delete_credentials()

    def test_save_rejects_linked_secrets_before_directory_creation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            actual = root / "actual"
            actual.mkdir()
            linked = root / "secrets"
            try:
                linked.symlink_to(actual, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Directory symlinks unavailable")
            path = linked / "cloud.dpapi"
            with patch.object(vault, "credential_path", return_value=path), \
                 patch.object(vault, "_crypt", side_effect=AssertionError("DPAPI called")):
                with self.assertRaisesRegex(RuntimeError, "unsafe"):
                    vault.save_credentials("fake-secret", "ai-sage/test")
            self.assertEqual(list(actual.iterdir()), [])

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
