# Yorika bounded neural supervisor

`backend.neural_supervisor.supervise` calls the single-brain long-run controller with a maximum number of retry attempts, exponential delay and wall-time budget. It never changes the selected active brain or downloads model weights. Transient OSError/RuntimeError failures are retried; configuration, integrity and validation failures fail closed. An unfinished run caused by a time budget is returned without busy-looping.

The long-run controller now clears the exact next uncommitted checkpoint and an abandoned temporary progress manifest before retrying. It does not trust uncommitted weights or bypass a damaged committed checkpoint hash.

**Limits:** this is a same-process supervisor, not a daemon that restarts after OS shutdown. It does not impose a hard RSS/VRAM limit, and RTX 3050 acceptance is still required. All tests run without Ollama.
