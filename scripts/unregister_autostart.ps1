param(
  [int]$Port = 8000
)

$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'

try {
  Remove-ItemProperty -Path $runKey -Name 'Mystrix' -ErrorAction SilentlyContinue
} catch {
  Write-Host "Failed to remove autostart: $($_.Exception.Message)"
}
