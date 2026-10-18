param([Parameter(Mandatory=$true)][string]$Root,[Parameter(Mandatory=$true)][string]$Sha)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$Root=[IO.Path]::GetFullPath($Root)
$work=Join-Path $Root '.yorika'
$stage=Join-Path $work 'staging'
$archive=Join-Path $stage ($Sha+'.zip')
$manifestPath=Join-Path $stage ($Sha+'.json')
$pending=Join-Path $work 'install-result.json'
function Report($ok,$message,$path='',$url=''){
 $json=@{success=$ok;message=$message;path=$path;url=$url;sha=$Sha;time=(Get-Date -Format o)}|ConvertTo-Json -Compress
 [IO.File]::WriteAllText($pending,$json,[Text.Encoding]::UTF8)
}
try{
 if($Sha -notmatch '^[0-9a-f]{40}\z'){throw 'Некорректный идентификатор версии'}
 if(-not (Test-Path -LiteralPath $archive) -or -not (Test-Path -LiteralPath $manifestPath)){throw 'Проверенный архив не найден'}
 $manifest=Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8|ConvertFrom-Json
 $hash=(Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash
 if($manifest.sha -ne $Sha -or $manifest.hash -ne $hash){throw 'Архив не прошёл повторную проверку SHA-256'}
 $parent=Split-Path -Parent $Root
 $target=Join-Path $parent ('Yorika-release-'+$Sha.Substring(0,12))
 $targetFull=[IO.Path]::GetFullPath($target)
 if($targetFull -eq $Root -or $targetFull.StartsWith(($Root.TrimEnd('\')+'\'),[StringComparison]::OrdinalIgnoreCase)){throw 'Недопустимое расположение новой версии'}
 if(Test-Path -LiteralPath $target){throw 'Папка этой версии уже существует. Установка не заменяет существующие файлы.'}
 $extract=Join-Path $parent ('Yorika-preparing-'+[guid]::NewGuid().ToString('N'))
 try{
  [IO.Directory]::CreateDirectory($extract)|Out-Null
  $zip=[IO.Compression.ZipFile]::OpenRead($archive)
  try{
   if($zip.Entries.Count -gt 10000){throw 'Слишком много файлов в архиве'}
   $sum=[long]0
   foreach($entry in $zip.Entries){
    $name=$entry.FullName
    if([string]::IsNullOrWhiteSpace($name) -or $name.StartsWith('/') -or $name.Contains('\') -or $name.Contains(':')){throw 'Небезопасный путь в архиве'}
    if($name.Split('/') | Where-Object {$_ -in @('.','..')}){throw 'Недопустимые сегменты пути в архиве'}
    $sum += [long]$entry.Length
    if($sum -gt 536870912){throw 'Архив превышает допустимый размер'}
   }
  }finally{$zip.Dispose()}
  [IO.Compression.ZipFile]::ExtractToDirectory($archive,$extract)
  $dirs=@(Get-ChildItem -LiteralPath $extract -Directory)
  if($dirs.Count -ne 1){throw 'Неправильная структура релиза'}
  $source=$dirs[0].FullName
  foreach($file in @('Yorika.bat','scripts\start.ps1','scripts\yorika-tray.ps1','www\index.html','www\main.js')){
   if(-not (Test-Path -LiteralPath (Join-Path $source $file))){throw ('Нет обязательного файла: '+$file)}
  }
  # Deploy to a new immutable directory, never delete or overwrite the currently running app.
  Move-Item -LiteralPath $source -Destination $target -ErrorAction Stop
  $newWork=Join-Path $target '.yorika'
  [IO.Directory]::CreateDirectory($newWork)|Out-Null
  foreach($name in @('github-token.dpapi','updates.json')){
   $oldFile=Join-Path $work $name
   if(Test-Path -LiteralPath $oldFile){Copy-Item -LiteralPath $oldFile -Destination (Join-Path $newWork $name) -Force}
  }
  $launcher=Join-Path $target 'scripts\start.ps1'
  $runner=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
  # The updates page navigates to the new address itself, so no extra browser tab.
  $launchArgs=@('-NoLogo','-NoProfile','-STA','-ExecutionPolicy','Bypass','-File',('"'+$launcher+'"'),'-NoBrowser')
  $launchProcess=Start-Process -FilePath $runner -ArgumentList $launchArgs -WindowStyle Hidden -PassThru
  $ready=Join-Path $newWork 'ready.url'
  for($i=0;$i -lt 70 -and -not(Test-Path -LiteralPath $ready);$i++){
   Start-Sleep -Milliseconds 250
   $launchProcess.Refresh()
   if($launchProcess.HasExited -and $launchProcess.ExitCode -ne 0){break}
  }
  if(-not(Test-Path -LiteralPath $ready)){throw 'Новая версия не запустилась; старые файлы не изменены'}
  $newUrl=[IO.File]::ReadAllText($ready).Trim()
  if($newUrl -notmatch '^http://127\.0\.0\.1:\d+/\z'){throw 'Неверный локальный адрес новой версии'}
  $request=[Net.WebRequest]::Create($newUrl);$request.Timeout=3000
  $response=$request.GetResponse()
  try{if($response.Headers['X-Yorika-App'] -ne 'Yorika'){throw 'Не удалось подтвердить запуск новой версии'}}finally{$response.Close()}
  $pointer=Join-Path $work 'active-install.json'
  $pointerTemp=$pointer+'.tmp'
  [IO.File]::WriteAllText($pointerTemp,(@{path=$target;sha=$Sha}|ConvertTo-Json -Compress),[Text.Encoding]::UTF8)
  Move-Item -LiteralPath $pointerTemp -Destination $pointer -Force
  [IO.File]::WriteAllText((Join-Path $newWork 'installed.json'),(@{sha=$Sha}|ConvertTo-Json -Compress),[Text.Encoding]::UTF8)
  Report $true 'Новая версия запущена и выбрана для последующих запусков. Предыдущая папка сохранена.' $target $newUrl
 }finally{if(Test-Path -LiteralPath $extract){Remove-Item -LiteralPath $extract -Recurse -Force -ErrorAction SilentlyContinue}}
}catch{Report $false $_.Exception.Message}
