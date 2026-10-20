"""Analogies: one skeleton of a task in different guises, so she learns the structure, not the words.

A counting task is a start and a list of changes, whether it is a fox with nuts, a train with
passengers or a piggy bank with coins. An ordering task is a chain of «больше», whether it is age,
height or speed. Lessons show a solved task in one guise next to a new one in another («реши так
же»). One guise is never used in lessons: the transfer test asks only it, so a better score there
means the structure moved to a place she has never seen.
"""
import random

from backend import logic

COUNT = {
    "лиса": ("У Лисы было {n} орехов.", "Она нашла ещё {n}.", "Она отдала {n}.", "Сколько у неё теперь?"),
    "поезд": ("В вагоне ехали {n} пассажиров.", "На станции вошли ещё {n}.", "На станции вышли {n}.", "Сколько пассажиров теперь?"),
    "копилка": ("В копилке было {n} монет.", "Туда положили ещё {n}.", "Оттуда взяли {n}.", "Сколько монет теперь?"),
    "склад": ("На складе лежало {n} ящиков.", "Привезли ещё {n}.", "Увезли {n}.", "Сколько ящиков теперь?"),
}
ORDER = {
    "возраст": ("{a} старше, чем {b}.", "Кто самый старший?"),
    "рост": ("{a} выше, чем {b}.", "Кто самый высокий?"),
    "бег": ("{a} бегает быстрее, чем {b}.", "Кто бегает быстрее всех?"),
    "очередь": ("{a} пришёл раньше, чем {b}.", "Кто пришёл первым?"),
}
HELD_OUT = {"count": "склад", "order": "очередь"}   # never in lessons: only the transfer test asks them


def count_task(rng, level, guise):
    start, says = rng.randint(3, 20), COUNT[guise]
    text, steps, value = [says[0].format(n=start)], [], start
    for _ in range(level):
        if rng.random() < 0.5 or value < 3:
            b = rng.randint(1, 12)
            text.append(says[1].format(n=b))
            steps.append("%d + %d = %d" % (value, b, value + b))
            value += b
        else:
            b = rng.randint(1, value - 1)
            text.append(says[2].format(n=b))
            steps.append("%d - %d = %d" % (value, b, value - b))
            value -= b
    return {"q": " ".join(text + [says[3]]), "steps": steps, "answer": str(value), "kind": "count", "guise": guise}


def order_task(rng, level, guise):
    people = rng.sample(logic.NAMES, level + 1)
    pairs = [(people[k], people[k + 1]) for k in range(level)]
    shown = pairs[:]
    rng.shuffle(shown)
    fact, question = ORDER[guise]
    steps = [fact.format(a=a, b=b).rstrip(".") for a, b in pairs]
    return {"q": " ".join(fact.format(a=a, b=b) for a, b in shown) + " " + question, "steps": steps,
            "answer": people[0], "kind": "order", "guise": guise}


def make(rng, kind, guise, level):
    return count_task(rng, level, guise) if kind == "count" else order_task(rng, level, guise)


def solution(t):
    return " ".join("Шаг %d: %s." % (k + 1, s) for k, s in enumerate(t["steps"])) + " Ответ: %s." % t["answer"]


def taught(kind):
    table = COUNT if kind == "count" else ORDER
    return [g for g in table if g != HELD_OUT[kind]]


def transfer_tasks(seed=0, per_kind=10):
    rng = random.Random(500_000 + seed)
    return [make(rng, kind, HELD_OUT[kind], rng.randint(1, 3)) for kind in ("count", "order") for _ in range(per_kind)]


def transfer(loaded, tasks):
    from backend.brain import generate
    model, state = loaded
    return sum(logic.correct(generate(model, state, t["q"], 96)["text"], t["answer"]) for t in tasks)


def lessons(loaded, seed=0, count=120):
    rng = random.Random(seed)
    check = transfer_tasks(seed % 7)
    made = {"transfer": transfer(loaded, check), "asked": len(check)}
    pairs = []
    for _ in range(count):
        kind = rng.choice(("count", "order"))
        source_guise, target_guise = rng.sample(taught(kind), 2)
        level = rng.randint(1, 2)
        source, target = make(rng, kind, source_guise, level), make(rng, kind, target_guise, level)
        pairs.append(("%s Похожая задача: %s Её решение: %s Реши так же." % (target["q"], source["q"], solution(source)),
                      solution(target)))
        pairs.append((target["q"], solution(target)))
    made["lessons"] = len(pairs)
    return pairs, made
