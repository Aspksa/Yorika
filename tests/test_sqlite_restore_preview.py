from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path
from backend.storage import Store
from scripts.sqlite_backup import create_verified_backup
from scripts.sqlite_restore_preview import preview


class RestorePreviewTests(unittest.TestCase):
    def test_snapshot_preview_is_read_only_and_preserves_original(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with Store(root / "live") as live:
                live.put("memories", "a", {"text": "Ёрика помнит"})
                live.append_event("memory", {"text": "привет"})
                report = create_verified_backup(live.path, root / "snapshot.db")
            before = (root / "snapshot.db").read_bytes()
            result = preview(root / "snapshot.db", report["sha256"])
            self.assertEqual(result["counts"], {"events": 1, "records": 1})
            self.assertTrue(result["read_only"])
            self.assertEqual(before, (root / "snapshot.db").read_bytes())
            with Store(root / "live") as live:
                self.assertEqual(live.get("memories", "a")["text"], "Ёрика помнит")

    def test_reject_corruption_and_bad_digest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bad = root / "bad.db"
            bad.write_bytes(b"not sqlite")
            with self.assertRaises((sqlite3.DatabaseError, ValueError)):
                preview(bad)
            with Store(root / "live") as live:
                report = create_verified_backup(live.path, root / "snapshot.db")
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                preview(root / "snapshot.db", "0" * 64)
            self.assertEqual(preview(root / "snapshot.db", report["sha256"])["schema_version"], 1)

    def test_large_backup_streaming_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with Store(root / "live") as live:
                live.put("memories", "large", {"text": "Ё" * (1024 * 1024)})
                report = create_verified_backup(live.path, root / "snapshot.db")
            result = preview(root / "snapshot.db", report["sha256"])
            self.assertEqual(result["sha256"], report["sha256"])
            self.assertEqual(result["counts"]["records"], 1)

    def test_reject_malformed_yorika_tables(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad-schema.sqlite3"
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("CREATE TABLE records (namespace TEXT, record_id TEXT, payload TEXT, updated_at TEXT)")
                db.execute("CREATE TABLE events (event_id INTEGER PRIMARY KEY, event_type TEXT NOT NULL, payload TEXT NOT NULL, recorded_at TEXT NOT NULL)")
                db.execute("PRAGMA user_version=1")
            with self.assertRaisesRegex(ValueError, "Backup schema mismatch: records"):
                preview(path)

    def test_reject_arbitrary_sqlite_database(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "other.db"
            with closing(sqlite3.connect(file)) as db, db:
                db.execute("PRAGMA user_version=1")
                db.execute("CREATE TABLE unrelated (x TEXT)")
            with self.assertRaisesRegex(ValueError, "tables"):
                preview(file)


if __name__ == "__main__":
    unittest.main()
