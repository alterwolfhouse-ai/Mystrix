param(
  [string]$PythonVersion = "3.11.9",
  [string]$Arch = "amd64",
  [string]$StagingDir = "",
  [string]$OutputDir = "",
  [switch]$SkipInstaller
)

$root = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$repo = Split-Path -Parent $root
$buildRoot = Join-Path $repo "build\installer"
$stage = if ($StagingDir) { $StagingDir } else { Join-Path $buildRoot "app" }
$outDir = if ($OutputDir) { $OutputDir } else { Join-Path $buildRoot "output" }

New-Item -ItemType Directory -Force -Path $buildRoot | Out-Null
if (Test-Path $stage) {
  Remove-Item -Recurse -Force -Path $stage
}
New-Item -ItemType Directory -Force -Path $stage | Out-Null
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$excludeDirs = @(
  ".git",
  ".venv",
  "__pycache__",
  "cache_data",
  "cache_test",
  "build",
  "dist",
  "docs",
  "deploy",
  "webversion"
)

$excludeFiles = @(
  "data_cache.db",
  "cloudflared_url.txt",
  "cloudflared_url.json",
  "*.log",
  "*.db",
  "*.csv"
)

$rc = & robocopy $repo $stage /E /XD $excludeDirs /XF $excludeFiles
if ($LASTEXITCODE -ge 8) {
  throw "Robocopy failed with code $LASTEXITCODE"
}

$runtime = Join-Path $stage "runtime\python"
New-Item -ItemType Directory -Force -Path $runtime | Out-Null

$pyZip = Join-Path $buildRoot ("python-" + $PythonVersion + "-embed-" + $Arch + ".zip")
$pyUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-$Arch.zip"
if (!(Test-Path $pyZip)) {
  Invoke-WebRequest -Uri $pyUrl -OutFile $pyZip
}
Expand-Archive -Path $pyZip -DestinationPath $runtime -Force

$pth = Get-ChildItem -Path $runtime -Filter "python*._pth" | Select-Object -First 1
if ($pth) {
  $lines = Get-Content $pth.FullName -ErrorAction SilentlyContinue
  $out = @()
  foreach ($line in $lines) {
    if ($line -match '^\s*#\s*import site\s*$') {
      $out += "import site"
    } else {
      $out += $line
    }
  }
  if (-not ($out -contains "Lib")) { $out += "Lib" }
  if (-not ($out -contains "Lib\site-packages")) { $out += "Lib\site-packages" }
  if (-not ($out -contains "import site")) { $out += "import site" }
  Set-Content -Path $pth.FullName -Value $out -Encoding ASCII
}

New-Item -ItemType Directory -Force -Path (Join-Path $runtime "Lib\site-packages") | Out-Null

$getPip = Join-Path $buildRoot "get-pip.py"
Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPip

$pyExe = Join-Path $runtime "python.exe"
& $pyExe $getPip --no-warn-script-location
& $pyExe -m pip install --upgrade pip --no-warn-script-location
& $pyExe -m pip install -r (Join-Path $repo "requirements.txt") --no-warn-script-location

if ($SkipInstaller) {
  Write-Host "Staging complete at $stage"
  exit 0
}

$iss = Join-Path $repo "installer\mystrix.iss"
$iscc = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
if (-not $iscc) {
  $default = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
  if (Test-Path $default) {
    $iscc = $default
  }
}

if ($iscc) {
  & $iscc $iss "/DStagingDir=$stage" "/DOutputDir=$outDir"
} else {
  Write-Host "Inno Setup not found. Install it or run with -SkipInstaller to keep staging output only."
}
