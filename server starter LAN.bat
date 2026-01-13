@echo off
setlocal ENABLEDELAYEDEXPANSION
title MystriX Server (LAN)

rem Change to repo root
cd /d "%~dp0"

echo === MystriX — Server Starter (LAN) ===
echo Working dir: %CD%

rem Ensure venv exists
if not exist ".venv\Scripts\python.exe" (
  echo Creating venv...
  py -3 -m venv .venv || python -m venv .venv
)

call ".venv\Scripts\activate.bat"

python -V >nul 2>&1 || (
  echo [ERROR] Python not available in venv. Aborting.
  pause
  exit /b 1
)

echo Installing requirements (first run may take a bit)...
python -m pip install -U pip >nul
python -m pip install -r requirements.txt >nul

set "HOST=0.0.0.0"
set "PORT=8000"

for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /r /c:"IPv4 Address"') do (
  set IP=%%A
  set IP=!IP: =!
)
if not defined IP set IP=127.0.0.1

echo Starting API on http://%IP%:%PORT%/
start "" http://%IP%:%PORT%/

python server.py

echo.
echo Server exited. Press any key to close...
pause >nul

