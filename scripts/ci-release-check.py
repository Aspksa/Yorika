#!/usr/bin/env python3
"""Safe release readiness check: build manifest, never auto-publish or run code."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ["ЦЕНТР_YORIKA/ЦЕНТР_YORIKA.bat", "ЦЕНТР_YORIKA/center.ps1",
            "scripts/run-acceptance.py", "scripts/ci-report-ru.py",
            "www/avatar.js", "docs/ROADMAP.md", "planning/tasks.json"]
EXCLUDED = {".git", ".yorika", "__pycache__", "node_modules", "python312-runtime", ".venv"}
SECRET_NAMES = {".env", ".credentials", "id_rsa", "id_ed25519"}


def eligible(path):
    parts = path.parts
    if any(part in EXCLUDED for part in parts) or ".git" in parts:
        return False
    if any(part in SECRET_NAMES or part.startswith(".env.") for part in parts):
        return False
    if path.suffix in (".pyc", ".db", ".sqlite", ".sqlite3", ".dpapi"):
        return False
    if path.name.startswith("python-") and path.name.endswith("-embed-amd64.zip"):
        return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="yorika-acceptance.json")
    parser.add_argument("--out", default="dist")
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()
    missing = [p for p in REQUIRED if not (ROOT / p).is_file()]
    try:
        checks = json.loads(Path(args.report).read_text(encoding="utf-8"))
        accepted = bool(checks["passed"]) and bool(checks["results"]) and all(
            x.get("status") == "passed" for x in checks["results"])
    except (OSError, ValueError, KeyError, TypeError):
        accepted = False
    if missing or not accepted:
        print("НЕ ГОТОВО: " + (", ".join(missing) if missing else "приёмочные тесты не пройдены или отчёт отсутствует"))
        return 1
    if not args.build:
        print("ГОТОВО К ПОДГОТОВКЕ АРХИВА: обязательные файлы и Python-тесты присутствуют.")
        print("Проверки Windows GUI, Cloud.ru и антивируса требуют отдельного подтверждения.")
        return 0
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    try:
        tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    except (OSError, subprocess.CalledProcessError):
        print("НЕ ГОТОВО: для сборки необходим проверенный Git checkout")
        return 1
    paths = sorted(ROOT / name for name in tracked.decode("utf-8", "surrogateescape").split("\0")
                   if name and eligible(Path(name)) and (ROOT / name).is_file()
                   and not (ROOT / name).is_symlink())
    archive = out / "Yorika-source-checked.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            zf.write(p, p.relative_to(ROOT).as_posix())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (out / "Yorika-source-checked.zip.sha256").write_text(
        digest + "  " + archive.name + "\n", encoding="ascii")
    print("Архив подготовлен, НЕ опубликован:", archive)
    print("SHA-256:", digest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
