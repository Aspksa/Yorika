import sqlite3
import tempfile
import unittest
from pathlib import Path
from scripts.sqlite_backup import create_verified_backup, verify_snapshot


class BackupTests(unittest.TestCase):
    def test_wal_snapshot_restores_live_rows_and_utf8(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            live = root / "db.sqlite3"
            with sqlite3.connect(live) as db:
                db.execute("PRAGMA journal_mode=WAL")
                db.execute("CREATE TABLE memories (content TEXT)")
                db.execute("INSERT INTO memories VALUES (?)", ("Ёрика помнит",))
            snapshot = root / "archive" / "backup.sqlite3"
            report = create_verified_backup(live, snapshot)
            self.assertEqual(report["integrity"], "ok")
            with sqlite3.connect(snapshot) as restored:
                self.assertEqual(restored.execute("SELECT content FROM memories").fetchone()[0], "Ёрика помнит")

    def test_wont_overwrite_source_or_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "db.sqlite3"
            with sqlite3.connect(path):
                pass
            with self.assertRaises(ValueError):
                create_verified_backup(path, path)
            destination = Path(folder) / "backup.sqlite3"
            destination.write_bytes(b"keep me")
            with self.assertRaises(FileExistsError):
                create_verified_backup(path, destination)
            self.assertEqual(destination.read_bytes(), b"keep me")

    def test_reject_symlink_destination(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original = root / "live.sqlite3"
            with sqlite3.connect(original) as db:
                db.execute("CREATE TABLE example (id INTEGER)")
            protected = root / "protected.txt"
            protected.write_text("untouched")
            link = root / "backup.sqlite3"
            try:
                link.symlink_to(protected)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks unavailable")
            with self.assertRaises(FileExistsError):
                create_verified_backup(original, link)
            self.assertEqual(protected.read_text(), "untouched")

    def test_verification_rejects_corrupt_file(self):
        with tempfile.TemporaryDirectory() as folder:
            bad = Path(folder) / "bad.sqlite3"
            bad.write_bytes(b"not a sqlite database")
            with self.assertRaises(sqlite3.DatabaseError):
                verify_snapshot(bad)


if __name__ == "__main__":
    unittest.main()
