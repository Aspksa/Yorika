"""Backup and restore the entire Yorika SQLite store, including learned personality."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.sqlite_backup import create_verified_backup, verify_snapshot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("backup", "verify", "restore"))
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", nargs="?", type=Path)
    args = parser.parse_args()
    if args.action in ("backup", "restore"):
        if args.destination is None:
            parser.error("destination is required for backup")
        # Restore only to a new destination, never over a running/live SQLite file.
        # A separate verified copy allows the operator to switch databases offline.
        print(create_verified_backup(args.source, args.destination))
    else:
        print(verify_snapshot(args.source))


if __name__ == "__main__":
    main()
