import tempfile
import unittest
from pathlib import Path

from backend.storage import Store
from scripts.sqlite_backup import create_verified_backup
from scripts.sqlite_recovery_drill import recovery_drill


class RecoveryDrillTests(unittest.TestCase):
    def test_unicode_data_backup_restores_and_keeps_live_database(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with Store(root / "live") as store:
                store.put("memory", "greeting", {"text": "Ёрика помнит"})
                store.append_event("saved", {"text": "Привет"})
                report = create_verified_backup(store.path, root / "backup.sqlite3")
            data_before = (root / "backup.sqlite3").read_bytes()
            result = recovery_drill(root / "backup.sqlite3", report["sha256"])
            self.assertTrue(result["passed"])
            self.assertEqual(result["counts"], {"events": 1, "records": 1})
            self.assertEqual((root / "backup.sqlite3").read_bytes(), data_before)
            with Store(root / "live") as store:
                self.assertEqual(store.get("memory", "greeting")["text"], "Ёрика помнит")

    def test_wrong_digest_aborts_drill(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with Store(root / "live") as store:
                report = create_verified_backup(store.path, root / "backup.sqlite3")
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                recovery_drill(root / "backup.sqlite3", "0" * 64)


if __name__ == "__main__":
    unittest.main()
