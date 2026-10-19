"""Health check and tidying, run at the start and end of every study block.

The check reads, it does not change: PyTorch, free disk space, lessons that were cut off,
the active version's file, the archive, plans that failed. Each finding says what to do.

Tidying deletes only working copies that no longer serve anything: the resume checkpoint of a
lesson that finished more than a day ago (its best checkpoint, the version itself, stays) and
the grown start file of a finished growth. It never deletes a version, the active one, an
archive elite, or anything of a running lesson or plan.
"""
import shutil
import time

LOW_DISK = 5 * 1024 ** 3
TIDY_AFTER = 24 * 3600


def check():
    from backend import archive, plans
    from backend import training_center as tc
    items = []

    def add(level, text, fix=None):
        items.append({"level": level, "text": text, "fix": fix})

    torch = tc.torch_state()
    if not torch["installed"]:
        add("bad", "PyTorch не установлен: учиться нечем", "Установите его в блоке «Видеокарта»")
    probe = tc._read(tc._system() / "probe.json") or {}
    if torch["installed"] and probe and probe.get("cuda_usable") is False:
        add("warn", "Последняя проверка не нашла видеокарту: уроки пойдут на процессоре медленно", "Нажмите «Проверить видеокарту»")
    try:
        free = shutil.disk_usage(tc.folder()).free
        if free < LOW_DISK:
            add("bad", "На диске осталось %.1f ГБ" % (free / 1024 ** 3), "Освободите место или перенесите папку обучения")
    except OSError:
        free = None
    runs = tc.runs()
    cut = [r["id"] for r in runs if r["state"] == "interrupted"]
    if cut:
        add("warn", "Прерваны уроки: %s" % ", ".join(cut[:3]), "Продолжите их кнопкой «Продолжить» или удалите")
    current = tc.active()
    if current and not (tc.folder() / current["checkpoint"]).is_file():
        add("bad", "Файл активной версии пропал", "Откатитесь или выберите другую версию")
    lost = [c["run"] for c in archive.load()["cells"].values() if not archive._exists(c["run"])]
    if lost:
        add("warn", "В архиве %d версий без файлов" % len(lost), "Они не будут родителями; ничего делать не нужно")
    failed = [p for p in plans.history()[-3:] if p.get("state") == "failed"]
    if failed:
        add("warn", "План не удался: %s" % (failed[-1].get("result") or "")[:120], None)
    if not items:
        add("ok", "Всё в порядке", None)
    worst = "bad" if any(i["level"] == "bad" for i in items) else "warn" if any(i["level"] == "warn" for i in items) else "ok"
    return {"state": worst, "items": items, "free_gb": round(free / 1024 ** 3, 1) if free is not None else None,
            "at": time.time()}


def _protected():
    from backend import archive, plans
    from backend import training_center as tc
    keep = set(archive.elites())
    current = tc.active()
    if current:
        keep.add(current.get("run"))
    plan = plans.current()
    if plan and plan.get("state") in ("preparing", "running"):
        keep.update(r["id"] for r in plan.get("runs", []))
        keep.update(plan.get("round_runs", []))
    return keep


def tidy(now=None):
    """Deletes stale working copies; returns what was deleted and how many bytes were freed."""
    from backend import training_center as tc
    now = now or time.time()
    keep, removed, freed = _protected(), [], 0
    for item in tc.runs():
        if item["id"] in keep or item["state"] not in ("finished", "stopped", "failed") or not item["has_best"]:
            continue
        path = tc._run_dir(item["id"])
        progress = tc._read(path / "progress.json", {}) or {}
        if now - progress.get("t", now) < TIDY_AFTER:
            continue
        for name in ("language-longrun.pt", "grown.pt"):
            target = path / name
            if target.is_file():
                freed += target.stat().st_size
                target.unlink()
                removed.append("%s/%s" % (item["id"], name))
    return {"removed": removed, "freed_mb": round(freed / 1024 ** 2, 1)}
