"""Local training center behind the «Обучение» page.

One durable folder outside the release directory holds training data, runs, model
versions and the active-brain pointer. Training runs in a detached worker that resumes
the single BPE checkpoint in short chunks, so the page can show progress and stop it
safely between chunks. Nothing is activated automatically and there is no CPU fallback
hidden behind a CUDA request.
"""
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "training-center.py"
TORCH_INDEX = "https://download.pytorch.org/whl/cu126"
MIN_LONG_RECORDS = 10000
MAX_DATA_BYTES = 30_000_000
CHUNK_SECONDS = 15
STALE_SECONDS = 90
STARTING_GRACE = 180
PILOT_SECONDS = 300
DEFAULT_CONFIG = {"width": 320, "heads": 8, "layers": 4, "context": 256,
                  "max_merges": 128, "seed": 42, "checkpoint_every": 100}
RUN_ID = re.compile(r"^[0-9]{8}-[0-9]{6}-(pilot|long)\Z")
DATA_NAME = re.compile(r"^[^\\/:*?\"<>|]{1,120}\.json\Z")

ERRORS = {
    "At least 10 explicitly authorized records required": "Нужно от 10 до 100 000 записей",
    "Every supplied record must have explicit consent": "У каждой записи должно быть \"consent\": true",
    "Source and supported license required": "У каждой записи нужны source и license (user-consent, public-domain или synthetic)",
    "Invalid dialogue text": "prompt и answer должны быть строками от 1 до 2000 символов",
    "Potential secret/PII: manual review required": "Похоже на почту, пароль или ключ: проверьте записи вручную",
    "Duplicate prompt can leak across splits": "Есть повторяющиеся вопросы (prompt)",
}


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def base_dir():
    override = os.environ.get("YORIKA_HOME")
    if override:
        return Path(override)
    if os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "Yorika"
    return Path.home() / ".local" / "share" / "yorika"


def _read(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(temp, path)


def folder():
    saved = _read(base_dir() / "training-settings.json", {}) or {}
    chosen = saved.get("folder") if isinstance(saved, dict) else None
    return Path(chosen) if chosen else base_dir() / "training"


def _system():
    return base_dir() / "training-system"


def set_folder(path):
    if not isinstance(path, str) or not path.strip() or len(path) > 400:
        raise ValueError("Укажите полный путь к папке")
    target = Path(path.strip())
    if not target.is_absolute():
        raise ValueError("Нужен полный путь, например D:\\Yorika-обучение")
    if _active_job():
        raise ValueError("Сначала остановите текущее обучение")
    try:
        (target / "data").mkdir(parents=True, exist_ok=True)
    except OSError:
        raise ValueError("Не удалось создать папку по этому пути")
    _write(base_dir() / "training-settings.json", {"folder": str(target)})
    return {"folder": str(target)}


def open_folder(which):
    places = {"data": folder() / "data", "results": folder()}
    if which not in places:
        raise ValueError("Неизвестная папка")
    places[which].mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        raise ValueError("Открыть папку можно только в Windows")
    os.startfile(str(places[which]))  # noqa: S606 - fixed local folder chosen above
    return {"opened": str(places[which])}


# ---- hardware -------------------------------------------------------------

def torch_state():
    installed = importlib.util.find_spec("torch") is not None
    version = None
    if installed:
        try:
            from importlib.metadata import version as package_version
            version = package_version("torch")
        except Exception:
            version = None
    install = _read(_system() / "torch-install.json", {}) or {}
    log_tail = []
    log = _system() / "torch-install.log"
    if log.is_file():
        try:
            lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
            log_tail = [line[-200:] for line in lines if line.strip()][-4:]
        except OSError:
            pass
    running = install.get("state") == "running" and time.time() - install.get("started", 0) < 3600
    return {"installed": installed, "version": version,
            "install": {"state": install.get("state") if install else None, "running": running,
                        "code": install.get("code"), "log": log_tail},
            "python": "%d.%d" % sys.version_info[:2]}


def probe():
    """Runs the read-only CUDA probe and keeps its last result."""
    spec = importlib.util.spec_from_file_location("cuda_probe", ROOT / "scripts" / "probe-language-cuda.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.probe(require_cuda=False)
    result["checked_at"] = _now()
    _write(_system() / "probe.json", result)
    return result


def install_torch():
    state = torch_state()
    if state["installed"]:
        raise ValueError("PyTorch уже установлен")
    if state["install"]["running"]:
        raise ValueError("Установка уже идёт")
    _system().mkdir(parents=True, exist_ok=True)
    _write(_system() / "torch-install.json", {"state": "running", "started": time.time()})
    log = _system() / "torch-install.log"
    log.write_text("", encoding="utf-8")
    _spawn([sys.executable, str(CLI), "pip-worker"], log)
    return {"started": True}


def pip_worker():
    log = _system() / "torch-install.log"
    with log.open("ab") as out:
        code = subprocess.call([sys.executable, "-m", "pip", "install", "torch", "--index-url", TORCH_INDEX],
                               stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT)
    _write(_system() / "torch-install.json", {"state": "done" if code == 0 else "failed",
                                              "code": code, "finished": _now()})
    return code


def _spawn(args, log_path):
    flags = 0
    if os.name == "nt":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    with open(log_path, "ab") as log:
        # The tray waits for this command's stdout to close, so the worker must not inherit it.
        subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                         creationflags=flags, close_fds=True, cwd=str(ROOT),
                         start_new_session=os.name != "nt")


# ---- data -----------------------------------------------------------------

def pilot_records():
    """Synthetic arithmetic dialogues: enough to measure speed and memory, never a real corpus."""
    return [{"prompt": "Сколько будет %d плюс %d?" % (a, b), "answer": "%d плюс %d будет %d." % (a, b, a + b),
             "source": "yorika-pilot-synthetic", "license": "synthetic", "consent": True}
            for a in range(1, 9) for b in range(1, 9)]


def data_files():
    directory = folder() / "data"
    if not directory.is_dir():
        return []
    return [{"name": p.name, "bytes": p.stat().st_size}
            for p in sorted(directory.glob("*.json")) if p.is_file()][:200]


def _load_records(name):
    if not isinstance(name, str) or not DATA_NAME.match(name):
        raise ValueError("Выберите JSON-файл из папки данных")
    path = folder() / "data" / name
    if not path.is_file():
        raise ValueError("Файл не найден в папке данных")
    if not 0 < path.stat().st_size <= MAX_DATA_BYTES:
        raise ValueError("Файл пустой или больше 30 МБ")
    try:
        records = json.loads(path.read_text(encoding="utf-8-sig"))
    except (UnicodeDecodeError, ValueError):
        raise ValueError("Файл не читается как JSON в UTF-8")
    return records


def long_gate(records):
    """Same rule as run-long-cuda-campaign.py: enough records, each reviewed for rights and quality."""
    if len(records) < MIN_LONG_RECORDS:
        return "Для долгого обучения нужно не меньше %d записей, сейчас %d" % (MIN_LONG_RECORDS, len(records))
    if any(not isinstance(r.get("rights_reviewed_by"), str) or not r["rights_reviewed_by"].strip() or
           r.get("quality_reviewed") is not True for r in records):
        return "У каждой записи для долгого обучения нужны rights_reviewed_by и \"quality_reviewed\": true"
    return None


def _prepare(records):
    from backend.neural_corpus_v2 import prepare
    try:
        return prepare(records)
    except ValueError as error:
        raise ValueError(ERRORS.get(str(error), "Данные не прошли проверку"))


def check_data(name):
    records = _load_records(name)
    try:
        data = _prepare(records)
    except ValueError as error:
        return {"name": name, "ok": False, "reason": str(error), "long_ready": False}
    blocker = long_gate(records)
    return {"name": name, "ok": True, "count": data["manifest"]["count"],
            "train": len(data["train"]), "validation": len(data["validation"]), "test": len(data["test"]),
            "long_ready": blocker is None, "long_blocker": blocker}


# ---- runs -----------------------------------------------------------------

def _run_dir(run_id):
    if not isinstance(run_id, str) or not RUN_ID.match(run_id):
        raise ValueError("Неизвестная версия")
    path = folder() / "runs" / run_id
    if not (path / "run.json").is_file():
        raise ValueError("Неизвестная версия")
    return path


def _progress(path):
    progress = _read(path / "progress.json", {}) or {}
    state = progress.get("state")
    if state in ("starting", "running"):
        beat = _read(path / "heartbeat.json", {}) or {}
        last = max(beat.get("t", 0), progress.get("t", 0))
        limit = STARTING_GRACE if state == "starting" else STALE_SECONDS
        if time.time() - last > limit:
            progress["state"] = "interrupted"
    return progress


def _summary(path):
    run = _read(path / "run.json", {}) or {}
    progress = _progress(path)
    best = path / "language-longrun.pt.best.pt"
    return {"id": run.get("id"), "mode": run.get("mode"), "dataset": run.get("dataset"),
            "device": run.get("device"), "created": run.get("created"),
            "total_steps": run.get("total_steps"), "time_limit": run.get("time_limit"),
            "state": progress.get("state", "unknown"), "steps": progress.get("steps", 0),
            "elapsed": progress.get("elapsed", 0), "best_nll": progress.get("best_nll"),
            "best_step": progress.get("best_step"), "gpu_name": progress.get("gpu_name"),
            "peak_vram": progress.get("peak_vram"), "speed": progress.get("speed"),
            "parameters": progress.get("parameters"), "error": progress.get("error"),
            "history": progress.get("history", []), "has_best": best.is_file(),
            "resumable": progress.get("state") in ("paused", "interrupted") and run.get("mode") == "long"}


def runs():
    directory = folder() / "runs"
    if not directory.is_dir():
        return []
    items = [_summary(p) for p in sorted(directory.iterdir(), reverse=True)
             if p.is_dir() and RUN_ID.match(p.name) and (p / "run.json").is_file()]
    return items[:50]


def _active_job():
    for item in runs():
        if item["state"] in ("starting", "running"):
            return item
    return None


def start(mode, *, dataset=None, device="cuda", total_steps=100000, hours=8.0, config=None, launch=True):
    if mode not in ("pilot", "long"):
        raise ValueError("Неизвестный режим")
    if device not in ("cpu", "cuda"):
        raise ValueError("Выберите видеокарту или процессор")
    if _active_job():
        raise ValueError("Обучение уже идёт")
    if mode == "pilot":
        records, dataset, total_steps, limit = pilot_records(), None, 1000000, PILOT_SECONDS
    else:
        records = _load_records(dataset)
        if (type(total_steps) is not int or not 100 <= total_steps <= 1000000 or
                type(hours) not in (int, float) or not 0.1 <= hours <= 72):
            raise ValueError("Шагов от 100 до 1 000 000, времени от 0,1 до 72 часов")
        limit = int(hours * 3600)
    data = _prepare(records)
    if mode == "long":
        blocker = long_gate(records)
        if blocker:
            raise ValueError(blocker)
    if importlib.util.find_spec("torch") is None:
        raise ValueError("Сначала установите PyTorch в блоке «Видеокарта»")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + mode
    path = folder() / "runs" / run_id
    if path.exists():
        raise ValueError("Подождите секунду и запустите снова")
    path.mkdir(parents=True)
    _write(path / "run.json", {"schema": "yorika-training-run-v1", "id": run_id, "mode": mode,
                               "dataset": dataset, "manifest": data["manifest"], "device": device,
                               "config": dict(config or DEFAULT_CONFIG), "total_steps": total_steps,
                               "time_limit": limit, "created": _now()})
    _write(path / "progress.json", {"state": "starting", "t": time.time(), "steps": 0, "history": []})
    if launch:
        _spawn([sys.executable, str(CLI), "worker", run_id], path / "worker.log")
    return {"id": run_id}


def control(run_id, action):
    path = _run_dir(run_id)
    item = _summary(path)
    if action in ("pause", "stop"):
        if item["state"] not in ("starting", "running"):
            raise ValueError("Это обучение сейчас не идёт")
        _write(path / "control.json", {"request": action, "t": _now()})
        return {"requested": action}
    if action == "resume":
        if not item["resumable"]:
            raise ValueError("Эту версию нельзя продолжить")
        if _active_job():
            raise ValueError("Обучение уже идёт")
        (path / "control.json").unlink(missing_ok=True)
        progress = _read(path / "progress.json", {}) or {}
        progress.update({"state": "starting", "t": time.time(), "error": None})
        _write(path / "progress.json", progress)
        _spawn([sys.executable, str(CLI), "worker", run_id], path / "worker.log")
        return {"resumed": run_id}
    raise ValueError("Неизвестное действие")


def _heartbeat(path, stop):
    while not stop.wait(5):
        try:
            _write(path / "heartbeat.json", {"t": time.time()})
        except OSError:
            pass


def worker(run_id):
    path = _run_dir(run_id)
    run_info = _read(path / "run.json")
    progress = _read(path / "progress.json", {}) or {}
    history = list(progress.get("history", []))
    elapsed = float(progress.get("elapsed", 0))
    stop = threading.Event()
    beat = threading.Thread(target=_heartbeat, args=(path, stop), daemon=True)
    _write(path / "heartbeat.json", {"t": time.time()})
    beat.start()

    def save(**fields):
        progress.update(fields, t=time.time(), history=history[-600:], elapsed=round(elapsed, 1))
        _write(path / "progress.json", progress)

    try:
        import torch
        from backend.neural_language_longrun import run
        records = pilot_records() if run_info["mode"] == "pilot" else _load_records(run_info["dataset"])
        data = _prepare(records)
        if data["manifest"] != run_info["manifest"]:
            raise ValueError("Файл данных изменился после запуска; начните новое обучение")
        device = run_info["device"]
        if device == "cuda" and not torch.cuda.is_available():
            raise ValueError("Видеокарта недоступна для PyTorch; переход на процессор не делается сам")
        gpu = torch.cuda.get_device_name(0) if device == "cuda" else None
        cfg = run_info["config"]
        save(state="running", gpu_name=gpu, error=None)
        while True:
            request = (_read(path / "control.json", {}) or {}).get("request")
            if request in ("pause", "stop"):
                (path / "control.json").unlink(missing_ok=True)
                save(state="paused" if request == "pause" and run_info["mode"] == "long" else "stopped")
                return 0
            if progress.get("steps", 0) >= run_info["total_steps"] or elapsed >= run_info["time_limit"]:
                save(state="finished")
                return 0
            chunk = max(1.0, min(CHUNK_SECONDS, run_info["time_limit"] - elapsed))
            began = time.monotonic()
            status = run(data["train"], data["validation"], path / "language-longrun.pt",
                         total_steps=run_info["total_steps"], checkpoint_every=cfg["checkpoint_every"],
                         width=cfg["width"], heads=cfg["heads"], layers=cfg["layers"],
                         context=cfg["context"], max_merges=cfg["max_merges"], seed=cfg["seed"],
                         max_run_seconds=chunk, device=device)
            elapsed += time.monotonic() - began
            if status["steps"] <= status["resumed_from"] and status["steps"] < run_info["total_steps"]:
                raise RuntimeError("Обучение не продвигается")
            if status["validation_nll"] is not None:
                history.append({"step": status["steps"], "nll": round(status["validation_nll"], 4),
                                "t": round(elapsed, 1)})
            peak = status.get("peak_cuda_allocated_bytes")
            save(steps=status["steps"], best_nll=status["best_validation_nll"], best_step=status["best_step"],
                 speed=round(status["steps_per_second"], 2), parameters=status["parameters"],
                 peak_vram=max(peak or 0, progress.get("peak_vram") or 0) or None)
    except Exception as error:  # the page must see why the worker ended
        message = str(error) if re.search("[а-яА-Я]", str(error)) else "Обучение остановилось с ошибкой: %s" % type(error).__name__
        if "out of memory" in str(error).lower():
            message = "Не хватило памяти видеокарты"
        save(state="failed", error=message[:200])
        print(repr(error), file=sys.stderr)
        return 1
    finally:
        stop.set()


# ---- versions -------------------------------------------------------------

def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def active():
    pointer = _read(folder() / "active-brain.json")
    meta = _read(folder() / "active-meta.json", {}) or {}
    if not pointer:
        return None
    return {"checkpoint": pointer.get("checkpoint"), "run": meta.get("run"), "step": meta.get("step"),
            "activated": meta.get("activated")}


def _point_to(relative, meta):
    _write(folder() / "active-brain.json", {"schema": 1, "checkpoint": relative,
                                            "engine": "yorika-own-transformer", "automatic": False})
    _write(folder() / "active-meta.json", meta)


def activate(run_id):
    path = _run_dir(run_id)
    item = _summary(path)
    if item["mode"] != "long":
        raise ValueError("Пробная версия обучена на тестовых данных и не может стать активной")
    if item["state"] in ("starting", "running"):
        raise ValueError("Дождитесь паузы или окончания обучения")
    best = path / "language-longrun.pt.best.pt"
    if not best.is_file():
        raise ValueError("У этой версии ещё нет сохранённой лучшей точки")
    brains = folder() / "brains"
    brains.mkdir(parents=True, exist_ok=True)
    target = brains / ("%s-step%d.pt" % (run_id, item["best_step"] or 0))
    if not target.exists():
        temp = target.with_name(target.name + ".tmp")
        shutil.copyfile(best, temp)
        os.replace(temp, target)
    history = _read(folder() / "active-history.json", []) or []
    current = _read(folder() / "active-brain.json")
    if current:
        history.append({"pointer": current, "meta": _read(folder() / "active-meta.json", {})})
        _write(folder() / "active-history.json", history[-20:])
    meta = {"run": run_id, "step": item["best_step"], "sha256": _sha256(target), "activated": _now(),
            "by": "user"}
    _point_to(target.relative_to(folder()).as_posix(), meta)
    return active()


def rollback():
    history = _read(folder() / "active-history.json", []) or []
    if not _read(folder() / "active-brain.json"):
        raise ValueError("Активной версии нет")
    if history:
        previous = history.pop()
        _point_to(previous["pointer"]["checkpoint"], previous.get("meta") or {})
        _write(folder() / "active-history.json", history)
    else:
        (folder() / "active-brain.json").unlink()
        (folder() / "active-meta.json").unlink(missing_ok=True)
    return active()


def _answer(model, state, prompt, max_tokens):
    import torch
    from backend.neural_bpe_v1 import OFFSET, SPECIAL, encode
    tokenizer, context = state["tokenizer"], state["config"][3]
    ids = [1, 3] + encode(prompt, tokenizer) + [4]
    out = []
    with torch.inference_mode():
        for _ in range(max_tokens):
            token = int(model(torch.tensor([ids[-context:]], dtype=torch.long))[0, -1].argmax())
            if token == 2:
                break
            ids.append(token)
            if token >= len(SPECIAL):
                out.append(token)
    pieces = [bytes([i]) for i in range(256)]
    for left, right in tokenizer["merges"]:
        pieces.append(pieces[left - OFFSET] + pieces[right - OFFSET])
    return b"".join(pieces[t - OFFSET] for t in out).decode("utf-8", errors="replace")


def compare(run_ids, questions):
    if not isinstance(run_ids, list) or not 1 <= len(run_ids) <= 2 or len(set(run_ids)) != len(run_ids):
        raise ValueError("Выберите одну или две версии")
    if (not isinstance(questions, list) or not 1 <= len(questions) <= 5 or
            any(not isinstance(q, str) or not q.strip() or len(q) > 300 for q in questions)):
        raise ValueError("Нужно от 1 до 5 вопросов, каждый до 300 символов")
    from backend.neural_language_benchmark import load_candidate
    columns = []
    for run_id in run_ids:
        best = _run_dir(run_id) / "language-longrun.pt.best.pt"
        if not best.is_file():
            raise ValueError("У версии %s ещё нет сохранённой лучшей точки" % run_id)
        model, state = load_candidate(best)
        columns.append({"id": run_id, "step": state["step"],
                        "answers": [_answer(model, state, q.strip(), 64) for q in questions]})
    return {"questions": [q.strip() for q in questions], "versions": columns,
            "note": "Ответы получены жадным выбором слов; сравнивайте сами, это не оценка людьми"}


def status():
    where = folder()
    return {"folder": str(where), "onedrive": "onedrive" in str(where).lower(),
            "data_folder": str(where / "data"), "torch": torch_state(),
            "probe": _read(_system() / "probe.json"), "data": data_files(), "runs": runs(),
            "active": active(), "min_long_records": MIN_LONG_RECORDS}
