# Проверка кандидата восстановления SQLite

Новый `scripts/sqlite_restore_preview.py` безопасно проверяет резервную копию без записи в живую базу и без операций замены файлов.

```powershell
python scripts/sqlite_restore_preview.py "C:\\Users\\USERNAME\\Documents\\yorika-backup.sqlite3"
python scripts/sqlite_restore_preview.py "C:\\Users\\USERNAME\\Documents\\yorika-backup.sqlite3" --sha256 <SHA256_ИЗ_ОТЧЁТА>
python -m unittest tests.test_sqlite_restore_preview -v
```

Требования: самодостаточный snapshot базы Yorika (`PRAGMA user_version=1`, таблицы `records` и `events`), `PRAGMA integrity_check=ok`. Отображается только SHA-256, версия и число записей — без личных сообщений. При ошибке целостности или несоответствии checksum инструмент прекращает проверку.

**Важно:** preview не восстанавливает живую базу, не останавливает Yorika, не копирует секреты. Не используйте его как доказательство полной процедуры восстановления DATA-003. Тесты в GitHub добавлены; в текущей сессии отдельно выполнен эквивалентный SQLite smoke-check на Linux (схема/кириллица/immutable read/checksum rejection), не полный тест репозитория и не Windows.

## Большие резервные копии

Контрольная сумма SHA-256 теперь вычисляется потоково блоками по 1 МиБ без загрузки всей копии SQLite в оперативную память. Это важно для ноутбуков с ограниченной памятью. Обновлён тест на резервную копию с объёмным Unicode-полем. Полная проверка на Windows остаётся отдельным критерием приёмки.
