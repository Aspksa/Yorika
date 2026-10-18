param([string]$ProjectRoot)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# No Python, Node, pip, or external packages are required.
# Portable: derive project root from this script, ignoring caller-supplied paths.
$ProjectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$siteRoot = [IO.Path]::GetFullPath((Join-Path $ProjectRoot 'www'))
$logDir = Join-Path $ProjectRoot '.yorika'
[IO.Directory]::CreateDirectory($logDir) | Out-Null
$logPath = Join-Path $logDir 'yorika.log'
$readyPath = Join-Path $logDir 'ready.url'
function Log([string]$message) {
  try { [IO.File]::AppendAllText($logPath, ("[{0}] {1}`r`n" -f (Get-Date -Format o), $message), [Text.Encoding]::UTF8) } catch {}
}
$keyBytes = [Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($ProjectRoot.ToLowerInvariant()))
$instanceKey = [BitConverter]::ToString($keyBytes, 0, 12).Replace('-', '')
$mutex = [System.Threading.Mutex]::new($false, ('Local\Yorika-' + $instanceKey))
if (-not $mutex.WaitOne(0)) {
  Log 'Yorika is already running. The existing instance may be in another folder.'
  Write-Host '[YORIKA] Yorika is already running.'
  exit 0
}
$listener = $null
$tray = $null
$timer = $null
try {
  [IO.Directory]::CreateDirectory($siteRoot) | Out-Null
  # Port 0 lets Windows select an available port and holds the socket open.
  $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
  $listener.Start(25)
  $port = ([Net.IPEndPoint]$listener.LocalEndpoint).Port
  $url = "http://127.0.0.1:$port/"
  Log "Server listening at $url"

  $menu = New-Object System.Windows.Forms.ContextMenuStrip
  $openItem = $menu.Items.Add('Открыть Yorika')
  $addressItem = $menu.Items.Add("Локальный адрес: $url")
  $addressItem.Enabled = $false
  $copyItem = $menu.Items.Add('Скопировать адрес сайта')
  $statusItem = $menu.Items.Add('Состояние системы')
  $logItem = $menu.Items.Add('Открыть журнал ошибок')
  $exitItem = $menu.Items.Add('Выйти из Yorika')
  $tray = New-Object System.Windows.Forms.NotifyIcon
  $tray.Icon = [Drawing.SystemIcons]::Application
  $tray.Text = 'Yorika'
  $tray.ContextMenuStrip = $menu
  $tray.Visible = $true

  $openAction = { Start-Process $url }
  $openItem.add_Click($openAction)
  $tray.add_DoubleClick($openAction)
  $copyItem.add_Click({ [System.Windows.Forms.Clipboard]::SetText($url) })
  $statusItem.add_Click({
    [System.Windows.Forms.MessageBox]::Show("Yorika работает`nАдрес: $url`nПроцесс: $PID`nPython не требуется", 'Yorika status') | Out-Null
  })
  $logItem.add_Click({ if ([IO.File]::Exists($logPath)) { Start-Process notepad.exe -ArgumentList ('"' + $logPath + '"') } })
  $exitItem.add_Click({ [System.Windows.Forms.Application]::ExitThread() })

  $timer = New-Object System.Windows.Forms.Timer
  $timer.Interval = 100
  $timer.add_Tick({
    try {
      $processed = 0
      while ($listener.Pending() -and $processed -lt 8) {
        $processed++
        $client = $listener.AcceptTcpClient()
        try {
          $client.ReceiveTimeout = 900
          $client.SendTimeout = 900
          $stream = $client.GetStream()
          $reader = [IO.StreamReader]::new($stream, [Text.Encoding]::ASCII, $false, 1024, $true)
          $first = $reader.ReadLine()
          if (-not $first -or $first.Length -gt 4096) { continue }
          $parts = $first.Split(' ')
          if ($parts.Length -lt 2) { continue }
          $headerCount = 0
          $contentLength = 0
          $requestOrigin = ''
          $requestHost = ''
          do {
            $line = $reader.ReadLine()
            $headerCount++
            if ($line -match '^Content-Length:\s*(\d+)\s* -gt 80 -or ($null -ne $line -and $line.Length -gt 8192)) { throw 'HTTP request headers exceeded limits' }
          } while ($null -ne $line -and $line.Length -gt 0)
          $status = '200 OK'
          $isApi = $parts[1] -match '^/api/updates/(settings|token|check|stage)(\?|$)'
          if ($isApi) {
            $apiAction = $Matches[1]
            $apiResponse = @{error='Неизвестная ошибка'}
            $status = '200 OK'
            try {
              if ($requestHost -ne "127.0.0.1:$port" -or $contentLength -gt 2048 -or $contentLength -lt 0) { throw 'Недопустимый запрос' }
              if ($parts[0] -ne 'GET' -and ($parts[0] -notin @('POST','DELETE') -or $requestOrigin -ne "http://127.0.0.1:$port")) { throw 'Доступ запрещён' }
              $bodyText = ''
              if ($contentLength -gt 0) {
                $buffer = New-Object byte[] $contentLength
                $readTotal = 0
                while ($readTotal -lt $contentLength) {
                  $n = $stream.Read($buffer,$readTotal,$contentLength-$readTotal)
                  if ($n -le 0) { throw 'Неполное тело запроса' }
                  $readTotal += $n
                }
                $bodyText = [Text.Encoding]::UTF8.GetString($buffer)
              }
              $params = if ($bodyText) { ConvertFrom-Json -InputObject $bodyText } else { $null }
              $scriptPath = Join-Path $PSScriptRoot 'update-engine.ps1'
              if ($apiAction -eq 'settings' -and $parts[0] -eq 'GET') {
                $json = & $scriptPath -Action settings
              } elseif ($apiAction -eq 'settings' -and $parts[0] -eq 'POST') {
                $json = & $scriptPath -Action save-settings -Channel $params.channel -Interval ([int]$params.interval)
              } elseif ($apiAction -eq 'token' -and $parts[0] -eq 'POST') {
                $json = & $scriptPath -Action save-token -Token $params.token
              } elseif ($apiAction -eq 'token' -and $parts[0] -eq 'DELETE') {
                $json = & $scriptPath -Action delete-token
              } elseif ($apiAction -eq 'check' -and $parts[0] -eq 'POST') {
                $json = & $scriptPath -Action check -Channel $params.channel
              } elseif ($apiAction -eq 'stage' -and $parts[0] -eq 'POST') {
                $json = & $scriptPath -Action stage -Channel $params.channel
              } else { throw 'Метод не поддерживается' }
              $apiResponse = $json
            } catch {
              $status = '400 Bad Request'
              $apiResponse = @{error=$_.Exception.Message} | ConvertTo-Json -Compress
              Log "Updates API error: $($_.Exception.Message)"
            }
            $payload = [Text.Encoding]::UTF8.GetBytes([string]$apiResponse)
            $header = "HTTP/1.1 $status`r`nContent-Type: application/json; charset=utf-8`r`nContent-Length: $($payload.Length)`r`nConnection: close`r`nCache-Control: no-store`r`nX-Content-Type-Options: nosniff`r`nX-Yorika-App: Yorika`r`n`r`n"
            $head = [Text.Encoding]::ASCII.GetBytes($header)
            $stream.Write($head,0,$head.Length)
            if ($parts[0] -ne 'HEAD') { $stream.Write($payload,0,$payload.Length) }
            $stream.Flush()
            continue
          }
          $mime = 'text/plain; charset=utf-8'
          $body = [Text.Encoding]::UTF8.GetBytes('Yorika')
          if ($parts[0] -ne 'GET' -and $parts[0] -ne 'HEAD') {
            $status = '405 Method Not Allowed'
            $body = [Text.Encoding]::UTF8.GetBytes('Method not allowed')
          } else {
            $path = [Uri]::UnescapeDataString(($parts[1] -split '[?#]', 2)[0]).Replace('/', [IO.Path]::DirectorySeparatorChar)
            if ($path.IndexOf([char]0) -ge 0) { throw 'Invalid path' }
            if ($path -eq [IO.Path]::DirectorySeparatorChar.ToString()) { $path = [IO.Path]::DirectorySeparatorChar + 'index.html' }
            $relative = $path.TrimStart([char][IO.Path]::DirectorySeparatorChar)
            $file = [IO.Path]::GetFullPath((Join-Path $siteRoot $relative))
            $prefix = $siteRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
            if (-not $file.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) -or -not [IO.File]::Exists($file)) {
              $status = '404 Not Found'
              $body = [Text.Encoding]::UTF8.GetBytes('Not found')
            } else {
              $ext = [IO.Path]::GetExtension($file).ToLowerInvariant()
              $mime = switch ($ext) {
                '.html' { 'text/html; charset=utf-8' }
                '.css' { 'text/css; charset=utf-8' }
                '.js' { 'text/javascript; charset=utf-8' }
                '.json' { 'application/json; charset=utf-8' }
                '.svg' { 'image/svg+xml' }
                '.png' { 'image/png' }
                '.ico' { 'image/x-icon' }
                default { 'application/octet-stream' }
              }
              $body = [IO.File]::ReadAllBytes($file)
            }
          }
          $header = "HTTP/1.1 $status`r`nContent-Type: $mime`r`nContent-Length: $($body.Length)`r`nConnection: close`r`nX-Yorika-App: Yorika`r`nX-Content-Type-Options: nosniff`r`n`r`n"
          $h = [Text.Encoding]::ASCII.GetBytes($header)
          $stream.Write($h, 0, $h.Length)
          if ($parts[0] -ne 'HEAD') { $stream.Write($body, 0, $body.Length) }
          $stream.Flush()
        } finally { $client.Close() }
      }
    } catch { Log "HTTP error: $($_.Exception.Message)" }
  })
  $timer.Start()
  # Publish the verified bound port; the BAT opens the default browser.
  [IO.File]::WriteAllText($readyPath, $url, [Text.Encoding]::ASCII)
  [System.Windows.Forms.Application]::Run()
} catch {
  Log "Startup error: $($_.Exception.ToString())"
  Write-Host ("[YORIKA] Startup error: " + $_.Exception.ToString())
  try { [System.Windows.Forms.MessageBox]::Show("Ошибка запуска Yorika. Журнал: .yorika\yorika.log", 'Yorika') | Out-Null } catch {}
} finally {
  try {
    if ([IO.File]::Exists($readyPath) -and [IO.File]::ReadAllText($readyPath).Trim() -eq $url) { [IO.File]::Delete($readyPath) }
  } catch {}
  if ($timer) { $timer.Stop(); $timer.Dispose() }
  if ($tray) { $tray.Visible = $false; $tray.Dispose() }
  if ($listener) { $listener.Stop() }
  if ($mutex) { try { $mutex.ReleaseMutex() } catch {} ; $mutex.Dispose() }
  Log 'Yorika stopped.'
}
) { $contentLength = [int]$Matches[1] }
            if ($line -match '^Origin:\s*(.+) -gt 80 -or ($null -ne $line -and $line.Length -gt 8192)) { throw 'HTTP request headers exceeded limits' }
          } while ($null -ne $line -and $line.Length -gt 0)
          $status = '200 OK'
          $mime = 'text/plain; charset=utf-8'
          $body = [Text.Encoding]::UTF8.GetBytes('Yorika')
          if ($parts[0] -ne 'GET' -and $parts[0] -ne 'HEAD') {
            $status = '405 Method Not Allowed'
            $body = [Text.Encoding]::UTF8.GetBytes('Method not allowed')
          } else {
            $path = [Uri]::UnescapeDataString(($parts[1] -split '[?#]', 2)[0]).Replace('/', [IO.Path]::DirectorySeparatorChar)
            if ($path.IndexOf([char]0) -ge 0) { throw 'Invalid path' }
            if ($path -eq [IO.Path]::DirectorySeparatorChar.ToString()) { $path = [IO.Path]::DirectorySeparatorChar + 'index.html' }
            $relative = $path.TrimStart([char][IO.Path]::DirectorySeparatorChar)
            $file = [IO.Path]::GetFullPath((Join-Path $siteRoot $relative))
            $prefix = $siteRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
            if (-not $file.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) -or -not [IO.File]::Exists($file)) {
              $status = '404 Not Found'
              $body = [Text.Encoding]::UTF8.GetBytes('Not found')
            } else {
              $ext = [IO.Path]::GetExtension($file).ToLowerInvariant()
              $mime = switch ($ext) {
                '.html' { 'text/html; charset=utf-8' }
                '.css' { 'text/css; charset=utf-8' }
                '.js' { 'text/javascript; charset=utf-8' }
                '.json' { 'application/json; charset=utf-8' }
                '.svg' { 'image/svg+xml' }
                '.png' { 'image/png' }
                '.ico' { 'image/x-icon' }
                default { 'application/octet-stream' }
              }
              $body = [IO.File]::ReadAllBytes($file)
            }
          }
          $header = "HTTP/1.1 $status`r`nContent-Type: $mime`r`nContent-Length: $($body.Length)`r`nConnection: close`r`nX-Yorika-App: Yorika`r`nX-Content-Type-Options: nosniff`r`n`r`n"
          $h = [Text.Encoding]::ASCII.GetBytes($header)
          $stream.Write($h, 0, $h.Length)
          if ($parts[0] -ne 'HEAD') { $stream.Write($body, 0, $body.Length) }
          $stream.Flush()
        } finally { $client.Close() }
      }
    } catch { Log "HTTP error: $($_.Exception.Message)" }
  })
  $timer.Start()
  # Publish the verified bound port; the BAT opens the default browser.
  [IO.File]::WriteAllText($readyPath, $url, [Text.Encoding]::ASCII)
  [System.Windows.Forms.Application]::Run()
} catch {
  Log "Startup error: $($_.Exception.ToString())"
  Write-Host ("[YORIKA] Startup error: " + $_.Exception.ToString())
  try { [System.Windows.Forms.MessageBox]::Show("Ошибка запуска Yorika. Журнал: .yorika\yorika.log", 'Yorika') | Out-Null } catch {}
} finally {
  try {
    if ([IO.File]::Exists($readyPath) -and [IO.File]::ReadAllText($readyPath).Trim() -eq $url) { [IO.File]::Delete($readyPath) }
  } catch {}
  if ($timer) { $timer.Stop(); $timer.Dispose() }
  if ($tray) { $tray.Visible = $false; $tray.Dispose() }
  if ($listener) { $listener.Stop() }
  if ($mutex) { try { $mutex.ReleaseMutex() } catch {} ; $mutex.Dispose() }
  Log 'Yorika stopped.'
}
) { $requestOrigin = $Matches[1].Trim() }
            if ($line -match '^Host:\s*(.+) -gt 80 -or ($null -ne $line -and $line.Length -gt 8192)) { throw 'HTTP request headers exceeded limits' }
          } while ($null -ne $line -and $line.Length -gt 0)
          $status = '200 OK'
          $mime = 'text/plain; charset=utf-8'
          $body = [Text.Encoding]::UTF8.GetBytes('Yorika')
          if ($parts[0] -ne 'GET' -and $parts[0] -ne 'HEAD') {
            $status = '405 Method Not Allowed'
            $body = [Text.Encoding]::UTF8.GetBytes('Method not allowed')
          } else {
            $path = [Uri]::UnescapeDataString(($parts[1] -split '[?#]', 2)[0]).Replace('/', [IO.Path]::DirectorySeparatorChar)
            if ($path.IndexOf([char]0) -ge 0) { throw 'Invalid path' }
            if ($path -eq [IO.Path]::DirectorySeparatorChar.ToString()) { $path = [IO.Path]::DirectorySeparatorChar + 'index.html' }
            $relative = $path.TrimStart([char][IO.Path]::DirectorySeparatorChar)
            $file = [IO.Path]::GetFullPath((Join-Path $siteRoot $relative))
            $prefix = $siteRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
            if (-not $file.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) -or -not [IO.File]::Exists($file)) {
              $status = '404 Not Found'
              $body = [Text.Encoding]::UTF8.GetBytes('Not found')
            } else {
              $ext = [IO.Path]::GetExtension($file).ToLowerInvariant()
              $mime = switch ($ext) {
                '.html' { 'text/html; charset=utf-8' }
                '.css' { 'text/css; charset=utf-8' }
                '.js' { 'text/javascript; charset=utf-8' }
                '.json' { 'application/json; charset=utf-8' }
                '.svg' { 'image/svg+xml' }
                '.png' { 'image/png' }
                '.ico' { 'image/x-icon' }
                default { 'application/octet-stream' }
              }
              $body = [IO.File]::ReadAllBytes($file)
            }
          }
          $header = "HTTP/1.1 $status`r`nContent-Type: $mime`r`nContent-Length: $($body.Length)`r`nConnection: close`r`nX-Yorika-App: Yorika`r`nX-Content-Type-Options: nosniff`r`n`r`n"
          $h = [Text.Encoding]::ASCII.GetBytes($header)
          $stream.Write($h, 0, $h.Length)
          if ($parts[0] -ne 'HEAD') { $stream.Write($body, 0, $body.Length) }
          $stream.Flush()
        } finally { $client.Close() }
      }
    } catch { Log "HTTP error: $($_.Exception.Message)" }
  })
  $timer.Start()
  # Publish the verified bound port; the BAT opens the default browser.
  [IO.File]::WriteAllText($readyPath, $url, [Text.Encoding]::ASCII)
  [System.Windows.Forms.Application]::Run()
} catch {
  Log "Startup error: $($_.Exception.ToString())"
  Write-Host ("[YORIKA] Startup error: " + $_.Exception.ToString())
  try { [System.Windows.Forms.MessageBox]::Show("Ошибка запуска Yorika. Журнал: .yorika\yorika.log", 'Yorika') | Out-Null } catch {}
} finally {
  try {
    if ([IO.File]::Exists($readyPath) -and [IO.File]::ReadAllText($readyPath).Trim() -eq $url) { [IO.File]::Delete($readyPath) }
  } catch {}
  if ($timer) { $timer.Stop(); $timer.Dispose() }
  if ($tray) { $tray.Visible = $false; $tray.Dispose() }
  if ($listener) { $listener.Stop() }
  if ($mutex) { try { $mutex.ReleaseMutex() } catch {} ; $mutex.Dispose() }
  Log 'Yorika stopped.'
}
) { $requestHost = $Matches[1].Trim() }
            if ($headerCount -gt 80 -or ($null -ne $line -and $line.Length -gt 8192)) { throw 'HTTP request headers exceeded limits' }
          } while ($null -ne $line -and $line.Length -gt 0)
          $status = '200 OK'
          $mime = 'text/plain; charset=utf-8'
          $body = [Text.Encoding]::UTF8.GetBytes('Yorika')
          if ($parts[0] -ne 'GET' -and $parts[0] -ne 'HEAD') {
            $status = '405 Method Not Allowed'
            $body = [Text.Encoding]::UTF8.GetBytes('Method not allowed')
          } else {
            $path = [Uri]::UnescapeDataString(($parts[1] -split '[?#]', 2)[0]).Replace('/', [IO.Path]::DirectorySeparatorChar)
            if ($path.IndexOf([char]0) -ge 0) { throw 'Invalid path' }
            if ($path -eq [IO.Path]::DirectorySeparatorChar.ToString()) { $path = [IO.Path]::DirectorySeparatorChar + 'index.html' }
            $relative = $path.TrimStart([char][IO.Path]::DirectorySeparatorChar)
            $file = [IO.Path]::GetFullPath((Join-Path $siteRoot $relative))
            $prefix = $siteRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
            if (-not $file.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) -or -not [IO.File]::Exists($file)) {
              $status = '404 Not Found'
              $body = [Text.Encoding]::UTF8.GetBytes('Not found')
            } else {
              $ext = [IO.Path]::GetExtension($file).ToLowerInvariant()
              $mime = switch ($ext) {
                '.html' { 'text/html; charset=utf-8' }
                '.css' { 'text/css; charset=utf-8' }
                '.js' { 'text/javascript; charset=utf-8' }
                '.json' { 'application/json; charset=utf-8' }
                '.svg' { 'image/svg+xml' }
                '.png' { 'image/png' }
                '.ico' { 'image/x-icon' }
                default { 'application/octet-stream' }
              }
              $body = [IO.File]::ReadAllBytes($file)
            }
          }
          $header = "HTTP/1.1 $status`r`nContent-Type: $mime`r`nContent-Length: $($body.Length)`r`nConnection: close`r`nX-Yorika-App: Yorika`r`nX-Content-Type-Options: nosniff`r`n`r`n"
          $h = [Text.Encoding]::ASCII.GetBytes($header)
          $stream.Write($h, 0, $h.Length)
          if ($parts[0] -ne 'HEAD') { $stream.Write($body, 0, $body.Length) }
          $stream.Flush()
        } finally { $client.Close() }
      }
    } catch { Log "HTTP error: $($_.Exception.Message)" }
  })
  $timer.Start()
  # Publish the verified bound port; the BAT opens the default browser.
  [IO.File]::WriteAllText($readyPath, $url, [Text.Encoding]::ASCII)
  [System.Windows.Forms.Application]::Run()
} catch {
  Log "Startup error: $($_.Exception.ToString())"
  Write-Host ("[YORIKA] Startup error: " + $_.Exception.ToString())
  try { [System.Windows.Forms.MessageBox]::Show("Ошибка запуска Yorika. Журнал: .yorika\yorika.log", 'Yorika') | Out-Null } catch {}
} finally {
  try {
    if ([IO.File]::Exists($readyPath) -and [IO.File]::ReadAllText($readyPath).Trim() -eq $url) { [IO.File]::Delete($readyPath) }
  } catch {}
  if ($timer) { $timer.Stop(); $timer.Dispose() }
  if ($tray) { $tray.Visible = $false; $tray.Dispose() }
  if ($listener) { $listener.Stop() }
  if ($mutex) { try { $mutex.ReleaseMutex() } catch {} ; $mutex.Dispose() }
  Log 'Yorika stopped.'
}
