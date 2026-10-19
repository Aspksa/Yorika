"""Time-aware retrieval never deletes underlying memories or leaks other namespaces."""
import tempfile
import unittest
from pathlib import Path
from backend.storage import Store


class MemoryLifecycleTests(unittest.TestCase):
    def test_priority_expiry_and_bounded_context(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with Store(root) as db:
                db.remember("low", "обычное воспоминание", "user", source_id="one")
                db.remember("high", "Важный план", "user", source_id="two")
                db.remember("expired", "устаревшая задача", "user")
                db.put("secrets", "hidden", {"text": "внутренний секрет"})
                db.set_memory_policy("low", priority=1)
                db.set_memory_policy("high", priority=5)
                db.set_memory_policy("expired", expires_at="2020-01-01T00:00:00+00:00")
                view = db.memory_context(at="2026-10-19T00:00:00+00:00")
                self.assertEqual([x["record_id"] for x in view], ["high", "low"])
                self.assertNotIn("внутренний секрет", str(view))
                tiny = db.memory_context(limit=1, max_chars=4)
                self.assertEqual(tiny[0]["text"], "Важн")
                self.assertTrue(tiny[0]["truncated"])
                self.assertEqual(db.get("memories", "expired")["text"], "устаревшая задача")
            with Store(root) as db:
                self.assertEqual(db.memory_context(limit=1)[0]["record_id"], "high")

    def test_invalid_policy_and_missing_id_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as db:
                db.remember("present", "память", "user")
                for kwargs in ({"priority": True}, {"priority": 0},
                               {"expires_at": "not-a-date"},
                               {"expires_at": "2026-01-01T00:00:00"}):
                    with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                        db.set_memory_policy("present", **kwargs)
                with self.assertRaises(ValueError):
                    db.set_memory_policy("missing")
                self.assertIsNone(db.get("memory_policies", "present"))
                with self.assertRaises(ValueError):
                    db.memory_context(max_chars=0)
                with self.assertRaises(ValueError):
                    db.memory_context(at="2026-01-01T00:00:00")


if __name__ == "__main__":
    unittest.main()
