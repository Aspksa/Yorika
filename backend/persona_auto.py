"""Reserve an automatic creative expansion once every 20 successful user turns.

Reservations are transactional; cloud calls run in a detached helper so normal
chat latency stays unchanged. The existing growth toggle disables this feature.
"""
import json
from backend.persona_growth import settings, SENSITIVE, ROLE
from backend.storage import utc_now

NAMESPACE = "persona_auto"
STATE = "periodic.v1"
INTERVAL = 20


def reserve(store, query):
    if not isinstance(query, str) or not 12 <= len(query) <= 300:
        return False
    if SENSITIVE.search(query) or ROLE.search(query):
        return False
    db = store.connection
    db.execute("BEGIN IMMEDIATE")
    try:
        if not settings(store)["enabled"]:
            db.rollback()
            return False
        row = db.execute("SELECT payload FROM records WHERE namespace=? AND record_id=?",
                         (NAMESPACE, STATE)).fetchone()
        count = json.loads(row[0])["count"] if row else 0
        count += 1
        db.execute("INSERT INTO records(namespace,record_id,payload,updated_at) "
                   "VALUES(?,?,?,?) ON CONFLICT(namespace,record_id) DO UPDATE SET "
                   "payload=excluded.payload,updated_at=excluded.updated_at",
                   (NAMESPACE, STATE, json.dumps({"count": count}), utc_now()))
        db.commit()
        return count % INTERVAL == 0
    except BaseException:
        db.rollback()
        raise
