"""Programs instead of answers: skills Yorika keeps as small verified programs, not in her weights.

For a family of tasks (days of the week, number rows, change in a shop...) a search over tiny
formulas finds the shortest one that fits a handful of examples. It is kept only if it is right
on 40 fresh examples it never saw. Then it becomes a tool: the model writes
[[skill:имя: аргументы]] and the program computes the answer, exactly, every time. Lessons
teach the model to call the skill. So she gains abilities without growing the network.

Formulas use only numbers, the task's arguments and + - * // %; they are evaluated by a small
interpreter, never by Python's eval, and nothing else can run.
"""
import ast
import random
import re
from datetime import datetime, timezone

DAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
CONSTANTS = (1, 2, 3, 4, 7, 10, 60, 100)
OPS = ("+", "-", "*", "//", "%")
TRAIN, CHECK = 8, 40
MAX_SIZE = 7
CALL = re.compile(r"^\s*([а-яёa-z_]{2,40})\s*:\s*(.{0,200})$")


def _days_task(rng):
    d, n = rng.randrange(7), rng.randint(1, 40)
    return "Сегодня %s. Какой день недели будет через %d дн.?" % (DAYS[d], n), [d, n], (d + n) % 7


def _row_task(rng):
    a, s = rng.randint(1, 30), rng.randint(2, 12)
    row = [a + s * k for k in range(4)]
    return "Продолжи ряд: %s, ?" % ", ".join(map(str, row)), row, row[-1] + s


def _alt_task(rng):
    v, s, o = rng.randint(1, 20), rng.randint(2, 9), rng.randint(2, 9)
    row = [v]
    for k in range(5):
        v += s if k % 2 == 0 else o
        row.append(v)
    return "Продолжи ряд: %s, ?" % ", ".join(map(str, row)), row, v + o


def _perimeter_task(rng):
    a, b = rng.randint(1, 60), rng.randint(1, 60)
    return "Какой периметр у прямоугольника %d на %d?" % (a, b), [a, b], 2 * (a + b)


def _change_task(rng):
    price, count = rng.randint(3, 90), rng.randint(1, 9)
    paid = (price * count // 100 + 1) * 100
    return "Взяли %d шт. по %d, дали %d. Сколько сдачи?" % (count, price, paid), [paid, price, count], paid - price * count


def _minutes_task(rng):
    h, m = rng.randint(0, 12), rng.randint(0, 59)
    return "Сколько минут в %d ч %d мин?" % (h, m), [h, m], h * 60 + m


def _nim_task(rng):
    n = rng.randint(5, 60)
    return "Камней %d, берём 1–3, кто взял последний, выиграл. Сколько взять?" % n, [n], n % 4


FAMILIES = {
    "день_через": {"title": "День недели через N дней", "args": ["день", "n"], "types": ["day", "int"], "out": "day", "make": _days_task},
    "ряд_шаг": {"title": "Ряд с постоянным шагом", "args": ["a", "b", "c", "d"], "types": ["int"] * 4, "out": "int", "make": _row_task},
    "ряд_через_один": {"title": "Ряд с двумя чередующимися шагами", "args": ["a", "b", "c", "d", "e", "f"], "types": ["int"] * 6, "out": "int", "make": _alt_task},
    "периметр": {"title": "Периметр прямоугольника", "args": ["a", "b"], "types": ["int"] * 2, "out": "int", "make": _perimeter_task},
    "сдача": {"title": "Сдача в лавке", "args": ["дали", "цена", "штук"], "types": ["int"] * 3, "out": "int", "make": _change_task},
    "минуты": {"title": "Часы и минуты в минуты", "args": ["ч", "мин"], "types": ["int"] * 2, "out": "int", "make": _minutes_task},
    "ним": {"title": "Выигрышный ход в камнях", "args": ["камней"], "types": ["int"], "out": "int", "make": _nim_task},
}


# ---- a tiny safe interpreter ------------------------------------------------

def evaluate(expr, values):
    """Numbers, argument names x0..x9 and + - * // % only. Raises ValueError on anything else."""
    ops = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
           ast.FloorDiv: lambda a, b: a // b, ast.Mod: lambda a, b: a % b}

    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return node.value
        if isinstance(node, ast.Name) and re.fullmatch(r"x[0-9]", node.id) and int(node.id[1:]) < len(values):
            return values[int(node.id[1:])]
        if isinstance(node, ast.BinOp) and type(node.op) in ops:
            left, right = walk(node.left), walk(node.right)
            if abs(left) > 10 ** 12 or abs(right) > 10 ** 12:
                raise ValueError("Слишком большие числа")
            return ops[type(node.op)](left, right)
        raise ValueError("Недопустимая формула")
    if not isinstance(expr, str) or len(expr) > 200:
        raise ValueError("Недопустимая формула")
    try:
        return walk(ast.parse(expr, mode="eval"))
    except (SyntaxError, ZeroDivisionError):
        raise ValueError("Формула не считается") from None


# ---- search: bottom-up enumeration with observational equivalence -------------

def synthesize(examples, arity, *, max_size=MAX_SIZE, cap=40000):
    """Shortest formula consistent with every (args, output) example, or None."""
    targets = tuple(out for _, out in examples)
    inputs = [args for args, _ in examples]
    by_size, seen = {}, {}

    def add(size, expr, values):
        if values in seen:
            return None
        seen[values] = expr
        by_size.setdefault(size, []).append((expr, values))
        return expr if values == targets else None

    for k in range(arity):
        hit = add(1, "x%d" % k, tuple(a[k] for a in inputs))
        if hit:
            return hit
    for c in CONSTANTS:
        add(1, str(c), tuple(c for _ in inputs))
    for size in range(3, max_size + 1, 2):
        for left_size in range(1, size - 1, 2):
            right_size = size - 1 - left_size
            for le, lv in by_size.get(left_size, []):
                for re_, rv in by_size.get(right_size, []):
                    for op in OPS:
                        try:
                            values = tuple(_apply(op, a, b) for a, b in zip(lv, rv))
                        except ZeroDivisionError:
                            continue
                        if any(abs(v) > 10 ** 9 for v in values):
                            continue
                        hit = add(size, "(%s %s %s)" % (le, op, re_), values)
                        if hit:
                            return hit
                        if len(seen) > cap:
                            return None
    return None


def _apply(op, a, b):
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "//":
        return a // b
    return a % b


def discover(name, seed=None):
    """Searches a program for one family and checks it on fresh examples."""
    family = FAMILIES[name]
    rng = random.Random(seed)
    train = [(args, out) for _, args, out in (family["make"](rng) for _ in range(TRAIN))]
    expr = synthesize(train, len(family["args"]))
    if expr is None:
        return {"name": name, "found": False, "why": "формула не найдена перебором"}
    check = [family["make"](rng) for _ in range(CHECK)]
    wrong = sum(1 for _, args, out in check if evaluate(expr, args) != out)
    if wrong:
        return {"name": name, "found": False, "why": "формула %s ошиблась на %d из %d новых примерах" % (expr, wrong, CHECK)}
    return {"name": name, "found": True, "expr": expr, "checked": CHECK}


# ---- the skill library -------------------------------------------------------

def _path():
    from backend import training_center as tc
    return tc.folder() / "skills.json"


def library():
    from backend import training_center as tc
    return tc._read(_path(), {}) or {}


def learn(seed=None):
    """Tries every family that has no skill yet; verified programs join the library."""
    from backend import training_center as tc
    skills = library()
    found = []
    for name in FAMILIES:
        if name in skills:
            continue
        result = discover(name, seed)
        if result["found"]:
            skills[name] = {"expr": result["expr"], "checked": result["checked"],
                            "found": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "uses": 0}
            found.append(name)
    tc._write(_path(), skills)
    return found


def _parse(family, text):
    parts = [p.strip().casefold() for p in text.split(",")]
    if len(parts) != len(family["args"]):
        raise ValueError("Нужно аргументов: %d" % len(family["args"]))
    values = []
    for part, kind in zip(parts, family["types"]):
        if kind == "day":
            if part not in DAYS:
                raise ValueError("Неизвестный день")
            values.append(DAYS.index(part))
        else:
            if not re.fullmatch(r"-?\d{1,9}", part):
                raise ValueError("Нужно целое число")
            values.append(int(part))
    return values


def call(text, skills=None):
    """Runs [[skill:имя: аргументы]] from the library."""
    match = CALL.match(text or "")
    if not match:
        raise ValueError("Формат: имя: аргументы")
    name, args = match.group(1).casefold(), match.group(2)
    skills = library() if skills is None else skills
    if name not in skills or name not in FAMILIES:
        raise ValueError("Такого навыка нет")
    family = FAMILIES[name]
    value = evaluate(skills[name]["expr"], _parse(family, args))
    return DAYS[value % 7] if family["out"] == "day" else str(value)


def lessons(names=None, per_skill=20, seed=5):
    """Teaches the model to call a skill: the question, then the call with its arguments."""
    from backend.logic import _exam_questions
    from backend.simworld import _banned
    rng = random.Random(seed)
    # Some families ask like the logic exam does; exam questions never become lessons.
    pairs, seen = [], set(_exam_questions()) | _banned() | {q for q, _ in exam_tasks()}
    for name in names if names is not None else library():
        family = FAMILIES.get(name)
        if not family:
            continue
        for _ in range(per_skill * 5):
            if sum(1 for p in pairs if p[2] == name) >= per_skill:
                break
            q, args, _ = family["make"](rng)
            if q in seen:
                continue
            seen.add(q)
            shown = [DAYS[a] if t == "day" else str(a) for a, t in zip(args, family["types"])]
            pairs.append((q, "Считаю программой. Ответ: [[skill:%s: %s]]." % (name, ", ".join(shown)), name))
    return [(q, a) for q, a, _ in pairs]


def exam_tasks(per_skill=4):
    """Held-out questions per family, from their own seed: (question, expected answer text)."""
    rng = random.Random(300_000)
    out = []
    for name, family in FAMILIES.items():
        for _ in range(per_skill):
            q, _, value = family["make"](rng)
            out.append((q, DAYS[value % 7] if family["out"] == "day" else str(value)))
    return out


def exam(loaded, max_tokens=64):
    """Share of held-out family questions answered right, with skills run as tools."""
    from backend.brain import generate
    from backend.logic import correct
    model, state = loaded
    tasks = exam_tasks()
    return round(sum(correct(generate(model, state, q, max_tokens)["text"], a) for q, a in tasks) / len(tasks), 3)


def describe():
    skills = library()
    return [{"name": n, "title": f["title"], "args": f["args"], "expr": skills.get(n, {}).get("expr"),
             "pretty": pretty(skills[n]["expr"], f["args"]) if n in skills else None,
             "found": skills.get(n, {}).get("found")} for n, f in FAMILIES.items()]


def pretty(expr, names):
    return re.sub(r"x([0-9])", lambda m: names[int(m.group(1))], expr).replace("//", "÷").replace("*", "×")
