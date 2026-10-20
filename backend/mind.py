"""Ways of thinking taken from living brains, each checked by code and by exams.

Two hemispheres: the active version and a partner (the strongest other version in the archive)
answer the same fresh tasks with checkable answers. Where one is right and the other wrong, the
right one's own words become a lesson for the active version; where both fail, the program's
solution does. A trust table counts, per kind of task, which side was right: it shows who is
the better teacher of what.

Gene exchange (ecosystem): versions of the same line (same build and word pieces) trade whole
blocks of neurons. A block of the donor replaces the active one's block only if the exam sample
gets better with it; the result is a new version that takes every exam as usual.

Language of thought: before answering she may write hidden steps between ⟦ and ⟧. The chat
shows only what comes after them. Her own thoughts are kept as lessons only when the answer they
led to is right, so she learns ways of thinking that work, in her own words.
"""
import random
import re
import time
from datetime import datetime, timezone

OPEN, CLOSE = "⟦", "⟧"
THOUGHT = re.compile(r"⟦[^⟧]{0,2000}⟧\s*")


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---- language of thought --------------------------------------------------------

def strip_thoughts(text):
    """What the chat shows: everything outside ⟦…⟧; an unclosed thought is hidden to the end."""
    visible = THOUGHT.sub("", text or "")
    if OPEN in visible:
        visible = visible[:visible.index(OPEN)]
    return visible.strip()


def thoughts_of(text):
    return [m.strip("⟦⟧ ") for m in re.findall(r"⟦[^⟧]{0,2000}⟧", text or "")]


def as_thought(solution):
    """«Шаг 1: … Ответ: X.» → «⟦… ; …⟧ Ответ: X.»"""
    match = re.search(r"Ответ:\s*[^\n]+$", solution.strip())
    if not match:
        return solution
    steps = solution[:match.start()].strip()
    steps = re.sub(r"Шаг \d+:\s*", "", steps).replace(". ", "; ").strip(" .")
    return "%s%s%s %s" % (OPEN, steps, CLOSE, match.group(0).strip())


def thought_lessons(count=120, seed=0):
    """Code-written solutions with the steps as hidden thoughts; never exam questions."""
    from backend import logic, simworld
    rng = random.Random(seed)
    pairs = [(q, as_thought(a)) for q, a in logic.lessons(3, count // 6 + 1, seed=seed + 17)]
    pairs += [(t["q"], as_thought(t["solution"])) for t in simworld.fresh(rng, count // 2, level=2)]
    rng.shuffle(pairs)
    return pairs[:count]


def own_thoughts(loaded, count=40, seed=0):
    """She thinks in her own words; only thoughts that led to a right answer are kept."""
    from backend import logic, simworld
    from backend.brain import generate
    model, state = loaded
    rng = random.Random(seed)
    kept = []
    for t in simworld.fresh(rng, count, level=1):
        text = generate(model, state, t["q"], 128, temperature=0.7)["text"]
        if OPEN in text and logic.correct(strip_thoughts(text) or text, t["answer"]):
            kept.append((t["q"], text.strip()))
    return kept


# ---- two hemispheres --------------------------------------------------------------

def partner(exclude):
    """The strongest other version: an archive elite, else the newest finished dialogue version."""
    from backend import archive
    from backend import training_center as tc
    cells = sorted(archive.load()["cells"].values(), key=lambda c: -c["fitness"])
    for c in cells:
        if c["run"] != exclude and archive._exists(c["run"]):
            return c["run"]
    for item in tc.runs():
        if item["id"] != exclude and item["mode"] == "long" and item["has_best"] and item["state"] == "finished":
            return item["id"]
    return None


def _tasks(rng, count):
    from backend import dreams, logic, simworld
    banned = logic._exam_questions() | simworld._banned()
    out = [("sim:" + t["env"], t["q"], t["answer"], t["solution"]) for t in simworld.fresh(rng, count // 2, level=2)]
    while len(out) < count:
        t = logic.task(rng, rng.choice((1, 2, 3)))
        if t["q"] not in banned:
            out.append(("logic", t["q"], t["answer"], t["solution"]))
    for _ in range(count // 4):
        q, solution, answer = rng.choice(dreams.INVERSE)(rng)
        out.append(("inverse", q, answer, solution))
    return out


def hemisphere_set(left_checkpoint, right_checkpoint, count=90, seed=0):
    """Lessons from the disagreement of two versions, and the trust table."""
    from backend import brain, logic, plans
    left, right = brain.load(left_checkpoint), brain.load(right_checkpoint)
    rng = random.Random(seed)
    lessons, report = [], {"asked": 0, "left": 0, "right": 0, "both": 0, "none": 0, "taught_by_right": 0}
    trust = {}
    for kind, q, answer, solution in _tasks(rng, count):
        report["asked"] += 1
        a = brain.generate(*left, q, 96)["text"]
        b = brain.generate(*right, q, 96)["text"]
        ok_a, ok_b = logic.correct(a, answer), logic.correct(b, answer)
        row = trust.setdefault(kind.split(":")[0], {"left": 0, "right": 0, "asked": 0})
        row["asked"] += 1
        row["left"] += ok_a
        row["right"] += ok_b
        if ok_a and ok_b:
            report["both"] += 1
            lessons.append((q, a.strip()))
        elif ok_b:
            report["right"] += 1
            report["taught_by_right"] += 1
            lessons.append((q, b.strip()))  # the other half's own words
        elif ok_a:
            report["left"] += 1
            lessons.append((q, a.strip()))
        else:
            report["none"] += 1
            lessons.append((q, solution))
    records = plans._synthetic(lessons, "hemispheres")
    keys = {r["prompt"].casefold().strip() for r in records}
    records += [r for r in plans._experience(len(records), seed) if r["prompt"].casefold().strip() not in keys]
    _save_trust(trust)
    return records, report


def _save_trust(trust):
    from backend import training_center as tc
    saved = tc._read(tc.folder() / "hemispheres.json", {}) or {}
    total = saved.get("trust", {})
    for kind, row in trust.items():
        t = total.setdefault(kind, {"left": 0, "right": 0, "asked": 0})
        for k in t:
            t[k] += row[k]
    tc._write(tc.folder() / "hemispheres.json", {"trust": total, "at": _now()})


def trust():
    from backend import training_center as tc
    return (tc._read(tc.folder() / "hemispheres.json", {}) or {}).get("trust", {})


# ---- gene exchange ----------------------------------------------------------------

def donors(base_run):
    """Versions that can trade blocks with base: the same build, size and word pieces."""
    import torch
    from backend import training_center as tc
    base = torch.load(tc._run_dir(base_run) / "language-longrun.pt.best.pt", map_location="cpu", weights_only=True)
    out = []
    for item in tc.runs():
        if item["id"] == base_run or item["mode"] != "long" or not item["has_best"]:
            continue
        other = torch.load(tc._run_dir(item["id"]) / "language-longrun.pt.best.pt", map_location="cpu", weights_only=True)
        if (other["config"][:4] == base["config"][:4] and other.get("arch", {}) == base.get("arch", {}) and
                other["tokenizer"]["sha256"] == base["tokenizer"]["sha256"]):
            out.append(item["id"])
        if len(out) >= 6:
            break
    return out


def exchange(base_run, donor_runs, examples):
    """Greedy horizontal gene transfer, block by block, kept only where the exam sample improves.

    Returns the new run id (or None when no block helped) and what was taken from whom."""
    import torch
    from backend import training_center as tc
    from backend.introspect import _loss
    from backend.neural_language_bpe_v2 import make_model
    base = torch.load(tc._run_dir(base_run) / "language-longrun.pt.best.pt", map_location="cpu", weights_only=True)
    width, heads, layers, context, _, _ = base["config"]
    model = make_model(torch, vocab_size=base["vocab_size"], width=width, heads=heads, layers=layers, context=context,
                       arch=base.get("arch") or {})
    model.load_state_dict(base["weights"], strict=True)
    model.eval()
    state = {"tokenizer": base["tokenizer"], "config": base["config"]}
    examples = list(examples)[:48]
    best = _loss(model, state, examples)
    start = best
    taken = []
    for donor in donor_runs:
        other = torch.load(tc._run_dir(donor) / "language-longrun.pt.best.pt", map_location="cpu", weights_only=True)["weights"]
        for k in range(layers):
            prefix = "blocks.%d." % k
            saved = {n: v.clone() for n, v in model.state_dict().items() if n.startswith(prefix)}
            model.load_state_dict({**model.state_dict(), **{n: other[n] for n in saved}}, strict=True)
            score = _loss(model, state, examples)
            if score < best - 1e-4:
                best = score
                taken.append({"block": k + 1, "from": donor, "gain": round(start - score, 4)})
            else:
                model.load_state_dict({**model.state_dict(), **saved}, strict=True)
    if not taken:
        return None, {"start": round(start, 4), "taken": []}
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-long"
    path = tc.folder() / "runs" / run_id
    while path.exists():
        time.sleep(1.1)
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-long"
        path = tc.folder() / "runs" / run_id
    path.mkdir(parents=True)
    payload = dict(base, weights=model.state_dict(), step=base.get("best_step", 0))
    payload.pop("optimizer", None)
    torch.save(payload, path / "language-longrun.pt.best.pt")
    info = tc._read(tc._run_dir(base_run) / "run.json")
    tc._write(path / "run.json", dict(info, id=run_id, created=_now(), kind="ecosystem", series=None, parent=base_run,
                                      merged=[base_run] + sorted({t["from"] for t in taken}),
                                      dataset="(обмен генами: %d блоков)" % len(taken)))
    if info.get("internal"):
        import shutil
        shutil.copyfile(tc._run_dir(base_run) / "dataset.json", path / "dataset.json")
    tc._write(path / "progress.json", {"state": "finished", "steps": 0, "best_step": 0, "history": [], "t": time.time(),
                                       "parameters": sum(v.numel() for v in model.state_dict().values()),
                                       "exchange": {"start": round(start, 4), "end": round(best, 4), "taken": taken}})
    return run_id, {"start": round(start, 4), "end": round(best, 4), "taken": taken}
