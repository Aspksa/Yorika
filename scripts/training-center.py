#!/usr/bin/env python3
"""CLI for the «Обучение» page; the tray passes the action and a JSON body on stdin.

Prints one JSON object. Errors are short Russian texts the page can show as is.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import continual_learning as cl
from backend import blind
from backend import night_cycle as night
from backend import self_learning as sl
from backend import teacher
from backend import training_center as tc

READS = {"status", "sl-status", "teacher-status", "night-status", "continual-status"}
WRITES = {"probe", "install-torch", "data-check", "folder", "open-folder", "start", "control",
          "activate", "rollback", "compare", "stop-all", "sl-collect-setting", "sl-collect",
          "sl-list", "sl-rate", "sl-delete", "sl-export", "sl-dismiss", "text-approve",
          "teacher-limits", "teacher-estimate", "teacher-start", "teacher-stop", "teacher-accept",
          "night-settings", "series", "sl-pack-preview", "sl-pack-add", "blind-start", "blind-vote", "blind-results",
          "teacher-models", "continual-settings", "continual-run", "continual-activate", "continual-stop", "continual-experience"}


def handle(action, body):
    if action == "continual-experience":
        if not cl.settings()["enabled"] or not sl._settings()["collect"] or cl.busy():
            return {"added": 0}
        with cl.lock():
            return sl.collect()
    if action == "continual-status":
        return cl.status()
    if action == "continual-settings":
        return cl.configure(body.get("enabled"), device=body.get("device", "cuda"),
                            steps=body.get("steps", 8), seconds=body.get("seconds", 60))
    if action == "continual-run":
        return {"queued": cl.trigger()}
    if action == "continual-activate":
        return cl.activate(body.get("id"))
    if action == "continual-stop":
        return cl.stop()
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
                        total_steps=body.get("steps", 100000), hours=hours, base=body.get("base"),
                        size=body.get("size", "s"))
    if action == "series":
        return tc.start_series(body.get("dataset"), body.get("sizes"), device=body.get("device", "cuda"),
                               total_steps=body.get("steps", 100000), hours_each=body.get("hours", 2.0))
    if action == "control":
        return tc.control(body.get("id"), body.get("action"))
    if action == "activate":
        return tc.activate(body.get("id"))
    if action == "rollback":
        return tc.rollback()
    if action == "compare":
        return tc.compare(body.get("ids"), body.get("questions"))
    if action == "stop-all":
        return tc.stop_all()
    if action == "sl-status":
        return sl.status()
    if action == "sl-collect-setting":
        return sl.set_collect(body.get("enabled"))
    if action == "sl-collect":
        return sl.collect()
    if action == "sl-list":
        return sl.list_items(body.get("view", "unrated"), body.get("offset", 0), body.get("limit", 20))
    if action == "sl-rate":
        result = sl.rate(body.get("id"), body.get("rating"), body.get("correction"))
        try:
            result["continual_queued"] = cl.trigger()
        except OSError:
            result["continual_queued"] = False
        return result
    if action == "sl-delete":
        return sl.delete(body.get("id"))
    if action == "sl-export":
        return sl.export()
    if action == "sl-dismiss":
        return sl.dismiss(body.get("id"))
    if action == "sl-pack-preview":
        return sl.pack_preview(body.get("name"))
    if action == "sl-pack-add":
        return sl.add_pack(body.get("name"), body.get("confirm") is True)
    if action == "text-approve":
        return tc.approve_text(body.get("name"), body.get("license"), body.get("approved", True) is True)
    if action == "teacher-status":
        return teacher.status()
    if action == "teacher-limits":
        return teacher.set_limits(body.get("per_run_tokens"), body.get("monthly_tokens"))
    if action == "teacher-estimate":
        return teacher.estimate(body.get("kind"), body.get("count"))
    if action == "teacher-start":
        return teacher.start(body.get("kind"), body.get("count"), confirm=body.get("confirm") is True,
                             topics=body.get("topics"))
    if action == "teacher-models":
        return teacher.set_models(body.get("models"))
    if action == "blind-start":
        return blind.start(body.get("ids"), body.get("count", 5))
    if action == "blind-vote":
        return blind.vote(body.get("round"), body.get("index"), body.get("choice"))
    if action == "blind-results":
        return {"results": blind.results()}
    if action == "teacher-stop":
        return teacher.stop()
    if action == "teacher-accept":
        return teacher.accept_verdicts()
    if action == "night-status":
        return night.status()
    if action == "night-settings":
        return night.set_settings(body.get("enabled"), body.get("time", "02:00"), body.get("hours", 4.0),
                                  body.get("teacher_tokens", 0), body.get("selfplay", 20),
                                  sizes=body.get("sizes"))
    raise ValueError("Неизвестное действие")


def main(argv):
    if len(argv) == 2 and argv[1] == "continual-worker":
        cl.worker()
        return 0
    if len(argv) == 3 and argv[1] == "worker":
        return tc.worker(argv[2])
    if len(argv) == 2 and argv[1] == "pip-worker":
        return tc.pip_worker()
    if len(argv) == 2 and argv[1] == "teacher-worker":
        return teacher.worker()
    if len(argv) == 2 and argv[1] == "night-run":
        night.run()
        return 0
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
