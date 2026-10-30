@echo off
REM TotalMant Admin - the console for the server's administrator, locally on Windows.
REM Start run_local.bat first (it prepares the database), then this one in a second window.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Start run_local.bat once first: it creates the Python environment.
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat
if "%ADMIN_PASSWORD%"=="" (
    findstr /r /c:"^ADMIN_PASSWORD=.........." .env >nul 2>nul
    if errorlevel 1 (
        echo.
        echo  ADMIN_PASSWORD is not set. For a local test it is set to: admin-locale-123
        echo  ^(put ADMIN_PASSWORD=... in the .env file to choose your own^)
        set ADMIN_PASSWORD=admin-locale-123
    )
)
echo.
echo  TotalMant Admin is starting on http://localhost:8001
echo  Stop with Ctrl+C
echo.
cd backend
python -m uvicorn app.admin_main:app --host 127.0.0.1 --port 8001 --reload --reload-dir app
pause
