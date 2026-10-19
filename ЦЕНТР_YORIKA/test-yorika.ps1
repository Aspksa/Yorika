# Portable Python 3.12 tests. Run only from a trusted copy of Yorika.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$tools = $PSScriptRoot
$root = [IO.Path]::GetFullPath((Join-Path $tools '..'))
$accept = Join-Path $root 'scripts\run-acceptance.py'
$portable = Join-Path $tools 'python312-runtime'
$python = Join-Path $portable 'python.exe'
$archiveFile = Join-Path $tools 'python-3.12.10-embed-amd64.zip'
$url = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip'
$reportDir = Join-Path $env:LOCALAPPDATA 'YorikaTestReports'
$report = Join-Path $reportDir 'yorika-portable-acceptance.json'
function CheckLast([string]$name) { if ($LASTEXITCODE -ne 0) { throw "$name failed (exit $LASTEXITCODE)" } }
try {
    Write-Host 'Yorika portable test environment'
    Write-Host ('Repository: ' + $root)
    if (-not (Test-Path -LiteralPath $accept)) { throw 'The full Yorika project is required: scripts/run-acceptance.py not found.' }
    if (-not (Test-Path -LiteralPath $python)) {
        if (-not (Test-Path -LiteralPath $archiveFile)) {
            Write-Host 'First run: downloading standalone Python 3.12.10 from python.org.'
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest -Uri $url -OutFile $archiveFile -UseBasicParsing
        }
        Add-Type -AssemblyName System.IO.Compression
        $z = [IO.Compression.ZipFile]::OpenRead($archiveFile)
        try {
            $names = @($z.Entries | ForEach-Object { $_.FullName })
            if ($names.Count -lt 10 -or -not ($names -contains 'python.exe') -or -not ($names -contains 'python312._pth')) {
                throw 'Invalid Python ZIP. Remove the ZIP and retry.'
            }
        } finally { $z.Dispose() }
        New-Item -ItemType Directory -Path $portable -Force | Out-Null
        Expand-Archive -LiteralPath $archiveFile -DestinationPath $portable -Force
    }
    $pth = Join-Path $portable 'python312._pth'
    if (-not (Test-Path -LiteralPath $pth)) { throw 'Portable Python is incomplete (python312._pth missing).' }
    $slash = $root.Replace('\','/')
    [IO.File]::WriteAllLines($pth, @('python312.zip', '.', $slash), (New-Object System.Text.UTF8Encoding($false)))
    & $python --version
    CheckLast 'Python'
    & $python -c 'import sqlite3, ssl; print("SQLite", sqlite3.sqlite_version)'
    CheckLast 'SQLite smoke test'
    New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
    Push-Location $root
    try {
        & $python $accept --report $report
        $acceptCode = $LASTEXITCODE
    } finally { Pop-Location }
    Write-Host ('JSON report: ' + $report)
    if ($acceptCode -ne 0) { throw 'Python/SQLite acceptance failed. Open the JSON report for details.' }
    Write-Host 'Python and SQLite acceptance: PASS'
    $node = Get-Command node -ErrorAction SilentlyContinue
    if ($node) {
        Push-Location $root
        try { & node --check 'www/avatar.js'; CheckLast 'JavaScript syntax' }
        finally { Pop-Location }
        Write-Host 'JavaScript syntax: PASS'
    } else {
        Write-Warning 'JavaScript syntax NOT TESTED (Node.js missing).'
    }
    Write-Host 'DPAPI, GUI and Cloud.ru integration require separate Windows acceptance.'
    exit 0
} catch {
    Write-Host ('TEST ERROR: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('See README in: ' + $tools)
    exit 1
}
