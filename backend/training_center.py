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
                  "max_merges": 128, "seed": 42, "checkpoint_every": 100,
                  # 16 examples per step and half precision on the GPU: same model, many times more examples per hour.
                  "batch_size": 16, "accumulate": 1, "precision": "auto"}
# Model sizes the owner can pick. "l" needs about 2 GB of video memory (estimate), so it takes
# half the batch per step and accumulates two of them: the same 16 examples per update.
SIZES = {"s": {"width": 320, "heads": 8, "layers": 4},
         "m": {"width": 512, "heads": 8, "layers": 8},
         "l": {"width": 640, "heads": 10, "layers": 10, "batch_size": 8, "accumulate": 2}}
RUN_ID = re.compile(r"^[0-9]{8}-[0-9]{6}-(pilot|long|pretrain)\Z")
TEXT_NAME = re.compile(r"^[^\\/:*?\"<>|]{1,120}\.txt\Z")
TEXT_LICENSES = ("public-domain", "user-consent")
MAX_TEXT_BYTES = 50_000_000
MIN_TEXT_CHUNKS = 20
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


# ---- open texts for pretraining ---------------------------------------------

def _texts_dir():
    return folder() / "data" / "тексты"


def _approvals():
    return _read(folder() / "texts.json", {}) or {}


def texts():
    directory = _texts_dir()
    directory.mkdir(parents=True, exist_ok=True)
    approvals, items = _approvals(), []
    for path in sorted(directory.glob("*.txt"))[:200]:
        if not path.is_file():
            continue
        approval = approvals.get(path.name) or {}
        # An edited file loses its approval: the owner checked a different text.
        approved = bool(approval) and approval.get("size") == path.stat().st_size and approval.get("sha256") == _sha256(path)
        items.append({"name": path.name, "bytes": path.stat().st_size, "approved": approved,
                      "license": approval.get("license") if approved else None})
    return {"folder": str(directory), "files": items}


def approve_text(name, license, approved=True):
    if not isinstance(name, str) or not TEXT_NAME.match(name):
        raise ValueError("Выберите .txt файл из папки текстов")
    path = _texts_dir() / name
    if not path.is_file():
        raise ValueError("Файл не найден в папке текстов")
    approvals = _approvals()
    if approved:
        if license not in TEXT_LICENSES:
            raise ValueError("Укажите права: общественное достояние или ваш собственный текст")
        approvals[name] = {"license": license, "sha256": _sha256(path), "size": path.stat().st_size,
                           "rights_reviewed_by": "владелец Yorika", "approved": _now()}
    else:
        approvals.pop(name, None)
    _write(folder() / "texts.json", approvals)
    return texts()


def _chunks(text, size=1000):
    out, current = [], ""
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = " ".join(paragraph.split())
        while len(paragraph) > size:
            out.append(paragraph[:size])
            paragraph = paragraph[size:]
        if current and len(current) + len(paragraph) + 1 > size:
            out.append(current)
            current = ""
        current = (current + "\n" + paragraph).strip() if paragraph else current
    if current:
        out.append(current)
    return out


def pretrain_corpus():
    """Approved texts cut into chunks; every 10th chunk (by content hash) is validation, another the exam."""
    listing = [f for f in texts()["files"] if f["approved"]]
    if not listing:
        raise ValueError("Отметьте хотя бы один текст: права проверены")
    if sum(f["bytes"] for f in listing) > MAX_TEXT_BYTES:
        raise ValueError("Тексты вместе больше 50 МБ")
    train, validation, test, manifest = [], [], [], []
    for item in listing:
        path = _texts_dir() / item["name"]
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            raise ValueError("Файл %s не в кодировке UTF-8" % item["name"])
        manifest.append({"name": item["name"], "sha256": _sha256(path), "license": item["license"]})
        for chunk in _chunks(text):
            if len(chunk) < 40:
                continue
            bucket = int(hashlib.sha256(chunk.encode("utf-8")).hexdigest()[:8], 16) % 10
            (validation if bucket == 0 else test if bucket == 1 else train).append(chunk)
    if len(train) < MIN_TEXT_CHUNKS or not validation or not test:
        raise ValueError("Текстов мало: нужно хотя бы около 100 КБ")
    return {"train": train, "validation": validation, "test": test,
            "manifest": {"schema": "yorika-pretrain-texts-v1", "texts": manifest,
                         "train": len(train), "validation": len(validation), "test": len(test)}}


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
            "examples_speed": progress.get("examples_speed"), "exam_nll": progress.get("exam_nll"),
            "exam_count": progress.get("exam_count"), "base": run.get("base"),
            "batch_size": (run.get("config") or {}).get("batch_size", 1),
            "precision": (run.get("config") or {}).get("precision", "fp32"),
            "size": (run.get("config") or {}).get("size", "s"), "series": run.get("series"),
            "exam_per_char": progress.get("exam_per_char"), "old_exams": progress.get("old_exams", []),
            # The page needs the score; the answers stay in progress.json for whoever wants to read them.
            "honesty": {k: v for k, v in (progress.get("honesty") or {}).items() if k != "answers"} or None,
            "history": progress.get("history", []), "has_best": best.is_file(),
            "resumable": progress.get("state") in ("paused", "interrupted") and run.get("mode") in ("long", "pretrain")}


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


def config_for(size):
    if size not in SIZES:
        raise ValueError("Размер модели: s, m или l")
    return dict(DEFAULT_CONFIG, **SIZES[size], size=size)


def start(mode, *, dataset=None, device="cuda", total_steps=100000, hours=8.0, config=None, launch=True, base=None,
          size="s", series=None):
    if mode not in ("pilot", "long", "pretrain"):
        raise ValueError("Неизвестный режим")
    config = dict(config) if config else config_for(size)
    config.setdefault("size", size)
    if device not in ("cpu", "cuda"):
        raise ValueError("Выберите видеокарту или процессор")
    if _active_job():
        raise ValueError("Обучение уже идёт")
    if mode != "pilot" and (type(total_steps) is not int or not 100 <= total_steps <= 1000000 or
                            type(hours) not in (int, float) or not 0.1 <= hours <= 72):
        raise ValueError("Шагов от 100 до 1 000 000, времени от 0,1 до 72 часов")
    if base is not None:
        if mode != "long":
            raise ValueError("Основу из предобучения можно взять только для долгого обучения")
        base_item = _summary(_run_dir(base))
        if base_item["mode"] != "pretrain" or not base_item["has_best"]:
            raise ValueError("Основой может быть только предобучение с сохранённой лучшей точкой")
        if base_item["size"] != config.get("size", "s"):
            raise ValueError("Основа другого размера: выберите тот же размер модели, что у предобучения")
    if mode == "pilot":
        records, dataset, total_steps, limit = pilot_records(), None, 1000000, PILOT_SECONDS
    elif mode == "pretrain":
        records, dataset, limit = None, None, int(hours * 3600)
    else:
        records = _load_records(dataset)
        limit = int(hours * 3600)
    data = pretrain_corpus() if mode == "pretrain" else _prepare(records)
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
                               "config": config, "total_steps": total_steps,
                               "time_limit": limit, "created": _now(), "base": base, "series": series})
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


def start_series(dataset, sizes, *, device="cuda", total_steps=100000, hours_each=2.0, launch=True):
    """Sandbox: the same data, several model sizes one after another, compared on the same exam."""
    if (not isinstance(sizes, list) or not 2 <= len(sizes) <= 3 or len(set(sizes)) != len(sizes) or
            any(size not in SIZES for size in sizes)):
        raise ValueError("Выберите от двух до трёх разных размеров")
    series_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    first = start("long", dataset=dataset, device=device, total_steps=total_steps, hours=hours_each,
                  size=sizes[0], series=series_id, launch=launch)
    _write(folder() / "series.json", {"id": series_id, "dataset": dataset, "device": device,
                                       "total_steps": total_steps, "hours_each": hours_each,
                                       "queue": sizes[1:], "runs": [first["id"]], "created": _now(),
                                       "launch": launch})
    return {"series": series_id, "first": first["id"], "queue": sizes[1:]}


def series():
    return _read(folder() / "series.json")


def _continue_series(run_id):
    """Called when a series run finishes: starts the next size, if any is left."""
    plan = series()
    if not plan or run_id not in plan.get("runs", []) or not plan.get("queue"):
        return None
    size = plan["queue"].pop(0)
    try:
        nxt = start("long", dataset=plan["dataset"], device=plan["device"], total_steps=plan["total_steps"],
                    hours=plan["hours_each"], size=size, series=plan["id"], launch=plan.get("launch", True))
    except ValueError as error:
        plan["error"] = str(error)
        _write(folder() / "series.json", plan)
        return None
    plan["runs"].append(nxt["id"])
    _write(folder() / "series.json", plan)
    return nxt["id"]


def stop_all():
    """Emergency stop: asks every running training to stop at the next chunk."""
    plan = series()
    if plan and plan.get("queue"):
        plan["queue"], plan["error"] = [], "Остановлено кнопкой «Стоп всё»"
        _write(folder() / "series.json", plan)
    stopped = []
    for item in runs():
        if item["state"] in ("starting", "running"):
            _write(_run_dir(item["id"]) / "control.json", {"request": "stop", "t": _now(), "emergency": True})
            stopped.append(item["id"])
    return {"stopped": stopped}


def _exam(path, data, lm, save):
    """Scores the best checkpoint on the test split no training step has seen."""
    best = path / "language-longrun.pt.best.pt"
    if not best.is_file():
        return
    from backend.neural_language_benchmark import load_candidate
    from backend.neural_language_longrun import score_checkpoint
    loaded = load_candidate(best)
    try:
        exam = score_checkpoint(best, data["test"], objective="lm" if lm else "dialogue", loaded=loaded)
    except ValueError:
        return
    save(exam_nll=round(exam["nll"], 4), exam_count=exam["count"], exam_per_char=round(exam["per_char"], 4))
    if lm or path.name.endswith("-pilot"):
        return
    # Old exams: the test splits of earlier dialogue versions. Scored per character, so a
    # version with another tokenizer compares fairly; worse than the old version means forgetting.
    old = []
    for item in runs():
        if (item["id"] == path.name or item["mode"] != "long" or item.get("exam_per_char") is None or
                not item.get("dataset") or len(old) >= 5):
            continue
        try:
            test = _prepare(_load_records(item["dataset"]))["test"]
            mine = score_checkpoint(best, test, loaded=loaded)["per_char"]
        except ValueError:
            continue
        old.append({"run": item["id"], "theirs": item["exam_per_char"], "mine": round(mine, 4)})
    save(old_exams=old)
    try:
        from backend import honesty
        save(honesty=honesty.exam(loaded))
    except (ValueError, ImportError):
        pass


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
        lm = run_info["mode"] == "pretrain"
        if lm:
            data = pretrain_corpus()
        else:
            records = pilot_records() if run_info["mode"] == "pilot" else _load_records(run_info["dataset"])
            data = _prepare(records)
        if data["manifest"] != run_info["manifest"]:
            raise ValueError("Данные изменились после запуска; начните новое обучение")
        device = run_info["device"]
        if device == "cuda" and not torch.cuda.is_available():
            raise ValueError("Видеокарта недоступна для PyTorch; переход на процессор не делается сам")
        gpu = torch.cuda.get_device_name(0) if device == "cuda" else None
        cfg = run_info["config"]
        precision = cfg.get("precision", "fp32")
        if precision == "auto":
            # Resolved once and saved, so every resumed chunk uses the same precision.
            precision = ("bf16" if torch.cuda.is_bf16_supported() else "fp16") if device == "cuda" else "fp32"
            cfg["precision"] = precision
            _write(path / "run.json", run_info)
        init_from = None
        if run_info.get("base"):
            init_from = _run_dir(run_info["base"]) / "language-longrun.pt.best.pt"
        save(state="running", gpu_name=gpu, error=None)
        while True:
            request = (_read(path / "control.json", {}) or {}).get("request")
            if request in ("pause", "stop"):
                (path / "control.json").unlink(missing_ok=True)
                _exam(path, data, lm, save)
                save(state="paused" if request == "pause" and run_info["mode"] != "pilot" else "stopped")
                return 0
            if progress.get("steps", 0) >= run_info["total_steps"] or elapsed >= run_info["time_limit"]:
                _exam(path, data, lm, save)
                save(state="finished")
                _continue_series(run_id)
                return 0
            chunk = max(1.0, min(CHUNK_SECONDS, run_info["time_limit"] - elapsed))
            began = time.monotonic()
            status = run(data["train"], data["validation"], path / "language-longrun.pt",
                         total_steps=run_info["total_steps"], checkpoint_every=cfg["checkpoint_every"],
                         width=cfg["width"], heads=cfg["heads"], layers=cfg["layers"],
                         context=cfg["context"], max_merges=cfg["max_merges"], seed=cfg["seed"],
                         max_run_seconds=chunk, device=device, batch_size=cfg.get("batch_size", 1),
                         accumulate=cfg.get("accumulate", 1), precision=precision,
                         objective="lm" if lm else "dialogue", init_from=init_from)
            elapsed += time.monotonic() - began
            if status["steps"] <= status["resumed_from"] and status["steps"] < run_info["total_steps"]:
                raise RuntimeError("Обучение не продвигается")
            if status["validation_nll"] is not None:
                history.append({"step": status["steps"], "nll": round(status["validation_nll"], 4),
                                "t": round(elapsed, 1)})
            peak = status.get("peak_cuda_allocated_bytes")
            save(steps=status["steps"], best_nll=status["best_validation_nll"], best_step=status["best_step"],
                 speed=round(status["steps_per_second"], 2), parameters=status["parameters"],
                 examples_speed=round(status["examples_per_second"], 1),
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
    if item["mode"] == "pretrain":
        raise ValueError("Предобучение знает язык, но не умеет отвечать: возьмите его основой для долгого обучения")
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


def _with_tools(answer):
    from backend.tools import run_tools
    try:
        return run_tools(answer)[0]
    except Exception:  # noqa: BLE001 - a broken tool must not hide the model's own answer
        return answer


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
                        "answers": [_with_tools(_answer(model, state, q.strip(), 64)) for q in questions]})
    return {"questions": [q.strip() for q in questions], "versions": columns,
            "note": "Ответы получены жадным выбором слов; сравнивайте сами, это не оценка людьми"}


def status():
    where = folder()
    return {"folder": str(where), "onedrive": "onedrive" in str(where).lower(),
            "data_folder": str(where / "data"), "torch": torch_state(),
            "probe": _read(_system() / "probe.json"), "data": data_files(), "runs": runs(),
            "active": active(), "min_long_records": MIN_LONG_RECORDS, "texts": texts(),
            "sizes": {k: dict(v) for k, v in SIZES.items()}, "series": series()}
