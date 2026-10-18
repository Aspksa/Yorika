param([Parameter(Mandatory=$true)][string]$Root,[Parameter(Mandatory=$true)][string]$Sha,[Parameter(Mandatory=$true)][int]$ServerPid,[switch]$TestOnly)
$ErrorActionPreference='Stop'
$work=Join-Path $Root '.yorika'
$staging=Join-Path $work 'staging'
$archive=Join-Path $staging ($Sha+'.zip')
$backup=Join-Path $work ('backup-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
$extract=Join-Path $work ('extract-'+[guid]::NewGuid().ToString('N'))
$journal=Join-Path $work 'update-result.json'
$protected=@('.yorika','.git')
function Result($ok,$message){
 $report=@{success=$ok;message=$message;time=(Get-Date -Format o)}
 [IO.File]::WriteAllText($journal,($report|ConvertTo-Json -Compress),[Text.Encoding]::UTF8)
}
try{
 if($Sha -notmatch '^[a-f0-9]{40}$'){throw 'Некорректный SHA'}
 if(-not(Test-Path -LiteralPath $archive)){throw 'Архив обновления не найден'}
 $manifestFile=Join-Path $staging ($Sha+'.json')
 if(-not(Test-Path -LiteralPath $manifestFile)){throw 'Нет проверенного манифеста архива'}
 $manifest=Get-Content -LiteralPath $manifestFile -Raw | ConvertFrom-Json
 $actual=(Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash
 if($manifest.hash -ne $actual){throw 'Контрольная сумма архива не совпадает'}
 # Avoid modifying a running installation.
 for($i=0;$i -lt $(if($TestOnly){0}else{80});$i++){
  $p=Get-Process -Id $ServerPid -ErrorAction SilentlyContinue
  if(-not $p){break}
  Start-Sleep -Milliseconds 250
 }
 if(-not $TestOnly -and (Get-Process -Id $ServerPid -ErrorAction SilentlyContinue)){throw 'Yorika ещё работает; обновление отменено'}
 Add-Type -AssemblyName System.IO.Compression.FileSystem
 [IO.Directory]::CreateDirectory($extract)|Out-Null
 $zip=[IO.Compression.ZipFile]::OpenRead($archive)
 try {
  foreach($entry in $zip.Entries){
   $name=$entry.FullName
   if($name -match '(^/|\\|(^|/)\.\.(/|$)|:)'){throw 'Недопустимое имя файла в архиве'}
  }
 }finally{$zip.Dispose()}
 [IO.Compression.ZipFile]::ExtractToDirectory($archive,$extract)
 $top=@(Get-ChildItem -LiteralPath $extract -Directory)
 if($top.Count -ne 1){throw 'Неверная структура архива'}
 $source=$top[0].FullName
 foreach($essential in @('Yorika.bat','www\index.html','scripts\start.ps1','scripts\yorika-tray.ps1')){
  if(-not(Test-Path -LiteralPath (Join-Path $source $essential))){throw "Отсутствует: $essential"}
 }
 if($TestOnly){ Result $true 'Проверка обновления успешна: файлы не изменены'; return }
 [IO.Directory]::CreateDirectory($backup)|Out-Null
 $original=@(Get-ChildItem -LiteralPath $Root -Force | Where-Object {$_.Name -notin $protected})
 foreach($item in $original){Copy-Item -LiteralPath $item.FullName -Destination $backup -Recurse -Force -ErrorAction Stop}
 foreach($item in $original){if(-not(Test-Path -LiteralPath (Join-Path $backup $item.Name))){throw ('Резервная копия неполна: '+$item.Name)}}
 try {
  foreach($item in $original){Remove-Item -LiteralPath $item.FullName -Recurse -Force -ErrorAction Stop}
  foreach($item in (Get-ChildItem -LiteralPath $source -Force)){
   if($item.Name -in $protected){continue}
   Copy-Item -LiteralPath $item.FullName -Destination $Root -Recurse -Force -ErrorAction Stop
  }
  [IO.File]::WriteAllText((Join-Path $work 'installed.json'),(@{sha=$Sha}|ConvertTo-Json -Compress),[Text.Encoding]::UTF8)
  Result $true ("Обновлено. Резервная копия: "+$backup)
 }catch{
  $errorText=$_.Exception.Message
  foreach($item in (Get-ChildItem -LiteralPath $Root -Force | Where-Object {$_.Name -notin $protected})){
   Remove-Item -LiteralPath $item.FullName -Recurse -Force -ErrorAction SilentlyContinue
  }
  foreach($item in (Get-ChildItem -LiteralPath $backup -Force)){Copy-Item -LiteralPath $item.FullName -Destination $Root -Recurse -Force -ErrorAction Stop}
  throw "Обновление отменено, восстановлена резервная копия: $errorText"
 }
}catch{Result $false $_.Exception.Message}
finally{if(Test-Path -LiteralPath $extract){Remove-Item -LiteralPath $extract -Recurse -Force -ErrorAction SilentlyContinue}}
