param(
  [int]$IntervalSec = 120,
  [int]$Port = 8000,
  [string]$Url = 'http://127.0.0.1:8000/healthz'
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Split-Path -Parent $root
$watchOnce = Join-Path $root 'watchdog_mystrix_server.ps1'
$lock = Join-Path $repo '.watchdog.lock'

if (Test-Path $lock) {
  try {
    $pid = (Get-Content $lock -ErrorAction Stop | Select-Object -First 1)
    if ($pid -match '^\d+$') {
      $p = Get-Process -Id $pid -ErrorAction SilentlyContinue
      if ($p) { exit 0 }
    }
  } catch {
  }
}

try {
  Set-Content -Path $lock -Value $PID -Encoding ASCII
} catch {
}

while ($true) {
  try {
    & $watchOnce -Port $Port -Url $Url
  } catch {
    try {
      Add-Content -Path (Join-Path $repo 'watchdog.log') -Value "[$(Get-Date -Format s)] Watchdog loop error: $($_.Exception.Message)"
    } catch {
    }
  }
  Start-Sleep -Seconds $IntervalSec
}
