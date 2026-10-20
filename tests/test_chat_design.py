"""The new chat: ratings given right in the chat go into «Опыт», and the panel keeps its contracts."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import self_learning as sl


class ChatRatingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = os.environ.get("YORIKA_HOME")
        os.environ["YORIKA_HOME"] = self.temp.name

    def tearDown(self):
        if self.old is None:
            os.environ.pop("YORIKA_HOME", None)
        else:
            os.environ["YORIKA_HOME"] = self.old
        self.temp.cleanup()

    def test_thumb_up_saves_the_pair_as_an_example_without_collection(self):
        self.assertFalse(sl.status()["collect"])
        out = sl.rate_chat("Как тебя зовут?", 1000, "Меня зовут Yorika.", "up")
        self.assertEqual(out["item"]["rating"], "up")
        self.assertEqual(out["item"]["source"], "yorika-chat")
        self.assertEqual(out["counts"]["up"], 1)
        # Rating the same pair again changes it, it does not duplicate it.
        out = sl.rate_chat("Как тебя зовут?", 1000, "Меня зовут Yorika.", "down", "Я Yorika, твоя помощница.")
        self.assertEqual(out["counts"]["total"], 1)
        self.assertEqual(out["item"]["correction"], "Я Yorika, твоя помощница.")

    def test_a_new_answer_to_the_same_question_replaces_the_old_one(self):
        sl.rate_chat("Сколько будет 2+2?", 5, "Пять.", "down")
        out = sl.rate_chat("Сколько будет 2+2?", 5, "Четыре.", "up")
        self.assertEqual((out["item"]["answer"], out["item"]["rating"], out["counts"]["total"]), ("Четыре.", "up", 1))

    def test_errors_stopped_answers_and_secrets_cannot_be_rated(self):
        for answer in ("Языковая модель не ответила: нет ключа.", "Не удалось получить ответ: сеть",
                       "Начало ответа\n\n(ответ остановлен)", "Пишите на me@example.com"):
            with self.assertRaises(ValueError):
                sl.rate_chat("Вопрос", 1, answer, "up")
        with self.assertRaises(ValueError):
            sl.rate_chat("Вопрос", 1, "Ответ.", "maybe")
        # Errors are no longer collected as examples either.
        self.assertEqual(sl.chat_pairs([{"from": "me", "text": "Привет", "ts": 1},
                                        {"from": "bot", "text": "Не удалось получить ответ: сеть", "ts": 2}]), [])


class ChatPanelTests(unittest.TestCase):
    def test_panel_contracts(self):
        js = (ROOT / "www/avatar.js").read_text(encoding="utf-8")
        css = (ROOT / "www/avatar.css").read_text(encoding="utf-8")
        for needle in ("setResponder", "/api/chat/history", '"yorika.chat.view"', "/api/training/sl-chat-rate",
                       "AbortController", "responder(text,history.slice()", "innerHTML='<svg", "Alt+Y"):
            self.assertIn(needle, js)
        # Message text is never put into HTML: the formatter builds text nodes.
        self.assertNotIn("innerHTML=m.text", js)
        self.assertNotIn("innerHTML=text", js)
        for needle in (".yc-wide", ".yc-full", ".yc-code", ".yc-actions", "prefers-reduced-motion"):
            self.assertIn(needle, css)
        tray = (ROOT / "scripts/yorika-tray.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("|sl-chat-rate|", tray)
        cli = (ROOT / "scripts/training-center.py").read_text(encoding="utf-8")
        self.assertIn('"sl-chat-rate"', cli)
        if shutil.which("node"):
            process = subprocess.run(["node", "--check", str(ROOT / "www/avatar.js")], capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)


if __name__ == "__main__":
    unittest.main()
