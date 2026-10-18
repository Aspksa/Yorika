# Compatible with Windows PowerShell 5.1; ASCII-only to avoid encoding ambiguity.
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$paths = @('scripts/start.ps1','scripts/yorika-tray.ps1','scripts/update-engine.ps1','scripts/apply-staged-update.ps1','scripts/test-updater.ps1')
$failed = $false
foreach ($relative in $paths) {
  $file = Join-Path $root $relative
  $tokens = $null
  $errors = $null
  [System.Management.Automation.Language.Parser]::ParseFile($file, [ref]$tokens, [ref]$errors) | Out-Null
  if ($errors.Count -gt 0) {
    $failed = $true
    Write-Host ("FAIL " + $relative)
    foreach ($problem in $errors) { Write-Host ("  Line " + $problem.Extent.StartLineNumber + ": " + $problem.Message) }
  } else { Write-Host ("PASS " + $relative) }
}
if ($failed) { exit 1 }
Write-Host 'All PowerShell scripts parsed successfully.'
