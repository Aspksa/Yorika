#!/usr/bin/env python3
"""Run Yorika's full Python and SQLite acceptance suite with an honest JSON report.

No account data is read: test cases create temporary databases themselves.
Exit status is nonzero if *any* check fails or cannot be executed.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = [
    ("plan", [sys.executable, "scripts/check-plan.py"]),
    ("chat_stress", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_chat_restore_stress.py", "-v"]),
    ("sqlite_restore", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_sqlite_restore_copy.py", "-v"]),
    ("chat_regressions", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_chat_memory_regressions.py", "-v"]),
    ("python_full", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]),
]


def execute(root=ROOT, *, runner=subprocess.run):
    results = []
    for name, command in COMMANDS:
        try:
            completed = runner(command, cwd=str(root), text=True, encoding="utf-8",
                               errors="replace", capture_output=True, timeout=240)
            results.append({"name": name, "status": "passed" if completed.returncode == 0 else "failed",
                            "returncode": completed.returncode,
                            "output": (completed.stdout + "\n" + completed.stderr)[-24000:]})
        except (OSError, subprocess.TimeoutExpired) as exc:
            results.append({"name": name, "status": "error", "returncode": None,
                            "output": type(exc).__name__})
    return {"executed_at_utc": datetime.now(timezone.utc).isoformat(),
            "platform": sys.platform,
            "results": results,
            "passed": all(item["status"] == "passed" for item in results)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=Path("yorika-acceptance.json"))
    args = parser.parse_args()
    result = execute()
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    for check in result["results"]:
        print(f'{check["name"]}: {check["status"]}')
    print("report:", args.report)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
