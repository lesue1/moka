@echo off
setlocal EnableExtensions

REM Install Python deps. Skips work if venv already has them.
REM Called by bootstrap.bat or can be run standalone.

if not exist ".venv\Scripts\activate.bat" (
    echo Creating venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [FAIL] venv creation failed.
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate.bat

echo Installing Python packages ...
python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple --quiet
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --quiet
if errorlevel 1 (
    echo Tsinghua mirror failed, retrying with PyPI ...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [FAIL] pip install failed. Network/VPN issue?
        pause
        exit /b 1
    )
)

echo Installing Playwright browser (~150MB) ...
playwright install chromium
echo [OK] Done.
pause