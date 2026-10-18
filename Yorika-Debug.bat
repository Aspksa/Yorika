@echo off
setlocal
cd /d "%~dp0"
echo ===========================================
echo  YORIKA - DIAGNOSTICS
echo ===========================================
echo Project folder: "%CD%"
if not exist "scripts\yorika-tray.ps1" (
 echo Missing scripts\yorika-tray.ps1
 echo Extract the complete repository ZIP archive.
 pause
 exit /b 1
)
echo.
echo Starting Yorika with an on-screen error console...
echo Keep this window open and send the error text if it fails.
echo.
powershell.exe -NoLogo -NoProfile -STA -ExecutionPolicy Bypass -File "%CD%\scripts\yorika-tray.ps1" -ProjectRoot "%CD%"
echo.
echo PowerShell returned exit code: %ERRORLEVEL%
echo Log file: "%CD%\.yorika\yorika.log"
if exist ".yorika\yorika.log" (
 echo.
 echo Most recent log entries:
 powershell.exe -NoLogo -NoProfile -Command "Get-Content -LiteralPath '.yorika\yorika.log' -Tail 15"
)
pause
