param([ValidateSet('menu','all','changes','tests','status','key-set','key-status')][string]$Mode='menu')
$ErrorActionPreference='Stop'
$base=$PSScriptRoot
$project=[IO.Path]::GetFullPath((Join-Path $base '..'))
$stateDir=Join-Path $env:LOCALAPPDATA 'YorikaDevelopment'
$statePath=Join-Path $stateDir 'status.json'
$keyDir=Join-Path $stateDir 'secrets'
New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
function Load-State {
  if(Test-Path $statePath) {
    try { return (Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json) }
    catch { Write-Warning 'Предыдущий отчёт повреждён; создаю новый.' }
  }
  return [pscustomobject]@{ checks=@(); updated='' }
}
function Record([string]$name,[string]$state,[string]$message) {
  $data=Load-State
  $entry=[pscustomobject]@{ name=$name; status=$state; message=$message; time=[DateTime]::UtcNow.ToString('o') }
  $remaining=@($data.checks | Where-Object { $_.name -ne $name })
  $data.checks=@($remaining)+@($entry)
  $data.updated=$entry.time
  $temp=$statePath+'.tmp'
  $data | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $temp -Encoding UTF8
  Move-Item -LiteralPath $temp -Destination $statePath -Force
}
function Show-State {
  $d=Load-State
  Write-Host 'СОСТОЯНИЕ ПРОВЕРОК YORIKA' -ForegroundColor Cyan
  if(-not $d.checks -or $d.checks.Count -eq 0) { Write-Host 'Проверок пока нет.' -ForegroundColor Yellow }
  foreach($c in $d.checks) {
    $color=switch($c.status){'OK'{'Green'} 'FAIL'{'Red'} default{'Yellow'}}
    Write-Host ('[{0}] {1}: {2} ({3})' -f $c.status,$c.name,$c.message,$c.time) -ForegroundColor $color
  }
  Write-Host ('Локальный отчёт: '+$statePath)
}
function Run-Step([string]$name,[scriptblock]$action) {
  Write-Host ('Запуск: '+$name) -ForegroundColor Cyan
  try {
    $global:LASTEXITCODE=0
    & $action | Out-Host
    if($LASTEXITCODE -is [int] -and $LASTEXITCODE -ne 0){ throw ('Код завершения '+$LASTEXITCODE) }
    Record $name 'OK' 'Успешно'
    Write-Host ('[OK] '+$name) -ForegroundColor Green
    return $true
  } catch {
    Record $name 'FAIL' $_.Exception.Message
    Write-Host ('[ОШИБКА] '+$name+': '+$_.Exception.Message) -ForegroundColor Red
    return $false
  }
}
function Save-Key {
  New-Item -ItemType Directory -Path $keyDir -Force | Out-Null
  $name=Read-Host 'Название ключа (латинские буквы, цифры, - или _)'
  if($name -notmatch '^[a-zA-Z0-9_-]{1,40}$'){throw 'Недопустимое имя ключа.'}
  $secret=Read-Host 'Введите секрет (скрыто)' -AsSecureString
  if(-not $secret -or $secret.Length -eq 0){throw 'Пустой секрет не сохранён.'}
  $file=Join-Path $keyDir ($name+'.dpapi')
  $secret | ConvertFrom-SecureString | Set-Content -LiteralPath $file -Encoding ASCII
  Write-Host ('Ключ '+$name+' сохранён локально через Windows DPAPI. Не переносите файл на другой ПК.') -ForegroundColor Green
}
function Key-Status {
  Write-Host 'ЛОКАЛЬНЫЕ КЛЮЧИ (значения не показываются)' -ForegroundColor Cyan
  if(-not (Test-Path $keyDir)){Write-Host 'Ключи отсутствуют.' -ForegroundColor Yellow;return}
  $files=@(Get-ChildItem -LiteralPath $keyDir -Filter '*.dpapi' -File)
  if($files.Count -eq 0){Write-Host 'Ключи отсутствуют.' -ForegroundColor Yellow;return}
  foreach($f in $files) {
    try {
      $s=Get-Content -LiteralPath $f.FullName -Raw | ConvertTo-SecureString
      if($s.Length -lt 1){throw 'empty'}
      Write-Host ('[ЗАЩИЩЁН] '+$f.BaseName) -ForegroundColor Green
    } catch {Write-Host ('[НЕДОСТУПЕН] '+$f.BaseName) -ForegroundColor Red}
  }
}
function Run-Changes {
  $git=Get-Command git -ErrorAction SilentlyContinue
  if(-not $git) {Record 'Новые изменения' 'SKIP' 'Git не установлен'; Write-Host 'Git отсутствует; изменения не проверены.' -ForegroundColor Yellow;return $false}
  if(-not (Test-Path (Join-Path $project '.git'))) {Record 'Новые изменения' 'SKIP' 'ZIP без .git';Write-Host 'Это ZIP без истории Git — сравнение невозможно.' -ForegroundColor Yellow;return $false}
  return (Run-Step 'Новые изменения' { & (Join-Path $base 'check-changes.ps1');if($LASTEXITCODE -ne 0){throw 'Проверка изменений не прошла'} })
}
function Run-Tests {
  return (Run-Step 'Python и SQLite' {& (Join-Path $base 'test-yorika.ps1');if($LASTEXITCODE -ne 0){throw 'Тесты не прошли'} })
}
function Run-All {
  $a=Run-Changes
  $b=Run-Tests
  Show-State
  return ($a -and $b)
}
if($Mode -eq 'key-set'){Save-Key;exit 0}
if($Mode -eq 'key-status'){Key-Status;exit 0}
if($Mode -eq 'status'){Show-State;exit 0}
if($Mode -eq 'changes'){if(Run-Changes){exit 0}else{exit 1}}
if($Mode -eq 'tests'){if(Run-Tests){exit 0}else{exit 1}}
if($Mode -eq 'all'){if(Run-All){exit 0}else{exit 1}}
while($true) {
  Write-Host ''
  Write-Host '========== ЦЕНТР YORIKA ==========' -ForegroundColor Cyan
  Write-Host '1 — Проверить всё'
  Write-Host '2 — Проверить изменения Git'
  Write-Host '3 — Запустить Python / SQLite тесты'
  Write-Host '4 — Цветные статусы'
  Write-Host '5 — Сохранить локальный секрет (DPAPI)'
  Write-Host '6 — Проверить сохранённые ключи'
  Write-Host '0 — Выход'
  $choice=Read-Host 'Выбор'
  switch($choice) {
    '1' {[void](Run-All)}
    '2' {[void](Run-Changes)}
    '3' {[void](Run-Tests)}
    '4' {Show-State}
    '5' {try{Save-Key}catch{Write-Host $_.Exception.Message -ForegroundColor Red}}
    '6' {Key-Status}
    '0' {exit 0}
    default {Write-Host 'Неизвестный пункт' -ForegroundColor Yellow}
  }
}
