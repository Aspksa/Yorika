"""More data: a dataset for long training made of your approved examples plus verified lessons.

Long training needs 10 000 reviewed records. Your conversations come first; the rest is filled
with lessons whose answers a program checked: logic, the game world at her ladder levels,
program skills, tools and dreams (tasks from answer to cause). Exam questions of every kind are
never included. The file shows its composition, so you see how much is conversation and how
much is practice. Practice teaches reasoning formats, not your style of talking; the more of
your own approved examples there are, the more she sounds like you.

The teacher (Cloud.ru) can add more conversations on the «Учитель» tab, within your token limit;
this step itself spends nothing.
"""
import json
import random
from datetime import datetime, timezone

SOURCES = ("logic", "sim", "programs", "tools", "dream")
NAMES = {"experience": "ваши разговоры", "logic": "логика", "sim": "мир задач", "programs": "программы",
         "tools": "инструменты", "dream": "сны"}


def _experience():
    from backend import self_learning as sl
    from backend import training_center as tc
    banned = tc.protected_prompts()
    records, seen = [], set()
    for item in reversed(sl._load()["items"]):
        answer = item["answer"] if item["rating"] == "up" else item.get("correction") if item["rating"] == "down" else None
        key = item["prompt"].casefold().strip()
        if not answer or key in seen or key in banned:
            continue
        seen.add(key)
        records.append({"prompt": item["prompt"], "answer": answer, "source": item.get("source", "yorika-chat"),
                        "license": "user-consent", "consent": True, "rights_reviewed_by": "владелец Yorika",
                        "quality_reviewed": True})
    return records


def _practice(source, count, seed):
    from backend import dreams, logic, plans, programs, simworld, tools
    rng = random.Random(seed)
    if source == "logic":
        pairs = logic.lessons(5, max(1, count // 5) + 5, seed=seed + 7)
    elif source == "sim":
        levels = simworld.ladder()["levels"]
        pairs = [(t["q"], t["solution"]) for t in simworld.fresh(rng, count, {e: min(simworld.MAX_LEVEL, v + 1) for e, v in levels.items()})]
        pairs += simworld.lessons(count, seed=seed + 11)
    elif source == "programs":
        if not programs.library():
            programs.learn(seed)
        pairs = programs.lessons(per_skill=max(1, count // max(1, len(programs.library()))) + 2, seed=seed + 5)
    elif source == "tools":
        pairs = tools.lessons(count, seed=seed + 3)
    else:
        pairs = dreams.dream(count, seed=seed + 13)
    return plans._synthetic(pairs, source)[:count]


def build(target=None, seed=0, write=True):
    """Returns {"name", "count", "mix", "long_ready"}; writes data/сбор-<time>.json."""
    from backend import training_center as tc
    target = target or tc.MIN_LONG_RECORDS
    if type(target) is not int or not 100 <= target <= 50000:
        raise ValueError("Размер от 100 до 50 000 записей")
    records = _experience()
    mix = {"experience": len(records)}
    keys = {r["prompt"].casefold().strip() for r in records}
    need = max(0, target - len(records))
    for k, source in enumerate(SOURCES):
        want = need // (len(SOURCES) - k) if k < len(SOURCES) - 1 else need
        got = [r for r in _practice(source, int(want * 1.3) + 10, seed + k) if r["prompt"].casefold().strip() not in keys][:want]
        keys.update(r["prompt"].casefold().strip() for r in got)
        records += got
        mix[source] = len(got)
        need -= len(got)
    random.Random(seed).shuffle(records)
    result = {"count": len(records), "mix": mix, "names": NAMES, "long_ready": tc.long_gate(records) is None,
              "conversation_share": round(mix["experience"] / max(1, len(records)), 3)}
    if write:
        name = "сбор-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + ".json"
        path = tc.folder() / "data" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as stream:
            json.dump(records, stream, ensure_ascii=False, indent=1)
        result["name"] = name
    return result
