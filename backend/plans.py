"""Three ways to learn that only a machine has, run as plans of several short lessons.

Copies (swarm): several copies of the active version each learn one skill (logic, the game
world, programs, tools, your conversations). Each copy is examined on its own skill; only
copies that got better there and did not get worse in general are merged back, and only their
strongest changes (TIES merging: trim small changes, agree on a sign, average). One Yorika comes
out, and she takes every exam.

Branches (search): from the same moment several lessons run with different seeds and learning
rates. The best on the exam becomes the new starting point and the others are thrown away, like
going back in time and taking another path. If no branch beats the start, the plan goes back
to the start and stops.

Future self (distill): the slow version of Yorika (five drafts, every pass, checked) answers
questions; only answers the program confirms, or that most drafts agree on, are kept; the fast
version (one draft) learns to answer like that. Repeated, each student becomes the next teacher.

Nothing here activates a version by itself, except through «включать сама, если не хуже».
"""
import random
import sys
import time
from datetime import datetime, timezone

from backend import self_learning as sl
from backend import training_center as tc

KINDS = ("swarm", "search", "distill")
SKILLS = ("logic", "sim", "programs", "tools", "experience")
SKILL_NAMES = {"logic": "логика", "sim": "мир задач", "programs": "программы", "tools": "инструменты",
               "experience": "ваши разговоры"}
LRS = (0.0001, 0.0003, 0.0006, 0.0002, 0.0004, 0.0008)
TRIM = 0.2


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _path():
    return tc.folder() / "plan.json"


def current():
    return tc._read(_path())


def history():
    return (tc._read(tc.folder() / "plans-log.json", []) or [])[-10:]


def _save(plan):
    tc._write(_path(), plan)


def _note(plan, text):
    plan.setdefault("log", []).append({"at": _now(), "text": text})
    plan["log"] = plan["log"][-40:]
    _save(plan)


def _end(plan, state, result):
    plan.update(state=state, result=result, finished=_now(), queue=[])
    _note(plan, result)
    tc._write(tc.folder() / "plans-log.json", (history() + [{k: plan.get(k) for k in (
        "id", "kind", "state", "result", "created", "finished", "runs")}])[-10:])
    return plan


def busy():
    plan = current()
    return bool(plan and plan.get("state") in ("preparing", "running"))


# ---- datasets ----------------------------------------------------------------

def _experience(limit=None, seed=0):
    from backend import continual
    banned = tc.protected_prompts()
    items = [i for i in continual._ready(sl._load()["items"]) if i["prompt"].casefold().strip() not in banned]
    random.Random(seed).shuffle(items)
    return [continual._record(i) for i in items[:limit]]


def _synthetic(pairs, source):
    banned = tc.protected_prompts()
    seen, out = set(), []
    for prompt, answer in pairs:
        key = prompt.casefold().strip()
        if key in banned or key in seen:
            continue
        seen.add(key)
        out.append({"prompt": prompt, "answer": answer, "source": source, "license": "synthetic",
                    "consent": True, "rights_reviewed_by": "owner", "quality_reviewed": True})
    return out


def skill_set(skill, seed=0):
    """Lessons for one copy: its skill, plus as many of your examples so it does not forget."""
    from backend import curiosity, logic, programs, simworld, tools
    if skill == "logic":
        own = _synthetic(logic.lessons(min(5, curiosity.logic_frontier() + 1), 80, seed=seed + 7), "logic")
    elif skill == "sim":
        own = _synthetic(simworld.lessons(200, seed=seed + 11), "sim")
    elif skill == "programs":
        if not programs.library():
            programs.learn(seed)
        own = _synthetic(programs.lessons(per_skill=25, seed=seed + 5), "programs")
    elif skill == "tools":
        own = _synthetic(tools.lessons(150, seed=seed + 3), "tools")
    elif skill == "experience":
        return _experience(seed=seed)
    else:
        raise ValueError("Неизвестный навык")
    keys = {r["prompt"].casefold().strip() for r in own}
    replay = [r for r in _experience(len(own), seed) if r["prompt"].casefold().strip() not in keys]
    return own + replay


def skill_score(skill, loaded, test=None):
    """Higher is better for every skill."""
    from backend import honesty, logic, programs, simworld
    from backend.neural_language_longrun import score_checkpoint
    if skill == "logic":
        return round(sum(logic.exam(loaded)["levels"].values()) / len(logic.LEVELS), 4)
    if skill == "sim":
        scores = simworld.exam(loaded)
        return round(sum(scores.values()) / len(scores), 4)
    if skill == "programs":
        return programs.exam(loaded)
    if skill == "tools":
        return _tools_exam(loaded)
    if skill == "honesty":
        h = honesty.exam(loaded)
        return round(h["honest"] / h["total"], 4)
    return round(-score_checkpoint(None, test, loaded=loaded)["per_char"], 4)


def _tools_exam(loaded):
    from backend.brain import generate
    from backend.tools import calc, run_tools
    rng = random.Random(400_000)
    model, state = loaded
    ok = 0
    for _ in range(12):
        a, b = rng.randint(100, 999), rng.randint(2, 99)
        text = generate(model, state, "Сколько будет %d умножить на %d?" % (a, b), 48)["text"]
        try:
            ok += calc("%d*%d" % (a, b)) in run_tools(text)[0]
        except Exception:  # noqa: BLE001 - a broken call is a wrong answer
            pass
    return round(ok / 12, 4)


# ---- start ------------------------------------------------------------------

def start(kind, *, copies=None, branches=3, rounds=2, minutes=20, prompts=120, device=None, launch=True,
          scheduled=False):
    if kind not in KINDS:
        raise ValueError("Неизвестный план")
    current_brain = tc.active()
    if not current_brain:
        raise ValueError("Сначала сделайте активной одну из версий")
    if busy():
        raise ValueError("План уже идёт: дождитесь конца или нажмите «Стоп всё»")
    if tc._active_job():
        raise ValueError("Обучение уже идёт")
    if type(minutes) not in (int, float) or not 1 <= minutes <= 240:
        raise ValueError("Урок от 1 до 240 минут")
    plan = {"id": datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"), "kind": kind, "state": "preparing",
            "created": _now(), "base": current_brain, "minutes": minutes, "round": 0, "queue": [], "runs": [],
            "device": device or _device(current_brain["run"]), "log": [], "scheduled": scheduled is True,
            "launch": launch}
    if kind == "swarm":
        copies = list(copies or SKILLS)
        if not 2 <= len(copies) <= 6 or len(set(copies)) != len(copies) or any(c not in SKILLS for c in copies):
            raise ValueError("Выберите от 2 до 6 разных навыков")
        plan["copies"] = copies
    elif kind == "search":
        if type(branches) is not int or not 2 <= branches <= 6 or type(rounds) is not int or not 1 <= rounds <= 5:
            raise ValueError("Веток от 2 до 6, раундов от 1 до 5")
        plan.update(branches=branches, rounds=rounds)
    else:
        if type(rounds) is not int or not 1 <= rounds <= 5 or type(prompts) is not int or not 20 <= prompts <= 1000:
            raise ValueError("Раундов от 1 до 5, вопросов от 20 до 1000")
        plan.update(rounds=rounds, prompts=prompts)
    _save(plan)
    _note(plan, "план создан")
    if launch:
        tc._spawn([sys.executable, str(tc.CLI), "plan-worker"], tc.folder() / "plan.log")
    return plan


def _device(run_id):
    return (tc._read(tc._run_dir(run_id) / "run.json") or {}).get("device", "cuda")


def worker():
    """Detached: prepares the first round (datasets can take minutes) and starts it."""
    plan = current()
    if not plan or plan.get("state") != "preparing":
        return 0
    try:
        _prepare_round(plan)
        _next(plan)
    except Exception as error:  # noqa: BLE001 - the page shows why the plan stopped
        _end(plan, "failed", str(error)[:200])
        return 1
    return 0


def _config(init_run):
    return dict(tc._read(tc._run_dir(init_run) / "run.json")["config"])


def _prepare_round(plan):
    plan["round"] += 1
    base_run, base_ckpt = plan.get("init_run") or plan["base"]["run"], plan.get("init") or plan["base"]["checkpoint"]
    config = _config(base_run)
    queue = []
    if plan["kind"] == "swarm":
        for k, skill in enumerate(plan["copies"]):
            records = skill_set(skill, seed=k)
            if len(records) < 20:
                _note(plan, "копия «%s» пропущена: примеров %d" % (SKILL_NAMES[skill], len(records)))
                continue
            queue.append({"label": "копия: " + SKILL_NAMES[skill], "skill": skill, "records": records,
                          "config": dict(config, seed=config["seed"] + 101 * (k + 1)), "kind": "copy"})
        if len(queue) < 2:
            raise ValueError("Для роя нужно хотя бы две копии с данными (одобрите опыт или уроки)")
    elif plan["kind"] == "search":
        records = _experience(seed=plan["round"])
        if len(records) < 20:
            raise ValueError("Для ветвей нужно хотя бы 20 одобренных примеров, сейчас %d" % len(records))
        for k in range(plan["branches"]):
            lr = LRS[k % len(LRS)]
            queue.append({"label": "ветка %d · шаг обучения %g" % (k + 1, lr), "records": records, "kind": "branch",
                          "config": dict(config, seed=config["seed"] + 1000 * plan["round"] + k, lr=lr)})
    else:
        records, made = distill_set(tc.folder() / base_ckpt, plan["prompts"], seed=plan["round"])
        plan["made"] = made
        if made["kept"] < 10:
            raise ValueError("Медленная я ещё слишком слаба: проверенных ответов %d из %d" % (made["kept"], made["asked"]))
        queue.append({"label": "раунд %d: быстрая учится у медленной" % plan["round"], "records": records,
                      "kind": "distill", "config": config})
        _note(plan, "медленная версия ответила: оставлено %d из %d (программа подтвердила или черновики согласны)" % (
            made["kept"], made["asked"]))
    folder = tc.folder() / "plan"
    folder.mkdir(parents=True, exist_ok=True)
    for k, item in enumerate(queue):
        # Datasets live in files: plan.json stays small enough to read on every page refresh.
        item["init"] = base_ckpt
        item["records_file"] = "plan/r%d-%d.json" % (plan["round"], k)
        tc._write(tc.folder() / item["records_file"], item.pop("records"))
    plan["queue"], plan["state"] = queue, "running"
    plan["round_runs"] = []
    _save(plan)


def _next(plan):
    """Starts the next queued lesson; returns its run id or None when the round is over."""
    while plan["queue"]:
        item = plan["queue"].pop(0)
        launch = plan.get("launch", True)
        for attempt in range(3):
            try:
                run = tc.start("long", device=plan["device"], total_steps=1000000, hours=plan["minutes"] / 60,
                               config=item["config"], kind=item["kind"], init=item["init"],
                               records=tc._read(tc.folder() / item["records_file"]),
                               dataset="(%s)" % item["label"], launch=launch, scheduled=plan.get("scheduled", False))
                break
            except ValueError as error:
                if "секунду" not in str(error) or attempt == 2:
                    raise
                time.sleep(1.1)
        entry = {"id": run["id"], "label": item["label"], "skill": item.get("skill"), "round": plan["round"]}
        plan["runs"].append(entry)
        plan["round_runs"].append(run["id"])
        _save(plan)
        return run["id"]
    return None


# ---- after every lesson -------------------------------------------------------

def on_finished(run_id):
    """Called by the training worker when a run ends. Moves the plan on."""
    plan = current()
    if not plan or plan.get("state") != "running" or run_id not in plan.get("round_runs", []):
        return None
    try:
        if _next(plan):
            return plan
        if plan["kind"] == "swarm":
            return _finish_swarm(plan)
        if plan["kind"] == "search":
            return _finish_search_round(plan)
        return _finish_distill_round(plan)
    except Exception as error:  # noqa: BLE001
        return _end(plan, "failed", str(error)[:200])


def on_stopped(run_id, why):
    plan = current()
    if plan and plan.get("state") == "running" and run_id in plan.get("round_runs", []):
        _end(plan, "stopped", why)


def stop():
    plan = current()
    if plan and plan.get("state") in ("preparing", "running"):
        _end(plan, "stopped", "Остановлено кнопкой «Стоп всё»")


def _load(run_id):
    from backend.neural_language_benchmark import load_candidate
    return load_candidate(tc._run_dir(run_id) / "language-longrun.pt.best.pt")


def _base_test(plan):
    info = tc._read(tc._run_dir(plan["base"]["run"]) / "run.json")
    records = tc._read(tc._run_dir(plan["base"]["run"]) / "dataset.json") if info.get("internal") else tc._load_records(info["dataset"])
    return tc._prepare(records)["test"]


def _finish_swarm(plan):
    from backend import continual
    from backend.neural_language_benchmark import load_candidate
    base = load_candidate(tc.folder() / plan["base"]["checkpoint"])
    test = _base_test(plan)
    general_base = skill_score("experience", base, test)
    accepted, report = [], []
    for entry in plan["runs"]:
        if not entry.get("skill") or not tc._summary(tc._run_dir(entry["id"]))["has_best"]:
            continue
        copy = _load(entry["id"])
        mine, theirs = skill_score(entry["skill"], copy, test), skill_score(entry["skill"], base, test)
        general = skill_score("experience", copy, test)
        if entry["skill"] == "experience":
            ok = mine > theirs
        else:
            # Not worse in general: per-character loss at most 3 % higher than the base.
            ok = mine > theirs and -general <= -general_base * 1.03
        report.append({"run": entry["id"], "skill": entry["skill"], "mine": mine, "theirs": theirs, "accepted": ok})
        if ok:
            accepted.append(entry["id"])
    plan["copies_report"] = report
    _save(plan)
    if not accepted:
        return _end(plan, "finished", "Ни одна копия не стала лучше в своём навыке без потерь: сливать нечего")
    merged = merge_skills(plan["base"]["checkpoint"], accepted)
    tc.exam_worker(merged)
    verdict = continual.judge(merged)
    progress = tc._read(tc._run_dir(merged) / "progress.json", {}) or {}
    progress["verdict"] = verdict
    tc._write(tc._run_dir(merged) / "progress.json", progress)
    plan["result_run"] = merged
    names = ", ".join(SKILL_NAMES[r["skill"]] for r in report if r["accepted"])
    return _end(plan, "finished", "Слиты навыки: %s. Итог: %s" % (names, {"rolled_back": "хуже активной, отложена",
                "waiting": "не хуже, ждёт вашего решения", "activated": "не хуже, включена сама"}[verdict["result"]]))


def merge_skills(base_checkpoint, run_ids, trim=TRIM):
    """TIES merge: base + the agreed, strongest changes of every accepted copy."""
    import torch
    base = torch.load(tc.folder() / base_checkpoint, map_location="cpu", weights_only=True)
    copies = [torch.load(tc._run_dir(r) / "language-longrun.pt.best.pt", map_location="cpu", weights_only=True)
              for r in run_ids]
    for c in copies:
        if c["config"][:4] != base["config"][:4] or c.get("arch", {}) != base.get("arch", {}) or \
                c["tokenizer"]["sha256"] != base["tokenizer"]["sha256"]:
            raise ValueError("Копии не совпадают с основой по устройству")
    weights = {}
    for key, value in base["weights"].items():
        if not value.is_floating_point():
            weights[key] = value
            continue
        deltas = torch.stack([c["weights"][key].float() - value.float() for c in copies])
        flat = deltas.abs().reshape(len(copies), -1)
        keep = max(1, int(flat.shape[1] * trim))
        threshold = flat.kthvalue(flat.shape[1] - keep + 1, dim=1).values if flat.shape[1] > 1 else flat[:, 0]
        trimmed = deltas * (deltas.abs() >= threshold.reshape(-1, *[1] * (deltas.dim() - 1)))
        sign = torch.sign(trimmed.sum(0))
        agree = (torch.sign(trimmed) == sign) & (trimmed != 0)
        total = (trimmed * agree).sum(0)
        count = agree.sum(0).clamp_min(1)
        weights[key] = (value.float() + total / count).to(value.dtype)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-long"
    path = tc.folder() / "runs" / run_id
    while path.exists():
        time.sleep(1.1)
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-long"
        path = tc.folder() / "runs" / run_id
    path.mkdir(parents=True)
    payload = dict(base, weights=weights)
    payload.pop("optimizer", None)
    torch.save(payload, path / "language-longrun.pt.best.pt")
    first = tc._read(tc._run_dir(run_ids[0]) / "run.json")
    tc._write(path / "run.json", dict(first, id=run_id, created=_now(), kind="swarm", series=None,
                                      merged=list(run_ids), dataset="(рой: %d копий)" % len(run_ids)))
    shutil_copy(tc._run_dir(run_ids[0]) / "dataset.json", path / "dataset.json")
    tc._write(path / "progress.json", {"state": "finished", "steps": 0, "best_step": 0, "history": [], "t": time.time(),
                                       "parameters": sum(v.numel() for v in weights.values())})
    return run_id


def shutil_copy(source, target):
    import shutil
    if source.is_file():
        shutil.copyfile(source, target)


def _finish_search_round(plan):
    from backend.neural_language_benchmark import load_candidate
    from backend.neural_language_longrun import score_checkpoint
    rows = [tc._summary(tc._run_dir(r)) for r in plan["round_runs"]]
    rows = [r for r in rows if r["has_best"] and r.get("exam_per_char") is not None]
    if not rows:
        return _end(plan, "failed", "Ни одна ветка не дошла до экзамена")
    best = min(rows, key=lambda r: r["exam_per_char"])
    records = tc._read(tc._run_dir(best["id"]) / "dataset.json")
    start_score = score_checkpoint(None, tc._prepare(records)["test"],
                                   loaded=load_candidate(tc.folder() / (plan.get("init") or plan["base"]["checkpoint"])))["per_char"]
    plan.setdefault("rounds_report", []).append({"round": plan["round"], "start": round(start_score, 4),
                                                 "branches": [{"run": r["id"], "exam": r["exam_per_char"]} for r in rows],
                                                 "best": best["id"]})
    if best["exam_per_char"] >= start_score:
        _note(plan, "раунд %d: ни одна ветка не лучше точки старта, возвращаюсь к ней" % plan["round"])
        return _finish_search(plan)
    plan["init"], plan["init_run"] = "runs/%s/language-longrun.pt.best.pt" % best["id"], best["id"]
    plan["result_run"] = best["id"]
    _note(plan, "раунд %d: лучшая ветка %s (%.3f против %.3f на старте)" % (plan["round"], best["id"], best["exam_per_char"], start_score))
    if plan["round"] >= plan["rounds"]:
        return _finish_search(plan)
    _prepare_round(plan)
    _next(plan)
    return plan


def _finish_search(plan):
    from backend import continual
    if not plan.get("result_run"):
        return _end(plan, "finished", "Ни одна ветка не оказалась лучше: Yorika осталась прежней")
    verdict = continual.judge(plan["result_run"])
    return _end(plan, "finished", "Лучший путь найден за %d раунд(а): %s" % (plan["round"], {
        "rolled_back": "но он хуже активной на её экзамене, отложен", "waiting": "ждёт вашего решения",
        "activated": "включён сам"}[verdict["result"]]))


def distill_set(checkpoint, prompts=120, seed=0):
    """The slow self answers; kept are answers the program confirms or that most drafts agree on."""
    from backend import brain, curiosity, logic, programs, simworld
    loaded = brain.load(checkpoint)
    model, state = loaded
    rng = random.Random(seed)
    asked = []
    level = curiosity.logic_frontier()
    banned = logic._exam_questions() | simworld._banned() | {q for q, _ in programs.exam_tasks()}
    for _ in range(prompts):
        t = logic.task(rng, level)
        if t["q"] not in banned:
            asked.append((t["q"], t["answer"]))
        if len(asked) >= prompts // 3:
            break
    asked += [(t["q"], t["answer"]) for t in simworld.fresh(rng, prompts // 3)]
    chat = [i["prompt"] for i in sl._load()["items"] if i.get("rating") == "up" and i.get("source") in (None, "yorika-chat")]
    rng.shuffle(chat)
    asked += [(q, None) for q in chat[:prompts - len(asked)]]
    kept = []
    for question, answer in asked:
        thought = brain.think(model, state, question, drafts=5, seed=rng.randrange(10 ** 6))
        if answer is not None:
            if logic.correct(thought["answer"], answer):
                kept.append((question, thought["answer"].strip()))
            continue
        votes = {}
        for text in thought["texts"]:
            key = " ".join(text.casefold().split())[:80]
            if key:
                votes[key] = votes.get(key, 0) + 1
        if votes and max(votes.values()) >= 3:
            kept.append((question, thought["answer"].strip()))
    records = _synthetic(kept, "distill")
    keys = {r["prompt"].casefold().strip() for r in records}
    records += [r for r in _experience(len(records), seed) if r["prompt"].casefold().strip() not in keys]
    return records, {"asked": len(asked), "kept": len(kept)}


def _finish_distill_round(plan):
    from backend import continual
    run_id = plan["round_runs"][-1]
    if not tc._summary(tc._run_dir(run_id))["has_best"]:
        return _end(plan, "failed", "Урок не сохранил точку")
    verdict = continual.judge(run_id)
    progress = tc._read(tc._run_dir(run_id) / "progress.json", {}) or {}
    progress["verdict"] = verdict
    tc._write(tc._run_dir(run_id) / "progress.json", progress)
    if verdict["result"] == "rolled_back":
        return _end(plan, "finished", "Раунд %d: быстрая стала хуже (%s), откат" % (plan["round"], verdict["why"]))
    plan["result_run"] = run_id
    plan["init"], plan["init_run"] = "runs/%s/language-longrun.pt.best.pt" % run_id, run_id
    _note(plan, "раунд %d: быстрая не хуже, теперь она учитель" % plan["round"])
    if plan["round"] >= plan["rounds"]:
        return _end(plan, "finished", "Готово: %d раунд(а) учёбы у себя будущей, последняя версия %s" % (
            plan["round"], {"waiting": "ждёт вашего решения", "activated": "включена сама"}[verdict["result"]]))
    _prepare_round(plan)
    _next(plan)
    return plan


def status():
    plan = current()
    if plan:
        plan = {k: v for k, v in plan.items() if k != "queue"} | {"queued": [q["label"] for q in plan.get("queue", [])]}
    return {"plan": plan, "history": history()}


