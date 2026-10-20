"""The scientist inside: guesses about numbers and days, checked on thousands of cases.

A small grammar writes conjectures about divisibility, remainders of squares, sums of numbers in a
row, weekdays after so many days and parity. Each is tested on every n from 1 to 2000: one
counterexample refutes it, and the smallest one is kept; a conjecture without one is recorded as
«проверено до 2000», which is evidence, not a proof, and is said so. The record of laws and
refutations lives in scientist.json.

Before the lesson she is asked to predict, for conjectures she never saw in lessons, whether each
holds; the lessons then teach the verdict and the reason (the counterexample or the check). The
conjectures come from a grammar written by code, not from her own imagination.
"""
import math
import random
import time

from backend import logic

LIMIT = 2000


def _conjectures():
    """(text, test(n) -> bool, explain(n) -> words about a counterexample)."""
    out = []
    for k in range(2, 10):
        out.append(("n·(n+1) делится на %d" % k, lambda n, k=k: n * (n + 1) % k == 0,
                    lambda n, k=k: "%d·%d = %d не делится на %d" % (n, n + 1, n * (n + 1), k)))
        out.append(("n³ − n делится на %d" % k, lambda n, k=k: (n ** 3 - n) % k == 0,
                    lambda n, k=k: "%d³ − %d = %d не делится на %d" % (n, n, n ** 3 - n, k)))
        out.append(("сумма %d чисел подряд, начиная с n, делится на %d" % (k, k),
                    lambda n, k=k: sum(range(n, n + k)) % k == 0,
                    lambda n, k=k: "%s = %d не делится на %d" % (" + ".join(str(n + i) for i in range(k)), sum(range(n, n + k)), k)))
    for m in range(3, 10):
        out.append(("n² при делении на %d даёт остаток 0 или 1" % m, lambda n, m=m: n * n % m in (0, 1),
                    lambda n, m=m: "%d² = %d, остаток %d" % (n, n * n, n * n % m)))
    for a, b in ((2, 3), (2, 4), (3, 5), (4, 6), (2, 5), (3, 6), (3, 4), (6, 9)):
        out.append(("если n делится на %d и на %d, то n делится на %d" % (a, b, a * b),
                    lambda n, a=a, b=b: not (n % a == 0 and n % b == 0) or n % (a * b) == 0,
                    lambda n, a=a, b=b: "%d делится на %d и на %d, но не на %d" % (n, a, b, a * b)))
    for d in (7, 14, 10, 21, 30, 35, 12, 28):
        out.append(("через %d дн. после любого дня недели наступит тот же день недели" % d,
                    lambda n, d=d: logic.DAYS[(n % 7 + d) % 7] == logic.DAYS[n % 7],
                    lambda n, d=d: "%s + %d дн. = %s" % (logic.DAYS[n % 7], d, logic.DAYS[(n % 7 + d) % 7])))
    for k in (2, 4, 8, 3):
        out.append(("если n чётное, то n² делится на %d" % k, lambda n, k=k: n % 2 or n * n % k == 0,
                    lambda n, k=k: "%d чётное, а %d² = %d не делится на %d" % (n, n, n * n, k)))
    out.append(("n² + n + 41 — простое число", lambda n: _prime(n * n + n + 41),
                lambda n: "%d² + %d + 41 = %d = %s" % (n, n, n * n + n + 41, _factor(n * n + n + 41))))
    out.append(("2·n + 1 — нечётное число", lambda n: (2 * n + 1) % 2 == 1, lambda n: ""))
    return out


def _prime(x):
    return x > 1 and all(x % d for d in range(2, int(math.isqrt(x)) + 1))


def _factor(x):
    d = next(d for d in range(2, x) if x % d == 0)
    return "%d·%d" % (d, x // d)


def test(conjecture):
    text, holds, explain = conjecture
    for n in range(1, LIMIT + 1):
        if not holds(n):
            return {"text": text, "holds": False, "counterexample": n, "why": explain(n)}
    return {"text": text, "holds": True, "checked": LIMIT}


def question(text):
    return "Верно ли, что для любого натурального n: %s?" % text


def answer(result):
    if result["holds"]:
        return "Похоже, да: проверено для n от 1 до %d, контрпримера нет. Ответ: да." % result["checked"]
    return "Нет. Контрпример: n = %d, %s. Ответ: нет." % (result["counterexample"], result["why"])


def split(seed=0):
    """Conjectures for lessons and ones only asked (a fifth, chosen by the seed)."""
    items = _conjectures()
    rng = random.Random(700_000 + seed)
    asked = set(rng.sample(range(len(items)), len(items) // 5))
    return [c for k, c in enumerate(items) if k not in asked], [c for k, c in enumerate(items) if k in asked]


def _path():
    from backend import training_center as tc
    return tc.folder() / "scientist.json"


def load():
    from backend import training_center as tc
    return tc._read(_path(), {}) or {}


def research():
    """Tests every conjecture and stores the laws and the refutations."""
    from backend import training_center as tc
    results = [test(c) for c in _conjectures()]
    data = load()
    data.update(laws=[r["text"] for r in results if r["holds"]],
                refuted=[{"text": r["text"], "n": r["counterexample"], "why": r["why"]} for r in results if not r["holds"]],
                at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    tc._write(_path(), data)
    return results


def predict(loaded, results):
    from backend.brain import generate
    model, state = loaded
    right = 0
    for r in results:
        got = logic.answer_of(generate(model, state, question(r["text"]), 64)["text"])
        right += got == ("да" if r["holds"] else "нет")
    return right


def lessons(loaded, seed=0):
    research()
    taught, asked = split(seed % 7)
    asked_results = [test(c) for c in asked]
    made = {"predicted": predict(loaded, asked_results), "asked": len(asked_results)}
    pairs = []
    for c in taught:
        r = test(c)
        pairs.append((question(r["text"]), answer(r)))
        pairs.append(("Проверь гипотезу: %s." % r["text"], answer(r)))
    data = load()
    made.update(laws=len(data.get("laws", [])), refuted=len(data.get("refuted", [])), lessons=len(pairs))
    return pairs, made


def status():
    data = load()
    return {"laws": data.get("laws", [])[:8], "refuted": data.get("refuted", [])[:8],
            "counts": [len(data.get("laws", [])), len(data.get("refuted", []))]}
