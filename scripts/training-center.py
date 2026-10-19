#!/usr/bin/env python3
"""CLI for the «Обучение» page; the tray passes the action and a JSON body on stdin.

Prints one JSON object. Errors are short Russian texts the page can show as is.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import training_center as tc

READS = {"status"}
WRITES = {"probe", "install-torch", "data-check", "folder", "open-folder", "start", "control",
          "activate", "rollback", "compare"}


def handle(action, body):
    if action == "status":
        return tc.status()
    if action == "probe":
        return tc.probe()
    if action == "install-torch":
        return tc.install_torch()
    if action == "data-check":
        return tc.check_data(body.get("name"))
    if action == "folder":
        return tc.set_folder(body.get("path"))
    if action == "open-folder":
        return tc.open_folder(body.get("which"))
    if action == "start":
        hours = body.get("hours", 8)
        return tc.start(body.get("mode"), dataset=body.get("dataset"), device=body.get("device", "cuda"),
                        total_steps=body.get("steps", 100000), hours=hours)
    if action == "control":
        return tc.control(body.get("id"), body.get("action"))
    if action == "activate":
        return tc.activate(body.get("id"))
    if action == "rollback":
        return tc.rollback()
    if action == "compare":
        return tc.compare(body.get("ids"), body.get("questions"))
    raise ValueError("Неизвестное действие")


def main(argv):
    if len(argv) == 3 and argv[1] == "worker":
        return tc.worker(argv[2])
    if len(argv) == 2 and argv[1] == "pip-worker":
        return tc.pip_worker()
    if len(argv) != 2 or argv[1] not in READS | WRITES:
        raise ValueError("Неизвестное действие")
    raw = sys.stdin.read(16385) if argv[1] in WRITES else ""
    if len(raw) > 16384:
        raise ValueError("Слишком большой запрос")
    body = json.loads(raw) if raw.strip() else {}
    if not isinstance(body, dict):
        raise ValueError("Неверный запрос")
    print(json.dumps(handle(argv[1], body), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except (ValueError, RuntimeError, OSError) as error:
        print(json.dumps({"error": str(error)[:160]}, ensure_ascii=False))
        sys.exit(1)
