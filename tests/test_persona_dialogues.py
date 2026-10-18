import json
import tempfile
import unittest
from pathlib import Path

from backend.persona_dialogues import choose_scenario, similarity
from backend.persona_profile import PACK_PATH
from backend.storage import Store


class PersonaDialogueTests(unittest.TestCase):
    def test_real_pack_manifest(self):
        data = json.loads(PACK_PATH.read_text(encoding="utf-8"))
        self.assertEqual(len(data["dialogue_extension"]["scenarios"]), 473)

    def test_conservative_similarity(self):
        self.assertEqual(similarity("совсем другой вопрос", "Устал от решений."), 0)
        self.assertGreaterEqual(
            similarity("Хочу чувствовать твою заботу.", "Хочу чувствовать твою заботу."), 0.8
        )

    def test_scenario_followup_persists_without_repeating_entry(self):
        with tempfile.TemporaryDirectory() as folder:
            dbpath = Path(folder) / "data"
            consent = {"adult_context": True, "romance_enabled": True}
            with Store(dbpath) as store:
                first = choose_scenario(store, "Хочу чувствовать твою заботу.", context=consent)
            self.assertEqual(first["scenario_id"], "yorika_dialogue_0001")
            with Store(dbpath) as store:
                next_reply = choose_scenario(store, "Устал от решений.", context=consent)
            self.assertEqual(next_reply["scenario_id"], first["scenario_id"])
            self.assertIn("вариант", next_reply["text"])
            with Store(dbpath) as store:
                self.assertIsNone(choose_scenario(store, "Хочу чувствовать твою заботу.", context=consent))

    def test_revoking_consent_blocks_active_scenario(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder) / "data"
            enabled = {"adult_context": True, "romance_enabled": True}
            with Store(directory) as store:
                started = choose_scenario(
                    store, "Хочу чувствовать твою заботу.", context=enabled
                )
            self.assertIsNotNone(started)
            with Store(directory) as store:
                self.assertIsNone(choose_scenario(store, "Устал от решений."))
            with Store(directory) as store:
                self.assertIsNone(choose_scenario(
                    store, "Устал от решений.",
                    context={**enabled, "distressed": True},
                ))

    def test_romantic_scenario_not_selected_without_opt_in(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder) / "data") as store:
                self.assertIsNone(choose_scenario(store, "Хочу чувствовать твою заботу."))


if __name__ == "__main__":
    unittest.main()
