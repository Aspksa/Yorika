"""Chat memory capture and timestamp regression tests."""
import importlib.util
import math
import tempfile
import unittest
from pathlib import Path

from backend.storage import Store

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("yorika_chat_memory_regressions", ROOT / "scripts" / "chat-store.py")
chat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chat)


class ChatMemoryRegressions(unittest.TestCase):
    def test_explicit_russian_and_english_requests(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as store:
                history = [
                    {"from": "me", "text": "Запомни: завтра встреча", "ts": 100},
                    {"from": "me", "text": "remember, preferred tea is green", "ts": 101},
                    {"from": "me", "text": "Это обычное сообщение", "ts": 102},
                ]
                chat.capture_explicit_memories(store.connection, [], history)
                values = store.connection.execute(
                    "SELECT payload FROM records WHERE namespace='memories' ORDER BY record_id"
                ).fetchall()
                self.assertEqual(len(values), 2)
                self.assertIn("завтра встреча", str(values))
                self.assertIn("preferred tea is green", str(values))

    def test_replayed_explicit_request_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            message = {"from": "me", "text": "Запомни важный факт", "ts": 100}
            first = chat.run("put", {"history": [message], "revision": 0}, Path(folder))
            self.assertEqual(first["revision"], 1)
            second = chat.run("put", {"history": [message], "revision": 1}, Path(folder))
            self.assertEqual(second["revision"], 2)
            with Store(Path(folder)) as store:
                count = store.connection.execute("SELECT COUNT(*) FROM records WHERE namespace='memories'").fetchone()[0]
                self.assertEqual(count, 1)

    def test_nonfinite_chat_timestamps_are_rejected(self):
        for ts in (math.nan, math.inf, -math.inf):
            with self.subTest(ts=ts), self.assertRaises(ValueError):
                chat.valid_history([{"from": "me", "text": "hello", "ts": ts}])

    def test_stale_revision_does_not_capture_memory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            chat.run("put", {"history": [{"from":"me","text":"first","ts":1}], "revision":0}, root)
            result = chat.run("put", {"history":[{"from":"me","text":"Запомни: чужое","ts":2}], "revision":0}, root)
            self.assertTrue(result["conflict"])
            with Store(root) as store:
                self.assertEqual(store.connection.execute(
                    "SELECT COUNT(*) FROM records WHERE namespace='memories'"
                ).fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
