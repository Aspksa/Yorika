"""Conservative scene matching over the bundled 473 dialogue graphs.

Examples guide Cloud.ru style; never send scripted answers directly to users.
Only strong lexical evidence selects a branch; uncertain turns use normal inference.
"""
import json
import re
from backend.persona_profile import PACK_PATH
from backend.persona_bank import canonical
from backend.storage import utc_now

NAMESPACE = "persona_rotation"
STATE_ID = "yorika.soul.ru.dialogues.v1"
STOP = {"что", "это", "меня", "тебя", "хочу", "мне", "для", "как", "очень",
        "мой", "моя", "моё", "моем", "хозяин", "давай", "можно", "просто"}


def tokens(text):
    return {word for word in re.findall(r"[а-яa-z0-9]+", canonical(text))
            if len(word) >= 4 and word not in STOP}


def similarity(query, example):
    wanted, pattern = tokens(query), tokens(example)
    if len(pattern) < 2 or not wanted:
        return 0.0
    return len(wanted & pattern) / len(pattern)


def _answer_node(graph, user_node):
    follow = user_node.get("next", {}).get("default")
    node = graph.get(follow)
    return node if node and node.get("role") == "assistant" else None


def _allowed(scenario, context):
    if scenario.get("adult_romantic_context_required") and not (
        context.get("adult_context") is True and context.get("romance_enabled") is True
    ):
        return False
    if scenario.get("scene_required") and context.get("scene_enabled") is not True:
        return False
    if context.get("distressed") is True and scenario.get("adult_romantic_context_required"):
        return False
    return True


def choose_scenario(store, query, *, context=None, pack_path=None):
    """Return example text only on strong match, with atomic scenario history."""
    context = context or {}
    with open(pack_path or PACK_PATH, encoding="utf-8") as source:
        extension = json.load(source).get("dialogue_extension", {})
    scenarios = extension.get("scenarios", [])
    if len(scenarios) != 473:
        raise ValueError("Incomplete Yorika dialogue extension")
    db = store.connection
    if db.in_transaction:
        raise RuntimeError("Dialogue selection requires an independent transaction")
    db.execute("BEGIN IMMEDIATE")
    try:
        row = db.execute("SELECT payload FROM records WHERE namespace=? AND record_id=?",
                         (NAMESPACE, STATE_ID)).fetchone()
        state = json.loads(row[0]) if row else {"seen": [], "active": None}
        previous = state.get("active")
        choice = None
        if previous:
            scenario = next((s for s in scenarios if s["id"] == previous["id"]), None)
            if scenario and _allowed(scenario, context):
                graph = {n["id"]: n for n in scenario["nodes"]}
                active_node = graph.get(previous["node"])
                if active_node and active_node.get("role") == "assistant":
                    options = []
                    for follow in active_node.get("next", {}).values():
                        node = graph.get(follow)
                        if node and node.get("role") == "user":
                            score = similarity(query, node.get("text", ""))
                            if score >= 0.6:
                                options.append((score, node))
                    if options:
                        options.sort(key=lambda item: -item[0])
                        node = _answer_node(graph, options[0][1])
                        if node:
                            choice = (scenario, node)
        if choice is None:
            for scenario in scenarios:
                if scenario["id"] in state["seen"]:
                    continue
                if not _allowed(scenario, context):
                    continue
                graph = {n["id"]: n for n in scenario["nodes"]}
                entry = graph.get(scenario.get("entry_node"))
                if entry and entry.get("role") == "user":
                    if similarity(query, entry.get("text", "")) >= 0.8:
                        node = _answer_node(graph, entry)
                        if node:
                            choice = (scenario, node)
                            break
        if not choice:
            db.rollback()
            return None
        scenario, node = choice
        if scenario["id"] not in state["seen"]:
            state["seen"].append(scenario["id"])
        state["active"] = {"id": scenario["id"], "node": node["id"]} if node.get("next") else None
        db.execute("INSERT INTO records(namespace,record_id,payload,updated_at) "
                   "VALUES(?,?,?,?) ON CONFLICT(namespace,record_id) DO UPDATE SET "
                   "payload=excluded.payload,updated_at=excluded.updated_at",
                   (NAMESPACE, STATE_ID, json.dumps(state, ensure_ascii=False), utc_now()))
        db.commit()
        return {"scenario_id": scenario["id"], "text": node["text"]}
    except BaseException:
        db.rollback()
        raise
