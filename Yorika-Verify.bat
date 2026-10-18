@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo YORIKA - 60 SCENARIO VERIFICATION
echo.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0scripts\verify-60.ps1" -ProjectRoot "%~dp0"
echo.
echo Completed verification. PASS is not the same as Windows end-to-end validation.
pause
