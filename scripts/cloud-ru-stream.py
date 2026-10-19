"""Bounded NDJSON gateway for Yorika Cloud.ru streaming."""
import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

MAX_REQUEST_BYTES = 5000
MAX_ANSWER_CHARS = 8000


def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def read_request(source):
    raw = source.read(MAX_REQUEST_BYTES + 1)
    if len(raw.encode("utf-8")) > MAX_REQUEST_BYTES:
        raise ValueError("Request too large")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Invalid request")
    query = data.get("query")
    if (not isinstance(query, str) or not query.strip() or
            len(query) > 3000 or len(query.encode("utf-8")) > 2048):
        raise ValueError("Invalid query")
    conversation_id = data.get("conversation_id")
    if conversation_id is not None and (
        not isinstance(conversation_id, str) or len(conversation_id) > 128
    ):
        raise ValueError("Invalid conversation identifier")
    return query, conversation_id


def main():
    query, conversation_id = read_request(sys.stdin)
    path = Path(__file__).with_name("cloud-ru-model.py")
    spec = importlib.util.spec_from_file_location("yorika_cloud_stream_model", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    delivered = 0

    def on_delta(chunk):
        nonlocal delivered
        if not isinstance(chunk, str):
            raise ValueError("Invalid model delta")
        delivered += len(chunk)
        if delivered > MAX_ANSWER_CHARS:
            raise ValueError("Model answer exceeds limit")
        emit({"type": "delta", "text": chunk})

    result = module.answer(
        query, conversation_id=conversation_id, stream=True, on_delta=on_delta
    )
    answer = result["answer"]
    if not isinstance(answer, str) or not answer.strip() or len(answer) > MAX_ANSWER_CHARS:
        raise ValueError("Invalid completed answer")
    emit({"type": "done", "answer": answer})


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, TypeError, KeyError, AttributeError) as exc:
        detail = str(exc)
        # Only display our own bounded, classified error messages. Never include
        # provider payloads, credentials or arbitrary exception details.
        if "HTTP 401" in detail:
            message = "Cloud.ru: неверный API-ключ (401)"
        elif "HTTP 403" in detail:
            message = "Cloud.ru: нет доступа к выбранной модели (403)"
        elif "HTTP 404" in detail:
            message = "Cloud.ru: проверьте ID выбранной модели (404)"
        elif "HTTP 429" in detail:
            message = "Cloud.ru: превышен лимит запросов (429)"
        elif "Incomplete Cloud.ru stream" in detail:
            message = "Cloud.ru: сервер прервал поток ответа"
        elif "key not configured" in detail:
            message = "Cloud.ru: сначала сохраните API-ключ в настройках"
        else:
            message = "Cloud.ru: поток недоступен; проверьте подключение и ID модели"
        emit({"type": "error", "message": message})
        sys.exit(1)
