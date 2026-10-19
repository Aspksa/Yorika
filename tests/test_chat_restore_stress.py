from contextlib import closing
"""Cross-connection SQLite chat CAS and non-destructive restore regression tests.

These tests use temporary local files, never real Yorika profile data.
"""
import concurrent.futures
import importlib.util
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from backend.storage import Store
from scripts.sqlite_backup import create_verified_backup
from scripts.sqlite_restore_copy import restore_copy

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("yorika_chat_stress", ROOT / "scripts" / "chat-store.py")
chat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chat)


class ChatRestoreStressTests(unittest.TestCase):
    def test_simultaneous_tabs_only_one_writer_wins_each_revision(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with Store(root):
                pass  # Create schema before concurrency starts.
            for round_id in range(8):
                starting = chat.run("get", directory=root)
                revision = starting["revision"]
                barrier = threading.Barrier(6)

                def writer(index):
                    item = {"from": "me", "text": f"tab-{round_id}-{index}", "ts": round_id * 10 + index}
                    barrier.wait(timeout=15)
                    return chat.run("put", {"history": [item], "revision": revision}, root)

                with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
                    results = list(executor.map(writer, range(6)))
                successes = [r for r in results if r.get("ok") is True]
                conflicts = [r for r in results if r.get("conflict") is True]
                self.assertEqual(len(successes), 1)
                self.assertEqual(len(conflicts), 5)
                self.assertEqual(chat.run("get", directory=root)["revision"], revision + 1)
                self.assertEqual(len(chat.run("get", directory=root)["history"]), 1)

    def test_restore_copy_retains_live_database_and_original_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            live = root / "live"
            with Store(live) as db:
                db.put("memories", "unicode", {"text": "Ёрика — память"})
                report = create_verified_backup(db.path, root / "source.sqlite3")
            source_before = (root / "source.sqlite3").read_bytes()
            destination = root / "recovery.sqlite3"
            result = restore_copy(root / "source.sqlite3", destination, report["sha256"])
            self.assertEqual(result["sha256"], report["sha256"])
            self.assertEqual((root / "source.sqlite3").read_bytes(), source_before)
            with closing(sqlite3.connect(destination)) as recovered, recovered:
                payload = recovered.execute(
                    "SELECT payload FROM records WHERE namespace=? AND record_id=?",
                    ("memories", "unicode"),
                ).fetchone()[0]
                self.assertIn("Ёрика", payload)
            with Store(live) as db:
                self.assertEqual(db.get("memories", "unicode")["text"], "Ёрика — память")
            with self.assertRaises(FileExistsError):
                restore_copy(root / "source.sqlite3", destination, report["sha256"])

    def test_restore_rejects_modified_snapshot_without_creating_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with Store(root / "live") as db:
                db.put("memories", "one", {"text": "original"})
                report = create_verified_backup(db.path, root / "source.sqlite3")
            with (root / "source.sqlite3").open("ab") as target:
                target.write(b"tampered")
            destination = root / "recovery.sqlite3"
            with self.assertRaises(ValueError):
                restore_copy(root / "source.sqlite3", destination, report["sha256"])
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
