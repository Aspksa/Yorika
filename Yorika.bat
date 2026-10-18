@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "ROOT=%~dp0"
set "STARTER=%ROOT%scripts\start.ps1"
if not exist "%STARTER%" (
 echo [YORIKA] Missing scripts\start.ps1. Extract the complete ZIP archive.
 pause
 exit /b 1
)
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -STA -ExecutionPolicy Bypass -File "%STARTER%"
if errorlevel 1 (
 echo.
 echo [YORIKA] Startup failed. Press a key to exit.
 pause >nul
 exit /b 1
)
exit /b 0
