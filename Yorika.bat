@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
set "ROOT=%~dp0"
set "STARTER=%ROOT%scripts\start.ps1"
set "WORK=%ROOT%.yorika"
set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"

rem Commands: Yorika.bat [/status | /log | /rollback | /help]
if /i "%~1"=="/help" (
 echo Yorika.bat           - запустить Yorika
 echo Yorika.bat /status   - показать адрес работающей Yorika
 echo Yorika.bat /log      - открыть журнал
 echo Yorika.bat /rollback - вернуться к исходной версии после обновления
 exit /b 0
)
if /i "%~1"=="/status" (
 if exist "%WORK%\ready.url" (
  set /p URL=<"%WORK%\ready.url"
  call echo [YORIKA] Адрес: %%URL%%
 ) else (
  echo [YORIKA] Yorika из этой папки не запущена.
 )
 if exist "%WORK%\active-install.json" echo [YORIKA] Запуск перенаправляется на установленное обновление.
 exit /b 0
)
if /i "%~1"=="/log" (
 if exist "%WORK%\yorika.log" (start "" notepad.exe "%WORK%\yorika.log") else (echo [YORIKA] Журнал ещё не создан.)
 exit /b 0
)
if /i "%~1"=="/rollback" (
 if exist "%WORK%\active-install.json" (
  del /q "%WORK%\active-install.json"
  echo [YORIKA] Следующий запуск откроет исходную версию из этой папки.
  echo [YORIKA] Если обновлённая Yorika ещё в трее, закройте её: «Выйти из Yorika».
 ) else (
  echo [YORIKA] Обновление не выбрано, уже используется исходная версия.
 )
 exit /b 0
)
if not "%~1"=="" (
 echo [YORIKA] Неизвестная команда "%~1". Список: Yorika.bat /help
 exit /b 2
)

rem Opened straight from a ZIP: Windows extracts only this file into a temporary folder.
if not "%ROOT:.zip\=%"=="%ROOT%" goto :zip
if not "%ROOT:\Temp1_=%"=="%ROOT%" goto :zip
if not exist "%STARTER%" (
 echo [YORIKA] Не найден scripts\start.ps1. Распакуйте архив полностью.
 pause
 exit /b 1
)
if not exist "%PS%" (
 echo [YORIKA] Не найден Windows PowerShell: %PS%
 pause
 exit /b 1
)
"%PS%" -NoLogo -NoProfile -STA -ExecutionPolicy Bypass -File "%STARTER%"
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (
 echo.
 echo [YORIKA] Запуск не удался ^(код %CODE%^). Журнал: Yorika.bat /log
 echo [YORIKA] Нажмите любую клавишу для выхода.
 pause >nul
 exit /b %CODE%
)
exit /b 0

:zip
echo [YORIKA] Yorika запущена прямо из ZIP-архива.
echo [YORIKA] Распакуйте архив ^(правый щелчок, «Извлечь все»^) и запустите Yorika.bat из распакованной папки.
pause
exit /b 1
