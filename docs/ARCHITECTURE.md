# Yorika — архитектура: базовый слой и актуальное состояние

> Аудит состояния: [STATUS_AUDIT.md](STATUS_AUDIT.md). Конечный образ: [YORIKA_VISION.md](YORIKA_VISION.md). Статусы задач: [ROADMAP.md](ROADMAP.md) и [tasks.json](../planning/tasks.json).

## Установочная архитектура
`Yorika.bat` → `scripts/start.ps1` → `scripts/yorika-tray.ps1` → loopback HTTP с автоматическим портом → `www/`.

Интерфейс, настройки и аватар доступны без Python. Для отдельной подсистемы памяти чат использует `GET/POST /api/chat/history` и **опционально** `scripts/chat-store.py` на Python со стандартной библиотекой `sqlite3`. При недоступности Python чат переходит на browser localStorage. Эта связка пока **не проверена на реальном Windows устройстве**.

## Хранилище и границы
- `www/core/database.js`: IndexedDB `yorika`, версия 1; stores `settings`, `projects`, `memories`, `conversations`, `messages`, `tasks`. Оно зависит от origin браузера и **может быть недоступно после смены порта**.
- `www/avatar.js`: localStorage `yorika.chat` и optional SQLite sync; браузерная история ограничена; старая версия страницы может содержать данные, которые не были импортированы.
- `backend/storage.py`: SQLite вне папки установки (`%LOCALAPPDATA%/Yorika/data` в Windows). Схема, события, ручной backup; не путать с шифрованием, автоматической ротацией и проверенным восстановлением.
- `scripts/chat-store.py`: ревизии и `BEGIN IMMEDIATE` для атомарного отклонения устаревших снимков; frontend делает ограниченное объединение. См. [CHAT_CONFLICTS.md](CHAT_CONFLICTS.md).
- `www/memory-export.html` и `scripts/import-browser-memory.py`: ручной экспорт текущего origin/архивный импорт, **не автоматическое восстановление всех портов**.

## Отдельные подсистемы
- Обновления: PowerShell updater и staged install, см. [UPDATES.md](UPDATES.md).
- Cloud.ru: [CLOUD_RU.md](CLOUD_RU.md) — план аутентификации, DPAPI, средств контроля бюджета. Реальной интеграции пока нет.
- AI: архитектура и критерии описаны в [AI_ARCHITECTURE.md](AI_ARCHITECTURE.md) и [YORIKA_VISION.md](YORIKA_VISION.md). Нет установленной обученной с нуля нейросети и фонового самообучения.

## Известные риски
- Взаимодействия между несколькими вкладками и процессами требуют Windows stress-тестов.
- Наличие локального API на loopback не означает завершённой аутентификации или отсутствия CSRF/DNS-rebinding.
- Текущая база памяти содержит plaintext и не является пожизненно защищённой.
- Готовность UI/документации не тождественна готовности ИИ.

## Правило актуализации
Перед каждым новым релизом сверяйте этот документ, `README.md`, `AGENTS.md`, `planning/tasks.json`, `docs/ROADMAP.md` и код. Отдельно отмечайте «проверено исходником» и «проверено запуском на Windows». Новые задачи завершаются только после приёмки.

## Решение об архитектуре: собственная модель без Ollama

Yorika не использует Ollama и не должна обращаться к её HTTP API. Локальный вход `scripts/local-model.py` использует только экспериментальный checkpoint собственной модели через `backend.neural_router.experimental_answer`. Путь задаётся `YORIKA_NEURAL_CHECKPOINT`. Если checkpoint отсутствует, повреждён или экспериментальная модель не выдаёт ответ, возвращается **явная ошибка**, а не ответ сторонней модели. Разработка собственного движка продолжается: текущая tiny Transformer — исследовательский прототип, не готовый полноценный собеседник. Возможные облачные интеграции регулируются отдельно и не должны автоматически подменять локальную нейросеть.
