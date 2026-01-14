@echo off
setlocal
cd /d "%~dp0"
powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File "scripts\bootstrap_mystrix.ps1"
endlocal
