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
function Log($msg){try{[IO.File]::AppendAllText($log,("["+(Get-Date -Format o)+"] "+$msg+"`r`n"),[Text.Encoding]::UTF8)}catch{}}
$key=[BitConverter]::ToString(([Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($root.ToLowerInvariant()))),0,12).Replace('-','')
$mutex=[Threading.Mutex]::new($false,('Local\Yorika-'+$key))
if(-not $mutex.WaitOne(0)){Log 'Уже запущена';exit}
$server=$null;$tray=$null;$timer=$null;$url=''
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
     $len=0;$origin='';$host='';$line='';$headers=0
     do{
      $line=$reader.ReadLine();$headers++
      if($headers -gt 60 -or ($null -ne $line -and $line.Length -gt 8192)){throw 'Некорректные заголовки'}
      if($line -match '^Content-Length:\s*(\d+)\s*$'){$len=[int]$Matches[1]}
      if($line -match '^Origin:\s*(.+)$'){$origin=$Matches[1].Trim()}
      if($line -match '^Host:\s*(.+)$'){$host=$Matches[1].Trim()}
     }while($null -ne $line -and $line.Length -gt 0)
     $status='200 OK';$mime='application/json; charset=utf-8';$bytes=[byte[]]@()
     if($path -match '^/api/updates/(settings|token|check|stage)$'){
      $action=$Matches[1]
      try {
       if($host -ne "127.0.0.1:$port" -or $len -gt 2048 -or $len -lt 0){throw 'Запрос отклонён'}
       if($method -ne 'GET' -and ($origin -ne "http://127.0.0.1:$port" -or $method -notin @('POST','DELETE'))){throw 'Доступ запрещён'}
       $body=''
       if($len -gt 0){
        $chars=New-Object char[] $len;$received=0
        while($received -lt $len){$n=$reader.Read($chars,$received,$len-$received);if($n -le 0){throw 'Неполное тело'};$received+=$n}
        $body=-join $chars
       }
       $data=if($body){$body|ConvertFrom-Json}else{$null}
       $engine=Join-Path $PSScriptRoot 'update-engine.ps1'
       if($action -eq 'settings' -and $method -eq 'GET'){$output=& $engine -Action settings}
       elseif($action -eq 'settings' -and $method -eq 'POST'){$output=& $engine -Action save-settings -Channel $data.channel -Interval ([int]$data.interval)}
       elseif($action -eq 'token' -and $method -eq 'POST'){$output=& $engine -Action save-token -Token $data.token}
       elseif($action -eq 'token' -and $method -eq 'DELETE'){$output=& $engine -Action delete-token}
       elseif($action -eq 'check' -and $method -eq 'POST'){$output=& $engine -Action check -Channel $data.channel}
       elseif($action -eq 'stage' -and $method -eq 'POST'){$output=& $engine -Action stage -Channel $data.channel}
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
        $mime=switch($ext){'.html'{'text/html; charset=utf-8'} '.js'{'text/javascript; charset=utf-8'} '.css'{'text/css; charset=utf-8'} '.json'{'application/json; charset=utf-8'} '.svg'{'image/svg+xml'} default{'application/octet-stream'}}
        $bytes=[IO.File]::ReadAllBytes($resolved)
       }catch{$status='404 Not Found';$mime='text/plain; charset=utf-8';$bytes=[Text.Encoding]::UTF8.GetBytes('Не найдено')}
      }
     }
     $header="HTTP/1.1 $status`r`nContent-Type: $mime`r`nContent-Length: $($bytes.Length)`r`nConnection: close`r`nCache-Control: no-store`r`nX-Yorika-App: Yorika`r`nX-Content-Type-Options: nosniff`r`n`r`n"
     $h=[Text.Encoding]::ASCII.GetBytes($header)
     $stream.Write($h,0,$h.Length)
     if($method -ne 'HEAD'){$stream.Write($bytes,0,$bytes.Length)}
     $stream.Flush()
    }finally{$client.Close()}
   }
  }catch{Log ("HTTP: "+$_.Exception.Message)}
 })
 $timer.Start()
 [IO.File]::WriteAllText($ready,$url,[Text.Encoding]::ASCII)
 Log "Server listening at $url"
 [Windows.Forms.Application]::Run()
}catch{Log ("Ошибка запуска: "+$_.Exception.ToString());try{[Windows.Forms.MessageBox]::Show($_.Exception.Message,'Ошибка Yorika')|Out-Null}catch{}}
finally{
 try{if([IO.File]::Exists($ready) -and [IO.File]::ReadAllText($ready).Trim() -eq $url){[IO.File]::Delete($ready)}}catch{}
 if($timer){$timer.Stop();$timer.Dispose()}
 if($tray){$tray.Visible=$false;$tray.Dispose()}
 if($server){$server.Stop()}
 try{$mutex.ReleaseMutex()}catch{};$mutex.Dispose()
}
