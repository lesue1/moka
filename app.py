"""Flask 主入口 — 给 HR 同事用的 Web 应用

同事首次使用:
  1. 双击 start.bat → 浏览器自动打开 http://localhost:5000
  2. 没 .env 时显示账号密码表单 → 同事填账号密码 → 提交
  3. 后端自动启动 Playwright 弹浏览器,账号密码已自动填好
  4. 同事只需处理可能的验证码 + 点登录 → 自动跳到 dashboard
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
    is_logged_in,
    load_jobs_cache,
    login_with_credentials,
    refresh_jobs_cache,
    save_credentials,
    verify_session_valid,
)

app = Flask(__name__)

# 简单内存缓存(防同事多次点"刷新"反复打 moka)
_cache_lock = threading.Lock()
_cache: dict | None = None
_cache_ts: float = 0.0
CACHE_TTL = 60  # 秒

# 防止同事重复点"登录"按钮并发触发多个 Playwright 实例
_browser_login_in_progress = False
_browser_login_lock = threading.Lock()


def _env_file_exists() -> bool:
    """检查 .env 文件是否存在(同事是否填过账号)"""
    from pathlib import Path

    return (Path(__file__).parent / ".env").exists()


def _trigger_browser_login() -> bool:
    """后台异步启动 Playwright 弹浏览器让同事完成登录。

    返回 True 表示已触发,False 表示正在登录中(防止并发)。
    """
    global _browser_login_in_progress
    with _browser_login_lock:
        if _browser_login_in_progress:
            return False
        _browser_login_in_progress = True

    def _run():
        global _browser_login_in_progress
        try:
            login_with_credentials(headless=False)
        except Exception:
            pass
        finally:
            _browser_login_in_progress = False

    threading.Thread(target=_run, daemon=True).start()
    return True


def _get_funnel_rows(force: bool = False) -> tuple[list[dict], list[dict]]:
    """返回 (rows, jobs)。60 秒内复用缓存。"""
    global _cache, _cache_ts

    if not force and _cache and (datetime.now().timestamp() - _cache_ts) < CACHE_TTL:
        return _cache["rows"], _cache["jobs"]

    # 1. 取职位列表(优先缓存,无则现抓)
    jobs = load_jobs_cache()
    if jobs is None:
        jobs = refresh_jobs_cache()

    # 2. 对每个职位抓漏斗
    rows = funnel_for_all_jobs(jobs)

    with _cache_lock:
        _cache = {"rows": rows, "jobs": jobs}
        _cache_ts = datetime.now().timestamp()
    return rows, jobs


@app.route("/")
def index():
    valid, reason = verify_session_valid()

    # 引导未配置的同事去填表单
    if not _env_file_exists():
        return redirect("/login")

    if not valid:
        # 有 .env 但没 session → 自动触发浏览器登录,跳到等待页
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
        # 已填过账号但 session 失效 → 引导去弹浏览器登录
        return redirect("/login-pending")

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()
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
        # 写完 .env 后跳到等待页(等待页自动触发浏览器登录)
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

    # 触发浏览器登录(幂等,已在跑的话不会重复启动)
    _trigger_browser_login()
    return render_template("login_pending.html")


@app.route("/api/login-status")
def login_status():
    """前端轮询用,检查 session 是否有效"""
    valid, reason = verify_session_valid()
    return {"logged_in": valid, "reason": reason}


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


@app.route("/health")
def health():
    valid, reason = verify_session_valid()
    return {
        "status": "ok" if valid else "session_invalid",
        "logged_in": valid,
        "reason": reason,
    }


if __name__ == "__main__":
    import webbrowser

    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", "5000"))

    # 启动后自动开浏览器(给同事的最简体验)
    def _open_browser():
        time.sleep(1.5)  # 等 Flask 起来
        webbrowser.open_new(f"http://localhost:{port}")

    threading.Thread(target=_open_browser, daemon=True).start()

    # 生产请改 waitress / gunicorn
    app.run(host=host, port=port, debug=False)