import tempfile
import unittest
from pathlib import Path

from backend.persona_growth import learn_reply, generated_example
from backend.storage import Store


class PersonaGrowthTests(unittest.TestCase):
    def test_unique_replies_survive_restart(self):
        text = "Я рада продолжить разговор и помочь вам разобраться в этом вопросе."
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            with Store(path) as store:
                self.assertTrue(learn_reply(store, "Давай поговорим", text))
                self.assertFalse(learn_reply(store, "Давай поговорим", text))
                self.assertFalse(learn_reply(store, "Давай поговорим", "Мой хозяин, " + text))
            with Store(path) as store:
                self.assertEqual(generated_example(store, "Поговорим"), text)

    def test_short_and_secret_responses_not_learned(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as store:
                self.assertFalse(learn_reply(store, "Привет", "Привет!"))
                self.assertFalse(learn_reply(store, "Привет", "api_key: " + "A" * 60))
                self.assertIsNone(generated_example(store, "Привет"))


if __name__ == "__main__":
    unittest.main()
