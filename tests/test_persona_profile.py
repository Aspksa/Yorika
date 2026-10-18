import json
import tempfile
import unittest
from pathlib import Path

from backend.persona_profile import DEFAULT_CAPSULE, load_persona_capsule


class PersonaProfileTests(unittest.TestCase):
    def test_default_without_pack(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(load_persona_capsule(Path(folder) / "absent.json"), DEFAULT_CAPSULE)

    def test_original_schema_capsule(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "pack.json"
            data = {
                "schema_version": "2.0.0", "pack_id": "yorika.soul.ru",
                "categories": [{"id": str(x)} for x in range(52)],
                "replies": [{"id": str(x)} for x in range(1024)],
                "runtime_prompt_capsule": "Тестовый профиль личности Йорики для Cloud.ru",
            }
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(load_persona_capsule(path), data["runtime_prompt_capsule"])
            data["replies"].pop()
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Incomplete"):
                load_persona_capsule(path)


if __name__ == "__main__":
    unittest.main()
