@echo off
REM TotalMaint - pubblica le modifiche su GitHub.
REM 1. esegue i test   2. mostra cosa e' cambiato   3. salva (commit) e invia (push)
REM Dopo: sul NAS esegui  sudo bash nas/update.sh
setlocal
cd /d "%~dp0"

if not exist ".git" (
    echo Prima esegui prima_configurazione_git.bat
    pause
    exit /b 1
)

echo ===== 1. Test automatici =====
if exist ".venv\Scripts\python.exe" (
    call .venv\Scripts\activate.bat
    python -m pip install --quiet -r backend\requirements.txt -r backend\requirements-dev.txt
    pushd backend
    python -m pytest -q
    if errorlevel 1 (
        popd
        echo.
        echo !! Alcuni test falliscono: niente e' stato pubblicato. Correggi prima.
        pause
        exit /b 1
    )
    popd
) else (
    echo ^(salto i test: avvia run_local.bat una volta per crearli^)
)

echo.
echo ===== 2. File modificati =====
git add -A
git status --short
git diff --cached --quiet
if not errorlevel 1 (
    echo Nessuna modifica da pubblicare.
    pause
    exit /b 0
)

echo.
set /p MSG=Descrivi la modifica in una riga: 
if "%MSG%"=="" set MSG=Aggiornamento
git commit -q -m "%MSG%"

echo.
echo ===== 3. Invio a GitHub =====
git push
if errorlevel 1 (
    echo !! Push non riuscito. Controlla la connessione e riprova con:  git push
    pause
    exit /b 1
)
echo.
echo Pubblicato. Ora sul NAS:  sudo bash nas/update.sh
pause
