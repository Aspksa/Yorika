#!/usr/bin/env python3
"""Explicit Cloud.ru creative expansion; costs provider tokens when invoked."""
import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.storage import Store
from backend.persona_creativity import expand_persona


def main():
    if len(sys.argv) != 2 or len(sys.argv[1]) > 500:
        raise ValueError("Usage: python scripts/expand-persona.py 'ситуация'")
    model_file = Path(__file__).with_name("cloud-ru-model.py")
    spec = importlib.util.spec_from_file_location("yorika_cloud_model", model_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def generate(prompt):
        return module.answer(prompt, include_memory=False)["answer"]

    with Store() as store:
        report = expand_persona(store, sys.argv[1], generate)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError) as error:
        print(json.dumps({"error": str(error)[:200]}, ensure_ascii=False))
        raise SystemExit(1)
