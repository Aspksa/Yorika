import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from backend.storage import Store

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("import_browser_memory", ROOT / "scripts" / "import-browser-memory.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class BrowserImportTests(unittest.TestCase):
    def test_snapshot_is_preserved_and_duplicate_skipped(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            snapshot = {
                "format": "yorika-browser-export",
                "schema_version": 1,
                "origin": "http://127.0.0.1:12345",
                "indexeddb": {"memories": [{"id": "m-1", "text": "Помню"}]},
                "localstorage": {"yorika.chat": '[{"from":"me","text":"Привет"}]'},
            }
            path = directory / "export.json"
            path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
            target = directory / "data"
            self.assertEqual(mod.import_file(path, target), (2, 0))
            self.assertEqual(mod.import_file(path, target), (0, 1))
            import hashlib
            namespace = "browser/" + hashlib.sha256(snapshot["origin"].encode()).hexdigest()[:20]
            with Store(target) as db:
                self.assertEqual(db.get(namespace + "/memories", "m-1")["record"]["text"], "Помню")
                self.assertIn("Привет", db.get(namespace + "/localstorage", "yorika.chat")["value"])

    def test_rejects_external_origin_without_touching_database(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "invalid.json"
            path.write_text(json.dumps({"format": "yorika-browser-export", "schema_version": 1,
                "origin": "https://other.example", "indexeddb": {}, "localstorage": {}}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "origin"):
                mod.import_file(path, root / "data")
            self.assertFalse((root / "data" / "yorika.sqlite3").exists())


if __name__ == "__main__":
    unittest.main()
