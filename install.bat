@echo off
chcp 65001 >nul
setlocal

echo.
echo ============================================
echo   Moka 漏斗导出器 — 一次性安装
echo ============================================
echo.

REM 检查 Python
where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 没检测到 Python
    echo.
    echo 请先下载安装 Python 3.10 或更高版本:
    echo   https://www.python.org/downloads/
    echo.
    echo 安装时务必勾选 "Add Python to PATH" 这一项
    echo (默认没勾,没勾就废了)
    echo.
    pause
    exit /b 1
)

echo 检测到 Python:
python --version
echo.

REM 创建虚拟环境(如果不存在)
if not exist ".venv\Scripts\activate.bat" (
    echo [1/3] 创建虚拟环境 .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败
        pause
        exit /b 1
    )
) else (
    echo [1/3] 虚拟环境已存在,跳过
)

REM 激活虚拟环境
call .venv\Scripts\activate.bat

REM 安装依赖
echo.
echo [2/3] 安装 Python 依赖(用清华镜像加速)...
python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple --quiet
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --quiet
if errorlevel 1 (
    echo.
    echo [警告] 清华镜像失败,尝试官方源...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败
        echo 可能原因:网络问题、公司防火墙、需要挂 VPN
        pause
        exit /b 1
    )
)

REM 装 Playwright 浏览器
echo.
echo [3/3] 下载 Playwright Chromium 浏览器(约 150MB,可能等 2-5 分钟)...
playwright install chromium
if errorlevel 1 (
    echo [警告] Playwright 浏览器下载失败
    echo 之后启动 start.bat 会重新尝试
)

echo.
echo ============================================
echo   安装完成
echo ============================================
echo.
echo 下一步:双击 start.bat 启动服务
echo 浏览器会自动打开 http://localhost:5000
echo 首次会要求你填 Moka 账号密码
echo.
pause