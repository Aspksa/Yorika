"""Standard-library tests for the experimental train-only byte BPE."""
import copy
import unittest

from backend.neural_bpe_v1 import train, encode, decode, validate, OFFSET


class BpeTests(unittest.TestCase):
    def setUp(self):
        self.train_only = ["Привет, мир!"] * 6 + ["Привет, Юрика!"] * 5
        self.manifest = train(self.train_only, max_merges=48)

    def test_roundtrip_unicode_and_unknown_input(self):
        for text in ("Привет, Юрика!", "кошка 🦊", "a\x00b", "中文 café", "", "\n"):
            self.assertEqual(decode(encode(text, self.manifest), self.manifest), text)

    def test_determinism(self):
        self.assertEqual(self.manifest, train(self.train_only, max_merges=48))

    def test_compression_on_training_distribution(self):
        text = "Привет, мир!"
        self.assertLess(len(encode(text, self.manifest)), len(text.encode("utf-8")))

    def test_holdout_not_used_by_training(self):
        before = train(self.train_only, max_merges=25)
        untouched_holdout = "Секретный текст только для проверки 🦊"
        self.assertEqual(before, train(self.train_only, max_merges=25))
        self.assertEqual(decode(encode(untouched_holdout, before), before), untouched_holdout)

    def test_tampering_is_rejected(self):
        altered = copy.deepcopy(self.manifest)
        altered["merges"][0][0] = OFFSET + 255
        with self.assertRaises(ValueError):
            validate(altered)

    def test_invalid_references_rejected(self):
        altered = copy.deepcopy(self.manifest)
        altered["merges"][0] = [OFFSET + 256, OFFSET + 1]
        with self.assertRaises(ValueError):
            validate(altered)

    def test_wrong_input_and_budget_rejected(self):
        for texts in ([], ["ok", 3], [""]):
            with self.assertRaises(ValueError):
                train(texts)
        with self.assertRaises(ValueError):
            train(["ok"], max_merges=4097)
        with self.assertRaises(ValueError):
            train(["ok"], min_frequency=1)

    def test_no_special_tokens_in_raw_text(self):
        with self.assertRaises(ValueError):
            decode([0], self.manifest)


if __name__ == "__main__":
    unittest.main()
