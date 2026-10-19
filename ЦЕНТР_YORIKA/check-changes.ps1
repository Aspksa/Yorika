# Check changed files without changing repository state.
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Push-Location $root
try {
  $git = Get-Command git -ErrorAction SilentlyContinue
  if (-not $git) { throw 'Git is required to inspect new changes. Download a git clone, not only a source ZIP.' }
  & git rev-parse --is-inside-work-tree *> $null
  if ($LASTEXITCODE -ne 0) { throw 'Not a Git working tree. Full tests can be run separately from the ZIP.' }
  $base = 'HEAD'
  & git show-ref --verify --quiet refs/remotes/origin/main
  if ($LASTEXITCODE -eq 0) {
    $base = (& git merge-base HEAD origin/main).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $base) { throw 'Cannot determine merge base with origin/main.' }
  }
  $files = @(
    & git diff --name-only --diff-filter=ACMR $base --
    & git ls-files --others --exclude-standard
  ) | Where-Object { $_ } | Sort-Object -Unique
  if ($LASTEXITCODE -ne 0) { throw 'Git change scan failed.' }
  Write-Host ("Files changed relative to $base or untracked: " + $files.Count)
  foreach ($file in $files) {
    Write-Host (" - " + $file)
    if ($file -match '(^|/|\\)(?:\.env(?:\..*)?|\.credentials(?:_rsaparams)?|\.runner|id_rsa|id_ed25519)$') {
      throw 'Possible credentials in changed files. Remove them before committing.'
    }
    if ($file -match '(^|/|\\)python312-runtime[/\\]' -or $file -match 'python-.*-embed-amd64\.zip$') {
      throw 'Portable runtime/archive must not be committed.'
    }
  }
  Write-Host 'PASS: changed filenames checked. This does NOT scan file contents for secrets.'
} finally { Pop-Location }
