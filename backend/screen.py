"""Help with what is on the screen, only when the owner presses the button.

Windows reads the text on the screen with its built-in OCR (scripts/screen-ocr.ps1); the picture
lives in a temp file for a few seconds and is deleted. Yorika answers about that text with her
own model. Nothing is saved: neither the picture, nor the text, nor the answer. She reads text,
she does not see pictures, buttons or colours, and a small model can easily be wrong about it.
"""
import json
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "screen-ocr.ps1"
MAX_TEXT = 1500
MAX_PROMPT = 400  # a small model's context is short: the most telling lines go into the question
KEYWORDS = ("ошибк", "error", "exception", "failed", "не удалось", "warning", "внимание", "traceback")


def focus(text, limit=MAX_PROMPT):
    """Error-looking lines first, then the last lines of the screen, up to `limit` characters."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    first = [l for l in lines if any(k in l.casefold() for k in KEYWORDS)]
    chosen, size = [], 0
    for line in first + [l for l in reversed(lines) if l not in first]:
        if size + len(line) > limit:
            break
        chosen.append(line)
        size += len(line) + 3
    return " / ".join(chosen)


def read_text(runner=None):
    if os.name != "nt" and runner is None:
        raise ValueError("Чтение экрана работает только в Windows")
    run = runner or (lambda: subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT)], capture_output=True,
        timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.decode("utf-8", "replace"))
    try:
        result = json.loads(run().strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise ValueError("Windows не вернул текст экрана") from None
    if result.get("error"):
        raise ValueError("Не удалось прочитать экран: %s" % str(result["error"])[:120])
    return (result.get("text") or "").strip()


def help_with(question, runner=None, loaded=None):
    """Reads the screen once and answers the question about its text."""
    from backend import brain, mind
    from backend import self_learning as sl
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= 300:
        raise ValueError("Вопрос от 1 до 300 символов")
    text = read_text(runner)
    if not text:
        return {"text": "", "answer": "На экране я не нашла текста.", "lines": 0}
    if loaded is None:
        checkpoint = sl._scoring_checkpoint()
        if checkpoint is None:
            return {"text": text[:MAX_TEXT], "answer": None, "lines": text.count("\n") + 1,
                    "note": "Своей обученной версии пока нет: показываю только прочитанный текст"}
        loaded = brain.load(checkpoint)
    prompt = "На экране написано: «%s». %s" % (focus(text), question.strip())
    answer = brain.think(*loaded, prompt, drafts=3)["answer"]
    return {"text": text[:MAX_TEXT], "answer": mind.strip_thoughts(answer) or answer, "lines": text.count("\n") + 1,
            "note": "Ничего не сохранено. Я читаю только текст с экрана и могу ошибаться."}
