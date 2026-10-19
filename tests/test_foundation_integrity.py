"""Foundation regressions for task integrity and durable user memory.

All memory tests operate in an isolated temporary directory, never the user profile.
"""
import re
import concurrent.futures
import threading
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from backend.storage import Store

ROOT = Path(__file__).resolve().parents[1]


class FoundationIntegrityTests(unittest.TestCase):
    def test_plan_registry_and_roadmap_are_consistent(self):
        completed = subprocess.run(
            [sys.executable, "scripts/check-plan.py"],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(completed.returncode, 0,
                         completed.stdout + "\n" + completed.stderr)

    def test_hypercommunication_checklist_has_machine_readable_ids(self):
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        for number in range(1, 11):
            task_id = f"HYPER-{number:03d}"
            with self.subTest(task=task_id):
                lines = re.findall(
                    rf"^- \[([ x])\] {task_id}\b", roadmap, re.MULTILINE
                )
                self.assertEqual(lines, [" "])

    def test_simultaneous_first_open_preserves_all_memories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            barrier = threading.Barrier(6)

            def worker(index):
                barrier.wait(timeout=15)
                with Store(root) as store:
                    store.remember(str(index), f"Событие {index}", "user")

            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                list(pool.map(worker, range(6)))
            with Store(root) as store:
                self.assertEqual(len(store.list_records("memories", limit=10)), 6)
                self.assertEqual(store.connection.execute(
                    "PRAGMA quick_check").fetchone()[0], "ok")

    def test_memory_survives_database_reopening(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with Store(root) as store:
                store.remember("test-memory", "Ёрика помнит русский текст", "user")
            with Store(root) as store:
                item = store.get("memories", "test-memory")
                self.assertEqual(item["text"], "Ёрика помнит русский текст")
                self.assertEqual(item["source"], "user")
                self.assertEqual(store.connection.execute(
                    "PRAGMA quick_check").fetchone()[0], "ok")

    def test_stale_memory_update_and_delete_do_not_lose_newer_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with Store(root) as writer:
                writer.remember("shared", "Версия 1", "user")
                old = writer.get("memories", "shared")
            with Store(root) as writer:
                current = dict(old, text="Версия 2")
                self.assertTrue(writer.update_record_if_unchanged(
                    "memories", "shared", old, current))
            with Store(root) as stale:
                self.assertFalse(stale.update_record_if_unchanged(
                    "memories", "shared", old, dict(old, text="Ошибка")))
                self.assertFalse(stale.delete_record_if_unchanged(
                    "memories", "shared", old))
                self.assertEqual(stale.get("memories", "shared")["text"],
                                 "Версия 2")


if __name__ == "__main__":
    unittest.main()
