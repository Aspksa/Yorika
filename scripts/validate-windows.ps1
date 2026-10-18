# Offline Windows validation for Yorika before a release.
# Run from the repository root in PowerShell 5.1+.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root

$python = Get-Command python.exe -ErrorAction Stop
$errors = $null
[void][System.Management.Automation.Language.Parser]::ParseFile(
    (Join-Path $root 'scripts\yorika-tray.ps1'), [ref]$null, [ref]$errors)
if ($errors.Count -gt 0) { throw ('Yorika tray syntax errors: ' + ($errors | Out-String)) }

& $python.Source -m compileall -q backend scripts tests
if ($LASTEXITCODE -ne 0) { throw 'Python compilation failed' }

& $python.Source -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Python unit tests failed' }

$node = Get-Command node.exe -ErrorAction SilentlyContinue
if ($node) {
    & $node.Source --check (Join-Path $root 'www\avatar.js')
    if ($LASTEXITCODE -ne 0) { throw 'Avatar JavaScript syntax failed' }
    & $node.Source --check (Join-Path $root 'www\settings.js')
    if ($LASTEXITCODE -ne 0) { throw 'Settings JavaScript syntax failed' }
} else {
    Write-Warning 'Node.js unavailable; JavaScript syntax check skipped'
}
Write-Host 'Yorika offline checks passed. Cloud.ru live API and DPAPI still require explicit manual acceptance.'
