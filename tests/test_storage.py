import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.storage import Store


class StorageTests(unittest.TestCase):
    def test_import_records_roundtrip_preview_and_namespace_isolation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with Store(root / "original") as source:
                source.put("memories", "greeting", {"text": "Привет, Ёрика"})
                bundle = source.export_records("memories")
            with Store(root / "destination") as target:
                target.put("settings", "greeting", {"secret": "preserve"})
                preview = target.import_records(bundle)
                self.assertEqual(preview["eligible"], 1)
                self.assertEqual(preview["applied"], 0)
                self.assertIsNone(target.get("memories", "greeting"))
                result = target.import_records(bundle, dry_run=False)
                self.assertEqual(result["applied"], 1)
                self.assertEqual(target.get("memories", "greeting"),
                                 {"text": "Привет, Ёрика"})
                self.assertEqual(target.export_records("memories"), bundle)
                self.assertEqual(target.get("settings", "greeting"),
                                 {"secret": "preserve"})
                with self.assertRaisesRegex(ValueError, "conflicts"):
                    target.import_records(bundle, dry_run=False)
                skipped = target.import_records(bundle, dry_run=False,
                                                on_conflict="skip")
                self.assertEqual(skipped["applied"], 0)
                self.assertEqual(skipped["conflicts"], 1)

    def test_import_records_rejects_invalid_batches_without_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            with Store(Path(temp)) as target:
                item = {"record_id": "one", "value": {"text": "Ёрика"},
                        "updated_at": "2026-10-19T00:00:00+00:00"}
                good = {"format": "yorika-records-v1", "namespace": "memories",
                        "records": [item]}
                invalid = [
                    {}, {**good, "format": "unknown"},
                    {**good, "namespace": ""},
                    {**good, "records": "bad"},
                    {**good, "records": [item, item]},
                    {**good, "records": [{**item, "record_id": ""}]},
                    {**good, "records": [{**item, "value": ["wrong"]}]},
                    {**good, "records": [{**item, "value": {"n": float("nan")}}]},
                    {**good, "records": [{**item, "updated_at": ""}]},
                ]
                for bundle in invalid:
                    with self.assertRaises((ValueError, TypeError)):
                        target.import_records(bundle, dry_run=False)
                with self.assertRaises(ValueError):
                    target.import_records(good, dry_run="false")
                with self.assertRaises(ValueError):
                    target.import_records(good, on_conflict="overwrite")
                self.assertEqual(target.export_records("memories")["records"], [])

    def test_import_records_skips_existing_ids_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temp:
            with Store(Path(temp)) as target:
                target.put("memories", "same", {"text": "keep"})
                bundle = {
                    "format": "yorika-records-v1", "namespace": "memories",
                    "records": [
                        {"record_id": "same", "value": {"text": "replace"},
                         "updated_at": "2026-10-19T00:00:00+00:00"},
                        {"record_id": "new", "value": {"text": "add"},
                         "updated_at": "2026-10-19T00:00:00+00:00"},
                    ],
                }
                result = target.import_records(bundle, dry_run=False, on_conflict="skip")
                self.assertEqual(result["conflicts"], 1)
                self.assertEqual(result["applied"], 1)
                self.assertEqual(target.get("memories", "same"), {"text": "keep"})
                self.assertEqual(target.get("memories", "new"), {"text": "add"})

    def test_import_hardening_rejects_untrusted_shapes(self):
        with tempfile.TemporaryDirectory() as temp:
            with Store(Path(temp)) as db:
                base_item = {"record_id": "one", "value": {"text": "Ёрика"},
                             "updated_at": "2026-10-19T00:00:00+00:00"}
                base = {"format": "yorika-records-v1", "namespace": "memories",
                        "records": [base_item]}
                def replace_item(**kw):
                    return {**base, "records": [{**base_item, **kw}]}
                invalid = [
                    {**base, "unknown": 1},
                    {**base, "namespace": "x" * 257},
                    {**base, "namespace": "bad\\nnamespace"},
                    replace_item(extra="field"),
                    replace_item(record_id="a" * 513),
                    replace_item(record_id="bad\\x00id"),
                    replace_item(updated_at="2026-10-19"),
                    replace_item(updated_at="invalid"),
                    replace_item(updated_at="x" * 65),
                    replace_item(value={"text": "x" * (1024 * 1024 + 1)}),
                    replace_item(value={"invalid": object()}),
                ]
                for document in invalid:
                    with self.subTest(document=str(document)[:120]):
                        with self.assertRaises(ValueError):
                            db.import_records(document, dry_run=False)
                self.assertEqual(db.export_records("memories")["records"], [])
                report = db.import_records(base)
                self.assertGreater(report["bytes"], 0)
                self.assertEqual(report["applied"], 0)

    def test_import_rejects_total_size_limit_atomically(self):
        with tempfile.TemporaryDirectory() as temp:
            with Store(Path(temp)) as db:
                records = [{"record_id": str(i), "value": {"text": "x" * 900000},
                            "updated_at": "2026-10-19T00:00:00+00:00"}
                           for i in range(38)]
                bundle = {"format": "yorika-records-v1", "namespace": "memories",
                          "records": records}
                with self.assertRaisesRegex(ValueError, "32 MiB"):
                    db.import_records(bundle, dry_run=False)
                self.assertEqual(db.export_records("memories")["records"], [])

    def test_explicit_memory_includes_provenance(self):
        with tempfile.TemporaryDirectory() as root:
            with Store(Path(root)) as db:
                item = db.remember("fact-1", "Ёрика запоминает", "user-confirmed",
                                   source_id="chat-12")
                self.assertEqual(item["source"], "user-confirmed")
                self.assertEqual(item["source_id"], "chat-12")
                self.assertTrue(item["created_at"])
                self.assertEqual(db.get("memories", "fact-1"), item)
                results = db.search_records_fts("memories", "Ёрика")
                self.assertEqual(results[0]["record_id"], "fact-1")
                for text, source in (("", "user"), ("valid", ""), ("x" * 10001, "user")):
                    with self.assertRaises(ValueError):
                        db.remember("bad", text, source)
                self.assertIsNone(db.get("memories", "bad"))

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

    def test_conditional_memory_edit_preserves_concurrent_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with Store(root) as db:
                db.put("memories", "one", {"text": "старое"})
                db.put("settings", "one", {"text": "не трогать"})
                self.assertFalse(db.update_record_if_unchanged(
                    "memories", "missing", {}, {"text": "новое"}))
                self.assertFalse(db.update_record_if_unchanged(
                    "memories", "one", {"text": "устаревшее"}, {"text": "новое"}))
                self.assertTrue(db.update_record_if_unchanged(
                    "memories", "one", {"text": "старое"}, {"text": "новое"}))
                self.assertFalse(db.update_record_if_unchanged(
                    "memories", "one", {"text": "старое"}, {"text": "перезапись"}))
                self.assertEqual(db.get("settings", "one"), {"text": "не трогать"})
                for bad in (None, [], 1):
                    with self.assertRaises(ValueError):
                        db.update_record_if_unchanged("memories", "one", bad, {})
            with Store(root) as db:
                self.assertEqual(db.get("memories", "one"), {"text": "новое"})

    def test_get_record_detail_for_memory_editor(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as db:
                db.put("memories", "one", {"text": "Ёрика"})
                db.put("settings", "one", {"text": "secret"})
                detail = db.get_record("memories", "one")
                self.assertEqual(detail["record_id"], "one")
                self.assertEqual(detail["value"], {"text": "Ёрика"})
                self.assertTrue(detail["updated_at"])
                self.assertIsNone(db.get_record("memories", "missing"))
                for namespace, record_id in (("", "one"), ("memories", ""), (None, "one")):
                    with self.assertRaises(ValueError):
                        db.get_record(namespace, record_id)

    def test_conditional_delete_rejects_stale_editor(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as db:
                db.put("memories", "one", {"text": "first"})
                db.put("settings", "one", {"text": "keep"})
                db.put("memories", "one", {"text": "new version"})
                self.assertFalse(db.delete_record_if_unchanged(
                    "memories", "one", {"text": "first"}))
                self.assertEqual(db.get("memories", "one"), {"text": "new version"})
                self.assertTrue(db.delete_record_if_unchanged(
                    "memories", "one", {"text": "new version"}))
                self.assertFalse(db.delete_record_if_unchanged(
                    "memories", "one", {"text": "new version"}))
                self.assertEqual(db.get("settings", "one"), {"text": "keep"})
                with self.assertRaises(ValueError):
                    db.delete_record_if_unchanged("memories", "one", [])

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

    def test_export_records_contains_only_requested_namespace(self):
        with tempfile.TemporaryDirectory() as temp:
            with Store(Path(temp)) as db:
                db.put("memories", "one", {"text": "Ёрика"})
                db.put("settings", "hidden", {"token": "never export"})
                exported = db.export_records("memories")
                self.assertEqual(exported["format"], "yorika-records-v1")
                self.assertEqual(exported["namespace"], "memories")
                self.assertEqual(len(exported["records"]), 1)
                self.assertEqual(exported["records"][0]["record_id"], "one")
                self.assertEqual(exported["records"][0]["value"], {"text": "Ёрика"})
                self.assertIn("updated_at", exported["records"][0])
                self.assertNotIn("never export", str(exported))
                self.assertEqual(db.export_records("missing")["records"], [])
                with self.assertRaises(ValueError):
                    db.export_records("")

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

    def test_fts_recall_ranks_text_without_leaking_namespaces(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as db:
                try:
                    db.connection.execute("CREATE VIRTUAL TABLE temp.fts_probe USING fts5(body)")
                except sqlite3.OperationalError:
                    self.skipTest("This SQLite build has no FTS5")
                db.put("memories", "one", {"text": ["Ёрика помнит разговор", "важный разговор"]})
                db.put("memories", "two", {"text": "Ёрика привет"})
                db.put("memories", "key-only", {"разговор": 5})
                db.put("private", "hidden", {"text": "Ёрика разговор"})
                matches = db.search_records_fts("memories", "Ёрика разговор")
                self.assertEqual([m["record_id"] for m in matches], ["one"])
                self.assertEqual(matches[0]["value"]["text"][0], "Ёрика помнит разговор")
                self.assertIn("rank", matches[0])
                self.assertEqual(db.search_records_fts("memories", "несуществующее"), [])
                self.assertEqual(db.search_records_fts("memories", '" OR *'), [])
                for invalid in ("", "   "):
                    with self.assertRaises(ValueError):
                        db.search_records_fts("memories", invalid)
                with self.assertRaises(ValueError):
                    db.search_records_fts("memories", "Ёрика", limit=0)

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
