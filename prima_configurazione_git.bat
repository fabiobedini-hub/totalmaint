@echo off
REM TotalMaint - configurazione Git (da eseguire UNA SOLA VOLTA).
REM Prepara il repository e lo carica sul tuo repository privato GitHub.
setlocal
cd /d "%~dp0"

where git >nul 2>nul
if errorlevel 1 (
    echo Git non e' installato. Scaricalo da https://git-scm.com/download/win
    echo ^(installazione con le opzioni predefinite^), poi riavvia questo file.
    pause
    exit /b 1
)

if exist ".git" (
    echo Il repository Git esiste gia'. Per le modifiche usa pubblica.bat
    pause
    exit /b 0
)

for /f "delims=" %%a in ('git config --global user.name') do set GITNAME=%%a
if "%GITNAME%"=="" (
    set /p GITNAME=Il tuo nome ^(es. Fabio Bedini^): 
    set /p GITMAIL=La tua e-mail di GitHub: 
)
if not "%GITMAIL%"=="" (
    git config --global user.name "%GITNAME%"
    git config --global user.email "%GITMAIL%"
)

git init -b main
git add -A
echo.
echo ===== File che verranno salvati su GitHub =====
git status --short
echo ================================================
echo Controlla: NON devono esserci .env, data\ o file .db
echo.
set /p OK=Va bene? (s/n): 
if /i not "%OK%"=="s" (
    rmdir /s /q .git
    echo Annullato, niente e' stato salvato.
    pause
    exit /b 1
)

git commit -q -m "TotalMaint 0.2.0 - prima versione sotto Git"
echo.
echo Ora incolla l'indirizzo del repository GitHub che hai creato
echo ^(es. https://github.com/TUONOME/totalmaint.git^)
set /p URL=Indirizzo: 
git remote add origin %URL%
git push -u origin main
if errorlevel 1 (
    echo.
    echo Push non riuscito. Controlla l'indirizzo e riprova con:  git push -u origin main
    pause
    exit /b 1
)
echo.
echo Fatto! Il codice e' su GitHub. D'ora in poi usa pubblica.bat
pause
