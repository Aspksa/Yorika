# Windows runner diagnostics. Does not install software or change execution policy.
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$report = Join-Path $root 'yorika-windows-diagnostics.json'
$checks = [Collections.Generic.List[object]]::new()
function Check([string]$name,[bool]$ok,[string]$detail) {
  $status = if ($ok) { 'passed' } else { 'failed' }
  $checks.Add([pscustomobject]@{ name=$name; status=$status; detail=$detail })
  $color = if ($ok) { 'Green' } else { 'Red' }
  Write-Host ('[' + $status + '] ' + $name + ': ' + $detail) -ForegroundColor $color
}
Check 'PowerShell 7' ($PSVersionTable.PSVersion.Major -ge 7) $PSVersionTable.PSVersion.ToString()
$node = Get-Command node -ErrorAction SilentlyContinue
if ($node) {
  $version = (& node --version 2>&1 | Out-String).Trim()
  Check 'Node.js' ($LASTEXITCODE -eq 0) $version
} else { Check 'Node.js' $false 'Не найден в PATH. Установите Node.js LTS и перезапустите runner.' }
$python = Join-Path $root 'ЦЕНТР_YORIKA/python312-runtime/python.exe'
if (Test-Path $python) {
  $version = (& $python --version 2>&1 | Out-String).Trim()
  Check 'Изолированный Python' ($LASTEXITCODE -eq 0) $version
} else {
  $checks.Add([pscustomobject]@{name='Изолированный Python';status='skipped';detail='Подготовит следующий тестовый шаг'})
  Write-Host '[ПРОПУЩЕНО] Изолированный Python: подготовит следующий шаг' -ForegroundColor Yellow
}
$git = Get-Command git -ErrorAction SilentlyContinue
Check 'Git' ([bool]$git) $(if ($git) { 'Команда доступна' } else { 'Установите Git' })
$checks.Add([pscustomobject]@{name='Антивирус';status='skipped';detail='Не проверяется и не изменяется'})
$checks.Add([pscustomobject]@{name='Cloud.ru';status='skipped';detail='Настоящие ключи и API не проверяются'})
[pscustomobject]@{time_utc=[DateTime]::UtcNow.ToString('o');checks=@($checks)} |
  ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $report -Encoding utf8
Write-Host ('Диагностика сохранена: ' + $report)
if (@($checks | Where-Object status -eq 'failed').Count -gt 0) { exit 1 }
exit 0
