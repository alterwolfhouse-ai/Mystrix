param(
  [int]$Port = 8000
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Split-Path -Parent $root
$outLog = Join-Path $repo 'server.out.log'
$errLog = Join-Path $repo 'server.err.log'

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) {
  exit 0
}

$python = Join-Path $repo 'runtime\python\python.exe'
if (!(Test-Path $python)) {
  $python = Join-Path $repo '.venv\Scripts\python.exe'
  if (!(Test-Path $python)) {
    $python = 'python'
  }
}

Start-Process -FilePath $python -ArgumentList 'server.py' -WorkingDirectory $repo -RedirectStandardOutput $outLog -RedirectStandardError $errLog -WindowStyle Hidden
