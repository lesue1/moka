@echo off
chcp 65001 >nul
setlocal

echo.
echo ============================================
echo   Moka 漏斗导出器 — 启动服务
echo ============================================
echo.

REM 检查 Python
where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 没检测到 Python,请先安装
    pause
    exit /b 1
)

REM 检查虚拟环境
if not exist ".venv\Scripts\activate.bat" (
    echo [错误] 没找到虚拟环境 .venv
    echo 请先双击 install.bat 装依赖
    echo.
    pause
    exit /b 1
)

REM 激活虚拟环境
call .venv\Scripts\activate.bat

echo 启动 Web 服务 ...
echo 浏览器会自动打开 http://localhost:5000
echo.
echo 关闭此窗口 = 关闭服务
echo.

REM 启动 Flask(app.py 内部会自动 webbrowser.open_new)
python app.py

echo.
echo 服务已关闭
pause