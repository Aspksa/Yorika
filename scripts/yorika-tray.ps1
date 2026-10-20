param()
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$site=[IO.Path]::GetFullPath((Join-Path $root 'www'))
$work=Join-Path $root '.yorika'
[IO.Directory]::CreateDirectory($work)|Out-Null
$log=Join-Path $work 'yorika.log'
$ready=Join-Path $work 'ready.url'
# .NET Framework used by Windows PowerShell 5.1 does not expose
# ProcessStartInfo.StandardInputEncoding. Write explicit UTF-8 bytes instead.
function Write-ChildUtf8($process, [string]$value){
 $data=[Text.Encoding]::UTF8.GetBytes($value)
 $process.StandardInput.BaseStream.Write($data,0,$data.Length)
 $process.StandardInput.BaseStream.Flush()
}
function Log($msg){try{[IO.File]::AppendAllText($log,("["+(Get-Date -Format o)+"] "+$msg+"`r`n"),[Text.Encoding]::UTF8)}catch{}}
# python.exe in WindowsApps may be the Microsoft Store stub that only prints "Python was not found".
# Each candidate must report Python 3 before it is used; the py launcher is the fallback.
# The choice is remembered: Microsoft Store Python keeps its own private copy of %LOCALAPPDATA%,
# so switching interpreters between starts made the saved Cloud.ru key and memory seem to vanish.
$pythonCache=@{}
$pythonPin=if($env:LOCALAPPDATA){Join-Path $env:LOCALAPPDATA 'Yorika\python-interpreter.txt'}else{''}
function Test-YorikaPython([string]$file,[string]$prefix){
 try{
  $check=New-Object Diagnostics.ProcessStartInfo
  $check.FileName=$file;$check.Arguments=$prefix+'--version'
  $check.UseShellExecute=$false;$check.CreateNoWindow=$true
  $check.RedirectStandardOutput=$true;$check.RedirectStandardError=$true
  $probe=[Diagnostics.Process]::Start($check)
  try{
   $outTask=$probe.StandardOutput.ReadToEndAsync();$errTask=$probe.StandardError.ReadToEndAsync()
   # A Store Python's first start after an update can take several seconds.
   if(-not $probe.WaitForExit(15000)){try{$probe.Kill()}catch{};return ''}
   $version=($outTask.GetAwaiter().GetResult()+$errTask.GetAwaiter().GetResult()).Trim()
   $exitCode=$probe.ExitCode
  }finally{$probe.Dispose()}
  if($exitCode -eq 0 -and $version -match '^Python 3\.'){return $version}
 }catch{}
 return ''
}
function Get-YorikaPython{
 if($pythonCache.File){return $pythonCache}
 $candidates=@()
 if($pythonPin -and [IO.File]::Exists($pythonPin)){
  try{$saved=[IO.File]::ReadAllLines($pythonPin);if($saved.Length -ge 1 -and $saved[0]){$candidates+=,@($saved[0],$(if($saved.Length -ge 2){$saved[1]}else{''}))}}catch{}
 }
 foreach($c in @(Get-Command python.exe -All -ErrorAction SilentlyContinue)){if($c.Source){$candidates+=,@($c.Source,'')}}
 $py=Get-Command py.exe -ErrorAction SilentlyContinue
 if($py){$candidates+=,@($py.Source,'-3 ')}
 foreach($candidate in $candidates){
  $version=Test-YorikaPython $candidate[0] $candidate[1]
  if($version){
   $pythonCache.File=$candidate[0];$pythonCache.Prefix=$candidate[1];$pythonCache.Source=$candidate[0]
   Log ('Python: '+$version+' '+$candidate[0])
   if($pythonPin){try{[IO.Directory]::CreateDirectory((Split-Path -Parent $pythonPin))|Out-Null;[IO.File]::WriteAllLines($pythonPin,[string[]]@($candidate[0],$candidate[1]))}catch{}}
   return $pythonCache
  }
 }
 Log 'Python 3 не найден: python.exe и py.exe недоступны'
 return $null
}
# Copies a Cloud.ru key that Microsoft Store Python saved in its private %LOCALAPPDATA% to the
# real one when it is newer, so every interpreter and every release sees the same key.
function Sync-StorePythonSecrets{
 if(-not $env:LOCALAPPDATA){return}
 $real=Join-Path $env:LOCALAPPDATA 'Yorika\secrets\cloud-ru.dpapi'
 $packages=Join-Path $env:LOCALAPPDATA 'Packages'
 if(-not [IO.Directory]::Exists($packages)){return}
 $newest=$null
 foreach($dir in @(Get-ChildItem -LiteralPath $packages -Directory -Filter 'PythonSoftwareFoundation.Python.*' -ErrorAction SilentlyContinue)){
  $copy=Join-Path $dir.FullName 'LocalCache\Local\Yorika\secrets\cloud-ru.dpapi'
  if([IO.File]::Exists($copy)){$info=Get-Item -LiteralPath $copy;if(-not $newest -or $info.LastWriteTimeUtc -gt $newest.LastWriteTimeUtc){$newest=$info}}
 }
 if(-not $newest){return}
 if([IO.File]::Exists($real) -and (Get-Item -LiteralPath $real).LastWriteTimeUtc -ge $newest.LastWriteTimeUtc){return}
 try{
  [IO.Directory]::CreateDirectory((Split-Path -Parent $real))|Out-Null
  $temp=$real+'.tmp';[IO.File]::Copy($newest.FullName,$temp,$true)
  if([IO.File]::Exists($real)){[IO.File]::Replace($temp,$real,$null)}else{[IO.File]::Move($temp,$real)}
  Log 'Ключ Cloud.ru из хранилища Microsoft Store Python перенесён в общий профиль'
 }catch{Log ('Перенос ключа Cloud.ru: '+$_.Exception.Message)}
}
$key=[BitConverter]::ToString(([Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($root.ToLowerInvariant()))),0,12).Replace('-','')
$mutex=[Threading.Mutex]::new($false,('Local\Yorika-'+$key))
if(-not $mutex.WaitOne(0)){Log 'Уже запущена';exit}
# Model replies can take a minute. They run in a background runspace so the
# tray keeps serving pages, settings and history while Yorika is answering.
$chatWorker=@'
param($client,$psi,$body,$mode,$log)
function Note($msg){try{[IO.File]::AppendAllText($log,("["+(Get-Date -Format o)+"] "+$msg+"`r`n"),[Text.Encoding]::UTF8)}catch{}}
function Send($target,[byte[]]$data){$target.Write($data,0,$data.Length)}
# Python errors are our own short English markers; only fixed Russian texts reach the browser.
function Explain([string]$detail){
 if($detail -match 'key not configured'){return 'Cloud.ru: сначала сохраните API-ключ в Настройках'}
 if($detail -match '^Cloud\.ru HTTP [0-9x]+: [^\r\n]{1,80}\z'){return $detail}
 if($detail -match 'API unavailable'){return 'Cloud.ru: нет соединения с API; проверьте сеть и прокси'}
 if($detail -match 'Empty Cloud\.ru response'){return 'Cloud.ru: модель вернула пустой ответ; попробуйте ещё раз или выберите другую модель'}
 if($detail -match 'timed out|timeout'){return 'Cloud.ru: превышено время ожидания ответа'}
 return 'Cloud.ru: ответ не получен; проверьте ID модели и подключение в Настройках'
}
$stream=$client.GetStream();$proc=$null
try{
 $client.SendTimeout=10000
 $proc=[Diagnostics.Process]::Start($psi)
 $payload=[Text.Encoding]::UTF8.GetBytes($body)
 $proc.StandardInput.BaseStream.Write($payload,0,$payload.Length);$proc.StandardInput.BaseStream.Flush();$proc.StandardInput.Close()
 $stderrTask=$proc.StandardError.ReadToEndAsync()
 if($mode -eq 'stream'){
  $head="HTTP/1.1 200 OK"+"`r`n"+"Content-Type: application/x-ndjson; charset=utf-8"+"`r`n"+"Transfer-Encoding: chunked"+"`r`n"+"Connection: close"+"`r`n"+"Cache-Control: no-store"+"`r`n"+"X-Content-Type-Options: nosniff"+"`r`n`r`n"
  Send $stream ([Text.Encoding]::ASCII.GetBytes($head));$stream.Flush()
  $deadline=[DateTime]::UtcNow.AddSeconds(120)
  while($true){
   $lineTask=$proc.StandardOutput.ReadLineAsync()
   $remaining=[int][Math]::Max(1,($deadline-[DateTime]::UtcNow).TotalMilliseconds)
   if(-not $lineTask.Wait($remaining)){
    try{$proc.Kill()}catch{}
    $line='{"type":"error","message":"Cloud.ru: превышено время ожидания ответа"}'
   }else{$line=$lineTask.Result}
   if($null -eq $line){break}
   if($line.Length -gt 12000){throw 'Stream line too long'}
   $chunk=[Text.Encoding]::UTF8.GetBytes($line+"`n")
   Send $stream ([Text.Encoding]::ASCII.GetBytes(("{0:x}" -f $chunk.Length)+"`r`n"));Send $stream $chunk;Send $stream ([byte[]](13,10));$stream.Flush()
   if($line.StartsWith('{"type":"error","message":"Cloud.ru: превышено')){break}
  }
  [void]$proc.WaitForExit(1500)
  Send $stream ([Text.Encoding]::ASCII.GetBytes("0`r`n`r`n"));$stream.Flush()
 }else{
  $status='200 OK'
  $stdoutTask=$proc.StandardOutput.ReadToEndAsync()
  if(-not $proc.WaitForExit(90000)){
   try{$proc.Kill()}catch{}
   $status='504 Gateway Timeout';$output=(@{error=$(if($mode -eq 'training'){'Истекло время ожидания'}else{'Cloud.ru: превышено время ожидания ответа'})}|ConvertTo-Json -Compress)
  }else{
   $output=$stdoutTask.GetAwaiter().GetResult().Trim()
   if($proc.ExitCode -ne 0){
    $detail='';try{$detail=[string]($output|ConvertFrom-Json).error}catch{}
    if($mode -eq 'training'){
     # training-center.py reports short Russian texts meant for the page.
     $reason=if($detail -and $detail.Length -lt 170){$detail}else{'Операция обучения не выполнена'}
     $status='400 Bad Request';$output=(@{error=$reason}|ConvertTo-Json -Compress)
     Note ('Training: '+$reason)
    }else{
    $status='503 Service Unavailable';$output=(@{error=(Explain $detail)}|ConvertTo-Json -Compress)
    Note ('Cloud.ru response failed: '+(Explain $detail))
    }
   }
  }
  $bytes=[Text.Encoding]::UTF8.GetBytes($output)
  $header="HTTP/1.1 $status`r`nContent-Type: application/json; charset=utf-8`r`nContent-Length: $($bytes.Length)`r`nConnection: close`r`nCache-Control: no-store`r`nX-Yorika-App: Yorika`r`nX-Content-Type-Options: nosniff`r`n`r`n"
  Send $stream ([Text.Encoding]::ASCII.GetBytes($header));Send $stream $bytes;$stream.Flush()
 }
}catch{
 $reason=$_.Exception.Message
 if($reason -match 'транспортное соединение|transport connection|forcibly closed|разорвала установленное подключение|broken pipe'){Note 'Cloud.ru streaming client disconnected'}
 else{Note ('Cloud.ru chat worker failed: '+$reason)}
}finally{
 if($proc){try{if(-not $proc.HasExited){$proc.Kill()}}catch{};$proc.Dispose()}
 try{$client.Close()}catch{}
}
'@
$chatPool=[runspacefactory]::CreateRunspacePool(1,4)
$chatPool.Open()
$chatJobs=New-Object Collections.ArrayList
# Hands the open connection to a background runspace; the caller must not close it.
function Start-ChatWorker($client,$psi,[string]$body,[string]$mode){
 $job=[PowerShell]::Create();$job.RunspacePool=$chatPool
 [void]$job.AddScript($chatWorker).AddArgument($client).AddArgument($psi).AddArgument($body).AddArgument($mode).AddArgument($log)
 [void]$chatJobs.Add(@{ps=$job;handle=$job.BeginInvoke()})
}
function Clear-ChatWorkers{
 foreach($item in @($chatJobs)){
  if($item.handle.IsCompleted){
   try{[void]$item.ps.EndInvoke($item.handle)}catch{Log ('Chat worker: '+$_.Exception.Message)}
   $item.ps.Dispose();$chatJobs.Remove($item)
  }
 }
}
$server=$null;$tray=$null;$timer=$null;$retire=$null;$url=''
Sync-StorePythonSecrets
try{
 $server=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,0)
 $server.Start(16)
 $port=([Net.IPEndPoint]$server.LocalEndpoint).Port
 $url="http://127.0.0.1:$port/"
 $menu=New-Object Windows.Forms.ContextMenuStrip
 $open=$menu.Items.Add('Открыть Yorika')
 $local=$menu.Items.Add("Локальный адрес: $url");$local.Enabled=$false
 $copy=$menu.Items.Add('Скопировать адрес сайта')
 $state=$menu.Items.Add('Состояние системы')
 $logs=$menu.Items.Add('Открыть журнал ошибок')
 $quit=$menu.Items.Add('Выйти из Yorika')
 $tray=New-Object Windows.Forms.NotifyIcon
 $tray.Icon=[Drawing.SystemIcons]::Application
 $tray.Text='Yorika'
 $tray.ContextMenuStrip=$menu;$tray.Visible=$true
 $open.add_Click({Start-Process $url})
 $tray.add_DoubleClick({Start-Process $url})
 $copy.add_Click({[Windows.Forms.Clipboard]::SetText($url)})
 $state.add_Click({[Windows.Forms.MessageBox]::Show("Yorika работает`nАдрес: $url",'Yorika')|Out-Null})
 $logs.add_Click({Start-Process notepad.exe -ArgumentList ('"'+$log+'"')})
 $quit.add_Click({[Windows.Forms.Application]::ExitThread()})
 $timer=New-Object Windows.Forms.Timer;$timer.Interval=100
 $timer.add_Tick({
  $stopAfterReply=$false
  Clear-ChatWorkers
  try {
   $count=0
   while($server.Pending() -and $count -lt 5){
    $count++
    $client=$server.AcceptTcpClient()
    try {
     $client.ReceiveTimeout=2000;$client.SendTimeout=2000
     $stream=$client.GetStream()
     $reader=[IO.StreamReader]::new($stream,[Text.Encoding]::UTF8,$false,4096,$true)
     $first=$reader.ReadLine()
     if(-not $first -or $first.Length -gt 4096){continue}
     $parts=$first.Split(' ')
     if($parts.Length -lt 3){continue}
     $method=$parts[0];$path=$parts[1].Split('?')[0]
     $len=0;$origin='';$requestHost='';$line='';$headers=0
     do{
      $line=$reader.ReadLine();$headers++
      if($headers -gt 60 -or ($null -ne $line -and $line.Length -gt 8192)){throw 'Некорректные заголовки'}
      if($line -match '^Content-Length:\s*(\d+)\s*\z'){$len=if($Matches[1].Length -gt 9){[int]::MaxValue}else{[int]$Matches[1]}}
      if($line -match '^Origin:\s*(.+)\z'){$origin=$Matches[1].Trim()}
      if($line -match '^Host:\s*(.+)\z'){$requestHost=$Matches[1].Trim()}
     }while($null -ne $line -and $line.Length -gt 0)
     $status='200 OK';$mime='application/json; charset=utf-8';$bytes=[byte[]]@();$streamHandled=$false;$handedOff=$false
     if($path -eq '/api/chat/history'){
      $mime='application/json; charset=utf-8'
      try{
       if($requestHost -ne "127.0.0.1:$port"){throw 'Неверный адрес'}
       if($method -notin @('GET','POST')){throw 'Неверный метод'}
       if($method -eq 'POST' -and $origin -ne "http://127.0.0.1:$port"){throw 'Доступ запрещён'}
       if($len -gt 262144 -or $len -lt 0){throw 'Слишком большой запрос'}
       if($method -eq 'POST' -and $len -le 0){throw 'Пустой запрос'}
       $python=Get-YorikaPython
       if(-not $python){$status='503 Service Unavailable';throw 'Python 3 не найден. Установите Python 3 с python.org и перезапустите Yorika'}
       $action=if($method -eq 'GET'){'get'}else{'put'}
       $body=''
       if($method -eq 'POST'){
        $builder=New-Object Text.StringBuilder
        $received=0
        while($received -lt $len){
         $chars=New-Object char[] ([Math]::Min(4096,$len-$received))
         $n=$reader.Read($chars,0,$chars.Length)
         if($n -le 0){throw 'Неполное тело'}
         $chunk=[string]::new($chars,0,$n)
         [void]$builder.Append($chunk)
         $received+=[Text.Encoding]::UTF8.GetByteCount($chunk)
        }
        if($received -ne $len){throw 'Неверная длина'}
        $body=$builder.ToString()
       }
       $psi=New-Object Diagnostics.ProcessStartInfo
       $psi.FileName=$python.Source
       $psi.Arguments=($python.Prefix+'"' + (Join-Path $root 'scripts\chat-store.py') + '" ' + $action)
       $psi.UseShellExecute=$false
       $psi.CreateNoWindow=$true
       $psi.RedirectStandardInput=$true
       $psi.RedirectStandardOutput=$true
       $psi.RedirectStandardError=$true
       $psi.StandardOutputEncoding=[Text.Encoding]::UTF8
       $psi.EnvironmentVariables['PYTHONIOENCODING']='utf-8:strict'
       $proc=[Diagnostics.Process]::Start($psi)
       try{
        if($method -eq 'POST'){Write-ChildUtf8 $proc $body}
        $proc.StandardInput.Close()
        $output=$proc.StandardOutput.ReadToEnd()
        $errorOutput=$proc.StandardError.ReadToEnd()
        if(-not $proc.WaitForExit(5000)){try{$proc.Kill()}catch{};throw 'Истекло время ожидания памяти'}
        if($proc.ExitCode -ne 0){throw 'Ошибка хранилища'}
        $bytes=[Text.Encoding]::UTF8.GetBytes($output.Trim())
       }finally{$proc.Dispose()}
      }catch{
       if($status -eq '200 OK'){$status='400 Bad Request'}
       $bytes=[Text.Encoding]::UTF8.GetBytes((@{error=$_.Exception.Message}|ConvertTo-Json -Compress))
       Log ('Chat memory: '+$_.Exception.Message)
      }
     }elseif($path -match '^/api/cloud-ru/(status|models|save|check|delete|diagnostics|persona-status|persona-config|persona-delete|memory-status|memory-set|memory-delete|memory-edit)\z'){
      $action=$Matches[1]
      try{
       if($requestHost -ne "127.0.0.1:$port"){throw 'Недопустимый Host'}
       if($action -in @('status','models','diagnostics','persona-status','memory-status')){
        if($method -ne 'GET'){throw 'Недопустимый метод'}
       }elseif($method -ne 'POST' -or $origin -ne "http://127.0.0.1:$port"){
        throw 'Доступ запрещён'
       }
       if($len -lt 0 -or $len -gt 16384){throw 'Неверная длина'}
       $body=''
       if($len -gt 0){
        $builder=New-Object Text.StringBuilder;$received=0
        while($received -lt $len){
         $chars=New-Object char[] ([Math]::Min(1024,$len-$received))
         $n=$reader.Read($chars,0,$chars.Length)
         if($n -le 0){throw 'Неполный запрос'}
         $chunk=[string]::new($chars,0,$n)
         [void]$builder.Append($chunk)
         $received+=[Text.Encoding]::UTF8.GetByteCount($chunk)
        }
        if($received -ne $len){throw 'Неверная длина'}
        $body=$builder.ToString()
       }
       if($action -in @('save','persona-config','persona-delete','memory-set','memory-delete','memory-edit') -and -not $body){throw 'Настройки не переданы'}
       $python=Get-YorikaPython
       if(-not $python){$status='503 Service Unavailable';throw 'Python 3 не найден. Установите Python 3 с python.org и перезапустите Yorika'}
       $psi=New-Object Diagnostics.ProcessStartInfo
       $psi.FileName=$python.Source
       $psi.Arguments=($python.Prefix+'"' + (Join-Path $root 'scripts\cloud-ru-settings.py') + '" ' + $action)
       $psi.UseShellExecute=$false;$psi.CreateNoWindow=$true
       $psi.RedirectStandardInput=$true;$psi.RedirectStandardOutput=$true;$psi.RedirectStandardError=$true
       $psi.StandardOutputEncoding=[Text.Encoding]::UTF8
       $psi.EnvironmentVariables['PYTHONIOENCODING']='utf-8:strict'
       $proc=[Diagnostics.Process]::Start($psi)
       try{
        if($action -in @('save','persona-config','persona-delete','memory-set','memory-delete','memory-edit')){Write-ChildUtf8 $proc $body}
        $proc.StandardInput.Close()
        $stdoutTask=$proc.StandardOutput.ReadToEndAsync()
        $stderrTask=$proc.StandardError.ReadToEndAsync()
        if(-not $proc.WaitForExit(28000)){try{$proc.Kill()}catch{};throw 'Истекло время ожидания'}
        $output=$stdoutTask.GetAwaiter().GetResult()
        $null=$stderrTask.GetAwaiter().GetResult()
        if($proc.ExitCode -ne 0){
         $status='400 Bad Request'
         $remote=$null
         try{$remote=$output|ConvertFrom-Json}catch{}
         if($remote -and $remote.error -and ([string]$remote.error).Length -lt 170){
          throw ([string]$remote.error)
         }
         throw 'Операция Cloud.ru не выполнена'
        }
        $bytes=[Text.Encoding]::UTF8.GetBytes($output.Trim())
       }finally{$proc.Dispose()}
      }catch{
       if($status -eq '200 OK'){$status='400 Bad Request'}
       $bytes=[Text.Encoding]::UTF8.GetBytes((@{error=$_.Exception.Message}|ConvertTo-Json -Compress))
       Log ('Cloud.ru settings failed: '+$action)
      }
     }elseif($path -eq '/api/chat/stream'){
      if($requestHost -ne "127.0.0.1:$port" -or $origin -ne "http://127.0.0.1:$port" -or $method -ne 'POST' -or $len -lt 1 -or $len -gt 4096){
       $status='403 Forbidden';$bytes=[Text.Encoding]::UTF8.GetBytes('{"error":"Forbidden"}')
      }else{
       $builder=New-Object Text.StringBuilder;$received=0
       while($received -lt $len){
        $chars=New-Object char[] ([Math]::Min(1024,$len-$received))
        $n=$reader.Read($chars,0,$chars.Length)
        if($n -le 0){throw 'Incomplete request'}
        $part=[string]::new($chars,0,$n);[void]$builder.Append($part)
        $received+=[Text.Encoding]::UTF8.GetByteCount($part)
       }
       if($received -ne $len){throw 'Invalid request size'}
       $data=$builder.ToString()|ConvertFrom-Json
       if([string]::IsNullOrWhiteSpace([string]$data.query) -or ([string]$data.query).Length -gt 4000){throw 'Invalid query'}
       $python=Get-YorikaPython
       if(-not $python){
        $status='503 Service Unavailable'
        $bytes=[Text.Encoding]::UTF8.GetBytes((@{error='Python 3 не найден. Установите Python 3 с python.org и перезапустите Yorika'}|ConvertTo-Json -Compress))
       }else{
        $psi=New-Object Diagnostics.ProcessStartInfo
        $psi.FileName=$python.Source
        $psi.Arguments=($python.Prefix+'"' + (Join-Path $root 'scripts\cloud-ru-stream.py') + '"')
        $psi.UseShellExecute=$false;$psi.CreateNoWindow=$true
        $psi.RedirectStandardInput=$true;$psi.RedirectStandardOutput=$true;$psi.RedirectStandardError=$true
        $psi.StandardOutputEncoding=[Text.Encoding]::UTF8
        $psi.EnvironmentVariables['PYTHONIOENCODING']='utf-8:strict'
        Start-ChatWorker $client $psi ($builder.ToString()) 'stream'
        $streamHandled=$true;$handedOff=$true
       }
      }
     }elseif($path -eq '/api/chat/respond'){
      try{
       if($requestHost -ne "127.0.0.1:$port" -or $origin -ne "http://127.0.0.1:$port" -or $method -ne 'POST'){throw 'Доступ запрещён'}
       if($len -lt 1 -or $len -gt 4096){throw 'Неверная длина запроса'}
       $builder=New-Object Text.StringBuilder;$received=0
       while($received -lt $len){
        $chars=New-Object char[] ([Math]::Min(1024,$len-$received))
        $n=$reader.Read($chars,0,$chars.Length)
        if($n -le 0){throw 'Неполный запрос'}
        $chunk=[string]::new($chars,0,$n)
        [void]$builder.Append($chunk)
        $received+=[Text.Encoding]::UTF8.GetByteCount($chunk)
       }
       if($received -ne $len){throw 'Неверная длина'}
       $body=$builder.ToString()
       $request=$body|ConvertFrom-Json
       $question=[string]$request.query
       if([string]::IsNullOrWhiteSpace($question) -or $question.Length -gt 4000){throw 'Неверный запрос'}
       $python=Get-YorikaPython
       if(-not $python){$status='503 Service Unavailable';throw 'Python 3 не найден. Установите Python 3 с python.org и перезапустите Yorika'}
       $psi=New-Object Diagnostics.ProcessStartInfo
       $psi.FileName=$python.Source
       $psi.Arguments=($python.Prefix+'"' + (Join-Path $root 'scripts\cloud-ru-model.py') + '"')
       $psi.UseShellExecute=$false
       $psi.CreateNoWindow=$true
       $psi.RedirectStandardInput=$true;$psi.RedirectStandardOutput=$true;$psi.RedirectStandardError=$true
       $psi.StandardOutputEncoding=[Text.Encoding]::UTF8
       $psi.EnvironmentVariables['PYTHONIOENCODING']='utf-8:strict'
       Start-ChatWorker $client $psi $body 'json'
       $streamHandled=$true;$handedOff=$true
      }catch{
       if($status -eq '200 OK'){$status='400 Bad Request'}
       $bytes=[Text.Encoding]::UTF8.GetBytes((@{error=$_.Exception.Message}|ConvertTo-Json -Compress))
       Log ('Cloud.ru response failed: '+$_.Exception.Message)
      }
     }elseif($path -eq '/api/memory/recall'){
      try{
       if($requestHost -ne "127.0.0.1:$port" -or $origin -ne "http://127.0.0.1:$port" -or $method -ne 'POST'){throw 'Доступ запрещён'}
       if($len -lt 1 -or $len -gt 4096){throw 'Неверная длина запроса'}
       $builder=New-Object Text.StringBuilder
       $received=0
       while($received -lt $len){
        $chars=New-Object char[] ([Math]::Min(1024,$len-$received))
        $n=$reader.Read($chars,0,$chars.Length)
        if($n -le 0){throw 'Неполный запрос'}
        $chunk=[string]::new($chars,0,$n)
        [void]$builder.Append($chunk)
        $received+=[Text.Encoding]::UTF8.GetByteCount($chunk)
       }
       if($received -ne $len){throw 'Неверная длина'}
       $data=$builder.ToString()|ConvertFrom-Json
       $text=[string]$data.query
       if([string]::IsNullOrWhiteSpace($text) -or $text.Length -gt 4000){throw 'Неверный запрос'}
       $python=Get-YorikaPython
       if(-not $python){$status='503 Service Unavailable';throw 'Python 3 не найден. Установите Python 3 с python.org и перезапустите Yorika'}
       $psi=New-Object Diagnostics.ProcessStartInfo
       $psi.FileName=$python.Source
       $psi.Arguments=($python.Prefix+'"' + (Join-Path $root 'scripts\recall-memory.py') + '"')
       $psi.UseShellExecute=$false
       $psi.CreateNoWindow=$true
       $psi.RedirectStandardInput=$true
       $psi.RedirectStandardOutput=$true
       $psi.RedirectStandardError=$true
       $psi.StandardOutputEncoding=[Text.Encoding]::UTF8
       $psi.EnvironmentVariables['PYTHONIOENCODING']='utf-8:strict'
       $proc=[Diagnostics.Process]::Start($psi)
       try{
        Write-ChildUtf8 $proc $text
        $proc.StandardInput.Close()
        $output=$proc.StandardOutput.ReadToEnd()
        $errorOutput=$proc.StandardError.ReadToEnd()
        if(-not $proc.WaitForExit(5000)){try{$proc.Kill()}catch{};throw 'Истекло время поиска'}
        if($proc.ExitCode -ne 0){throw 'Ошибка поиска памяти'}
        $bytes=[Text.Encoding]::UTF8.GetBytes($output.Trim())
       }finally{$proc.Dispose()}
      }catch{
       if($status -eq '200 OK'){$status='400 Bad Request'}
       $bytes=[Text.Encoding]::UTF8.GetBytes((@{error=$_.Exception.Message}|ConvertTo-Json -Compress))
       Log ('Memory recall: '+$_.Exception.Message)
      }
     }elseif($path -match '^/api/training/(status|probe|install-torch|data-check|folder|open-folder|start|control|activate|rollback|compare|stop-all|sl-status|sl-collect-setting|sl-collect|sl-list|sl-rate|sl-delete|sl-export|sl-dismiss|text-approve|teacher-status|teacher-limits|teacher-estimate|teacher-start|teacher-stop|teacher-accept|night-status|night-settings|series|sl-pack-preview|sl-pack-add|blind-start|blind-vote|blind-results|teacher-models|brain-status|chat-engine|continual-settings|continual-now|evolve|merge|compress|grow|curiosity-now|think|plan-start|schedule-set|autopilot|programs-learn|sim-now|introspect|autopilot-options|tidy|selfcheck|harvest|exchange|screen-help|diary-write|rebirth|extinction-preview|extinction)\z'){
      # The «Обучение» page. Loading PyTorch can take many seconds, so every action runs in the
      # background pool; training itself is a detached process started by training-center.py.
      $action=$Matches[1]
      try{
       if($requestHost -ne "127.0.0.1:$port"){throw 'Недопустимый Host'}
       if($action -in @('status','sl-status','teacher-status','night-status','brain-status')){if($method -ne 'GET'){throw 'Недопустимый метод'}}
       elseif($method -ne 'POST' -or $origin -ne "http://127.0.0.1:$port"){throw 'Доступ запрещён'}
       if($len -lt 0 -or $len -gt 16384){throw 'Неверная длина'}
       $body=''
       if($len -gt 0){
        $builder=New-Object Text.StringBuilder;$received=0
        while($received -lt $len){
         $chars=New-Object char[] ([Math]::Min(1024,$len-$received))
         $n=$reader.Read($chars,0,$chars.Length)
         if($n -le 0){throw 'Неполный запрос'}
         $chunk=[string]::new($chars,0,$n)
         [void]$builder.Append($chunk)
         $received+=[Text.Encoding]::UTF8.GetByteCount($chunk)
        }
        if($received -ne $len){throw 'Неверная длина'}
        $body=$builder.ToString()
       }
       $python=Get-YorikaPython
       if(-not $python){$status='503 Service Unavailable';throw 'Python 3 не найден. Установите Python 3 с python.org и перезапустите Yorika'}
       $psi=New-Object Diagnostics.ProcessStartInfo
       $psi.FileName=$python.Source
       $psi.Arguments=($python.Prefix+'"' + (Join-Path $root 'scripts\training-center.py') + '" ' + $action)
       $psi.UseShellExecute=$false;$psi.CreateNoWindow=$true
       $psi.RedirectStandardInput=$true;$psi.RedirectStandardOutput=$true;$psi.RedirectStandardError=$true
       $psi.StandardOutputEncoding=[Text.Encoding]::UTF8
       $psi.EnvironmentVariables['PYTHONIOENCODING']='utf-8:strict'
       Start-ChatWorker $client $psi $body 'training'
       $streamHandled=$true;$handedOff=$true
      }catch{
       if($status -eq '200 OK'){$status='400 Bad Request'}
       $bytes=[Text.Encoding]::UTF8.GetBytes((@{error=$_.Exception.Message}|ConvertTo-Json -Compress))
       Log ('Training: '+$_.Exception.Message)
      }
     }elseif($path -match '^/api/updates/(settings|token|check|stage|apply)\z'){
      $action=$Matches[1]
      try {
       if($requestHost -ne "127.0.0.1:$port" -or $len -gt 2048 -or $len -lt 0){throw 'Запрос отклонён'}
       if($method -ne 'GET' -and ($origin -ne "http://127.0.0.1:$port" -or $method -notin @('POST','DELETE'))){throw 'Доступ запрещён'}
       $body=''
       if($len -gt 0){
        # Content-Length counts UTF-8 bytes; each char is at least one byte, so never over-read.
        $text=New-Object Text.StringBuilder;$received=0
        while($received -lt $len){$chars=New-Object char[] ($len-$received);$n=$reader.Read($chars,0,$chars.Length);if($n -le 0){throw 'Неполное тело'};$part=[string]::new($chars,0,$n);[void]$text.Append($part);$received+=[Text.Encoding]::UTF8.GetByteCount($part)}
        $body=$text.ToString()
       }
       $data=if($body){$body|ConvertFrom-Json}else{$null}
       $engine=Join-Path $PSScriptRoot 'update-engine.ps1'
       if($action -eq 'settings' -and $method -eq 'GET'){$output=& $engine -Action settings}
       elseif($action -eq 'settings' -and $method -eq 'POST'){$output=& $engine -Action save-settings -Channel $data.channel -Interval ([int]$data.interval)}
       elseif($action -eq 'token' -and $method -eq 'POST'){$output=& $engine -Action save-token -Token $data.token}
       elseif($action -eq 'token' -and $method -eq 'DELETE'){$output=& $engine -Action delete-token}
       elseif($action -eq 'check' -and $method -eq 'POST'){$output=& $engine -Action check -Channel $data.channel}
       elseif($action -eq 'stage' -and $method -eq 'POST'){$output=& $engine -Action stage -Channel $data.channel}
       elseif($action -eq 'apply' -and $method -eq 'POST'){
        $sha=[string]$data.sha
        if(-not $sha -or $sha.Length -ne 40 -or $sha -cmatch '[^0-9a-f]'){throw 'Неверная версия'}
        $installer=Join-Path $PSScriptRoot 'install-release.ps1'
        & $installer -Root $root -Sha $sha
        $result=Join-Path $work 'install-result.json'
        if(-not(Test-Path -LiteralPath $result)){throw 'Нет результата установки'}
        $outcome=Get-Content -LiteralPath $result -Raw -Encoding UTF8|ConvertFrom-Json
        if(-not $outcome.success){throw ([string]$outcome.message)}
        $output=$outcome|ConvertTo-Json -Compress
        # The new release now serves its own copy; this one closes once the reply is sent.
        $stopAfterReply=$true
       }
       else{throw 'Метод запрещён'}
       $bytes=[Text.Encoding]::UTF8.GetBytes([string]$output)
      }catch{$status='400 Bad Request';$bytes=[Text.Encoding]::UTF8.GetBytes((@{error=$_.Exception.Message}|ConvertTo-Json -Compress));Log $_.Exception.Message}
     }else{
      if($method -notin @('GET','HEAD')){$status='405 Method Not Allowed';$bytes=[Text.Encoding]::UTF8.GetBytes('Недопустимый метод')}
      else{
       try{
        $relative=[Uri]::UnescapeDataString($path).TrimStart('/').Replace('/',[IO.Path]::DirectorySeparatorChar)
        if(-not $relative){$relative='index.html'}
        $resolved=[IO.Path]::GetFullPath((Join-Path $site $relative))
        $prefix=$site.TrimEnd([IO.Path]::DirectorySeparatorChar)+[IO.Path]::DirectorySeparatorChar
        if(-not $resolved.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase) -or -not [IO.File]::Exists($resolved)){throw 'Не найдено'}
        $ext=[IO.Path]::GetExtension($resolved).ToLowerInvariant()
        $mime=switch($ext){'.html'{'text/html; charset=utf-8'} '.js'{'text/javascript; charset=utf-8'} '.css'{'text/css; charset=utf-8'} '.json'{'application/json; charset=utf-8'} '.svg'{'image/svg+xml'} '.webp'{'image/webp'} '.png'{'image/png'} default{'application/octet-stream'}}
        $bytes=[IO.File]::ReadAllBytes($resolved)
       }catch{$status='404 Not Found';$mime='text/plain; charset=utf-8';$bytes=[Text.Encoding]::UTF8.GetBytes('Не найдено')}
      }
     }
     if(-not $streamHandled){
     $header="HTTP/1.1 $status`r`nContent-Type: $mime`r`nContent-Length: $($bytes.Length)`r`nConnection: close`r`nCache-Control: no-store`r`nX-Yorika-App: Yorika`r`nX-Content-Type-Options: nosniff`r`n`r`n"
     $h=[Text.Encoding]::ASCII.GetBytes($header)
     $stream.Write($h,0,$h.Length)
     if($method -ne 'HEAD'){$stream.Write($bytes,0,$bytes.Length)}
     $stream.Flush()
     }
    }finally{if(-not $handedOff){$client.Close()}}
   }
  }catch{
   $reason=$_.Exception.Message
   if($reason -match "транспортное соединение|transport connection|forcibly closed|разорвала установленное подключение|broken pipe"){
    Log "HTTP: browser disconnected"
   }else{Log ("HTTP: "+$reason)}
  }
  if($stopAfterReply){Log 'Новая версия запущена, эта копия закрывается';[Windows.Forms.Application]::ExitThread()}
 })
 $timer.Start()
 # Releases before this fix keep serving after installing a new one. Once that install has
 # finished, stop any sibling copy whose launcher now redirects here.
 $retire=New-Object Windows.Forms.Timer;$retire.Interval=20000
 $retire.add_Tick({
  $retire.Stop()
  try{
   foreach($dir in @(Get-ChildItem -LiteralPath (Split-Path -Parent $root) -Directory -ErrorAction SilentlyContinue)){
    $pointer=Join-Path $dir.FullName '.yorika\active-install.json'
    if($dir.FullName -eq $root -or -not(Test-Path -LiteralPath $pointer)){continue}
    try{$target=[IO.Path]::GetFullPath([string](Get-Content -LiteralPath $pointer -Raw -Encoding UTF8|ConvertFrom-Json).path)}catch{continue}
    if($target -ne $root){continue}
    $oldTray=Join-Path $dir.FullName 'scripts\yorika-tray.ps1'
    foreach($p in @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue)){
     if($p.CommandLine -and $p.CommandLine.IndexOf($oldTray,[StringComparison]::OrdinalIgnoreCase) -ge 0){
      Log ('Остановлена прежняя копия: '+$dir.FullName)
      Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
     }
    }
   }
  }catch{Log ('Остановка прежней копии: '+$_.Exception.Message)}
 })
 $retire.Start()
 [IO.File]::WriteAllText($ready,$url,[Text.Encoding]::ASCII)
 Log "Server listening at $url"
 [Windows.Forms.Application]::Run()
}catch{Log ("Ошибка запуска: "+$_.Exception.ToString());try{[Windows.Forms.MessageBox]::Show($_.Exception.Message,'Ошибка Yorika')|Out-Null}catch{}}
finally{
 try{if([IO.File]::Exists($ready) -and [IO.File]::ReadAllText($ready).Trim() -eq $url){[IO.File]::Delete($ready)}}catch{}
 if($timer){$timer.Stop();$timer.Dispose()}
 if($retire){$retire.Stop();$retire.Dispose()}
 if($tray){$tray.Visible=$false;$tray.Dispose()}
 if($server){$server.Stop()}
 if($chatPool){try{$chatPool.Close();$chatPool.Dispose()}catch{}}
 try{$mutex.ReleaseMutex()}catch{};$mutex.Dispose()
}
