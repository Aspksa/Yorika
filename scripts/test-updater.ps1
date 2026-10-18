# Run in Windows PowerShell 5.1. Creates an isolated update fixture in TEMP.
$ErrorActionPreference='Stop'
$root=Join-Path $env:TEMP ('yorika-update-test-'+[guid]::NewGuid().ToString('N'))
try {
 $work=Join-Path $root '.yorika\staging'
 [IO.Directory]::CreateDirectory($work)|Out-Null
 $sha='1234567890abcdef1234567890abcdef12345678'
 $source=Join-Path $root 'source\yorika-test'
 foreach($dir in @($source,(Join-Path $source 'www'),(Join-Path $source 'scripts'))){[IO.Directory]::CreateDirectory($dir)|Out-Null}
 foreach($name in @('Yorika.bat','www\index.html','scripts\start.ps1','scripts\yorika-tray.ps1')){
   [IO.File]::WriteAllText((Join-Path $source $name),'test fixture',[Text.Encoding]::UTF8)
 }
 Add-Type -AssemblyName System.IO.Compression.FileSystem
 $zipPath=Join-Path $work ($sha+'.zip')
 [IO.Compression.ZipFile]::CreateFromDirectory((Join-Path $root 'source'),$zipPath)
 $hash=(Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash
 [IO.File]::WriteAllText((Join-Path $work ($sha+'.json')),(@{sha=$sha;hash=$hash}|ConvertTo-Json -Compress))
 $installer=Join-Path $PSScriptRoot 'apply-staged-update.ps1'
 & $installer -Root $root -Sha $sha -ServerPid 0 -TestOnly
 $report=Get-Content -LiteralPath (Join-Path $root '.yorika\update-result.json') -Raw|ConvertFrom-Json
 if(-not $report.success){throw $report.message}
 if(Test-Path -LiteralPath (Join-Path $root '.yorika\installed.json')){throw 'Test unexpectedly installed update'}
 Write-Host 'PASS: staged package validated without touching a running project.'
 # Verify tamper detection
 [IO.File]::AppendAllText($zipPath,'tamper')
 & $installer -Root $root -Sha $sha -ServerPid 0 -TestOnly
 $report=Get-Content -LiteralPath (Join-Path $root '.yorika\update-result.json') -Raw|ConvertFrom-Json
 if($report.success){throw 'Tampering was not rejected'}
 Write-Host 'PASS: tampered archive rejected.'
}catch{Write-Error $_.Exception.Message;exit 1}
finally{if(Test-Path -LiteralPath $root){Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue}}
