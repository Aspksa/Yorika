# Windows PowerShell 5.1 updater integration tests.
# All destructive operations are confined to a unique TEMP fixture.
$ErrorActionPreference='Stop'
$root=Join-Path $env:TEMP ('yorika-update-test-'+[guid]::NewGuid().ToString('N'))
$fixture=Join-Path $env:TEMP ('yorika-fixture-'+[guid]::NewGuid().ToString('N'))
$sha='1234567890abcdef1234567890abcdef12345678'
$installer=Join-Path $PSScriptRoot 'apply-staged-update.ps1'
function Verify([bool]$expected,[string]$label) {
 $report=Get-Content -LiteralPath (Join-Path $root '.yorika\update-result.json') -Raw|ConvertFrom-Json
 if([bool]$report.success -ne $expected){throw "$label : $($report.message)"}
 Write-Host ("PASS: "+$label)
}
function SeedOld {
 foreach($name in @('Yorika.bat','www\index.html','scripts\start.ps1','scripts\yorika-tray.ps1')){
  $path=Join-Path $root $name
  [IO.Directory]::CreateDirectory((Split-Path -Parent $path))|Out-Null
  [IO.File]::WriteAllText($path,'old version',[Text.Encoding]::UTF8)
 }
}
try{
 $staging=Join-Path $root '.yorika\staging'
 [IO.Directory]::CreateDirectory($staging)|Out-Null
 $source=Join-Path $fixture 'yorika-release'
 foreach($dir in @($source,(Join-Path $source 'www'),(Join-Path $source 'scripts'))){[IO.Directory]::CreateDirectory($dir)|Out-Null}
 foreach($name in @('Yorika.bat','www\index.html','scripts\start.ps1','scripts\yorika-tray.ps1')){
  [IO.File]::WriteAllText((Join-Path $source $name),'new version',[Text.Encoding]::UTF8)
 }
 SeedOld
 Add-Type -AssemblyName System.IO.Compression.FileSystem
 $zipPath=Join-Path $staging ($sha+'.zip')
 [IO.Compression.ZipFile]::CreateFromDirectory($fixture,$zipPath)
 $hash=(Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash
 [IO.File]::WriteAllText((Join-Path $staging ($sha+'.json')),(@{sha=$sha;hash=$hash}|ConvertTo-Json -Compress))
 & $installer -Root $root -Sha $sha -ServerPid 0 -TestOnly
 Verify $true 'Предварительная проверка'
 if((Get-Content -LiteralPath (Join-Path $root 'Yorika.bat') -Raw) -ne 'old version'){throw 'Предпроверка изменила файлы'}
 & $installer -Root $root -Sha $sha -ServerPid 0 -SimulateFailure
 Verify $false 'Сбой установки обнаружен'
 if((Get-Content -LiteralPath (Join-Path $root 'Yorika.bat') -Raw) -ne 'old version'){throw 'Откат не восстановил BAT'}
 & $installer -Root $root -Sha $sha -ServerPid 0
 Verify $true 'Установка тестовой версии'
 if((Get-Content -LiteralPath (Join-Path $root 'Yorika.bat') -Raw) -ne 'new version'){throw 'Новая версия не установлена'}
 if(-not(Test-Path -LiteralPath (Join-Path $root '.yorika\installed.json'))){throw 'Манифест установки отсутствует'}
 [IO.File]::AppendAllText($zipPath,'tamper')
 & $installer -Root $root -Sha $sha -ServerPid 0 -TestOnly
 Verify $false 'Изменённый ZIP отклонён'
 if((Get-Content -LiteralPath (Join-Path $root 'Yorika.bat') -Raw) -ne 'new version'){throw 'Проверка повреждённого архива изменила проект'}
 Write-Host 'PASS: все тестовые сценарии выполнены.'
}catch{Write-Error $_.Exception.Message;exit 1}
finally{
 foreach($path in @($root,$fixture)){
  if(Test-Path -LiteralPath $path){Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue}
 }
}
