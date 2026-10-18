import json
import tempfile
import unittest
from pathlib import Path

from backend.storage import Store
from backend.persona_growth import learn_reply, remove_reply, stats
from backend.persona_bank import fingerprint
from backend.storage import utc_now


class PersonaGrowthIndexTests(unittest.TestCase):
    def test_preexisting_records_are_backfilled_and_compared(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as db:
                original = "Я помогу вам внимательно разобрать эту непростую задачу по шагам."
                db.connection.execute(
                    "INSERT INTO records(namespace,record_id,payload,updated_at) VALUES(?,?,?,?)",
                    ("persona_generated", fingerprint(original),
                     json.dumps({"text": original, "category_id": "listening"}), utc_now()))
                db.connection.commit()
                self.assertFalse(learn_reply(db, "поговорим", original.replace(".", "!")))
                self.assertEqual(stats(db)["count"], 1)

    def test_delete_removes_index_and_allows_relearning(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as db:
                reply = "Сегодня мы можем внимательно обсудить предложенный вами вариант решения."
                self.assertTrue(learn_reply(db, "поговорим", reply))
                self.assertTrue(remove_reply(db, fingerprint(reply))["deleted"])
                self.assertTrue(learn_reply(db, "поговорим", reply))
                count = db.connection.execute(
                    "SELECT COUNT(*) FROM persona_growth_words WHERE reply_id=?",
                    (fingerprint(reply),)).fetchone()[0]
                self.assertGreater(count, 0)


if __name__ == "__main__":
    unittest.main()
