"""Language plus a strict solver: she writes the facts, a small logic engine draws the conclusion.

The idea of AlphaGeometry and neuro-symbolic systems on a small scale: the neural network does
what it is good at (reading a task in Russian and writing its facts in a short formal language),
and code does what code is good at (exact deduction). In think(), a draft that contains
«Факты: …» is run through the engine; when the engine can derive an answer, that answer replaces
the network's guess. Lessons teach the translation; the engine is never trained and never guesses.

The fact language, one fact per «;»:
  число 5 · плюс 3 · минус 2 · вдвое          (counting)
  Аня > Боря                                   (older than; the answer is the one nobody is above)
  день среда · плюс 5 дн.                      (days of the week)
  ряд 3 8 10 15                                (continue a row)
  Аня есть лисы · все лисы есть звери · вопрос Аня есть птицы   (deduction)
"""
import random
import re

from backend import logic

DAY_STEP = re.compile(r"(%s)\s*\+\s*(\d+)\s*дн\.?\s*=\s*(%s)" % ("|".join(logic.DAYS), "|".join(logic.DAYS)))
FACTS = re.compile(r"Факты:\s*(.+?)(?:Ответ:|$)", re.S)


# ---- reading a task (the code translator that writes the lessons) ---------------------

def facts_of(question):
    """The facts of a task written by logic.py, or None for anything else."""
    q = question.strip()
    if q.startswith("Продолжи ряд:"):
        numbers = re.findall(r"-?\d+", q)
        return ["ряд " + " ".join(numbers)] if len(numbers) >= 3 else None
    if q.startswith("Сегодня "):
        day = next((d for d in logic.DAYS if q.startswith("Сегодня %s." % d)), None)
        shifts = re.findall(r"(\d+) дн\.", q)
        return ["день " + day] + ["плюс %s дн." % s for s in shifts] if day and shifts else None
    if "Кто самый старший?" in q:
        pairs = re.findall(r"(\w+) старше, чем (\w+)\.", q)
        return ["%s > %s" % p for p in pairs] or None
    if q.startswith("У Лисы было"):
        start = re.match(r"У Лисы было (\d+)", q)
        facts = ["число " + start.group(1)]
        for sentence in re.split(r"(?<=\.)\s+", q)[1:]:
            number = re.search(r"\d+", sentence)
            if "в два раза больше" in sentence:
                facts.append("вдвое")
            elif number and re.search(r"нашла|подарили|собрала", sentence):
                facts.append("плюс " + number.group(0))
            elif number and re.search(r"отдала|съела|потерял", sentence):
                facts.append("минус " + number.group(0))
        return facts
    if "Верно ли, что" in q:
        name = re.match(r"(\w+) — ([^.]+)\.", q)
        asked = re.search(r"Верно ли, что (\w+) — ([^?]+)\?", q)
        if not name or not asked:
            return None
        facts = ["%s есть %s" % (name.group(1), name.group(2))]
        facts += ["все %s есть %s" % m for m in re.findall(r"Все ([^.—]+?) — ([^.]+)\.", q)]
        return facts + ["вопрос %s есть %s" % (asked.group(1), asked.group(2).strip())]
    return None


def lesson_answer(question, answer):
    facts = facts_of(question)
    return None if facts is None else "Факты: %s. Ответ: %s." % ("; ".join(facts), answer)


# ---- the engine ------------------------------------------------------------------

def derive(facts):
    """The answer the facts force, with the steps; None when they force nothing."""
    facts = [f.strip().rstrip(".") for f in facts if f.strip()]
    if not facts:
        return None
    head = facts[0]
    try:
        if head.startswith("число "):
            value, steps = int(head.split()[1]), []
            for f in facts[1:]:
                if f == "вдвое":
                    steps.append("%d * 2 = %d" % (value, value * 2))
                    value *= 2
                elif f.startswith("плюс "):
                    b = int(f.split()[1])
                    steps.append("%d + %d = %d" % (value, b, value + b))
                    value += b
                elif f.startswith("минус "):
                    b = int(f.split()[1])
                    steps.append("%d - %d = %d" % (value, b, value - b))
                    value -= b
                else:
                    return None
            return {"answer": str(value), "steps": steps}
        if head.startswith("день "):
            day = logic.DAYS.index(head.split()[1])
            steps = []
            for f in facts[1:]:
                n = int(re.match(r"плюс (\d+)", f).group(1))
                new = (day + n) % 7
                steps.append("%s + %d дн. = %s" % (logic.DAYS[day], n, logic.DAYS[new]))
                day = new
            return {"answer": logic.DAYS[day], "steps": steps}
        if head.startswith("ряд "):
            row = [int(x) for x in head.split()[1:]]
            diffs = [b - a for a, b in zip(row, row[1:])]
            if len(set(diffs)) == 1:
                step = diffs[0]
            elif len(diffs) >= 3 and len(set(diffs[0::2])) == 1 and len(set(diffs[1::2])) == 1:
                step = diffs[0] if len(diffs) % 2 == 0 else diffs[1]   # the steps take turns
            else:
                return None
            return {"answer": str(row[-1] + step), "steps": ["%d + %d = %d" % (row[-1], step, row[-1] + step)]}
        if ">" in head:
            above, everyone = set(), set()
            for f in facts:
                a, b = [x.strip() for x in f.split(">")]
                above.add(b)
                everyone |= {a, b}
            top = everyone - above
            return {"answer": top.pop(), "steps": ["никто не старше"]} if len(top) == 1 else None
        if " есть " in head:
            groups, rules, query = set(), {}, None
            for f in facts:
                if f.startswith("вопрос "):
                    query = f[len("вопрос "):].split(" есть ", 1)
                elif f.startswith("все "):
                    a, b = f[len("все "):].split(" есть ", 1)
                    rules.setdefault(a.strip(), set()).add(b.strip())
                else:
                    groups.add(f.split(" есть ", 1)[1].strip())
            if not query:
                return None
            seen, todo = set(), list(groups)
            while todo:
                g = todo.pop()
                if g not in seen:
                    seen.add(g)
                    todo += list(rules.get(g, ()))
            yes = query[1].strip() in seen
            return {"answer": "да" if yes else "неизвестно", "steps": ["%s: %s" % (query[0].strip(), ", ".join(sorted(seen)))]}
    except (ValueError, IndexError, AttributeError):
        return None
    return None


def facts_in(text):
    match = FACTS.search(text or "")
    return [f for f in match.group(1).replace("\n", ";").split(";")] if match else None


def apply(text):
    """(text, checked): when the draft wrote facts the engine can use, its answer is the engine's."""
    facts = facts_in(text)
    if not facts:
        return text, False
    found = derive(facts)
    if not found:
        return text, False
    head = text[:text.index("Ответ:")] if "Ответ:" in text else text.rstrip() + " "
    return "%sОтвет: %s." % (head, found["answer"]), True


def wrong_steps(text):
    """Day-of-week steps that are wrong («среда + 5 дн. = суббота»), like arithmetic claims."""
    bad = 0
    for day, n, result in DAY_STEP.findall(text or ""):
        if logic.DAYS[(logic.DAYS.index(day) + int(n)) % 7] != result:
            bad += 1
    return bad


# ---- lessons ---------------------------------------------------------------------

def fresh_tasks(count, seed=0, max_level=3):
    rng, banned, out, seen = random.Random(seed), logic._exam_questions(), [], set()
    for _ in range(count * 30):
        t = logic.task(rng, rng.randint(1, max_level))
        if t["q"] not in banned and t["q"] not in seen and facts_of(t["q"]) is not None:
            seen.add(t["q"])
            out.append(t)
        if len(out) >= count:
            break
    return out


def measure(loaded, tasks):
    """How often her own written facts lead the engine to the right answer."""
    from backend.brain import generate
    model, state = loaded
    ok = 0
    for t in tasks:
        text = generate(model, state, t["q"], 96)["text"]
        found = derive(facts_in(text) or [])
        ok += bool(found and found["answer"].casefold() == str(t["answer"]).casefold())
    return ok


def lessons(loaded, seed=0, count=160):
    from backend import curiosity
    level = min(5, curiosity.logic_frontier() + 1)
    tasks = fresh_tasks(count + 20, seed, level)
    check, teach = tasks[:20], tasks[20:]
    made = {"translated": measure(loaded, check), "checked": len(check)}
    pairs = [(t["q"], lesson_answer(t["q"], t["answer"])) for t in teach]
    made["lessons"] = len(pairs)
    return pairs, made
