"""How Yorika's own model answers: generation, thinking before answering, and the chat engine.

think() is the "обдумывание": several drafts, each checked (arithmetic claims and day-of-week steps
are recomputed, tool calls are run, facts written as «Факты: …» go to the logic engine, whose
answer wins over a guess), and the most confident correct-looking one wins. A model trained with
loops thinks longer on hard questions: when the first word is uncertain it runs every pass.
"""
import re

from backend.neural_bpe_v1 import OFFSET, SPECIAL, encode

CLAIM = re.compile(r"(-?\d+(?:[.,]\d+)?)\s*([+\-*/×÷])\s*(-?\d+(?:[.,]\d+)?)\s*=\s*(-?\d+(?:[.,]\d+)?)")
HARD_ENTROPY = 2.0


def _decode(tokens, tokenizer):
    pieces = [bytes([i]) for i in range(256)]
    for left, right in tokenizer["merges"]:
        pieces.append(pieces[left - OFFSET] + pieces[right - OFFSET])
    return b"".join(pieces[t - OFFSET] for t in tokens).decode("utf-8", errors="replace")


def _forward(model, ids, passes):
    import torch
    x = torch.tensor([ids], dtype=torch.long)
    return model(x, passes=passes) if passes and getattr(model, "passes", 1) > 1 else model(x)


def loops_of(state):
    return (state.get("arch") or {}).get("loops", 1)


def generate(model, state, prompt, max_tokens=64, *, temperature=0.0, passes=None, generator=None):
    """One answer; returns its text and the mean log-probability of its tokens (confidence)."""
    import torch
    tokenizer, context = state["tokenizer"], state["config"][3]
    ids = [1, 3] + encode(prompt, tokenizer) + [4]
    out, logprob = [], 0.0
    with torch.inference_mode():
        for _ in range(max_tokens):
            logits = _forward(model, ids[-context:], passes)[0, -1].float()
            probs = torch.softmax(logits / temperature if temperature else logits, -1)
            token = int(torch.multinomial(probs, 1, generator=generator)) if temperature else int(probs.argmax())
            logprob += float(torch.log_softmax(logits, -1)[token])
            if token == 2:
                break
            ids.append(token)
            if token >= len(SPECIAL):
                out.append(token)
    count = max(1, len(out))
    return {"text": _decode(out, tokenizer), "confidence": logprob / count, "tokens": len(out)}


def difficulty(model, state, prompt):
    """Entropy of the first answer token after one pass: high means the model is unsure."""
    import torch
    ids = ([1, 3] + encode(prompt, state["tokenizer"]) + [4])[-state["config"][3]:]
    with torch.inference_mode():
        logits = _forward(model, ids, 1)[0, -1].float()
    p = torch.softmax(logits, -1)
    return float(-(p * torch.log(p.clamp_min(1e-12))).sum())


def wrong_claims(text):
    """Arithmetic the draft states ("7 + 5 = 13") that the calculator disagrees with."""
    from backend.tools import calc
    bad = 0
    for a, op, b, result in CLAIM.findall(text or ""):
        try:
            if calc("%s%s%s" % (a, op, b)).replace(",", ".") != result.replace(",", "."):
                bad += 1
        except ValueError:
            bad += 1
    return bad


def think(model, state, prompt, *, drafts=3, max_tokens=96, seed=0):
    """Draft several answers, check each, keep the best. Returns the answer and how it was chosen."""
    import torch
    from backend.tools import run_tools
    loops = loops_of(state)
    from backend import latent, solver
    # A silent question («Подумай про себя») always gets every pass: the steps happen inside.
    hard = latent.SILENT in prompt or difficulty(model, state, prompt) > HARD_ENTROPY
    passes = loops if hard else 1
    rng = torch.Generator().manual_seed(seed)
    candidates = []
    for k in range(max(1, drafts)):
        draft = generate(model, state, prompt, max_tokens, temperature=0 if k == 0 else 0.7,
                         passes=passes, generator=rng)
        try:
            text, calls = run_tools(draft["text"])
        except Exception:  # noqa: BLE001 - a broken tool must not hide the draft
            text, calls = draft["text"], []
        text, checked = solver.apply(text)
        errors = wrong_claims(text) + solver.wrong_steps(text)
        # Confidence decides between drafts; a false step costs more than any confidence, and an
        # answer the logic engine derived from her own facts is worth more than a guess.
        score = draft["confidence"] - 5.0 * errors - (3.0 if not text.strip() else 0.0) + (2.0 if checked else 0.0)
        candidates.append({"text": text, "score": score, "errors": errors, "tools": calls, "solver": checked})
    best = max(candidates, key=lambda c: c["score"])
    return {"answer": best["text"], "drafts": len(candidates), "passes": passes, "hard": hard,
            "fixed": best is not candidates[0], "errors": best["errors"], "tools": best["tools"], "solver": best["solver"],
            "texts": [c["text"] for c in candidates]}


# ---- loading: full checkpoints and 4-bit compressed copies ----------------

def load(path):
    from pathlib import Path
    path = Path(path)
    if path.name.endswith(".q4.pt"):
        from backend.quantize import load_quantized
        return load_quantized(path)
    from backend.neural_language_benchmark import load_candidate
    return load_candidate(path)


# ---- chat engine: Cloud.ru or Yorika's own active model -------------------

def engine():
    from backend import training_center as tc
    saved = tc._read(tc.folder() / "chat-engine.json", {}) or {}
    return {"engine": saved.get("engine") if saved.get("engine") in ("cloud", "own") else "cloud",
            "drafts": saved.get("drafts") if saved.get("drafts") in (1, 3, 5) else 3,
            "compressed": saved.get("compressed") is True}


def set_engine(name, drafts=3, compressed=False):
    from backend import training_center as tc
    if name not in ("cloud", "own") or drafts not in (1, 3, 5) or not isinstance(compressed, bool):
        raise ValueError("Выберите Cloud.ru или свою модель; черновиков 1, 3 или 5")
    if name == "own" and not tc.active():
        raise ValueError("Сначала сделайте активной одну из версий")
    tc._write(tc.folder() / "chat-engine.json", {"engine": name, "drafts": drafts, "compressed": compressed})
    return engine()


def chat(query, conversation_id=None):
    """Answer in chat with the active version. Never falls back to another model silently."""
    from backend import training_center as tc
    current = tc.active()
    if not current or not current.get("checkpoint"):
        raise RuntimeError("Своя модель выбрана для чата, но активной версии нет")
    settings = engine()
    path = tc.folder() / current["checkpoint"]
    small = path.with_name(path.name[:-3] + ".q4.pt")
    loaded = load(small if settings["compressed"] and small.is_file() else path)
    drafts, sure = settings["drafts"], None
    try:
        # Knowing her limits: a question she is sure about gets one draft, a hard one five.
        from backend import metacog
        first = generate(loaded[0], loaded[1], query[:2000], 24)
        sure = metacog.sure(loaded[0], loaded[1], query[:2000], first["confidence"], current.get("run"))
        drafts = metacog.drafts_for(sure, drafts)
    except Exception:  # noqa: BLE001 - without self-knowledge the owner's setting stays
        pass
    result = dict(think(*loaded, query[:2000], drafts=drafts), sure=sure)
    if not result["answer"].strip():
        raise RuntimeError("Своя модель не смогла ответить: пустой ответ")
    try:
        # Same history as Cloud.ru answers, so experience collection and context see this turn too.
        from backend.cloud_ru_history import save_turn
        from backend.storage import Store
        with Store() as db:
            save_turn(db, query, result["answer"], conversation_id)
    except Exception:  # noqa: BLE001 - the answer matters more than its history entry
        pass
    return dict(result, engine="yorika-own", run=current.get("run"))


def own_engine_selected():
    try:
        return engine()["engine"] == "own"
    except Exception:  # noqa: BLE001 - a broken setting means the default engine
        return False


def chat_error(error):
    """Own-model errors shown in chat; they are ours and contain no provider data."""
    if isinstance(error, ImportError):
        return "Своя модель: не установлен PyTorch (вкладка «Обучение»)"
    text = str(error)
    return text[:200] if re.search("[а-яА-Я]", text) else "Своя модель не смогла ответить"
