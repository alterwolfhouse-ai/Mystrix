param(
  [int]$Port = 8000
)

$root = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$repo = Split-Path -Parent $root

function Stop-Pid([int]$pid) {
  try {
    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
  } catch {
  }
}

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) {
  Stop-Pid -pid $listener.OwningProcess
}

$watchdogLock = Join-Path $repo '.watchdog.lock'
if (Test-Path $watchdogLock) {
  try {
    $pid = (Get-Content $watchdogLock -ErrorAction Stop | Select-Object -First 1)
    if ($pid -match '^\d+$') {
      Stop-Pid -pid $pid
    }
  } catch {
  }
}

$cloudExe = Join-Path $repo 'tools\cloudflared.exe'
if (Test-Path $cloudExe) {
  Get-Process -Name cloudflared -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -eq $cloudExe } |
    ForEach-Object { Stop-Pid -pid $_.Id }
} else {
  Get-Process -Name cloudflared -ErrorAction SilentlyContinue | ForEach-Object { Stop-Pid -pid $_.Id }
}
