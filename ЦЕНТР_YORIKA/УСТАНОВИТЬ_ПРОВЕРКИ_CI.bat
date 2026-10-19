@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
title YORIKA - Install CI checks
echo [YORIKA] Installing actionlint and zizmor through package managers.
echo [YORIKA] This script does NOT change PowerShell policy or antivirus settings.
echo [YORIKA] Do not continue if Kaspersky still blocks the project.
echo.
choice /C YN /M "Have you verified that the project is safe and want to install tools"
if errorlevel 2 exit /b 2
where winget >nul 2>nul
if errorlevel 1 (
 echo [ERROR] winget missing. Install Windows App Installer from Microsoft.
 pause
 exit /b 1
)
where actionlint >nul 2>nul
if errorlevel 1 (
 echo [1/2] Installing actionlint with winget...
 winget install --id Rhysd.actionlint --exact --source winget
 if errorlevel 1 (
   echo [ERROR] actionlint install failed. Check winget search actionlint.
   pause
   exit /b 1
 )
) else (echo [OK] actionlint already in PATH.)
where uv >nul 2>nul
if errorlevel 1 (
 echo [2/2] Installing uv with winget...
 winget install --id astral-sh.uv --exact --source winget
 if errorlevel 1 (
   echo [ERROR] uv install failed. See https://docs.astral.sh/uv/
   pause
   exit /b 1
 )
)
where uv >nul 2>nul
if errorlevel 1 (
 echo [ACTION] Close CMD, reopen it, then rerun this installer to install zizmor.
 pause
 exit /b 2
)
echo [2/2] Installing zizmor using uv tool...
uv tool install zizmor
if errorlevel 1 (
 echo [ERROR] zizmor install failed.
 pause
 exit /b 1
)
where zizmor >nul 2>nul
if errorlevel 1 (
 echo [ACTION] zizmor is installed but not visible in this CMD PATH yet.
 echo [ACTION] Close CMD and open a new window before running checks.
) else (
 zizmor --version
 if errorlevel 1 echo [WARNING] Could not verify zizmor version.
)
echo.
echo [ACTION] Open a NEW CMD window and run PROVERIT_GITHUB_CI.bat in this folder.
pause
exit /b 0
