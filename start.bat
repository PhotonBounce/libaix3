@echo off
chcp 65001 >nul
setlocal

echo =========================================
echo   OpsBrief Backend Launcher
echo =========================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"
cd backend

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python 3.11+ from https://python.org
    pause
    exit /b 1
)

REM Check Python version (3.10+)
python -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.10 or higher is required.
    pause
    exit /b 1
)

REM Check for venv
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
)

REM Activate venv
call venv\Scripts\activate.bat

REM Install deps
if not exist "venv\Lib\site-packages\fastapi" (
    echo Installing dependencies (first run, may take 2-3 minutes)...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: pip install failed.
        pause
        exit /b 1
    )
)

REM Check .env
if not exist ".env" (
    echo.
    echo WARNING: No .env file found. Copying from .env.example...
    copy "%SCRIPT_DIR%.env.example" .env
    echo Please edit .env and add your OPENAI_API_KEY before using AI features.
    echo.
)

REM Start app
echo.
echo Starting OpsBrief backend on http://localhost:8000
echo API docs: http://localhost:8000/docs
echo.

python run.py

pause
