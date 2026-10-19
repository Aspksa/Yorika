"""Versioned UTF-8 byte tokenizer: lossless Russian and arbitrary Unicode."""
import hashlib
import json

SPECIAL = ("<pad>", "<bos>", "<eos>", "<user>", "<assistant>")
VOCAB_SIZE = len(SPECIAL) + 256

def encode(text):
    if not isinstance(text, str):
        raise TypeError("text must be str")
    return [len(SPECIAL) + value for value in text.encode("utf-8")]

def decode(ids):
    if any(type(x) is not int or not len(SPECIAL) <= x < VOCAB_SIZE for x in ids):
        raise ValueError("Not a sequence of byte tokens")
    return bytes(x - len(SPECIAL) for x in ids).decode("utf-8")

def encode_dialogue(prompt, answer, *, include_eos=True):
    return ([1, 3] + encode(prompt) + [4] + encode(answer)
            + ([2] if include_eos else []))

def fingerprint():
    return hashlib.sha256(json.dumps({"version": 1, "special": SPECIAL, "bytes": 256},
                                      sort_keys=True).encode()).hexdigest()
