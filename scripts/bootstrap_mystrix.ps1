param(
  [int]$Port = 8000
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Split-Path -Parent $root
$startScript = Join-Path $root 'start_mystrix_server.ps1'
$loopScript = Join-Path $root 'watchdog_loop.ps1'
$cloudStart = Join-Path $root 'start_cloudflared.ps1'
$cloudWatch = Join-Path $root 'cloudflared_watch.ps1'
$cloudConfig = Join-Path $repo 'cloudflared.yml'
$cloudConfigAlt = Join-Path $repo 'cloudflared.yaml'

try {
  & $startScript -Port $Port
} catch {
}

$loopCmd = "-ExecutionPolicy Bypass -File `"$loopScript`" -Port $Port"
Start-Process -FilePath 'powershell.exe' -ArgumentList $loopCmd -WorkingDirectory $repo -WindowStyle Hidden

try {
  & $cloudStart -Port $Port
} catch {
}

if (!(Test-Path $cloudConfig) -and !(Test-Path $cloudConfigAlt)) {
  $watchCmd = "-ExecutionPolicy Bypass -File `"$cloudWatch`""
  Start-Process -FilePath 'powershell.exe' -ArgumentList $watchCmd -WorkingDirectory $repo -WindowStyle Hidden
}
