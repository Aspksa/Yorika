import tempfile
import unittest
from pathlib import Path
from backend.storage import Store
from backend.persona_auto import reserve, INTERVAL
from backend.persona_growth import set_enabled


class AutomaticPersonaGrowthTests(unittest.TestCase):
    def test_expansion_runs_every_twenty_valid_turns(self):
        with tempfile.TemporaryDirectory() as root:
            with Store(Path(root)) as store:
                for i in range(1, INTERVAL):
                    self.assertFalse(reserve(store, "Поговорим о планах на завтра"))
                self.assertTrue(reserve(store, "Поговорим о планах на завтра"))
                self.assertFalse(reserve(store, "Поговорим о планах на завтра"))

    def test_respects_disabled_setting_and_sensitive_input(self):
        with tempfile.TemporaryDirectory() as root:
            with Store(Path(root)) as store:
                self.assertFalse(reserve(store, "user@example.com данные для разговора"))
                set_enabled(store, False)
                for _ in range(INTERVAL + 1):
                    self.assertFalse(reserve(store, "Поговорим о планах на завтра"))
                set_enabled(store, True)
                self.assertFalse(reserve(store, "Поговорим о планах на завтра"))


if __name__ == "__main__":
    unittest.main()
