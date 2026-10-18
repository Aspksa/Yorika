#!/usr/bin/env python3
"""Validate machine-readable tasks and checked Markdown statuses (stdlib only)."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / "planning" / "tasks.json").read_text(encoding="utf-8"))
roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
statuses = set(data["status_values"])
tasks = data["tasks"]
ids = [t["id"] for t in tasks]
assert len(set(ids)) == len(ids), "Duplicate task IDs"
assert ids, "Empty task registry"
for task in tasks:
    assert task["status"] in statuses, task["id"]
    assert isinstance(task.get("evidence"), list), task["id"]
    assert all(dep in ids and dep != task["id"] for dep in task["depends_on"]), task["id"]
    if task["status"] == "done":
        assert task["evidence"], "Done without evidence: " + task["id"]
    matches = re.findall(r"^- \[([ x])\] " + re.escape(task["id"]) + r"\b", roadmap, re.MULTILINE)
    assert len(matches) == 1, "Missing/duplicate roadmap line: " + task["id"]
    assert (matches[0] == "x") == (task["status"] == "done"), "Checkbox/status mismatch: " + task["id"]

def visit(node, stack, visited):
    if node in stack:
        raise AssertionError("Dependency cycle: " + " -> ".join(stack + [node]))
    if node in visited:
        return
    stack.append(node)
    for dep in next(t for t in tasks if t["id"] == node)["depends_on"]:
        visit(dep, stack, visited)
    stack.pop()
    visited.add(node)

seen = set()
for task_id in ids:
    visit(task_id, [], seen)
print(f"OK: {len(tasks)} tasks, unique IDs, checklist, evidence and DAG dependencies")
