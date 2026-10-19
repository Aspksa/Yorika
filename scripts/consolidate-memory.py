#!/usr/bin/env python3
"""Preview exact duplicate memories; apply only with explicit acknowledgement.

Default output contains IDs/counts only, never private memory text.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.storage import Store


def main(argv=None):
    parser = argparse.ArgumentParser(description="Yorika memory consolidation, preview by default")
    parser.add_argument("--directory", type=Path, help="Optional Yorika data directory")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--apply", action="store_true", help="Delete exact duplicates")
    parser.add_argument("--confirm", action="store_true", help="Confirm destructive action")
    args = parser.parse_args(argv)
    if args.apply != args.confirm:
        parser.error("--apply and --confirm must be supplied together")
    with Store(args.directory) as store:
        report = store.consolidate_memories(dry_run=not args.apply, limit=args.limit)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
