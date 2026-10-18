@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "ROOT=%~dp0"
set "READY=%ROOT%.yorika\ready.url"
set "LOG=%ROOT%.yorika\yorika.log"
if not exist "%ROOT%scripts\yorika-tray.ps1" goto missing
if not exist "%ROOT%www\index.html" goto missing
if not exist "%ROOT%.yorika" mkdir "%ROOT%.yorika"
where powershell.exe >nul 2>&1
if errorlevel 1 (
 echo [YORIKA] PowerShell was not found.
 pause
 exit /b 1
)
if exist "%READY%" del /q "%READY%" >nul 2>&1
start "Yorika" /min powershell.exe -NoLogo -NoProfile -STA -ExecutionPolicy Bypass -WindowStyle Hidden -File "%ROOT%scripts\yorika-tray.ps1" -ProjectRoot "%ROOT%"
if errorlevel 1 goto failed
set /a "COUNT=0"
:wait
if exist "%READY%" goto open
set /a "COUNT+=1"
if %COUNT% GEQ 15 goto failed
timeout /t 1 /nobreak >nul
goto wait
:open
set "YORIKA_URL="
set /p "YORIKA_URL="<"%READY%"
if not defined YORIKA_URL goto failed
echo [YORIKA] Opening %YORIKA_URL%
start "" "%YORIKA_URL%"
if errorlevel 1 goto failed
exit /b 0
:missing
echo [YORIKA] Missing files. Extract the complete ZIP before running.
pause
exit /b 1
:failed
echo [YORIKA] Could not start or open the website.
echo Run Yorika-Debug.bat or inspect "%LOG%"
pause
exit /b 1
