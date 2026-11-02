@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" exit /b 0
".venv\Scripts\python.exe" -m docloop.workbench --root "%~dp0." --stop %*
if errorlevel 1 (
  echo Could not request shutdown. Keep this window for troubleshooting.
  pause
  exit /b 1
)
