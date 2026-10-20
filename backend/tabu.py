"""Memory of failures: changes that already failed are not tried again for a while (a tabu list).

Every mutant carries the list of changes that made it from its parent ("mixer → liquid",
"layers 4 → 6"). When the mutant fails (it does not enter the archive, or a recipe does not
win), each of its changes gets a failure mark; a success clears them. A change that failed
FAILS times with no success is tabu for the next TERM mutants of its kind, then it gets
another chance: the world around it (the parent, the data) may have changed.
"""
from datetime import datetime, timezone

FAILS = 2
TERM = 12


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _path():
    from backend import training_center as tc
    return tc.folder() / "tabu.json"


def load():
    from backend import training_center as tc
    data = tc._read(_path(), {}) or {}
    return {"changes": data.get("changes", {}), "generation": data.get("generation", {}), "log": data.get("log", [])[-30:]}


def _save(data):
    from backend import training_center as tc
    data["log"] = data["log"][-30:]
    tc._write(_path(), data)


def diff(parent, child, prefix=""):
    """The changes from parent to child, as short readable strings; nested dicts are walked."""
    out = []
    for key in sorted(set(parent or {}) | set(child or {})):
        if key in ("label", "from_run"):
            continue
        a, b = (parent or {}).get(key), (child or {}).get(key)
        if isinstance(a, dict) or isinstance(b, dict):
            out += diff(a if isinstance(a, dict) else {}, b if isinstance(b, dict) else {}, prefix + key + ".")
        elif a != b:
            out.append("%s%s: %s → %s" % (prefix, key, a, b))
    return out


def banned(domain, changes):
    """True when any of the changes is tabu now."""
    data = load()
    now = data["generation"].get(domain, 0)
    for change in changes:
        entry = data["changes"].get("%s|%s" % (domain, change))
        if entry and entry.get("until", -1) > now:
            return True
    return False


def record(domain, changes, improved):
    data = load()
    data["generation"][domain] = now = data["generation"].get(domain, 0) + 1
    for change in changes:
        key = "%s|%s" % (domain, change)
        entry = data["changes"].get(key) or {"fails": 0, "wins": 0}
        if improved:
            entry.update(fails=0, wins=entry["wins"] + 1, until=-1)
        else:
            entry["fails"] += 1
            if entry["fails"] >= FAILS and not entry["wins"]:
                entry["until"] = now + TERM
                data["log"].append({"at": _now(), "domain": domain, "change": change, "until": entry["until"]})
                entry["fails"] = 0
        data["changes"][key] = entry
    _save(data)


def status():
    data = load()
    active = []
    for key, entry in data["changes"].items():
        domain, change = key.split("|", 1)
        left = entry.get("until", -1) - data["generation"].get(domain, 0)
        if left > 0:
            active.append({"domain": domain, "change": change, "left": left})
    return {"active": sorted(active, key=lambda e: -e["left"])[:12], "count": len(active), "log": data["log"][-6:]}
