@echo off
setlocal
cd /d "%~dp0"
title YORIKA - CHECK ALL BEFORE COMMIT
echo [1/2] Checking changed files...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0check-changes.ps1"
if errorlevel 1 goto fail
echo [2/2] Running Python and SQLite acceptance...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0test-yorika.ps1"
if errorlevel 1 goto fail
echo.
echo Python and SQLite acceptance passed. Other Windows/Cloud.ru/GUI tests are separate.
pause
exit /b 0
:fail
echo.
echo FAILURE: see messages above. Do not mark checks passed.
pause
exit /b 1
