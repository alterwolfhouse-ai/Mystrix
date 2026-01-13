param(
  [int]$Port = 8000,
  [string]$Url = 'http://127.0.0.1:8000/healthz'
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Split-Path -Parent $root
$startScript = Join-Path $root 'start_mystrix_server.ps1'
$logPath = Join-Path $repo 'watchdog.log'

function LogLine([string]$msg) {
  $ts = (Get-Date).ToString('s')
  Add-Content -Path $logPath -Value "[$ts] $msg"
}

$ok = $false
try {
  $resp = Invoke-WebRequest -Uri $Url -TimeoutSec 5 -UseBasicParsing
  if ($resp.StatusCode -eq 200) { $ok = $true }
} catch {
  $ok = $false
}

if ($ok) {
  exit 0
}

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) {
  try {
    Stop-Process -Id $listener.OwningProcess -Force
    LogLine "Stopped process $($listener.OwningProcess) on port $Port"
  } catch {
    LogLine "Failed to stop process on port $Port: $($_.Exception.Message)"
  }
}

try {
  & $startScript -Port $Port
  LogLine 'Server start triggered.'
} catch {
  LogLine "Failed to start server: $($_.Exception.Message)"
}
