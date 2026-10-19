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


if __name__ == "__main__":
    unittest.main()
