import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.persona_bank import choose_example, eligible, fingerprint, category_for_query
from backend.storage import Store


class PersonaBankTests(unittest.TestCase):
    def pack(self, path):
        categories = [{"id": x} for x in ["greetings", "listening"] +
                      ["category_" + str(n) for n in range(50)]]
        replies = []
        for n in range(1024):
            category = "greetings" if n < 3 else "listening"
            replies.append({
                "id": "p%04d" % n, "ordinal": n,
                "category_id": category, "text": "Фраза номер %d" % n,
                "opening_family": "opening" + str(n % 2),
                "min_romance_level": 2 if n == 2 else 0,
                "scene_required": n == 2, "required_facts": []
            })
        path.write_text(json.dumps({"pack_id": "yorika.soul.ru",
                        "schema_version": "2.0.0",
                        "categories": categories, "replies": replies}), encoding="utf-8")

    def test_rotation_survives_store_restart_and_exhausts_without_repeating(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack.json"
            self.pack(pack)
            chosen = []
            for _ in range(3):
                with Store(Path(tmp) / "db") as store:
                    chosen.append(choose_example(store, "Привет", pack_path=pack))
            self.assertEqual(len({x["id"] for x in chosen[:2]}), 2)
            self.assertIsNone(chosen[2])
            self.assertEqual({x["category_id"] for x in chosen[:2]}, {"greetings"})

    def test_romance_requires_explicit_adult_and_scene_consent(self):
        reply = {"min_romance_level": 2, "scene_required": True,
                 "required_facts": []}
        self.assertFalse(eligible(reply, {}))
        self.assertFalse(eligible(reply, {"adult_context": True,
                         "romance_enabled": True, "romance_level": 2}))
        self.assertTrue(eligible(reply, {"adult_context": True,
                        "romance_enabled": True, "romance_level": 2,
                        "scene_enabled": True}))
        self.assertFalse(eligible(reply, {"adult_context": True,
                        "romance_enabled": True, "romance_level": 2,
                        "scene_enabled": True, "distressed": True}))

    def test_canonical_deduplicates_honorific_variations(self):
        self.assertEqual(fingerprint("Мой хозяин, здравствуйте!"),
                         fingerprint("Господин, здравствуйте!"))
        self.assertEqual(category_for_query("Спасибо!", {"gratitude", "listening"}),
                         "gratitude")


if __name__ == "__main__":
    unittest.main()
