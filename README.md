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

Commands:
- `Yorika.bat /status` — show the address of the running Yorika.
- `Yorika.bat /log` — open the log in Notepad.
- `Yorika.bat /rollback` — go back to the original version after an installed update.
- `Yorika.bat /help` — list the commands.

Current limitations: the updater API and experimental SQLite chat-history API exist. A separate **experimental Yorika-native PyTorch Transformer and checkpoint inference path** now exist (through PR #149), but a verified conversational-quality model is **not installed or accepted for production**. Python remains optional for the basic browser/tray interface; native neural inference requires its own Python/PyTorch environment and a selected, valid checkpoint. Windows end-to-end behavior and RTX 3050 acceptance remain unverified.

## Current reliability features

- Automatic free TCP port selection with localhost-only binding.
- Mutex to prevent duplicate running instances.
- Windows tray operation with log and status menu actions.
- UTF-8 for site and diagnostic log; no Python dependency.
- No separate launcher user interface.

Implemented in code: manual SQLite backup and browser-export utilities; these are not automatic backup/recovery. Still outstanding: process recovery, verified restore, and an actual neural AI backend.

## 60-scenario verification

For development, the 60-scenario checks remain in `scripts/verify-60.ps1`. The extra `Yorika-Verify.bat` and `Yorika-Debug.bat` have been removed from the project.

**Current limitations:** This update is not a guarantee of fault-free operation. In particular, the browser IndexedDB is per port and is not durable memory across random-port launches; manual export and SQLite backup utilities now exist, but recovery of legacy origins and complete restoration remain unfinished.

## Русский интерфейс трея

Меню значка возле часов: «Открыть Yorika», «Локальный адрес», «Скопировать адрес сайта», «Состояние системы», «Открыть журнал ошибок», «Выйти из Yorika». Основной запуск остаётся через `Yorika.bat`. Вспомогательные BAT диагностики удалены; журнал `.yorika/yorika.log` сохранён. Для проверки перевода перезапустите Yorika через пункт «Выйти из Yorika» и откройте обновлённую версию.

## Обновление проекта

На веб-странице внизу слева есть кнопка **↻ Обновления**: она открывает отдельную страницу `updates.html` (не боковую панель). Каналы «Свежий» и «Стабильный», автопроверка во время работы страницы, локальный DPAPI-токен, ручное скачивание и подготовка ZIP во временной папке. После «Скачать пакет» появляется «Установить и запустить»: новая версия ставится в отдельную папку рядом с текущей. Вернуться назад: `Yorika.bat /rollback`. Подробности: [docs/UPDATES.md](docs/UPDATES.md).

## Настройки

Рядом с «Обновлениями» в меню есть кнопка **⚙ Настройки**: отдельная страница `settings.html`. На ней канал и автопроверка обновлений (те же значения, что на странице обновлений), состояние токена GitHub, локальный адрес сайта с копированием и командами `Yorika.bat`, а также число записей в браузерном хранилище IndexedDB с кнопкой его очистки.

## Цель развития Yorika

[Полная спецификация конечного продукта](docs/YORIKA_VISION.md) описывает целевое поведение и критерии приёмки A01–A20; [живой план](docs/ROADMAP.md) и [генеральная дорожная карта всего проекта](docs/FULL_PROJECT_ROADMAP.md) и [машинные статусы](planning/tasks.json) показывают, что выполнено, а что только запланировано. Это **не** означает, что собственная обученная нейросеть или автономная инициатива уже работают.

## Проверка реализованного состояния

[Аудит исходников и незавершённые проверки](docs/STATUS_AUDIT.md) поясняют, что реально добавлено, что осталось прототипом и какие Windows-тесты необходимы. Не следует путать наличие SQLite API с готовым искусственным мозгом.
