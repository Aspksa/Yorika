"""Autopilot: one switch for everything Yorika can do by herself, within the limits you set.

On: chat pairs are collected, quick lessons follow conversations, and every painted block of
the week runs the study cycle (practice, programs, the planned training). Off: all of it stops.
It never turns on spending: the teacher's nightly tokens and auto-activation keep your choice.
"""
import os

from backend import continual
from backend import night_cycle
from backend import self_learning as sl


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
