param([string]$ProjectRoot)
$ErrorActionPreference = 'Stop'
# Resolve from the script's own location, never from an externally quoted argument.
$ProjectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$work = Join-Path $ProjectRoot '.yorika'
$ready = Join-Path $work 'ready.url'
$log = Join-Path $work 'yorika.log'
$server = Join-Path $ProjectRoot 'scripts\yorika-tray.ps1'
# Files from a downloaded ZIP carry the internet zone mark; clear it so Windows does not block the scripts.
foreach ($folder in @('scripts','www')) {
  Get-ChildItem -LiteralPath (Join-Path $ProjectRoot $folder) -Recurse -File -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue
}
# The original launcher is a stable entrypoint; keep a fallback copy in this directory.
$pointer=Join-Path $work 'active-install.json'
if(Test-Path -LiteralPath $pointer){
 try{
  $selection=Get-Content -LiteralPath $pointer -Raw -Encoding UTF8|ConvertFrom-Json
  $active=[IO.Path]::GetFullPath([string]$selection.path)
  $parent=[IO.Path]::GetFullPath((Split-Path -Parent $ProjectRoot))
  $expected=Join-Path $parent ('Yorika-release-'+([string]$selection.sha).Substring(0,12))
  if(-not $selection.sha -or ([string]$selection.sha).Length -ne 40 -or $active -ne $expected){throw 'Invalid release pointer'}
  $activeLauncher=Join-Path $active 'scripts\start.ps1'
  if(-not(Test-Path -LiteralPath $activeLauncher)){throw 'Release missing launcher'}
  & $activeLauncher
  if($LASTEXITCODE -ne 0){throw 'Release launcher failed'}
  exit 0
 }catch{
  Write-Host ("[YORIKA] Release failed, returning to previous version: "+$_.Exception.Message)
  Remove-Item -LiteralPath $pointer -Force -ErrorAction SilentlyContinue
 }
}
function IsLive([string]$address) {
  if ($address -notmatch '^http://127\.0\.0\.1:\d+/\z') { return $false }
  try {
    $request = [Net.WebRequest]::Create($address)
    $request.Timeout = 1500
    $response = $request.GetResponse()
    try { return (([int]$response.StatusCode -eq 200) -and ($response.Headers['X-Yorika-App'] -eq 'Yorika')) }
    finally { $response.Close() }
  } catch { return $false }
}
try {
  if (-not (Test-Path -LiteralPath $server) -or -not (Test-Path -LiteralPath (Join-Path $ProjectRoot 'www\index.html'))) {
    throw 'Project files are missing. Extract the complete archive.'
  }
  [IO.Directory]::CreateDirectory($work) | Out-Null
  if (Test-Path -LiteralPath $ready) {
    $existing = [IO.File]::ReadAllText($ready).Trim()
    if (IsLive $existing) {
      Write-Host "[YORIKA] Existing server: $existing"
      Start-Process $existing
      exit 0
    }
    Remove-Item -LiteralPath $ready -Force -ErrorAction SilentlyContinue
  }
  $process = Start-Process -FilePath "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -ArgumentList @('-NoLogo','-NoProfile','-STA','-ExecutionPolicy','Bypass','-WindowStyle','Hidden','-File',('"' + $server + '"')) -WindowStyle Hidden -PassThru
  for ($i=0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 250
    if (Test-Path -LiteralPath $ready) {
      $url = [IO.File]::ReadAllText($ready).Trim()
      if (IsLive $url) {
        Write-Host "[YORIKA] Opening $url"
        Start-Process $url
        exit 0
      }
    }
    $process.Refresh()
    if ($process.HasExited) { break }
  }
  throw 'Server did not become ready. Check the diagnostic log.'
} catch {
  Write-Host ("[YORIKA] ERROR: " + $_.Exception.Message)
  if (Test-Path -LiteralPath $log) {
    Write-Host '--- Last log entries ---'
    Get-Content -LiteralPath $log -Tail 12 | ForEach-Object { Write-Host $_ }
  }
  exit 1
}
