"""Memory consolidation contract: preview, provenance, idempotence and isolation."""
import tempfile
import unittest
from pathlib import Path
from backend.storage import Store


class MemoryConsolidationTests(unittest.TestCase):
    def test_preview_then_apply_only_exact_duplicates(self):
        with tempfile.TemporaryDirectory() as d:
            with Store(Path(d)) as db:
                db.remember("a", "Книга о космосе", "user", source_id="chat1")
                db.remember("b", "Книга о космосе", "user", source_id="chat1")
                db.remember("c", "Книга о космосе", "user", source_id="chat2")
                db.remember("d", "Книга о космосе", "import", source_id="chat1")
                db.put("settings", "b", {"text": "не удалять"})
                preview = db.consolidate_memories()
                self.assertEqual(preview["duplicates"], 1)
                self.assertEqual(preview["removed"], 0)
                self.assertIsNotNone(db.get("memories", "b"))
                result = db.consolidate_memories(dry_run=False)
                self.assertEqual(result["duplicate_ids"], ["b"])
                self.assertEqual(db.get("memories", "b"), None)
                self.assertEqual(db.get("settings", "b"), {"text": "не удалять"})
                self.assertIsNotNone(db.get("memories", "c"))
                self.assertIsNotNone(db.get("memories", "d"))
                self.assertEqual(db.consolidate_memories(dry_run=False)["removed"], 0)
            with Store(Path(d)) as db:
                self.assertIsNotNone(db.get("memories", "a"))
                self.assertIsNone(db.get("memories", "b"))

    def test_no_merge_for_contradictions_or_missing_provenance(self):
        with tempfile.TemporaryDirectory() as d:
            with Store(Path(d)) as db:
                db.put("memories", "a", {"subject": "погода", "claim": "ясно"})
                db.put("memories", "b", {"subject": "погода", "claim": "не ясно"})
                db.put("memories", "c", {"text": "текст без источника"})
                db.put("memories", "d", {"text": "текст без источника"})
                self.assertEqual(db.consolidate_memories(dry_run=False)["removed"], 0)

    def test_limit_and_validation_fail_without_writes(self):
        with tempfile.TemporaryDirectory() as d:
            with Store(Path(d)) as db:
                db.remember("a", "то же", "user")
                db.remember("b", "то же", "user")
                with self.assertRaises(ValueError):
                    db.consolidate_memories(dry_run=False, limit=1)
                for kwargs in ({"dry_run": 0}, {"limit": True}, {"limit": 0}):
                    with self.assertRaises(ValueError):
                        db.consolidate_memories(**kwargs)
                self.assertIsNotNone(db.get("memories", "b"))


if __name__ == "__main__":
    unittest.main()
