#!/usr/bin/env python3
"""CLI for the «Обучение» page; the tray passes the action and a JSON body on stdin.

Prints one JSON object. Errors are short Russian texts the page can show as is.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import blind
from backend import night_cycle as night
from backend import self_learning as sl
from backend import teacher
from backend import training_center as tc

READS = {"status", "sl-status", "teacher-status", "night-status", "brain-status"}
WRITES = {"probe", "install-torch", "data-check", "folder", "open-folder", "start", "control",
          "activate", "rollback", "compare", "stop-all", "sl-collect-setting", "sl-collect",
          "sl-list", "sl-rate", "sl-delete", "sl-export", "sl-dismiss", "text-approve",
          "teacher-limits", "teacher-estimate", "teacher-start", "teacher-stop", "teacher-accept",
          "night-settings", "series", "sl-pack-preview", "sl-pack-add", "blind-start", "blind-vote", "blind-results",
          "teacher-models", "chat-engine", "continual-settings", "continual-now", "evolve", "merge",
          "compress", "grow", "curiosity-now", "think", "plan-start", "schedule-set", "autopilot",
          "programs-learn", "sim-now", "introspect", "autopilot-options", "tidy"}


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
                        total_steps=body.get("steps", 100000), hours=hours, base=body.get("base"),
                        size=body.get("size", "s"), arch=body.get("arch"))
    if action == "series":
        return tc.start_series(body.get("dataset"), body.get("sizes"), device=body.get("device", "cuda"),
                               total_steps=body.get("steps", 100000), hours_each=body.get("hours", 2.0),
                               arch=body.get("arch"))
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
        return sl.rate(body.get("id"), body.get("rating"), body.get("correction"))
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
    if action == "brain-status":
        from backend import brain, continual, curiosity
        from backend import autopilot, plans, programs, simworld
        return {"engine": brain.engine(), "continual": continual.status(), "wishes": curiosity.wishes(),
                "frontier": curiosity.logic_frontier(), "curiosity": curiosity.last(), "plans": plans.status(),
                "sim": dict(simworld.totals(), job=tc._read(tc.folder() / "sim-job.json")),
                "skills": programs.describe(), "autopilot": autopilot.status(), "evolution": _evolution()}
    if action == "plan-start":
        from backend import plans
        return plans.start(body.get("kind"), copies=body.get("copies"), branches=body.get("branches", 3),
                           rounds=body.get("rounds", 2), minutes=body.get("minutes", 20),
                           prompts=body.get("prompts", 120), teacher=body.get("teacher"))
    if action == "autopilot-options":
        from backend import autopilot
        return autopilot.set_options(body.get("auto_week"), body.get("tidy"))
    if action == "tidy":
        from backend import health
        return health.tidy()
    if action == "schedule-set":
        from backend import schedule
        result = schedule.set_grid(body.get("grid"), body.get("enforce", True) is True)
        if night.settings()["enabled"] and night.os.name == "nt":
            night.apply_schedule(True)
        return result
    if action == "autopilot":
        from backend import autopilot
        return autopilot.set_enabled(body.get("enabled"))
    if action == "programs-learn":
        from backend import curiosity, programs
        found = programs.learn()
        added = curiosity._add(programs.lessons(found), "programs") if found else 0
        return {"found": found, "lessons": added, "skills": programs.describe()}
    if action == "sim-now":
        job = tc._read(tc.folder() / "sim-job.json", {}) or {}
        if job.get("state") == "running" and __import__("time").time() - job.get("t", 0) < 3600:
            raise ValueError("Мир задач уже работает")
        tc._write(tc.folder() / "sim-job.json", {"state": "running", "t": __import__("time").time(), "result": None})
        tc._spawn([sys.executable, str(tc.CLI), "sim-worker"], tc.folder() / "sim.log")
        return {"state": "running"}
    if action == "introspect":
        tc._run_dir(body.get("id"))
        tc._spawn([sys.executable, str(tc.CLI), "introspect-worker", body.get("id")], tc.folder() / "introspect.log")
        return {"state": "running"}
    if action == "chat-engine":
        from backend import brain
        return brain.set_engine(body.get("engine"), body.get("drafts", 3), body.get("compressed", False) is True)
    if action == "continual-settings":
        from backend import continual
        return continual.set_settings(body.get("enabled"), body.get("auto_activate", False) is True,
                                      body.get("min_new", 20), body.get("minutes", 5))
    if action == "continual-now":
        from backend import continual
        return {"run": continual.maybe_start(force=True)}
    if action == "evolve":
        return tc.start_evolution(body.get("dataset"), body.get("population", 4), device=body.get("device", "cuda"),
                                  total_steps=body.get("steps", 100000), hours_each=body.get("hours", 1.0))
    if action == "merge":
        ids = body.get("ids") or [None, None]
        return tc.merge(*ids[:2]) if isinstance(ids, list) and len(ids) == 2 else tc.merge(None, None)
    if action == "compress":
        return tc.compress(body.get("id"))
    if action == "grow":
        return tc.start("long", dataset=body.get("dataset"), device=body.get("device", "cuda"),
                        total_steps=body.get("steps", 100000), hours=body.get("hours", 8),
                        grow={"from": body.get("id"), "experts": body.get("experts", 0)} if body.get("experts") in (2, -2)
                        else {"from": body.get("id"), "layers": body.get("layers", 2)})
    if action == "curiosity-now":
        from backend import curiosity
        return curiosity.start()
    if action == "think":
        from backend import brain
        loaded = brain.load(tc._run_dir(body.get("id")) / "language-longrun.pt.best.pt")
        question = body.get("question")
        if not isinstance(question, str) or not 1 <= len(question.strip()) <= 500:
            raise ValueError("Вопрос от 1 до 500 символов")
        drafts = body.get("drafts", 3)
        if drafts not in (1, 3, 5):
            raise ValueError("Черновиков 1, 3 или 5")
        return brain.think(*loaded, question.strip(), drafts=drafts)
    if action == "teacher-stop":
        return teacher.stop()
    if action == "teacher-accept":
        return teacher.accept_verdicts()
    if action == "night-status":
        return night.status()
    if action == "night-settings":
        return night.set_settings(body.get("enabled"), body.get("time", "02:00"), body.get("hours", 4.0),
                                  body.get("teacher_tokens", 0), body.get("selfplay", 20),
                                  sizes=body.get("sizes"), sleep=body.get("sleep", True) is True,
                                  curiosity=body.get("curiosity", True) is True, evolve=body.get("evolve", 0),
                                  week=body.get("week"), lives=body.get("lives", 300),
                                  programs=body.get("programs", True) is True)
    raise ValueError("Неизвестное действие")


def _evolution():
    """Archive, study recipes, the task ladder, health, tonight's choice and the morning report."""
    from backend import archive, health, planner, recipes, simworld
    parts = {}
    for key, read in (("archive", archive.cells), ("recipes", recipes.status), ("ladder", simworld.ladder),
                      ("health", health.check), ("report", planner.morning), ("tonight", lambda: planner.today(night.activity()))):
        try:
            parts[key] = read()
        except Exception as error:  # noqa: BLE001 - one broken part never hides the page
            parts[key] = {"error": str(error)[:160]}
    parts["envs"] = {env: name for env, (name, _) in simworld.ENVS.items()}
    from backend import autopilot
    parts["options"], parts["activities"] = autopilot.settings(), night.ACTIVITIES
    return parts


def main(argv):
    if len(argv) == 3 and argv[1] == "worker":
        return tc.worker(argv[2])
    if len(argv) == 2 and argv[1] == "pip-worker":
        return tc.pip_worker()
    if len(argv) == 2 and argv[1] == "teacher-worker":
        return teacher.worker()
    if len(argv) == 3 and argv[1] == "exam-worker":
        return tc.exam_worker(argv[2])
    if len(argv) == 2 and argv[1] == "curiosity-worker":
        from backend import curiosity
        return curiosity.worker()
    if len(argv) == 2 and argv[1] == "plan-worker":
        from backend import plans
        return plans.worker()
    if len(argv) == 2 and argv[1] == "sim-worker":
        import time
        try:
            result, state = night._sim_lives(150), "finished"
        except Exception as error:  # noqa: BLE001 - the page shows why it stopped
            result, state = str(error)[:200], "failed"
        tc._write(tc.folder() / "sim-job.json", {"state": state, "t": time.time(), "result": result})
        return 0 if state == "finished" else 1
    if len(argv) == 3 and argv[1] == "introspect-worker":
        return tc.introspect_worker(argv[2])
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
