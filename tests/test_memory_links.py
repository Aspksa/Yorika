"""Associations remain explicit, recoverable, and never resurrect deleted memory."""
import tempfile
import unittest
from pathlib import Path
from backend.storage import Store


class MemoryLinksTests(unittest.TestCase):
    def test_links_survive_reopen_without_duplicate_creation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with Store(root) as db:
                db.remember("a", "Ёрика сохраняет план", "user")
                db.remember("b", "У плана есть задачи", "user")
                first = db.link_memories("a", "b", "related")
                self.assertEqual(first, db.link_memories("a", "b", "related"))
                self.assertEqual(len(db.list_memory_links("a")), 1)
            with Store(root) as db:
                self.assertEqual(db.list_memory_links("b")[0]["link_id"], first["link_id"])
                self.assertEqual(len(db.list_records("memory_links")), 1)

    def test_no_links_for_missing_memory_or_invalid_relations(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as db:
                db.remember("a", "известное", "user")
                db.put("secrets", "b", {"text": "не память"})
                for left, right, relation in (("a", "b", "related"),
                                              ("a", "a", "related"),
                                              ("a", "b", "invented")):
                    with self.subTest(left=left, right=right, relation=relation):
                        with self.assertRaises(ValueError):
                            db.link_memories(left, right, relation)
                self.assertEqual(db.list_records("memory_links"), [])

    def test_deletion_hides_links_and_never_exposes_memory_text(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as db:
                db.remember("a", "секретное воспоминание", "user")
                db.remember("b", "другое воспоминание", "user")
                result = db.link_memories("a", "b", "contradicts")
                self.assertNotIn("секретное", str(result))
                self.assertTrue(db.delete_record("memories", "b"))
                self.assertEqual(db.list_memory_links("a"), [])
                self.assertIsNotNone(db.get("memories", "a"))


if __name__ == "__main__":
    unittest.main()
