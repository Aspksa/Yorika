import tempfile
import unittest
from pathlib import Path
from backend.storage import Store
from backend.persona_auto import reserve, INTERVAL
from backend.persona_creativity import store_scenario, branching_hint
from backend.persona_growth import set_enabled


class AutomaticCreativeExpansionTests(unittest.TestCase):
    def test_expansion_every_twenty_eligible_turns(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as store:
                results = [reserve(store, "Давай обсудим планы на завтра подробно")
                           for _ in range(INTERVAL * 2)]
                self.assertEqual([i + 1 for i, flag in enumerate(results) if flag],
                                 [INTERVAL, INTERVAL * 2])

    def test_disable_growth_disables_automation(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as store:
                set_enabled(store, False)
                self.assertFalse(reserve(store, "Обсудим разные идеи на завтра"))

    def test_generated_branch_continues_only_in_own_thread(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as store:
                seed = "Хочу поговорить о планах на завтра"
                reply = "Давайте подумаем о завтрашних планах и выберем самый приятный вариант."
                self.assertTrue(store_scenario(store, seed, reply))
                self.assertEqual(branching_hint(store, seed, "first"), reply)
                self.assertEqual(branching_hint(store, "планы на завтра обсудим подробнее", "first"), reply)
                self.assertIsNone(branching_hint(store, "совершенно другой разговор", "first"))
                self.assertEqual(branching_hint(store, seed, "second"), reply)


if __name__ == "__main__":
    unittest.main()
