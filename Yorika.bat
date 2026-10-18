@echo off
setlocal
set "ROOT=%~dp0"
if not exist "%ROOT%scripts\yorika-tray.ps1" (
  echo Yorika launcher files are missing.
  pause
  exit /b 1
)
start "" /min powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%ROOT%scripts\yorika-tray.ps1" -ProjectRoot "%ROOT%"
exit /b 0
