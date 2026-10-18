import importlib.util
from pathlib import Path
import tempfile
import unittest

from backend.storage import Store

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "recall-memory.py"
spec = importlib.util.spec_from_file_location("yorika_recall_memory", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MemoryRecallTests(unittest.TestCase):
    def test_returns_sourced_recall_without_cross_namespace_leak(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with Store(root) as store:
                store.remember("a", "Ёрика помнит разговор", "user-confirmed", source_id="chat-1")
                store.put("secrets", "x", {"text": "Ёрика разговор"})
            result = module.recall("Ёрика разговор", root)
            self.assertFalse(result["generated"])
            self.assertEqual([row["record_id"] for row in result["memories"]], ["a"])
            self.assertEqual(result["memories"][0]["source"], "user-confirmed")
            self.assertEqual(result["memories"][0]["source_id"], "chat-1")

    def test_bad_queries_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            for value in ("", " ", "a" * 4001, None):
                with self.assertRaises(ValueError):
                    module.recall(value, Path(folder))


if __name__ == "__main__":
    unittest.main()
