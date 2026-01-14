param(
  [string]$LogPath,
  [switch]$Once
)

$root = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$repo = Split-Path -Parent $root
$root = (Resolve-Path $root).Path
$repo = (Resolve-Path $repo).Path
$log = if ($LogPath) { $LogPath } else { Join-Path $repo "cloudflared.err.log" }
$urlTxt = Join-Path $repo "cloudflared_url.txt"
$urlJson = Join-Path $repo "cloudflared_url.json"
$lock = Join-Path $repo ".cloudflared_watch.lock"
$regex = [regex]"https://[a-z0-9-]+\.trycloudflare\.com"
$lastUrl = $null
$runOnce = $Once

Set-Content -Path $lock -Value $PID

function Write-Url($url) {
  if (-not $url) { return }
  if ($script:lastUrl -eq $url) { return }
  Set-Content -Path $urlTxt -Value $url
  $payload = @{ url = $url; updated_at = (Get-Date).ToString("o") } | ConvertTo-Json -Compress
  Set-Content -Path $urlJson -Value $payload
  $script:lastUrl = $url
}

function Sync-From-Log {
  if (!(Test-Path $log)) { return }
  $found = $null
  $lines = Get-Content -Path $log -ErrorAction SilentlyContinue
  foreach ($line in $lines) {
    if ($line -match $regex) {
      $found = $Matches[0]
    }
  }
  if ($found) {
    Write-Url $found
  }
}

Sync-From-Log

if ($Once) {
  return
}

while ($true) {
  Sync-From-Log
  Start-Sleep -Seconds 2
}
