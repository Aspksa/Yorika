"""Safety and forwarding checks for own-brain weight continuation."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend.neural_resume import resume_training


class ResumeTests(unittest.TestCase):
    def test_missing_and_existing_files_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "old.pt"
            dest = Path(folder) / "new.pt"
            with self.assertRaises(ValueError):
                resume_training([], source, dest)
            source.write_bytes(b"fixture")
            with self.assertRaises(FileExistsError):
                resume_training([], source, source)
            dest.write_bytes(b"fixture")
            with self.assertRaises(FileExistsError):
                resume_training([], source, dest)

    def test_strict_step_limits(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "old.pt"
            source.write_bytes(b"fixture")
            for value in (0, -1, 10001, True):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    resume_training([], source, Path(folder) / "new.pt", additional_steps=value)


if __name__ == "__main__":
    unittest.main()
