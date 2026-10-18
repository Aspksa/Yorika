"""Grow Yorika's example bank with distinct Cloud.ru replies, without modifying the source pack.

Generated text is untrusted data and never becomes executable instructions.
"""
import json
import re

from backend.persona_bank import category_for_query, fingerprint, KEYWORDS
from backend.storage import utc_now

NAMESPACE = "persona_generated"
MAX_REPLY = 2000
MIN_REPLY = 32


def learn_reply(store, query, response):
    if not isinstance(query, str) or not isinstance(response, str):
        return False
    text = response.strip()
    if not MIN_REPLY <= len(text) <= MAX_REPLY:
        return False
    # Avoid learning diagnostics, secrets or instructions disguised as role directives.
    if re.search(r"(?i)(api[_ -]?key|bearer\s+|sk-[A-Za-z0-9]{10,}|пароль\s*[:=])", text):
        return False
    fp = fingerprint(text)
    category = category_for_query(query, {item[0] for item in KEYWORDS} | {"listening"})
    db = store.connection
    if db.in_transaction:
        raise RuntimeError("Persona growth requires a separate transaction")
    db.execute("BEGIN IMMEDIATE")
    try:
        exists = db.execute(
            "SELECT 1 FROM records WHERE namespace=? AND record_id=?",
            (NAMESPACE, fp),
        ).fetchone()
        if exists:
            db.rollback()
            return False
        value = json.dumps({"text": text, "category_id": category}, ensure_ascii=False)
        db.execute(
            "INSERT INTO records(namespace,record_id,payload,updated_at) VALUES(?,?,?,?)",
            (NAMESPACE, fp, value, utc_now()),
        )
        db.commit()
        return True
    except BaseException:
        db.rollback()
        raise


def generated_example(store, query):
    category = category_for_query(query, {item[0] for item in KEYWORDS} | {"listening"})
    rows = store.connection.execute(
        "SELECT payload FROM records WHERE namespace=? ORDER BY updated_at DESC LIMIT 200",
        (NAMESPACE,),
    ).fetchall()
    for row in rows:
        try:
            value = json.loads(row[0])
        except (ValueError, TypeError):
            continue
        if value.get("category_id") == category and isinstance(value.get("text"), str):
            return value["text"]
    return None
