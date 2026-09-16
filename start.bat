@echo off
setlocal EnableExtensions

REM Start the Flask web service. App auto-opens browser.

if not exist ".venv\Scripts\activate.bat" (
    echo [FAIL] .venv missing. Run bootstrap.bat first.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
python app.py
pause