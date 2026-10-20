"""Yorika's diary: after each study block a short entry in the first person.

Every number in it is measured: the active version's exams, the night's log, the task ladder,
the archive. The sentences are templates filled with those numbers, not text the model makes
up, so the diary never claims a feeling or a success that did not happen.
"""
from datetime import datetime, timezone

KEEP = 60


def _path():
    from backend import training_center as tc
    return tc.folder() / "diary.json"


def entries():
    from backend import training_center as tc
    return (tc._read(_path(), []) or [])[-KEEP:]


def _mean(values):
    values = [v for v in values if isinstance(v, (int, float))]
    return sum(values) / len(values) if values else None


def _numbers():
    from backend import archive, simworld
    from backend import training_center as tc
    current = tc.active()
    item = next((r for r in tc.runs() if current and r["id"] == current.get("run")), None) or {}
    honesty = item.get("honesty") or {}
    return {"version": item.get("id"), "exam": item.get("exam_per_char"),
            "logic": _mean(((item.get("logic") or {}).get("levels") or {}).values()),
            "sim": _mean((item.get("sim") or {}).values()),
            "honesty": honesty["honest"] / honesty["total"] if honesty.get("total") else None,
            "ladder": sum(simworld.ladder()["levels"].values()), "archive": archive.cells()["filled"]}


def _change(name, now, before, better_low=False, percent=True):
    if now is None:
        return None
    if before is None:
        return "%s: %s" % (name, "%d%%" % round(now * 100) if percent else "%.3f" % now)
    delta = now - before
    if abs(delta) < 1e-9:
        return "%s без изменений" % name
    good = delta < 0 if better_low else delta > 0
    shown = "%+d п.п." % round(delta * 100) if percent else "%+.3f" % delta
    return "%s %s (%s)" % (name, "стала лучше" if good else "стала хуже", shown)


def write(night_entry=None):
    """Adds today's entry and returns it."""
    from backend import planner
    from backend import training_center as tc
    numbers = _numbers()
    previous = (entries() or [{}])[-1].get("numbers", {})
    learned, failed = [], []
    for step in (night_entry or {}).get("steps", []):
        text = step["result"]
        if step["step"] in ("sim", "dreams", "programs", "train") and not any(w in text for w in ("ошибк", "нет ", "выключ")):
            learned.append(text)
        elif any(w in text for w in ("ошибк", "не удал", "не хватило", "упал")):
            failed.append(text)
    changes = [c for c in (
        _change("Логика", numbers["logic"], previous.get("logic")),
        _change("Мир задач", numbers["sim"], previous.get("sim")),
        _change("Честность", numbers["honesty"], previous.get("honesty")),
        _change("Экзамен на символ", numbers["exam"], previous.get("exam"), better_low=True, percent=False)) if c]
    if numbers["ladder"] != previous.get("ladder") and previous.get("ladder") is not None:
        changes.append("на лестнице задач теперь %d ступеней вместо %d" % (numbers["ladder"], previous["ladder"]))
    try:
        from backend.night_cycle import ACTIVITIES
        plan = planner.today()
        wish = "Дальше хочу: %s, потому что %s." % (ACTIVITIES.get(plan["activity"], plan["activity"]).lower(), plan["why"])
    except Exception:  # noqa: BLE001
        wish = None
    lines = []
    if learned:
        lines.append("Чему училась: " + "; ".join(learned[:3]) + ".")
    if changes:
        lines.append("Что изменилось по экзаменам: " + "; ".join(changes) + ".")
    if failed:
        lines.append("Что не получилось: " + "; ".join(failed[:2]) + ".")
    if not lines:
        lines.append("Сегодня я не училась: новых уроков и экзаменов не было.")
    if wish:
        lines.append(wish)
    entry = {"at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "lines": lines, "numbers": numbers}
    tc._write(_path(), (entries() + [entry])[-KEEP:])
    return entry
