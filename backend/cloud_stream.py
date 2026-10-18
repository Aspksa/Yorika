"""Read OpenAI-compatible Server-Sent Events from Cloud.ru with hard bounds."""
import json

MAX_EVENT_BYTES = 64 * 1024
MAX_OUTPUT = 8000
MAX_STREAM_BYTES = 512 * 1024


def collect_stream(response, on_delta=None):
    """Consume SSE data fields, including events spread across multiple data lines.

    Keep the older single-data-line framing compatible with providers that omit
    the empty SSE event delimiter.
    """
    output = []
    size = 0
    total = 0
    pending = []
    ended = False

    def process(data):
        nonlocal size, ended
        if data == b"[DONE]":
            ended = True
            return
        try:
            event = json.loads(data.decode("utf-8"))
            chunk = event["choices"][0].get("delta", {}).get("content")
        except (UnicodeError, ValueError, KeyError, IndexError, AttributeError, TypeError):
            raise RuntimeError("Invalid Cloud.ru stream event") from None
        if chunk is None:
            return
        if not isinstance(chunk, str):
            raise RuntimeError("Invalid Cloud.ru stream delta")
        size += len(chunk)
        if size > MAX_OUTPUT:
            raise RuntimeError("Cloud.ru streamed answer too long")
        output.append(chunk)
        if on_delta is not None:
            on_delta(chunk)

    for line in response:
        if not isinstance(line, bytes):
            raise RuntimeError("Invalid Cloud.ru stream")
        total += len(line)
        if total > MAX_STREAM_BYTES or len(line) > MAX_EVENT_BYTES:
            raise RuntimeError("Cloud.ru stream too large")
        stripped = line.rstrip(b"\r\n")
        if not stripped:
            if pending:
                data = b"\n".join(pending)
                if len(data) > MAX_EVENT_BYTES:
                    raise RuntimeError("Cloud.ru stream too large")
                process(data)
                pending.clear()
            if ended:
                break
            continue
        if stripped.startswith(b":"):
            continue  # SSE keepalive comment
        if not stripped.startswith(b"data:"):
            continue  # event/id/retry fields
        data = stripped[5:]
        if data.startswith(b" "):
            data = data[1:]
        pending.append(data)
        if sum(map(len, pending)) + len(pending) > MAX_EVENT_BYTES:
            raise RuntimeError("Cloud.ru stream too large")
        # Compatibility: existing Cloud.ru fixtures and some providers send one
        # complete JSON object per data line with no separating blank line.
        candidate = b"\n".join(pending)
        if candidate == b"[DONE]":
            process(candidate)
            pending.clear()
            break
        try:
            json.loads(candidate.decode("utf-8"))
        except (UnicodeError, ValueError):
            continue
        process(candidate)
        pending.clear()

    if pending:
        raise RuntimeError("Incomplete Cloud.ru stream")
    if not ended or not "".join(output).strip():
        raise RuntimeError("Incomplete Cloud.ru stream")
    return "".join(output)
