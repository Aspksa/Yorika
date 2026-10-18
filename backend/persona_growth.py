"""Safely maintain a growing, locally stored library of style examples.

These are untrusted examples, not model training data or executable prompts.
The similarity filter is a lexical heuristic, not semantic equivalence detection.
"""
import json
import re
from backend.persona_bank import KEYWORDS, category_for_query, canonical, fingerprint
from backend.storage import utc_now

NAMESPACE = "persona_generated"
SETTINGS_NS = "persona_settings"
SETTINGS_ID = "growth.v1"
MAX_REPLY = 2000
MIN_REPLY = 32
SENSITIVE = re.compile(
    r"(?i)(?:api[_ -]?key|bearer\s+\S+|sk-[a-z0-9]{10,}|"
    r"пароль\s*[:=]|password\s*[:=]|"
    r"[\w.+-]+@[\w.-]+\.[a-z]{2,}|"
    r"https?://\S+|"
    r"(?:\+?\d[\d ()-]{8,}\d))"
)
ROLE = re.compile(r"(?im)^\s*(?:system|developer|assistant|user)\s*:")
REJECTION = re.compile(r"(?i)(?:не могу помочь|не удалось получить ответ|ошибка сервера|cloud\.ru недоступен)")


def settings(store):
    row = store.connection.execute(
        "SELECT payload FROM records WHERE namespace=? AND record_id=?",
        (SETTINGS_NS, SETTINGS_ID),
    ).fetchone()
    if not row:
        return {"enabled": True}
    value = json.loads(row[0])
    return {"enabled": value.get("enabled") is True}


def set_enabled(store, enabled):
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be a boolean")
    with store.connection:
        store.connection.execute(
            "INSERT INTO records(namespace,record_id,payload,updated_at) VALUES(?,?,?,?) "
            "ON CONFLICT(namespace,record_id) DO UPDATE SET "
            "payload=excluded.payload,updated_at=excluded.updated_at",
            (SETTINGS_NS, SETTINGS_ID, json.dumps({"enabled": enabled}), utc_now()),
        )
    return settings(store)


def stats(store):
    count = store.connection.execute(
        "SELECT COUNT(*) FROM records WHERE namespace=?", (NAMESPACE,)
    ).fetchone()[0]
    return {"count": count, **settings(store)}


def _index_exists(db):
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                      "AND name='persona_growth_indexed'").fetchone() is not None


def remove_reply(store, reply_id):
    if not isinstance(reply_id, str) or not re.fullmatch(r"[0-9a-f]{64}", reply_id):
        raise ValueError("Invalid reply ID")
    with store.connection:
        changed = store.connection.execute(
            "DELETE FROM records WHERE namespace=? AND record_id=?",
            (NAMESPACE, reply_id),
        ).rowcount
        store.connection.execute("DELETE FROM persona_growth_words WHERE reply_id=?", (reply_id,)) if _index_exists(store.connection) else None
        store.connection.execute("DELETE FROM persona_growth_indexed WHERE reply_id=?", (reply_id,)) if _index_exists(store.connection) else None
    return {"deleted": bool(changed)}


def list_replies(store, limit=20):
    limit = max(1, min(int(limit), 100))
    rows = store.connection.execute(
        "SELECT record_id,payload FROM records WHERE namespace=? "
        "ORDER BY updated_at DESC LIMIT ?", (NAMESPACE, limit)
    ).fetchall()
    result = []
    for record_id, payload in rows:
        try:
            value = json.loads(payload)
            if isinstance(value.get("text"), str):
                result.append({"id": record_id, "category_id": value.get("category_id"),
                               "text": value["text"]})
        except (TypeError, ValueError, AttributeError):
            continue
    return result


def _words(value):
    return {w for w in canonical(value).split() if len(w) > 3}


def _near_duplicate(a, b):
    left, right = _words(a), _words(b)
    return bool(left and right and len(left & right) / len(left | right) >= 0.78)


def _ensure_index(db):
    """Sidecar inverted index, rebuilt once for pre-existing records."""
    db.execute("CREATE TABLE IF NOT EXISTS persona_growth_words ("
               "word TEXT NOT NULL, category TEXT NOT NULL, reply_id TEXT NOT NULL, "
               "PRIMARY KEY(word, category, reply_id)) WITHOUT ROWID")
    db.execute("CREATE INDEX IF NOT EXISTS idx_persona_growth_reply "
               "ON persona_growth_words(reply_id)")
    db.execute("CREATE TABLE IF NOT EXISTS persona_growth_indexed ("
               "reply_id TEXT PRIMARY KEY)")
    # Incremental backfill makes upgrades safe for existing installations.
    rows = db.execute(
        "SELECT record_id,payload FROM records WHERE namespace=? AND record_id NOT IN "
        "(SELECT reply_id FROM persona_growth_indexed)", (NAMESPACE,)
    ).fetchall()
    for reply_id, raw in rows:
        try:
            entry = json.loads(raw)
            category = entry["category_id"]
            words = _words(entry["text"])
        except (ValueError, TypeError, KeyError, AttributeError):
            words, category = set(), ""
        for word in words:
            db.execute("INSERT OR IGNORE INTO persona_growth_words VALUES(?,?,?)",
                       (word, category, reply_id))
        db.execute("INSERT OR IGNORE INTO persona_growth_indexed VALUES(?)", (reply_id,))


def learn_reply(store, query, response):
    if not isinstance(query, str) or not isinstance(response, str):
        return False
    text = response.strip()
    if (not MIN_REPLY <= len(text) <= MAX_REPLY or
            SENSITIVE.search(text) or SENSITIVE.search(query) or
            ROLE.search(text) or REJECTION.search(text)):
        return False
    fp = fingerprint(text)
    category = category_for_query(query, {item[0] for item in KEYWORDS} | {"listening"})
    db = store.connection
    if db.in_transaction:
        raise RuntimeError("Persona growth requires a separate transaction")
    db.execute("BEGIN IMMEDIATE")
    try:
        if not settings(store)["enabled"]:
            db.rollback()
            return False
        _ensure_index(db)
        words = _words(text)
        if not words:
            db.rollback()
            return False
        # Candidate records share at least one normalized word with this category.
        placeholders = ",".join("?" for _ in words)
        rows = db.execute(
            "SELECT DISTINCT r.record_id,r.payload FROM persona_growth_words w "
            "JOIN records r ON r.record_id=w.reply_id AND r.namespace=? "
            "WHERE w.category=? AND w.word IN (" + placeholders + ")",
            (NAMESPACE, category, *sorted(words)),
        ).fetchall()
        for old_id, raw in rows:
            if old_id == fp:
                db.rollback()
                return False
            try:
                old = json.loads(raw)
            except (ValueError, TypeError):
                continue
            if old.get("category_id") == category and _near_duplicate(text, old.get("text", "")):
                db.rollback()
                return False
        db.execute(
            "INSERT INTO records(namespace,record_id,payload,updated_at) VALUES(?,?,?,?)",
            (NAMESPACE, fp, json.dumps({"text": text, "category_id": category},
                                       ensure_ascii=False), utc_now()),
        )
        for word in words:
            db.execute("INSERT OR IGNORE INTO persona_growth_words VALUES(?,?,?)",
                       (word, category, fp))
        db.execute("INSERT OR IGNORE INTO persona_growth_indexed VALUES(?)", (fp,))
        db.commit()
        return True
    except BaseException:
        db.rollback()
        raise


def generated_example(store, query):
    if not settings(store)["enabled"]:
        return None
    category = category_for_query(query, {item[0] for item in KEYWORDS} | {"listening"})
    # Sample across the whole category, not just the 200 newest replies.
    rows = store.connection.execute(
        "SELECT payload FROM records WHERE namespace=? "
        "AND json_extract(payload, '$.category_id')=? "
        "ORDER BY RANDOM() LIMIT 1",
        (NAMESPACE, category),
    ).fetchall()
    for (raw,) in rows:
        try:
            value = json.loads(raw)
        except (ValueError, TypeError):
            continue
        if value.get("category_id") == category and isinstance(value.get("text"), str):
            return value["text"]
    return None
