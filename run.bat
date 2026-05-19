@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Project virtual environment not found: .venv\Scripts\python.exe
    echo Please install dependencies before running this app.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" main.py
pause
