# Experimental local chat SQLite integration

The new `/api/chat/history` endpoint is served on the existing PowerShell localhost port; Python stdlib is an **optional** dependency. A missing Python installation leaves the website usable with its previous per-origin localStorage behavior and a visible "браузерная память" label.

On a new origin the avatar requests SQLite history from `GET /api/chat/history`. If no SQLite record exists, it uploads the *current origin's* localStorage conversation once. On success the SQLite snapshot becomes authoritative. Sending and clearing messages persist full snapshots through `POST /api/chat/history`; on backend errors the interface retains its browser copy and reports browser-only persistence.

There is no AI model yet; this only persists the existing chat history. Old browser port origins still require separate export/import and are not automatically recoverable.

Security: exact Host and Origin checks, no cross-origin POST, JSON content type, 256 KiB body cap, localhost-only listener, process isolation using Python (no shell interpolation of user text). This is a prototype, not a complete local API authentication or multi-tab conflict-resolution design. Sensitive data is currently stored unencrypted in SQLite. Never delete old browser profiles without backups.

Windows runtime test required: launch using Yorika.bat with Python present, send Unicode and restart on different port, verify saved conversation reappears; then test missing Python fallback, race/cross-origin requests and updater compatibility. Do not close DATA-001/CHAT-001 until these tests and full integration are verified.
