import tempfile
import unittest
from pathlib import Path
from backend.storage import Store
from backend.memory_controls import (set_preference, list_preferences, list_memories,
                                     update_memory, delete_record)


class MemoryControlsTests(unittest.TestCase):
    def test_explicit_preference_and_delete(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as store:
                self.assertEqual(list_preferences(store), [])
                set_preference(store, "tone", "Кратко и ясно")
                self.assertEqual(list_preferences(store)[0]["text"], "Кратко и ясно")
                self.assertTrue(delete_record(store, "user_preferences", "tone")["deleted"])
                self.assertEqual(list_preferences(store), [])

    def test_edit_and_delete_memory(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as store:
                store.remember("a", "старое", "explicit-chat-request")
                update_memory(store, "a", "новое")
                self.assertEqual(list_memories(store)[0]["text"], "новое")
                self.assertTrue(delete_record(store, "memories", "a")["deleted"])
                self.assertEqual(list_memories(store), [])

    def test_bad_input_and_no_implicit_preference(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as store:
                with self.assertRaises(ValueError):
                    set_preference(store, "../unsafe", "value")
                with self.assertRaises(ValueError):
                    update_memory(store, "missing", "value")
                with self.assertRaises(ValueError):
                    delete_record(store, "persona_generated", "any")
                self.assertEqual(list_preferences(store), [])


if __name__ == "__main__":
    unittest.main()
