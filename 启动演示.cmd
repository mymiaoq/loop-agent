@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto run
set "DOCLOOP_UV=uv"
where uv >nul 2>nul
if not errorlevel 1 goto setup
if exist "%USERPROFILE%\.local\bin\uv.exe" (
  set "DOCLOOP_UV=%USERPROFILE%\.local\bin\uv.exe"
  goto setup
)
echo uv was not found. See README.md for installation.
pause
exit /b 1
:setup
echo Preparing Python and locked dependencies. First setup requires internet.
"%DOCLOOP_UV%" sync --frozen --python 3.12
if errorlevel 1 (
  echo Setup failed. Check network and README.md.
  pause
  exit /b 1
)
:run
".venv\Scripts\python.exe" -m docloop.launcher "%~dp0."
set "DOCLOOP_EXIT=%ERRORLEVEL%"
pause
exit /b %DOCLOOP_EXIT%
