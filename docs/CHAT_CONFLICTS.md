# Chat history concurrency (revision compare-and-swap)

Each server history snapshot has integer `revision`, initially 0. GET `/api/chat/history` returns `{history, revision}`. POST accepts `{history, revision}` and writes only when the revision matches SQLite within a `BEGIN IMMEDIATE` transaction; success `{ok: true, revision: new_revision}`. On conflict it returns `{conflict:true, revision, history}`, **without writing anything**.

Browser retries up to three times, merging distinct existing messages identified by `from + text + timestamp`. Incoming changes in the current browser origin are kept. If an attempt is stale, it cannot silently replace newer SQLite history. An intentional clear that sees a conflicting write does **not** erase new remote messages; it warns about the conflict. Older clients that still POST raw arrays are rejected rather than overwriting newer records.

Limits: same-content messages with exactly equal millisecond timestamps are not globally unique; future message UUIDs are needed. Simultaneous clear/new message, origin migration, process crashes and browser storage fallbacks require real Windows end-to-end and stress testing. No claim that MEMORY-004 or DATA-001 is complete. Legacy browser origins still need independent export.

Run tests with `python -m unittest discover -s tests -v`; JS syntax with `node --check www/avatar.js`. CI runs on Ubuntu and Windows and checks PowerShell syntax, but passing CI is not equal to a physical Windows laptop test.
