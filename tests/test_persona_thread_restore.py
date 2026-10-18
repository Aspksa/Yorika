import tempfile
import unittest
from pathlib import Path
from backend.storage import Store
from backend.persona_dialogues import choose_scenario
from backend.cloud_ru_history import record_id
from scripts.sqlite_backup import create_verified_backup, verify_snapshot


class ScenarioIsolationRestoreTests(unittest.TestCase):
    def test_scenarios_are_isolated_by_thread(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as store:
                optin = {"adult_context": True, "romance_enabled": True}
                a = choose_scenario(store, "Хочу чувствовать твою заботу.",
                                    context=optin, conversation_id="thread_A")
                b = choose_scenario(store, "Хочу чувствовать твою заботу.",
                                    context=optin, conversation_id="thread_B")
                self.assertEqual(a["scenario_id"], b["scenario_id"])
                self.assertIsNone(choose_scenario(store, "Хочу чувствовать твою заботу.",
                                                  context=optin, conversation_id="thread_A"))
                self.assertRaises(ValueError, record_id, "../unsafe")

    def test_snapshot_can_be_restored_only_to_new_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with Store(root / "live") as store:
                source = store.path
                store.connection.execute(
                    "INSERT INTO records(namespace,record_id,payload,updated_at) VALUES(?,?,?,?)",
                    ("test", "one", '{"value":1}', "2026-10-19T00:00:00Z"))
                store.connection.commit()
            snapshot, restored = root / "saved.sqlite3", root / "restored.sqlite3"
            create_verified_backup(source, snapshot)
            create_verified_backup(snapshot, restored)
            self.assertEqual(verify_snapshot(restored)["integrity"], "ok")
            self.assertEqual(verify_snapshot(restored)["sha256"], verify_snapshot(snapshot)["sha256"])
            with self.assertRaises(FileExistsError):
                create_verified_backup(snapshot, restored)


if __name__ == "__main__":
    unittest.main()
