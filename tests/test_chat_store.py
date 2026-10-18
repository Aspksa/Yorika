import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "chat-store.py"

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
            self.assertEqual(run("get"), {"history": None})
            data = [{"from": "me", "text": "Привет, Ёрика!", "ts": 1234567890000}]
            self.assertEqual(run("put", data), {"ok": True})
            self.assertEqual(run("get"), {"history": data})
            self.assertEqual(run("clear"), {"ok": True})
            self.assertEqual(run("get"), {"history": []})

    def test_rejects_invalid_history(self):
        with tempfile.TemporaryDirectory() as temp:
            env = dict(os.environ, LOCALAPPDATA=temp)
            p = subprocess.run([sys.executable, str(SCRIPT), "put"],
                input=json.dumps([{"from": "evil", "text": "hi", "ts": 1}]),
                capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT), env=env)
            self.assertNotEqual(p.returncode, 0)
            self.assertFalse((Path(temp)/"Yorika"/"data"/"yorika.sqlite3").exists())

if __name__ == "__main__":
    unittest.main()
