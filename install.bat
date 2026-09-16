@echo off
setlocal EnableExtensions

set "LOG=%TEMP%\moka-install.log"
echo [%DATE% %TIME%] install.bat started >> "%LOG%"

echo.
echo ============================================================
echo   Installing Python Dependencies
echo ============================================================
echo.

REM Check Python
where python >nul 2>nul
if errorlevel 1 (
    echo [FAIL] Python not found. Run bootstrap.bat first.
    echo [%DATE% %TIME%] FAIL: no python in install.bat >> "%LOG%"
    pause
    exit /b 1
)

REM Create venv if missing
if not exist ".venv\Scripts\activate.bat" (
    echo [1/3] Creating virtual environment .venv ...
    echo [%DATE% %TIME%] Creating venv >> "%LOG%"
    python -m venv .venv
    if errorlevel 1 (
        echo [FAIL] venv creation failed.
        echo [%DATE% %TIME%] FAIL: venv creation >> "%LOG%"
        pause
        exit /b 1
    )
) else (
    echo [1/3] venv exists, skip.
)

REM Activate venv
call .venv\Scripts\activate.bat

REM Install pip deps
echo.
echo [2/3] Installing Python packages (using Tsinghua mirror for speed) ...
echo [%DATE% %TIME%] pip install >> "%LOG%"
python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple --quiet
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --quiet
if errorlevel 1 (
    echo.
    echo [WARN] Tsinghua mirror failed, retrying with official PyPI ...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [FAIL] pip install failed.
        echo Check: network / VPN / antivirus
        echo [%DATE% %TIME%] FAIL: pip install >> "%LOG%"
        pause
        exit /b 1
    )
)
echo [OK] Python packages installed.

REM Install Playwright browser
echo.
echo [3/3] Downloading Playwright Chromium (~150MB, 2-5 minutes) ...
echo [%DATE% %TIME%] playwright install >> "%LOG%"
playwright install chromium
if errorlevel 1 (
    echo [WARN] Playwright browser download failed.
    echo start.bat will retry on next run.
    echo [%DATE% %TIME%] WARN: playwright install failed >> "%LOG%"
)

echo.
echo ============================================================
echo   Installation Complete
echo ============================================================
echo.
echo Next: run start.bat (or bootstrap.bat to auto-start)
echo.
echo [%DATE% %TIME%] install.bat done >> "%LOG%"
pause