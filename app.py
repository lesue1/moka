"""Flask 主入口 — 给 HR 同事用的 Web 应用

同事首次使用:
  1. 双击 start.bat -> 浏览器自动打开 http://localhost:5000
  2. 没 .env 时显示账号密码表单 -> 同事填账号密码 -> 提交
  3. 后端自动启动 Playwright 弹浏览器,账号密码已自动填好
  4. 同事只需处理可能的验证码 + 点登录 -> 自动跳到 dashboard
"""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, Response, redirect, render_template, request

load_dotenv()

from exporter import build_workbook
from funnel import funnel_for_all_jobs
from moka_client import (
    MokaError,
    delete_credentials,
    load_jobs_cache,
    login_with_credentials,
    refresh_jobs_cache,
    save_credentials,
    verify_session_valid,
)

app = Flask(__name__)

# 漏斗数据内存缓存(防同事多次点刷新反复打 moka)
_cache_lock = threading.Lock()
_cache: dict | None = None
_cache_ts: float = 0.0
CACHE_TTL = 60  # 秒

# Playwright 浏览器登录线程的状态 + 错误信息
_browser_login_in_progress = False
_browser_login_error: str | None = None  # 给前端显示用
_browser_login_lock = threading.Lock()


def _env_file_exists() -> bool:
    """检查 .env 文件是否存在(同事是否填过账号)"""
    from pathlib import Path

    return (Path(__file__).parent / ".env").exists()


def _trigger_browser_login() -> bool:
    """后台异步启动 Playwright 弹浏览器让同事完成登录。

    返回 True 表示已触发,False 表示正在登录中(防止并发)。
    """
    global _browser_login_in_progress, _browser_login_error
    with _browser_login_lock:
        if _browser_login_in_progress:
            return False
        _browser_login_in_progress = True
        _browser_login_error = None  # 重置错误

    def _run():
        global _browser_login_in_progress, _browser_login_error
        try:
            login_with_credentials(headless=False)
        except Exception as e:
            # 之前静默吞掉 — 现在写日志 + 暴露给前端,同事能看到为啥失败
            _browser_login_error = str(e)
            from pathlib import Path
            log = Path(os.getenv("TEMP", "/tmp")) / "moka-install.log"
            try:
                with open(log, "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now().isoformat()}] login error: {e}\n")
            except Exception:
                pass
        finally:
            _browser_login_in_progress = False

    threading.Thread(target=_run, daemon=True).start()
    return True


def _venv_healthy() -> bool:
    """检查 .venv 是否真的能 import flask(防半残 venv)。"""
    from pathlib import Path
    venv_python = Path(__file__).parent / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        return False
    try:
        import subprocess
        r = subprocess.run(
            [str(venv_python), "-c", "import flask, requests, openpyxl, playwright"],
            capture_output=True, timeout=10,
        )
        return r.returncode == 0
    except Exception:
        return False


def _get_funnel_rows(force: bool = False) -> tuple[list[dict], list[dict]]:
    """返回 (rows, jobs)。60 秒内复用缓存。"""
    global _cache, _cache_ts

    if not force and _cache and (time.time() - _cache_ts) < CACHE_TTL:
        return _cache["rows"], _cache["jobs"]

    # 1. 取职位列表(优先缓存,无则现抓)
    jobs = load_jobs_cache()
    if jobs is None:
        jobs = refresh_jobs_cache()

    # 2. 对每个职位抓漏斗
    rows = funnel_for_all_jobs(jobs)

    with _cache_lock:
        _cache = {"rows": rows, "jobs": jobs}
        _cache_ts = time.time()
    return rows, jobs


@app.route("/")
def index():
    if not _env_file_exists():
        return redirect("/login")

    valid, reason = verify_session_valid()
    if not valid:
        _trigger_browser_login()
        return redirect("/login-pending")

    try:
        rows, jobs = _get_funnel_rows(force=request.args.get("force") == "1")
    except MokaError as e:
        return render_template("error.html", error=f"Moka 接口错误:{e}"), 500
    except Exception as e:
        return render_template("error.html", error=str(e)), 500

    return render_template(
        "index.html",
        rows=rows,
        job_count=len(rows),
        total_applications=sum(r["total"] for r in rows),
        fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    """账号密码表单(只有没 .env 时才显示)"""
    if _env_file_exists():
        return redirect("/login-pending")

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        # H1 修复: 密码只去 \n 不去空格 — HR 常带空格复制粘贴,会被默默截掉
        password = (request.form.get("password") or "").rstrip("\n\r")
        if not username or not password:
            return render_template(
                "login.html",
                error="账号和密码都不能为空",
                username=username,
            )
        try:
            save_credentials(username, password)
        except Exception as e:
            return render_template(
                "login.html",
                error=f"保存账号失败:{e}",
                username=username,
            )
        return redirect("/login-pending")

    return render_template("login.html", error=None, username="")


@app.route("/login-pending")
def login_pending():
    """等同事在弹出的浏览器里完成登录(可能含验证码)"""
    if not _env_file_exists():
        return redirect("/login")

    valid, _ = verify_session_valid()
    if valid:
        return redirect("/")

    _trigger_browser_login()
    return render_template("login_pending.html")


@app.route("/api/login-status")
def login_status():
    """前端轮询用,检查 session 是否有效 + 暴露登录错误信息(替代之前的静默吞错)"""
    valid, reason = verify_session_valid()
    with _browser_login_lock:
        in_progress = _browser_login_in_progress
        err = _browser_login_error
    return {
        "logged_in": valid,
        "reason": reason,
        "in_progress": in_progress,
        "error": err,
    }


@app.route("/api/reset-env", methods=["POST"])
def reset_env():
    """删除 .env,让同事能重新填账号(不是改密码 — 密码是 moka 的事)"""
    deleted = delete_credentials()
    return {"deleted": deleted}


@app.route("/export.xlsx")
def export_excel():
    valid, reason = verify_session_valid()
    if not valid:
        return Response(f"Moka 登录态失效:{reason}", status=503)
    try:
        rows, _ = _get_funnel_rows()
    except MokaError as e:
        return Response(f"Moka 接口错误:{e}", status=500)
    except Exception as e:
        return Response(f"导出失败:{e}", status=500)

    data = build_workbook(rows)
    filename = f"moka-funnel-{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx"
    return Response(
        data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


if __name__ == "__main__":
    import webbrowser

    # C1 修复: 默认只监听 127.0.0.1 (本机),同事在公司 WiFi 不会被别人访问
    # 想让局域网同事访问才需要改 .env 里 FLASK_HOST=0.0.0.0
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", "5000"))

    # H6 修复: 端口占用检测,防止双击 start.bat 两次崩端口
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, port))
        s.close()
    except OSError:
        print(f"[FAIL] Port {port} already in use. Maybe already running?")
        print("If a previous instance crashed, wait 30 seconds or restart your computer.")
        import sys
        sys.exit(1)

    # H2 修复: 检查 .venv 是否真的能 import(防半残 venv)
    if not _venv_healthy():
        print("[FAIL] .venv is broken or missing. Run bootstrap.bat to reinstall.")
        print("Log: %TEMP%\\moka-install.log")
        import sys
        sys.exit(1)

    # 启动后自动开浏览器(给同事的最简体验)
    def _open_browser():
        time.sleep(1.5)
        webbrowser.open_new(f"http://localhost:{port}")

    threading.Thread(target=_open_browser, daemon=True).start()

    # 生产请改 waitress / gunicorn
    app.run(host=host, port=port, debug=False)