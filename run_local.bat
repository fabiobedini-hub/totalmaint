@echo off
REM TotalMaint - start locally on Windows (no Docker needed).
REM First run creates a virtual environment and installs the packages.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    py -3 -m venv .venv || python -m venv .venv
    if errorlevel 1 (
        echo Could not create the virtual environment. Is Python 3.11+ installed?
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate.bat
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r backend\requirements.txt

echo.
echo  TotalMaint is starting on http://localhost:8000
echo  On your phone (same Wi-Fi): http://%COMPUTERNAME%:8000
echo  Stop with Ctrl+C
echo.
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app
pause
