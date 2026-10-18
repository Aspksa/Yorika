# Yorika creative expansion, streaming, and Windows validation

## Adding new replies and scenario hints

From a configured local Yorika environment, run:

```powershell
python scripts/expand-persona.py "Хочу поговорить о планах на завтра"
```

The command sends **one explicit request** to Cloud.ru and expects a JSON array of exactly two variants. It only persists candidates passing the existing privacy, length, and duplicate controls. Original 1,024 persona replies and 473 authored scenarios are never overwritten. Generated scenario seeds are optional style hints, not deterministic dialogue scripts or model fine-tuning.

## Streaming status

`scripts/cloud-ru-model.py` now accepts `answer(..., stream=True, on_delta=callback)`. A bounded parser accepts Cloud.ru/OpenAI-style SSE delta events, reports chunks to the caller, and stores the complete result only after `[DONE]`.

**The tray HTTP API and avatar UI now have a streaming path in source code**: the tray exposes `/api/chat/stream`, `scripts/cloud-ru-stream.py` forwards NDJSON `delta`/`done` events, and `www/avatar.js` incrementally renders deltas. A JSON fallback remains for requests without a delivered delta. The Cloud.ru SSE parser accepts comments, CRLF, and multiline JSON `data:` fields, with event/response size bounds. This is code-level implementation, not a claim of successful real Cloud.ru or Windows end-to-end testing.

## Windows validation

Run `powershell -ExecutionPolicy Bypass -File scripts/validate-windows.ps1` from the repository root. This validates PowerShell syntax, Python compilation and unit tests, and JavaScript syntax when Node.js is installed. A live Cloud.ru call, credential DPAPI operations, UI interaction and packaging still need manual verification. Run `python -m unittest discover -s tests -p 'test_cloud_stream_framing.py' -v` to exercise SSE framing regressions. GitHub Actions are currently failing before job steps start; do not infer code test failures or passing CI from these runs. GitHub CI success is not assumed.

Never commit API keys, local SQLite files or backups.
