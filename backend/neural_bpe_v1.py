"""Deterministic train-only byte-pair encoder for Yorika research.

No implicit download, no corpus collection, and no change to the active brain.
This tokenizer is NOT compatible with language-v1 checkpoints.
"""
import hashlib
import heapq
import json
import re
from collections import Counter, defaultdict

SPECIAL = ("<pad>", "<bos>", "<eos>", "<user>", "<assistant>")
OFFSET = len(SPECIAL)
SCHEMA = "yorika-byte-bpe-v1"
MAX_MERGES = 4096


def _bytes(text):
    if not isinstance(text, str):
        raise TypeError("text must be str")
    return tuple(OFFSET + byte for byte in text.encode("utf-8"))


def train(texts, *, max_merges=256, min_frequency=2):
    """Learn merges exclusively from caller-supplied training strings.

    Caller must already filter consent and split train/validation/test.
    Returns an immutable JSON-compatible manifest; no disk writes.
    """
    if not isinstance(texts, (list, tuple)) or not texts:
        raise ValueError("Nonempty training strings required")
    if type(max_merges) is not int or not 0 <= max_merges <= MAX_MERGES:
        raise ValueError("Invalid merge budget")
    if type(min_frequency) is not int or not 2 <= min_frequency <= 1000000:
        raise ValueError("Invalid minimum frequency")
    if len(texts) > 100000 or any(not isinstance(t, str) or not t or len(t) > 20000 for t in texts):
        raise ValueError("Invalid training texts")
    sequences = [list(_bytes(t)) for t in texts]
    merges = []
    for _ in range(max_merges):
        counts = Counter()
        for row in sequences:
            counts.update(zip(row, row[1:]))
        if not counts:
            break
        best = min(counts, key=lambda pair: (-counts[pair], pair))
        if counts[best] < min_frequency:
            break
        token = OFFSET + 256 + len(merges)
        merges.append([best[0], best[1]])
        sequences = [_merge(row, best, token) for row in sequences]
    manifest = {"schema": SCHEMA, "special": list(SPECIAL), "merges": merges}
    manifest["sha256"] = _digest(manifest)
    return manifest


WORD = re.compile(r" ?[^\s]+|\s+")


def train_words(texts, *, max_merges=1024, min_frequency=2):
    """Same manifest as train(), learned over word counts so thousands of merges take seconds.

    Merges are learned inside words (a leading space belongs to the word), which is how large
    vocabularies are usually fitted; encode() and decode() are unchanged.
    """
    if not isinstance(texts, (list, tuple)) or not texts:
        raise ValueError("Nonempty training strings required")
    if type(max_merges) is not int or not 0 <= max_merges <= MAX_MERGES:
        raise ValueError("Invalid merge budget")
    if type(min_frequency) is not int or not 2 <= min_frequency <= 1000000:
        raise ValueError("Invalid minimum frequency")
    if len(texts) > 100000 or any(not isinstance(t, str) or not t or len(t) > 20000 for t in texts):
        raise ValueError("Invalid training texts")
    freq = Counter(w for t in texts for w in WORD.findall(t))
    words = [list(_bytes(w)) for w in freq]
    counts = [freq[w] for w in freq]
    pairs, where = Counter(), defaultdict(set)
    for k, row in enumerate(words):
        for pair in zip(row, row[1:]):
            pairs[pair] += counts[k]
            where[pair].add(k)
    heap = [(-n, pair) for pair, n in pairs.items()]
    heapq.heapify(heap)
    merges = []
    while len(merges) < max_merges and heap:
        n, best = heapq.heappop(heap)
        if pairs.get(best, 0) != -n:
            continue  # stale entry; the current count is elsewhere in the heap
        if -n < min_frequency:
            break
        token = OFFSET + 256 + len(merges)
        merges.append([best[0], best[1]])
        touched = Counter()
        for k in list(where.pop(best, ())):
            row = words[k]
            for pair in zip(row, row[1:]):
                pairs[pair] -= counts[k]
                touched[pair] += 0
                where[pair].discard(k)
            row = words[k] = _merge(row, best, token)
            for pair in zip(row, row[1:]):
                pairs[pair] += counts[k]
                touched[pair] += 0
                where[pair].add(k)
        pairs.pop(best, None)
        for pair in touched:
            if pairs.get(pair, 0) > 0:
                heapq.heappush(heap, (-pairs[pair], pair))
            else:
                pairs.pop(pair, None)
    manifest = {"schema": SCHEMA, "special": list(SPECIAL), "merges": merges}
    manifest["sha256"] = _digest(manifest)
    return manifest


def _merge(row, pair, token):
    result = []
    i = 0
    while i < len(row):
        if i + 1 < len(row) and (row[i], row[i + 1]) == tuple(pair):
            result.append(token)
            i += 2
        else:
            result.append(row[i])
            i += 1
    return result


def _digest(manifest):
    payload = {key: manifest[key] for key in ("schema", "special", "merges")}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def validate(manifest):
    if not isinstance(manifest, dict) or set(manifest) != {"schema", "special", "merges", "sha256"}:
        raise ValueError("Invalid BPE manifest")
    if manifest["schema"] != SCHEMA or manifest["special"] != list(SPECIAL):
        raise ValueError("Unsupported tokenizer")
    merges = manifest["merges"]
    if not isinstance(merges, list) or len(merges) > MAX_MERGES:
        raise ValueError("Invalid merges")
    for i, pair in enumerate(merges):
        ceiling = OFFSET + 256 + i
        if (not isinstance(pair, list) or len(pair) != 2
                or any(type(token) is not int or not OFFSET <= token < ceiling for token in pair)):
            raise ValueError("Invalid merge token reference")
    if not isinstance(manifest["sha256"], str) or manifest["sha256"] != _digest(manifest):
        raise ValueError("Tokenizer checksum mismatch")
    return True


_RANKS = {}


def _ranks(manifest):
    key = manifest.get("sha256") if isinstance(manifest, dict) else None
    if key not in _RANKS:
        validate(manifest)
        if len(_RANKS) > 16:
            _RANKS.clear()
        _RANKS[key] = {tuple(pair): i for i, pair in enumerate(manifest["merges"])}
    return _RANKS[key]


def encode(text, manifest):
    """Applies merges in learned order. Merging the lowest-ranked pair present each time gives the
    same tokens as one pass per merge, but costs the text length instead of the merge count."""
    ranks = _ranks(manifest)
    row = list(_bytes(text))
    while len(row) > 1:
        rank = min((ranks.get(pair, 1 << 30) for pair in zip(row, row[1:])), default=1 << 30)
        if rank == 1 << 30:
            break
        row = _merge(row, manifest["merges"][rank], OFFSET + 256 + rank)
    return row


def decode(tokens, manifest):
    validate(manifest)
    if not isinstance(tokens, (list, tuple)):
        raise ValueError("Invalid token list")
    expansions = [bytes([i]) for i in range(256)]
    for left, right in manifest["merges"]:
        expansions.append(expansions[left - OFFSET] + expansions[right - OFFSET])
    if any(type(t) is not int or not OFFSET <= t < OFFSET + len(expansions) for t in tokens):
        raise ValueError("Invalid text token")
    return b"".join(expansions[t - OFFSET] for t in tokens).decode("utf-8")
