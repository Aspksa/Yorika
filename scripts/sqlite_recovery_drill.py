"""Non-destructive SQLite recovery drill: verify and restore a backup in a temp folder."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.sqlite_restore_preview import preview
from scripts.sqlite_restore_copy import restore_copy


def recovery_drill(backup: Path, sha256: str) -> dict:
    """Exercise the real restore-copy code without touching the live database."""
    source = Path(backup).expanduser().resolve(strict=True)
    initial = preview(source, sha256)
    original_digest = initial["sha256"]
    with tempfile.TemporaryDirectory(prefix="yorika-recovery-drill-") as folder:
        destination = Path(folder) / "yorika.sqlite3"
        restored = restore_copy(source, destination, initial["sha256"])
        # Snapshot bytes must be identical; restore_copy verifies this too.
        if restored["sha256"] != initial["sha256"]:
            raise ValueError("Recovery drill: restored snapshot hash mismatch")
        if restored["counts"] != initial["counts"]:
            raise ValueError("Recovery drill: restored row counts mismatch")
        result = {"passed": True, "sha256": restored["sha256"],
                  "schema_version": restored["schema_version"],
                  "counts": restored["counts"], "original_untouched": True}
    # Only report successful cleanup once TemporaryDirectory has exited.
    result["temporary_copy_removed"] = not destination.exists()
    # Recheck the original after the entire drill, not only before copying.
    final_source = preview(source, original_digest)
    result["original_untouched"] = final_source["sha256"] == original_digest
    if not result["temporary_copy_removed"]:
        raise RuntimeError("Recovery drill temporary copy was not removed")
    if not result["original_untouched"]:
        raise RuntimeError("Recovery drill original backup changed")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Exercise Yorika SQLite restoration without altering live data")
    parser.add_argument("backup", type=Path)
    parser.add_argument("--sha256", required=True, help="Expected SHA256 from backup report")
    args = parser.parse_args()
    print(json.dumps(recovery_drill(args.backup, args.sha256), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
