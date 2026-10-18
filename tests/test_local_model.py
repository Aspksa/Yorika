import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from backend.storage import Store

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "local-model.py"
spec = importlib.util.spec_from_file_location("yorika_local_model", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Response:
    def __init__(self, value):
        self.value = value
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def read(self, _max_bytes):
        return json.dumps(self.value).encode("utf-8")


class LocalModelTests(unittest.TestCase):
    def test_local_only_request_and_sourced_context(self):
        with tempfile.TemporaryDirectory() as temp:
            with Store(Path(temp)) as store:
                store.remember("fact", "Ёрика любит чай", "user-confirmed")
                store.put("private", "secret", {"text": "секрет Ёрика"})
            requests = []
            def fake(request, timeout):
                requests.append((request, timeout))
                return Response({"message": {"content": "Это локальный ответ."}})
            result = module.answer("Ёрика", Path(temp), model="llama3.2", opener=fake)
            self.assertEqual(result["provider"], "local-ollama")
            self.assertEqual(result["answer"], "Это локальный ответ.")
            request, timeout = requests[0]
            self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/chat")
            body = json.loads(request.data)
            self.assertEqual(body["model"], "llama3.2")
            self.assertIn("Ёрика любит чай", body["messages"][0]["content"])
            self.assertNotIn("секрет Ёрика", body["messages"][0]["content"])
            self.assertEqual(timeout, 20)

    def test_invalid_config_rejected_before_network(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(RuntimeError):
                module.answer("привет", Path(temp), model="not allowed /etc")
            with self.assertRaises(ValueError):
                module.answer("", Path(temp), model="llama3.2")


if __name__ == "__main__":
    unittest.main()
