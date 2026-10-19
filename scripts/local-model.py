#!/usr/bin/env python3
"""Yorika's own experimental local neural checkpoint; no third-party model server."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.neural_router import experimental_answer
from backend.active_brain import active_brain
from backend.tools import run_tools

MAX_QUERY = 2000


def _is_language_checkpoint(path):
    try:
        import torch
        data = torch.load(path, map_location="cpu", weights_only=True)
    except Exception:  # noqa: BLE001 - anything unreadable goes through the legacy path and its errors
        return False
    return isinstance(data, dict) and data.get("schema") in ("yorika-language-longrun-v1", "yorika-q4-v1")


def answer(query: str, *, checkpoint=None, generator=None) -> dict:
    if not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY:
        raise ValueError("Invalid query")
    path = checkpoint if checkpoint is not None else (active_brain(os.environ["YORIKA_MODEL_DIRECTORY"]) if os.environ.get("YORIKA_MODEL_DIRECTORY") else os.environ.get("YORIKA_NEURAL_CHECKPOINT", ""))
    if not path:
        raise RuntimeError("Yorika checkpoint is not configured; no external model fallback")
    if generator is None and _is_language_checkpoint(path):
        # Versions from the «Обучение» page answer with drafts, self-check and tools.
        from backend.brain import load, think
        result = think(*load(path), query)
        if not result["answer"].strip():
            raise RuntimeError("Yorika experimental model generated an empty response")
        return {"answer": result["answer"], "provider": "yorika-own", "experimental": True,
                "checkpoint": Path(path).name, "quality_verified": False, "drafts": result["drafts"]}
    kwargs = {"checkpoint": path, "enabled": True}
    if generator is not None:
        kwargs["generator"] = generator
    result = experimental_answer(query, **kwargs)
    # Tool calls the model wrote ([[calc:…]], [[time:]], [[memory:…]]) are computed here, not guessed.
    try:
        text, calls = run_tools(result["answer"])
    except Exception:  # noqa: BLE001 - a broken tool must not hide the model's own answer
        text, calls = result["answer"], []
    if calls:
        result["answer"], result["tools"] = text, calls
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
