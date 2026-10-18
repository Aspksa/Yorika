import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.storage import Store


class StorageTests(unittest.TestCase):
    def test_unicode_persistence_and_upsert(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with Store(root) as db:
                db.put("memories", "one", {"text": "Привет, Yorika"})
                db.put("memories", "one", {"text": "Помню"})
                self.assertEqual(db.get("memories", "one"), {"text": "Помню"})
            with Store(root) as db:
                self.assertEqual(db.get("memories", "one"), {"text": "Помню"})
                self.assertIsNone(db.get("memories", "missing"))

    def test_events_backup_and_restore(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with Store(root / "data") as db:
                event_id = db.append_event("chat", {"text": "история"})
                self.assertGreater(event_id, 0)
                db.put("settings", "profile", {"tone": "gentle"})
                backup_path = db.backup(root / "snapshot.sqlite3")
                self.assertTrue(backup_path.exists())
            with sqlite3.connect(root / "snapshot.sqlite3") as restored:
                self.assertEqual(restored.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(restored.execute("SELECT count(*) FROM events").fetchone()[0], 1)
                self.assertEqual(restored.execute("SELECT count(*) FROM records").fetchone()[0], 1)

    def test_backup_refuses_to_overwrite_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with Store(root / "data") as db:
                db.put("chat", "one", {"text": "Ёрика"})
                target = root / "saved.sqlite3"
                db.backup(target)
                original = target.read_bytes()
                with self.assertRaises(FileExistsError):
                    db.backup(target)
                self.assertEqual(target.read_bytes(), original)
                self.assertEqual(db.get("chat", "one"), {"text": "Ёрика"})

    def test_reject_future_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with Store(root):
                pass
            with sqlite3.connect(root / "yorika.sqlite3") as db:
                db.execute("PRAGMA user_version=999")
            with self.assertRaisesRegex(RuntimeError, "newer"):
                Store(root)


if __name__ == "__main__":
    unittest.main()
