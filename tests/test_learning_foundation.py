"""Learning Foundation release gates must never approve regressions silently."""
import tempfile
import unittest
from pathlib import Path
from backend.storage import Store
from backend import learning_foundation as learning


class LearningFoundationTests(unittest.TestCase):
    def test_consent_and_reopening(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            with Store(root) as db:
                with self.assertRaises(PermissionError):
                    learning.add_example(db, prompt="Привет", answer="Здравствуйте")
                one = learning.add_example(db, prompt="Привет", answer="Здравствуйте", consent=True)
                two = learning.add_example(db, prompt="Привет", answer="Здравствуйте", consent=True)
                self.assertEqual(one, two)
            with Store(root) as db:
                self.assertEqual(len(db.list_records("learning_examples")), 1)

    def test_evaluation_manual_gate_and_rollback(self):
        with tempfile.TemporaryDirectory() as path:
            with Store(Path(path)) as db:
                learning.evaluate(db, "model-v1", quality=0.95, regressions=1, tests=50)
                with self.assertRaises(ValueError):
                    learning.promote(db, "model-v1", approved=True)
                learning.evaluate(db, "model-v1", quality=0.95, regressions=0, tests=50)
                with self.assertRaises(PermissionError):
                    learning.promote(db, "model-v1")
                self.assertEqual(learning.promote(db, "model-v1", approved=True)["candidate"], "model-v1")
                with self.assertRaises(PermissionError):
                    learning.rollback(db)
                self.assertTrue(learning.rollback(db, approved=True))
                self.assertIsNone(db.get("learning_settings", "active"))

    def test_invalid_metrics_rejected(self):
        with tempfile.TemporaryDirectory() as path:
            with Store(Path(path)) as db:
                for quality in (float("nan"), float("inf"), -1, 2, True):
                    with self.subTest(quality=quality), self.assertRaises(ValueError):
                        learning.evaluate(db, "candidate", quality=quality, regressions=0, tests=10)
                with self.assertRaises(ValueError):
                    learning.evaluate(db, "candidate", quality=0.9, regressions=0, tests=9)


if __name__ == "__main__":
    unittest.main()
