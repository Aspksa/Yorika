"""Validation and fail-closed regression tests for streaming gateway."""
import importlib.util
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / "scripts" / "cloud-ru-stream.py"
spec = importlib.util.spec_from_file_location("yorika_gateway_bounds", PATH)
gateway = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gateway)


class GatewayBoundsTests(unittest.TestCase):
    def test_rejects_non_object_or_empty_query(self):
        for data in ('[]', '{}', '{"query": 12}', '{"query":"  "}', '{"query":"hi","conversation_id":10}'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                gateway.read_request(io.StringIO(data))

    def test_rejects_oversized_request(self):
        with self.assertRaises(ValueError):
            gateway.read_request(io.StringIO(json.dumps({"query": "x" * 6000})))

    def test_rejects_oversized_utf8_request(self):
        with self.assertRaises(ValueError):
            gateway.read_request(io.StringIO(json.dumps({"query": "Я" * 1500}, ensure_ascii=False)))

    def test_bounded_valid_request(self):
        self.assertEqual(gateway.read_request(io.StringIO('{"query":"Привет","conversation_id":"thread"}')),
                         ("Привет", "thread"))

    def test_rejects_invalid_completed_answer(self):
        class FakeModel:
            @staticmethod
            def answer(query, conversation_id=None, stream=False, on_delta=None):
                return {"answer": "x" * 8001}
        with patch.object(gateway, "read_request", return_value=("hi", None)), \
             patch.object(gateway.importlib.util, "spec_from_file_location", return_value=type("FakeSpec", (), {"loader": type("FakeLoader", (), {"exec_module": lambda self, module: None})()})()), \
             patch.object(gateway.importlib.util, "module_from_spec", return_value=FakeModel):
            with self.assertRaisesRegex(ValueError, "completed"):
                gateway.main()

    def test_rejects_delta_exceeding_limit_before_emission(self):
        class FakeModel:
            @staticmethod
            def answer(query, conversation_id=None, stream=False, on_delta=None):
                on_delta("x" * 8001)
                return {"answer": "x"}
        with patch.object(gateway, "read_request", return_value=("hi", None)), \
             patch.object(gateway.importlib.util, "spec_from_file_location", return_value=type("FakeSpec", (), {"loader": type("FakeLoader", (), {"exec_module": lambda self, module: None})()})()), \
             patch.object(gateway.importlib.util, "module_from_spec", return_value=FakeModel):
            with self.assertRaisesRegex(ValueError, "exceeds"):
                gateway.main()


if __name__ == "__main__":
    unittest.main()
