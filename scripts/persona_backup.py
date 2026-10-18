"""Backup and restore the entire Yorika SQLite store, including learned personality."""
import argparse
from pathlib import Path
from scripts.sqlite_backup import create_verified_backup, verify_snapshot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("backup", "verify"))
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", nargs="?", type=Path)
    args = parser.parse_args()
    if args.action == "backup":
        if args.destination is None:
            parser.error("destination is required for backup")
        print(create_verified_backup(args.source, args.destination))
    else:
        print(verify_snapshot(args.source))


if __name__ == "__main__":
    main()
