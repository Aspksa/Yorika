@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
title YORIKA - Control Center

:MENU
echo.
echo ============== YORIKA CENTER ==============
echo 1. Check and install dependencies
echo 2. Check GitHub CI (actionlint + zizmor)
echo 3. Open PowerShell testing menu
echo 4. Show tool versions
echo 0. Exit
choice /C 12340 /N /M "Select: "
if errorlevel 5 exit /b 0
if errorlevel 4 goto VERSIONS
if errorlevel 3 goto CENTER
if errorlevel 2 goto CI
if errorlevel 1 goto DEPS
goto MENU

:DEPS
echo.
echo Installer only runs after confirmation. Do not continue if antivirus blocks the project.
choice /C YN /M "Install missing tools using winget / uv"
if errorlevel 2 goto MENU
where winget >nul 2>nul
if errorlevel 1 (
 echo [ERROR] winget missing. Install Microsoft App Installer.
 goto MENU
)
call :INSTALL pwsh Microsoft.PowerShell
call :INSTALL node OpenJS.NodeJS.LTS
call :INSTALL git Git.Git
call :INSTALL actionlint Rhysd.actionlint
call :INSTALL uv astral-sh.uv
where zizmor >nul 2>nul
if errorlevel 1 (
 where uv >nul 2>nul
 if errorlevel 1 (
  echo [WAIT] Reopen CMD to refresh PATH, then retry zizmor.
 ) else (
  choice /C YN /M "Install zizmor via uv"
  if not errorlevel 2 uv tool install zizmor
 )
)
echo [INFO] Python is checked separately. The bundled 3.12 runtime is for Yorika tests.
python --version 2>nul
if errorlevel 1 echo [WARNING] System Python is unavailable, Yorika has separate test bootstrap.
echo [INFO] Reopen CMD before running checks after installing tools.
goto MENU

:INSTALL
where %~1 >nul 2>nul
if not errorlevel 1 (
 echo [OK] %~1
 exit /b 0
)
echo [MISSING] %~1
choice /C YN /M "Install %~1 with winget"
if errorlevel 2 exit /b 0
winget install --id %~2 --exact --source winget --accept-package-agreements --accept-source-agreements
if errorlevel 1 echo [ERROR] Installation failed for %~1
exit /b 0

:CI
where actionlint >nul 2>nul
if errorlevel 1 (
 echo [NOT RUN] actionlint is missing. Choose option 1.
) else (
 actionlint
 if errorlevel 1 (echo [FAIL] actionlint) else (echo [PASS] actionlint)
)
where zizmor >nul 2>nul
if errorlevel 1 (
 echo [NOT RUN] zizmor is missing. Choose option 1.
) else (
 zizmor .github/workflows
 if errorlevel 1 (echo [FAIL] zizmor) else (echo [PASS] zizmor)
)
goto MENU

:CENTER
powershell.exe -NoLogo -NoProfile -Command "if ((Get-ExecutionPolicy) -eq 'Restricted') { exit 10 } else { exit 0 }"
if "%ERRORLEVEL%"=="10" (
 echo [BLOCKED] Windows PowerShell is Restricted. This script will not bypass policy.
 echo Run: Get-ExecutionPolicy -List
 echo Resolve prior antivirus warning before authorizing scripts.
 goto MENU
)
powershell.exe -NoLogo -NoProfile -File "%~dp0center.ps1"
if errorlevel 1 echo [ERROR] Testing menu did not complete successfully.
goto MENU

:VERSIONS
for %%T in (winget pwsh node git actionlint uv zizmor python) do (
 where %%T >nul 2>nul
 if errorlevel 1 (echo [MISSING] %%T) else (echo [FOUND] %%T)
)
goto MENU
