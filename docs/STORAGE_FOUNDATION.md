# Durable storage foundation (experimental)

`backend/storage.py` is an **isolated** prototype; not wired to the tray or web avatar. It uses Python standard-library sqlite3; no additional dependencies needed for this module.

## Location
Windows: `%LOCALAPPDATA%\\Yorika\\data\\yorika.sqlite3`. Non-Windows development fallback: `~/.local/share/Yorika/data/yorika.sqlite3`. Keep storage separate from release folders. Never commit this file. Schema version 1 is currently a generic namespaced record and append-only event journal (events have no delete API in this foundation).

## Quick checks
```powershell
python -m unittest discover -s tests -v
python scripts/check-plan.py
```

## Status / critical missing parts
- No automatic migration from IndexedDB or localStorage; browser data must be explicitly exported before any cleanup.
- No API, user authentication, encryption, scheduled backups, rotation or multi-instance locking; treat all records as locally sensitive plaintext.
- `Store.backup()` uses SQLite's online backup; restoring it must be tested on actual Windows device.
- Do not mark DATA-001 done until wired safely into running Yorika, and DATA-002/003 until migration and recovery tests pass.
