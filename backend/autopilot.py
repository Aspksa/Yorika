"""Autopilot: one switch for everything Yorika can do by herself, within the limits you set.

On: chat pairs are collected, quick lessons follow conversations, and every painted block of
the week runs the study cycle (practice, programs, the planned training). Off: all of it stops.
It never turns on spending: the teacher's nightly tokens and auto-activation keep your choice.

With it she also picks each night's activity from measurements (planner.py), checks her own
health and tidies stale working copies (health.py). Both can be turned off separately.
"""
import os

from backend import continual
from backend import night_cycle
from backend import self_learning as sl


def _path():
    from backend import training_center as tc
    return tc.folder() / "autopilot.json"


def settings():
    from backend import training_center as tc
    saved = tc._read(_path(), {}) or {}
    return {"auto_week": saved.get("auto_week") is True, "tidy": saved.get("tidy", True) is not False}


def set_options(auto_week=None, tidy=None):
    from backend import training_center as tc
    value = settings()
    for key, given in (("auto_week", auto_week), ("tidy", tidy)):
        if given is not None:
            if not isinstance(given, bool):
                raise ValueError("Неверное значение")
            value[key] = given
    tc._write(_path(), value)
    return status()


def status():
    from backend import schedule
    night = night_cycle.settings()
    live = continual.settings()
    parts = [
        {"key": "collect", "title": "Собирает опыт из чата", "on": sl._settings()["collect"]},
        {"key": "continual", "title": "Учится после разговоров", "on": live["enabled"]},
        {"key": "night", "title": "Учится по расписанию", "on": night["enabled"]},
        {"key": "sim", "title": "Тренируется в мире задач", "on": night["enabled"] and night["lives"] > 0},
        {"key": "programs", "title": "Ищет программы-навыки", "on": night["enabled"] and night["programs"]},
        {"key": "curiosity", "title": "Занимается тем, где слабее", "on": night["enabled"] and night["curiosity"]},
        {"key": "auto_week", "title": "Сама выбирает занятие ночи по замерам", "on": night["enabled"] and settings()["auto_week"]},
        {"key": "tidy", "title": "Проверяет здоровье и убирает старые рабочие копии", "on": night["enabled"] and settings()["tidy"]},
        {"key": "auto", "title": "Включает версию сама, если не хуже", "on": live["auto_activate"], "optional": True},
        {"key": "teacher", "title": "Учитель Cloud.ru ночью", "on": night["teacher_tokens"] > 0, "optional": True},
    ]
    core = [p for p in parts if not p.get("optional")]
    return {"on": all(p["on"] for p in core), "parts": parts, "today": night_cycle.ACTIVITIES[night_cycle.activity(night)],
            "schedule": schedule.summary(), "windows": os.name == "nt"}


def set_enabled(enabled, apply=True):
    if not isinstance(enabled, bool):
        raise ValueError("Неверное значение")
    notes = []
    night = night_cycle.settings()
    live = continual.settings()
    if enabled:
        sl.set_collect(True)
        set_options(auto_week=True, tidy=True)
    else:
        set_options(auto_week=False)
    continual.set_settings(enabled, live["auto_activate"], live["min_new"], live["minutes"])
    keep = {k: night[k] for k in ("time", "hours", "teacher_tokens", "selfplay", "sizes", "sleep", "evolve", "week")}
    keep.update(curiosity=night["curiosity"] or enabled, lives=night["lives"] or (300 if enabled else 0),
                programs=night["programs"] or enabled)
    try:
        night_cycle.set_settings(enabled, apply=apply and os.name == "nt", **keep)
    except ValueError as error:
        notes.append(str(error))
    if os.name != "nt":
        notes.append("Задачи планировщика ставятся только на Windows")
    return dict(status(), notes=notes)
