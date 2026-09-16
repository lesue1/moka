@echo off
setlocal EnableExtensions

REM ============================================================
REM Moka Funnel Exporter - One-click bootstrap
REM Assumes Python 3.10+ already installed and on PATH
REM ============================================================

set "WORK_DIR=%USERPROFILE%\moka-funnel-exporter"
set "GITHUB_ZIP=https://github.com/lesue1/moka/archive/refs/heads/main.zip"
set "MARKER=%WORK_DIR%\.bootstrap_done"
set "LOG=%TEMP%\moka-install.log"

echo.
echo ============================================================
echo   Moka Funnel Exporter
echo ============================================================
echo.

REM --- Step 1: download from GitHub (skip if already done) ---
if exist "%MARKER%" goto :check_venv

echo [1/3] Downloading from GitHub ...
echo [%DATE% %TIME%] download start >> "%LOG%"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ProgressPreference = 'SilentlyContinue';" ^
  "try {" ^
  "  Invoke-WebRequest -Uri '%GITHUB_ZIP' -OutFile '%WORK_DIR%\moka.zip' -UseBasicParsing" ^
  "} catch {" ^
  "  Write-Host ('[FAIL] ' + $_.Exception.Message);" ^
  "  exit 1" ^
  "}"

if errorlevel 1 goto :download_fail

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Expand-Archive -Path '%WORK_DIR%\moka.zip' -DestinationPath '%WORK_DIR%' -Force;" ^
  "Remove-Item '%WORK_DIR%\moka.zip';" ^
  "$src = '%WORK_DIR%\moka-main';" ^
  "if (Test-Path $src) {" ^
  "  Get-ChildItem -Path $src -Force | ForEach-Object {" ^
  "    Move-Item -Path $_.FullName -Destination '%WORK_DIR%' -Force" ^
  "  };" ^
  "  Remove-Item $src -Recurse -Force" ^
  "};"

echo. > "%MARKER%"
echo [OK] Downloaded and extracted.
echo [%DATE% %TIME%] download OK >> "%LOG%"

goto :install_deps

:download_fail
echo.
echo [FAIL] Download failed. Manual fallback:
echo   1. Browser: https://github.com/lesue1/moka - Code - Download ZIP
echo   2. Extract to: %WORK_DIR%
echo   3. Re-run this script
echo Log: %LOG%
pause
exit /b 1

REM --- Already downloaded - check if venv exists ---
:check_venv
if exist "%WORK_DIR%\.venv\Scripts\activate.bat" goto :start_only

:install_deps
echo.
echo [2/3] Installing dependencies (2-5 minutes on first run) ...
echo [%DATE% %TIME%] install start >> "%LOG%"

pushd "%WORK_DIR%"
call install.bat
if errorlevel 1 (
    popd
    echo.
    echo [FAIL] Dependency install failed. Check log: %LOG%
    pause
    exit /b 1
)
popd
echo [OK] Dependencies installed.

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