import tempfile
import unittest
from pathlib import Path
from backend.storage import Store
from backend.persona_growth import learn_reply, stats
from scripts.sqlite_backup import create_verified_backup, verify_snapshot


class PersonaReliabilityTests(unittest.TestCase):
    def test_backfill_multiple_batches_and_preserve_dedup(self):
        with tempfile.TemporaryDirectory() as temp:
            with Store(Path(temp)) as db:
                for i in range(260):
                    text = f"Вариант {i} имеет особенное содержание и уникальное понятие {i}."
                    db.connection.execute(
                        "INSERT INTO records(namespace,record_id,payload,updated_at) VALUES(?,?,?,?)",
                        ("persona_generated", f"{i:064x}", 
                         __import__("json").dumps({"text": text, "category_id": "listening"}),
                         "2026-10-19T00:00:00Z"))
                db.connection.commit()
                self.assertFalse(learn_reply(db, "поговорим",
                    "Вариант 259 имеет особенное содержание и уникальное понятие 259!"))
                count = db.connection.execute("SELECT COUNT(*) FROM persona_growth_indexed").fetchone()[0]
                self.assertEqual(count, 260)

    def test_verified_backup_keeps_persona(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            with Store(directory / "live") as db:
                self.assertTrue(learn_reply(db, "поговорим",
                    "Йорика рассказывает новую историю и предлагает изучить интересную идею вместе."))
                source = db.path
            destination = directory / "snapshot.sqlite3"
            report = create_verified_backup(source, destination)
            self.assertEqual(report["integrity"], "ok")
            self.assertEqual(verify_snapshot(destination)["integrity"], "ok")
            with Store(directory / "live") as db:
                self.assertEqual(stats(db)["count"], 1)


if __name__ == "__main__":
    unittest.main()
