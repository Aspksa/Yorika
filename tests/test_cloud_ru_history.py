import tempfile
import unittest
from pathlib import Path

from backend.cloud_ru_history import load_history, save_turn
from backend.storage import Store


class CloudDialogueHistoryTests(unittest.TestCase):
    def test_history_persists_and_is_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            with Store(path) as store:
                for i in range(12):
                    save_turn(store, "вопрос " + str(i), "ответ " + str(i))
            with Store(path) as store:
                messages = load_history(store)
            self.assertEqual(len(messages), 16)
            self.assertEqual(messages[0]["content"], "вопрос 4")
            self.assertEqual(messages[-1]["content"], "ответ 11")
            self.assertEqual(set(m["role"] for m in messages), {"user", "assistant"})

    def test_empty_history_and_trimmed_turn(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as store:
                self.assertEqual(load_history(store), [])
                save_turn(store, "x" * 5000, "y" * 5000)
                messages = load_history(store)
                self.assertEqual(len(messages[0]["content"]), 4000)
                self.assertEqual(len(messages[1]["content"]), 4000)


if __name__ == "__main__":
    unittest.main()
