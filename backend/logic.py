"""Logic Yorika can be checked on: tasks written and verified by code, in levels of steps.

Every task has a known answer, so nobody has to judge it. Exam tasks come from their own
random seeds and are removed from every lesson, so passing the exam cannot come from
memorising it. Self-play keeps only solutions whose final answer the program confirms.
"""
import random
import re

LEVELS = (1, 2, 3, 4, 5)
EXAM_PER_LEVEL = 12
PASS = 0.8
NAMES = ["Аня", "Боря", "Вика", "Гена", "Даша", "Егор", "Жанна", "Захар", "Ира", "Костя", "Лена", "Миша"]
THINGS = ["яблок", "орехов", "шишек", "конфет", "ягод", "камушков"]
DAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
ANSWER = re.compile(r"Ответ:\s*([^\n.]+)")


def _arith(rng, level):
    a = rng.randint(2, 20)
    thing = rng.choice(THINGS)
    text, steps, value = ["У Лисы было %d %s." % (a, thing)], [], a
    for k in range(level):
        kind = rng.choice(["add", "sub", "mul"] if value <= 30 else ["add", "sub"])
        if kind == "add":
            b = rng.randint(1, 15)
            text.append(rng.choice(["Она нашла ещё %d.", "Ей подарили %d.", "Потом она собрала ещё %d."]) % b)
            steps.append("%d + %d = %d" % (value, b, value + b))
            value += b
        elif kind == "sub" and value > 1:
            b = rng.randint(1, value - 1)
            text.append(rng.choice(["Она отдала %d.", "%d она съела.", "Потом %d потерялись."]) % b)
            steps.append("%d - %d = %d" % (value, b, value - b))
            value -= b
        else:
            text.append("Потом их стало в два раза больше.")
            steps.append("%d * 2 = %d" % (value, value * 2))
            value *= 2
    return " ".join(text) + " Сколько у неё теперь?", steps, str(value)


def _order(rng, level):
    people = rng.sample(NAMES, level + 1)
    pairs = [(people[k], people[k + 1]) for k in range(level)]
    shown = pairs[:]
    rng.shuffle(shown)
    facts = " ".join("%s старше, чем %s." % p for p in shown)
    steps = ["%s старше, чем %s" % p for p in pairs]
    if level > 1:
        steps.append("значит, по возрасту: " + " > ".join(people))
    return facts + " Кто самый старший?", steps, people[0]


def _days(rng, level):
    start = rng.randrange(7)
    shifts = [rng.randint(1, 9) for _ in range(level)]
    if level == 1:
        text = "Сегодня %s. Какой день недели будет через %d дн.?" % (DAYS[start], shifts[0])
    else:
        text = "Сегодня %s. Прошло %s дн. Какой теперь день недели?" % (
            DAYS[start], " дн., потом ещё ".join(str(s) for s in shifts))
    steps, day = [], start
    for shift in shifts:
        new = (day + shift) % 7
        steps.append("%s + %d дн. = %s" % (DAYS[day], shift, DAYS[new]))
        day = new
    return text, steps, DAYS[day]


def _sequence(rng, level):
    start, step = rng.randint(1, 20), rng.randint(2, 9)
    if level == 1:
        row = [start + step * k for k in range(4)]
        return ("Продолжи ряд: %s, ?" % ", ".join(map(str, row)),
                ["каждое число больше на %d" % step, "%d + %d = %d" % (row[-1], step, row[-1] + step)], str(row[-1] + step))
    other = rng.randint(2, 9)
    row, value = [start], start
    for k in range(5):
        value += step if k % 2 == 0 else other
        row.append(value)
    nxt = value + (step if len(row) % 2 == 1 else other)
    add = step if len(row) % 2 == 1 else other
    return ("Продолжи ряд: %s, ?" % ", ".join(map(str, row)),
            ["прибавляем по очереди %d и %d" % (step, other), "%d + %d = %d" % (value, add, nxt)], str(nxt))


def _syllogism(rng, level):
    chain = rng.sample(["лисы", "звери", "существа", "жители леса", "друзья снега", "любители зимы"], level + 1)
    name = rng.choice(NAMES)
    facts = ["%s — %s." % (name, chain[0])] + ["Все %s — %s." % (chain[k], chain[k + 1]) for k in range(level)]
    shown = facts[1:]
    rng.shuffle(shown)
    steps = ["%s — %s, а все %s — %s" % (name, chain[k], chain[k], chain[k + 1]) for k in range(level)]
    if rng.random() < 0.4:
        # Not everything follows: the asked group is linked the other way round.
        other = rng.choice(["птицы", "рыбы", "горожане", "соседи"])
        shown.append("Все %s — %s." % (other, chain[-1]))
        rng.shuffle(shown)
        steps.append("из этого не следует, что %s — %s" % (name, other))
        return " ".join([facts[0]] + shown) + " Верно ли, что %s — %s?" % (name, other), steps, "неизвестно"
    return " ".join([facts[0]] + shown) + " Верно ли, что %s — %s?" % (name, chain[-1]), steps, "да"


KINDS = {1: (_arith, _order, _days, _sequence, _syllogism), 2: (_arith, _order, _days, _sequence, _syllogism),
         3: (_arith, _order, _days, _syllogism), 4: (_arith, _order, _days, _syllogism), 5: (_arith, _order, _days)}


def task(rng, level):
    question, steps, answer = rng.choice(KINDS[level])(rng, level)
    solution = " ".join("Шаг %d: %s." % (k + 1, s) for k, s in enumerate(steps)) + " Ответ: %s." % answer
    return {"q": question, "solution": solution, "answer": answer, "level": level}


def exam_tasks(level):
    rng = random.Random(900_000 + level)
    seen, tasks = set(), []
    while len(tasks) < EXAM_PER_LEVEL:
        t = task(rng, level)
        if t["q"] not in seen:
            seen.add(t["q"])
            tasks.append(t)
    return tasks


_EXAM_QUESTIONS = None


def _exam_questions():
    global _EXAM_QUESTIONS
    if _EXAM_QUESTIONS is None:
        _EXAM_QUESTIONS = {t["q"] for level in LEVELS for t in exam_tasks(level)}
    return _EXAM_QUESTIONS


def lessons(max_level=2, per_level=60, seed=7):
    """Code-written step-by-step solutions; never an exam question."""
    if type(max_level) is not int or not 1 <= max_level <= 5:
        raise ValueError("Уровень от 1 до 5")
    rng, banned, pairs = random.Random(seed), _exam_questions(), []
    for level in range(1, max_level + 1):
        seen = set()
        for _ in range(per_level * 20):
            if len(seen) >= per_level:
                break
            t = task(rng, level)
            if t["q"] in banned or t["q"] in seen:
                continue
            seen.add(t["q"])
            pairs.append((t["q"], t["solution"]))
    return pairs


def answer_of(text):
    match = ANSWER.search(text or "")
    return match.group(1).strip().casefold() if match else None


def correct(text, expected):
    from backend.tools import run_tools
    try:
        text = run_tools(text)[0]
    except Exception:  # noqa: BLE001 - a broken tool call simply is not a correct answer
        pass
    got = answer_of(text)
    return got is not None and got == str(expected).casefold()


def frontier(scores):
    """The first level not yet passed: where learning is most useful (the edge of ability)."""
    for level in LEVELS:
        if (scores or {}).get(str(level), 0) < PASS:
            return level
    return LEVELS[-1]


def exam(loaded, *, think=None, max_tokens=96):
    """Accuracy per level on held-out tasks; think(model, state, q) can replace greedy answers."""
    from backend.brain import generate
    model, state = loaded
    scores = {}
    for level in LEVELS:
        tasks = exam_tasks(level)
        ok = 0
        for t in tasks:
            text = think(model, state, t["q"]) if think else generate(model, state, t["q"], max_tokens)["text"]
            ok += correct(text, t["answer"])
        scores[str(level)] = round(ok / len(tasks), 3)
        if ok == 0 and level >= 2:
            # Higher levels cannot be passed when this one has zero; skip the time.
            for rest in LEVELS[level:]:
                scores[str(rest)] = 0.0
            break
    return {"levels": scores, "frontier": frontier(scores)}


def selfplay(loaded, level, count=40, tries=4, seed=None):
    """The model solves fresh tasks several times; the program keeps verified solutions.

    Correct own solutions are what it learns from (self-taught reasoning). Where every try
    failed, the code-written solution is added instead, so a failure still teaches.
    """
    from backend.brain import generate
    if type(level) is not int or level not in LEVELS or type(count) is not int or not 1 <= count <= 500:
        raise ValueError("Уровень 1–5, задач от 1 до 500")
    model, state = loaded
    rng, banned = random.Random(seed), _exam_questions()
    own, hints, solved, seen = [], [], 0, set()
    while len(seen) < count:
        t = task(rng, level)
        if t["q"] in banned or t["q"] in seen:
            continue
        seen.add(t["q"])
        found = None
        for k in range(tries):
            text = generate(model, state, t["q"], 96, temperature=0 if k == 0 else 0.8)["text"]
            if correct(text, t["answer"]):
                found = text
                break
        if found:
            solved += 1
            own.append((t["q"], found.strip()))
        else:
            hints.append((t["q"], t["solution"]))
    return {"own": own, "hints": hints, "solved": solved, "count": count, "level": level}
