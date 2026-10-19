@echo off
setlocal
cd /d "%~dp0"
title YORIKA - CENTER
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0center.ps1" %*
set "rc=%ERRORLEVEL%"
if not "%~1"=="" exit /b %rc%
echo.
pause
exit /b %rc%
