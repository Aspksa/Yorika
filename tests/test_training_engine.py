"""Training pipeline remains optional, consent-bound, and fail closed."""
import tempfile
import unittest
from pathlib import Path
from backend.storage import Store
from backend.learning_foundation import add_example
from backend.training_engine import dataset, train


class TrainingEngineTests(unittest.TestCase):
    def test_only_consented_examples_exported(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as db:
                add_example(db, prompt="Привет", answer="Здравствуй", consent=True)
                db.put("learning_examples", "untrusted", {"prompt": "секрет", "answer": "данные", "consent": False})
                db.put("secrets", "private", {"prompt": "не экспортировать", "answer": "секрет"})
                self.assertEqual(dataset(db), [("Привет", "Здравствуй")])

    def test_invalid_or_empty_training_fails_without_torch(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "model.pt"
            with self.assertRaises(ValueError):
                train([], output)
            with self.assertRaises(ValueError):
                train([("a", "b")], output, width=30, heads=8)
            with self.assertRaises(ValueError):
                train([("a", "b")], output, steps=0)
            self.assertFalse(output.exists())

    def test_dataset_limits_and_deduplication(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as db:
                add_example(db, prompt="План", answer="Ответ", consent=True)
                self.assertEqual(len(dataset(db)), 1)
                for limit in (0, True, 1001):
                    with self.assertRaises(ValueError):
                        dataset(db, limit=limit)


if __name__ == "__main__":
    unittest.main()
