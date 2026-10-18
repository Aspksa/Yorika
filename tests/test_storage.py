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

    def test_delete_record_is_exact_and_persistent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with Store(root) as db:
                db.put("memories", "shared", {"text": "Удалить"})
                db.put("settings", "shared", {"text": "Сохранить"})
                self.assertTrue(db.delete_record("memories", "shared"))
                self.assertFalse(db.delete_record("memories", "shared"))
                self.assertIsNone(db.get("memories", "shared"))
                self.assertEqual(db.get("settings", "shared"), {"text": "Сохранить"})
                for namespace, record_id in (("", "shared"), ("memories", ""), (None, "shared")):
                    with self.assertRaises(ValueError):
                        db.delete_record(namespace, record_id)
            with Store(root) as db:
                self.assertIsNone(db.get("memories", "shared"))
                self.assertEqual(db.get("settings", "shared"), {"text": "Сохранить"})

    def test_list_records_is_bounded_and_namespace_scoped(self):
        with tempfile.TemporaryDirectory() as temp:
            with Store(Path(temp)) as db:
                db.put("memories", "b", {"text": "Ёрика"})
                db.put("memories", "a", {"text": "Привет"})
                db.put("settings", "private", {"secret": "hidden"})
                rows = db.list_records("memories", limit=1)
                self.assertEqual(len(rows), 1)
                self.assertIn(rows[0]["record_id"], {"a", "b"})
                self.assertEqual({x["record_id"] for x in db.list_records("memories")}, {"a", "b"})
                self.assertTrue(all("updated_at" in x for x in db.list_records("memories")))
                for bad in (0, -1, 1001, True, "10"):
                    with self.assertRaises(ValueError):
                        db.list_records("memories", bad)
                with self.assertRaises(ValueError):
                    db.list_records("")

    def test_search_records_cyrillic_casefold_and_namespace_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as db:
                db.put("memories", "one", {"text": "Ёрика помнит наш разговор"})
                db.put("memories", "two", {"text": "Совсем другая тема"})
                db.put("private", "hidden", {"text": "ЁРИКА секрет"})
                found = db.search_records("memories", "ёРИКА")
                self.assertEqual([row["record_id"] for row in found], ["one"])
                self.assertEqual(db.search_records("memories", "нет совпадений"), [])
                self.assertEqual(db.search_records("memories", "разговор", 1)[0]["record_id"], "one")
                for bad in (0, 101, True, "2"):
                    with self.assertRaises(ValueError):
                        db.search_records("memories", "Ёрика", bad)
                with self.assertRaises(ValueError):
                    db.search_records("", "Ёрика")
                with self.assertRaises(ValueError):
                    db.search_records("memories", "   ")

    def test_search_ignores_json_keys_but_finds_nested_text_values(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as db:
                db.put("memories", "nested", {
                    "секретный_ключ": {"notes": ["Привет, ЁРИКА", {"text": "Вспомни"}]},
                    "count": 42,
                })
                db.put("memories", "only-key", {"ЁРИКА": 1})
                self.assertEqual(
                    [x["record_id"] for x in db.search_records("memories", "ёрика")],
                    ["nested"],
                )
                self.assertEqual(
                    [x["record_id"] for x in db.search_records("memories", "вспомни")],
                    ["nested"],
                )
                self.assertEqual(db.search_records("memories", "секретный_ключ"), [])

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

    def test_backup_rejects_uncommitted_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with Store(root / "data") as db:
                db.connection.execute("BEGIN")
                db.connection.execute("INSERT INTO events(event_type,payload,recorded_at) VALUES(?,?,?)",
                                      ("test", "{}", "2026-10-18"))
                target = root / "snapshot.sqlite3"
                with self.assertRaisesRegex(RuntimeError, "Commit or rollback"):
                    db.backup(target)
                self.assertFalse(target.exists())
                db.connection.rollback()
                self.assertTrue(db.backup(target).exists())

    def test_refuse_unversioned_existing_database_without_modification(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            file = root / "yorika.sqlite3"
            with sqlite3.connect(file) as db:
                db.execute("CREATE TABLE private_notes (message TEXT)")
                db.execute("INSERT INTO private_notes VALUES (?)", ("Не удалять",))
            with self.assertRaisesRegex(RuntimeError, "Unversioned database"):
                Store(root)
            with sqlite3.connect(file) as db:
                self.assertEqual(db.execute("SELECT message FROM private_notes").fetchone()[0], "Не удалять")
                self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 0)
                self.assertNotIn("records", {r[0] for r in db.execute("SELECT name FROM sqlite_master")})

    def test_reject_versioned_but_incomplete_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db_path = root / "yorika.sqlite3"
            with sqlite3.connect(db_path) as db:
                db.execute("CREATE TABLE records (namespace TEXT, record_id TEXT)")
                db.execute("CREATE TABLE events (event_id INTEGER)")
                db.execute("PRAGMA user_version=1")
            with self.assertRaisesRegex(RuntimeError, "schema mismatch"):
                Store(root)
            with sqlite3.connect(db_path) as db:
                self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 1)
                self.assertEqual(len(db.execute("PRAGMA table_info(records)").fetchall()), 2)

    def test_reject_existing_schema_with_wrong_constraints(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with sqlite3.connect(root / "yorika.sqlite3") as db:
                db.execute("CREATE TABLE records (namespace TEXT, record_id TEXT, payload TEXT, updated_at TEXT)")
                db.execute("CREATE TABLE events (event_id INTEGER PRIMARY KEY, event_type TEXT NOT NULL, payload TEXT NOT NULL, recorded_at TEXT NOT NULL)")
                db.execute("PRAGMA user_version=1")
            with self.assertRaisesRegex(RuntimeError, "schema mismatch: records"):
                Store(root)
            with sqlite3.connect(root / "yorika.sqlite3") as db:
                self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 1)

    def test_reject_corrupt_existing_database(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            file = root / "yorika.sqlite3"
            file.write_bytes(b"not a sqlite database")
            original = file.read_bytes()
            with self.assertRaises((RuntimeError, sqlite3.DatabaseError)):
                Store(root)
            self.assertEqual(file.read_bytes(), original)

    def test_rejected_schema_does_not_switch_journal_mode(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "yorika.sqlite3"
            with sqlite3.connect(path) as db:
                db.execute("CREATE TABLE alien (value TEXT)")
                self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0], "delete")
            with self.assertRaisesRegex(RuntimeError, "Unversioned database"):
                Store(root)
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0], "delete")

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
