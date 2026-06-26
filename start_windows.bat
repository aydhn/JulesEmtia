@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

cd /d "%~dp0"

echo ===================================================
echo     ED Capital Quant Engine - Windows Bootstrapper
echo ===================================================
echo.

if not exist "ed_quant_engine\main.py" (
    echo [ERROR] Must be run from the repository root.
    pause
    exit /b 1
)

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Virtual environment not found. Creating .venv...
    python -m venv .venv
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo [INFO] Activating virtual environment...
call .venv\Scripts\activate.bat

echo [INFO] Upgrading pip...
python -m pip install --upgrade pip >nul 2>&1

echo [INFO] Checking dependencies...
pip install -r ed_quant_engine\requirements.txt >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies. Retrying with verbose output...
    pip install -r ed_quant_engine\requirements.txt
    pause
    exit /b 1
)

if not exist ".env" (
    echo [INFO] .env file not found. Running environment wizard...
    python scripts\env_wizard.py
    if !errorlevel! neq 0 (
        echo [ERROR] Environment wizard failed.
        pause
        exit /b 1
    )
)

echo [INFO] Running pre-flight healthcheck...
python scripts\windows_healthcheck.py
if %errorlevel% neq 0 (
    echo [ERROR] Healthcheck failed. Aborting startup.
    echo.
    echo Last 30 lines of ed_quant_engine\logs\quant_engine.log:
    echo -----------------------------------
    powershell -NoProfile -Command "if (Test-Path 'ed_quant_engine\logs\quant_engine.log') { Get-Content 'ed_quant_engine\logs\quant_engine.log' -Tail 30 } else { Write-Host '(log file not found)' }"
    echo -----------------------------------
    pause
    exit /b 1
)

echo.
echo ===================================================
echo       HEALTHCHECK PASSED. STARTING SYSTEM
echo ===================================================
echo.

set MAX_RESTARTS=10
set RESTARTS=0

:START_ENGINE
echo [INFO] Starting ED Quant Engine (restart !RESTARTS! of %MAX_RESTARTS%)...
set PYTHONPATH=%cd%\ed_quant_engine
python ed_quant_engine\main.py

if %errorlevel% equ 0 (
    echo [INFO] Engine stopped cleanly.
    goto END
)

echo.
echo [WARNING] Engine crashed with exit code %errorlevel%.
echo.
echo === Last 30 lines of ed_quant_engine\logs\quant_engine.log ===
powershell -NoProfile -Command "if (Test-Path 'ed_quant_engine\logs\quant_engine.log') { Get-Content 'ed_quant_engine\logs\quant_engine.log' -Tail 30 } else { Write-Host '(log file not found)' }"
echo ===================================================
echo.

set /a RESTARTS+=1
if !RESTARTS! gtr %MAX_RESTARTS% (
    echo [CRITICAL] Max restarts reached. Review the log output above.
    pause
    exit /b 1
)

echo [INFO] Restarting in 5 seconds...
timeout /t 5 /nobreak >nul
goto START_ENGINE

:END
echo [INFO] Process completed.
if "%JULESEMTIA_NO_PAUSE%"=="1" goto EOF
pause

:EOF
