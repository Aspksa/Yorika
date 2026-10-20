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

Recipes: the best known way to study and its mutants run from the same version; the one that
improved the exams most per hour becomes the way quick lessons and sleep study (recipes.py).

Shrink: a version that grew (deeper or wider) teaches a version of the size it grew from. The
small one learns the big one's checked answers; it is kept only if it is not worse.

Hemispheres and thoughts (mind.py): lessons from where two versions disagree, and lessons in
thinking with hidden steps, each one lesson judged against the active version.

Coevolution, the Red Queen and the Baldwin effect (coevolution.py, baldwin.py): lessons from
the task genomes she fails; a match of two quiz masters after which both study their losses;
newborn starting points that compete on how fast they learn the same lesson.

Weights without gradients, lessons that evolve, endosymbiosis (es.py, data_evolution.py,
growth.engulf): the active version's weights evolve by evolution strategies alone; the lessons
are selected by how much each one helps; a smaller specialist moves inside her.

Breeding by an evolved recipe and learning without answers (breeding.py, selfevolve.py): parents
with healthy kinship are merged by a recipe evolved per layer while skills take turns as the goal;
lessons are her own drafts that most of five agree on, the most novel of them.

The school of reasoning (reasoning.py): Piaget's stages, a logic engine for her facts, legible
solutions and a checker, her own concepts, analogies, knowing her limits, steps moved inside, and a
laboratory experiment on insight (grok, no version made).

Nothing here activates a version by itself, except through «включать сама, если не хуже».
"""
import random
import sys
import time
from datetime import datetime, timezone

from backend import self_learning as sl
from backend import training_center as tc

KINDS = ("swarm", "search", "distill", "recipes", "shrink", "hemispheres", "thoughts", "coevolve", "redqueen", "baldwin",
         "es", "dataevo", "symbiosis", "breed", "evolrl",
         "development", "solver", "prover", "concepts", "analogy", "metacog", "latent", "grok")
REASONING = ("development", "solver", "prover", "concepts", "analogy", "metacog", "latent")   # reasoning.KINDS
SKILLS = ("logic", "sim", "programs", "tools", "experience")
SKILL_NAMES = {"logic": "логика", "sim": "мир задач", "programs": "программы", "tools": "инструменты",
               "experience": "ваши разговоры"}
LRS = (0.0001, 0.0003, 0.0006, 0.0002, 0.0004, 0.0008)
TRIM = 0.2
MAX_CHARS = 360


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _path():
    return tc.folder() / "plan.json"


def current():
    return tc._read(_path())


def history(limit=10):
    return (tc._read(tc.folder() / "plans-log.json", []) or [])[-limit:]


def _save(plan):
    tc._write(_path(), plan)


def _note(plan, text):
    plan.setdefault("log", []).append({"at": _now(), "text": text})
    plan["log"] = plan["log"][-40:]
    _save(plan)


def _end(plan, state, result):
    plan.update(state=state, result=result, finished=_now(), queue=[])
    _note(plan, result)
    # Forty plans: the autopilot's rhythm looks a month back at what each activity gave.
    tc._write(tc.folder() / "plans-log.json", (history(40) + [{k: plan.get(k) for k in (
        "id", "kind", "state", "result", "created", "finished", "runs", "result_run")}])[-40:])
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
    from backend import species
    banned = tc.protected_prompts() | species.probe_questions()
    seen, out = set(), []
    for prompt, answer in pairs:
        key = prompt.casefold().strip()
        # Very long lessons (big mazes, chains of tasks) would not fit the model's context.
        if key in banned or key in seen or len(prompt) + len(answer) > MAX_CHARS:
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
          scheduled=False, teacher=None):
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
    elif kind == "recipes":
        if type(branches) is not int or not 2 <= branches <= 6:
            raise ValueError("Рецептов от 2 до 6")
        plan.update(branches=branches, rounds=1)
    elif kind == "shrink":
        teacher = teacher or shrink_teacher()
        if not teacher:
            raise ValueError("Нет выросшей версии, которую можно сжать")
        item = tc._summary(tc._run_dir(teacher))
        if not item.get("grown_from") or item.get("kind") != "grow" or not item["has_best"]:
            raise ValueError("Сжать после роста можно только выросшую обученную версию")
        if type(prompts) is not int or not 20 <= prompts <= 1000:
            raise ValueError("Вопросов от 20 до 1000")
        plan.update(teacher=teacher, student=_root(teacher), rounds=1, prompts=prompts)
    elif kind == "hemispheres":
        from backend import mind
        other = teacher or mind.partner(current_brain["run"])
        if not other:
            raise ValueError("Нужна вторая обученная версия: второе полушарие")
        tc._run_dir(other)
        if type(prompts) is not int or not 20 <= prompts <= 1000:
            raise ValueError("Вопросов от 20 до 1000")
        plan.update(partner=other, rounds=1, prompts=prompts)
    elif kind == "redqueen":
        from backend import mind
        other = teacher or mind.partner(current_brain["run"])
        if not other:
            raise ValueError("Нужна вторая обученная версия: соперница")
        if not tc._summary(tc._run_dir(other))["has_best"]:
            raise ValueError("У соперницы нет сохранённой точки")
        if type(prompts) is not int or not 20 <= prompts <= 1000:
            raise ValueError("Вопросов от 20 до 1000")
        plan.update(partner=other, rounds=1, prompts=prompts)
    elif kind == "baldwin":
        if type(branches) is not int or not 2 <= branches <= 6:
            raise ValueError("Стартов от 2 до 6")
        plan.update(branches=branches, rounds=1)
    elif kind in ("thoughts", "coevolve", "es", "dataevo", "breed", "grok") + REASONING:
        plan.update(rounds=1)
    elif kind == "evolrl":
        if type(prompts) is not int or not 20 <= prompts <= 1000:
            raise ValueError("Вопросов от 20 до 1000")
        plan.update(rounds=1, prompts=prompts)
    elif kind == "symbiosis":
        guest = teacher or symbiont(current_brain["run"])
        if not guest:
            raise ValueError("Нет версии-специалиста меньше активной с тем же словарём")
        plan.update(guest=guest, rounds=1)
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
        if plan["kind"] == "es":
            return _run_es(plan)
        if plan["kind"] == "breed":
            return _run_breed(plan)
        if plan["kind"] == "grok":
            return _run_grok(plan)
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
    if plan["kind"] == "recipes":
        from backend import recipes
        plan["recipes"] = recipes.candidates(plan["branches"], seed=int(plan["id"][-6:]))
        for k, recipe in enumerate(plan["recipes"]):
            records = recipes.records(recipe, seed=k)
            if len(records) < 20:
                raise ValueError("Для рецептов мало уроков: %d" % len(records))
            queue.append({"label": "рецепт %d: %s" % (k + 1, recipes.describe(recipe)), "records": records,
                          "kind": "branch", "recipe": k, "minutes": max(1, plan["minutes"] * recipe["time"]),
                          "config": dict(config, lr=recipe["lr"], rule=recipe.get("rule"), seed=config["seed"] + 77 * (k + 1))})
    elif plan["kind"] == "shrink":
        student = plan["student"]
        records, made = distill_set(tc._run_dir(plan["teacher"]) / "language-longrun.pt.best.pt", plan["prompts"],
                                    seed=plan["round"])
        plan["made"] = made
        if made["kept"] < 10:
            raise ValueError("Большая версия ещё слаба для учителя: проверенных ответов %d из %d" % (made["kept"], made["asked"]))
        base_ckpt = "runs/%s/language-longrun.pt.best.pt" % student
        queue.append({"label": "малая учится у выросшей %s" % plan["teacher"], "records": records, "kind": "distill",
                      "config": _config(student)})
        _note(plan, "выросшая ответила: оставлено %d из %d" % (made["kept"], made["asked"]))
    elif plan["kind"] == "hemispheres":
        from backend import mind
        records, made = mind.hemisphere_set(tc.folder() / base_ckpt, tc._run_dir(plan["partner"]) / "language-longrun.pt.best.pt",
                                            plan["prompts"], seed=plan["round"])
        plan["made"] = made
        queue.append({"label": "полушария: урок из %d споров" % made["asked"], "records": records, "kind": "hemispheres",
                      "config": config})
        _note(plan, "права только активная %d, только вторая %d, обе %d, никто %d" % (
            made["left"], made["right"], made["both"], made["none"]))
    elif plan["kind"] == "thoughts":
        from backend import mind
        from backend.neural_language_benchmark import load_candidate
        own = mind.own_thoughts(load_candidate(tc.folder() / base_ckpt), 40, seed=plan["round"])
        records = _synthetic(own + mind.thought_lessons(160, seed=plan["round"]), "thoughts")
        keys = {r["prompt"].casefold().strip() for r in records}
        records += [r for r in _experience(len(records), plan["round"]) if r["prompt"].casefold().strip() not in keys]
        plan["made"] = {"own": len(own), "lessons": len(records)}
        queue.append({"label": "язык мыслей: своих верных мыслей %d" % len(own), "records": records, "kind": "branch",
                      "config": config})
    elif plan["kind"] == "coevolve":
        from backend import coevolution
        from backend.neural_language_benchmark import load_candidate
        pairs, made = coevolution.evolve(load_candidate(tc.folder() / base_ckpt), seed=int(plan["id"][-6:]) + plan["round"])
        records = _with_replay(_synthetic(pairs, "coevolution"), plan["round"])
        plan["made"] = made
        if len(records) < 20:
            raise ValueError("Слабых мест для урока мало: %d примеров" % len(records))
        queue.append({"label": "коэволюция: слабые места поколения %d" % made["generation"], "records": records,
                      "kind": "coevolve", "config": config})
        _note(plan, "поколение задач %d: слабее всего %s" % (made["generation"], ", ".join(
            "%s (%d%%)" % (w["label"], round(100 * w["fail"])) for w in made["weak"][:3])))
    elif plan["kind"] == "redqueen":
        from backend import coevolution
        from backend.neural_language_benchmark import load_candidate
        partner_ckpt = "runs/%s/language-longrun.pt.best.pt" % plan["partner"]
        left, right, made = coevolution.match((plan["base"]["run"], load_candidate(tc.folder() / base_ckpt)),
                                              (plan["partner"], load_candidate(tc.folder() / partner_ckpt)),
                                              seed=int(plan["id"][-6:]), questions=max(10, plan["prompts"] // 4))
        plan["made"] = made
        for side, pairs, init, cfg in (("active", left, base_ckpt, config), ("partner", right, partner_ckpt, _config(plan["partner"]))):
            records = _with_replay(_synthetic(pairs, "redqueen"), plan["round"])
            if len(records) < 20:
                _note(plan, "%s: учить почти нечего (%d примеров)" % ("активная" if side == "active" else "соперница", len(records)))
                continue
            queue.append({"label": "Красная Королева: %s учит проигранное" % ("активная" if side == "active" else "соперница"),
                          "records": records, "kind": "redqueen", "config": cfg, "init": init, "side": side})
        _note(plan, "матч: активная %d : %d соперница (верных вопросов %d и %d), рейтинг %s : %s" % (
            made["score"][0], made["score"][1], made["asked"][0], made["asked"][1], made["ratings"][0], made["ratings"][1]))
        if not queue:
            raise ValueError("После матча учить нечего: обе ответили на всё одинаково")
    elif plan["kind"] == "baldwin":
        from backend import baldwin, recipes
        genomes, files = baldwin.prepare(tc.folder() / base_ckpt, plan["branches"], int(plan["id"][-6:]))
        plan["genomes"] = genomes
        records = recipes.records(recipes.DEFAULT, seed=int(plan["id"][-6:]) % 1000)
        if len(records) < 20:
            raise ValueError("Для стартов мало уроков: %d" % len(records))
        for k, (genome, path) in enumerate(zip(genomes, files)):
            queue.append({"label": "старт %d: %s" % (k + 1, baldwin.describe(genome)), "records": records, "kind": "baldwin",
                          "config": config, "init": path, "baldwin": k})
    elif plan["kind"] == "dataevo":
        from backend import data_evolution, recipes
        from backend.neural_language_benchmark import load_candidate
        seed = int(plan["id"][-6:]) % 100000
        recipe = recipes.best()
        records, made = data_evolution.evolve(load_candidate(tc.folder() / base_ckpt), recipes.records(recipe, seed=seed),
                                              lambda source, n, s: _refill(recipe, source, n, s), seed=seed)
        plan["made"] = made
        queue.append({"label": "уроки поколения %d: выжило %d, умерло %d, новых %d" % (
            made["generation"], made["kept"], made["died"], made["fresh"]), "records": records, "kind": "branch", "config": config})
        _note(plan, "эволюция уроков: выжило %d, умерло %d, новых %d" % (made["kept"], made["died"], made["fresh"]))
    elif plan["kind"] in REASONING:
        from backend import reasoning
        from backend.neural_language_benchmark import load_candidate
        pairs, made = reasoning.make(plan["kind"], load_candidate(tc.folder() / base_ckpt), seed=int(plan["id"][-6:]) + plan["round"],
                                     run_id=base_run)
        plan["made"] = made
        records = _with_replay(_synthetic(pairs, plan["kind"]), plan["round"])
        if len(records) < 20:
            raise ValueError("Для урока «%s» мало примеров: %d" % (reasoning.TITLES[plan["kind"]], len(records)))
        queue.append({"label": "%s: %s" % (reasoning.TITLES[plan["kind"]], reasoning.describe(plan["kind"], made)),
                      "records": records, "kind": "branch", "config": config})
        _note(plan, reasoning.describe(plan["kind"], made))
    elif plan["kind"] == "evolrl":
        from backend import selfevolve
        pairs, made = selfevolve.build(tc.folder() / base_ckpt, plan["prompts"], seed=int(plan["id"][-6:]) + plan["round"],
                                       should_stop=lambda: (current() or {}).get("state") not in ("preparing", "running"))
        plan["made"] = made
        selfevolve.remember(made)
        if made["kept"] < 10:
            raise ValueError("Большинство черновиков согласилось только в %d вопросах из %d: учить нечему" % (made["kept"], made["asked"]))
        records = _with_replay(_synthetic(pairs, "evolrl"), plan["round"])
        queue.append({"label": "большинство и новизна: %d согласных ответов" % made["kept"], "records": records,
                      "kind": "branch", "config": config})
        _note(plan, "согласие большинства в %d вопросах из %d%s" % (made["kept"], made["asked"], (
            "; в задачах большинство право в %d из %d (ответы не подсказывались)" % (made["right"], made["tasks"]))
            if made["tasks"] else ""))
    elif plan["kind"] == "symbiosis":
        from backend import growth, recipes
        guest_ckpt = tc._run_dir(plan["guest"]) / "language-longrun.pt.best.pt"
        target = tc.folder() / "plan" / "symbiosis.pt"
        made = growth.engulf(tc.folder() / base_ckpt, guest_ckpt, target)
        import torch
        arch = torch.load(target, map_location="cpu", weights_only=True)["arch"]
        plan["made"] = made
        records = _with_replay(recipes.records(recipes.best(), seed=plan["round"]), plan["round"])
        queue.append({"label": "эндосимбиоз: %s внутри активной" % plan["guest"], "records": records, "kind": "branch",
                      "config": dict(config, arch=arch), "init": "plan/symbiosis.pt"})
        _note(plan, "специалист %s встроен: %d параметров внутри %d" % (plan["guest"], made["guest_parameters"], made["parameters"]))
    elif plan["kind"] == "swarm":
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
        item.setdefault("init", base_ckpt)
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
                run = tc.start("long", device=plan["device"], total_steps=1000000,
                               hours=round(item.get("minutes", plan["minutes"]) / 60, 4),
                               config=item["config"], kind=item["kind"], init=item["init"],
                               records=tc._read(tc.folder() / item["records_file"]),
                               dataset="(%s)" % item["label"], launch=launch, scheduled=plan.get("scheduled", False))
                break
            except ValueError as error:
                if "секунду" not in str(error) or attempt == 2:
                    raise
                time.sleep(1.1)
        entry = {"id": run["id"], "label": item["label"], "skill": item.get("skill"), "round": plan["round"],
                 "recipe": item.get("recipe"), "minutes": item.get("minutes", plan["minutes"]),
                 "side": item.get("side"), "baldwin": item.get("baldwin"), "init": item["init"]}
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
        if plan["kind"] == "recipes":
            return _finish_recipes(plan)
        if plan["kind"] == "shrink":
            return _finish_shrink(plan)
        if plan["kind"] in ("hemispheres", "thoughts", "coevolve", "dataevo", "symbiosis", "evolrl") + REASONING:
            return _finish_single(plan)
        if plan["kind"] == "redqueen":
            return _finish_redqueen(plan)
        if plan["kind"] == "baldwin":
            return _finish_baldwin(plan)
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


def _finish_recipes(plan):
    from backend import continual, recipes
    from backend.neural_language_benchmark import load_candidate
    test = _base_test(plan)
    before = recipes.scores(load_candidate(tc.folder() / plan["base"]["checkpoint"]), test)
    results = []
    for entry in plan["runs"]:
        if entry.get("recipe") is None or not tc._summary(tc._run_dir(entry["id"]))["has_best"]:
            continue
        after = recipes.scores(_load(entry["id"]), test)
        per_hour, delta = recipes.gain(before, after, entry["minutes"] / 60)
        results.append({"recipe": plan["recipes"][entry["recipe"]], "run": entry["id"], "gain_per_hour": per_hour,
                        "gain": delta, "hours": entry["minutes"] / 60})
    if not results:
        return _end(plan, "failed", "Ни один рецепт не дошёл до экзамена")
    outcome = recipes.remember(results)
    plan["recipes_report"] = [{k: r[k] for k in ("run", "gain_per_hour", "gain")} | {"label": recipes.describe(r["recipe"])}
                              for r in results]
    winner = outcome["winner"]
    if winner["gain"] <= 0:
        return _end(plan, "finished", "Ни один рецепт не улучшил экзамены; прежний рецепт остаётся")
    plan["result_run"] = winner["run"]
    verdict = continual.judge(winner["run"])
    return _end(plan, "finished", "Лучший рецепт: %s (+%.4f за час)%s; его урок %s" % (
        recipes.describe(winner["recipe"]), winner["gain_per_hour"], ", теперь так учатся быстрые уроки и сон" if outcome["changed"] else "",
        {"rolled_back": "хуже активной, отложен", "waiting": "ждёт вашего решения", "activated": "включён сам"}[verdict["result"]]))


def _root(run_id):
    """The version a grown one grew from, following several growths back to the first size."""
    seen = set()
    while run_id and run_id not in seen:
        seen.add(run_id)
        info = tc._read(tc._run_dir(run_id) / "run.json", {}) or {}
        source = info.get("grown_from") if info.get("kind") == "grow" else None
        if not source:
            return run_id
        run_id = source
    return run_id


def shrink_teacher():
    """The newest finished grown version whose smaller ancestor still has its weights."""
    for item in tc.runs():
        if item.get("grown_from") and item.get("kind") == "grow" and item["has_best"] and item["state"] == "finished":
            try:
                if tc._summary(tc._run_dir(_root(item["id"])))["has_best"]:
                    return item["id"]
            except ValueError:
                continue
    return None


def _finish_single(plan):
    from backend import continual, reasoning
    run_id = plan["round_runs"][-1]
    if not tc._summary(tc._run_dir(run_id))["has_best"]:
        return _end(plan, "failed", "Урок не сохранил точку")
    plan["result_run"] = run_id
    verdict = continual.judge(run_id)
    progress = tc._read(tc._run_dir(run_id) / "progress.json", {}) or {}
    progress["verdict"] = verdict
    tc._write(tc._run_dir(run_id) / "progress.json", progress)
    if plan["kind"] in REASONING:
        reasoning.after(plan["kind"], plan.get("made"), verdict["result"])
        reasoning.remember(plan["kind"], plan.get("made"), run_id, verdict["result"])
    return _end(plan, "finished", "%s: урок %s, %s" % (dict(reasoning.TITLES, **{"hemispheres": "Два полушария", "thoughts": "Язык мыслей",
                                                         "coevolve": "Коэволюция задач", "dataevo": "Эволюция уроков",
                                                         "symbiosis": "Эндосимбиоз",
                                                         "evolrl": "Большинство и новизна"})[plan["kind"]],
                run_id, {"rolled_back": "хуже активной, отложен (%s)" % verdict["why"], "waiting": "не хуже, ждёт вашего решения",
                         "activated": "не хуже, включён сам"}[verdict["result"]]))


def _refill(recipe, source, n, seed):
    """Fresh lessons of one source for data evolution."""
    from backend import recipes
    if source in recipe["mix"]:
        only = dict(recipe, mix={k: (1 if k == source else 0) for k in recipe["mix"]})
        return recipes.records(only, seed=seed, total=n)[:n]
    return _experience(n, seed)


def symbiont(host_run):
    """The best smaller version with the same word pieces and context: a specialist to engulf."""
    from backend import archive
    host = tc._summary(tc._run_dir(host_run))
    try:
        info = tc._read(tc._run_dir(host_run) / "run.json")["config"]
        import torch
        sha = torch.load(tc._run_dir(host_run) / "language-longrun.pt.best.pt", map_location="cpu", weights_only=True)["tokenizer"]["sha256"]
    except Exception:  # noqa: BLE001 - no host, no guest
        return None
    found = []
    for item in tc.runs():
        if (item["id"] == host_run or item["mode"] != "long" or not item["has_best"] or not item.get("parameters")
                or item["parameters"] >= (host.get("parameters") or 0) or not (item.get("arch") or {}).get("lab")
                or (item.get("arch") or {}).get("guest") or archive.fitness(item) is None):
            continue
        try:
            cfg = tc._read(tc._run_dir(item["id"]) / "run.json")["config"]
            if cfg["context"] != info["context"] or cfg["max_merges"] != info["max_merges"]:
                continue
            state = torch.load(tc._run_dir(item["id"]) / "language-longrun.pt.best.pt", map_location="cpu", weights_only=True)
        except Exception:  # noqa: BLE001
            continue
        if state["tokenizer"]["sha256"] == sha:
            found.append((archive.fitness(item), item["id"]))
    return max(found)[1] if found else None


def new_version(base_checkpoint, weights, kind, label, source_run):
    """A version made without ordinary training: saved, then examined like any other."""
    import torch
    base = torch.load(tc.folder() / base_checkpoint, map_location="cpu", weights_only=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-long"
    path = tc.folder() / "runs" / run_id
    while path.exists():
        time.sleep(1.1)
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-long"
        path = tc.folder() / "runs" / run_id
    path.mkdir(parents=True)
    payload = dict(base, weights=weights)
    for key in ("optimizer", "rng", "cuda_rng", "scaler"):
        payload.pop(key, None)
    torch.save(payload, path / "language-longrun.pt.best.pt")
    info = tc._read(tc._run_dir(source_run) / "run.json")
    tc._write(path / "run.json", dict(info, id=run_id, created=_now(), kind=kind, series=None, parent=source_run,
                                      dataset=label if info.get("internal") else info["dataset"], made_as=label))
    shutil_copy(tc._run_dir(source_run) / "dataset.json", path / "dataset.json")
    tc._write(path / "progress.json", {"state": "finished", "steps": 0, "best_step": 0, "history": [], "t": time.time(),
                                       "parameters": sum(v.numel() for v in weights.values())})
    return run_id


def _run_es(plan):
    """Evolution strategies on the active version's weights, then the usual exam and judgement."""
    from backend import continual, es, recipes
    from backend.neural_language_benchmark import load_candidate
    plan["state"], plan["round"], plan["round_runs"] = "running", 1, []
    _save(plan)
    records = _with_replay(recipes.records(recipes.best(), seed=int(plan["id"][-6:]) % 1000), 1)
    weights, made = es.evolve(load_candidate(tc.folder() / plan["base"]["checkpoint"]), records,
                              seconds=plan["minutes"] * 60, seed=int(plan["id"][-6:]),
                              should_stop=lambda: (current() or {}).get("state") != "running")
    if (current() or {}).get("state") != "running":
        return 0
    plan["made"] = made
    _note(plan, "поколений %d, копий %d: потеря на проверочных уроках %.4f → %.4f" % (
        made["generations"], made["copies"], made["loss_before"], made["loss_after"]))
    if made["loss_after"] >= made["loss_before"]:
        es.remember(made, None)
        _end(plan, "finished", "Эволюция весов не нашла лучше за %d поколений: версия не создана" % made["generations"])
        return 0
    run_id = new_version(plan["base"]["checkpoint"], weights, "es", "(эволюция весов: %d поколений)" % made["generations"],
                         plan["base"]["run"])
    tc.exam_worker(run_id)
    verdict = continual.judge(run_id)
    progress = tc._read(tc._run_dir(run_id) / "progress.json", {}) or {}
    progress["verdict"] = verdict
    tc._write(tc._run_dir(run_id) / "progress.json", progress)
    plan["result_run"] = run_id
    es.remember(made, run_id, verdict["result"])
    _end(plan, "finished", "Эволюция весов без градиентов: %s, %s" % (run_id, {
        "rolled_back": "хуже активной, отложена (%s)" % verdict["why"], "waiting": "не хуже, ждёт вашего решения",
        "activated": "не хуже, включена сама"}[verdict["result"]]))
    return 0


def _run_breed(plan):
    """Parents with healthy kinship, a recipe evolved while skills take turns, then the exams."""
    from backend import breeding, continual
    plan["state"], plan["round"], plan["round_runs"] = "running", 1, []
    _save(plan)
    info = tc._read(tc._run_dir(plan["base"]["run"]) / "run.json")
    try:
        records = tc._read(tc._run_dir(plan["base"]["run"]) / "dataset.json") if info.get("internal") else tc._load_records(info["dataset"])
    except (ValueError, OSError):
        records = None
    weights, made = breeding.breed(plan["base"]["checkpoint"], plan["base"]["run"], seconds=plan["minutes"] * 60,
                                   seed=int(plan["id"][-6:]), records=records, previous=breeding.load()["recipe"],
                                   should_stop=lambda: (current() or {}).get("state") != "running")
    if (current() or {}).get("state") != "running":
        return 0
    plan["made"] = {k: made.get(k) for k in ("parents", "skipped", "generations", "children", "cells", "gains", "why")}
    names = ", ".join("%s (родство %s)" % (p["run"], "/".join("—" if k is None else str(k) for k in p["kin"]) or "первый")
                      for p in made["parents"])
    if made["parents"]:
        _note(plan, "родители: %s; рецептов испытано %d" % (names, made.get("children", 0)))
    if weights is None:
        breeding.remember(made, None)
        _end(plan, "finished", "Скрещивание по рецепту: версия не создана, %s" % made["why"])
        return 0
    run_id = new_version(plan["base"]["checkpoint"], weights, "breed",
                         "(скрещивание по рецепту: %d родителя, %d рецептов)" % (len(made["parents"]), made["children"]),
                         plan["base"]["run"])
    info = tc._read(tc._run_dir(run_id) / "run.json")
    tc._write(tc._run_dir(run_id) / "run.json", dict(info, merged=[plan["base"]["run"]] + [p["run"] for p in made["parents"]]))
    tc.exam_worker(run_id)
    verdict = continual.judge(run_id)
    progress = tc._read(tc._run_dir(run_id) / "progress.json", {}) or {}
    progress["verdict"] = verdict
    tc._write(tc._run_dir(run_id) / "progress.json", progress)
    plan["result_run"] = run_id
    breeding.remember(made, run_id, verdict["result"])
    gains = ", ".join("%s %+.3f" % (breeding.SKILL_NAMES[s], g) for s, g in made["gains"].items())
    _end(plan, "finished", "Скрещивание по рецепту: %s (на уроках навыков: %s), %s" % (run_id, gains, {
        "rolled_back": "хуже активной, отложена (%s)" % verdict["why"], "waiting": "не хуже, ждёт вашего решения",
        "activated": "не хуже, включена сама"}[verdict["result"]]))
    return 0


def _run_grok(plan):
    """The insight experiment: two small networks of her kind, strong and weak weight decay."""
    from backend import grokking
    plan["state"], plan["round"], plan["round_runs"] = "running", 1, []
    _save(plan)
    device = plan.get("device") or "cpu"
    try:
        import torch
        if device == "cuda" and not torch.cuda.is_available():
            device = "cpu"
    except ImportError:
        raise ValueError("Для опыта нужен PyTorch")
    made = grokking.experiment(seconds=plan["minutes"] * 60, seed=int(plan["id"][-6:]) % 1000, device=device,
                               should_stop=lambda: (current() or {}).get("state") != "running")
    if (current() or {}).get("state") != "running":
        return 0
    grokking.remember(made)
    plan["made"] = {k: made[k] for k in ("p", "verdict")}
    _end(plan, "finished", "Озарение (опыт, версия не создаётся): %s" % made["verdict"])
    return 0


def _with_replay(records, seed):
    """Lessons plus as many of your examples, so a skill does not push out the conversation."""
    keys = {r["prompt"].casefold().strip() for r in records}
    return records + [r for r in _experience(len(records), seed) if r["prompt"].casefold().strip() not in keys]


def _finish_redqueen(plan):
    from backend import continual
    made = plan.get("made") or {}
    lines = ["Матч: активная %d : %d соперница" % tuple(made.get("score", [0, 0]))]
    for entry in plan["runs"]:
        if not tc._summary(tc._run_dir(entry["id"]))["has_best"]:
            continue
        if entry.get("side") == "active":
            plan["result_run"] = entry["id"]
            verdict = continual.judge(entry["id"])
            progress = tc._read(tc._run_dir(entry["id"]) / "progress.json", {}) or {}
            progress["verdict"] = verdict
            tc._write(tc._run_dir(entry["id"]) / "progress.json", progress)
            lines.append("урок активной %s: %s" % (entry["id"], {"rolled_back": "хуже активной, отложен", "waiting": "не хуже, ждёт вашего решения",
                                                                 "activated": "не хуже, включён сам"}[verdict["result"]]))
        else:
            lines.append("соперница тоже подучилась: %s" % entry["id"])
    return _end(plan, "finished", "; ".join(lines))


def _finish_baldwin(plan):
    from backend import baldwin
    results = []
    for entry in plan["runs"]:
        if entry.get("baldwin") is None:
            continue
        item = tc._summary(tc._run_dir(entry["id"]))
        if item["has_best"] and item.get("exam_per_char") is not None:
            results.append({"k": entry["baldwin"], "run": entry["id"], "exam": item["exam_per_char"], "init": entry["init"]})
    made = baldwin.remember(plan["genomes"], results)
    plan["made"] = made
    text = "Поколение стартов %d: быстрее всех училась «%s» (экзамен %.3f)" % (made["generation"], made["winner"], made["exam"])
    if made.get("inherited") is not None and made.get("control") is not None:
        text += "; врождённая точка %.3f против случайной %.3f — %s" % (
            made["inherited"], made["control"], "врождённая учится быстрее" if made["inherited"] < made["control"] else "пока не быстрее случайной")
    return _end(plan, "finished", text)


def _finish_shrink(plan):
    from backend import continual
    run_id = plan["round_runs"][-1]
    item = tc._summary(tc._run_dir(run_id))
    if not item["has_best"]:
        return _end(plan, "failed", "Урок не сохранил точку")
    teacher = tc._summary(tc._run_dir(plan["teacher"]))
    plan["result_run"] = run_id
    verdict = continual.judge(run_id)
    progress = tc._read(tc._run_dir(run_id) / "progress.json", {}) or {}
    progress["verdict"] = verdict
    tc._write(tc._run_dir(run_id) / "progress.json", progress)
    small, big = item.get("parameters") or 0, teacher.get("parameters") or 0
    return _end(plan, "finished", "Сжатие: малая версия %s (%.1f млн против %.1f млн у выросшей), экзамен %s против %s; %s" % (
        run_id, small / 1e6, big / 1e6, item.get("exam_per_char"), teacher.get("exam_per_char"),
        {"rolled_back": "хуже активной, отложена", "waiting": "ждёт вашего решения", "activated": "включена сама"}[verdict["result"]]))


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


