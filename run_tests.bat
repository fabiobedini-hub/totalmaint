@echo off
REM TotalMaint - run the automatic tests (uses a temporary database, never your real data).
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Start run_local.bat once first, so the virtual environment exists.
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat
python -m pip install --quiet -r backend\requirements.txt -r backend\requirements-dev.txt
cd backend
python -m pytest
pause
