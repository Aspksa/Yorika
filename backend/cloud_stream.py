"""Read OpenAI-compatible Server-Sent Events from Cloud.ru with hard bounds."""
import json

MAX_EVENT_BYTES = 64 * 1024
MAX_OUTPUT = 8000


def collect_stream(response, on_delta=None):
    output = []
    size = 0
    total = 0
    ended = False
    for line in response:
        if not isinstance(line, bytes):
            raise RuntimeError("Invalid Cloud.ru stream")
        total += len(line)
        if total > 512 * 1024 or len(line) > MAX_EVENT_BYTES:
            raise RuntimeError("Cloud.ru stream too large")
        if not line.startswith(b"data:"):
            continue
        data = line[5:].strip()
        if data == b"[DONE]":
            ended = True
            break
        try:
            event = json.loads(data.decode("utf-8"))
            chunk = event["choices"][0].get("delta", {}).get("content")
        except (ValueError, KeyError, IndexError, AttributeError, TypeError):
            raise RuntimeError("Invalid Cloud.ru stream event") from None
        if chunk is None:
            continue
        if not isinstance(chunk, str):
            raise RuntimeError("Invalid Cloud.ru stream delta")
        size += len(chunk)
        if size > MAX_OUTPUT:
            raise RuntimeError("Cloud.ru streamed answer too long")
        output.append(chunk)
        if on_delta is not None:
            on_delta(chunk)
    if not ended or not "".join(output).strip():
        raise RuntimeError("Incomplete Cloud.ru stream")
    return "".join(output)
