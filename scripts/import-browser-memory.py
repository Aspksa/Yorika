#!/usr/bin/env python3
"""Import an explicitly exported browser-memory JSON snapshot into Yorika SQLite.

Does not delete browser data, does not overwrite different snapshots accidentally,
and does not modify the running PowerShell web site.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.storage import Store  # noqa: E402

STORES = {"settings", "projects", "memories", "conversations", "messages", "tasks"}
KEYS = {"yorika.chat", "yorika.avatar", "yorika.avatars"}
MAX_BYTES = 50 * 1024 * 1024

def import_file(path: Path, directory: Path | None = None) -> tuple[int, int]:
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Export exceeds 50 MiB; split or review it manually")
    raw = path.read_bytes()
    snapshot = json.loads(raw.decode("utf-8-sig"))
    if snapshot.get("format") != "yorika-browser-export" or snapshot.get("schema_version") != 1:
        raise ValueError("Unsupported Yorika browser export format")
    origin = snapshot.get("origin")
    if not isinstance(origin, str) or not (origin.startswith("http://127.0.0.1:") or origin.startswith("http://localhost:")):
        raise ValueError("Export origin is not a local Yorika address")
    stores = snapshot.get("indexeddb")
    local = snapshot.get("localstorage")
    if not isinstance(stores, dict) or not isinstance(local, dict):
        raise ValueError("Invalid export structure")
    if set(stores) - STORES or set(local) - KEYS:
        raise ValueError("Unknown store or localStorage key")
    export_sha = hashlib.sha256(raw).hexdigest()
    origin_tag = hashlib.sha256(origin.encode("utf-8")).hexdigest()[:20]
    count = 0
    with Store(directory) as db:
        if db.get("browser-imports", export_sha):
            return (0, 1)
        for store, records in stores.items():
            if not isinstance(records, list):
                raise ValueError("Invalid IndexedDB store")
            for idx, item in enumerate(records):
                if not isinstance(item, dict):
                    raise ValueError("Invalid IndexedDB record")
                key = item.get("id")
                if not isinstance(key, str) or not key.strip():
                    raise ValueError("Missing record ID")
                db.put("browser/" + origin_tag + "/" + store, key, {"origin": origin, "record": item})
                count += 1
        for key, value in local.items():
            if not isinstance(value, str):
                raise ValueError("Invalid localStorage value")
            db.put("browser/" + origin_tag + "/localstorage", key, {"origin": origin, "value": value})
            count += 1
        db.put("browser-imports", export_sha, {"origin": origin, "source_filename": path.name, "sha256": export_sha, "records": count})
    return (count, 0)

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_export", type=Path)
    parser.add_argument("--data-dir", type=Path, default=None, help="Override isolated SQLite target directory")
    args = parser.parse_args()
    inserted, skipped = import_file(args.json_export, args.data_dir)
    print(f"Imported {inserted} records; duplicate snapshots skipped: {skipped}. Originals untouched.")

if __name__ == "__main__":
    main()
