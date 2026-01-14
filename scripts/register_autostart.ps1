param(
  [int]$Port = 8000
)

$root = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$repo = Split-Path -Parent $root
$bootstrap = Join-Path $repo 'scripts\bootstrap_mystrix.ps1'

$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$cmd = "powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$bootstrap`" -Port $Port"

try {
  New-Item -Path $runKey -Force | Out-Null
  Set-ItemProperty -Path $runKey -Name 'Mystrix' -Value $cmd
} catch {
  Write-Host "Failed to register autostart: $($_.Exception.Message)"
}
