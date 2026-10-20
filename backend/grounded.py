"""Language through actions: words mean what they do in a small world, checked by executing them.

A field 5 by 5 with a few objects and a tree. An instruction («возьми синий квадрат, сделай два
шага вправо и один вниз») is carried out by code in that world, and the answer is where the object
ends up or which object stands where. So «вправо», «левее дерева», «синий» are not just words next
to other words: each lesson is a sentence whose truth the world itself confirmed (the idea of
grounded language learning, e.g. BabyAI, Chevalier-Boisvert et al. 2019).

One combination of colour and shape (жёлтая звезда) never appears in lessons; the transfer test
asks only about it, so a better score there means she put «жёлтый» and «звезда» together herself.
"""
import random

from backend import logic

SIZE = 5
COLOURS = ("красный", "синий", "зелёный", "жёлтый")
FEMININE = {"красный": "красная", "синий": "синяя", "зелёный": "зелёная", "жёлтый": "жёлтая"}
ACCUSATIVE = {"красный": "красную", "синий": "синюю", "зелёный": "зелёную", "жёлтый": "жёлтую"}
SHAPES = ("круг", "квадрат", "треугольник", "звезда")
MOVES = {"вправо": (1, 0), "влево": (-1, 0), "вверх": (0, -1), "вниз": (0, 1)}
COUNT = {1: "один шаг", 2: "два шага", 3: "три шага"}
HELD_OUT = ("жёлтый", "звезда")


def name(obj, case="nom"):
    colour, shape = obj
    if shape == "звезда":
        return "%s %s" % ((FEMININE if case == "nom" else ACCUSATIVE)[colour], shape if case == "nom" else "звезду")
    return "%s %s" % (colour, shape)


def cell(pos):
    return "(%d,%d)" % pos


def scene(rng, target=None, allow_held=False):
    """A world: 3 objects with different colours and shapes in different cells, and a tree."""
    objects = [target] if target else []
    while len(objects) < 3:
        obj = (rng.choice(COLOURS), rng.choice(SHAPES))
        if obj not in objects and (obj != HELD_OUT or allow_held):
            objects.append(obj)
    cells = rng.sample([(x, y) for x in range(1, SIZE + 1) for y in range(1, SIZE + 1)], 4)
    return {"objects": dict(zip(objects, cells[:3])), "tree": cells[3]}


def describe(world):
    parts = ["Поле %dx%d, клетка (столбец,строка)." % (SIZE, SIZE)]
    for obj, pos in world["objects"].items():
        parts.append("%s в %s." % (name(obj).capitalize(), cell(pos)))
    parts.append("Дерево в %s." % cell(world["tree"]))
    return " ".join(parts)


def execute(world, obj, steps):
    """Where the object ends up; the edge of the field stops it."""
    x, y = world["objects"][obj]
    trace = []
    for direction, n in steps:
        dx, dy = MOVES[direction]
        for _ in range(n):
            x, y = min(SIZE, max(1, x + dx)), min(SIZE, max(1, y + dy))
        trace.append("%s %d → %s" % (direction, n, cell((x, y))))
    return (x, y), trace


def relation(world, obj):
    """Where the object is relative to the tree, in words that the coordinates confirm."""
    (x, y), (tx, ty) = world["objects"][obj], world["tree"]
    side = "левее" if x < tx else "правее" if x > tx else "в том же столбце, что и"
    level = "выше" if y < ty else "ниже" if y > ty else "в той же строке"
    return side, level


def task(rng, target=None, allow_held=False):
    world = scene(rng, target, allow_held)
    obj = target or rng.choice(list(world["objects"]))
    kind = rng.choice(("move", "move", "side", "where"))
    text = describe(world)
    if kind == "move":
        steps = [(d, rng.randint(1, 3)) for d in rng.sample(list(MOVES), rng.randint(1, 2))]
        end, trace = execute(world, obj, steps)
        said = " и ".join("%s %s" % (COUNT[n], d) for d, n in steps)
        q = "%s Возьми %s и сделай %s. В какой клетке %s теперь?" % (text, name(obj, "acc"), said, "она" if obj[1] == "звезда" else "он")
        sol = ["%s в %s" % (name(obj), cell(world["objects"][obj]))] + trace
        return {"q": q, "solution": _solution(sol, cell(end)), "answer": cell(end), "kind": kind, "object": obj}
    if kind == "side":
        side, _ = relation(world, obj)
        q = "%s %s левее или правее дерева?" % (text, name(obj).capitalize())
        x, tx = world["objects"][obj][0], world["tree"][0]
        answer = side if side in ("левее", "правее") else "в том же столбце"
        sol = ["столбец предмета %d, столбец дерева %d" % (x, tx)]
        return {"q": q, "solution": _solution(sol, answer), "answer": answer, "kind": kind, "object": obj}
    q = "%s В какой клетке %s?" % (text, name(obj))
    return {"q": q, "solution": _solution(["смотрю на описание поля"], cell(world["objects"][obj])),
            "answer": cell(world["objects"][obj]), "kind": kind, "object": obj}


def _solution(steps, answer):
    return " ".join("Шаг %d: %s." % (k + 1, s) for k, s in enumerate(steps)) + " Ответ: %s." % answer


def check(t, text):
    """The answer, checked against the world (a cell is compared without spaces)."""
    got = logic.answer_of(text)
    return got is not None and got.replace(" ", "") == t["answer"].casefold().replace(" ", "")


def transfer_tasks(seed=0, count=16):
    rng = random.Random(600_000 + seed)
    return [task(rng, HELD_OUT, allow_held=True) for _ in range(count)]


def measure(loaded, tasks):
    from backend.brain import generate
    model, state = loaded
    return sum(check(t, generate(model, state, t["q"], 96)["text"]) for t in tasks)


def lessons(loaded, seed=0, count=160):
    rng = random.Random(seed)
    check_tasks = transfer_tasks(seed % 5)
    made = {"transfer": measure(loaded, check_tasks), "asked": len(check_tasks)}
    pairs = []
    for _ in range(count):
        t = task(rng)
        if t["object"] != HELD_OUT:
            pairs.append((t["q"], t["solution"]))
    made["lessons"] = len(pairs)
    return pairs, made
