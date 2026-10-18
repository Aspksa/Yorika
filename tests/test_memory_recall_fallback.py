import tempfile
import unittest
from pathlib import Path

from backend.storage import Store


class MemoryRecallFallbackTests(unittest.TestCase):
    def test_relaxed_search_only_when_strict_match_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as store:
                if not store.ensure_memory_index():
                    self.skipTest("SQLite FTS5 unavailable")
                store.remember("a", "У меня есть любимая фиолетовая книга", "user")
                store.remember("b", "Люблю утренний кофе", "user")
                exact = store.search_memory_index("фиолетовая книга", 5)
                self.assertEqual([r["record_id"] for r in exact], ["a"])
                relaxed = store.search_memory_index("фиолетовая кофе", 5)
                self.assertEqual({r["record_id"] for r in relaxed}, {"a", "b"})
                self.assertEqual(store.search_memory_index("совсемнеизвестное", 5), [])

    def test_explicit_memories_only(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as store:
                if not store.ensure_memory_index():
                    self.skipTest("SQLite FTS5 unavailable")
                store.put("persona_generated", "x", {"text": "уникальнаяпроверка"})
                self.assertEqual(store.search_memory_index("уникальнаяпроверка", 5), [])


if __name__ == "__main__":
    unittest.main()
