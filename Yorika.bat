@echo off
setlocal
set "ROOT=%~dp0"
set "LOG=%ROOT%.yorika\yorika.log"
if not exist "%ROOT%scripts\yorika-tray.ps1" (
  echo [YORIKA] Missing scripts\yorika-tray.ps1
  echo Extract the whole ZIP archive first.
  pause
  exit /b 1
)
if not exist "%ROOT%www\index.html" (
  echo [YORIKA] Missing www\index.html
  pause
  exit /b 1
)
if not exist "%ROOT%.yorika" mkdir "%ROOT%.yorika"
where powershell.exe >nul 2>&1
if errorlevel 1 (
  echo [YORIKA] Windows PowerShell was not found.
  pause
  exit /b 1
)
rem Launch the tray process without keeping a console open.
start "Yorika" /min powershell.exe -NoLogo -NoProfile -STA -ExecutionPolicy Bypass -WindowStyle Hidden -File "%ROOT%scripts\yorika-tray.ps1" -ProjectRoot "%ROOT%"
rem Give the child process time to write diagnostics.
timeout /t 3 /nobreak >nul
if exist "%LOG%" (
  findstr /C:"Startup error:" "%LOG%" >nul 2>&1
  if not errorlevel 1 (
    echo [YORIKA] Startup errors were recorded. Check:
    echo "%LOG%"
    echo Run Yorika-Debug.bat for details.
  )
)
exit /b 0
