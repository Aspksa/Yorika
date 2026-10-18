param([Parameter(Mandatory=$true)][string]$ProjectRoot)
$ErrorActionPreference = 'Stop'
$ProjectRoot = [IO.Path]::GetFullPath($ProjectRoot)
$work = Join-Path $ProjectRoot '.yorika'
$ready = Join-Path $work 'ready.url'
$log = Join-Path $work 'yorika.log'
$server = Join-Path $ProjectRoot 'scripts\yorika-tray.ps1'
function IsLive([string]$address) {
  if ($address -notmatch '^http://127\.0\.0\.1:\d+/$') { return $false }
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
  $process = Start-Process -FilePath "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -ArgumentList @('-NoLogo','-NoProfile','-STA','-ExecutionPolicy','Bypass','-WindowStyle','Hidden','-File',('"' + $server + '"'),'-ProjectRoot',('"' + $ProjectRoot + '"')) -WindowStyle Hidden -PassThru
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
