"""SSE framing regressions for Cloud.ru streaming."""
import json
import unittest

from backend.cloud_stream import collect_stream


def event(text):
    return b"data: " + json.dumps(
        {"choices": [{"delta": {"content": text}}]}, ensure_ascii=False
    ).encode("utf-8") + b"\r\n"


class StreamFramingTests(unittest.TestCase):
    def test_crlf_keepalive_and_metadata(self):
        chunks = []
        response = [b": ping\r\n", b"event: message\r\n", event("Привет"),
                    b"\r\n", b"data: [DONE]\r\n", b"\r\n"]
        self.assertEqual(collect_stream(response, chunks.append), "Привет")
        self.assertEqual(chunks, ["Привет"])

    def test_multiline_json_data_event(self):
        payload = b'{"choices": [{"delta":{\n"content":"hello"}}]}'
        response = [b"data: " + payload.split(b"\n")[0] + b"\n",
                    b"data: " + payload.split(b"\n")[1] + b"\n",
                    b"\n", b"data: [DONE]\n"]
        self.assertEqual(collect_stream(response), "hello")

    def test_old_framing_without_empty_lines(self):
        self.assertEqual(collect_stream([event("A"), event("B"), b"data: [DONE]\n"]), "AB")

    def test_truncated_multiline_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "Incomplete"):
            collect_stream([b'data: {"choices":\n'])

    def test_oversized_incomplete_event_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "too large"):
            collect_stream([b"data: " + b"x" * 40000 + b"\n",
                            b"data: " + b"x" * 30000 + b"\n"])

    def test_reasoning_model_answer_after_long_reasoning(self):
        # DeepSeek-style models stream reasoning_content first; only content is the answer.
        thinking = b"data: " + json.dumps({"choices": [{"delta": {"content": None,
            "reasoning_content": "x" * 300}}]}).encode("utf-8") + b"\n\n"
        response = [thinking] * 2000 + [event("Готово"), b"\n", b"data: [DONE]\n"]
        self.assertEqual(collect_stream(response), "Готово")

    def test_finished_stream_without_answer_is_reported_as_empty(self):
        thinking = b'data: {"choices":[{"delta":{"reasoning_content":"..."}}]}\n\n'
        with self.assertRaisesRegex(RuntimeError, "Empty Cloud.ru response"):
            collect_stream([thinking, b"data: [DONE]\n", b"\n"])

    def test_usage_and_role_chunks_are_ignored(self):
        # OpenAI-compatible servers end with a usage chunk whose choices list is empty.
        role = b'data: {"choices":[{"index":0,"delta":{"role":"assistant"}}]}\n\n'
        null_delta = b'data: {"choices":[{"index":0,"delta":null,"finish_reason":"stop"}]}\n\n'
        usage = b'data: {"id":"x","choices":[],"usage":{"total_tokens":12}}\n\n'
        response = [role, event("Привет"), null_delta, usage, b"data: [DONE]\n", b"\n"]
        self.assertEqual(collect_stream(response), "Привет")

    def test_error_event_is_reported(self):
        with self.assertRaisesRegex(RuntimeError, "reported an error"):
            collect_stream([b'data: {"error":{"message":"overloaded"}}\n\n'])


if __name__ == "__main__":
    unittest.main()
