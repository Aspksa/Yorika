"""When Yorika studies: a week of hours the owner paints, used by every automatic lesson.

A grid of 7 days × 24 hours. The night cycle starts at the beginning of each painted block and
studies until it ends; quick lessons after conversations start only inside painted hours; lessons
started automatically pause when their block ends and continue in the next one. Lessons you
start yourself are never paused by the schedule.
"""
from datetime import datetime, timedelta

DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
PRESETS = {
    "night": ["0" + "1" * 6 + "0" * 17] * 7,             # 01:00–07:00
    "day": ["0" * 10 + "1" * 6 + "0" * 8] * 7,             # 10:00–16:00
    "evening": ["0" * 18 + "1" * 4 + "0" * 2] * 7,         # 18:00–22:00
    "weekend": ["0" * 24] * 5 + ["1" * 24] * 2,
    "always": ["1" * 24] * 7,
}


def _path():
    from backend import training_center as tc
    return tc.folder() / "schedule.json"


def _from_night():
    """Before the owner paints anything: the night cycle's own start time and length."""
    from backend import night_cycle
    plan = night_cycle.settings()
    start, hours = int(plan["time"][:2]), max(1, round(plan["hours"]))
    row = ["0"] * 24
    for h in range(hours):
        row[(start + h) % 24] = "1"
    return ["".join(row)] * 7


def settings():
    from backend import training_center as tc
    saved = tc._read(_path(), {}) or {}
    grid = saved.get("grid") if valid(saved.get("grid")) else _from_night()
    return {"grid": grid, "enforce": saved.get("enforce", True) is True, "painted": valid(saved.get("grid")),
            "tasks": saved.get("tasks", [])}


def valid(grid):
    return (isinstance(grid, list) and len(grid) == 7 and
            all(isinstance(r, str) and len(r) == 24 and set(r) <= {"0", "1"} for r in grid))


def set_grid(grid, enforce=True):
    from backend import training_center as tc
    if isinstance(grid, str) and grid in PRESETS:
        grid = PRESETS[grid]
    if not valid(grid) or not isinstance(enforce, bool):
        raise ValueError("Расписание: 7 дней по 24 часа")
    saved = tc._read(_path(), {}) or {}
    saved.update(grid=grid, enforce=enforce)
    tc._write(_path(), saved)
    return settings()


def allowed(moment=None, grid=None):
    moment = moment or datetime.now()
    grid = grid or settings()["grid"]
    return grid[moment.weekday()][moment.hour] == "1"


def hours_left(moment=None, grid=None):
    """Hours from now to the end of the painted block, across midnight; 0 outside the schedule."""
    moment = moment or datetime.now()
    grid = grid or settings()["grid"]
    if not allowed(moment, grid):
        return 0.0
    left = 60 - moment.minute
    probe = moment.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    while allowed(probe, grid) and left < 7 * 24 * 60:
        left += 60
        probe += timedelta(hours=1)
    return round(left / 60, 2)


def blocks(grid=None):
    """Painted blocks as (weekday, start hour, length in hours); a block may cross midnight."""
    grid = grid or settings()["grid"]
    flat = "".join(grid)
    if "0" not in flat:
        return [(d, 0, 24) for d in range(7)]
    out = []
    for i in range(168):
        if flat[i] == "1" and flat[i - 1] == "0":
            length = 0
            while flat[(i + length) % 168] == "1" and length < 168:
                length += 1
            out.append((i // 24, i % 24, length))
    return out


def tasks(grid=None):
    """Task Scheduler entries: one per start time and length, with the weekdays it runs on."""
    groups = {}
    for day, hour, length in blocks(grid):
        # A night of study is at most 10 hours; longer blocks get a new start every 10 hours.
        for offset in range(0, length, 10):
            at = day * 24 + hour + offset
            groups.setdefault((at % 24, min(10, length - offset)), []).append(DAYS[(at // 24) % 7])
    return [{"time": "%02d:00" % hour, "hours": float(length), "days": sorted(set(days), key=DAYS.index)}
            for (hour, length), days in sorted(groups.items())]


def summary(grid=None):
    grid = grid or settings()["grid"]
    total = sum(r.count("1") for r in grid)
    return {"hours_week": total, "blocks": len(blocks(grid)), "now": allowed(grid=grid), "left": hours_left(grid=grid)}
