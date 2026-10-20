"""Dreams: at night the day's kinds of tasks are replayed backwards, from the answer to its cause.

Like the hippocampus replaying the day in sleep, but checked by code. Three kinds of dream:
«why» (the task and its answer are given, the lesson is the chain of steps that leads there),
inverse tasks (the result is known, find what produced it) and chains of two tasks. Every dream
is generated together with its true answer and kept only if the program confirms it, so a dream
never teaches something false. They become approved lessons in experience, source «dream».
"""
import random

from backend.logic import correct

MAX_CHARS = 360


def _steps(*steps, answer):
    return " ".join("Шаг %d: %s." % (k + 1, s) for k, s in enumerate(steps)) + " Ответ: %s." % answer


def _inverse_number(rng):
    x, b = rng.randint(2, 60), rng.randint(2, 40)
    op = rng.choice(["прибавили", "умножили на"])
    c = x + b if op == "прибавили" else x * b
    q = "Задумали число, %s %d и получили %d. Какое число задумали?" % (op, b, c)
    back = "%d - %d = %d" % (c, b, x) if op == "прибавили" else "%d : %d = %d" % (c, b, x)
    return q, _steps("иду назад от результата", back, answer=x), str(x)


def _inverse_shop(rng):
    paid = rng.choice([50, 100, 200, 500])
    total = rng.randint(5, paid - 1)
    change = paid - total
    q = "Заплатили %d, сдачи дали %d. На сколько купили?" % (paid, change)
    return q, _steps("покупка + сдача = заплатили", "%d - %d = %d" % (paid, change, total), answer=total), str(total)


def _inverse_nim(rng):
    left = 4 * rng.randint(1, 10)
    took = rng.randint(1, 3)
    q = ("В игре в камни я взяла %d и оставила сопернику %d, это кратно 4. Сколько камней было перед моим ходом?"
         % (took, left))
    return q, _steps("было = осталось + взяла", "%d + %d = %d" % (left, took, left + took), answer=left + took), str(left + took)


def _inverse_days(rng):
    days = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
    end, n = rng.randrange(7), rng.randint(1, 20)
    start = (end - n) % 7
    q = "Через %d дн. будет %s. Какой день сегодня?" % (n, days[end])
    return q, _steps("иду назад на %d дней" % n, "%d по модулю 7 = %d" % (n, n % 7), answer=days[start]), days[start]


INVERSE = (_inverse_number, _inverse_shop, _inverse_nim, _inverse_days)


def why(task):
    """The task with its answer given; the lesson is how the answer follows."""
    q = "Почему в задаче «%s» ответ %s?" % (task["q"], task["answer"])
    return q, task["solution"], task["answer"]


def dream(count=80, seed=None, levels=None):
    """Verified dream lessons: (prompt, answer) pairs, never exam questions."""
    from backend import logic, simworld
    rng = random.Random(seed)
    banned = logic._exam_questions() | simworld._banned()
    out, seen = [], set()
    for _ in range(count * 10):
        if len(out) >= count:
            break
        kind = rng.random()
        if kind < 0.45:
            q, solution, answer = rng.choice(INVERSE)(rng)
        elif kind < 0.8:
            t = simworld.fresh(rng, 1, level=levels or 1)[0]
            q, solution, answer = why(t)
        else:
            t = logic.task(rng, rng.choice((1, 2, 3)))
            q, solution, answer = why(t)
        if q in banned or q in seen or len(q) + len(solution) > MAX_CHARS or not correct(solution, answer):
            continue
        seen.add(q)
        out.append((q, solution))
    return out


def night_step(count=80):
    from backend import curiosity, simworld
    pairs = dream(count, levels=simworld.ladder()["levels"])
    added = curiosity._add(pairs, "dream")
    return "приснилось %d задач от ответа к причине, новых уроков %d" % (len(pairs), added)
