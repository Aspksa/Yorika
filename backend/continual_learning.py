"""Bounded local weight consolidation; one active brain, offline candidates only.

Reviewed experience is fast memory; copied neural weights are slow memory. Validation
selects candidates, retention guards old skills. Neither is a final unbiased exam.
No cloud calls, unreviewed self-training, automatic activation or memory deletion.
"""
import hashlib
import math
import os
import shutil
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path

from backend import training_center as tc
from backend import self_learning as sl

DEFAULTS = {"enabled": False, "device": "cuda", "steps": 8, "seconds": 60,
            "new_limit": 16, "replay_limit": 64, "night_steps": 64, "night_seconds": 600}


def root():
    return tc.folder() / "continual"


def settings():
    return dict(DEFAULTS, **(tc._read(root() / "settings.json", {}) or {}))


@contextmanager
def lock():
    root().mkdir(parents=True, exist_ok=True)
    path = root() / "busy"
    try:
        path.mkdir()
    except FileExistsError as exc:
        raise ValueError("Консолидация уже идёт; после аварии проверьте процесс перед удалением continual/busy") from exc
    try:
        (path / "pid").write_text(str(os.getpid()), encoding="ascii")
        yield
    finally:
        (path / "pid").unlink(missing_ok=True)
        path.rmdir()


def busy():
    return (root() / "busy").exists()


def _key(prompt):
    return prompt.strip().casefold()


def _hash(value):
    from backend.neural_language_benchmark import fingerprint
    return fingerprint(value)


def reviewed():
    """Newest reviewed answer wins; withdrawn consent stops use of chat experience."""
    if not sl._settings()["collect"]:
        raise ValueError("Сбор опыта выключен")
    result, seen = [], set()
    for item in reversed(sl._load()["items"]):
        prompt = item.get("prompt", "")
        answer = item.get("answer") if item.get("rating") == "up" else (
            item.get("correction") if item.get("rating") == "down" else None)
        key = _key(prompt)
        if key in seen:
            continue
        seen.add(key)
        if not prompt.strip() or not isinstance(answer, str) or not answer.strip():
            continue
        if any(len(s) > sl.MAX_TEXT or sl.EMAIL.search(s) or sl.SECRET.search(s) for s in (prompt, answer)):
            continue
        pair = (prompt.strip(), answer.strip())
        result.append({"id": _hash(pair), "pair": pair})
    return result


def configure(enabled, *, device="cuda", steps=8, seconds=60):
    if type(enabled) is not bool or device not in ("cpu", "cuda"):
        raise ValueError("Укажите режим и устройство")
    if type(steps) is not int or not 1 <= steps <= 64 or type(seconds) is not int or not 5 <= seconds <= 600:
        raise ValueError("От 1 до 64 шагов и от 5 до 600 секунд")
    with lock():
        plan = dict(DEFAULTS, enabled=enabled, device=device, steps=steps, seconds=seconds)
        if enabled:
            (root() / "stop").unlink(missing_ok=True)
        tc._write(root() / "settings.json", plan)
    return plan


def partition(rows, *, require_all=True):
    """Stable prompt buckets: corrections do not migrate exams into training."""
    groups = {"train": [], "validation": [], "retention": []}
    for row in rows:
        bucket = int(hashlib.sha256(_key(row["pair"][0]).encode()).hexdigest(), 16) % 10
        groups["validation" if bucket == 0 else "retention" if bucket == 1 else "train"].append(row)
    if require_all and any(not part for part in groups.values()):
        raise ValueError("Нужны оценённые примеры в трёх независимых группах; добавьте больше разных вопросов")
    return groups


def make_batch(groups, consumed, *, new_limit=16, replay_limit=64, replay_offset=0, rehearsal=False):
    new = [row for row in groups["train"] if row["id"] not in consumed][:new_limit]
    if not new and not rehearsal:
        return [], []
    old = sorted((row for row in groups["train"] if row["id"] in consumed), key=lambda r: r["id"])
    if old:
        offset = replay_offset % len(old)
        old = (old[offset:] + old[:offset])[:replay_limit]
    # Interleave so a short micro-update actually sees both old and new examples.
    batch = []
    for i in range(max(len(new), len(old))):
        if i < len(new):
            batch.append(new[i]["pair"])
        if i < len(old):
            batch.append(old[i]["pair"])
    return batch, [row["id"] for row in new]


def with_original_skills(groups):
    """Replay the active run's original training rows and guard its original exams.

    Without provenance the cycle refuses to advertise preservation of old skills.
    """
    meta = tc._read(tc.folder() / "active-meta.json", {}) or {}
    run_id = meta.get("origin_run") or meta.get("run")
    if not run_id:
        raise ValueError("Для сохранения старых навыков нужен исходный запуск и его учебный файл")
    info = tc._read(tc._run_dir(run_id) / "run.json", {}) or {}
    records = tc._load_records(info.get("dataset"))
    original = tc._prepare(records)
    if original["manifest"] != info.get("manifest"):
        raise ValueError("Исходные учебные данные изменились")
    exams = {_key(p) for name in ("validation", "test") for p, _ in original[name]}
    trained = {_key(p) for p, _ in original["train"]}
    # Never train original exams; never label a previously trained prompt as held out.
    rows = {name: [r for r in groups[name] if _key(r["pair"][0]) not in exams | trained]
            for name in groups}
    for name, origin in (("validation", "validation"), ("retention", "test")):
        prior = [{"id": _hash(pair), "pair": pair} for pair in original[origin]]
        rows[name] = (sorted(prior, key=lambda r: r["id"])[:64] +
                      sorted(rows[name], key=lambda r: r["id"])[:64])
    replay = [{"id": _hash(pair), "pair": pair} for pair in original["train"]]
    rows["train"] += replay
    return rows, [r["id"] for r in replay], run_id


def gate(baseline, candidate):
    """Both suites must be finite and non-regressing, at least one strictly better."""
    if set(baseline) != {"validation", "retention"} or set(candidate) != set(baseline):
        raise ValueError("Missing evaluation suite")
    values = list(baseline.values()) + list(candidate.values())
    if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values):
        return False
    return (all(candidate[k] <= baseline[k] for k in baseline) and
            any(candidate[k] < baseline[k] for k in baseline))


def _source():
    from backend.active_brain import active_brain
    return active_brain(tc.folder())


def _scores(path, groups):
    from backend.neural_language_benchmark import load_candidate, score
    model, state = load_candidate(path)
    return {name: score(model, state, [r["pair"] for r in groups[name]])["nll"]
            for name in ("validation", "retention")}


def run(*, night=False):
    """One transaction. On rejection/error the prior offline head and active pointer survive."""
    with lock():
        plan = settings()
        if plan["enabled"] is not True:
            return {"state": "disabled"}
        if tc._active_job():
            return {"state": "deferred", "reason": "Идёт другое обучение"}
        review_ids = {r["id"] for r in reviewed()}
        groups, original_ids, origin_run = with_original_skills(partition(reviewed(), require_all=False))
        active = _source()
        active_sha = tc._sha256(active)
        head = tc._read(root() / "head.json", {}) or {}
        consumed = head.get("consumed", []) if head.get("active_sha256") == active_sha else []
        all_ids = {r["id"] for group in groups.values() for r in group}
        # A correction/deletion invalidates all inherited offline weights. Active weights
        # may still remember erased data: genuine unlearning requires clean retraining.
        if not set(consumed).issubset(all_ids):
            consumed, head = [], {}
        source = active
        if consumed:
            candidate = root() / head["candidate"]
            if not candidate.is_file() or tc._sha256(candidate) != head["sha256"]:
                raise ValueError("Повреждена предыдущая версия консолидации")
            source = candidate
        batch, new_ids = make_batch(groups, list(set(consumed) | set(original_ids)),
                                   new_limit=plan["new_limit"], replay_limit=plan["replay_limit"],
                                   replay_offset=head.get("replay_offset", 0), rehearsal=night)
        if not batch:
            return {"state": "idle"}
        # Refuse additional disk growth; the user reviews/archives old artifacts explicitly.
        if len(list((root() / "runs").glob("*"))) >= 20:
            raise ValueError("Лимит 20 экспериментов: сохраните нужные и освободите архив continual/runs")
        used_bytes = sum(p.stat().st_size for p in root().rglob("*.pt"))
        needed = source.stat().st_size * 4 + 256_000_000
        if used_bytes + needed > 2_000_000_000 or shutil.disk_usage(root()).free < needed:
            raise ValueError("Недостаточно места в локальном бюджете консолидации 2 ГБ")
        if (root() / "stop").exists():
            return {"state": "disabled"}
        experiment = root() / "runs" / uuid.uuid4().hex
        experiment.mkdir(parents=True)
        backup = experiment / "before.pt"
        shutil.copyfile(source, backup)
        before_sha = tc._sha256(backup)
        if before_sha != tc._sha256(source):
            raise ValueError("Источник изменился во время копирования")
        report = {"state": "running", "id": experiment.name, "created": tc._now(), "night": night,
                  "active_sha256": active_sha, "source_sha256": before_sha,
                  "batch_count": len(batch), "new_count": len(new_ids), "origin_run": origin_run,
                  "evaluation_counts": {k: len(groups[k]) for k in ("validation", "retention")},
                  "validation_sha256": _hash([r["pair"] for r in groups["validation"]]),
                  "retention_sha256": _hash([r["pair"] for r in groups["retention"]])}
        tc._write(root() / "last.json", report)
        try:
            from backend.neural_language_benchmark import load_candidate
            from backend.neural_language_longrun import run as train
            _, state = load_candidate(backup)
            width, heads, layers, context, merges, seed = state["config"]
            del _, state
            report["baseline"] = _scores(backup, groups)
            candidate = experiment / "candidate.pt"
            report["training"] = train(batch, [r["pair"] for r in groups["validation"]], candidate,
                total_steps=plan["night_steps"] if night else plan["steps"],
                checkpoint_every=plan["night_steps"] if night else plan["steps"],
                width=width, heads=heads, layers=layers, context=context, max_merges=merges, seed=seed,
                max_run_seconds=plan["night_seconds"] if night else plan["seconds"],
                device=plan["device"], init_from=backup, continue_dialogue=True,
                stop_requested=lambda: (root() / "stop").exists())
            if (root() / "stop").exists():
                raise ValueError("Остановлено пользователем")
            report["candidate"] = _scores(candidate, groups)
            accepted = gate(report["baseline"], report["candidate"])
            if tc._sha256(_source()) != active_sha:
                raise ValueError("Активная модель изменилась во время обучения")
            if tc._sha256(backup) != before_sha:
                raise ValueError("Резервная копия повреждена")
            # Recheck consent/ratings before committing an offline head.
            if {r["id"] for r in reviewed()} != review_ids:
                raise ValueError("Опыт изменился во время обучения; повторите цикл")
            report["state"] = "proposed" if accepted else "rejected"
            report["candidate_sha256"] = tc._sha256(candidate)
            if accepted:
                # Only records the bounded batch actually traversed count as consumed.
                seen = batch[:min(len(batch), report["training"]["steps"])]
                used = list(dict.fromkeys(consumed + [_hash(pair) for pair in seen]))
                tc._write(root() / "head.json", {"candidate": str(candidate.relative_to(root())),
                    "sha256": report["candidate_sha256"], "active_sha256": active_sha,
                    "consumed": used, "id": experiment.name, "review_ids": sorted(review_ids),
                    "origin_run": origin_run,
                    "replay_offset": head.get("replay_offset", 0) + max(1, report["training"]["steps"] // 2)})
        except Exception as exc:
            report.update(state="failed", error=type(exc).__name__ + ": " + str(exc)[:200])
        report["finished"] = tc._now()
        tc._write(experiment / "report.json", report)
        tc._write(root() / "last.json", report)
        return report


def trigger():
    """Queue a detached update after a reviewed answer; never block the chat with training."""
    if settings()["enabled"] is not True or busy() or tc._active_job():
        return False
    root().mkdir(parents=True, exist_ok=True)
    tc._spawn([sys.executable, str(tc.CLI), "continual-worker"], root() / "worker.log")
    return True


def worker():
    try:
        return run()
    except Exception as exc:
        # A duplicate worker must never overwrite the running worker's evidence.
        if busy():
            return {"state": "deferred"}
        report = {"state": "failed", "finished": tc._now(),
                  "error": type(exc).__name__ + ": " + str(exc)[:200]}
        tc._write(root() / "last.json", report)
        return report


def activate(expected_id):
    """Explicit UI action, with integrity and current-parent checks."""
    with lock():
        head = tc._read(root() / "head.json", {}) or {}
        if not expected_id or head.get("id") != expected_id:
            raise ValueError("Предложение изменилось; обновите страницу")
        candidate = root() / head["candidate"]
        if tc._sha256(_source()) != head["active_sha256"] or tc._sha256(candidate) != head["sha256"]:
            raise ValueError("Модель изменилась или повреждена")
        if head["active_sha256"] == head["sha256"]:
            return tc.active()
        if set(head["review_ids"]) != {r["id"] for r in reviewed()}:
            raise ValueError("Использованный опыт удалён или исправлен; сначала повторите обучение")
        current = tc._read(tc.folder() / "active-brain.json")
        history = tc._read(tc.folder() / "active-history.json", []) or []
        history.append({"pointer": current, "meta": tc._read(tc.folder() / "active-meta.json", {})})
        tc._write(tc.folder() / "active-history.json", history[-20:])
        tc._point_to(candidate.relative_to(tc.folder()).as_posix(),
                     {"run": None, "origin_run": head["origin_run"], "step": None,
                      "sha256": head["sha256"], "by": "user", "activated": tc._now()})
        # Preserve replay history when this head becomes the active baseline.
        head["active_sha256"] = head["sha256"]
        tc._write(root() / "head.json", head)
        return tc.active()


def status():
    head = tc._read(root() / "head.json", {}) or {}
    last = tc._read(root() / "last.json")
    return {"settings": settings(), "busy": busy(), "last": last,
            "proposal": head.get("id") if head.get("active_sha256") != head.get("sha256") else None,
            "reviewed_only": True, "automatic_activation": False}


def stop():
    root().mkdir(parents=True, exist_ok=True)
    (root() / "stop").touch()
    # Prevent new workers from starting; current worker checks stop between steps.
    tc._write(root() / "settings.json", dict(settings(), enabled=False))
    return {"stop_requested": True}
