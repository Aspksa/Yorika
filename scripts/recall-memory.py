#!/usr/bin/env python3
"""Read-only recall of explicit SQLite memories for Yorika's local chat."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.storage import Store


def recall(query: str, directory=None, limit: int = 3) -> dict:
    if not isinstance(query, str) or not query.strip() or len(query) > 4000:
        raise ValueError("Invalid recall query")
    with Store(directory) as db:
        try:
            found = db.search_records_fts("memories", query, limit)
        except RuntimeError as exc:
            if "FTS5" not in str(exc):
                raise
            found = db.search_records("memories", query, limit)
    return {
        "memories": [
            {"record_id": row["record_id"], "text": row["value"].get("text"),
             "source": row["value"].get("source", "unknown"),
             "source_id": row["value"].get("source_id", "")}
            for row in found if isinstance(row["value"].get("text"), str)
        ],
        "generated": False,
    }


if __name__ == "__main__":
    try:
        query = sys.stdin.read(4097)
        if len(query) > 4000:
            raise ValueError("Query too long")
        print(json.dumps(recall(query), ensure_ascii=False))
    except (ValueError, OSError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        sys.exit(1)
