# Yorika

Yorika starts directly from **Yorika.bat**. There is no separate launcher window or launcher UI.

## Start on Windows

1. Download or clone the repository.
2. Double-click `Yorika.bat`.
3. The local website opens automatically in the default browser.
4. Yorika runs silently in the Windows notification area (near the clock, possibly under **^**).
5. Double-click the tray icon to reopen the site. Right-click to open the site, copy its address, view status, read diagnostics, or exit.

A small background PowerShell process is necessary to keep the site available and manage the tray icon after the BAT exits. It is **not** a separate launcher interface.

The site is served locally at `127.0.0.1` using a port allocated automatically by Windows. No fixed port is assumed. HTML is UTF-8 and supports Cyrillic. No Python, Node.js, pip, administrator rights, or package installation are required for this starter page.

Source files:
- `Yorika.bat` — entry point.
- `scripts/yorika-tray.ps1` — background tray process and static HTTP server.
- `www/index.html` — starter website.

Logs: `.yorika/yorika.log` (hidden support logging only).

Current limitations: static starter website only; no AI API or backend. Windows runtime behavior has not yet been tested on a real Windows computer.

## Current reliability features

- Automatic free TCP port selection with localhost-only binding.
- Mutex to prevent duplicate running instances.
- Windows tray operation with log and status menu actions.
- UTF-8 for site and diagnostic log; no Python dependency.
- No separate launcher user interface.

Planned but not yet implemented: automatic process recovery, backups, updates/rollback, and live API backend.

## 60-scenario verification

For development, the 60-scenario checks remain in `scripts/verify-60.ps1`. The extra `Yorika-Verify.bat` and `Yorika-Debug.bat` have been removed from the project.

**Current limitations:** This update is not a guarantee of fault-free operation. In particular, the browser IndexedDB is per port and is not durable memory across random-port launches; backing up and restoring data is future work.

## Русский интерфейс трея

Меню значка возле часов: «Открыть Yorika», «Локальный адрес», «Скопировать адрес сайта», «Состояние системы», «Открыть журнал ошибок», «Выйти из Yorika». Основной запуск остаётся через `Yorika.bat`. Вспомогательные BAT диагностики удалены; журнал `.yorika/yorika.log` сохранён. Для проверки перевода перезапустите Yorika через пункт «Выйти из Yorika» и откройте обновлённую версию.

## Обновление проекта

На пустой веб-странице внизу слева появилось меню ☰ → **Обновление**. Каналы «Свежий» и «Стабильный», автопроверка во время работы страницы, локальный DPAPI-токен, ручное скачивание и подготовка ZIP во временной папке. Автоматическая установка ещё не включена. Подробности: [docs/UPDATES.md](docs/UPDATES.md).
