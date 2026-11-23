@echo off
setlocal
cd /d "%~dp0"

REM Keep the build environment, pip cache, PyInstaller work files, and output
REM inside this project directory.
set "PIP_CACHE_DIR=%CD%\.pip-cache"
set "PYINSTALLER_CONFIG_DIR=%CD%\.pyinstaller"
set "TEMP=%CD%\.build-temp"
set "TMP=%CD%\.build-temp"
if not exist ".build-temp" mkdir ".build-temp"

if not exist ".venv\Scripts\python.exe" (
    py -3.13 -m venv .venv
    if errorlevel 1 goto :error
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 goto :error
python -m pip install -r requirements.txt "pyinstaller>=6.22.3"
if errorlevel 1 goto :error

python -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --windowed ^
    --onedir ^
    --name DaymarkTodo ^
    --collect-all customtkinter ^
    --collect-all jdatetime ^
    --workpath "%CD%\build" ^
    --distpath "%CD%\dist" ^
    --specpath "%CD%\build" ^
    app.py
if errorlevel 1 goto :error

echo.
powershell -NoProfile -Command "Compress-Archive -Path '.\dist\DaymarkTodo' -DestinationPath '.\DaymarkTodo-Windows.zip' -Force"
if errorlevel 1 goto :error

echo Build complete.
echo EXE: %CD%\dist\DaymarkTodo\DaymarkTodo.exe
echo ZIP: %CD%\DaymarkTodo-Windows.zip
echo Distribute the ZIP or the entire DaymarkTodo folder, not only the EXE.
echo Keep the installed folder in a location where the Windows user can write files.
pause
exit /b 0

:error
echo.
echo Build failed. Review the error messages above.
pause
exit /b 1
