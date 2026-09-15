@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo.
echo ============================================
echo   Moka 漏斗导出器 — 一键启动
echo ============================================
echo.
echo 这个脚本会:
echo   1. 从 GitHub 下载最新代码到你的用户目录
echo   2. 自动装 Python 依赖(约 2-5 分钟)
echo   3. 自动启动 Web 服务,浏览器会弹出
echo.
echo 首次会让你填 Moka 账号密码
echo.

REM 工作目录 = %USERPROFILE%\moka-funnel-exporter(标准位置,不用关心从哪运行)
set "WORK_DIR=%USERPROFILE%\moka-funnel-exporter"
set "GITHUB_ZIP_URL=https://github.com/lesue1/moka/archive/refs/heads/main.zip"
set "MARKER=%WORK_DIR%\.bootstrap_done"

REM 检测是否已经 bootstrap 过(跳过下载)
if exist "%MARKER%" goto :skip_download

echo [1/4] 创建工作目录 %WORK_DIR% ...
if not exist "%WORK_DIR%" mkdir "%WORK_DIR%"

echo.
echo [2/4] 从 GitHub 下载项目(可能等 5-30 秒)...
echo       网络不通就手动下载:浏览器打开 https://github.com/lesue1/moka
echo       点绿色 Code → Download ZIP → 解压到 %WORK_DIR%
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ProgressPreference = 'SilentlyContinue';" ^
  "try {" ^
  "  Invoke-WebRequest -Uri '%GITHUB_ZIP_URL%' -OutFile '%WORK_DIR%\moka.zip' -UseBasicParsing" ^
  "} catch {" ^
  "  Write-Host ('下载失败:' + $_.Exception.Message);" ^
  "  Write-Host '公司可能要挂 VPN,或手动下载';" ^
  "  exit 1" ^
  "}"

if errorlevel 1 (
    echo.
    echo [错误] 下载失败
    pause
    exit /b 1
)

echo.
echo [3/4] 解压 ...
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

REM 标记已 bootstrap(下次跳过下载)
echo. > "%MARKER%"

:skip_download
echo.
echo [4/4] 装依赖 ...
echo.

pushd "%WORK_DIR%"
call install.bat
set "INSTALL_RC=%errorlevel%"
popd

if not "%INSTALL_RC%"=="0" (
    echo.
    echo [错误] install.bat 退出码 %INSTALL_RC%
    pause
    exit /b %INSTALL_RC%
)

echo.
echo ============================================
echo   启动服务
echo ============================================
echo 浏览器会自动打开 http://localhost:5000
echo 首次会让你填 Moka 账号密码
echo 关闭此窗口 = 关闭服务
echo.

pushd "%WORK_DIR%"
call start.bat
popd