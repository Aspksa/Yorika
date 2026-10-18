# Yorika

Yorika starts directly from **Yorika.bat**. There is no separate launcher window or launcher UI.

## Start on Windows

1. Download or clone the repository.
2. Double-click `Yorika.bat`.
3. The local website opens automatically in the default browser.
4. Yorika runs silently in the Windows notification area (near the clock, possibly under **^**).
5. Double-click its tray icon to open the website again. Right-click > **Exit Yorika** to stop it.

A small background PowerShell process is necessary to keep the site available and manage the tray icon after the BAT exits. It is **not** a separate launcher interface.

The site is served locally at `127.0.0.1` using a port allocated automatically by Windows. No fixed port is assumed. HTML is UTF-8 and supports Cyrillic. No Python, Node.js, pip, administrator rights, or package installation are required for this starter page.

Source files:
- `Yorika.bat` — entry point.
- `scripts/yorika-tray.ps1` — background tray process and static HTTP server.
- `www/index.html` — starter website.

Logs: `.yorika/launcher.log` (legacy filename; hidden support logging only).

Current limitations: static starter website only; no AI API or backend. Windows runtime behavior has not yet been tested on a real Windows computer.
