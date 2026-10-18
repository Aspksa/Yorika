import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "cloud-ru-stream.py"
spec = importlib.util.spec_from_file_location("yorika_stream_gateway_test", SCRIPT)
gateway = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gateway)


class StreamGatewayTests(unittest.TestCase):
    def test_gateway_emits_delta_then_done(self):
        output = io.StringIO()
        class FakeModel:
            @staticmethod
            def answer(query, conversation_id=None, stream=False, on_delta=None):
                self.assertEqual(query, "Привет")
                self.assertEqual(conversation_id, "example")
                self.assertTrue(stream)
                on_delta("При")
                on_delta("вет")
                return {"answer": "Привет"}
        class FakeSpec:
            loader = None
        original_spec = gateway.importlib.util.spec_from_file_location
        original_module = gateway.importlib.util.module_from_spec
        try:
            gateway.importlib.util.spec_from_file_location = lambda *a, **k: FakeSpec()
            gateway.importlib.util.module_from_spec = lambda *a, **k: FakeModel()
            with patch.object(gateway.sys, "stdin", io.StringIO(json.dumps(
                    {"query": "Привет", "conversation_id": "example"}))), \
                 patch.object(gateway.sys, "stdout", output):
                gateway.main()
        finally:
            gateway.importlib.util.spec_from_file_location = original_spec
            gateway.importlib.util.module_from_spec = original_module
        events = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([event["type"] for event in events],
                         ["delta", "delta", "done"])
        self.assertEqual(events[-1]["answer"], "Привет")


if __name__ == "__main__":
    unittest.main()
