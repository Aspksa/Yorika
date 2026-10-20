"""One summary of what the autopilot tried and what helped, from measurements only.

- growth: the exam score (loss per character, lower is better) of every version that was
  active, in the order it became active, and the best exam among all versions so far;
- tried: for the last WEEK (or another window), every activity that produced versions, how many it produced and how
  many helped. A version helped when its verdict says it is not worse than the active one, or
  when it entered the archive. A lesson that was rolled back did not help;
- brain: the active version's blocks and parts from introspection;
- pareto: the front from archive.pareto().
"""
import time
from datetime import datetime, timezone

WEEK = 7 * 24 * 3600
NAMES = {"quick": "Урок после разговора", "sleep": "Сон", "evolution": "Эволюция", "merge": "Скрещивание", "grow": "Рост",
         "swarm": "Копии", "copy": "Копии", "branch": "Ветки и уроки", "distill": "Учёба у себя будущей",
         "selfcheck": "Самопроверка", "hemispheres": "Два полушария", "rebirth": "Нейрогенез", "ecosystem": "Обмен генами",
         "coevolve": "Коэволюция задач", "redqueen": "Красная Королева", "baldwin": "Эффект Болдуина", "es": "Эволюция весов",
         "search": "Ветки времени", "recipes": "Рецепты учёбы", "shrink": "Сжатие", "thoughts": "Язык мыслей",
         "dataevo": "Эволюция уроков", "symbiosis": "Эндосимбиоз", "breed": "Скрещивание по рецепту",
         "evolrl": "Большинство и новизна", "development": "Развитие по этапам", "solver": "Язык и решатель",
         "prover": "Доказывающая и проверяющая", "concepts": "Свои понятия", "analogy": "Аналогии",
         "metacog": "Знает, чего не знает", "latent": "Мышление без слов", "grok": "Озарение", "emergent": "Свой язык",
         "grounded": "Язык через действия", "scientist": "Учёный внутри", "counterfactual": "Что было бы, если",
         "teaching": "Учит младшую", "observer": "Внутренний наблюдатель", "budget": "Цена мысли", None: "Обучение вручную"}


def _ts(text):
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        return 0


def growth():
    from backend import training_center as tc
    exams = {r["id"]: r for r in tc.runs() if r.get("exam_per_char") is not None}
    history = [e.get("meta") or {} for e in tc._read(tc.folder() / "active-history.json", []) or []]
    current = tc.active()
    if current:
        history.append(current)
    points, seen = [], set()
    for meta in history:
        run = meta.get("run")
        if run in exams and (run, meta.get("activated")) not in seen:
            seen.add((run, meta.get("activated")))
            points.append({"run": run, "at": meta.get("activated"), "exam": exams[run]["exam_per_char"]})
    ordered = sorted(exams.values(), key=lambda r: r.get("created") or "")
    best, record = None, []
    for r in ordered:
        if best is None or r["exam_per_char"] < best:
            best = r["exam_per_char"]
            record.append({"run": r["id"], "at": r.get("created"), "exam": best})
    return {"active": points[-20:], "record": record[-20:]}


def tried(now=None, window=WEEK):
    from backend import plans
    from backend import training_center as tc
    now = now or time.time()
    plan_of = {}
    for p in plans.history(40):
        for r in p.get("runs") or []:
            plan_of[r["id"] if isinstance(r, dict) else r] = p.get("kind")
    rows = {}
    for r in tc.runs():
        if r["mode"] != "long" or now - _ts(r.get("created")) > window:
            continue
        kind = plan_of.get(r["id"]) or r.get("kind")
        row = rows.setdefault(kind, {"kind": kind, "title": NAMES.get(kind, kind), "tried": 0, "helped": 0, "waiting": 0})
        verdict = (r.get("verdict") or {}).get("result")
        entered = "вошла" in ((r.get("tournament") or {}).get("result") or "")
        if verdict is None and r.get("exam_per_char") is None:
            row["waiting"] += 1
            continue
        row["tried"] += 1
        if verdict in ("activated", "waiting") or entered or _entered_archive(r["id"]):
            row["helped"] += 1
    return sorted(rows.values(), key=lambda x: (-x["helped"], -x["tried"]))


def _entered_archive(run_id):
    from backend import archive
    return any(e.get("run") == run_id and (e.get("result") or "").startswith("вошла") for e in archive.load()["log"])


def brain():
    from backend import training_center as tc
    current = tc.active()
    if not current:
        return None
    item = next((r for r in tc.runs() if r["id"] == current["run"]), None)
    report = (item or {}).get("introspection") or {}
    if not report.get("blocks"):
        return {"run": current["run"], "blocks": [], "parts": []}
    return {"run": current["run"], "blocks": report["blocks"], "parts": report.get("parts") or [],
            "experts": report.get("experts"), "loss": report.get("loss")}


def build():
    from backend import archive
    out = {}
    for key, read in (("growth", growth), ("tried", tried), ("brain", brain), ("pareto", archive.pareto_status)):
        try:
            out[key] = read()
        except Exception as error:  # noqa: BLE001 - one broken part never hides the summary
            out[key] = {"error": str(error)[:160]}
    return out
