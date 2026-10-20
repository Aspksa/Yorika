"""Breeding by an evolved recipe: chosen parents, per-layer weights, skills that take turns.

Three ideas from model-merging research, joined into one mechanism:

- Evolutionary model merge (Sakana AI, 2024). Instead of averaging two versions, a recipe is
  evolved: for every parent and every layer a weight, and how many of each parent's changes are
  randomly dropped and the rest rescaled (DARE) before the parents agree on a sign (TIES). Recipes
  are scored by measurements only; the best one becomes a version that takes the usual exams.
- Model kinship (2024). Parents that changed the same way add nothing to each other. The kinship
  of two parents is the cosine of their changes from the active version; near-clones are not
  bred together, and a version that barely differs from the active one is not a parent at all.
- CycleQD (Sakana AI, 2025). Each skill (logic, honesty, conversation) takes its turn as the
  quality to improve, while the other two describe where a child sits. Every skill keeps its own
  archive with the best child of every niche, so breeding does not trade one skill for another.

The fitness used here is fast: the loss on each skill's checked answers with teacher forcing (one
forward pass per lesson, no generation), on lessons that are never exam questions. It only ranks
recipes; the real exams, the tournament and the comparison with the active version still decide
what happens to the version that comes out. Nothing is activated here.
"""
import math
import random
import time

SKILLS = ("logic", "honesty", "dialogue")
SKILL_NAMES = {"logic": "логика", "honesty": "честность", "dialogue": "разговор"}
KIN_MAX = 0.98          # cosine of changes above which two parents count as near-clones
MIN_CHANGE = 1e-4       # a parent must differ from the active version at least this much (relative)
MAX_PARENTS = 3
BIG = 20_000_000        # above this many parameters only two parents fit in memory comfortably
CANDIDATES = 8          # versions loaded to choose parents from
W_LOW, W_HIGH = -0.5, 1.5
TOLERANCE = 0.01        # a skill may lose this much loss per token in exchange for others
BINS = (-0.05, 0.0, 0.05)
ROWS = 24


# ---- parents and kinship ----------------------------------------------------------

def _load(path):
    import torch
    return torch.load(path, map_location="cpu", weights_only=True)


def compatible(a, b):
    return (a["config"][:4] == b["config"][:4] and (a.get("arch") or {}) == (b.get("arch") or {})
            and a["tokenizer"]["sha256"] == b["tokenizer"]["sha256"])


def _float_keys(weights):
    return [k for k, v in weights.items() if v.is_floating_point()]


def change(weights, base):
    """How far a version moved from base: norm of the difference over the norm of base."""
    moved = total = 0.0
    for key in _float_keys(base):
        moved += float((weights[key].float() - base[key].float()).pow(2).sum())
        total += float(base[key].float().pow(2).sum())
    return math.sqrt(moved / total) if total else 0.0


def kinship(a, b, base):
    """Cosine of the two versions' changes from base: 1 means they learned the same thing."""
    dot = na = nb = 0.0
    for key in _float_keys(base):
        da, db = a[key].float() - base[key].float(), b[key].float() - base[key].float()
        dot += float((da * db).sum())
        na += float(da.pow(2).sum())
        nb += float(db.pow(2).sum())
    if not na or not nb:
        return None
    return round(dot / math.sqrt(na * nb), 4)


def lineage(run_id, limit=40):
    """The version itself, then where it came from: parent, the point it continued from, the first
    of the merged ones."""
    from backend import training_center as tc
    chain, seen = [], set()
    while run_id and run_id not in seen and len(chain) < limit:
        seen.add(run_id)
        chain.append(run_id)
        try:
            info = tc._read(tc._run_dir(run_id) / "run.json", {}) or {}
        except ValueError:
            break
        init = info.get("init") or ""
        parts = init.replace("\\", "/").split("/")
        run_id = info.get("parent") or (parts[1] if len(parts) > 2 and parts[0] == "runs" else None) \
            or (info.get("merged") or [None])[0] or info.get("grown_from")
    return chain


def pair_kinship(run_a, run_b, sa, sb):
    """Kinship of two versions from their nearest common ancestor with the same network; None when
    they have none (two versions trained from scratch are not related)."""
    from backend import training_center as tc
    theirs = set(lineage(run_b))
    for ancestor in lineage(run_a)[1:]:
        if ancestor not in theirs or ancestor == run_b:
            continue
        try:
            state = _load(tc._run_dir(ancestor) / "language-longrun.pt.best.pt")
        except (ValueError, OSError, RuntimeError):
            continue
        if compatible(state, sa):
            return kinship(sa["weights"], sb["weights"], state["weights"])
    return None


def _cheap_pool(anchor_run):
    """Versions that could be parents, judged from their records only (no weights loaded)."""
    from backend import archive
    from backend import training_center as tc
    try:
        mine = tc._read(tc._run_dir(anchor_run) / "run.json")["config"]
    except (ValueError, TypeError, KeyError):
        return []
    found = []
    for item in tc.runs():
        if item["id"] == anchor_run or item["mode"] != "long" or not item["has_best"] or archive.fitness(item) is None:
            continue
        try:
            cfg = tc._read(tc._run_dir(item["id"]) / "run.json")["config"]
        except (ValueError, TypeError, KeyError):
            continue
        if all(cfg.get(k) == mine.get(k) for k in ("width", "heads", "layers", "context", "max_merges")) and \
                (cfg.get("arch") or {}) == (mine.get("arch") or {}):
            found.append(item)
    return sorted(found, key=lambda i: -archive.fitness(i))


def ready(anchor_run):
    """True when at least one other version with the same network could be a parent."""
    return bool(_cheap_pool(anchor_run))


def choose_parents(anchor_run, anchor_state):
    """The fittest versions with the same network that differ from the active one and from each
    other: healthy kinship, not near-clones."""
    from backend import archive
    from backend import training_center as tc
    base = anchor_state["weights"]
    limit = 2 if sum(v.numel() for v in base.values()) > BIG else MAX_PARENTS
    chosen, skipped = [], []
    for item in _cheap_pool(anchor_run)[:CANDIDATES]:
        try:
            state = _load(tc._run_dir(item["id"]) / "language-longrun.pt.best.pt")
        except (ValueError, OSError, RuntimeError):
            continue
        if not compatible(state, anchor_state):
            continue
        moved = change(state["weights"], base)
        if moved < MIN_CHANGE:
            skipped.append({"run": item["id"], "why": "почти не отличается от активной"})
            continue
        kin = [kinship(state["weights"], c["weights"], base) for c in chosen]
        if any(k is not None and k > KIN_MAX for k in kin):
            skipped.append({"run": item["id"], "why": "почти клон уже выбранного родителя"})
            continue
        chosen.append({"run": item["id"], "weights": state["weights"], "fitness": archive.fitness(item),
                       "change": round(moved, 5), "kin": kin})
        if len(chosen) >= limit:
            break
    return chosen, skipped


# ---- the recipe (genome) and the child it makes ------------------------------------

def groups(weights):
    """Layer groups: «in» (word pieces and positions), every block, «out» (the rest)."""
    blocks = sorted({int(k.split(".")[1]) for k in weights if k.startswith("blocks.")})
    return ["in"] + ["block %d" % b for b in blocks] + ["out"]


def group_of(key):
    if key.startswith(("embedding", "position")):
        return "in"
    if key.startswith("blocks."):
        return "block %d" % int(key.split(".")[1])
    return "out"


def random_genome(rng, parents, n_groups, plain=False):
    if plain:
        w = [[1.0 / parents] * n_groups for _ in range(parents)]
        return {"w": w, "density": 1.0, "seed": rng.randrange(10 ** 6)}
    return {"w": [[round(rng.uniform(0.2, 1.0), 3) for _ in range(n_groups)] for _ in range(parents)],
            "density": round(rng.uniform(0.3, 1.0), 3), "seed": rng.randrange(10 ** 6)}


def mutate(genome, rng, sigma=0.15):
    w = [[round(min(W_HIGH, max(W_LOW, x + rng.gauss(0, sigma))), 3) for x in row] for row in genome["w"]]
    density = round(min(1.0, max(0.2, genome["density"] + rng.gauss(0, 0.1))), 3)
    return {"w": w, "density": density, "seed": rng.randrange(10 ** 6)}


def crossover(a, b, rng):
    w = [[x if rng.random() < 0.5 else y for x, y in zip(ra, rb)] for ra, rb in zip(a["w"], b["w"])]
    return {"w": w, "density": a["density"] if rng.random() < 0.5 else b["density"], "seed": rng.randrange(10 ** 6)}


def materialize(base, parents, genome, names):
    """DARE (drop changes at random, rescale the rest), weights per parent and layer, then TIES:
    the sign most of the weighted change agrees on, and only changes with that sign are added."""
    import torch
    generator = torch.Generator().manual_seed(genome["seed"])
    density = genome["density"]
    index = {name: k for k, name in enumerate(names)}
    out = {}
    for key, value in base.items():
        if not value.is_floating_point():
            out[key] = value
            continue
        g = index[group_of(key)]
        scaled = []
        for p, parent in enumerate(parents):
            tau = parent[key].float() - value.float()
            if density < 1.0:
                keep = torch.rand(tau.shape, generator=generator) < density
                tau = tau * keep / density
            scaled.append(tau * genome["w"][p][g])
        stack = torch.stack(scaled)
        sign = torch.sign(stack.sum(0))
        agree = (torch.sign(stack) == sign) & (stack != 0)
        out[key] = (value.float() + (stack * agree).sum(0)).to(value.dtype)
    return out


# ---- fast skill fitness ----------------------------------------------------------------

def skill_lessons(anchor_records, seed=0):
    """Checked answers per skill that no exam asks: fresh logic tasks with their solutions, the
    honesty lessons, and the active version's validation split of conversations."""
    from backend import curiosity, honesty, logic
    rng, banned = random.Random(seed), logic._exam_questions()
    level = min(5, max(1, curiosity.logic_frontier() + 1))
    tasks, seen = [], set()
    for _ in range(ROWS * 20):
        t = logic.task(rng, rng.randint(1, level))
        if t["q"] not in banned and t["q"] not in seen:
            seen.add(t["q"])
            tasks.append((t["q"], t["solution"]))
        if len(tasks) >= ROWS:
            break
    dialogue = []
    if anchor_records:
        from backend import training_center as tc
        try:
            dialogue = list(tc._prepare(anchor_records)["validation"])[:ROWS]
        except ValueError:
            dialogue = []
    return {"logic": tasks, "honesty": honesty.lessons()[:ROWS], "dialogue": dialogue}


def _rows(state, pairs):
    from backend import es
    return es._rows(state, [{"prompt": q, "answer": a} for q, a in pairs])


def losses(torch, model, rows):
    from backend import es
    return {skill: round(es._loss(torch, model, r), 5) for skill, r in rows.items() if r}


def _cell(gains, quality):
    return tuple(sum(gains[o] >= b for b in BINS) for o in sorted(gains) if o != quality)


def breed(anchor_checkpoint, anchor_run, *, seconds=600, seed=0, should_stop=None, records=None, previous=None):
    """Evolves a recipe within `seconds`. Returns (weights or None, report)."""
    import torch
    from backend.neural_language_benchmark import load_candidate
    from backend import training_center as tc
    start = time.monotonic()
    model, anchor_state = load_candidate(tc.folder() / anchor_checkpoint)
    base = {k: v.detach().clone() for k, v in anchor_state["weights"].items()}
    parents, skipped = choose_parents(anchor_run, anchor_state)
    made = {"parents": [{k: p[k] for k in ("run", "fitness", "change", "kin")} for p in parents], "skipped": skipped,
            "generations": 0, "children": 0}
    if not parents:
        made["why"] = "нет версии с тем же устройством, которая отличается от активной и не клон"
        return None, made
    names = groups(base)
    rows = {s: _rows(anchor_state, pairs) for s, pairs in skill_lessons(records, seed).items()}
    rows = {s: r for s, r in rows.items() if len(r) >= 4}
    if len(rows) < 2:
        made["why"] = "мало проверенных уроков для оценки навыков"
        return None, made
    skills = [s for s in SKILLS if s in rows]
    model.eval()
    before = losses(torch, model, rows)
    weights = [p["weights"] for p in parents]
    rng = random.Random(seed)
    archives = {s: {} for s in skills}
    tried = []

    def evaluate(genome):
        model.load_state_dict(materialize(base, weights, genome, names))
        after = losses(torch, model, rows)
        gains = {s: round(before[s] - after[s], 5) for s in skills}
        tried.append((genome, gains))
        for quality in skills:
            cell = _cell(gains, quality)
            held = archives[quality].get(cell)
            if held is None or gains[quality] > held[1][quality]:
                archives[quality][cell] = (genome, gains)
        return gains

    first = [random_genome(rng, len(parents), len(names), plain=True)]
    if previous and previous.get("parents") == [p["run"] for p in parents] and previous.get("groups") == len(names):
        first.append({"w": previous["w"], "density": previous["density"], "seed": rng.randrange(10 ** 6)})
    first += [random_genome(rng, len(parents), len(names)) for _ in range(4)]
    for genome in first:
        if should_stop and should_stop():
            break
        evaluate(genome)
    generation = 0
    while time.monotonic() - start < seconds and not (should_stop and should_stop()) and generation < 400:
        quality = skills[generation % len(skills)]
        elites = [g for g, _ in archives[quality].values()] or [g for g, _ in tried]
        a, b = rng.choice(elites), rng.choice(elites)
        evaluate(mutate(crossover(a, b, rng), rng))
        generation += 1
    made.update(generations=generation, children=len(tried), before=before,
                cells={s: len(archives[s]) for s in skills}, seconds=round(time.monotonic() - start, 1))
    balanced = [(sum(g.values()), genome, g) for genome, g in tried if min(g.values()) >= -TOLERANCE and sum(g.values()) > 0]
    if not balanced:
        made["why"] = "ни один рецепт не улучшил навыки без заметной потери в другом"
        made["best_gains"] = max((g for _, g in tried), key=lambda g: sum(g.values()), default=None)
        return None, made
    _, genome, gains = max(balanced, key=lambda x: x[0])
    made["recipe"] = {"parents": [p["run"] for p in parents], "groups": len(names), "w": genome["w"],
                      "density": genome["density"]}
    made["gains"] = gains
    return materialize(base, weights, genome, names), made


# ---- memory --------------------------------------------------------------------------

def _path():
    from backend import training_center as tc
    return tc.folder() / "breeding.json"


def load():
    from backend import training_center as tc
    data = tc._read(_path(), {}) or {}
    return {"log": data.get("log") or [], "recipe": data.get("recipe")}


def remember(made, run_id, verdict=None):
    from backend import training_center as tc
    data = load()
    entry = {k: made.get(k) for k in ("parents", "skipped", "generations", "children", "cells", "gains", "why", "seconds")}
    data["log"] = (data["log"] + [dict(entry, run=run_id, verdict=verdict,
                                       at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))])[-20:]
    if made.get("recipe") and verdict in ("waiting", "activated"):
        data["recipe"] = made["recipe"]   # the next breeding starts from the recipe that worked
    tc._write(_path(), data)


def status():
    from backend import training_center as tc
    data = load()
    current = tc.active()
    return {"runs": len(data["log"]), "last": data["log"][-1] if data["log"] else None,
            "recipe": bool(data["recipe"]), "skills": SKILL_NAMES, "ready": bool(current and ready(current["run"]))}
