@echo off
SETLOCAL
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [run_project.bat] Python was not found in PATH.
    echo Please install Python 3.10+ and try again.
    exit /b 1
)

python run_project.py
if errorlevel 1 (
    echo.
    echo [run_project.bat] The project launcher exited with an error.
    pause
    exit /b 1
)

exit /b 0
