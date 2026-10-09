@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    set "BUILD_PYTHON=.venv\Scripts\python.exe"
) else (
    set "BUILD_PYTHON=python"
)
"%BUILD_PYTHON%" -m pip install -r requirements-dev.txt
if errorlevel 1 goto failed
"%BUILD_PYTHON%" scripts\build.py
if errorlevel 1 goto failed
echo Build complete: dist\ChromeMultiOpener.exe
if /i not "%~1"=="--no-pause" pause
exit /b 0
:failed
echo Build failed. Check the messages above.
if /i not "%~1"=="--no-pause" pause
exit /b 1
