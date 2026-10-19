#!/usr/bin/env python3
"""Conservative git-tracked secret filename check; no secret values are printed."""
from pathlib import PurePosixPath
import subprocess
import sys

BLOCKED = {".env", ".credentials", "id_rsa", "id_ed25519", ".netrc"}
SUFFIXES = (".pfx", ".p12", ".pem", ".key", ".dpapi", ".sqlite3", ".sqlite", ".db")


def flagged(name):
    path = PurePosixPath(name)
    return any(part.lower() in BLOCKED or part.lower().startswith(".env.") for part in path.parts) or path.suffix.lower() in SUFFIXES


def main():
    try:
        listing = subprocess.run(["git", "ls-files", "-z"], stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        print("ОШИБКА: список отслеживаемых файлов Git недоступен")
        return 1
    bad = [n for n in listing.decode("utf-8", "surrogateescape").split("\0") if n and flagged(n)]
    if bad:
        print("ОШИБКА: найдены файлы с потенциальными секретами в Git (значения не выводятся):")
        for item in bad:
            print("  " + item)
        return 1
    print("УСПЕШНО: имена отслеживаемых файлов проверены; содержимое на секреты не сканировалось.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
