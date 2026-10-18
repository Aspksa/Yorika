param([ValidateSet('settings','save-settings','save-token','delete-token','check','stage')][string]$Action,[string]$Channel='fresh',[int]$Interval=86400000,[string]$Token='')
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$work=Join-Path $root '.yorika'
[IO.Directory]::CreateDirectory($work)|Out-Null
$settings=Join-Path $work 'updates.json'
$secret=Join-Path $work 'github-token.dpapi'
function Read-Settings {
 if(Test-Path -LiteralPath $settings){try{return (Get-Content -LiteralPath $settings -Raw -Encoding UTF8|ConvertFrom-Json)}catch{}}
 return [pscustomobject]@{channel='fresh';interval=86400000}
}
function Get-Token {
 if(-not(Test-Path -LiteralPath $secret)){return ''}
 $bytes=[IO.File]::ReadAllBytes($secret)
 return [Text.Encoding]::UTF8.GetString([Security.Cryptography.ProtectedData]::Unprotect($bytes,$null,[Security.Cryptography.DataProtectionScope]::CurrentUser))
}
function Request($uri,[switch]$Binary){
 $headers=@{'User-Agent'='Yorika-Updater';'Accept'='application/vnd.github+json';'X-GitHub-Api-Version'='2022-11-28'}
 $t=Get-Token
 if($t){$headers.Authorization="Bearer $t"}
 if($Binary){return $headers}
 return Invoke-RestMethod -Uri $uri -Headers $headers -TimeoutSec 25 -MaximumRedirection 3
}
function Target($channel){
 if($channel -eq 'fresh'){
  $r=Request 'https://api.github.com/repos/Aspksa/Yorika/commits/main'
  return @{sha=$r.sha;label=$r.sha.Substring(0,12);archive="https://api.github.com/repos/Aspksa/Yorika/zipball/$($r.sha)"}
 }
 $r=Request 'https://api.github.com/repos/Aspksa/Yorika/releases/latest'
 if(-not $r.tag_name -or -not $r.target_commitish){throw 'Нет опубликованного стабильного выпуска'}
 $ref=[uri]::EscapeDataString($r.tag_name)
 $commit=Request "https://api.github.com/repos/Aspksa/Yorika/commits/$ref"
 return @{sha=$commit.sha;label=$r.tag_name;archive="https://api.github.com/repos/Aspksa/Yorika/zipball/$($commit.sha)"}
}
function Output($obj){$obj|ConvertTo-Json -Depth 5 -Compress}
switch($Action){
 'settings' { $s=Read-Settings;Output @{channel=$s.channel;interval=$s.interval;hasToken=(Test-Path $secret)} }
 'save-settings' {if($Channel -notin @('fresh','stable') -or $Interval -notin @(0,3600000,86400000)){throw 'Недопустимые настройки'}
   $json=@{channel=$Channel;interval=$Interval}|ConvertTo-Json -Compress
   [IO.File]::WriteAllText($settings,$json,[Text.Encoding]::UTF8);Output @{ok=$true}}
 'save-token' {if(-not $Token -or $Token.Length -gt 512){throw 'Пустой или слишком длинный токен'}
   $bytes=[Security.Cryptography.ProtectedData]::Protect([Text.Encoding]::UTF8.GetBytes($Token),$null,[Security.Cryptography.DataProtectionScope]::CurrentUser)
   [IO.File]::WriteAllBytes($secret,$bytes);Output @{ok=$true}}
 'delete-token' {if(Test-Path $secret){Remove-Item -LiteralPath $secret -Force};Output @{ok=$true}}
 'check' {$target=Target $Channel
   $installed=Join-Path $work 'installed.json'
   $known='';if(Test-Path $installed){try{$known=(Get-Content $installed -Raw|ConvertFrom-Json).sha}catch{}}
   Output @{available=($target.sha -ne $known);sha=$target.sha;detail=("GitHub: "+$target.label+"; локальная установленная ревизия: "+$(if($known){$known}else{'не определена'}))}}
 'stage' {
   $target=Target $Channel
   $dir=Join-Path $work 'staging'
   [IO.Directory]::CreateDirectory($dir)|Out-Null
   $destination=Join-Path $dir ($target.sha+'.zip')
   $temp=Join-Path $env:TEMP ('yorika-'+[guid]::NewGuid().ToString('N')+'.zip')
   try{
     $headers=Request $target.archive -Binary
     Invoke-WebRequest -Uri $target.archive -Headers $headers -OutFile $temp -TimeoutSec 180 -MaximumRedirection 3 -UseBasicParsing
     if((Get-Item -LiteralPath $temp).Length -lt 128){throw 'Архив подозрительно мал'}
     Add-Type -AssemblyName System.IO.Compression
     $zip=[IO.Compression.ZipFile]::OpenRead($temp)
     try {
       $names=@($zip.Entries|ForEach-Object FullName)
       if(-not($names|Where-Object {$_ -match '^[^/]+/Yorika\.bat$'}) -or -not($names|Where-Object {$_ -match '^[^/]+/www/index\.html$'})){throw 'Архив не содержит обязательных файлов'}
       foreach($entry in $zip.Entries){$name=$entry.FullName;if($name.Contains('..') -or $name.StartsWith('/') -or $name.Contains('\')){throw 'Опасный путь в архиве'}}
     }finally{$zip.Dispose()}
     $hash=(Get-FileHash -LiteralPath $temp -Algorithm SHA256).Hash
     Move-Item -LiteralPath $temp -Destination $destination -Force
     Output @{ok=$true;detail=("Архив подготовлен: "+$target.label+"; SHA-256: "+$hash+"; установленная версия не изменена")}
   }finally{if(Test-Path $temp){Remove-Item -LiteralPath $temp -Force}}
 }
}
