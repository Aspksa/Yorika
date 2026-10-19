from contextlib import closing
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import scripts.sqlite_backup as backup_module
from pathlib import Path
from scripts.sqlite_backup import create_verified_backup, verify_snapshot


class BackupTests(unittest.TestCase):
    def test_wal_snapshot_restores_live_rows_and_utf8(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            live = root / "db.sqlite3"
            with closing(sqlite3.connect(live)) as db, db:
                db.execute("PRAGMA journal_mode=WAL")
                db.execute("CREATE TABLE memories (content TEXT)")
                db.execute("INSERT INTO memories VALUES (?)", ("Ёрика помнит",))
            snapshot = root / "archive" / "backup.sqlite3"
            report = create_verified_backup(live, snapshot)
            self.assertEqual(report["integrity"], "ok")
            with closing(sqlite3.connect(snapshot)) as restored, restored:
                self.assertEqual(restored.execute("SELECT content FROM memories").fetchone()[0], "Ёрика помнит")

    def test_wont_overwrite_source_or_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "db.sqlite3"
            with closing(sqlite3.connect(path)) as db:
                pass
            with self.assertRaises(ValueError):
                create_verified_backup(path, path)
            destination = Path(folder) / "backup.sqlite3"
            destination.write_bytes(b"keep me")
            with self.assertRaises(FileExistsError):
                create_verified_backup(path, destination)
            self.assertEqual(destination.read_bytes(), b"keep me")

    def test_rejects_source_alias_with_existing_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "db.sqlite3"
            with closing(sqlite3.connect(source)) as db:
                db.execute("CREATE TABLE example (id INTEGER)")
            alias = root / "alias.sqlite3"
            try:
                alias.symlink_to(source)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks unavailable on this runner")
            with self.assertRaises(ValueError):
                create_verified_backup(source, alias)
            self.assertTrue(source.exists())

    def test_reject_symlink_destination(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original = root / "live.sqlite3"
            with closing(sqlite3.connect(original)) as db, db:
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

    def test_backup_verification_releases_file_handles(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            live = root / "live.sqlite3"
            with closing(sqlite3.connect(live)) as db, db:
                db.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
                db.execute("INSERT INTO sample VALUES (1)")
            snapshot = root / "backup.sqlite3"
            create_verified_backup(live, snapshot)
            verify_snapshot(snapshot)
            snapshot.unlink()
            self.assertFalse(snapshot.exists())

    def test_published_backup_is_verified_and_removed_on_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "live.sqlite3"
            with closing(sqlite3.connect(source)) as db, db:
                db.execute("CREATE TABLE example (value TEXT)")
            target = root / "backup.sqlite3"
            real_verify = backup_module.verify_snapshot

            def reject_target(path):
                if Path(path) == target:
                    raise ValueError("simulated published verification failure")
                return real_verify(path)

            with patch.object(backup_module, "verify_snapshot", side_effect=reject_target):
                with self.assertRaisesRegex(ValueError, "simulated published verification failure"):
                    create_verified_backup(source, target)
            self.assertFalse(target.exists())

    def test_verification_rejects_corrupt_file(self):
        with tempfile.TemporaryDirectory() as folder:
            bad = Path(folder) / "bad.sqlite3"
            bad.write_bytes(b"not a sqlite database")
            with self.assertRaises(sqlite3.DatabaseError):
                verify_snapshot(bad)


if __name__ == "__main__":
    unittest.main()
