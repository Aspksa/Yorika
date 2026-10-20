"""Study cycle: in the hours the owner painted, Yorika gathers experience, plays, finds programs,
asks the teacher, trains, and takes the exam.

Off until the owner turns it on. On Windows each painted block of the week (backend/schedule.py)
is a Task Scheduler task for the current user. What a block trains is set per weekday: sleep,
copies, branches, learning from her slower self, evolution, a fresh version or rest. The teacher step spends tokens only up to the nightly limit the owner set when turning
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
            "sleep": True, "curiosity": True, "evolve": 0, "week": None, "lives": 300, "programs": True}
ACTIVITIES = {"sleep": "Сон", "distill": "Учёба у себя будущей", "search": "Ветки времени", "swarm": "Копии",
              "evolution": "Эволюция", "fresh": "Новая версия", "rest": "Отдых", "recipes": "Рецепты учёбы",
              "grow": "Рост глубже", "experts": "Рост вширь (эксперты)", "shrink": "Сжатие после роста",
              "hemispheres": "Два полушария", "thoughts": "Язык мыслей", "ecosystem": "Обмен генами",
              "rebirth": "Нейрогенез", "pretrain": "Чтение книг", "coevolve": "Коэволюция задач",
              "redqueen": "Красная Королева", "baldwin": "Эффект Болдуина", "es": "Эволюция весов",
              "dataevo": "Эволюция уроков", "symbiosis": "Эндосимбиоз"}
TASK_PREFIX = "Yorika Study"
EVOLUTION_WEEKDAY = 5  # Saturday night: evolution; other nights: sleep that continues the active version


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def settings():
    saved = tc._read(tc.folder() / "night.json", {}) or {}
    plan = {k: saved.get(k, v) for k, v in DEFAULTS.items()}
    if not _valid_week(plan["week"]):
        # Before the week was planned: sleep every night, evolution on Saturday if it was on.
        plan["week"] = ["evolution" if plan["evolve"] and d == EVOLUTION_WEEKDAY else "sleep" if plan["sleep"] else "fresh"
                        for d in range(7)]
    return plan


def _valid_week(week):
    return isinstance(week, list) and len(week) == 7 and all(a in ACTIVITIES for a in week)


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


def apply_schedule(enabled):
    """Replaces Yorika's Task Scheduler tasks with one per painted block of the week."""
    from backend import schedule
    saved = tc._read(schedule._path(), {}) or {}
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    for name in saved.get("tasks", []) + [TASK_NAME]:
        subprocess.run(["schtasks", "/Delete", "/F", "/TN", name], capture_output=True, creationflags=flags)
    names = []
    if enabled:
        launcher = _launcher()
        for k, item in enumerate(schedule.tasks()):
            name = "%s %d" % (TASK_PREFIX, k + 1)
            result = subprocess.run(["schtasks", "/Create", "/F", "/SC", "WEEKLY", "/D", ",".join(item["days"]),
                                     "/ST", item["time"], "/TN", name, "/TR", '"%s"' % launcher],
                                    capture_output=True, creationflags=flags)
            if result.returncode:
                raise ValueError("Планировщик Windows не принял задачу")
            names.append(name)
    saved["tasks"] = names
    tc._write(schedule._path(), saved)
    return names


def set_settings(enabled, time="02:00", hours=4.0, teacher_tokens=0, selfplay=20, apply=True, sizes=None,
                 sleep=True, curiosity=True, evolve=0, week=None, lives=300, programs=True):
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
    if week is not None and not _valid_week(week):
        raise ValueError("План недели: 7 занятий из списка")
    if type(lives) is not int or not 0 <= lives <= 5000 or not isinstance(programs, bool):
        raise ValueError("Жизней в мире задач от 0 до 5000")
    if apply:
        if os.name != "nt":
            raise ValueError("Учёба по расписанию ставится в планировщик Windows")
        apply_schedule(enabled)
    value = {"enabled": enabled, "time": time, "hours": float(hours), "teacher_tokens": teacher_tokens,
             "selfplay": selfplay, "sizes": sizes, "sleep": sleep, "curiosity": curiosity, "evolve": evolve,
             "week": week, "lives": lives, "programs": programs, "changed": _now()}
    tc._write(tc.folder() / "night.json", value)
    return settings()


def _newest_experience():
    files = sorted((f for f in tc.data_files() if f["name"].startswith("опыт-")), key=lambda f: f["name"])
    return files[-1]["name"] if files else None


def activity(plan=None, moment=None):
    plan = plan or settings()
    return plan["week"][(moment or datetime.now()).weekday()]


def _train(plan, name, launch, hours=None):
    """Today's activity from the week plan: sleep, copies, branches, future self, evolution..."""
    hours = hours or plan["hours"]
    what = activity(plan)
    choice = None
    from backend import autopilot, planner
    if autopilot.settings()["auto_week"] and what != "rest":
        # She picks tonight's activity from measurements; rest days of the week plan stay rest.
        choice = planner.today(what)
        what = choice["activity"]
    result = _start_activity(what, choice, plan, name, launch, hours)
    if choice:
        planner.done(choice)
        result = "сама выбрала «%s», потому что %s; %s" % (ACTIVITIES[what], choice["why"], result)
    return result


def _start_activity(what, choice, plan, name, launch, hours):
    if what == "rest":
        return "сегодня отдых по плану недели"
    current = tc.active()
    if what == "ecosystem":
        return _ecosystem(current)
    if what == "pretrain":
        started = tc.start("pretrain", device=_device(current["run"]) if current else "cuda", total_steps=1000000,
                           hours=hours, launch=launch, scheduled=True)
        return "чтение книг %s на %s ч: сначала язык, потом диалоги" % (started["id"], hours)
    if what in ("swarm", "search", "distill", "recipes", "shrink", "hemispheres", "thoughts", "coevolve", "redqueen", "baldwin",
                "es", "dataevo", "symbiosis"):
        from backend import plans
        if not current:
            raise ValueError("нет активной версии для «%s»" % ACTIVITIES[what])
        rounds = 2 if what in ("search", "distill") else 1
        lessons = {"swarm": 5, "search": 3 * rounds, "distill": rounds, "recipes": 3, "shrink": 1, "hemispheres": 1,
                   "thoughts": 1, "coevolve": 1, "redqueen": 2, "baldwin": 3, "es": 1, "dataevo": 1, "symbiosis": 1}[what]
        minutes = max(5, min(240, round(hours * 60 / lessons)))
        started = plans.start(what, minutes=minutes, rounds=rounds, launch=launch, scheduled=True, branches=3,
                              teacher=(choice or {}).get("teacher"))
        return "%s: план %s, по %d мин на урок" % (ACTIVITIES[what], started["id"], minutes)
    if what in ("grow", "experts", "rebirth"):
        from backend import planner, plans
        if not current:
            raise ValueError("нет активной версии, чтобы расти")
        grow = (choice or {}).get("grow")
        if not grow:
            if what == "experts":
                change = planner.expert_change(planner._active_item())
                if not change:
                    raise ValueError("эксперты загружены ровно или их нет: расти вширь незачем")
                grow = {"from": current["run"], "experts": change}
            elif what == "rebirth":
                grow = {"from": current["run"], "rebirth": True}
            else:
                grow = {"from": current["run"], "layers": 2}
        records = plans._experience()
        if name:
            from backend import continual
            records = continual.sleep_set(name)[0]
        if len(records) < 20:
            raise ValueError("для роста нужно хотя бы 20 примеров, сейчас %d" % len(records))
        started = tc.start("long", device=_device(current["run"]), total_steps=1000000, hours=hours,
                           kind="rebirth" if grow.get("rebirth") else "grow",
                           grow=grow, records=records, dataset=name, launch=launch, scheduled=True)
        if grow.get("rebirth"):
            born = tc._read(tc._run_dir(started["id"]) / "reborn.json", {}) or {}
            return "нейрогенез %s: заново родились %d молчавших нейронов" % (started["id"], born.get("total", 0))
        how = ("+%d эксперта" % grow["experts"] if grow.get("experts", 0) > 0 else "%d эксперта" % grow["experts"]) \
            if grow.get("experts") else "+%d слоя" % grow.get("layers", 2)
        return "рост %s (%s) из %s" % (started["id"], how, grow["from"])
    if not name:
        raise ValueError("нет файла опыта")
    if current and what == "sleep":
        # Sleep: the active version relives the day mixed with older examples and continues.
        from backend import continual
        records, mix = continual.sleep_set(name)
        config = dict(tc._read(tc._run_dir(current["run"]) / "run.json")["config"])
        from backend import recipes
        config["lr"], config["rule"] = recipes.learning_rate(), recipes.learning_rule()
        started = tc.start("long", device=continual._device(current["run"]), total_steps=1000000,
                           hours=hours, config=config, kind="sleep", init=current["checkpoint"],
                           records=records, dataset=name, launch=launch, scheduled=True)
        return "сон %s: новых %d, повтор старого %d, всего %d" % (started["id"], mix["new"], mix["replay"], len(records))
    blocker = tc.long_gate(tc._load_records(name))
    if blocker:
        raise ValueError(blocker)
    if what == "evolution":
        population = plan["evolve"] or 4
        each = round(hours / population, 2)
        started = tc.start_evolution(name, population, device="cuda", total_steps=1000000, hours_each=each,
                                     launch=launch)
        return "эволюция %s: %d вариантов по %s ч" % (started["series"], population, each)
    sizes = plan["sizes"] if isinstance(plan["sizes"], list) and plan["sizes"] else ["s"]
    if len(sizes) > 1:
        each = round(hours / len(sizes), 2)
        started = tc.start_series(name, sizes, device="cuda", total_steps=1000000, hours_each=each, launch=launch)
        return "песочница %s: размеры %s, по %s ч" % (started["series"], "/".join(sizes).upper(), each)
    started = tc.start("long", dataset=name, device="cuda", total_steps=1000000, hours=hours,
                       launch=launch, size=sizes[0], scheduled=True)
    return "запущено обучение %s на %s ч" % (started["id"], hours)


def _ecosystem(current):
    """Gene exchange with versions of the same line; the new version takes every exam."""
    from backend import continual, mind
    if not current:
        raise ValueError("нет активной версии для обмена генами")
    donors = mind.donors(current["run"])
    if not donors:
        return "обменяться не с кем: нет версий того же устройства и словаря"
    info = tc._read(tc._run_dir(current["run"]) / "run.json")
    records = tc._read(tc._run_dir(current["run"]) / "dataset.json") if info.get("internal") else tc._load_records(info["dataset"])
    run_id, made = mind.exchange(current["run"], donors, tc._prepare(records)["validation"])
    if not run_id:
        return "обмен генами: ни один чужой блок не улучшил экзамен, всё осталось как было"
    tc.exam_worker(run_id)
    verdict = continual.judge(run_id)
    return "обмен генами %s: взято блоков %d, итог: %s" % (run_id, len(made["taken"]), verdict["why"])


def _device(run_id):
    return (tc._read(tc._run_dir(run_id) / "run.json") or {}).get("device", "cuda")


def run(launch=True, opener=None):
    """One night. Each step writes what happened; a failed step does not hide the others."""
    plan = settings()
    entry = {"started": _now(), "steps": []}

    def step(name, result):
        entry["steps"].append({"step": name, "result": result})

    if not plan["enabled"]:
        step("cycle", "выключен")
    else:
        from backend import schedule
        hours = min(10.0, schedule.hours_left()) or plan["hours"]
        try:
            from backend import health
            report = health.check()
            step("health", "; ".join(i["text"] for i in report["items"])[:300])
        except Exception as error:  # noqa: BLE001
            step("health", str(error)[:160])
        try:
            resumed = tc.resume_scheduled()
            if resumed:
                step("resume", "продолжаю урок %s с места паузы" % resumed[0])
        except Exception as error:  # noqa: BLE001
            step("resume", str(error)[:160])
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
        if plan["lives"]:
            try:
                step("sim", _sim_lives(plan["lives"]))
            except Exception as error:  # noqa: BLE001
                step("sim", str(error)[:160])
        try:
            from backend import dreams
            step("dreams", dreams.night_step())
        except Exception as error:  # noqa: BLE001
            step("dreams", str(error)[:160])
        if plan["programs"]:
            try:
                step("programs", _programs())
            except Exception as error:  # noqa: BLE001
                step("programs", str(error)[:160])
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
            if tc._active_job():
                raise ValueError("урок уже идёт")
            step("train", _train(plan, _newest_experience(), launch, hours))
        except Exception as error:  # noqa: BLE001
            step("train", str(error)[:160])
        try:
            step("compress", _compress_active())
        except Exception as error:  # noqa: BLE001
            step("compress", str(error)[:160])
        try:
            from backend import autopilot, health
            if autopilot.settings()["tidy"]:
                done = health.tidy()
                step("tidy", "удалено рабочих копий %d, освобождено %.1f МБ" % (len(done["removed"]), done["freed_mb"])
                     if done["removed"] else "убирать нечего")
            else:
                step("tidy", "уборка выключена")
        except Exception as error:  # noqa: BLE001
            step("tidy", str(error)[:160])
    if plan["enabled"]:
        try:
            from backend import diary
            diary.write(entry)
            step("diary", "запись в дневнике сделана")
        except Exception as error:  # noqa: BLE001
            step("diary", str(error)[:160])
    entry["finished"] = _now()
    history = log() + [entry]
    tc._write(tc.folder() / "night-log.json", history[-14:])
    return entry


def _sim_lives(lives):
    """Free practice in the game world; verified own solutions and program hints join experience."""
    from backend import curiosity, simworld
    from backend.neural_language_benchmark import load_candidate
    checkpoint = sl._scoring_checkpoint()
    if checkpoint is None:
        return "нет обученной версии: мир задач ждёт"
    result = simworld.live(load_candidate(checkpoint), lives, level=simworld.ladder()["levels"])
    total = simworld.record(result["stats"])
    moves = simworld.climb(result["stats"])
    added = curiosity._add(result["own"] + result["hints"][:max(20, lives // 5)], "sim")
    wins = sum(s["wins"] for s in result["stats"].values())
    climbed = "; лестница: " + ", ".join("%s %d→%d" % (simworld.ENVS[m["env"]][0], m["from"], m["to"]) for m in moves) if moves else ""
    return "прожито %d жизней, побед %d, всего жизней %d, в опыт добавлено %d%s" % (lives, wins, total["lives"], added, climbed)


def _programs():
    """New skills found by program search join the library; lessons teach how to call them."""
    from backend import curiosity, programs
    found = programs.learn()
    if not found:
        return "новых навыков нет, в библиотеке %d" % len(programs.library())
    added = curiosity._add(programs.lessons(found), "programs")
    return "найдены программы: %s; уроков %d" % (", ".join(found), added)


def _compress_active():
    """When the chat answers with the compressed copy, the active version is compressed for it."""
    from backend import brain
    current = tc.active()
    if not current or not brain.engine()["compressed"]:
        return "не нужно"
    target = tc.folder() / current["checkpoint"]
    if target.with_name(target.name[:-3] + ".q4.pt").is_file():
        return "сжатая копия уже есть"
    result = tc.compress(current["run"])
    return "сжата активная версия: %d КБ" % (result["bytes"] // 1024)


def status():
    from backend import schedule
    return {"settings": settings(), "log": log(), "windows": os.name == "nt", "activities": ACTIVITIES,
            "schedule": dict(schedule.settings(), **schedule.summary()), "today": activity(),
            "note": "Ноутбук должен быть включён и на зарядке; из сна он сам не просыпается"}
