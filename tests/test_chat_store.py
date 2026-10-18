import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "chat-store.py"
spec = importlib.util.spec_from_file_location("yorika_chat_store", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ChatStoreTests(unittest.TestCase):
    def test_persist_across_processes_and_clear(self):
        with tempfile.TemporaryDirectory() as temp:
            env = dict(os.environ, LOCALAPPDATA=temp)

            def run(action, value=None):
                p = subprocess.run(
                    [sys.executable, str(SCRIPT), action],
                    input=json.dumps(value, ensure_ascii=False) if value is not None else "",
                    capture_output=True, text=True, encoding="utf-8",
                    cwd=str(ROOT), env=env,
                )
                self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
                return json.loads(p.stdout)

            self.assertEqual(run("get"), {"history": None, "revision": 0})
            data = [{"from": "me", "text": "Привет, Ёрика!", "ts": 1234567890000}]
            self.assertEqual(run("put", {"history": data, "revision": 0}), {"ok": True, "revision": 1})
            self.assertEqual(run("get"), {"history": data, "revision": 1})
            conflict = run("put", {"history": [], "revision": 0})
            self.assertTrue(conflict["conflict"])
            self.assertEqual(conflict["history"], data)
            self.assertEqual(conflict["revision"], 1)
            self.assertEqual(run("clear", {"revision": 1}), {"ok": True, "revision": 2})
            self.assertEqual(run("get"), {"history": [], "revision": 2})

    def test_two_tabs_stale_snapshot_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            a = [{"from": "me", "text": "A", "ts": 100}]
            b = [{"from": "me", "text": "B", "ts": 101}]
            self.assertEqual(module.run("put", {"history": a, "revision": 0}, target)["revision"], 1)
            stale = module.run("put", {"history": b, "revision": 0}, target)
            self.assertTrue(stale["conflict"])
            self.assertEqual(stale["history"], a)
            self.assertEqual(module.run("get", directory=target)["history"], a)
            self.assertEqual(module.run("put", {"history": a + b, "revision": 1}, target)["revision"], 2)
            self.assertEqual(module.run("get", directory=target)["history"], a + b)

    def test_bad_revision_rejected_without_database(self):
        with tempfile.TemporaryDirectory() as temp:
            env = dict(os.environ, LOCALAPPDATA=temp)
            p = subprocess.run([sys.executable, str(SCRIPT), "put"],
                input=json.dumps({"history": [], "revision": True}),
                capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT), env=env)
            self.assertNotEqual(p.returncode, 0)
            self.assertFalse((Path(temp) / "Yorika" / "data" / "yorika.sqlite3").exists())


if __name__ == "__main__":
    unittest.main()
