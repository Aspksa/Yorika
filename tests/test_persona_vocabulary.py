import tempfile
import unittest
from pathlib import Path

from backend.storage import Store
from backend.persona_growth import learn_reply, remove_reply, list_replies
from backend.persona_vocabulary import vocabulary_stats


class PersonaVocabularyTests(unittest.TestCase):
    def test_counts_unique_vocabulary_and_updates_after_delete(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as store:
                self.assertEqual(vocabulary_stats(store)["unique_words"], 0)
                text = "Йорика обсуждает необычные истории и предлагает творческие варианты решения."
                self.assertTrue(learn_reply(store, "поговорим", text))
                result = vocabulary_stats(store)
                self.assertEqual(result["replies"], 1)
                self.assertGreater(result["unique_words"], 4)
                self.assertTrue(any(e["word"] == "йорика" for e in result["frequent_words"]))
                item = list_replies(store)[0]
                remove_reply(store, item["id"])
                self.assertEqual(vocabulary_stats(store)["unique_words"], 0)

    def test_validates_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as store:
                with self.assertRaises(ValueError):
                    vocabulary_stats(store, limit=0)


if __name__ == "__main__":
    unittest.main()
