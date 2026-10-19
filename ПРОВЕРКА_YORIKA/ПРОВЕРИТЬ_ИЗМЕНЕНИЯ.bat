@echo off
setlocal
cd /d "%~dp0"
title YORIKA - CHANGE CHECKS
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0check-changes.ps1"
set "rc=%ERRORLEVEL%"
echo.
echo Exit code: %rc%
pause
exit /b %rc%
