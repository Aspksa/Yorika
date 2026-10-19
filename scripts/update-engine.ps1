param([ValidateSet('settings','save-settings','save-token','delete-token','check','stage')][string]$Action,[string]$Channel='fresh',[int]$Interval=86400000,[string]$Token='')
$ErrorActionPreference='Stop'
# Windows PowerShell 5.1: explicitly load DPAPI assembly before using ProtectedData.
Add-Type -AssemblyName System.Security
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
function Request($uri,[switch]$Binary,[string]$CandidateToken='', [switch]$StrictCandidate){
 $headers=@{'User-Agent'='Yorika-Updater';'Accept'='application/vnd.github+json';'X-GitHub-Api-Version'='2022-11-28'}
 $t=if($StrictCandidate){$CandidateToken}else{Get-Token}
 if($t){$headers.Authorization="Bearer $t"}
 if($Binary){return $headers}
 try {
  return Invoke-RestMethod -Uri $uri -Headers $headers -TimeoutSec 25 -MaximumRedirection 3
 } catch {
  $statusCode=0
  try { $statusCode=[int]$_.Exception.Response.StatusCode } catch {}
  if($statusCode -eq 404) {
   if($uri.EndsWith('/releases/latest')) { throw 'Стабильный выпуск не найден. Если доступ к репозиторию есть, выберите Свежий.' }
   throw 'GitHub вернул 404. Проверьте адрес репозитория и наличие публикации.'
  }
  if($statusCode -eq 401) { throw 'GitHub отклонил токен доступа. Удалите устаревший токен для публичного репозитория.' }
  if($statusCode -eq 403) { throw 'GitHub запретил запрос. Проверьте лимит API либо удалите неработающий токен.' }
  throw ('Ошибка соединения с GitHub: ' + $_.Exception.Message)
 }
}
function Target($channel){
 if($channel -notin @('fresh','stable')){throw 'Неверный канал обновления'}
 if($channel -eq 'fresh'){
  $r=Request 'https://api.github.com/repos/Aspksa/Yorika/commits/main'
  return @{sha=$r.sha;label=$r.sha.Substring(0,12);archive="https://api.github.com/repos/Aspksa/Yorika/zipball/$($r.sha)"}
 }
 $r=Request 'https://api.github.com/repos/Aspksa/Yorika/releases/latest'
 if(-not $r.tag_name){throw 'Нет опубликованного стабильного выпуска'}
 $ref=[uri]::EscapeDataString($r.tag_name)
 $commit=Request "https://api.github.com/repos/Aspksa/Yorika/commits/$ref"
 return @{sha=$commit.sha;label=$r.tag_name;archive="https://api.github.com/repos/Aspksa/Yorika/zipball/$($commit.sha)"}
}
function Get-LocalRevision {
 # 1) git clone: read HEAD without requiring git.exe.
 $gitDir=Join-Path $root '.git'
 $headFile=Join-Path $gitDir 'HEAD'
 if(Test-Path -LiteralPath $headFile -PathType Leaf){
  try{
   $head=([IO.File]::ReadAllText($headFile)).Trim()
   if($head -match '^[0-9a-f]{40}\z'){return @{sha=$head;source='git'}}
   if($head -match '^ref:\s*(refs/\S+)\z'){
    $ref=$Matches[1]
    $refFile=Join-Path $gitDir $ref
    if(Test-Path -LiteralPath $refFile -PathType Leaf){
     $value=([IO.File]::ReadAllText($refFile)).Trim()
     if($value -match '^[0-9a-f]{40}\z'){return @{sha=$value;source='git'}}
    }
    $packed=Join-Path $gitDir 'packed-refs'
    if(Test-Path -LiteralPath $packed -PathType Leaf){
     foreach($line in [IO.File]::ReadAllLines($packed)){
      if($line -match '^([0-9a-f]{40}) (\S+)\z' -and $Matches[2] -eq $ref){return @{sha=$Matches[1];source='git'}}
     }
    }
   }
  }catch{}
 }
 # 2) Version installed through the updater.
 $installed=Join-Path $work 'installed.json'
 if(Test-Path -LiteralPath $installed){
  try{$known=[string](Get-Content -LiteralPath $installed -Raw -Encoding UTF8|ConvertFrom-Json).sha;if($known -match '^[0-9a-f]{40}\z'){return @{sha=$known;source='installed'}}}catch{}
 }
 # 3) Unpacked GitHub zipball keeps the short commit in the folder name: Aspksa-Yorika-1a2b3c4.
 $leaf=Split-Path -Leaf $root
 if($leaf -match '-([0-9a-f]{7,40})\z'){$short=$Matches[1];if($short -match '[0-9]'){return @{sha=$short;source='folder'}}}
 return $null
}
function Get-BlobSha([byte[]]$bytes){
 $prefix=[Text.Encoding]::ASCII.GetBytes('blob '+$bytes.Length+[char]0)
 $sha1=[Security.Cryptography.SHA1]::Create()
 try{
  $sha1.TransformBlock($prefix,0,$prefix.Length,$null,0)|Out-Null
  $sha1.TransformFinalBlock($bytes,0,$bytes.Length)|Out-Null
  return ([BitConverter]::ToString($sha1.Hash)).Replace('-','').ToLowerInvariant()
 }finally{$sha1.Dispose()}
}
function Remove-CarriageReturns([byte[]]$bytes){
 $list=New-Object 'System.Collections.Generic.List[byte]' $bytes.Length
 for($i=0;$i -lt $bytes.Length;$i++){if(-not($bytes[$i] -eq 13 -and $i+1 -lt $bytes.Length -and $bytes[$i+1] -eq 10)){$list.Add($bytes[$i])}}
 return $list.ToArray()
}
# Compares local files with the GitHub tree of a commit using git blob hashes.
# Returns 'same', 'different' or '' when the comparison is not possible.
function Compare-Files($sha){
 $tree=Request ("https://api.github.com/repos/Aspksa/Yorika/git/trees/"+$sha+"?recursive=1")
 if($tree.truncated -or -not $tree.tree){return ''}
 foreach($item in $tree.tree){
  if($item.type -ne 'blob' -or $item.mode -eq '120000'){continue}
  $path=Join-Path $root ([string]$item.path)
  if(-not(Test-Path -LiteralPath $path -PathType Leaf)){return 'different'}
  if(([IO.FileInfo]::new($path)).Length -gt 52428800){return ''}
  $bytes=[IO.File]::ReadAllBytes($path)
  if((Get-BlobSha $bytes) -eq $item.sha){continue}
  # Windows checkouts and ZIP archives may store text files with CRLF line endings.
  if([Array]::IndexOf($bytes,[byte]13) -ge 0 -and (Get-BlobSha (Remove-CarriageReturns $bytes)) -eq $item.sha){continue}
  return 'different'
 }
 return 'same'
}
function Output($obj){$obj|ConvertTo-Json -Depth 5 -Compress}
switch($Action){
 'settings' { $s=Read-Settings;Output @{channel=$s.channel;interval=$s.interval;hasToken=(Test-Path $secret)} }
 'save-settings' {if($Channel -notin @('fresh','stable') -or $Interval -notin @(0,3600000,86400000)){throw 'Недопустимые настройки'}
   $json=@{channel=$Channel;interval=$Interval}|ConvertTo-Json -Compress
   [IO.File]::WriteAllText($settings,$json,[Text.Encoding]::UTF8);Output @{ok=$true}}
 'save-token' { $Token=$Token.Trim(); if(-not $Token -or $Token.Length -gt 512){throw 'Пустой или слишком длинный токен'}
   $validated=Request 'https://api.github.com/repos/Aspksa/Yorika' -CandidateToken $Token -StrictCandidate
   if($validated.full_name -ne 'Aspksa/Yorika'){throw 'Токен не видит нужный репозиторий'}
   $validatedCommit=Request 'https://api.github.com/repos/Aspksa/Yorika/commits/main' -CandidateToken $Token -StrictCandidate
   if(-not $validatedCommit.sha -or $validatedCommit.sha.Length -ne 40){throw 'Не подтверждён доступ к ветке main'}
   $bytes=[Security.Cryptography.ProtectedData]::Protect([Text.Encoding]::UTF8.GetBytes($Token),$null,[Security.Cryptography.DataProtectionScope]::CurrentUser)
   [IO.File]::WriteAllBytes($secret,$bytes);Output @{ok=$true;verified=$true;detail='Токен проверен: доступ к Yorika/main подтверждён'}}
 'delete-token' {if(Test-Path $secret){Remove-Item -LiteralPath $secret -Force};Output @{ok=$true}}
 'check' {$target=Target $Channel
   $local=Get-LocalRevision
   $source='';$localSha='';$compare=''
   if($local){$localSha=$local.sha;$source=$local.source}
   else{try{$compare=Compare-Files $target.sha}catch{$compare=''}}
   if($localSha){$available=-not $target.sha.StartsWith($localSha)}
   elseif($compare -eq 'same'){$available=$false;$localSha=$target.sha;$source='files'}
   elseif($compare -eq 'different'){$available=$true;$source='files'}
   else{$available=$false}
   $untracked=($source -eq '')
   $localLabel=if($localSha){$localSha.Substring(0,[Math]::Min(12,$localSha.Length))}elseif($compare -eq 'different'){'отличается от GitHub'}else{'не определена'}
   Output @{available=$available;untracked=$untracked;sha=$target.sha;target=$target.label;local=$localLabel;localSource=$source;detail=("GitHub: "+$target.label+"; локальная версия: "+$localLabel)}}
 'stage' {
   $target=Target $Channel
   $dir=Join-Path $work 'staging'
   [IO.Directory]::CreateDirectory($dir)|Out-Null
   $destination=Join-Path $dir ($target.sha+'.zip')
   $temp=Join-Path $env:TEMP ('yorika-'+[guid]::NewGuid().ToString('N')+'.zip')
   try{
     $headers=Request $target.archive -Binary
     Invoke-WebRequest -Uri $target.archive -Headers $headers -OutFile $temp -TimeoutSec 180 -MaximumRedirection 3 -UseBasicParsing
     $downloadSize=(Get-Item -LiteralPath $temp).Length
     if($downloadSize -lt 128 -or $downloadSize -gt 104857600){throw 'Архив пуст или превышает 100 МБ'}
     Add-Type -AssemblyName System.IO.Compression.FileSystem
     $zip=[IO.Compression.ZipFile]::OpenRead($temp)
     try {
       $names=@($zip.Entries|ForEach-Object FullName)
       if(-not($names|Where-Object {$_ -match '^[^/]+/Yorika\.bat\z'}) -or -not($names|Where-Object {$_ -match '^[^/]+/www/index\.html\z'})){throw 'Архив не содержит обязательных файлов'}
       $totalBytes=[long]0
       if($zip.Entries.Count -gt 10000){throw 'В архиве слишком много файлов'}
       foreach($entry in $zip.Entries){
         $name=$entry.FullName
         if([string]::IsNullOrWhiteSpace($name) -or $name.StartsWith('/') -or $name.Contains([char]92) -or $name.Contains(':')){throw 'Опасный путь в архиве'}
         $segments=$name.Split('/')
         if($segments | Where-Object {$_ -eq '..' -or $_ -eq '.'}){throw 'Выход за пределы папки архива'}
         $totalBytes += [long]$entry.Length
         if($totalBytes -gt 536870912){throw 'Распакованные файлы превышают 512 МБ'}
       }
     }finally{$zip.Dispose()}
     $hash=(Get-FileHash -LiteralPath $temp -Algorithm SHA256).Hash
     Move-Item -LiteralPath $temp -Destination $destination -Force
     [IO.File]::WriteAllText((Join-Path $dir ($target.sha+'.json')),(@{sha=$target.sha;hash=$hash}|ConvertTo-Json -Compress),[Text.Encoding]::UTF8)
     Output @{ok=$true;sha=$target.sha;detail=("Архив подготовлен: "+$target.label+"; SHA-256: "+$hash+"; установленная версия не изменена")}
   }finally{if(Test-Path $temp){Remove-Item -LiteralPath $temp -Force}}
 }
}
