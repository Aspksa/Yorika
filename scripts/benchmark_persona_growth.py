"""Repeatable local stress probe of Yorika's persona-growth SQLite index."""
import argparse
import tempfile
import time
from pathlib import Path
from backend.storage import Store
from backend.persona_growth import learn_reply, stats


def run(count=10000):
    with tempfile.TemporaryDirectory() as directory:
        with Store(Path(directory)) as store:
            start = time.perf_counter()
            accepted = 0
            for i in range(count):
                reply = f"Разговор номер {i} предлагает осмысленный уникальный путь работы с задачей {i}."
                accepted += bool(learn_reply(store, "поговорим", reply))
            elapsed = time.perf_counter() - start
            return {"requested": count, "accepted": accepted,
                    "stored": stats(store)["count"], "seconds": round(elapsed, 3)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=10000)
    args = parser.parse_args()
    if not 1 <= args.count <= 100000:
        parser.error("count must be from 1 to 100000")
    print(run(args.count))
