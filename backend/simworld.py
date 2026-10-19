"""A world of games and puzzles where every outcome is checked by code: thousands of lives a night.

Each environment writes a task, the code-written solution and the true answer. Yorika plays: her
own correct solutions are kept (the program confirms the final answer), failures get the
program's solution as a lesson. Exam tasks come from their own seeds and never become lessons.
Lives, wins and the best streak are counted per environment, so growth is visible.

The ladder: each environment has its own level. When she wins at least 80 % of at least ten
lives in one, the next nights bring harder tasks there (bigger mazes, more words, more goods);
below 20 % it steps back down, so practice stays at the edge of what she can do. The «chain»
environment is made of two other tasks whose answers must be added: a new kind of task composed
from the ones she already meets, still checked by code.
"""
import random
from collections import deque

from backend.logic import ANSWER, correct

EXAM_PER_ENV = 8
WORDS = ["лиса", "снег", "ветер", "луна", "сосна", "река", "звезда", "облако", "тропа", "иней", "заря", "лес"]
FRUITS = ["яблоки", "груши", "сливы", "вишни", "персики"]
MAX_LEVEL = 10
CLIMB, DROP, MIN_LIVES = 0.8, 0.2, 10


def _nim(rng, level):
    """Take 1–3 stones; whoever takes the last wins. The winning move keeps a multiple of 4."""
    stones = rng.randint(5, 9 + 6 * level)
    move = stones % 4
    q = "На столе %d камней. Ходим по очереди, за ход можно взять 1, 2 или 3. Кто берёт последний, выигрывает. Сколько взять сейчас, чтобы выиграть?" % stones
    if move == 0:
        steps = ["%d делится на 4" % stones, "любой ход оставляет сопернику выигрыш"]
        return q, steps, "никак"
    steps = ["%d : 4 = %d, остаток %d" % (stones, stones // 4, move), "беру %d, остаётся %d, это кратно 4" % (move, stones - move)]
    return q, steps, str(move)


def _grid(rng, level):
    """Shortest path on a small map; the program checks it with breadth-first search."""
    size = 4 + min(level, 3)
    while True:
        walls = {(rng.randrange(size), rng.randrange(size)) for _ in range(size + min(level, 5) * 2)}
        walls -= {(0, 0), (size - 1, size - 1)}
        dist = _bfs(size, walls)
        if dist is not None:
            break
    rows = ["".join("#" if (r, c) in walls else "." for c in range(size)) for r in range(size)]
    q = "Карта %d×%d, # — стена: %s. Сколько шагов от левого верхнего угла до правого нижнего (вверх, вниз, влево, вправо)?" % (
        size, size, " / ".join(rows))
    return q, ["обхожу стены", "кратчайший путь: %d шагов" % dist], str(dist)


def _bfs(size, walls):
    seen, queue = {(0, 0): 0}, deque([(0, 0)])
    while queue:
        r, c = queue.popleft()
        if (r, c) == (size - 1, size - 1):
            return seen[(r, c)]
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (r + dr, c + dc)
            if 0 <= nxt[0] < size and 0 <= nxt[1] < size and nxt not in walls and nxt not in seen:
                seen[nxt] = seen[(r, c)] + 1
                queue.append(nxt)
    return None


def _sort(rng, level):
    words = rng.sample(WORDS, min(len(WORDS), 3 + level))
    ordered = sorted(words)
    q = "Расставь по алфавиту: %s." % ", ".join(words)
    return q, ["сравниваю первые буквы, потом следующие"], ", ".join(ordered)


def _count(rng, level):
    word = "".join(rng.choice(WORDS) for _ in range(level))
    letter = rng.choice(sorted(set(word)))
    n = word.count(letter)
    q = "Сколько раз буква «%s» встречается в «%s»?" % (letter, word)
    return q, ["иду по буквам и считаю «%s»" % letter], str(n)


def _shop(rng, level):
    items = rng.sample(FRUITS, min(len(FRUITS), level + 1))
    lines, total, steps = [], 0, []
    for item in items:
        price, count = rng.randint(2, 20), rng.randint(1, 5)
        lines.append("%s по %d, взяли %d" % (item, price, count))
        steps.append("%d * %d = %d" % (price, count, price * count))
        total += price * count
    paid = (total // 50 + 1) * 50
    q = "В лавке: %s. Заплатили %d. Сколько сдачи?" % ("; ".join(lines), paid)
    steps.append("всего %d" % total)
    steps.append("%d - %d = %d" % (paid, total, paid - total))
    return q, steps, str(paid - total)


def _chain(rng, level):
    """Two tasks of other environments; the answer is the sum of their answers."""
    parts = [ENVS[env][1](rng, max(1, min(2, level - 1))) for env in (rng.choice(NUMERIC), rng.choice(NUMERIC))]
    total = int(parts[0][2]) + int(parts[1][2])
    q = "Реши две задачи и сложи ответы. Первая: %s Вторая: %s" % (parts[0][0], parts[1][0])
    steps = ["первая: %s" % parts[0][2], "вторая: %s" % parts[1][2], "%s + %s = %d" % (parts[0][2], parts[1][2], total)]
    return q, steps, str(total)


NUMERIC = ("count", "shop")
ENVS = {"nim": ("Камни (ним)", _nim), "grid": ("Лабиринт", _grid), "sort": ("Алфавит", _sort),
        "count": ("Счёт букв", _count), "shop": ("Лавка", _shop), "chain": ("Цепочка из двух задач", _chain)}
# Exam seeds per environment; older environments keep their seeds so their exams never change.
ORDER = ["count", "grid", "nim", "shop", "sort", "chain"]


def task(rng, env, level=1):
    question, steps, answer = ENVS[env][1](rng, level)
    solution = " ".join("Шаг %d: %s." % (k + 1, s) for k, s in enumerate(steps)) + " Ответ: %s." % answer
    return {"q": question, "solution": solution, "answer": answer, "env": env, "level": level}


def exam_tasks(env):
    rng = random.Random(700_000 + ORDER.index(env))
    out, seen = [], set()
    while len(out) < EXAM_PER_ENV:
        t = task(rng, env, 1 + len(out) % 3)
        if t["q"] not in seen:
            seen.add(t["q"])
            out.append(t)
    return out


_BANNED = None


def _banned():
    global _BANNED
    if _BANNED is None:
        _BANNED = {t["q"] for env in ENVS for t in exam_tasks(env)}
    return _BANNED


def fresh(rng, count, level=1, envs=None):
    """New tasks across environments, never an exam task. level: a number, or a level per environment."""
    envs = list(envs or ENVS)
    out, seen = [], set()
    for _ in range(count * 20):
        if len(out) >= count:
            break
        env = rng.choice(envs)
        t = task(rng, env, level.get(env, 1) if isinstance(level, dict) else level)
        if t["q"] in _banned() or t["q"] in seen:
            continue
        seen.add(t["q"])
        out.append(t)
    return out


def lessons(count=150, seed=11):
    rng = random.Random(seed)
    return [(t["q"], t["solution"]) for t in fresh(rng, count, 1) + fresh(rng, count // 2, 2)][:count]


def exam(loaded, max_tokens=96):
    from backend.brain import generate
    model, state = loaded
    scores = {}
    for env in sorted(ENVS):
        tasks = exam_tasks(env)
        ok = sum(correct(generate(model, state, t["q"], max_tokens)["text"], t["answer"]) for t in tasks)
        scores[env] = round(ok / len(tasks), 3)
    return scores


def live(loaded, lives=200, tries=2, seed=None, level=1):
    """Plays `lives` episodes. Returns verified own solutions, program hints and per-env stats."""
    from backend.brain import generate
    if type(lives) is not int or not 1 <= lives <= 5000:
        raise ValueError("Жизней от 1 до 5000")
    model, state = loaded
    rng = random.Random(seed)
    own, hints, stats = [], [], {env: {"lives": 0, "wins": 0} for env in ENVS}
    for t in fresh(rng, lives, level):
        stats[t["env"]]["lives"] += 1
        found = None
        for k in range(tries):
            text = generate(model, state, t["q"], 96, temperature=0 if k == 0 else 0.8)["text"]
            if correct(text, t["answer"]):
                found = text
                break
        if found:
            stats[t["env"]]["wins"] += 1
            own.append((t["q"], found.strip()))
        else:
            hints.append((t["q"], t["solution"]))
    return {"own": own, "hints": hints, "stats": stats}


def ladder():
    from backend import training_center as tc
    saved = tc._read(tc.folder() / "ladder.json", {}) or {}
    levels = saved.get("levels") or {}
    return {"levels": {env: min(MAX_LEVEL, max(1, int(levels.get(env, 1)))) for env in ENVS},
            "history": saved.get("history", [])[-30:]}


def climb(stats):
    """After a night of lives: up a level where she wins most, down where she loses most."""
    from backend import training_center as tc
    state = ladder()
    moves = []
    for env, s in stats.items():
        if env not in ENVS or s["lives"] < MIN_LIVES:
            continue
        rate, level = s["wins"] / s["lives"], state["levels"][env]
        if rate >= CLIMB and level < MAX_LEVEL:
            state["levels"][env] = level + 1
            moves.append({"env": env, "from": level, "to": level + 1, "rate": round(rate, 3)})
        elif rate < DROP and level > 1:
            state["levels"][env] = level - 1
            moves.append({"env": env, "from": level, "to": level - 1, "rate": round(rate, 3)})
    if moves:
        from datetime import datetime, timezone
        at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        state["history"] = (state["history"] + [dict(m, at=at) for m in moves])[-30:]
    tc._write(tc.folder() / "ladder.json", state)
    return moves


def record(stats):
    """Adds one night's lives to the running totals (sim.json in the training folder)."""
    from backend import training_center as tc
    total = tc._read(tc.folder() / "sim.json", {}) or {}
    envs = total.setdefault("envs", {})
    for env, s in stats.items():
        e = envs.setdefault(env, {"lives": 0, "wins": 0})
        e["lives"] += s["lives"]
        e["wins"] += s["wins"]
    total["lives"] = sum(e["lives"] for e in envs.values())
    total["nights"] = total.get("nights", 0) + 1
    tc._write(tc.folder() / "sim.json", total)
    return total


def totals():
    from backend import training_center as tc
    total = tc._read(tc.folder() / "sim.json", {}) or {}
    return {"lives": total.get("lives", 0), "nights": total.get("nights", 0),
            "envs": {env: dict(total.get("envs", {}).get(env, {"lives": 0, "wins": 0}), name=ENVS[env][0]) for env in ENVS},
            "ladder": ladder()}


__all__ = ["ANSWER", "ENVS", "exam", "lessons", "live", "task"]
