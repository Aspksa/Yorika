@echo off
setlocal
cd /d "%~dp0"
title Yorika - Portable tests
echo ============================================
echo   Yorika portable Python and SQLite tests
echo ============================================
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-tests.ps1"
set "result=%ERRORLEVEL%"
echo.
echo Exit code: %result%
pause
exit /b %result%
