# Manual bridge: browser-origin storage → SQLite

The website has a random localhost port. Browser IndexedDB and localStorage are tied to **origin**, including the port. These tools do not automatically discover old browser profiles/ports and **do not make the live website use SQLite yet**.

1. Open the running Yorika's `http://127.0.0.1:<port>/memory-export.html`.
2. Click **Export**. File is downloaded locally; do not upload it to a public repository. This contains potentially sensitive chat history and settings.
3. Run `python scripts/import-browser-memory.py <path-to-export.json>` in the repo, or use `--data-dir` for an isolated test directory.
4. The SQLite copy is saved separately from release folders (`%LOCALAPPDATA%/Yorika/data` on Windows). Preserve the original downloaded JSON securely until inspected and backed up.
5. Browser history saved at **older ports cannot be accessed from the current origin**. Do not delete old browser profiles/caches. If an old origin can be reopened, export it individually. Don't claim full migration until all origins are accounted for.
6. Each snapshot is tracked by its SHA-256. Imports are namespaced by origin and are **archival copies**, not live chat records. Re-import of identical file is skipped. The exported `yorika.avatars` string may contain base64 user images.
7. This early importer is **not atomic across the entire multi-record snapshot**; a validation error after a subset of records may leave partial archival imports. Reimport after fixing the input is idempotent per original record ID. Full transaction import and recovery tests are still required.

Verify with `python -m unittest discover -s tests -v` on a local Python installation. No end-to-end Windows test has been conducted via this chat. Source data remains in browser; nothing is deleted.

Do not mark DATA-002 complete until tested recovery, browser-to-live-DB integration and real Windows validation exist.
