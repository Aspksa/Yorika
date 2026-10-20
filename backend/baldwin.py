"""The Baldwin effect: evolution of the starting point, judged by how fast it learns.

What evolves here is not a trained version but the weights a new version is born with. Every
generation several newborns of the active version's shape and word pieces take the same short
lesson on the same data: a plain random start (the control), the inherited start, and mutants
(another random seed, a different initial scale). The one with the best exam after the lesson
learned fastest. Its genes pass on, and its inherited start moves a step towards what it
learned (start + 0.3 × (learned − start), the Reptile rule): learning shapes what is inherited,
but the learned weights themselves are not copied, which is the Baldwin effect.

The control makes the result honest: the page shows whether the inherited start actually beats
a random one on the same lesson. It is measured on short lessons of one laptop.
"""
import random
from datetime import datetime, timezone

SCALES = (0.5, 0.75, 1.0, 1.25, 1.5)
STEP = 0.3
KEEP_GENERATIONS = 2


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dir():
    from backend import training_center as tc
    return tc.folder() / "baldwin"


def load():
    from backend import training_center as tc
    data = tc._read(_dir() / "baldwin.json", {}) or {}
    return {"best": data.get("best"), "generation": int(data.get("generation", 0)), "history": data.get("history", [])[-20:],
            "inherited": data.get("inherited")}


def _save(data):
    from backend import training_center as tc
    _dir().mkdir(parents=True, exist_ok=True)
    data["history"] = data["history"][-20:]
    tc._write(_dir() / "baldwin.json", data)


def mutate(genome, rng):
    child = dict(genome)
    if rng.random() < 0.5:
        child["scale"] = rng.choice([s for s in SCALES if s != genome.get("scale", 1.0)])
    else:
        child["seed"] = rng.randrange(1, 10 ** 6)
    return child


def describe(genome):
    if genome.get("inherit"):
        return "врождённая точка (поколение %d)" % genome.get("from_generation", 0)
    return "случайный старт · зерно %d · масштаб ×%g" % (genome["seed"], genome["scale"])


def candidates(count, seed=0):
    """The control (plain random start), the inherited start if there is one, and mutants."""
    from backend import mutation
    rng = random.Random(seed)
    data = load()
    best = data["best"] or {"seed": 1, "scale": 1.0}
    out = [{"seed": rng.randrange(1, 10 ** 6), "scale": 1.0, "control": True}]
    if data["inherited"]:
        out.append({"inherit": True, "seed": best.get("seed", 1), "scale": 1.0, "from_generation": data["generation"]})
    seen = {(g["seed"], g["scale"], bool(g.get("inherit"))) for g in out}
    for _ in range(count * 20):
        if len(out) >= count:
            break
        child = mutation.apply(mutate, {k: best[k] for k in ("seed", "scale")}, rng)
        if (child["seed"], child["scale"], False) not in seen:
            seen.add((child["seed"], child["scale"], False))
            out.append(child)
    return out[:count]


def newborn(template, genome, target):
    """Writes a starting checkpoint: the template's shape and word pieces, fresh weights."""
    import torch
    from backend.neural_language_bpe_v2 import make_model
    state = torch.load(template, map_location="cpu", weights_only=True)
    if genome.get("inherit"):
        inherited = torch.load(_dir() / "inherited.pt", map_location="cpu", weights_only=True)
        if inherited.get("config", [None] * 4)[:4] != state["config"][:4] or inherited.get("arch", {}) != state.get("arch", {}) or \
                inherited["tokenizer"]["sha256"] != state["tokenizer"]["sha256"]:
            raise ValueError("Врождённая точка другого устройства: начните поколения заново")
        weights = inherited["weights"]
    else:
        width, heads, layers, context, _, _ = state["config"]
        torch.manual_seed(genome["seed"])
        model = make_model(torch, vocab_size=state["vocab_size"], width=width, heads=heads, layers=layers,
                           context=context, arch=state.get("arch") or {})
        weights = model.state_dict()
        with torch.no_grad():
            for name, value in weights.items():
                if value.is_floating_point() and value.dim() >= 2:
                    value.mul_(genome["scale"])
    payload = dict(state, weights=weights, step=0, best_step=0)
    payload.pop("optimizer", None)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + ".tmp")
    torch.save(payload, temp)
    temp.replace(target)


def prepare(template, count, generation_seed):
    """Candidate starting points as files; old generations' files are removed."""
    gen = load()["generation"] + 1
    folder = _dir()
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("g*-c*.pt"):
        try:
            if int(old.name[1:].split("-")[0]) <= gen - KEEP_GENERATIONS:
                old.unlink()
        except (ValueError, OSError):
            continue
    genomes = candidates(count, generation_seed)
    files = []
    for k, genome in enumerate(genomes):
        target = folder / ("g%d-c%d.pt" % (gen, k))
        newborn(template, genome, target)
        files.append("baldwin/" + target.name)
    return genomes, files


def remember(genomes, results):
    """results: [{"k", "run", "exam"}] (lower exam is better). The winner's genes pass on and the
    inherited start moves towards what it learned."""
    import torch
    from backend import mutation
    from backend import training_center as tc
    data = load()
    rows = [dict(r, label=describe(genomes[r["k"]]), control=bool(genomes[r["k"]].get("control")),
                 inherit=bool(genomes[r["k"]].get("inherit"))) for r in results if r.get("exam") is not None]
    if not rows:
        raise ValueError("Ни один старт не дошёл до экзамена")
    winner = min(rows, key=lambda r: r["exam"])
    genome = genomes[winner["k"]]
    control = next((r for r in rows if r["control"]), None)
    inherited = next((r for r in rows if r["inherit"]), None)
    previous = data["best"]
    improved = previous is None or winner["exam"] < previous.get("exam", float("inf"))
    data["best"] = {"seed": genome.get("seed", 1), "scale": genome.get("scale", 1.0), "exam": winner["exam"], "run": winner["run"]}
    start = torch.load(tc.folder() / winner["init"], map_location="cpu", weights_only=True)
    learned = torch.load(tc._run_dir(winner["run"]) / "language-longrun.pt.best.pt", map_location="cpu", weights_only=True)
    weights = {k: (v.float() + STEP * (learned["weights"][k].float() - v.float())).to(v.dtype) if v.is_floating_point() else v
               for k, v in start["weights"].items()}
    payload = dict(start, weights=weights, step=0)
    payload.pop("optimizer", None)
    temp = _dir() / "inherited.pt.tmp"
    torch.save(payload, temp)
    temp.replace(_dir() / "inherited.pt")
    data["generation"] += 1
    data["inherited"] = {"generation": data["generation"], "from": winner["run"], "at": _now()}
    entry = {"at": _now(), "generation": data["generation"], "winner": winner["label"], "exam": winner["exam"],
             "control": control["exam"] if control else None, "inherited": inherited["exam"] if inherited else None,
             "rows": [{k: r[k] for k in ("run", "exam", "label", "control", "inherit")} for r in rows]}
    data["history"].append(entry)
    _save(data)
    mutation.record("старт Болдуина", improved)
    return entry


def status():
    data = load()
    last = data["history"][-1] if data["history"] else None
    wins = sum(1 for h in data["history"] if h.get("inherited") is not None and h.get("control") is not None and h["inherited"] < h["control"])
    duels = sum(1 for h in data["history"] if h.get("inherited") is not None and h.get("control") is not None)
    return {"generation": data["generation"], "last": last, "best": data["best"], "has_inherited": bool(data["inherited"]),
            "duels": duels, "inherited_wins": wins,
            "curve": [{"g": h["generation"], "inherited": h.get("inherited"), "control": h.get("control")} for h in data["history"]]}
