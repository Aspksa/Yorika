"""Growing up in stages, after Piaget: the early ideas children master before counting and proofs.

0. Object permanence: a hidden thing is still where it was put (also when it was moved in plain
   view: the «A, not B» task).
1. Conservation: pouring water into a narrow glass or spreading cones apart does not change how
   much there is; only adding or taking away does.
2. Cause and effect: what came first, and what follows when the cause is absent («если пошёл
   дождь, дорога мокрая; дорога сухая — был ли дождь?»).
3. Reversibility and classes: adding back what was taken returns the start; there are more
   animals than foxes when every fox is an animal.

Every stage has its own exam from its own seeds, never used in lessons. A stage counts as reached
at 80 %; lessons are the current stage plus a review of the earlier ones. Then logic.py (counting,
order, days, rows, deductions) is the next school.
"""
import random

from backend import logic

STAGES = ("Постоянство предмета", "Сохранение количества", "Причина и следствие", "Обратимость и классы")
PASS = 0.8
EXAM = 10
THINGS = ("мяч", "ключ", "шишку", "колокольчик", "орех")
PLACES = (("под коробку", "под коробкой"), ("в корзину", "в корзине"), ("за дерево", "за деревом"),
          ("в сундук", "в сундуке"), ("под подушку", "под подушкой"))


def _permanence(rng):
    thing, name = rng.choice(THINGS), rng.choice(("Аня", "Вика", "Даша", "Жанна", "Ира", "Лена", "Лиса"))
    (put, where), (put2, where2) = rng.sample(PLACES, 2)
    if rng.random() < 0.5:
        return "%s спрятала %s %s и ушла. Где %s?" % (name, thing, put, thing), where
    return ("%s спрятала %s %s, потом у всех на глазах переложила %s. Где %s?" % (name, thing, put, put2, thing), where2)


def _conservation(rng):
    n = rng.randint(4, 12)
    kind = rng.randrange(4)
    if kind == 0:
        liquid = rng.choice(("Воду", "Сок", "Молоко", "Чай"))
        source = rng.choice(("широкого стакана", "миски", "кастрюли", "кружки"))
        target = rng.choice(("узкий высокий стакан", "бутылку", "вазу", "графин"))
        return "%s из %s перелили в %s. Его стало больше, меньше или столько же?" % (liquid, source, target), "столько же"
    if kind == 1:
        return "В ряду %d шишек. Их раздвинули пошире, ряд стал длиннее. Шишек стало больше, меньше или столько же?" % n, "столько же"
    if kind == 2:
        stuff = rng.choice(("пластилина", "теста", "глины", "снега"))
        shape = rng.choice(("длинную колбаску", "плоский блин", "много маленьких шариков", "башенку"))
        return "Из комка %s сделали %s. %s стало больше, меньше или столько же?" % (stuff, shape, stuff.capitalize()), "столько же"
    k = rng.randint(1, 3)
    return "В ряду %d шишек. Добавили ещё %d. Шишек стало больше, меньше или столько же?" % (n, k), "больше"


CAUSES = (("пошёл дождь", "дорога мокрая", "дорога сухая"), ("лиса толкнула вазу", "ваза упала", "ваза стоит на месте"),
          ("выключили свет", "в комнате темно", "в комнате светло"), ("пришла зима", "выпал снег", "снега нет"),
          ("полили цветы", "земля влажная", "земля сухая"), ("закипел чайник", "из носика идёт пар", "пара нет"),
          ("подул ветер", "листья шевелятся", "листья неподвижны"), ("зажгли печь", "в доме тепло", "в доме холодно"),
          ("лиса проголодалась", "она ищет еду", "она спит"), ("сломался будильник", "он не звонит", "он звонит"),
          ("растаял лёд", "на полу лужа", "пол сухой"), ("закрыли окно", "сквозняка нет", "сквозняк есть"))


def _cause(rng):
    cause, effect, absent = rng.choice(CAUSES)
    kind = rng.randrange(3)
    if kind == 0:
        return "Если %s, то %s. Сейчас %s. Было ли так, что %s?" % (cause, effect, absent, cause), "нет"
    if kind == 1:
        return "Сначала %s, и поэтому %s. Что было раньше: «%s» или «%s»?" % (cause, effect, effect, cause), cause
    return "Если %s, то %s. Известно, что %s. Верно ли, что %s?" % (cause, effect, cause, effect), "да"


def _reverse(rng):
    if rng.random() < 0.5:
        n, k = rng.randint(4, 15), rng.randint(1, 3)
        return "Было %d орехов. Убрали %d, а потом положили обратно %d. Сколько стало?" % (n, k, k), str(n)
    foxes, hares = rng.randint(2, 6), rng.randint(1, 6)
    return ("На поляне %d лис и %d зайцев. Все они звери. Кого больше: лис или зверей?" % (foxes, hares), "зверей")


MAKERS = (_permanence, _conservation, _cause, _reverse)


def task(rng, stage):
    q, a = MAKERS[stage](rng)
    return {"q": q, "answer": a, "stage": stage}


def exam_tasks(stage):
    rng, seen, out = random.Random(700_000 + stage), set(), []
    for _ in range(400):
        t = task(rng, stage)
        if t["q"] not in seen:
            seen.add(t["q"])
            out.append(t)
        if len(out) >= EXAM:
            break
    return out


def _banned():
    return {t["q"] for s in range(len(STAGES)) for t in exam_tasks(s)}


def exam(loaded):
    from backend.brain import generate
    model, state = loaded
    scores = {}
    for stage in range(len(STAGES)):
        tasks = exam_tasks(stage)
        ok = sum(logic.correct(generate(model, state, t["q"], 48)["text"], t["answer"]) for t in tasks)
        scores[str(stage)] = round(ok / len(tasks), 3)
    return scores


def stage_of(scores):
    for stage in range(len(STAGES)):
        if (scores or {}).get(str(stage), 0) < PASS:
            return stage
    return len(STAGES)


def _path():
    from backend import training_center as tc
    return tc.folder() / "development.json"


def load():
    from backend import training_center as tc
    return tc._read(_path(), {}) or {"stage": 0, "scores": {}, "history": []}


def finished():
    return load()["stage"] >= len(STAGES)


def lessons(loaded, seed=0, count=160):
    from backend import training_center as tc
    import time
    scores = exam(loaded)
    stage = stage_of(scores)
    data = load()
    data.update(stage=stage, scores=scores)
    data["history"] = (data.get("history", []) + [{"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "stage": stage,
                                                    "scores": scores}])[-20:]
    tc._write(_path(), data)
    rng, banned, pairs, seen = random.Random(seed), _banned(), [], set()
    current = min(stage, len(STAGES) - 1)
    for _ in range(count * 10):
        # Two thirds the current stage, the rest a review of the earlier ones.
        s = current if rng.random() < 0.67 or current == 0 else rng.randrange(current)
        t = task(rng, s)
        if t["q"] in banned or t["q"] in seen:
            continue
        seen.add(t["q"])
        pairs.append((t["q"], "Ответ: %s." % t["answer"]))
        if len(pairs) >= count:
            break
    return pairs, {"stage": stage, "title": STAGES[current], "scores": scores, "lessons": len(pairs)}
