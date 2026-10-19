"""Only one explicitly selected checkpoint may be active."""
import json
import tempfile
import unittest
from pathlib import Path
from backend.active_brain import select_brain, active_brain


class ActiveBrainTests(unittest.TestCase):
    def test_select_once_without_autopromotion(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            model = root / "brain.pt"
            model.write_bytes(b"fixture")
            select_brain(root, model)
            self.assertEqual(active_brain(root), model.resolve())
            with self.assertRaises(FileExistsError):
                select_brain(root, model)
            self.assertIs(json.loads((root / "active-brain.json").read_text())["automatic"], False)

    def test_reject_external_path_and_manifest_escape(self):
        with tempfile.TemporaryDirectory() as base:
            root = Path(base) / "models"
            root.mkdir()
            external = Path(base) / "outside.pt"
            external.write_bytes(b"fixture")
            with self.assertRaises(ValueError):
                select_brain(root, external)
            (root / "active-brain.json").write_text(json.dumps({
                "schema": 1, "checkpoint": "../outside.pt",
                "engine": "yorika-own-transformer", "automatic": False}))
            with self.assertRaises(ValueError):
                active_brain(root)


if __name__ == "__main__":
    unittest.main()
