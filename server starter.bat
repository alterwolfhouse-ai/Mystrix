@echo off
setlocal ENABLEDELAYEDEXPANSION
title MystriX Server Starter

rem Change to this script's directory (repo root)
cd /d "%~dp0"

echo === MystriX — Server Starter ===
echo Working dir: %CD%

rem Ensure virtual environment exists
if not exist ".venv\Scripts\python.exe" (
  echo Creating venv...
  py -3 -m venv .venv || python -m venv .venv
)

rem Activate venv
call ".venv\Scripts\activate.bat"

rem Verify Python is available
python -V >nul 2>&1 || (
  echo [ERROR] Python not available in venv. Aborting.
  pause
  exit /b 1
)

rem Install/upgrade dependencies
echo Installing requirements (first run may take a bit)...
python -m pip install -U pip >nul
python -m pip install -r requirements.txt || (
  echo [WARN] Failed to install some deps; continuing in case they are already present.
)

rem Bind locally only
set "HOST=127.0.0.1"
set "PORT=8000"

rem Launch server in this window (foreground)
echo Starting API on http://%HOST%:%PORT%/

rem Give the server a moment, then open homepage in default browser
start "" http://%HOST%:%PORT%/static/index.html

python server.py

echo.
echo Server exited. Press any key to close...
pause >nul

