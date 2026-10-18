import sqlite3
import tempfile
import unittest
from pathlib import Path
from backend.storage import Store
from scripts.sqlite_backup import create_verified_backup
from scripts.sqlite_restore_copy import restore_copy


class RestoreCopyTests(unittest.TestCase):
    def test_unicode_round_trip_without_touching_live_database(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with Store(root / "live") as db:
                db.put("memories", "one", {"text": "Ёрика помнит"})
                report = create_verified_backup(db.path, root / "source.sqlite3")
            result = restore_copy(root / "source.sqlite3", root / "restored.sqlite3", report["sha256"])
            self.assertEqual(result["counts"]["records"], 1)
            with sqlite3.connect(root / "restored.sqlite3") as db:
                row = db.execute("SELECT payload FROM records").fetchone()
                self.assertIn("Ёрика", row[0])
            with Store(root / "live") as db:
                self.assertEqual(db.get("memories", "one")["text"], "Ёрика помнит")

    def test_refuse_overwrite_or_untrusted_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with Store(root / "live") as db:
                report = create_verified_backup(db.path, root / "source.sqlite3")
            target = root / "target.sqlite3"
            target.write_bytes(b"keep")
            with self.assertRaises(FileExistsError):
                restore_copy(root / "source.sqlite3", target, report["sha256"])
            self.assertEqual(target.read_bytes(), b"keep")
            target.unlink()
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                restore_copy(root / "source.sqlite3", target, "0" * 64)
            self.assertFalse(target.exists())

if __name__ == "__main__":
    unittest.main()
