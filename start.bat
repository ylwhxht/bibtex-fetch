@echo off
setlocal
cd /d "%~dp0"
set "BIBFETCH_UV=uv"
where uv >nul 2>nul
if %errorlevel% equ 0 goto use_uv
if exist "%USERPROFILE%\.local\bin\uv.exe" (
    set "BIBFETCH_UV=%USERPROFILE%\.local\bin\uv.exe"
    goto use_uv
)
if exist ".venv\Scripts\python.exe" goto install_deps
where py >nul 2>nul
if %errorlevel% equ 0 goto use_py
where python >nul 2>nul
if %errorlevel% equ 0 goto use_python
echo Please install Python 3.11+ or uv, then run this file again.
pause
exit /b 1

:use_uv
"%BIBFETCH_UV%" run --frozen --no-dev bibtex-fetch %*
set "result=%errorlevel%"
goto finished

:use_py
py -3 -m venv .venv
if errorlevel 1 goto failed
goto install_deps

:use_python
python -m venv .venv
if errorlevel 1 goto failed

:install_deps
".venv\Scripts\python.exe" -m pip --version >nul 2>nul
if errorlevel 1 ".venv\Scripts\python.exe" -m ensurepip --upgrade
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install --require-hashes -r requirements.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install --no-deps .
if errorlevel 1 goto failed
".venv\Scripts\python.exe" run.py %*
set "result=%errorlevel%"
goto finished

:failed
echo Setup failed. Read the error above and see docs\USAGE.md.
set "result=1"

:finished
pause
exit /b %result%
