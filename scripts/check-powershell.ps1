# Compatible with Windows PowerShell 5.1; ASCII-only to avoid encoding ambiguity.
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$paths = @('scripts/start.ps1','scripts/yorika-tray.ps1','scripts/update-engine.ps1','scripts/install-release.ps1','scripts/apply-staged-update.ps1','scripts/test-updater.ps1','ЦЕНТР_YORIKA/center.ps1','ЦЕНТР_YORIKA/test-yorika.ps1','ЦЕНТР_YORIKA/check-changes.ps1')
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
  } elseif ([IO.File]::ReadAllText($file).Contains(([string][char]36 + [string][char]39))) {
    # Some web editors expand a dollar-quote pair into the rest of the file; regexes must end with \z instead.
    $failed = $true
    Write-Host ("FAIL " + $relative + ": contains a dollar sign before a quote; use \z to end regexes")
  } else { Write-Host ("PASS " + $relative) }
}
if ($failed) { exit 1 }
Write-Host 'All PowerShell scripts parsed successfully.'
