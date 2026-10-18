param([string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference = 'Stop'
$ProjectRoot = [IO.Path]::GetFullPath($ProjectRoot)
$report = New-Object System.Collections.Generic.List[object]
function Check([int]$number,[string]$name,[scriptblock]$test) {
  try {
    $okay = & $test
    $status = if ($okay) { 'PASS' } else { 'FAIL' }
  } catch { $status = 'FAIL'; Write-Warning ("Check {0}: {1}" -f $number, $_.Exception.Message) }
  $report.Add([pscustomobject]@{ Id = $number; Scenario = $name; Result = $status })
}
function Manual([int]$number,[string]$name) {
  $report.Add([pscustomobject]@{ Id = $number; Scenario = $name; Result = 'MANUAL' })
}
$starter = Join-Path $ProjectRoot 'scripts\start.ps1'
$tray = Join-Path $ProjectRoot 'scripts\yorika-tray.ps1'
$batch = Join-Path $ProjectRoot 'Yorika.bat'
$web = Join-Path $ProjectRoot 'www\index.html'
$db = Join-Path $ProjectRoot 'www\core\database.js'
$batText = if (Test-Path -LiteralPath $batch) { [IO.File]::ReadAllText($batch) } else { '' }
$trayText = if (Test-Path -LiteralPath $tray) { [IO.File]::ReadAllText($tray) } else { '' }
$startText = if (Test-Path -LiteralPath $starter) { [IO.File]::ReadAllText($starter) } else { '' }
$names = @(
'BAT missing','PowerShell missing','execution policy','PowerShell non-STA','WinForms load failure','Windows update changes','duplicate same-folder process','different-folder process','process exit during bootstrap','console hides fatal error',
'Cyrillic directory','path with spaces','OneDrive sync folder','external SSD/USB drive','drive-letter change','long path','read-only location','offline/network mapped drive','missing www files','media unplugged during run',
'occupied fixed port avoided','port released on exit','TCP bind permission denied','HTTP response readiness','stale ready.url','wrong service on old port','partial HTTP request','invalid encoded URI','directory traversal','simultaneous client requests',
'no default browser','browser launch failure','browser runs but 404','icon under overflow chevron','tray icon fails to initialize','Windows Explorer restarts','tray double-click handler','copy address operation','exit menu releases socket','reopen running server',
'IndexedDB blocked','private browsing storage','random-port origin change','browser profile switch','site data wiped','quota exceeded','schema upgrade','bad record ID','interrupted database write','backup restore unavailable',
'logs not writable','log file grows indefinitely','firewall interference','localhost-only binding','unexpected HTTP method','malformed file extensions','resource exhaustion','process recovery policy','portable permissions','manual recovery instructions'
)
for ($i=1; $i -le 60; $i++) {
  $name = $names[$i-1]
  switch ($i) {
    1 { Check $i $name { Test-Path -LiteralPath $batch }; break }
    2 { Check $i $name { Test-Path -LiteralPath (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe') }; break }
    3 { Check $i $name { $batText.Contains('-ExecutionPolicy Bypass') }; break }
    4 { Check $i $name { $batText.Contains('-STA') }; break }
    5 { Check $i $name { [Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms') -ne $null }; break }
    7 { Check $i $name { $trayText.Contains('Local\Yorika-') }; break }
    8 { Check $i $name { $trayText.Contains('ComputeHash') }; break }
    10 { Check $i $name { $batText.Contains('pause') }; break }
    11 { Check $i $name { $startText.Contains('GetFullPath') }; break }
    12 { Check $i $name { $batText.Contains('"%ROOT%"') -or $batText.Contains('"%STARTER%"') }; break }
    19 { Check $i $name { Test-Path -LiteralPath $web }; break }
    21 { Check $i $name { $trayText.Contains('Loopback,0') }; break }
    22 { Check $i $name { $trayText.Contains('$server.Stop()') }; break }
    24 { Check $i $name { $startText.Contains('IsLive $url') }; break }
    25 { Check $i $name { $startText.Contains('Remove-Item -LiteralPath $ready') }; break }
    26 { Check $i $name { $startText.Contains("X-Yorika-App") }; break }
    27 { Check $i $name { $trayText.Contains('ReceiveTimeout=') }; break }
    29 { Check $i $name { $trayText.Contains('StartsWith($prefix') }; break }
    32 { Check $i $name { $startText.Contains('Start-Process $url') }; break }
    37 { Check $i $name { $trayText.Contains('add_DoubleClick') }; break }
    38 { Check $i $name { $trayText.Contains('Clipboard') }; break }
    39 { Check $i $name { $trayText.Contains('ExitThread') }; break }
    40 { Check $i $name { $startText.Contains('Existing server') }; break }
    41 { Check $i $name { Test-Path -LiteralPath $db }; break }
    48 { Check $i $name { ([IO.File]::ReadAllText($db)).Contains('nonempty string id') }; break }
    54 { Check $i $name { $trayText.Contains('IPAddress]::Loopback') }; break }
    55 { Check $i $name { $trayText.Contains('405 Method Not Allowed') }; break }
    60 { Check $i $name { $batText.Contains('/rollback') }; break }
    default { Manual $i $name }
  }
}
$report | Format-Table -AutoSize
$summary = $report | Group-Object Result | ForEach-Object { "$($_.Name): $($_.Count)" }
Write-Host ('Yorika verification: ' + ($summary -join ', '))
Write-Host 'MANUAL means not verified by this script; PASS means a structural or local dependency check, not a Windows end-to-end guarantee.'
if ($report.Result -contains 'FAIL') { exit 1 }
