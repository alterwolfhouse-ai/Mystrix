param(
  [int]$Port = 8000
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Split-Path -Parent $root
$startScript = Join-Path $root 'start_mystrix_server.ps1'
$loopScript = Join-Path $root 'watchdog_loop.ps1'

try {
  & $startScript -Port $Port
} catch {
}

$loopCmd = "-ExecutionPolicy Bypass -File `"$loopScript`" -Port $Port"
Start-Process -FilePath 'powershell.exe' -ArgumentList $loopCmd -WorkingDirectory $repo -WindowStyle Hidden
