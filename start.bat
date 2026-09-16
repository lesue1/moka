@echo off
setlocal EnableExtensions

set "LOG=%TEMP%\moka-install.log"

echo.
echo ============================================================
echo   Starting Moka Funnel Exporter
echo ============================================================
echo.
echo [%DATE% %TIME%] start.bat invoked >> "%LOG%"

REM Check Python
where python >nul 2>nul
if errorlevel 1 (
    echo [FAIL] Python not found.
    echo Install Python 3.10+ from python.org first.
    echo [%DATE% %TIME%] FAIL: no python in start.bat >> "%LOG%"
    pause
    exit /b 1
)

REM Check venv
if not exist ".venv\Scripts\activate.bat" (
    echo [FAIL] Virtual environment .venv not found.
    echo Run bootstrap.bat first to install dependencies.
    echo [%DATE% %TIME%] FAIL: no venv in start.bat >> "%LOG%"
    pause
    exit /b 1
)

REM Activate venv
call .venv\Scripts\activate.bat

echo Starting web service ...
echo Browser will open automatically to http://localhost:5000
echo Close this window to stop the service.
echo.
echo [%DATE% %TIME%] Launching python app.py >> "%LOG%"

python app.py

echo.
echo [%DATE% %TIME%] Service exited >> "%LOG%"
pause