"""Run a single periodic creative expansion from standard input."""
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.storage import Store
from backend.persona_creativity import expand_persona


def main():
    seed = sys.stdin.read(400)
    spec = importlib.util.spec_from_file_location(
        "yorika_auto_model", Path(__file__).with_name("cloud-ru-model.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    def generate(prompt):
        return module.answer(prompt, include_memory=False)["answer"]
    with Store() as db:
        expand_persona(db, seed, generate)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, TypeError):
        sys.exit(1)
