#!/usr/bin/env python3
"""Русский CI-отчёт: не подменяет результаты тестов и не публикует их логи."""
import argparse
import json
import os
from pathlib import Path
import sys

NAMES = {
    "plan": "План задач",
    "chat_stress": "Нагрузка на память диалогов",
    "sqlite_restore": "Восстановление SQLite",
    "chat_regressions": "Регрессии истории диалогов",
    "python_full": "Полный набор Python-тестов",
}
LABELS = {"passed": "УСПЕШНО", "failed": "ОШИБКА", "error": "СБОЙ", "skipped": "ПРОПУЩЕНО"}
GITHUB_STATES = {"success": "passed", "failure": "failed", "cancelled": "error", "skipped": "skipped", "": "error"}
ICONS = {"passed": "✅", "failed": "❌", "error": "❌", "skipped": "⚠️"}


def build_report(report_path, *, extra=None):
    try:
        obj = json.loads(Path(report_path).read_text(encoding="utf-8"))
        results = obj["results"]
        if not isinstance(results, list) or not results:
            raise ValueError("Нет результатов проверок")
        rows = []
        for item in results:
            name, status = item["name"], item["status"]
            if status not in LABELS:
                raise ValueError("Неизвестный статус: " + str(status))
            rows.append((NAMES.get(name, name), status))
        platform = str(obj.get("platform", "не указана"))
        date = str(obj.get("executed_at_utc", "не указана"))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        rows = [("Python и SQLite", "error")]
        platform, date = "неизвестна", "неизвестно"
    for name, status in (extra or []):
        rows.append((name, status))
    success = bool(rows) and all(status == "passed" for _, status in rows)
    lines = [
        "# Отчёт Yorika — контроль качества", "",
        "**Итог: " + ("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ" if success else "❌ НЕ ГОТОВО / НЕ ВСЁ ПРОВЕРЕНО") + "**", "",
        "Платформа: " + platform + "  ",
        "Дата (UTC): " + date, "",
        "| Проверка | Результат |", "|---|---|",
    ]
    for name, status in rows:
        safe = str(name).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {safe} | {ICONS[status]} {LABELS[status]} |")
    lines += ["", "⚠️ Этот отчёт отражает **только перечисленные проверки**.",
              "Windows GUI, настоящая Cloud.ru и антивирусная проверка не считаются пройденными автоматически.",
              "Логи ошибок и секреты в отчёт не включаются.", ""]
    return "\n".join(lines), success


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="yorika-acceptance.json")
    parser.add_argument("--output", default="ОТЧЁТ_YORIKA.md")
    parser.add_argument("--require", action="append", default=[], metavar="NAME=STATE")
    args = parser.parse_args()
    extras = []
    for pair in args.require:
        if "=" not in pair:
            parser.error("--require ожидает NAME=STATE")
        name, status = pair.rsplit("=", 1)
        status = GITHUB_STATES.get(status, status)
        if status not in LABELS:
            parser.error("неизвестный статус: " + status)
        extras.append((name, status))
    report, success = build_report(args.input, extra=extras)
    Path(args.output).write_text(report, encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as dest:
            dest.write(report + "\n")
    print(report)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
