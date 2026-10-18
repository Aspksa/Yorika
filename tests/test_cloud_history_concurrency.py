import threading
import tempfile
import unittest
from pathlib import Path

from backend.cloud_ru_history import load_history, save_turn
from backend.storage import Store


class CloudHistoryConcurrencyTests(unittest.TestCase):
    def test_concurrent_writers_keep_all_bounded_turns(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            barrier = threading.Barrier(4)
            errors = []

            def worker(i):
                try:
                    with Store(directory) as store:
                        barrier.wait(timeout=10)
                        save_turn(store, f"вопрос {i}", f"ответ {i}", "thread_A")
                except BaseException as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=20)
            self.assertFalse(errors)
            self.assertTrue(all(not thread.is_alive() for thread in threads))
            with Store(directory) as store:
                entries = load_history(store, "thread_A")
                self.assertEqual(len(entries), 8)
                self.assertEqual({e["content"] for e in entries},
                                 {f"вопрос {i}" for i in range(4)} |
                                 {f"ответ {i}" for i in range(4)})

    def test_separate_threads_still_isolated(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as store:
                save_turn(store, "первый", "ответ", "threadA")
                save_turn(store, "второй", "ответ", "threadB")
                self.assertEqual(load_history(store, "threadA")[0]["content"], "первый")


if __name__ == "__main__":
    unittest.main()
