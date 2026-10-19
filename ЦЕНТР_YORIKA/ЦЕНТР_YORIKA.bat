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
echo [YORIKA] All five policy scopes can show Undefined, while effective policy remains Restricted.
echo [YORIKA] Inspect both effective policy and configured scopes:
echo             Get-ExecutionPolicy
echo             Get-ExecutionPolicy -List
echo             pwsh -NoProfile -Command "Get-ExecutionPolicy"
echo [YORIKA] On managed PCs ask IT to authorize vetted, signed scripts.
echo [YORIKA] On personal PCs verify the Kaspersky alert before any policy changes.
echo [YORIKA] Do not disable security tools or use ExecutionPolicy Bypass.
set "rc=10"

:END
if not "%~1"=="" exit /b %rc%
echo.
pause
exit /b %rc%
