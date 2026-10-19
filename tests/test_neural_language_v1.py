"""Contract tests for versioned Unicode tokenizer and independent language evaluation."""
import tempfile
import unittest
from pathlib import Path
from backend.neural_tokenizer_v1 import encode, decode, encode_dialogue, fingerprint
from backend.neural_evaluation import split_examples


class LanguageV1Tests(unittest.TestCase):
    def test_russian_unicode_roundtrip(self):
        for value in ("Привет, Ёрика! 🦊", "Строка\nс новой строкой", "日本語", ""):
            self.assertEqual(decode(encode(value)), value)
        self.assertEqual(len(fingerprint()), 64)
        self.assertEqual(encode_dialogue("Привет", "Да")[-1], 2)

    def test_invalid_decode_rejected(self):
        for item in ([1], [-1], [999], [True]):
            with self.assertRaises(ValueError):
                decode(item)

    def test_holdout_is_disjoint(self):
        train, heldout = split_examples([(f"Вопрос {i}", f"Ответ {i}") for i in range(30)])
        self.assertFalse(set(train) & set(heldout))
        self.assertGreaterEqual(len(heldout), 5)


if __name__ == "__main__":
    unittest.main()
