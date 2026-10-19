@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
title YORIKA - Windows dependency checks
echo.
echo =================================================
echo    YORIKA - CHECK AND INSTALL DEPENDENCIES
echo =================================================
echo This checker does not change PowerShell policies, antivirus or Windows security.
echo If Kaspersky is blocking Yorika, STOP and investigate before installation.
echo.
choice /C YN /M "Have you verified this project and want to check dependencies"
if errorlevel 2 exit /b 2

where winget >nul 2>nul
if errorlevel 1 (
 echo [ERROR] winget is missing. Install Microsoft App Installer from a trusted Microsoft source.
 echo [NOT CHECKED] Cannot automatically install missing dependencies without winget.
 goto DONE_FAIL
)

call :CHECK_TOOL "PowerShell 7" pwsh "Microsoft.PowerShell"
call :CHECK_TOOL "Node.js LTS" node "OpenJS.NodeJS.LTS"
call :CHECK_TOOL "Git" git "Git.Git"
call :CHECK_TOOL "actionlint" actionlint "Rhysd.actionlint"
call :CHECK_TOOL "uv" uv "astral-sh.uv"

where zizmor >nul 2>nul
if errorlevel 1 (
 echo [MISSING] zizmor - GitHub Actions security auditor.
 where uv >nul 2>nul
 if errorlevel 1 (
  echo [NOT RUN] uv not found in this CMD session. Restart CMD and rerun this file.
  set "FAILED=1"
 ) else (
  choice /C YN /M "Install zizmor using uv tool install zizmor"
  if errorlevel 2 (
   echo [SKIP] zizmor was not installed.
   set "FAILED=1"
  ) else (
   uv tool install zizmor
   if errorlevel 1 (
    echo [ERROR] zizmor installation failed.
    set "FAILED=1"
   ) else (
    echo [INFO] zizmor installed. Open a new CMD session to refresh PATH.
   )
  )
 )
) else (
 echo [OK] zizmor is available.
)

echo.
echo [PYTHON] System Python is optional for Yorika acceptance tests.
python --version 2>nul
if errorlevel 1 (
 echo [WARNING] System Python is missing or broken.
 echo [INFO] Yorika has a separate Python 3.12 bootstrap in test-yorika.ps1.
 echo [INFO] No silent Python download is performed by this BAT.
)
echo.
echo [NEXT] Close CMD, open it again, run this check once more.
echo [NEXT] Then run the GitHub CI checker in this folder.
goto DONE

:CHECK_TOOL
where %2 >nul 2>nul
if not errorlevel 1 (
 echo [OK] %~1 is in PATH.
 exit /b 0
)
echo [MISSING] %~1
choice /C YN /M "Install %~1 using winget package %~3"
if errorlevel 2 (
 echo [SKIP] %~1
 set "FAILED=1"
 exit /b 0
)
winget install --id %~3 --exact --source winget --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
 echo [ERROR] Installation failed for %~1. Verify package ID with winget search.
 set "FAILED=1"
) else (
 echo [INFO] %~1 installed. If not detected, reopen CMD to refresh PATH.
)
exit /b 0

:DONE
if "%FAILED%"=="1" goto DONE_FAIL
echo [OK] Dependency check completed; installed tools may require a new CMD session.
pause
exit /b 0

:DONE_FAIL
echo [ATTENTION] Some dependencies are missing or were not installed.
pause
exit /b 1
