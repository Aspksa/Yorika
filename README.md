# Yorika

Windows launcher and starter website for Yorika.

## Start

1. Download or clone the repository.
2. Double-click **Yorika.bat**.
3. Your default browser opens the Yorika page automatically.
4. Find the Yorika icon in the Windows notification area (near the clock; check the **^** menu).
5. Double-click the icon to reopen the page, or right-click and choose **Exit Yorika** to stop the server.

**Requirements:** Windows 10/11 with Windows PowerShell 5.1 and .NET Framework WinForms (normally included). No Python, Node.js, pip, or administrator privileges are required.

## How it works

- The batch script launches a hidden PowerShell tray application, then exits.
- The launcher binds to `127.0.0.1` on **port 0**, letting Windows allocate an unused port.
- The selected port stays reserved while Yorika is running.
- The launcher serves static files from `www/` and opens the actual URL in the browser.
- UTF-8 HTML supports Cyrillic text; avoid hard-coding paths or ports.
- A process mutex prevents duplicate tray instances.
- Logs are saved in `.yorika/launcher.log` (gitignored).

## Limitations

This version hosts a **local static site only**. Python-backed AI features, APIs, application logic, updates, and packaged installers are not yet implemented. Windows execution has not yet been tested on a real machine.

If the icon is not visible, expand the Windows notification area (^) and inspect `.yorika/launcher.log` if the launcher does not start.
