@echo off
setlocal
cd /d "%~dp0"
title YORIKA - CENTER

rem Do not bypass execution policy. Diagnose it before attempting to run scripts.
powershell.exe -NoLogo -NoProfile -Command "if ((Get-ExecutionPolicy) -eq 'Restricted') { exit 10 } else { exit 0 }"
if "%ERRORLEVEL%"=="10" goto POLICY_BLOCKED

powershell.exe -NoLogo -NoProfile -File "%~dp0center.ps1" %*
set "rc=%ERRORLEVEL%"
if "%rc%"=="0" goto END
echo.
echo [YORIKA] Script could not run or returned error %rc%.
echo [YORIKA] To diagnose PowerShell policy, run in PowerShell:
echo             Get-ExecutionPolicy -List
echo [YORIKA] Do not disable antivirus protection or bypass company policies.
goto END

:POLICY_BLOCKED
echo.
echo [YORIKA] Windows has blocked PowerShell script execution (Restricted).
echo [YORIKA] Open PowerShell and inspect:
echo             Get-ExecutionPolicy -List
echo [YORIKA] On managed PCs ask IT to authorize signed scripts.
echo [YORIKA] Do not disable security tools or use ExecutionPolicy Bypass.
set "rc=10"

:END
if not "%~1"=="" exit /b %rc%
echo.
pause
exit /b %rc%
