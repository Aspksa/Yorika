"""Learning without answers: the majority selects, novelty adds variation (EVOL-RL, 2025).

For each question Yorika writes five drafts. No answer key is used to choose:
- selection: an answer is kept only when at least three of the five drafts agree on it (for a
  task, on the number after «Ответ:»; for a conversation, on how the reply begins);
- variation: among the drafts of that majority the one least like the other drafts is kept, so
  she learns the agreed answer by a path that is not a copy of the others and does not collapse
  into one way of saying everything.

Questions are fresh logic tasks (never exam questions) and prompts of conversations you rated
well. For logic the true answer is known, but it is used only afterwards, to report how often the
label-free majority was actually right: a measurement of the method, not a filter. The lesson is
judged like any other, by the exams and against the active version.
"""
import random
import time

DRAFTS = 5
MAJORITY = 3


def _words(text):
    return set(text.casefold().split())


def similarity(a, b):
    wa, wb = _words(a), _words(b)
    return len(wa & wb) / len(wa | wb) if wa | wb else 1.0


def key_of(text, is_task):
    from backend import logic
    if is_task:
        return logic.answer_of(text)
    return " ".join(text.casefold().split())[:60] or None


def pick(texts, is_task):
    """(the kept draft, its key, votes) or None when no answer has a majority."""
    votes = {}
    for k, text in enumerate(texts):
        key = key_of(text, is_task)
        if key:
            votes.setdefault(key, []).append(k)
    if not votes:
        return None
    key, members = max(votes.items(), key=lambda kv: len(kv[1]))
    if len(members) < MAJORITY:
        return None
    others = lambda k: [similarity(texts[k], texts[j]) for j in range(len(texts)) if j != k]
    novel = min(members, key=lambda k: (sum(others(k)) / max(1, len(texts) - 1), k))
    return texts[novel].strip(), key, len(members), 1 - sum(others(novel)) / max(1, len(texts) - 1)


def questions(count, seed=0):
    from backend import curiosity, logic
    from backend import self_learning as sl
    from backend import training_center as tc
    rng, banned = random.Random(seed), logic._exam_questions() | tc.protected_prompts()
    level = curiosity.logic_frontier()
    asked, seen = [], set()
    for _ in range(count * 20):
        if len(asked) >= count // 2:
            break
        t = logic.task(rng, level)
        if t["q"] not in banned and t["q"] not in seen:
            seen.add(t["q"])
            asked.append((t["q"], t["answer"]))
    chat = [i["prompt"] for i in sl._load()["items"] if i.get("rating") == "up" and i.get("source") in (None, "yorika-chat")
            and i["prompt"].casefold().strip() not in banned]
    rng.shuffle(chat)
    asked += [(q, None) for q in chat[:count - len(asked)]]
    return asked


def build(checkpoint, count=60, seed=0, should_stop=None):
    """Lessons from her own agreed drafts. Returns (pairs, report)."""
    from backend import brain, logic
    model, state = brain.load(checkpoint)
    rng = random.Random(seed)
    kept, tasks, right, novelty = [], 0, 0, []
    asked = questions(count, seed)
    for question, truth in asked:
        if should_stop and should_stop():
            break
        is_task = truth is not None
        thought = brain.think(model, state, question, drafts=DRAFTS, seed=rng.randrange(10 ** 6))
        chosen = pick(thought["texts"], is_task)
        if not chosen:
            continue
        text, key, votes, novel = chosen
        kept.append((question, text))
        novelty.append(novel)
        if is_task:
            tasks += 1
            right += logic.correct(text, truth)
    made = {"asked": len(asked), "kept": len(kept), "tasks": tasks, "right": right,
            "novelty": round(sum(novelty) / len(novelty), 3) if novelty else None}
    return kept, made


def _path():
    from backend import training_center as tc
    return tc.folder() / "selfevolve.json"


def remember(made, run_id=None):
    from backend import training_center as tc
    log = (tc._read(_path(), []) or [])[-19:]
    log.append(dict(made, run=run_id, at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
    tc._write(_path(), log)


def status():
    from backend import training_center as tc
    log = tc._read(_path(), []) or []
    tasks = sum(e.get("tasks") or 0 for e in log)
    right = sum(e.get("right") or 0 for e in log)
    return {"runs": len(log), "last": log[-1] if log else None,
            "majority_right": round(right / tasks, 3) if tasks else None}
