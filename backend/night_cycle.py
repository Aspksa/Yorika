"""Night cycle: every night Yorika gathers experience, asks the teacher, trains, and takes the exam.

Off until the owner turns it on. On Windows it is a daily Task Scheduler task for the current
user. The teacher step spends tokens only up to the nightly limit the owner set when turning
it on (0 means no teacher at night). Nothing is activated: in the morning the page proposes
the new version and the owner decides.
"""
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from backend import self_learning as sl
from backend import teacher
from backend import training_center as tc

TASK_NAME = "Yorika Night Training"
TIME = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]\Z")
DEFAULTS = {"enabled": False, "time": "02:00", "hours": 4.0, "teacher_tokens": 0, "selfplay": 20, "sizes": ["s"],
            "sleep": True, "curiosity": True, "evolve": 0}
EVOLUTION_WEEKDAY = 5  # Saturday night: evolution; other nights: sleep that continues the active version


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def settings():
    saved = tc._read(tc.folder() / "night.json", {}) or {}
    return {k: saved.get(k, v) for k, v in DEFAULTS.items()}


def log():
    return (tc._read(tc.folder() / "night-log.json", []) or [])[-14:]


def _launcher():
    """A short .cmd outside OneDrive: Task Scheduler limits the command line to 261 characters."""
    script = tc.base_dir() / "night-run.cmd"
    script.parent.mkdir(parents=True, exist_ok=True)
    python = Path(sys.executable)
    pythonw = python.with_name("pythonw.exe")
    exe = pythonw if pythonw.is_file() else python
    script.write_text('@echo off\r\nchcp 65001 >nul\r\n"%s" "%s" night-run\r\n' % (exe, tc.CLI), encoding="utf-8")
    return script


def schedule_command(enabled, time):
    if not enabled:
        return ["schtasks", "/Delete", "/F", "/TN", TASK_NAME]
    return ["schtasks", "/Create", "/F", "/SC", "DAILY", "/ST", time, "/TN", TASK_NAME,
            "/TR", '"%s"' % _launcher()]


def set_settings(enabled, time="02:00", hours=4.0, teacher_tokens=0, selfplay=20, apply=True, sizes=None,
                 sleep=True, curiosity=True, evolve=0):
    if not isinstance(enabled, bool):
        raise ValueError("Неверное значение")
    if not isinstance(time, str) or not TIME.match(time):
        raise ValueError("Время в формате ЧЧ:ММ")
    if type(hours) not in (int, float) or not 0.5 <= hours <= 10:
        raise ValueError("Обучение ночью от 0,5 до 10 часов")
    limits = teacher.settings()
    if type(teacher_tokens) is not int or not 0 <= teacher_tokens <= limits["per_run_tokens"]:
        raise ValueError("Токенов за ночь от 0 до лимита на один запуск (%d)" % limits["per_run_tokens"])
    if type(selfplay) is not int or not 5 <= selfplay <= 500:
        raise ValueError("Примеров самоигры от 5 до 500")
    sizes = ["s"] if sizes is None else sizes
    # Two or three sizes make the night a sandbox: the hours are shared between them.
    if (not isinstance(sizes, list) or not 1 <= len(sizes) <= 3 or len(set(sizes)) != len(sizes) or
            any(size not in tc.SIZES for size in sizes)):
        raise ValueError("Выберите от одного до трёх размеров модели")
    if not isinstance(sleep, bool) or not isinstance(curiosity, bool) or type(evolve) is not int or evolve not in (0, 3, 4, 5, 6):
        raise ValueError("Эволюция: 0 или от 3 до 6 вариантов")
    if apply:
        if os.name != "nt":
            raise ValueError("Ночной цикл ставится в планировщик Windows")
        result = subprocess.run(schedule_command(enabled, time), capture_output=True,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode and enabled:
            raise ValueError("Планировщик Windows не принял задачу")
    value = {"enabled": enabled, "time": time, "hours": float(hours), "teacher_tokens": teacher_tokens,
             "selfplay": selfplay, "sizes": sizes, "sleep": sleep, "curiosity": curiosity, "evolve": evolve,
             "changed": _now()}
    tc._write(tc.folder() / "night.json", value)
    return settings()


def _newest_experience():
    files = sorted((f for f in tc.data_files() if f["name"].startswith("опыт-")), key=lambda f: f["name"])
    return files[-1]["name"] if files else None


def _train(plan, name, launch):
    """Sleep continues the active version; evolution night breeds variants; else a fresh run."""
    if not name:
        raise ValueError("нет файла опыта")
    current = tc.active()
    evolution_night = plan["evolve"] and datetime.now().weekday() == EVOLUTION_WEEKDAY
    if current and plan["sleep"] and not evolution_night:
        # Sleep: the active version relives the day mixed with older examples and continues.
        from backend import continual
        records, mix = continual.sleep_set(name)
        config = dict(tc._read(tc._run_dir(current["run"]) / "run.json")["config"])
        started = tc.start("long", device=continual._device(current["run"]), total_steps=1000000,
                           hours=plan["hours"], config=config, kind="sleep", init=current["checkpoint"],
                           records=records, dataset=name, launch=launch)
        return "сон %s: новых %d, повтор старого %d, всего %d" % (started["id"], mix["new"], mix["replay"], len(records))
    blocker = tc.long_gate(tc._load_records(name))
    if blocker:
        raise ValueError(blocker)
    if evolution_night:
        each = round(plan["hours"] / plan["evolve"], 2)
        started = tc.start_evolution(name, plan["evolve"], device="cuda", total_steps=1000000, hours_each=each,
                                     launch=launch)
        return "эволюция %s: %d вариантов по %s ч" % (started["series"], plan["evolve"], each)
    sizes = plan["sizes"] if isinstance(plan["sizes"], list) and plan["sizes"] else ["s"]
    if len(sizes) > 1:
        each = round(plan["hours"] / len(sizes), 2)
        started = tc.start_series(name, sizes, device="cuda", total_steps=1000000, hours_each=each, launch=launch)
        return "песочница %s: размеры %s, по %s ч" % (started["series"], "/".join(sizes).upper(), each)
    started = tc.start("long", dataset=name, device="cuda", total_steps=1000000, hours=plan["hours"],
                       launch=launch, size=sizes[0])
    return "запущено обучение %s на %s ч" % (started["id"], plan["hours"])


def run(launch=True, opener=None):
    """One night. Each step writes what happened; a failed step does not hide the others."""
    plan = settings()
    entry = {"started": _now(), "steps": []}

    def step(name, result):
        entry["steps"].append({"step": name, "result": result})

    if not plan["enabled"]:
        step("cycle", "выключен")
    else:
        try:
            step("collect", "добавлено %d" % sl.collect()["added"] if sl._settings()["collect"] else "сбор выключен")
        except Exception as error:  # noqa: BLE001 - the log shows each step's outcome
            step("collect", str(error)[:160])
        if plan["teacher_tokens"] and teacher.weak_prompts():
            try:
                count = max(5, min(plan["selfplay"], plan["teacher_tokens"] // teacher.ESTIMATE["selfplay"] * teacher.PAIRS_PER_REQUEST))
                job = teacher.start("selfplay", count, confirm=True, launch=False, budget=plan["teacher_tokens"])
                job_state = teacher.run_job(opener=opener)
                step("teacher", "самоигра: новых примеров %d, токенов %d" % (job_state["added"], job_state["tokens"]))
                del job
            except Exception as error:  # noqa: BLE001
                step("teacher", str(error)[:160])
        else:
            step("teacher", "учитель ночью выключен" if not plan["teacher_tokens"] else "нет слабых мест")
        if plan["curiosity"]:
            try:
                from backend import curiosity
                step("curiosity", curiosity.night_step())
            except Exception as error:  # noqa: BLE001
                step("curiosity", str(error)[:160])
        try:
            newest = _newest_experience()
            ready = sl.counts()["ready"]
            if newest and len(tc._load_records(newest)) == ready:
                raise ValueError("новых оценённых примеров нет")
            exported = sl.export()
            step("export", "файл %s, примеров %d" % (exported["name"], exported["count"]))
        except Exception as error:  # noqa: BLE001
            step("export", str(error)[:160])
        try:
            step("train", _train(plan, _newest_experience(), launch))
        except Exception as error:  # noqa: BLE001
            step("train", str(error)[:160])
    entry["finished"] = _now()
    history = log() + [entry]
    tc._write(tc.folder() / "night-log.json", history[-14:])
    return entry


def status():
    return {"settings": settings(), "log": log(), "windows": os.name == "nt",
            "note": "Ноутбук должен быть включён и на зарядке; из сна он сам не просыпается"}
