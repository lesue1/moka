@echo off
REM ============================================================
REM Moka Funnel Exporter - One-click Bootstrap
REM For HR colleagues without Python env
REM ============================================================
REM This script is intentionally ASCII-only to avoid
REM Windows GBK cmd encoding issues that garble UTF-8 chars.
REM All user-facing messages use English + status codes.
REM ============================================================

REM Force console to NOT close immediately even on error
setlocal EnableExtensions

REM Log file for post-mortem if window closes
set "LOG=%TEMP%\moka-install.log"
echo [%DATE% %TIME%] Bootstrap started > "%LOG%"

REM --- Pre-check: if .bat file association is broken, fix it ---
REM Symptom: double-clicking .bat shows "Windows cannot find file '.bat'"
REM Fix: re-register .bat as a cmd.exe-runnable file type.
assoc .bat 2>nul | findstr /C:".bat=batfile" >nul
if errorlevel 1 (
    echo [WARN] .bat file association appears broken - fixing ...
    assoc .bat=batfile >nul 2>&1
    ftype batfile=cmd.exe /c "%1" %* >nul 2>&1
    echo [%DATE% %TIME%] Fixed .bat association >> "%LOG%"
)

REM --- Step 1: Check Python ---
echo.
echo ============================================================
echo   Moka Funnel Exporter - Bootstrap
echo ============================================================
echo.
echo [1/4] Checking Python ...
echo [%DATE% %TIME%] Step 1: check python >> "%LOG%"

where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo [FAIL] Python not found on this computer.
    echo.
    echo Opening python.org download page in your browser ...
    echo.
    echo IMPORTANT: During Python installation, check the box:
    echo   [x] Add Python to PATH
    echo.
    echo After installing Python, RE-RUN this script (bootstrap.bat).
    echo.
    echo Full log: %LOG%
    echo [%DATE% %TIME%] FAIL: python not found >> "%LOG%"

    REM Auto-open Python download page
    start "" "https://www.python.org/downloads/"

    echo.
    echo After installing Python, press any key to retry ...
    pause >nul

    REM Re-check after pause (user may have installed during pause)
    where python >nul 2>nul
    if errorlevel 1 (
        echo.
        echo Python still not found. Install it first, then run again.
        echo [%DATE% %TIME%] FAIL: python still missing after prompt >> "%LOG%"
        pause >nul
        exit /b 1
    )
)

python --version
echo [%DATE% %TIME%] Python OK >> "%LOG%"

REM --- Step 2: Prepare working directory ---
set "WORK_DIR=%USERPROFILE%\moka-funnel-exporter"
set "GITHUB_ZIP_URL=https://github.com/lesue1/moka/archive/refs/heads/main.zip"
set "MARKER=%WORK_DIR%\.bootstrap_done"

echo.
echo [2/4] Working directory: %WORK_DIR%
echo [%DATE% %TIME%] Step 2: prepare dir >> "%LOG%"

if not exist "%WORK_DIR%" mkdir "%WORK_DIR%"

REM --- Step 3: Download from GitHub (skip if already done) ---
if exist "%MARKER%" goto :check_venv

echo.
echo [3/4] Downloading from GitHub ...
echo       (If this fails, see the manual steps at the bottom)
echo [%DATE% %TIME%] Step 3: download >> "%LOG%"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ProgressPreference = 'SilentlyContinue';" ^
  "try {" ^
  "  Invoke-WebRequest -Uri '%GITHUB_ZIP_URL%' -OutFile '%WORK_DIR%\moka.zip' -UseBasicParsing" ^
  "} catch {" ^
  "  Write-Host ('[FAIL] Download error: ' + $_.Exception.Message);" ^
  "  exit 1" ^
  "}"

if errorlevel 1 (
    echo.
    echo [FAIL] Download failed.
    echo.
    echo Manual fallback:
    echo   1. Open browser, go to https://github.com/lesue1/moka
    echo   2. Click green "Code" button - "Download ZIP"
    echo   3. Extract ZIP to: %WORK_DIR%
    echo   4. Re-run this script
    echo.
    echo Full log: %LOG%
    echo [%DATE% %TIME%] FAIL: download >> "%LOG%"
    echo.
    echo Press any key to close ...
    pause >nul
    exit /b 1
)

echo.
echo Extracting ...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Expand-Archive -Path '%WORK_DIR%\moka.zip' -DestinationPath '%WORK_DIR%' -Force;" ^
  "Remove-Item '%WORK_DIR%\moka.zip';" ^
  "$source = '%WORK_DIR%\moka-main';" ^
  "if (Test-Path $source) {" ^
  "  Get-ChildItem -Path $source -Force | ForEach-Object {" ^
  "    Move-Item -Path $_.FullName -Destination '%WORK_DIR%' -Force" ^
  "  };" ^
  "  Remove-Item $source -Recurse -Force" ^
  "};"

REM Mark bootstrap done (skip download next time)
echo. > "%MARKER%"
echo [OK] Downloaded and extracted.
echo [%DATE% %TIME%] Download OK >> "%LOG%"

goto :install_deps

REM --- Already bootstrapped - check if venv exists ---
:check_venv
if exist "%WORK_DIR%\.venv\Scripts\activate.bat" goto :start_only
echo.
echo [WARN] .venv missing, will reinstall dependencies ...
echo [%DATE% %TIME%] Reinstall needed >> "%LOG%"

:install_deps
echo.
echo [4/4] Installing dependencies (this may take 2-5 minutes) ...
echo [%DATE% %TIME%] Step 4: install deps >> "%LOG%"

pushd "%WORK_DIR%"
call install.bat
set "INSTALL_RC=%errorlevel%"
popd

if not "%INSTALL_RC%"=="0" (
    echo.
    echo [FAIL] Dependency installation failed.
    echo.
    echo Possible causes:
    echo   - No internet / VPN required
    echo   - Antivirus blocking pip
    echo.
    echo Full log: %LOG%
    echo [%DATE% %TIME%] FAIL: install rc=%INSTALL_RC% >> "%LOG%"
    echo.
    echo Press any key to close ...
    pause >nul
    exit /b %INSTALL_RC%
)

echo [OK] Dependencies installed.
echo [%DATE% %TIME%] Install OK >> "%LOG%"

:start_only
echo.
echo ============================================================
echo   Starting Web Service
echo ============================================================
echo.
echo Your browser will open automatically to:
echo   http://localhost:5000
echo.
echo First time? It will ask for your Moka account/password.
echo Close this window to stop the service.
echo.
echo [%DATE% %TIME%] Starting service >> "%LOG%"

pushd "%WORK_DIR%"
call start.bat
popd

echo [%DATE% %TIME%] Service stopped >> "%LOG%"