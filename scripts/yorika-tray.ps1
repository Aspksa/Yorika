param([string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# No Python, Node, pip, or external packages are required.
$ProjectRoot = [IO.Path]::GetFullPath($ProjectRoot)
$siteRoot = [IO.Path]::GetFullPath((Join-Path $ProjectRoot 'www'))
$logDir = Join-Path $ProjectRoot '.yorika'
[IO.Directory]::CreateDirectory($logDir) | Out-Null
$logPath = Join-Path $logDir 'yorika.log'
$readyPath = Join-Path $logDir 'ready.url'
function Log([string]$message) {
  try { [IO.File]::AppendAllText($logPath, ("[{0}] {1}`r`n" -f (Get-Date -Format o), $message), [Text.Encoding]::UTF8) } catch {}
}
$mutex = [System.Threading.Mutex]::new($false, 'Local\Yorika-Tray-Launcher')
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
  $openItem = $menu.Items.Add('Open Yorika')
  $addressItem = $menu.Items.Add("Local address: $url")
  $addressItem.Enabled = $false
  $copyItem = $menu.Items.Add('Copy website address')
  $statusItem = $menu.Items.Add('System status')
  $logItem = $menu.Items.Add('Open diagnostic log')
  $exitItem = $menu.Items.Add('Exit Yorika')
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
    [System.Windows.Forms.MessageBox]::Show("Yorika online`nURL: $url`nProcess: $PID`nPython: not required", 'Yorika status') | Out-Null
  })
  $logItem.add_Click({ if ([IO.File]::Exists($logPath)) { Start-Process notepad.exe -ArgumentList ('"' + $logPath + '"') } })
  $exitItem.add_Click({ [System.Windows.Forms.Application]::ExitThread() })

  $timer = New-Object System.Windows.Forms.Timer
  $timer.Interval = 60
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
          if (-not $first) { continue }
          $parts = $first.Split(' ')
          if ($parts.Length -lt 2) { continue }
          do { $line = $reader.ReadLine() } while ($null -ne $line -and $line.Length -gt 0)
          $status = '200 OK'
          $mime = 'text/plain; charset=utf-8'
          $body = [Text.Encoding]::UTF8.GetBytes('Yorika')
          if ($parts[0] -ne 'GET' -and $parts[0] -ne 'HEAD') {
            $status = '405 Method Not Allowed'
            $body = [Text.Encoding]::UTF8.GetBytes('Method not allowed')
          } else {
            $path = [Uri]::UnescapeDataString(($parts[1] -split '[?#]', 2)[0]).Replace('/', [IO.Path]::DirectorySeparatorChar)
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
          $header = "HTTP/1.1 $status`r`nContent-Type: $mime`r`nContent-Length: $($body.Length)`r`nConnection: close`r`nX-Content-Type-Options: nosniff`r`n`r`n"
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
  try { [System.Windows.Forms.MessageBox]::Show("Yorika failed to start. See .yorika\yorika.log", 'Yorika') | Out-Null } catch {}
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
