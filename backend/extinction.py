"""Mass extinction: when evolution is stuck, the weak half goes and bold mutants take its place.

A plateau is when the last eight versions that reached the archive all failed to enter it, or
when six mutation generations in a row brought nothing. Then the page offers an extinction:
the weaker half of the trained versions (by the same archive score) is deleted from the disk,
and the next three generations mutate at full strength.

It never happens by itself: the owner sees the list and confirms by typing a word, every
time. Never deleted: the active version and the versions it was activated from, its ancestors,
the best of every archive cell, members of young protected species, versions still training or
waiting for a decision, and anything a running plan uses.
"""
import shutil
from datetime import datetime, timezone

WINDOW = 8


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _path():
    from backend import training_center as tc
    return tc.folder() / "extinction.json"


def history():
    from backend import training_center as tc
    return (tc._read(_path(), []) or [])[-10:]


def plateau():
    from backend import archive, mutation
    log = [e for e in archive.load()["log"]][-WINDOW:]
    stuck_archive = len(log) >= WINDOW and not any("вошла в архив" in (e.get("result") or "") for e in log)
    m = mutation.status()
    if stuck_archive:
        return {"plateau": True, "why": "последние %d версий не смогли войти в архив" % WINDOW}
    if m["plateau"]:
        return {"plateau": True, "why": "%d поколений мутаций подряд без улучшения" % m["streak"]}
    return {"plateau": False, "why": "эволюция ещё находит улучшения"}


def _lineage(run_id):
    from backend import training_center as tc
    seen = set()
    while run_id and run_id not in seen:
        seen.add(run_id)
        try:
            info = tc._read(tc._run_dir(run_id) / "run.json", {}) or {}
        except ValueError:
            break
        run_id = info.get("parent") or info.get("grown_from")
    return seen


def _kept():
    from backend import archive, plans, species
    from backend import training_center as tc
    keep = set()
    current = tc.active()
    if current and current.get("run"):
        keep |= _lineage(current["run"])
    for entry in tc._read(tc.folder() / "active-history.json", []) or []:
        run = (entry.get("meta") or {}).get("run")
        if run:
            keep |= _lineage(run)
    keep |= {c["run"] for c in archive.load()["cells"].values()}
    keep |= species.protected_runs()
    plan = plans.current() or {}
    if plan.get("state") in ("preparing", "running"):
        keep |= {r["id"] for r in plan.get("runs", [])}
        keep |= {plan.get("partner"), plan.get("teacher"), plan.get("student")}
    return keep


def candidates():
    """The weaker half of trained dialogue versions, minus everything that must stay."""
    from backend import archive
    from backend import training_center as tc
    population = []
    for item in tc.runs():
        if item["mode"] != "long" or not item["has_best"] or item["state"] not in ("finished", "stopped"):
            continue
        score = archive.fitness(item)
        if score is None or (item.get("verdict") or {}).get("result") == "waiting":
            continue
        population.append((score, item))
    population.sort(key=lambda p: p[0])
    keep = _kept()
    out = []
    for score, item in population[:len(population) // 2]:
        if item["id"] in keep:
            continue
        size = sum(f.stat().st_size for f in tc._run_dir(item["id"]).rglob("*") if f.is_file())
        out.append({"run": item["id"], "fitness": score, "mb": round(size / 1e6, 1)})
    return out


def preview():
    found = candidates()
    return dict(plateau(), candidates=found, count=len(found), mb=round(sum(c["mb"] for c in found), 1))


def run(confirm=False, expect=None):
    """Deletes the weak half shown by preview(). `expect` must equal the number shown, so nothing
    is deleted that the owner did not see."""
    from backend import archive, mutation, plans, species
    from backend import training_center as tc
    if confirm is not True:
        raise ValueError("Вымирание только с вашего подтверждения")
    if tc._active_job() or plans.busy():
        raise ValueError("Сначала дождитесь конца обучения или нажмите «Стоп всё»")
    found = candidates()
    if type(expect) is not int or expect != len(found):
        raise ValueError("Список изменился: откройте его заново")
    if not found:
        raise ValueError("Удалять некого: все версии нужны")
    removed, freed = [], 0.0
    for c in found:
        try:
            shutil.rmtree(tc._run_dir(c["run"]))
            removed.append(c["run"])
            freed += c["mb"]
        except (OSError, ValueError):
            continue
    data = archive.load()
    data["cells"] = {k: v for k, v in data["cells"].items() if v["run"] not in removed}
    data["log"].append({"run": "вымирание", "at": _now(), "cell": "", "fitness": None,
                        "result": "удалено %d слабых версий, следующие 3 поколения — смелые мутанты" % len(removed)})
    archive._save(data)
    species.forget(removed)
    mutation.boost(3)
    entry = {"at": _now(), "removed": removed, "freed_mb": round(freed, 1), "why": plateau()["why"]}
    tc._write(_path(), (history() + [entry])[-10:])
    return entry


def status():
    try:
        found = candidates()
    except Exception as error:  # noqa: BLE001 - a broken run folder never hides the page
        found, error_text = [], str(error)[:120]
    else:
        error_text = None
    return dict(plateau(), count=len(found), mb=round(sum(c["mb"] for c in found), 1), history=history()[-3:], error=error_text)
