@echo off
REM ============================================================
REM Moka Funnel Exporter - One-click bootstrap
REM Uses only curl + tar (both built into Windows 10 1803+)
REM Avoids PowerShell Invoke-WebRequest which fails silently
REM on some Windows 10 builds with non-ASCII user paths.
REM ============================================================

setlocal
set "WORK_DIR=%USERPROFILE%\moka-funnel-exporter"
set "GITHUB_ZIP=https://github.com/lesue1/moka/archive/refs/heads/main.zip"
set "MARKER=%WORK_DIR%\.bootstrap_done"
set "LOG=%TEMP%\moka-install.log"

echo [%DATE% %TIME%] Bootstrap started > "%LOG%"

echo.
echo ============================================================
echo   Moka Funnel Exporter - Bootstrap
echo ============================================================
echo.

REM Verify curl is available (Windows 10 1803+)
where curl >nul 2>nul
if errorlevel 1 (
    echo [FAIL] curl.exe not found. Need Windows 10 1803 or newer.
    echo This script uses curl + tar to avoid PowerShell quirks.
    pause
    exit /b 1
)

REM Ensure target dir exists
if not exist "%WORK_DIR%" mkdir "%WORK_DIR%" 2>nul

REM --- Step 1: download from GitHub (skip if already done) ---
if exist "%MARKER%" goto :check_venv

echo [1/3] Downloading from GitHub ...
echo [%DATE% %TIME%] download start >> "%LOG%"

curl -sSL -o "%WORK_DIR%\moka.zip" "%GITHUB_ZIP%"
if errorlevel 1 (
    echo.
    echo [FAIL] curl download failed (network or SSL issue).
    echo Common causes:
    echo   - No internet
    echo   - Company blocks github.com
    echo   - SSL certificate problem
    echo.
    echo Manual fallback:
    echo   1. Browser: https://github.com/lesue1/moka - Code - Download ZIP
    echo   2. Extract ZIP to: %WORK_DIR%
    echo   3. Re-run this script
    echo Log: %LOG%
    pause
    exit /b 1
)

REM Verify the download is actually a zip (not 404 HTML page)
if not exist "%WORK_DIR%\moka.zip" (
    echo [FAIL] Download produced no file.
    pause
    exit /b 1
)

REM Quick sanity check - zip files start with PK (hex 50 4B)
for %%I in ("%WORK_DIR%\moka.zip") do set "SIZE=%%~zI"
if "%SIZE%" LSS "1000" (
    echo [FAIL] Downloaded file too small (%SIZE% bytes), probably an error page.
    type "%WORK_DIR%\moka.zip" 2>nul
    del "%WORK_DIR%\moka.zip"
    pause
    exit /b 1
)
echo [%DATE% %TIME%] download OK size=%SIZE% >> "%LOG%"

echo.
echo [2/3] Extracting ...
tar -xf "%WORK_DIR%\moka.zip" -C "%WORK_DIR%"
if errorlevel 1 (
    echo [FAIL] tar extract failed.
    del "%WORK_DIR%\moka.zip" 2>nul
    pause
    exit /b 1
)

REM Flatten moka-main/* into WORK_DIR
if exist "%WORK_DIR%\moka-main" (
    robocopy "%WORK_DIR%\moka-main" "%WORK_DIR%" /E /MOVE /NFL /NDL /NJH /NJS >nul 2>&1
    rmdir "%WORK_DIR%\moka-main" 2>nul
)

del "%WORK_DIR%\moka.zip" 2>nul
echo. > "%MARKER%"
echo [OK] Downloaded and extracted.
echo [%DATE% %TIME%] extract OK >> "%LOG%"

goto :install_deps

REM --- Already downloaded - check if venv exists ---
:check_venv
if exist "%WORK_DIR%\.venv\Scripts\activate.bat" goto :start_only

:install_deps
echo.
echo [3/3] Installing dependencies (2-5 minutes on first run) ...
echo [%DATE% %TIME%] install start >> "%LOG%"

pushd "%WORK_DIR%"
call install.bat
set "INSTALL_RC=%errorlevel%"
popd

if not "%INSTALL_RC%"=="0" (
    echo.
    echo [FAIL] Dependency install failed.
    echo Log: %LOG%
    pause
    exit /b %INSTALL_RC%
)

echo [OK] Dependencies installed.
echo [%DATE% %TIME%] install OK >> "%LOG%"

:start_only
echo.
echo ============================================================
echo   Starting service
echo ============================================================
echo Browser will open at http://localhost:5000
echo First run: enter your Moka account/password in the page.
echo Close this window to stop the service.
echo.

pushd "%WORK_DIR%"
call start.bat
popd

pause