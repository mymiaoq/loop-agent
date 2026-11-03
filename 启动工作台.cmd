@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "DOCLOOP_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%DOCLOOP_PY%" goto setup
"%DOCLOOP_PY%" -c "import fastapi,uvicorn,sqlalchemy,oracledb,httpx" >nul 2>nul
if errorlevel 1 goto setup
goto run
:setup
set "DOCLOOP_UV=uv"
where uv >nul 2>nul
if not errorlevel 1 goto install
if exist "%USERPROFILE%\.local\bin\uv.exe" (
  set "DOCLOOP_UV=%USERPROFILE%\.local\bin\uv.exe"
  goto install
)
echo uv was not found. See README.md for setup.
pause
exit /b 1
:install
echo Preparing the locked Python environment. First setup requires internet.
"%DOCLOOP_UV%" sync --frozen --python 3.12 --no-dev
if errorlevel 1 (
  echo Setup failed. See README.md.
  pause
  exit /b 1
)
:run
"%DOCLOOP_PY%" -m docloop.workbench --root "%~dp0." --restart --open %*
set "DOCLOOP_EXIT=%ERRORLEVEL%"
if not "%DOCLOOP_EXIT%"=="0" (
  echo Workbench stopped with an error. Keep this window for troubleshooting.
  pause
)
exit /b %DOCLOOP_EXIT%
