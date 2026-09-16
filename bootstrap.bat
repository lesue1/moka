@echo off
setlocal

REM ============================================================
REM Moka Funnel Exporter - One-click bootstrap
REM Assumes Python 3.10+ already installed and on PATH
REM ============================================================

set "WORK_DIR=%USERPROFILE%\moka-funnel-exporter"
set "GITHUB_ZIP=https://github.com/lesue1/moka/archive/refs/heads/main.zip"
set "MARKER=%WORK_DIR%\.bootstrap_done"
set "LOG=%TEMP%\moka-install.log"

REM Clear log on each run
echo [%DATE% %TIME%] Bootstrap started > "%LOG%"

echo.
echo ============================================================
echo   Moka Funnel Exporter - Bootstrap
echo ============================================================
echo.

REM Force window to stay open even on early exit
REM (Prevents the "flash and disappear" symptom)
if not "%~1"=="NO_PAUSE" pause

echo [%DATE% %TIME%] Step 1: prepare dir >> "%LOG%"
if not exist "%WORK_DIR%" mkdir "%WORK_DIR%"

REM --- Step 1: download from GitHub (skip if already done) ---
if exist "%MARKER%" goto :check_venv

echo [1/3] Downloading from GitHub ...
echo.
echo     (If stuck here for more than 60 seconds,
echo     your company may block GitHub.
echo     See %LOG% for details.)
echo.

REM Use a temp .ps1 file instead of inline multi-line powershell.
REM This avoids cmd caret-line-continuation parsing issues.
set "PS1=%TEMP%\moka-download.ps1"
> "%PS1%" echo try {
>> "%PS1%" echo   $ProgressPreference = 'SilentlyContinue'
>> "%PS1%" echo   Invoke-WebRequest -Uri '%GITHUB_ZIP%' -OutFile '%WORK_DIR%\moka.zip' -UseBasicParsing
>> "%PS1%" echo } catch {
>> "%PS1%" echo   Write-Host ('[FAIL] ' + $_.Exception.Message)
>> "%PS1%" echo   exit 1
>> "%PS1%" echo }

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
if errorlevel 1 goto :download_fail
del "%PS1%" 2>nul

echo.
echo [2/3] Extracting ...
set "PS1=%TEMP%\moka-extract.ps1"
> "%PS1%" echo Expand-Archive -Path '%WORK_DIR%\moka.zip' -DestinationPath '%WORK_DIR%' -Force
>> "%PS1%" echo Remove-Item '%WORK_DIR%\moka.zip'
>> "%PS1%" echo $src = '%WORK_DIR%\moka-main'
>> "%PS1%" echo if (Test-Path $src) {
>> "%PS1%" echo   Get-ChildItem -Path $src -Force ^| ForEach-Object {
>> "%PS1%" echo     Move-Item -Path $_.FullName -Destination '%WORK_DIR%' -Force
>> "%PS1%" echo   }
>> "%PS1%" echo   Remove-Item $src -Recurse -Force
>> "%PS1%" echo }

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
if errorlevel 1 (
    del "%PS1%" 2>nul
    echo.
    echo [FAIL] Extract failed.
    echo Log: %LOG%
    pause
    exit /b 1
)
del "%PS1%" 2>nul

REM Mark bootstrap done (skip download next time)
echo. > "%MARKER%"
echo [OK] Downloaded and extracted.
echo [%DATE% %TIME%] Download OK >> "%LOG%"

goto :install_deps

:download_fail
del "%PS1%" 2>nul
echo.
echo [FAIL] Download failed. Manual fallback:
echo   1. Browser: https://github.com/lesue1/moka - Code - Download ZIP
echo   2. Extract ZIP to: %WORK_DIR%
echo   3. Re-run this script
echo Log: %LOG%
pause
exit /b 1

REM --- Already downloaded - check if venv exists ---
:check_venv
if exist "%WORK_DIR%\.venv\Scripts\activate.bat" goto :start_only

:install_deps
echo.
echo [3/3] Installing dependencies (2-5 minutes on first run) ...
echo.
echo     This will: create venv, pip install, download Chromium
echo     See %LOG% for progress
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