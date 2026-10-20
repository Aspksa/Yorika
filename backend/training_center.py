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
# New versions use 1024–2048 word pieces instead of 128 (words cost one or two tokens, not five)
# and the pre-norm "lab" network that can grow and think in loops.
SIZES = {"s": {"width": 320, "heads": 8, "layers": 4, "max_merges": 1024},
         "m": {"width": 512, "heads": 8, "layers": 8, "max_merges": 2048},
         "l": {"width": 640, "heads": 10, "layers": 10, "batch_size": 8, "accumulate": 2, "max_merges": 2048}}
KINDS = ("quick", "sleep", "evolution", "merge", "grow", "swarm", "copy", "branch", "distill", "selfcheck",
         "hemispheres", "rebirth", "ecosystem", "coevolve", "redqueen", "baldwin", "es")
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
            "forward_forward": progress.get("forward_forward"),
            # The page needs the score; the answers stay in progress.json for whoever wants to read them.
            "honesty": {k: v for k, v in (progress.get("honesty") or {}).items() if k != "answers"} or None,
            "logic": progress.get("logic"), "kind": run.get("kind"), "verdict": progress.get("verdict"),
            "arch": (run.get("config") or {}).get("arch") or {}, "layers": (run.get("config") or {}).get("layers"),
            "grown_from": run.get("grown_from"), "compressed": progress.get("compressed"),
            "parent": run.get("parent"), "merged": run.get("merged"), "sim": progress.get("sim"),
            "tournament": progress.get("tournament"),
            "introspection": progress.get("introspection"), "lr": (run.get("config") or {}).get("lr"),
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


FF_STEPS = 200


def config_for(size, arch=None, ff=False):
    from backend.neural_language_bpe_v2 import check_arch
    if size not in SIZES:
        raise ValueError("Размер модели: s, m или l")
    try:
        arch = check_arch(dict({"lab": True}, **(arch or {})))
    except ValueError:
        raise ValueError("Неверные настройки устройства мозга") from None
    if type(ff) is not bool:
        raise ValueError("Неверные настройки устройства мозга")
    config = dict(DEFAULT_CONFIG, **SIZES[size], size=size, arch=arch)
    if ff:
        config["rule"] = {"ff": FF_STEPS}  # Forward-Forward warm-up of the newborn
    return config


def start(mode, *, dataset=None, device="cuda", total_steps=100000, hours=8.0, config=None, launch=True, base=None,
          size="s", series=None, arch=None, kind=None, init=None, grow=None, records=None, scheduled=False, ff=False):
    """init: a checkpoint (relative to the folder) whose weights and tokenizer the run continues;
    grow: {"from": run id, "layers": n} grows that version deeper first; records: a prepared
    dataset for internal runs (quick learning, sleep), which skip the 10 000 gate."""
    if mode not in ("pilot", "long", "pretrain"):
        raise ValueError("Неизвестный режим")
    if kind is not None and kind not in KINDS:
        raise ValueError("Неизвестный вид обучения")
    config = dict(config) if config else config_for(size, arch, ff)
    config.setdefault("size", size)
    if grow is not None:
        source = _summary(_run_dir(grow.get("from")))
        if source["mode"] != "long" or not source["has_best"]:
            raise ValueError("Вырастить можно обученную версию диалогов")
        config = dict(_read(_run_dir(source["id"]) / "run.json")["config"])
        if grow.get("rebirth"):
            pass  # same shape: dead neurons are born again (backend/growth.py rebirth)
        elif grow.get("experts"):
            # Wider instead of deeper: two experts split or removed (backend/growth.py).
            from backend.neural_language_bpe_v2 import check_arch
            try:
                config["arch"] = check_arch(dict(config.get("arch") or {}, experts=(config.get("arch") or {}).get("experts", 0) + grow["experts"]))
            except ValueError:
                raise ValueError("Экспертов может быть 2, 4, 6 или 8") from None
            if not (source["arch"] or {}).get("experts"):
                raise ValueError("У этой версии нет роя экспертов")
        else:
            config["layers"] = config["layers"] + grow.get("layers", 2)
        if config["layers"] > 16:
            raise ValueError("Больше 16 слоёв не поддерживается")
    if device not in ("cpu", "cuda"):
        raise ValueError("Выберите видеокарту или процессор")
    if _active_job():
        raise ValueError("Обучение уже идёт")
    if mode != "pilot" and (type(total_steps) is not int or not 100 <= total_steps <= 1000000 or
                            type(hours) not in (int, float) or not (0.01 if records is not None else 0.1) <= hours <= 72):
        raise ValueError("Шагов от 100 до 1 000 000, времени от 0,1 до 72 часов")
    if base is not None:
        if mode != "long":
            raise ValueError("Основу из предобучения можно взять только для долгого обучения")
        base_item = _summary(_run_dir(base))
        if base_item["mode"] != "pretrain" or not base_item["has_best"]:
            raise ValueError("Основой может быть только предобучение с сохранённой лучшей точкой")
        if base_item["size"] != config.get("size", "s") or base_item["arch"] != config.get("arch", {}):
            raise ValueError("Основа другого размера или устройства: выберите те же, что у предобучения")
    internal = records is not None
    if mode == "pilot":
        records, dataset, total_steps, limit = pilot_records(), None, 1000000, PILOT_SECONDS
    elif mode == "pretrain":
        records, dataset, limit = None, None, int(hours * 3600)
    else:
        records = records if internal else _load_records(dataset)
        limit = int(hours * 3600)
    data = pretrain_corpus() if mode == "pretrain" else _prepare(records)
    if mode == "long" and not internal and kind not in ("quick", "sleep"):
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
    if internal:
        # Internal datasets are saved next to the run, so resumed chunks read the same records.
        _write(path / "dataset.json", records)
        dataset = dataset or "(%s)" % kind
    if grow is not None:
        from backend.growth import grow as grow_brain, rebirth, reshape_experts
        try:
            source_best = _run_dir(grow["from"]) / "language-longrun.pt.best.pt"
            if grow.get("rebirth"):
                born = rebirth(source_best, path / "grown.pt", list(data["train"])[:64])
                if not born["total"]:
                    raise ValueError("Мёртвых нейронов нет: перерождать некого")
                _write(path / "reborn.json", born)
            elif grow.get("experts"):
                usage = ((_read(_run_dir(grow["from"]) / "progress.json", {}) or {}).get("introspection") or {}).get("experts")
                reshape_experts(source_best, path / "grown.pt", usage, grow["experts"])
            else:
                grow_brain(source_best, path / "grown.pt", grow.get("layers", 2))
        except ValueError:
            shutil.rmtree(path, ignore_errors=True)
            raise
        init, kind = "runs/%s/grown.pt" % run_id, kind or ("rebirth" if grow.get("rebirth") else "grow")
    parent = _parent_of(init, base, grow) or config.get("from_run")
    _write(path / "run.json", {"schema": "yorika-training-run-v1", "id": run_id, "mode": mode,
                               "dataset": dataset, "manifest": data["manifest"], "device": device,
                               "config": config, "total_steps": total_steps,
                               "time_limit": limit, "created": _now(), "base": base, "series": series,
                               "kind": kind, "init": init, "internal": internal,
                               "grown_from": grow["from"] if grow else None, "parent": parent,
                               # Started by the night cycle or a plan: pauses outside study hours.
                               "scheduled": scheduled is True})
    _write(path / "progress.json", {"state": "starting", "t": time.time(), "steps": 0, "history": []})
    if launch:
        _spawn([sys.executable, str(CLI), "worker", run_id], path / "worker.log")
    return {"id": run_id}


def _parent_of(init, base, grow):
    """The version a run starts from, for the family tree and tournaments against ancestors."""
    if grow:
        return grow["from"]
    if init:
        match = re.match(r"^runs/([0-9]{8}-[0-9]{6}-(?:pilot|long|pretrain))/", init)
        if match:
            return match.group(1)
        current = active()
        if current and current.get("checkpoint") == init:
            return current.get("run")
    return base


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
        progress.update({"state": "starting", "t": time.time(), "error": None, "paused_by": None})
        _write(path / "progress.json", progress)
        _spawn([sys.executable, str(CLI), "worker", run_id], path / "worker.log")
        return {"resumed": run_id}
    raise ValueError("Неизвестное действие")


def start_series(dataset, sizes=None, *, device="cuda", total_steps=100000, hours_each=2.0, launch=True,
                 configs=None, kind=None, arch=None, ff=False):
    """Sandbox: the same data, several model sizes (or evolution variants) one after another,
    compared on the same exam."""
    if configs is None:
        if (not isinstance(sizes, list) or not 2 <= len(sizes) <= 3 or len(set(sizes)) != len(sizes) or
                any(size not in SIZES for size in sizes)):
            raise ValueError("Выберите от двух до трёх разных размеров")
        configs = [config_for(size, arch, ff) for size in sizes]
    series_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    first = start("long", dataset=dataset, device=device, total_steps=total_steps, hours=hours_each,
                  config=configs[0], series=series_id, launch=launch, kind=kind)
    _write(folder() / "series.json", {"id": series_id, "dataset": dataset, "device": device,
                                       "total_steps": total_steps, "hours_each": hours_each,
                                       "queue": configs[1:], "runs": [first["id"]], "created": _now(),
                                       "launch": launch, "kind": kind})
    return {"series": series_id, "first": first["id"], "queue": [c.get("label") or c.get("size") for c in configs[1:]]}


def series():
    plan = _read(folder() / "series.json")
    if plan:
        # Older plans queued size letters; newer ones queue whole configurations.
        plan["queue"] = [q if isinstance(q, str) else (q.get("label") or q.get("size")) for q in plan.get("queue", [])]
    return plan


def _continue_series(run_id):
    """Called when a series run finishes: starts the next variant, if any is left."""
    plan = _read(folder() / "series.json")
    if not plan or run_id not in plan.get("runs", []) or not plan.get("queue"):
        return None
    item = plan["queue"].pop(0)
    config = config_for(item) if isinstance(item, str) else item
    try:
        nxt = start("long", dataset=plan["dataset"], device=plan["device"], total_steps=plan["total_steps"],
                    hours=plan["hours_each"], config=config, series=plan["id"], launch=plan.get("launch", True),
                    kind=plan.get("kind"))
    except ValueError as error:
        plan["error"] = str(error)
        _write(folder() / "series.json", plan)
        return None
    plan["runs"].append(nxt["id"])
    _write(folder() / "series.json", plan)
    return nxt["id"]


def _describe(config):
    arch = config.get("arch") or {}
    parts = ["%s слоёв × %s" % (config["layers"], config["width"])]
    if arch.get("loops", 1) > 1:
        parts.append("думает ×%d" % arch["loops"])
    if arch.get("experts"):
        parts.append("%d экспертов" % arch["experts"])
    if arch.get("memory"):
        parts.append("память %d" % arch["memory"])
    for key, value in (("mixer", MIXER_NAMES.get(arch.get("mixer"))), ("dendrites", arch.get("dendrites") and "дендриты ×%d" % arch["dendrites"]),
                       ("hopfield", arch.get("hopfield") and "Хопфилд %d" % arch["hopfield"]), ("fast", arch.get("fast") and "быстрые веса"),
                       ("epigenetic", arch.get("epigenetic") and "эпигенетика"),
                       ("guest", arch.get("guest") and "специалист внутри"),
                       ("ff", (config.get("rule") or {}).get("ff") and "разгон Forward-Forward")):
        if value:
            parts.append(value)
    return ", ".join(parts)


MIXER_NAMES = {"ssm": "Mamba вместо внимания", "liquid": "жидкие нейроны", "hybrid": "Mamba + внимание"}


def mutate(parent, rng):
    """One variant of a configuration: a random change of depth, width, loops, experts, memory,
    the token mixer (attention, Mamba, liquid, both), dendrites, Hopfield memory, fast weights or
    a Forward-Forward warm-up."""
    child = json.loads(json.dumps(parent))
    arch = dict(child.get("arch") or {"lab": True}, lab=True)
    gene = rng.choice(["layers", "width", "loops", "experts", "memory", "merges", "mixer", "dendrites", "hopfield", "fast", "ff",
                       "epigenetic"])
    if gene == "layers":
        child["layers"] = max(2, min(12, child["layers"] + rng.choice([-2, 2])))
    elif gene == "width":
        child["width"] = max(128, min(640, child["width"] + rng.choice([-64, 64])))
        child["heads"] = 8 if child["width"] % 8 == 0 else 4
    elif gene == "loops":
        arch["loops"] = rng.choice([v for v in (1, 2, 3) if v != arch.get("loops", 1)])
    elif gene == "experts":
        arch["experts"] = 0 if arch.get("experts") else rng.choice([4, 6])
        arch.pop("dendrites", None)
    elif gene == "memory":
        arch["memory"] = 0 if arch.get("memory") else rng.choice([128, 256])
    elif gene == "mixer":
        arch["mixer"] = rng.choice([m for m in ("attn", "ssm", "liquid", "hybrid") if m != arch.get("mixer", "attn")])
    elif gene == "dendrites":
        arch["dendrites"] = 0 if arch.get("dendrites") else 4
        arch.pop("experts", None)
    elif gene == "hopfield":
        arch["hopfield"] = 0 if arch.get("hopfield") else rng.choice([128, 256])
    elif gene == "fast":
        arch["fast"] = not arch.get("fast", False)
    elif gene == "epigenetic":
        arch["epigenetic"] = not arch.get("epigenetic", False)
    elif gene == "ff":
        rule = dict(child.get("rule") or {})
        if rule.pop("ff", 0) == 0:
            rule["ff"] = FF_STEPS
        child["rule"] = rule or None
    else:
        child["max_merges"] = rng.choice([v for v in (512, 1024, 2048) if v != child.get("max_merges")])
    from backend.neural_language_bpe_v2 import check_arch
    child["arch"] = check_arch(arch)
    child["label"] = _describe(child)
    return child


def start_evolution(dataset, population=4, *, device="cuda", total_steps=100000, hours_each=1.0, launch=True, seed=None):
    """Evolution: the current best configuration and its mutants train on the same data.

    The exam picks the winner; the next round mutates the winner. Nothing is activated."""
    import random
    if type(population) is not int or not 3 <= population <= 8:
        raise ValueError("В поколении от 3 до 8 вариантов")
    rng = random.Random(seed)
    finished = [r for r in runs() if r["mode"] == "long" and r.get("exam_per_char") is not None]
    from backend import archive
    elite = archive.pick_parent(rng)
    if elite:
        # Open-ended: the parent is any elite of the archive, not always the single best.
        best = {"id": elite}
    elif finished:
        best = min(finished, key=lambda r: r["exam_per_char"])
    else:
        best = None
    if best:
        parent = dict(_read(_run_dir(best["id"]) / "run.json")["config"], from_run=best["id"])
    else:
        parent = config_for("s")
    parent["label"] = "родитель: " + _describe(parent)
    children, seen = [parent], {json.dumps({k: v for k, v in parent.items() if k != "label"}, sort_keys=True)}
    for _ in range(population * 10):
        if len(children) >= population:
            break
        # Several genes at once when evolution is stuck (backend/mutation.py).
        from backend import mutation, tabu
        child = mutation.apply(mutate, parent, rng)
        child["changes"] = tabu.diff({k: v for k, v in parent.items() if k != "changes"},
                                     {k: v for k, v in child.items() if k != "changes"})
        if not child["changes"] or tabu.banned("архитектура", child["changes"]):
            continue  # a change that already failed twice waits its turn (backend/tabu.py)
        child["label"] = _describe(child)
        key = json.dumps({k: v for k, v in child.items() if k != "label"}, sort_keys=True)
        if key not in seen:
            seen.add(key)
            children.append(child)
    return start_series(dataset, configs=children, device=device, total_steps=total_steps,
                        hours_each=hours_each, launch=launch, kind="evolution")


def merge(run_a, run_b, launch=True):
    """Crossbreeding by averaging weights. Only versions with the same network and the same word
    pieces can be averaged; the merged version takes its own exam and is kept only if you want."""
    import torch
    a, b = _summary(_run_dir(run_a)), _summary(_run_dir(run_b))
    if run_a == run_b or a["mode"] != "long" or b["mode"] != "long" or not a["has_best"] or not b["has_best"]:
        raise ValueError("Выберите две разные обученные версии диалогов")
    sa = torch.load(_run_dir(run_a) / "language-longrun.pt.best.pt", map_location="cpu", weights_only=True)
    sb = torch.load(_run_dir(run_b) / "language-longrun.pt.best.pt", map_location="cpu", weights_only=True)
    if (sa["config"][:4] != sb["config"][:4] or sa.get("arch", {}) != sb.get("arch", {}) or
            sa["tokenizer"]["sha256"] != sb["tokenizer"]["sha256"]):
        raise ValueError("Скрестить можно только версии с одинаковым устройством и словарём "
                         "(например, выросшие из одной основы)")
    weights = {k: (v + sb["weights"][k]) / 2 if v.is_floating_point() else v for k, v in sa["weights"].items()}
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-long"
    path = folder() / "runs" / run_id
    if path.exists():
        raise ValueError("Подождите секунду и запустите снова")
    path.mkdir(parents=True)
    info = _read(_run_dir(run_a) / "run.json")
    payload = dict(sa, weights=weights, optimizer=None)
    payload.pop("optimizer")
    torch.save(payload, path / "language-longrun.pt.best.pt")
    _write(path / "run.json", dict(info, id=run_id, created=_now(), kind="merge", series=None,
                                   merged=[run_a, run_b]))
    if info.get("internal"):
        shutil.copyfile(_run_dir(run_a) / "dataset.json", path / "dataset.json")
    _write(path / "progress.json", {"state": "finished", "steps": sa.get("best_step", 0), "best_step": sa.get("best_step", 0),
                                    "history": [], "t": time.time(),
                                    "parameters": sum(v.numel() for v in weights.values())})

    if launch:
        _spawn([sys.executable, str(CLI), "exam-worker", run_id], path / "worker.log")
    return _summary(path)


def exam_worker(run_id):
    """Exams for a version made without training (crossbreeding); takes minutes on a laptop."""
    path = _run_dir(run_id)
    info = _read(path / "run.json")
    progress = _read(path / "progress.json", {}) or {}

    def save(**fields):
        progress.update(fields)
        _write(path / "progress.json", progress)
    try:
        data = _read(path / "dataset.json") if info.get("internal") else _load_records(info["dataset"])
        _exam(path, _prepare(data), False, save)
    except Exception as error:  # noqa: BLE001 - the page shows why the exam failed
        save(error=str(error)[:200])
        return 1
    _to_archive(run_id)
    return 0


def _to_archive(run_id):
    """A tournament against the parent and a place in the archive; never stops the run's end."""
    try:
        from backend import archive
        return archive.update(run_id)
    except Exception as error:  # noqa: BLE001
        print(repr(error), file=sys.stderr)
        return None


def introspect_worker(run_id):
    """Looks inside an older version on demand; new versions are looked into after their exam."""
    from backend import introspect
    from backend.neural_language_benchmark import load_candidate
    path = _run_dir(run_id)
    info = _read(path / "run.json")
    progress = _read(path / "progress.json", {}) or {}
    try:
        records = _read(path / "dataset.json") if info.get("internal") else _load_records(info["dataset"])
        progress["introspection"] = introspect.inspect(load_candidate(path / "language-longrun.pt.best.pt"),
                                                       _prepare(records)["test"])
    except Exception as error:  # noqa: BLE001 - the page shows why
        progress["introspection"] = {"error": str(error)[:200]}
    _write(path / "progress.json", progress)
    return 0


def compress(run_id):
    """4-bit copy of a version for answering; reports the size and what the exam says it cost."""
    from backend.neural_language_longrun import score_checkpoint
    from backend.quantize import load_quantized, quantize
    item = _summary(_run_dir(run_id))
    if item["mode"] != "long" or not item["has_best"]:
        raise ValueError("Сжать можно обученную версию диалогов")
    best = _run_dir(run_id) / "language-longrun.pt.best.pt"
    small = _run_dir(run_id) / "language-longrun.pt.best.q4.pt"
    sizes = quantize(best, small)
    info = _read(_run_dir(run_id) / "run.json")
    records = _read(_run_dir(run_id) / "dataset.json") if info.get("internal") else _load_records(info["dataset"])
    test = _prepare(records)["test"]
    after = score_checkpoint(small, test, loaded=load_quantized(small))["per_char"]
    result = {"bytes": sizes["bytes"], "original_bytes": best.stat().st_size, "exam_before": item["exam_per_char"],
              "exam_after": round(after, 4)}
    progress = _read(_run_dir(run_id) / "progress.json", {}) or {}
    progress["compressed"] = result
    _write(_run_dir(run_id) / "progress.json", progress)
    # The chat uses the compressed copy of the active version when asked to; copy it next to it.
    current = active()
    if current and current.get("run") == run_id:
        target = folder() / current["checkpoint"]
        shutil.copyfile(small, target.with_name(target.name[:-3] + ".q4.pt"))
    return result


def protected_prompts():
    """Prompts of every earlier exam: internal datasets never train on them."""
    banned = set()
    for item in runs():
        if item["mode"] != "long" or not item.get("dataset"):
            continue
        info = _read(_run_dir(item["id"]) / "run.json", {}) or {}
        try:
            records = _read(_run_dir(item["id"]) / "dataset.json") if info.get("internal") else _load_records(item["dataset"])
            banned.update(p.casefold().strip() for p, _ in _prepare(records)["test"])
        except (ValueError, TypeError):
            continue
    return banned


def stop_all():
    """Emergency stop: asks every running training to stop at the next chunk."""
    plan = series()
    if plan and plan.get("queue"):
        plan["queue"], plan["error"] = [], "Остановлено кнопкой «Стоп всё»"
        _write(folder() / "series.json", plan)
    from backend import plans
    plans.stop()
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
    try:
        from backend import logic
        save(logic=logic.exam(loaded))
    except (ValueError, ImportError):
        pass
    try:
        from backend import simworld
        save(sim=simworld.exam(loaded))
    except (ValueError, ImportError):
        pass
    try:
        from backend import introspect
        save(introspection=introspect.inspect(loaded, data["test"]))
    except (ValueError, ImportError, RuntimeError):
        pass


def _outside_schedule():
    try:
        from backend import schedule
        plan = schedule.settings()
        return plan["enforce"] and not schedule.allowed(grid=plan["grid"])
    except Exception:  # noqa: BLE001 - a broken schedule never stops a lesson
        return False


def resume_scheduled():
    """At the start of study hours: lessons the schedule paused continue where they stopped."""
    resumed = []
    for item in runs():
        progress = _read(_run_dir(item["id"]) / "progress.json", {}) or {}
        if item["state"] == "paused" and progress.get("paused_by") == "schedule" and item["resumable"] and not _active_job():
            control(item["id"], "resume")
            resumed.append(item["id"])
    return resumed


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
            records = (pilot_records() if run_info["mode"] == "pilot" else
                       _read(path / "dataset.json") if run_info.get("internal") else _load_records(run_info["dataset"]))
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
        if run_info.get("init"):
            init_from = folder() / run_info["init"]
        save(state="running", gpu_name=gpu, error=None)
        while True:
            request = (_read(path / "control.json", {}) or {}).get("request")
            if request in ("pause", "stop"):
                (path / "control.json").unlink(missing_ok=True)
                _exam(path, data, lm, save)
                save(state="paused" if request == "pause" and run_info["mode"] != "pilot" else "stopped")
                if request == "stop":
                    from backend import plans
                    plans.on_stopped(run_id, "Урок остановлен")
                return 0
            if run_info.get("scheduled") and _outside_schedule():
                _exam(path, data, lm, save)
                save(state="paused", paused_by="schedule")
                return 0
            if progress.get("steps", 0) >= run_info["total_steps"] or elapsed >= run_info["time_limit"]:
                _exam(path, data, lm, save)
                save(state="finished")
                if not lm:
                    _to_archive(run_id)
                    progress.update(_read(path / "progress.json", {}) or {})
                if run_info.get("kind") in ("quick", "sleep"):
                    from backend import continual
                    save(verdict=continual.judge(run_id))
                _continue_series(run_id)
                try:
                    from backend import plans
                    plans.on_finished(run_id)
                except Exception as error:  # noqa: BLE001 - the plan records its own failure
                    print(repr(error), file=sys.stderr)
                return 0
            chunk = max(1.0, min(CHUNK_SECONDS, run_info["time_limit"] - elapsed))
            began = time.monotonic()
            status = run(data["train"], data["validation"], path / "language-longrun.pt",
                         total_steps=run_info["total_steps"], checkpoint_every=cfg["checkpoint_every"],
                         width=cfg["width"], heads=cfg["heads"], layers=cfg["layers"],
                         context=cfg["context"], max_merges=cfg["max_merges"], seed=cfg["seed"],
                         max_run_seconds=chunk, device=device, batch_size=cfg.get("batch_size", 1),
                         accumulate=cfg.get("accumulate", 1), precision=precision,
                         objective="lm" if lm else "dialogue", init_from=init_from, arch=cfg.get("arch"),
                         lr=float(cfg.get("lr", 0.0003)), rule=cfg.get("rule"))
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
            if status.get("ff_report"):
                save(forward_forward=status["ff_report"])
    except Exception as error:  # the page must see why the worker ended
        message = str(error) if re.search("[а-яА-Я]", str(error)) else "Обучение остановилось с ошибкой: %s" % type(error).__name__
        if "out of memory" in str(error).lower():
            message = "Не хватило памяти видеокарты"
        save(state="failed", error=message[:200])
        print(repr(error), file=sys.stderr)
        try:
            from backend import plans
            plans.on_stopped(run_id, message[:200])
        except Exception:  # noqa: BLE001
            pass
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


def activate(run_id, by="user"):
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
            "by": by}
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
    from backend.brain import generate
    return generate(model, state, prompt, max_tokens)["text"]


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
