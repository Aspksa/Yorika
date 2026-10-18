"""Vocabulary statistics derived from approved generated persona replies.

Vocabulary is recomputed from accepted local replies to avoid duplicating private text.
"""
import collections
import json
import re

from backend.persona_bank import canonical

NAMESPACE = "persona_generated"
WORD = re.compile(r"[а-яa-z]{4,}", re.I)


def vocabulary_stats(store, *, limit=30):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    counts = collections.Counter()
    replies = 0
    cursor = store.connection.execute(
        "SELECT payload FROM records WHERE namespace=?", (NAMESPACE,)
    )
    for (payload,) in cursor:
        try:
            entry = json.loads(payload)
        except (ValueError, TypeError):
            continue
        if not isinstance(entry, dict) or not isinstance(entry.get("text"), str):
            continue
        replies += 1
        counts.update(set(WORD.findall(canonical(entry["text"]))))
    return {"replies": replies, "unique_words": len(counts),
            "frequent_words": [{"word": word, "replies": amount}
                               for word, amount in counts.most_common(limit)]}
