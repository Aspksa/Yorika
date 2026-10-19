import tempfile
import unittest
from pathlib import Path
from backend.neural_language_bpe_v2 import train_language, load_language, heldout_loss, generate_language


class LanguageBpeV2Tests(unittest.TestCase):
    def test_training_checkpoint_and_heldout(self):
        try:
            import torch
        except ImportError:
            self.skipTest("PyTorch optional")
        train = [("Привет, мир", "Здравствуйте, мир")] * 3
        heldout = [("Как дела?", "Хорошо.")]
        with tempfile.TemporaryDirectory() as d:
            checkpoint = Path(d) / "brain.pt"
            result = train_language(train, checkpoint, steps=2, width=32, heads=4, context=128, max_merges=16)
            self.assertEqual(result["steps"], 2)
            _, data = load_language(checkpoint)
            self.assertEqual(data["schema"], "yorika-language-bpe-v2")
            self.assertEqual(data["vocab_size"], 261 + len(data["tokenizer"]["merges"]))
            self.assertGreater(heldout_loss(checkpoint, heldout), 0)
            answer = generate_language(checkpoint, "Привет", max_tokens=3)
            self.assertEqual(answer["engine"], "yorika-language-bpe-v2")

    def test_old_checkpoint_not_accepted(self):
        try:
            import torch
        except ImportError:
            self.skipTest("PyTorch optional")
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "old.pt"
            torch.save({"schema": "yorika-language-v1"}, path)
            with self.assertRaises(ValueError):
                load_language(path)


if __name__ == "__main__":
    unittest.main()
