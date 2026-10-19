@echo off
setlocal
cd /d "%~dp0"
title YORIKA - TESTS
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0test-yorika.ps1"
set "rc=%ERRORLEVEL%"
echo.
echo Test exit code: %rc%
echo Press any key to close this window...
pause >nul
exit /b %rc%
