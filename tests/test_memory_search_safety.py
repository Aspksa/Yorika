"""Memory Foundation 2: search bounds and namespace isolation, without profile data."""
import tempfile
import unittest
from pathlib import Path
from backend.storage import Store


class MemorySearchSafetyTests(unittest.TestCase):
    def test_bounded_queries_fail_before_scanning(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as db:
                db.put("memories", "a", {"text": "память"})
                for search in (db.search_records, db.search_records_fts):
                    with self.subTest(method=search.__name__):
                        with self.assertRaises(ValueError):
                            search("memories", "а" * 4001)

    def test_ranked_search_cannot_cross_namespaces_with_equal_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as db:
                db.put("memories", "same", {"text": "фиолетовая книга"})
                db.put("secrets", "same", {"text": "фиолетовый пароль"})
                try:
                    found = db.search_records_fts("memories", "фиолетовая")
                except RuntimeError as exc:
                    if "FTS5" in str(exc):
                        self.skipTest("FTS5 not available")
                    raise
                self.assertEqual([x["record_id"] for x in found], ["same"])
                self.assertEqual(found[0]["value"]["text"], "фиолетовая книга")
                self.assertEqual(db.search_records_fts("memories", "пароль"), [])

    def test_repeated_fts_search_and_reopen_are_stable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with Store(root) as db:
                db.remember("note", "Ёрика сохраняет контекст разговора", "user")
                try:
                    for _ in range(15):
                        self.assertEqual(len(db.search_records_fts("memories", "контекст")), 1)
                except RuntimeError as exc:
                    if "FTS5" in str(exc):
                        self.skipTest("FTS5 not available")
                    raise
            with Store(root) as db:
                self.assertEqual(db.get("memories", "note")["source"], "user")


if __name__ == "__main__":
    unittest.main()
