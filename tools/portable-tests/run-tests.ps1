# Requires Windows PowerShell 5.1 or later. No system Python is used.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$toolDir = $PSScriptRoot
$root = [IO.Path]::GetFullPath((Join-Path $toolDir '..\\..'))
$runner = Join-Path $root 'scripts\\run-acceptance.py'
$runtime = Join-Path $toolDir 'runtime'
$python = Join-Path $runtime 'python.exe'
$zip = Join-Path $toolDir 'python-3.12.10-embed-amd64.zip'
$source = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip'
$reportFolder = Join-Path $env:LOCALAPPDATA 'YorikaTestReports'
$report = Join-Path $reportFolder 'yorika-portable-acceptance.json'
if (-not (Test-Path -LiteralPath $runner)) { throw 'Run this BAT from the Yorika project folder (tools\\portable-tests).' }
if (-not (Test-Path -LiteralPath $python)) {
    Write-Host 'First run: downloading official Python 3.12.10 embedded x64 from python.org.'
    Write-Host 'WARNING: SHA256 is not pinned; verify archive provenance if this is a managed device.'
    if (-not (Test-Path -LiteralPath $zip)) {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $source -OutFile $zip -UseBasicParsing
    }
    Add-Type -AssemblyName System.IO.Compression
    $archive = [IO.Compression.ZipFile]::OpenRead($zip)
    try {
        $names = @($archive.Entries | ForEach-Object { $_.FullName })
        if ($names.Count -lt 10 -or -not ($names -contains 'python.exe') -or -not ($names -contains 'python312._pth')) {
            throw 'Archive structure is invalid; delete the ZIP and retry.'
        }
    } finally { $archive.Dispose() }
    if (-not (Test-Path -LiteralPath $runtime)) {
        New-Item -ItemType Directory -Path $runtime | Out-Null
    }
    Expand-Archive -LiteralPath $zip -DestinationPath $runtime -Force
}
$pth = Join-Path $runtime 'python312._pth'
if (-not (Test-Path -LiteralPath $pth)) { throw 'Missing embedded Python path configuration.' }
# Keep site-packages disabled; import project modules directly from the reviewed repo.
$rootSlash = $root -replace '\\','/'
[IO.File]::WriteAllLines($pth, @('python312.zip', '.', $rootSlash), (New-Object Text.UTF8Encoding($false)))
& $python -V
if ($LASTEXITCODE -ne 0) { throw 'Portable Python cannot start.' }
& $python -c 'import sqlite3, ssl; print("SQLite:", sqlite3.sqlite_version)'
if ($LASTEXITCODE -ne 0) { throw 'Portable Python SQLite smoke test failed.' }
New-Item -ItemType Directory -Path $reportFolder -Force | Out-Null
Push-Location $root
try {
    & $python $runner --report $report
    $code = $LASTEXITCODE
} finally { Pop-Location }
Write-Host ('Acceptance report: ' + $report)
if ($code -ne 0) {
    Write-Warning 'At least one acceptance test failed. Inspect the report; missing third-party packages are not silently skipped.'
    exit 1
}
Write-Host 'PASS: all Python acceptance checks succeeded.'
exit 0
