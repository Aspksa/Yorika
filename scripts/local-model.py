#!/usr/bin/env python3
"""Yorika's own experimental local neural checkpoint; no third-party model server."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.neural_router import experimental_answer

MAX_QUERY = 2000


def answer(query: str, *, checkpoint=None, generator=None) -> dict:
    if not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY:
        raise ValueError("Invalid query")
    path = checkpoint if checkpoint is not None else os.environ.get("YORIKA_NEURAL_CHECKPOINT", "")
    if not path:
        raise RuntimeError("Yorika checkpoint is not configured; no external model fallback")
    kwargs = {"checkpoint": path, "enabled": True}
    if generator is not None:
        kwargs["generator"] = generator
    result = experimental_answer(query, **kwargs)
    if not result["answer"].strip():
        raise RuntimeError("Yorika experimental model generated an empty response")
    return result


def main():
    raw = sys.stdin.read(MAX_QUERY + 1)
    print(json.dumps(answer(raw), ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, TypeError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        sys.exit(1)
