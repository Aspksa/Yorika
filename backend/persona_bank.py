"""Deterministic, persistent non-repeating examples from Yorika's persona pack.

Examples remain untrusted data for Cloud.ru; they never replace a generated answer.
Romantic and scene-gated examples require explicit opt-in context.
"""
import hashlib
import json
import re
import unicodedata

from backend.persona_profile import PACK_PATH
from backend.storage import utc_now

NAMESPACE = "persona_rotation"
RECORD_ID = "yorika.soul.ru.history.v1"
KEYWORDS = (
    ("gratitude", ("спасибо", "благодар", "благодарю")),
    ("greetings", ("привет", "здравствуй", "доброе утро", "добрый вечер", "с возвращением")),
    ("fatigue", ("устал", "устала", "нет сил", "вымотал")),
    ("sadness", ("груст", "печаль", "одинок", "тоскл")),
    ("anxiety", ("тревож", "волнуюсь", "боюсь", "страшно")),
    ("celebration", ("ура", "получилось", "победа", "достижение")),
    ("correction", ("ошибка", "неправильно", "исправь", "переделай")),
    ("planning", ("план", "дальше", "следующий шаг")),
    ("creativity", ("истори", "придумай", "творческ", "идея")),
    ("practical", ("код", "github", "файл", "установ", "скрипт", "программ")),
    ("listening", ("поговор", "расскажу", "поболта", "послушай")),
)


def canonical(text):
    value = unicodedata.normalize("NFKC", text).casefold().replace("ё", "е")
    value = re.sub(
        r"\b(?:мой\s+)?(?:(?:любимый|дорогой|родной)\s+)?(?:хозяин|господин)\b",
        "", value,
    )
    return " ".join(re.findall(r"[a-zа-я0-9]+", value))


def fingerprint(text):
    return hashlib.sha256(canonical(text).encode("utf-8")).hexdigest()


def category_for_query(query, available):
    lowered = query.casefold().replace("ё", "е")
    for category, phrases in KEYWORDS:
        if category in available and any(word in lowered for word in phrases):
            return category
    return "listening" if "listening" in available else "universal"


def eligible(reply, context):
    level = reply.get("min_romance_level", 0)
    if not isinstance(level, int) or level < 0 or level > 3:
        return False
    if level:
        if context.get("adult_context") is not True or context.get("romance_enabled") is not True:
            return False
        if level > context.get("romance_level", 0):
            return False
    if reply.get("scene_required") and context.get("scene_enabled") is not True:
        return False
    if context.get("distressed") is True and level >= 2:
        return False
    facts = context.get("facts", {})
    return isinstance(facts, dict) and all(facts.get(name) is True for name in reply.get("required_facts", []))


def choose_example(store, query, *, context=None, pack_path=None):
    """Atomically reserve one unused example in persistent SQLite; return None on exhaustion."""
    context = context or {}
    source = pack_path or PACK_PATH
    with open(source, encoding="utf-8") as stream:
        pack = json.load(stream)
    if pack.get("pack_id") != "yorika.soul.ru" or pack.get("schema_version") != "2.0.0":
        raise ValueError("Unsupported persona pack")
    replies = pack.get("replies", [])
    if len(replies) != 1024 or len(pack.get("categories", [])) != 52:
        raise ValueError("Incomplete persona pack")
    categories = {row["id"] for row in pack["categories"]}
    category = category_for_query(query, categories)
    candidates = [r for r in replies if r.get("category_id") == category
                  and isinstance(r.get("text"), str) and eligible(r, context)]
    if not candidates:
        return None
    db = store.connection
    if db.in_transaction:
        raise RuntimeError("Persona selection requires its own transaction")
    db.execute("BEGIN IMMEDIATE")
    try:
        row = db.execute(
            "SELECT payload FROM records WHERE namespace=? AND record_id=?",
            (NAMESPACE, RECORD_ID),
        ).fetchone()
        history = json.loads(row[0]) if row else {
            "seen_ids": [], "seen_fingerprints": [], "recent_openings": []
        }
        seen = set(history["seen_ids"])
        hashes = set(history["seen_fingerprints"])
        remaining = [r for r in candidates if r["id"] not in seen
                     and fingerprint(r["text"]) not in hashes]
        if not remaining:
            db.rollback()
            return None
        recent = history["recent_openings"][-8:]
        remaining.sort(key=lambda r: (r.get("opening_family", "") in recent, r["ordinal"]))
        selected = remaining[0]
        history["seen_ids"].append(selected["id"])
        history["seen_fingerprints"].append(fingerprint(selected["text"]))
        history["recent_openings"] = (history["recent_openings"] +
                                      [selected.get("opening_family", "")])[-32:]
        db.execute(
            "INSERT INTO records(namespace,record_id,payload,updated_at) VALUES(?,?,?,?) "
            "ON CONFLICT(namespace,record_id) DO UPDATE SET "
            "payload=excluded.payload,updated_at=excluded.updated_at",
            (NAMESPACE, RECORD_ID, json.dumps(history, ensure_ascii=False), utc_now()),
        )
        db.commit()
        return {"id": selected["id"], "text": selected["text"], "category_id": category}
    except BaseException:
        db.rollback()
        raise
