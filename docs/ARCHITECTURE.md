# Yorika architecture — foundation

## Scope
A deliberately empty web UI and browser-native application core. `Yorika.bat` and the existing Windows tray process remain untouched.

## Core
- `www/core/app.js`: lifecycle state (`new -> starting -> ready / failed -> stopped`), database, event bus.
- `www/core/events.js`: scoped subscribe/unsubscribe/emit.
- `www/core/database.js`: versioned IndexedDB storage with get/all/put/delete/clear APIs.
- `www/main.js`: initializes the core and leaves the UI empty.
- `www/index.html` / `www/styles.css`: neutral shell.

## Storage
Database: `yorika`, schema version 1.
Empty stores: `settings`, `projects`, `memories`, `conversations`, `messages`, `tasks`.
Every record uses a nonempty string `id`. There is intentionally no seed content.
Data is stored **in the browser profile for the site's local origin**. It is not a server-side SQLite database; clearing browser site data removes it. As the free port changes, the browser sees a *different origin*, so IndexedDB data **will not automatically persist across launches using different ports**.

## Next engineering requirement
Before storing important user data, implement a durable stable-origin strategy or a local backend datastore, database migrations, export/import and backup. Do not treat the current IndexedDB as reliable long-term memory with randomized ports.

## Not implemented
AI model connectivity, agent orchestration, memory retrieval, sync, backups, account auth and visualization.
