@echo off
setlocal
cd /d "%~dp0"
set "PIP_CACHE_DIR=%CD%\.pip-cache"
set "TEMP=%CD%\.runtime-temp"
set "TMP=%CD%\.runtime-temp"
if not exist ".runtime-temp" mkdir ".runtime-temp"

if not exist ".venv\Scripts\python.exe" (
    py -3.13 -m venv .venv
    if errorlevel 1 goto :error
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 goto :error
python -m pip install -r requirements.txt
if errorlevel 1 goto :error
python app.py
exit /b %errorlevel%

:error
echo.
echo Failed to prepare or launch Daymark Todo.
pause
exit /b 1
