@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
title YORIKA - GitHub CI checks
set "failed=0"
echo.
echo === YORIKA GitHub Actions static checks ===
where actionlint >nul 2>nul
if errorlevel 1 (
 echo [NOT RUN] actionlint is not in PATH.
 set "failed=1"
) else (
 actionlint
 if errorlevel 1 (echo [FAIL] actionlint & set "failed=1") else (echo [PASS] actionlint)
)
where zizmor >nul 2>nul
if errorlevel 1 (
 where uv >nul 2>nul
 if errorlevel 1 (
  echo [NOT RUN] zizmor and uv are missing.
  set "failed=1"
 ) else (
  uv tool run --offline zizmor .github/workflows
  if errorlevel 1 (echo [FAIL] zizmor & set "failed=1") else (echo [PASS] zizmor)
 )
) else (
 zizmor .github/workflows
 if errorlevel 1 (echo [FAIL] zizmor & set "failed=1") else (echo [PASS] zizmor)
)
echo.
if "%failed%"=="0" (echo [PASS] All available checks passed.) else (echo [ATTENTION] Some checks failed or did not run.)
echo These are static checks only - not Windows/Cloud.ru acceptance.
pause
if "%failed%"=="0" (exit /b 0) else (exit /b 1)
