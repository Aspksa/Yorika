"""Self-check: one button that tries every part of the study machinery on this computer.

It trains a tiny throwaway version for about a minute (on the video card when there is one),
takes the exams, plays a few lives of the game world, searches one program, checks the study
schedule and the Task Scheduler, and writes a report you can copy and send. Each step reports
its own result and time; a failed step does not hide the others. The throwaway version is
deleted afterwards; nothing else is changed, nothing is activated.
"""
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

TINY = {"width": 64, "heads": 4, "layers": 2, "context": 192, "max_merges": 256, "seed": 7, "checkpoint_every": 20,
        "batch_size": 8, "accumulate": 1, "precision": "auto", "arch": {"lab": True, "loops": 2, "experts": 2, "memory": 64}}
SECONDS = 60


def _path():
    from backend import training_center as tc
    return tc.folder() / "selfcheck.json"


def last():
    from backend import training_center as tc
    return tc._read(_path())


def start(launch=True):
    from backend import training_center as tc
    current = last() or {}
    if current.get("state") == "running" and time.time() - current.get("t", 0) < 1800:
        raise ValueError("Самопроверка уже идёт")
    if tc._active_job():
        raise ValueError("Сейчас идёт обучение: самопроверка мешала бы ему, дождитесь конца")
    tc._write(_path(), {"state": "running", "t": time.time(), "steps": [], "started": _now()})
    if launch:
        tc._spawn([sys.executable, str(tc.CLI), "selfcheck-worker"], tc.folder() / "selfcheck.log")
    return last()


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _records():
    """Synthetic, varied dialogues: enough to train for a minute, never a real corpus."""
    from backend import logic, simworld
    import random
    rng = random.Random(1)
    out = [{"prompt": "Сколько будет %d плюс %d?" % (a, b), "answer": "%d плюс %d будет %d." % (a, b, a + b)}
           for a in range(1, 13) for b in range(1, 13)]
    out += [{"prompt": t["q"], "answer": t["solution"]} for t in simworld.fresh(rng, 60)]
    out += [{"prompt": q, "answer": a} for q, a in logic.lessons(1, 60, seed=3)]
    seen, records = set(), []
    for r in out:
        if r["prompt"] not in seen and len(r["prompt"]) + len(r["answer"]) <= 300:
            seen.add(r["prompt"])
            records.append(dict(r, source="selfcheck", license="synthetic", consent=True, rights_reviewed_by="selfcheck",
                                quality_reviewed=True))
    return records


def run(device=None, seconds=SECONDS):
    """Runs every step and returns the report (also saved as selfcheck.json)."""
    from backend import training_center as tc
    report = {"state": "running", "t": time.time(), "started": _now(), "steps": [],
              "machine": {"os": platform.platform(), "python": platform.python_version(), "windows": os.name == "nt"}}
    tc._write(_path(), report)
    box = {}

    def step(name, title, work):
        began = time.monotonic()
        entry = {"step": name, "title": title}
        try:
            entry.update(ok=True, detail=work())
        except Exception as error:  # noqa: BLE001 - the report shows every failure
            entry.update(ok=False, detail=str(error)[:240] or type(error).__name__)
        entry["seconds"] = round(time.monotonic() - began, 1)
        report["steps"].append(entry)
        report["t"] = time.time()
        tc._write(_path(), report)
        return entry["ok"]

    def torch_step():
        state = tc.torch_state()
        if not state["installed"]:
            raise ValueError("PyTorch не установлен")
        import torch
        box["cuda"] = torch.cuda.is_available()
        report["machine"].update(torch=state["version"], cuda=box["cuda"],
                                 gpu=torch.cuda.get_device_name(0) if box["cuda"] else None,
                                 vram_gb=round(torch.cuda.get_device_properties(0).total_memory / 1024 ** 3, 1) if box["cuda"] else None)
        return "PyTorch %s, %s" % (state["version"], "видеокарта %s" % report["machine"]["gpu"] if box["cuda"] else "видеокарты нет, только процессор")

    def disk_step():
        probe = tc.folder() / ".selfcheck-write"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        free = shutil.disk_usage(tc.folder()).free / 1024 ** 3
        if free < 2:
            raise ValueError("Свободно всего %.1f ГБ" % free)
        return "папка %s пишется, свободно %.1f ГБ" % (tc.folder(), free)

    def train_step():
        use = device or ("cuda" if box.get("cuda") else "cpu")
        config = dict(TINY, precision="auto" if use == "cuda" else "fp32")
        started = tc.start("long", device=use, total_steps=100000, hours=0.02, config=config, kind="selfcheck",
                           records=_records(), dataset="(самопроверка)", launch=False)
        box["run"] = started["id"]
        info = tc._read(tc._run_dir(started["id"]) / "run.json")
        info["time_limit"] = seconds
        tc._write(tc._run_dir(started["id"]) / "run.json", info)
        tc.worker(started["id"])
        item = tc._summary(tc._run_dir(started["id"]))
        if item["state"] != "finished":
            raise ValueError(item.get("error") or "урок закончился в состоянии %s" % item["state"])
        report["machine"]["peak_vram_mb"] = round((item.get("peak_vram") or 0) / 1024 ** 2) or None
        return "%d шагов за %d с на %s (%.1f примеров/с), точность %s, экзамен %s" % (
            item["steps"], item["elapsed"], "видеокарте" if use == "cuda" else "процессоре", item.get("examples_speed") or 0,
            info["config"]["precision"], item.get("exam_per_char"))

    def exams_step():
        item = tc._summary(tc._run_dir(box["run"]))
        missing = [k for k in ("logic", "honesty", "sim", "introspection") if not item.get(k)]
        if missing:
            raise ValueError("нет экзаменов: %s" % ", ".join(missing))
        return "логика, честность, мир задач и взгляд внутрь посчитаны (крошечная модель, оценки близки к нулю — так и должно быть)"

    def world_step():
        from backend import simworld
        from backend.neural_language_benchmark import load_candidate
        result = simworld.live(load_candidate(tc._run_dir(box["run"]) / "language-longrun.pt.best.pt"), 10)
        return "прожито 10 жизней, побед %d" % sum(s["wins"] for s in result["stats"].values())

    def programs_step():
        from backend import programs
        found = programs.discover("периметр", seed=1)
        if not found["found"]:
            raise ValueError(found["why"])
        return "найдена формула %s" % programs.pretty(found["expr"], ["a", "b"])

    def schedule_step():
        from backend import night_cycle, schedule
        plan = schedule.settings()
        text = "часов учёбы в неделю: %d, задач планировщика по расписанию: %d" % (
            sum(r.count("1") for r in plan["grid"]), len(schedule.tasks(plan["grid"])))
        if os.name == "nt" and night_cycle.settings()["enabled"]:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            missing = [n for n in plan.get("tasks", [])
                       if subprocess.run(["schtasks", "/Query", "/TN", n], capture_output=True, creationflags=flags).returncode]
            if missing:
                raise ValueError("в планировщике Windows нет задач: %s; включите учёбу по расписанию заново" % ", ".join(missing))
            text += ", задачи в планировщике на месте"
        elif os.name != "nt":
            text += " (не Windows: планировщик не проверялся)"
        return text

    def tidy_step():
        if box.get("run"):
            shutil.rmtree(tc._run_dir(box["run"]), ignore_errors=True)
        return "пробная версия удалена"

    step("torch", "PyTorch и видеокарта", torch_step)
    step("disk", "Папка обучения и диск", disk_step)
    if step("train", "Урок на минуту", train_step):
        step("exams", "Экзамены", exams_step)
        step("world", "Мир задач", world_step)
    step("programs", "Поиск программы", programs_step)
    step("schedule", "Расписание и планировщик", schedule_step)
    step("tidy", "Уборка за собой", tidy_step)
    report.update(state="finished", finished=_now(), ok=all(s["ok"] for s in report["steps"]))
    report["text"] = as_text(report)
    tc._write(_path(), report)
    return report


def as_text(report):
    m = report.get("machine", {})
    lines = ["Самопроверка Yorika %s" % report.get("finished", ""),
             "Система: %s, Python %s, PyTorch %s" % (m.get("os"), m.get("python"), m.get("torch")),
             "Видеокарта: %s%s" % (m.get("gpu") or "нет", ", %s ГБ, пик %s МБ" % (m.get("vram_gb"), m.get("peak_vram_mb")) if m.get("gpu") else "")]
    for s in report.get("steps", []):
        lines.append("%s %s (%s с): %s" % ("✓" if s["ok"] else "✗", s["title"], s["seconds"], s["detail"]))
    return "\n".join(lines)
