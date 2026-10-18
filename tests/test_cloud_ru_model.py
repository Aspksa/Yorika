import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError

from backend.storage import Store

PATH = Path(__file__).resolve().parents[1] / "scripts" / "cloud-ru-model.py"
spec = importlib.util.spec_from_file_location("yorika_cloud_ru", PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeResponse:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def read(self, length):
        return json.dumps({"choices": [{"message": {"content": "Ответ Ёрики"}}]}).encode()


class CloudRuTests(unittest.TestCase):
    def test_cloud_endpoint_bearer_and_memory_context(self):
        with tempfile.TemporaryDirectory() as root:
            with Store(Path(root)) as db:
                db.remember("favorite", "Ёрика любит чай", "user")
                db.put("private", "private", {"text": "секрет Ёрика"})
            requests = []
            def opener(req, timeout):
                requests.append((req, timeout))
                return FakeResponse()
            result = module.answer("Ёрика", Path(root), model="ai-sage/GigaChat3-10B-A1.8B",
                                   api_key="test-secret", opener=opener)
            self.assertEqual(result["provider"], "cloud-ru-foundation-models")
            self.assertEqual(result["answer"], "Ответ Ёрики")
            req, timeout = requests[0]
            self.assertEqual(req.full_url,
                             "https://foundation-models.api.cloud.ru/v1/chat/completions")
            self.assertEqual(req.get_header("Authorization"), "Bearer test-secret")
            self.assertEqual(timeout, 20)
            data = json.loads(req.data)
            self.assertIn("Ёрика любит чай", data["messages"][0]["content"])
            self.assertNotIn("секрет Ёрика", data["messages"][0]["content"])
            self.assertFalse(data["stream"])

    def test_environment_credential_fallback_without_dpapi(self):
        from unittest.mock import patch
        import os
        with tempfile.TemporaryDirectory() as root:
            captured = []
            def fake(req, timeout):
                captured.append(req)
                return FakeResponse()
            with patch.object(module.sys, "platform", "linux"), \
                 patch.dict(os.environ, {
                     "YORIKA_CLOUD_RU_API_KEY": "env-test-secret",
                     "YORIKA_CLOUD_RU_MODEL": "ai-sage/GigaChat3-10B-A1.8B",
                 }):
                result = module.answer("Привет", Path(root), opener=fake)
            self.assertEqual(result["provider"], "cloud-ru-foundation-models")
            self.assertEqual(captured[0].get_header("Authorization"),
                             "Bearer env-test-secret")

    def test_connection_check_does_not_read_or_send_memories(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            requests = []
            def fake(req, timeout):
                requests.append(req)
                return FakeResponse()
            with patch.object(module, "Store", side_effect=AssertionError("Memory accessed")):
                response = module.answer(
                    "Ответь одним словом: готово", Path(folder),
                    api_key="example", model="ai-sage/test", opener=fake,
                    include_memory=False,
                )
            self.assertEqual(response["memories_used"], [])
            payload = json.loads(requests[0].data)
            self.assertIn("(нет)", payload["messages"][0]["content"])
            self.assertEqual(len(payload["messages"]), 2)

    def test_invalid_credentials_and_query_never_call_network(self):
        with tempfile.TemporaryDirectory() as root:
            def blocked(*args, **kwargs):
                self.fail("Network was called")
            with self.assertRaises(RuntimeError):
                module.answer("привет", Path(root), api_key="bad\nheader", opener=blocked)
            with self.assertRaises(ValueError):
                module.answer("", Path(root), api_key="test", opener=blocked)
            with self.assertRaises(ValueError):
                module.answer("привет", Path(root), api_key="test", model="bad model", opener=blocked)

    def test_cloud_http_errors_are_classified_without_secrets(self):
        with tempfile.TemporaryDirectory() as root:
            for status, expected in ((401, "ключ"), (403, "доступ"),
                                     (404, "модель"), (429, "лимит"),
                                     (503, "сервиса")):
                def failed(req, timeout):
                    raise HTTPError(req.full_url, status, "provider-secret-body", {}, None)
                with self.subTest(status=status):
                    with self.assertRaises(RuntimeError) as ctx:
                        module.answer("Привет", Path(root), api_key="never-echo-this",
                                      model="ai-sage/test", opener=failed,
                                      include_memory=False)
                    message = str(ctx.exception)
                    self.assertIn(expected, message)
                    self.assertNotIn("never-echo-this", message)
                    self.assertNotIn("provider-secret-body", message)

    def test_http_error_does_not_disclose_token(self):
        with tempfile.TemporaryDirectory() as root:
            def forbidden(req, timeout):
                raise HTTPError(req.full_url, 401, "unauthorized", {}, None)
            with self.assertRaisesRegex(RuntimeError, "HTTP 401") as cm:
                module.answer("привет", Path(root), api_key="super-secret", opener=forbidden)
            self.assertNotIn("super-secret", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
