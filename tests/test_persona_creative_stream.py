import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from backend.cloud_stream import collect_stream
from backend.persona_creativity import expand_persona, scenario_hint
from backend.storage import Store

MODEL = Path(__file__).resolve().parents[1] / "scripts" / "cloud-ru-model.py"
spec = importlib.util.spec_from_file_location("yorika_stream_test", MODEL)
cloud = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cloud)


class StreamResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __iter__(self):
        return iter((
            b'data: {"choices":[{"delta":{"content":"\u041f\u0440\u0438"}}]}\n',
            b'data: {"choices":[{"delta":{"content":"\u0432\u0435\u0442"}}]}\n',
            b'data: [DONE]\n',
        ))


class CreativeStreamingTests(unittest.TestCase):
    def test_sse_parser_and_live_callbacks(self):
        seen = []
        self.assertEqual(collect_stream(StreamResponse(), seen.append), "Привет")
        self.assertEqual(seen, ["При", "вет"])

    def test_stream_requires_end_marker(self):
        with self.assertRaisesRegex(RuntimeError, "Incomplete"):
            collect_stream([b'data: {"choices":[{"delta":{"content":"text"}}]}\n'])

    def test_cloud_answer_stream_does_not_change_default_contract(self):
        with tempfile.TemporaryDirectory() as folder:
            requests = []
            seen = []
            def opener(request, timeout):
                requests.append(json.loads(request.data))
                return StreamResponse()
            answer = cloud.answer(
                "Привет", Path(folder), model="ai-sage/test", api_key="fake",
                opener=opener, stream=True, on_delta=seen.append,
                include_memory=False,
            )
            self.assertEqual(answer["answer"], "Привет")
            self.assertTrue(requests[0]["stream"])
            self.assertEqual("".join(seen), "Привет")

    def test_expansion_adds_variations_and_scenario_hints(self):
        with tempfile.TemporaryDirectory() as folder:
            seed = "Хочу поговорить о планах на завтра"
            options = [
                "Я могу вместе с вами обдумать завтрашние планы и выбрать удобный следующий шаг.",
                "Давайте спокойно наметим несколько вариантов на завтра, учитывая ваши пожелания."
            ]
            with Store(Path(folder)) as store:
                result = expand_persona(store, seed, lambda prompt: json.dumps(options, ensure_ascii=False))
                self.assertEqual(result["generated"], 2)
                self.assertEqual(result["accepted"], 2)
                self.assertEqual(result["scenarios_added"], 2)
                self.assertIn(scenario_hint(store, seed), options)
                repeated = expand_persona(store, seed, lambda prompt: json.dumps(options, ensure_ascii=False))
                self.assertEqual(repeated["accepted"], 0)

    def test_expansion_rejects_bad_model_output(self):
        with tempfile.TemporaryDirectory() as folder:
            with Store(Path(folder)) as store:
                with self.assertRaises(ValueError):
                    expand_persona(store, "Обсудим вечерние планы", lambda _: "not json")


if __name__ == "__main__":
    unittest.main()
