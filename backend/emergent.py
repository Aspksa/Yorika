"""Her own language is born: a signalling game, generations, and then a translation into Russian.

Lewis signalling game (Lewis 1969; Lazaridou et al. 2017): a speaker sees one of 16 objects (four
colours times four shapes) and sends two signs from an alphabet of eight; a listener sees only the
signs and must name the object. Nobody gives them a dictionary: the signs get meaning only because
some messages work and others do not (REINFORCE with a baseline for the speaker, the true object
for the listener after each game).

Language of generations (iterated learning, Kirby et al. 2008/2015): a new speaker learns only from
part of the previous speaker's messages (a bottleneck: not every object is seen) and then plays.
A language that says colour and shape by separate signs passes the bottleneck; a list of arbitrary
names does not. How compositional it is, is measured, not assumed: topographic similarity, the
rank correlation between how different two objects are and how different their messages are.

The language lives on between nights in emergent.json: each night continues from the last
generation. Then it is grounded: lessons tie each signal to Russian words («сигнал «ab» — это
красный круг») for most objects; the rest are only asked, so a better score there means she reads
the signs by their parts. The game is code with small tables, not her network; what her network
learns is the translation.
"""
import math
import random
import time

COLOURS = ("красный", "синий", "зелёный", "жёлтый")
FEMININE = {"красный": "красная", "синий": "синяя", "зелёный": "зелёная", "жёлтый": "жёлтая"}
SHAPES = ("круг", "квадрат", "треугольник", "звезда")
ALPHABET = "abcdefgh"
LENGTH = 2
OBJECTS = [(c, s) for c in range(len(COLOURS)) for s in range(len(SHAPES))]
BOTTLENECK = 10      # of 16 objects a new generation sees
ASKED_ONLY = 4       # objects never in lessons, only in her test


def name(obj):
    colour, shape = COLOURS[obj[0]], SHAPES[obj[1]]
    return "%s %s" % (FEMININE[colour] if shape == "звезда" else colour, shape)


def _softmax(xs):
    m = max(xs)
    e = [math.exp(x - m) for x in xs]
    s = sum(e)
    return [v / s for v in e]


class Speaker:
    """Message logits are a whole-object part plus a colour part and a shape part: she can give
    every object an arbitrary name or build names from parts; the game decides which."""

    def __init__(self, rng, spread=1.0):
        self.h = {o: [[rng.gauss(0, spread) for _ in ALPHABET] for _ in range(LENGTH)] for o in OBJECTS}
        self.c = [[[0.0 for _ in ALPHABET] for _ in range(LENGTH)] for _ in COLOURS]
        self.s = [[[0.0 for _ in ALPHABET] for _ in range(LENGTH)] for _ in SHAPES]

    def probs(self, obj, pos):
        return _softmax([h + a + b for h, a, b in zip(self.h[obj][pos], self.c[obj[0]][pos], self.s[obj[1]][pos])])

    def sample(self, obj, rng):
        return tuple(rng.choices(range(len(ALPHABET)), self.probs(obj, p))[0] for p in range(LENGTH))

    def say(self, obj):
        return tuple(max(range(len(ALPHABET)), key=lambda k: self.probs(obj, p)[k]) for p in range(LENGTH))

    def push(self, obj, message, weight, lr):
        """Raises (or lowers, for a negative weight) the log-probability of this message."""
        for p, sym in enumerate(message):
            probs = self.probs(obj, p)
            for k in range(len(ALPHABET)):
                g = lr * weight * ((k == sym) - probs[k])
                self.h[obj][p][k] += g
                self.c[obj[0]][p][k] += g
                self.s[obj[1]][p][k] += g


class Listener:
    """Reads a whole message as a name of an object, or sign by sign; the game decides which."""

    def __init__(self, rng):
        self.h = {}
        self.c = [[[0.0 for _ in COLOURS] for _ in ALPHABET] for _ in range(LENGTH)]
        self.s = [[[0.0 for _ in SHAPES] for _ in ALPHABET] for _ in range(LENGTH)]

    def probs(self, message):
        whole = self.h.get(message) or [0.0] * len(OBJECTS)
        return _softmax([whole[k] + sum(self.c[p][sym][o[0]] + self.s[p][sym][o[1]] for p, sym in enumerate(message))
                         for k, o in enumerate(OBJECTS)])

    def guess(self, message):
        probs = self.probs(message)
        return OBJECTS[max(range(len(OBJECTS)), key=probs.__getitem__)]

    def learn(self, message, obj, lr):
        probs = self.probs(message)
        whole = self.h.setdefault(message, [0.0] * len(OBJECTS))
        for k, o in enumerate(OBJECTS):
            err = lr * ((o == obj) - probs[k])
            whole[k] += err
            for p, sym in enumerate(message):
                self.c[p][sym][o[0]] += err
                self.s[p][sym][o[1]] += err


def play(speaker, listener, rng, games=3000, lr=0.5):
    baseline = 0.0
    for _ in range(games):
        obj = rng.choice(OBJECTS)
        message = speaker.sample(obj, rng)
        reward = float(listener.guess(message) == obj)
        speaker.push(obj, message, reward - baseline, lr)
        listener.learn(message, obj, lr)
        baseline += 0.05 * (reward - baseline)


def accuracy(speaker, listener, objects=OBJECTS):
    return sum(listener.guess(speaker.say(o)) == o for o in objects) / len(objects)


def _ranks(xs):
    order = sorted(range(len(xs)), key=xs.__getitem__)
    ranks = [0.0] * len(xs)
    k = 0
    while k < len(order):
        j = k
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[k]]:
            j += 1
        for i in range(k, j + 1):
            ranks[order[i]] = (k + j) / 2
        k = j + 1
    return ranks


def spearman(a, b):
    ra, rb = _ranks(a), _ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va, vb = sum((x - ma) ** 2 for x in ra), sum((y - mb) ** 2 for y in rb)
    return cov / math.sqrt(va * vb) if va and vb else 0.0


def topsim(language):
    """Rank correlation of object distance and message distance (1 = fully compositional)."""
    meaning, form = [], []
    for i, a in enumerate(OBJECTS):
        for b in OBJECTS[i + 1:]:
            meaning.append((a[0] != b[0]) + (a[1] != b[1]))
            form.append(sum(x != y for x, y in zip(language[a], language[b])))
    return round(spearman(meaning, form), 3)


def language_of(speaker):
    return {o: speaker.say(o) for o in OBJECTS}


def word(message):
    return "".join(ALPHABET[k] for k in message)


def generation(previous, rng, games=3000):
    """A new speaker learns from a bottleneck of the old language, then plays with a new listener.
    Returns the new speaker, listener and how well it named objects it never saw."""
    speaker, listener = Speaker(rng), Listener(rng)
    seen = rng.sample(OBJECTS, BOTTLENECK) if previous else []
    for _ in range(300 if previous else 0):
        for obj in seen:
            speaker.push(obj, previous[obj], 1.0, 0.3)
    unseen = [o for o in OBJECTS if o not in seen]
    inherited = (sum(speaker.say(o) == previous[o] for o in unseen) / len(unseen)) if previous else None
    play(speaker, listener, rng, games)
    return speaker, listener, inherited


def evolve(start=None, generations=4, seed=0, games=3000):
    """Several generations from a stored language (or from nothing). Each row is one generation."""
    rng = random.Random(seed)
    previous, rows = start, []
    for g in range(generations):
        speaker, listener, inherited = generation(previous, rng, games)
        previous = language_of(speaker)
        rows.append({"accuracy": round(accuracy(speaker, listener), 3), "topsim": topsim(previous),
                     "inherited": None if inherited is None else round(inherited, 3),
                     "words": len(set(previous.values()))})
    return previous, rows


# ---- memory between nights -----------------------------------------------

def _path():
    from backend import training_center as tc
    return tc.folder() / "emergent.json"


def load():
    from backend import training_center as tc
    data = tc._read(_path(), {}) or {}
    if data.get("language"):
        data["language"] = {tuple(json_key): tuple(msg) for json_key, msg in data["language"]}
    return data


def save(language, rows, made):
    from backend import training_center as tc
    data = tc._read(_path(), {}) or {}
    data["language"] = [[list(o), list(m)] for o, m in language.items()]
    data["generation"] = data.get("generation", 0) + len(rows)
    data["history"] = (data.get("history", []) + [dict(r, at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())) for r in rows])[-30:]
    data["last"] = made
    tc._write(_path(), data)
    return data


# ---- grounding in Russian --------------------------------------------------

ASK = ("В нашей игре знаков сигнал «%s». Что он значит?", "Что значит сигнал «%s» в игре знаков?",
       "Тебе подали сигнал «%s». Какой это предмет?")
SAY = ("Как в игре знаков сказать «%s»?", "Какой сигнал в игре знаков значит «%s»?")


def asked_only(seed=0):
    return random.Random(800_000 + seed).sample(OBJECTS, ASKED_ONLY)


def measure(loaded, language, objects):
    from backend import logic
    from backend.brain import generate
    model, state = loaded
    right = 0
    for obj in objects:
        text = generate(model, state, ASK[0] % word(language[obj]), 32)["text"]
        right += logic.answer_of(text) == name(obj)
    return right


def lessons(loaded, seed=0, generations=4):
    data = load()
    language, rows = evolve(data.get("language"), generations, seed)
    held = asked_only(data.get("generation", 0) // 10)
    made = {"generation": data.get("generation", 0) + generations, "accuracy": rows[-1]["accuracy"],
            "topsim": rows[-1]["topsim"], "topsim_start": rows[0]["topsim"], "inherited": rows[-1]["inherited"],
            "unseen_right": measure(loaded, language, held), "unseen": len(held)}
    pairs = []
    for obj in OBJECTS:
        if obj in held:
            continue
        signal = word(language[obj])
        for ask in ASK:
            pairs.append((ask % signal, "Ответ: %s." % name(obj)))
        for say in SAY:
            pairs.append((say % name(obj), "Сигнал «%s». Ответ: %s." % (signal, signal)))
    made["lessons"] = len(pairs)
    save(language, rows, made)
    return pairs, made


def status():
    data = load()
    language = data.get("language") or {}
    return {"generation": data.get("generation", 0), "history": data.get("history", [])[-8:], "last": data.get("last"),
            "words": [{"object": name(o), "signal": word(m)} for o, m in sorted(language.items())]}
