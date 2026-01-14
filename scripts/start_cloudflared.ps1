param(
  [int]$Port = 8000
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Split-Path -Parent $root
$toolsDir = Join-Path $repo "tools"
$exe = Join-Path $toolsDir "cloudflared.exe"
$log = Join-Path $repo "cloudflared.log"
$err = Join-Path $repo "cloudflared.err.log"
$config = Join-Path $repo "cloudflared.yml"
$configAlt = Join-Path $repo "cloudflared.yaml"

if (!(Test-Path $exe)) {
  New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null
  $url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
  Invoke-WebRequest -Uri $url -OutFile $exe
}

$existing = Get-Process -Name cloudflared -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $exe }
if ($existing) {
  return
}

if (Test-Path $config) {
  $args = "--no-autoupdate tunnel --config `"$config`" run"
} elseif (Test-Path $configAlt) {
  $args = "--no-autoupdate tunnel --config `"$configAlt`" run"
} else {
  $args = "--no-autoupdate tunnel --url http://127.0.0.1:$Port"
}
Start-Process -FilePath $exe -ArgumentList $args -WorkingDirectory $repo -RedirectStandardOutput $log -RedirectStandardError $err -WindowStyle Hidden
